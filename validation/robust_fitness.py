from dataclasses import dataclass
from statistics import median, stdev
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import traceback
import pandas as pd

from validation.episodes import EpisodeSampler, RegimeTagger, slice_episode, EpisodeSpec

if TYPE_CHECKING:
    from validation.evaluation import StrategyEvaluationResult

WORST_FITNESS_THRESHOLD = -0.5
WORST_CASE_PENALTY = 0.5
DISPERSION_THRESHOLD = 0.3
DISPERSION_PENALTY = 0.25
LUCKY_SPIKE_THRESHOLD = 0.6  # best episode accounts for >60% of total positive fitness
LUCKY_SPIKE_PENALTY = 0.2


def _collect_debug_stats(strategy: Any, episode_df: Any, result: Any) -> Dict[str, Any]:
    """Collect no-trade autopsy diagnostics.

    Args:
        strategy: Strategy graph
        episode_df: Episode data
        result: Evaluation result

    Returns:
        Dict with diagnostic counts
    """
    from graph.executor import GraphExecutor

    debug_stats = {
        "bars_in_episode": len(episode_df),
        "bars_after_warmup": 0,
        "signal_true_count": 0,
        "entries_attempted": 0,
        "entries_blocked_by_risk": 0,
        "orders_submitted": 0,
        "fills": 0,
        "exits": 0,
        "feature_nan_pct": {},
        "key_thresholds": {},
    }

    try:
        # Execute strategy to get signals
        executor = GraphExecutor()
        context = executor.execute(strategy, episode_df)

        # Get orders config
        orders_key = list(strategy.outputs.values())[0]
        orders_config = context.get(orders_key, {})

        # Count signal trues
        entry_signal = orders_config.get('entry_signal')
        if entry_signal is not None and hasattr(entry_signal, '__len__'):
            debug_stats["signal_true_count"] = int(entry_signal.sum()) if hasattr(entry_signal, 'sum') else 0

        exit_signal = orders_config.get('exit_signal')
        if exit_signal is not None and hasattr(exit_signal, '__len__'):
            debug_stats["exits"] = int(exit_signal.sum()) if hasattr(exit_signal, 'sum') else 0

        # Extract trade count from result
        n_trades = 0
        if hasattr(result, 'validation_report'):
            # Try multiple possible keys for trade counts
            if "train_metrics" in result.validation_report:
                n_trades = result.validation_report.get("train_metrics", {}).get("trades", 0)
            elif "train" in result.validation_report:
                n_trades = result.validation_report.get("train", {}).get("n_trades", 0)
            elif "performance" in result.validation_report:
                n_trades = result.validation_report.get("performance", {}).get("n_trades", 0)
            elif "holdout_metrics" in result.validation_report:
                n_trades = result.validation_report.get("holdout_metrics", {}).get("trades", 0)

        debug_stats["fills"] = n_trades

        # Check for NaN percentages in key features
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in episode_df.columns or (hasattr(episode_df, 'index') and col == episode_df.index.name):
                if col in episode_df.columns:
                    nan_pct = episode_df[col].isna().sum() / len(episode_df) * 100
                    debug_stats["feature_nan_pct"][col] = round(nan_pct, 2)

        # Try to extract computed features from context
        for node_id, value in context.items():
            if isinstance(value, pd.Series) and len(value) == len(episode_df):
                nan_pct = value.isna().sum() / len(value) * 100
                if nan_pct > 0:
                    debug_stats["feature_nan_pct"][node_id] = round(nan_pct, 2)

    except Exception:
        # If debug stats collection fails, just return what we have
        pass

    return debug_stats


@dataclass
class RobustEpisodeResult:
    episode_spec: EpisodeSpec
    episode_fitness: float
    decision: str
    kill_reason: List[str]
    tags: Dict[str, str]
    error_details: Optional[Dict[str, str]] = None  # Track execution failures
    debug_stats: Optional[Dict[str, Any]] = None  # No-trade autopsy diagnostics


@dataclass
class RobustAggregateResult:
    aggregated_fitness: float
    median_fitness: float
    worst_fitness: float
    best_fitness: float
    std_fitness: float
    worst_case_penalty: float
    dispersion_penalty: float
    single_regime_penalty: float
    lucky_spike_penalty: float
    episodes: List[RobustEpisodeResult]
    regime_coverage: Dict[str, Any]  # Per-regime statistics
    n_trades_per_episode: List[int]  # Track trades per episode


def evaluate_strategy_on_episodes(
    strategy: Any,
    data: Any,
    n_episodes: int = 8,
    min_months: int = 6,
    max_months: int = 12,
    min_bars: int = 100,
    seed: Optional[int] = None,
    initial_capital: float = 100000.0,
    sampling_mode: str = "random",
    min_trades_per_episode: int = 3,
    regime_penalty_weight: float = 0.3,
    abort_on_all_failures: bool = True,
) -> RobustAggregateResult:
    # Import here to avoid circular dependency
    from validation.evaluation import evaluate_strategy

    sampler = EpisodeSampler(seed=seed)
    episodes = sampler.sample_episodes(
        df=data,
        n_episodes=n_episodes,
        min_months=min_months,
        max_months=max_months,
        min_bars=min_bars,
        sampling_mode=sampling_mode,
    )
    tagger = RegimeTagger()

    episode_results: List[RobustEpisodeResult] = []
    fitnesses: List[float] = []
    n_trades_list: List[int] = []

    for spec in episodes:
        episode_df = slice_episode(data, spec.start_ts, spec.end_ts)
        history_df = data.loc[: spec.start_ts]

        # Tag if not already tagged (stratified sampling pre-tags)
        if not spec.regime_tags:
            tags = tagger.tag_episode(episode_df, history_df=history_df)
            spec.regime_tags = tags
        else:
            tags = spec.regime_tags

        error_details = None
        debug_stats = None
        try:
            result = evaluate_strategy(strategy, episode_df, initial_capital=initial_capital)
            fitness = result.fitness
            decision = result.decision
            kill_reason = result.kill_reason

            # Extract trade count from validation report
            n_trades = 0
            if "train" in result.validation_report:
                n_trades = result.validation_report.get("train", {}).get("n_trades", 0)
            elif "performance" in result.validation_report:
                n_trades = result.validation_report.get("performance", {}).get("n_trades", 0)

            # Collect debug stats for no-trade autopsy
            debug_stats = _collect_debug_stats(strategy, episode_df, result)

        except Exception as e:
            # Capture failure details for debugging
            fitness = -1.0
            decision = "kill"
            kill_reason = ["episode_failure"]
            n_trades = 0

            error_details = {
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "traceback_snippet": ''.join(traceback.format_exception(type(e), e, e.__traceback__)[-5:])
            }

            # Still try to collect debug stats
            try:
                debug_stats = _collect_debug_stats(strategy, episode_df, None)
            except:
                pass

        episode_results.append(
            RobustEpisodeResult(
                episode_spec=spec,
                episode_fitness=fitness,
                decision=decision,
                kill_reason=kill_reason,
                tags=tags,
                error_details=error_details,
                debug_stats=debug_stats,
            )
        )
        fitnesses.append(fitness)
        n_trades_list.append(n_trades)

    # Check if ALL episodes failed (critical integration error)
    all_failed = all(ep.error_details is not None for ep in episode_results)
    if all_failed and abort_on_all_failures:
        # Collect error details for debugging
        error_summary = "\n".join([
            f"  Episode {i+1}: {ep.error_details['exception_type']}: {ep.error_details['exception_message']}"
            for i, ep in enumerate(episode_results) if ep.error_details
        ][:3])  # Show first 3

        raise RuntimeError(
            f"Phase 3 evaluation failed on ALL {len(episode_results)} episodes. "
            f"This indicates a critical integration error.\n"
            f"Sample errors:\n{error_summary}\n"
            f"Set abort_on_all_failures=False to continue anyway."
        )

    best = max(fitnesses)
    worst = min(fitnesses)
    med = median(fitnesses)
    std_val = stdev(fitnesses) if len(fitnesses) > 1 else 0.0

    # Calculate regime coverage and single-regime penalty
    regime_coverage = _compute_regime_coverage(episode_results)
    single_regime_penalty = _compute_single_regime_penalty(
        regime_coverage, regime_penalty_weight
    )

    # Apply penalties
    worst_case_penalty = WORST_CASE_PENALTY if worst < WORST_FITNESS_THRESHOLD else 0.0
    dispersion_penalty = DISPERSION_PENALTY if std_val > DISPERSION_THRESHOLD else 0.0
    lucky_spike_penalty = _compute_lucky_spike_penalty(fitnesses)

    aggregated = med - (worst_case_penalty + dispersion_penalty + single_regime_penalty + lucky_spike_penalty)

    return RobustAggregateResult(
        aggregated_fitness=aggregated,
        median_fitness=med,
        worst_fitness=worst,
        best_fitness=best,
        std_fitness=std_val,
        worst_case_penalty=worst_case_penalty,
        dispersion_penalty=dispersion_penalty,
        single_regime_penalty=single_regime_penalty,
        lucky_spike_penalty=lucky_spike_penalty,
        episodes=episode_results,
        regime_coverage=regime_coverage,
        n_trades_per_episode=n_trades_list,
    )


def _compute_lucky_spike_penalty(fitnesses: List[float]) -> float:
    """Penalty if best episode dominates total positive fitness.

    Applied when the single best episode accounts for more than 60% of the
    total positive fitness across all episodes.  This catches strategies
    that look good only because of one lucky window.
    """
    positive = [f for f in fitnesses if f > 0]
    if len(positive) < 2:
        return 0.0
    total_positive = sum(positive)
    if total_positive <= 0:
        return 0.0
    best_share = max(positive) / total_positive
    if best_share >= LUCKY_SPIKE_THRESHOLD:
        return LUCKY_SPIKE_PENALTY
    return 0.0


def _compute_regime_coverage(episodes: List[RobustEpisodeResult]) -> Dict[str, Any]:
    """Compute per-regime statistics.

    Returns dict with:
        - unique_regimes: count of unique regime combinations
        - regime_counts: dict mapping regime tuple to count
        - per_regime_fitness: dict mapping regime tuple to list of fitness values
    """
    regime_counts: Dict[tuple, int] = {}
    per_regime_fitness: Dict[tuple, List[float]] = {}

    for ep in episodes:
        regime_tuple = tuple(sorted(ep.tags.items()))
        regime_counts[regime_tuple] = regime_counts.get(regime_tuple, 0) + 1

        if regime_tuple not in per_regime_fitness:
            per_regime_fitness[regime_tuple] = []
        per_regime_fitness[regime_tuple].append(ep.episode_fitness)

    # Convert to serializable format
    regime_counts_serializable = {
        str(k): v for k, v in regime_counts.items()
    }
    per_regime_fitness_serializable = {
        str(k): v for k, v in per_regime_fitness.items()
    }

    # Track year coverage
    years_covered = set()
    for ep in episodes:
        years_covered.add(ep.episode_spec.start_ts.year)
        years_covered.add(ep.episode_spec.end_ts.year)

    return {
        "unique_regimes": len(regime_counts),
        "regime_counts": regime_counts_serializable,
        "per_regime_fitness": per_regime_fitness_serializable,
        "years_covered": sorted(years_covered),
    }


def _compute_single_regime_penalty(
    regime_coverage: Dict[str, Any], weight: float
) -> float:
    """Compute penalty if strategy only works in a single regime.

    Penalty applied if:
    - Only 1 unique regime observed, OR
    - One regime has 80%+ of positive fitness episodes
    """
    if regime_coverage["unique_regimes"] <= 1:
        return weight

    # Check if one regime dominates positive fitness episodes
    per_regime_fitness = regime_coverage["per_regime_fitness"]
    positive_episodes_by_regime: Dict[str, int] = {}
    total_positive = 0

    for regime_str, fitness_list in per_regime_fitness.items():
        n_positive = sum(1 for f in fitness_list if f > 0)
        positive_episodes_by_regime[regime_str] = n_positive
        total_positive += n_positive

    if total_positive == 0:
        return 0.0  # No positive episodes at all

    # Check if any regime has 80%+ of positive episodes
    max_positive_pct = max(positive_episodes_by_regime.values()) / total_positive
    if max_positive_pct >= 0.8:
        return weight

    return 0.0
