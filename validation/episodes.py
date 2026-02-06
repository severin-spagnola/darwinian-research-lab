from dataclasses import dataclass, field
from datetime import timedelta
import pandas as pd
import random
from typing import Dict, List, Optional


@dataclass
class EpisodeSpec:
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    label: str = ""
    regime_tags: Dict[str, str] = field(default_factory=dict)
    difficulty: Optional[float] = None  # 0.0=easy, 1.0=hard (based on regime diversity + vol)


class EpisodeSampler:
    """Sample contiguous episodes from time series data."""

    MAX_RETRIES = 30
    MAX_STRATIFIED_CANDIDATES = 100

    # All supported sampling modes
    MODES = ("random", "uniform_random", "stratified_by_regime", "stratified_by_year")

    def __init__(self, seed: Optional[int] = None):
        self.random = random.Random(seed)

    def sample_episodes(
        self,
        df: pd.DataFrame,
        n_episodes: int,
        min_months: int = 6,
        max_months: int = 12,
        min_bars: Optional[int] = None,
        sampling_mode: str = "random",
    ) -> List[EpisodeSpec]:
        """Sample episodes from dataframe.

        Args:
            df: DataFrame with datetime index
            n_episodes: Number of episodes to sample
            min_months: Minimum episode duration in months
            max_months: Maximum episode duration in months
            min_bars: Minimum bars per episode
            sampling_mode: One of "random", "uniform_random",
                           "stratified_by_regime", "stratified_by_year"

        Returns:
            List of EpisodeSpec (optionally with regime tags and difficulty)
        """
        if sampling_mode == "stratified_by_regime":
            return self._sample_stratified(df, n_episodes, min_months, max_months, min_bars)
        elif sampling_mode == "stratified_by_year":
            return self._sample_stratified_by_year(df, n_episodes, min_months, max_months, min_bars)
        elif sampling_mode == "uniform_random":
            return self._sample_uniform_random(df, n_episodes, min_months, max_months, min_bars)
        else:
            return self._sample_random(df, n_episodes, min_months, max_months, min_bars)

    # ---- random (original) ------------------------------------------------

    def _sample_random(
        self,
        df: pd.DataFrame,
        n_episodes: int,
        min_months: int = 6,
        max_months: int = 12,
        min_bars: Optional[int] = None,
    ) -> List[EpisodeSpec]:
        """Original random sampling method."""
        if df.empty:
            raise ValueError("Cannot sample episodes from empty dataset")

        index = pd.DatetimeIndex(df.index).sort_values()
        if min_bars is None:
            min_bars = max(20, min_months * 15)

        episodes: List[EpisodeSpec] = []
        tries = 0

        while len(episodes) < n_episodes and tries < self.MAX_RETRIES:
            tries += 1
            start_idx = self.random.randint(0, len(index) - 1)
            start_ts = index[start_idx]
            duration_months = self.random.randint(min_months, max_months)
            end_ts_target = start_ts + pd.DateOffset(months=duration_months)

            if end_ts_target > index[-1]:
                continue

            end_idx = index.searchsorted(end_ts_target, side="right") - 1
            if end_idx <= start_idx:
                continue

            count = end_idx - start_idx + 1
            if count < min_bars:
                continue

            spec = EpisodeSpec(
                start_ts=start_ts,
                end_ts=index[end_idx],
                label=f"episode_{len(episodes)+1}",
            )
            episodes.append(spec)

        if len(episodes) < n_episodes:
            raise ValueError("Insufficient data to sample requested episodes")

        return episodes

    # ---- uniform_random ----------------------------------------------------

    def _sample_uniform_random(
        self,
        df: pd.DataFrame,
        n_episodes: int,
        min_months: int = 6,
        max_months: int = 12,
        min_bars: Optional[int] = None,
    ) -> List[EpisodeSpec]:
        """Sample episodes uniformly across the full date span.

        Divides the date range into n_episodes equal segments and samples
        one episode from each segment, ensuring temporal coverage.
        """
        if df.empty:
            raise ValueError("Cannot sample episodes from empty dataset")

        index = pd.DatetimeIndex(df.index).sort_values()
        if min_bars is None:
            min_bars = max(20, min_months * 15)

        total_span = (index[-1] - index[0]).days
        segment_days = total_span / n_episodes

        episodes: List[EpisodeSpec] = []

        for seg_idx in range(n_episodes):
            seg_start = index[0] + pd.Timedelta(days=int(seg_idx * segment_days))
            seg_end = index[0] + pd.Timedelta(days=int((seg_idx + 1) * segment_days))

            # Find bars in this segment
            mask = (index >= seg_start) & (index < seg_end)
            seg_indices = index[mask]

            if len(seg_indices) < min_bars:
                # Try wider window: extend into neighbouring segments
                seg_indices = index[(index >= seg_start)][:min_bars * 2]

            if len(seg_indices) < min_bars:
                continue

            # Pick random start within this segment
            tries = 0
            while tries < self.MAX_RETRIES:
                tries += 1
                pick = self.random.randint(0, max(0, len(seg_indices) - min_bars))
                start_ts = seg_indices[pick]
                duration_months = self.random.randint(min_months, max_months)
                end_ts_target = start_ts + pd.DateOffset(months=duration_months)

                if end_ts_target > index[-1]:
                    continue

                end_idx = index.searchsorted(end_ts_target, side="right") - 1
                start_idx_global = index.searchsorted(start_ts, side="left")
                if end_idx <= start_idx_global:
                    continue

                count = end_idx - start_idx_global + 1
                if count < min_bars:
                    continue

                spec = EpisodeSpec(
                    start_ts=start_ts,
                    end_ts=index[end_idx],
                    label=f"episode_{len(episodes)+1}",
                )
                episodes.append(spec)
                break

        if len(episodes) < n_episodes:
            # Fallback to basic random for missing slots
            remaining = n_episodes - len(episodes)
            extra = self._sample_random(df, remaining, min_months, max_months, min_bars)
            for i, ep in enumerate(extra):
                ep.label = f"episode_{len(episodes)+1}"
                episodes.append(ep)

        return episodes

    # ---- stratified_by_year ------------------------------------------------

    def _sample_stratified_by_year(
        self,
        df: pd.DataFrame,
        n_episodes: int,
        min_months: int = 6,
        max_months: int = 12,
        min_bars: Optional[int] = None,
    ) -> List[EpisodeSpec]:
        """Ensure coverage across years (or quarters) if dataset spans multiple years.

        Distributes episode slots proportionally across years, then samples
        randomly within each year.
        """
        if df.empty:
            raise ValueError("Cannot sample episodes from empty dataset")

        index = pd.DatetimeIndex(df.index).sort_values()
        if min_bars is None:
            min_bars = max(20, min_months * 15)

        # Group bars by year
        years = sorted(set(index.year))

        if len(years) <= 1:
            # Single year: fall back to random
            return self._sample_random(df, n_episodes, min_months, max_months, min_bars)

        # Distribute slots across years proportionally
        bars_per_year = {y: int((index.year == y).sum()) for y in years}
        total_bars = sum(bars_per_year.values())
        slots_per_year: Dict[int, int] = {}

        remaining_slots = n_episodes
        for y in years:
            share = max(1, round(n_episodes * bars_per_year[y] / total_bars))
            slots_per_year[y] = min(share, remaining_slots)
            remaining_slots -= slots_per_year[y]
            if remaining_slots <= 0:
                break

        # Fill any remaining slots into years with most data
        while remaining_slots > 0:
            for y in sorted(years, key=lambda y: bars_per_year[y], reverse=True):
                if remaining_slots <= 0:
                    break
                slots_per_year[y] = slots_per_year.get(y, 0) + 1
                remaining_slots -= 1

        episodes: List[EpisodeSpec] = []

        for year, n_slots in sorted(slots_per_year.items()):
            if n_slots <= 0:
                continue
            year_mask = index.year == year
            year_index = index[year_mask]

            if len(year_index) < min_bars:
                continue

            for _ in range(n_slots):
                tries = 0
                while tries < self.MAX_RETRIES:
                    tries += 1
                    pick = self.random.randint(0, len(year_index) - 1)
                    start_ts = year_index[pick]
                    duration_months = self.random.randint(min_months, max_months)
                    end_ts_target = start_ts + pd.DateOffset(months=duration_months)

                    if end_ts_target > index[-1]:
                        continue

                    end_idx = index.searchsorted(end_ts_target, side="right") - 1
                    start_idx_global = index.searchsorted(start_ts, side="left")
                    if end_idx <= start_idx_global:
                        continue

                    count = end_idx - start_idx_global + 1
                    if count < min_bars:
                        continue

                    spec = EpisodeSpec(
                        start_ts=start_ts,
                        end_ts=index[end_idx],
                        label=f"episode_{len(episodes)+1}",
                    )
                    episodes.append(spec)
                    break

        if len(episodes) < n_episodes:
            remaining = n_episodes - len(episodes)
            extra = self._sample_random(df, remaining, min_months, max_months, min_bars)
            for ep in extra:
                ep.label = f"episode_{len(episodes)+1}"
                episodes.append(ep)

        return episodes

    # ---- stratified_by_regime (existing) -----------------------------------

    def _sample_stratified(
        self,
        df: pd.DataFrame,
        n_episodes: int,
        min_months: int = 6,
        max_months: int = 12,
        min_bars: Optional[int] = None,
    ) -> List[EpisodeSpec]:
        """Stratified sampling to ensure regime diversity.

        Strategy:
        1. Sample more candidate episodes than needed
        2. Tag each candidate with regime labels
        3. Select final episodes to maximize regime coverage
        4. Fall back to random if insufficient diversity
        """
        if df.empty:
            raise ValueError("Cannot sample episodes from empty dataset")

        index = pd.DatetimeIndex(df.index).sort_values()
        if min_bars is None:
            min_bars = max(20, min_months * 15)

        # Sample candidate episodes (2-3x more than needed)
        n_candidates = min(n_episodes * 3, self.MAX_STRATIFIED_CANDIDATES)
        candidates: List[EpisodeSpec] = []
        tries = 0

        while len(candidates) < n_candidates and tries < self.MAX_RETRIES * 3:
            tries += 1
            start_idx = self.random.randint(0, len(index) - 1)
            start_ts = index[start_idx]
            duration_months = self.random.randint(min_months, max_months)
            end_ts_target = start_ts + pd.DateOffset(months=duration_months)

            if end_ts_target > index[-1]:
                continue

            end_idx = index.searchsorted(end_ts_target, side="right") - 1
            if end_idx <= start_idx:
                continue

            count = end_idx - start_idx + 1
            if count < min_bars:
                continue

            spec = EpisodeSpec(
                start_ts=start_ts,
                end_ts=index[end_idx],
                label=f"candidate_{len(candidates)+1}",
            )
            candidates.append(spec)

        if len(candidates) < n_episodes:
            # Fall back to random sampling
            return self._sample_random(df, n_episodes, min_months, max_months, min_bars)

        # Tag candidates with regime labels
        tagger = RegimeTagger()
        for spec in candidates:
            episode_df = slice_episode(df, spec.start_ts, spec.end_ts)
            history_df = df.loc[: spec.start_ts]
            tags = tagger.tag_episode(episode_df, history_df=history_df)
            spec.regime_tags = tags

        # Select episodes to maximize regime diversity
        selected = self._select_diverse_episodes(candidates, n_episodes)

        # Renumber labels
        for i, spec in enumerate(selected, 1):
            spec.label = f"episode_{i}"

        return selected

    def _select_diverse_episodes(
        self, candidates: List[EpisodeSpec], n_episodes: int
    ) -> List[EpisodeSpec]:
        """Select episodes to maximize regime coverage.

        Greedy algorithm:
        - Track unique regime combinations seen
        - Prioritize episodes with unseen regime combinations
        - Randomly select among episodes with same regime coverage
        """
        selected: List[EpisodeSpec] = []
        remaining = candidates.copy()
        seen_regimes: set[tuple[str, ...]] = set()

        while len(selected) < n_episodes and remaining:
            # Score candidates by regime novelty
            scored = []
            for spec in remaining:
                regime_tuple = tuple(sorted(spec.regime_tags.items()))
                novelty_score = 0 if regime_tuple in seen_regimes else 1
                scored.append((spec, regime_tuple, novelty_score))

            # Prioritize unseen regimes
            scored.sort(key=lambda x: x[2], reverse=True)

            # Among top candidates with same score, pick randomly
            top_score = scored[0][2]
            top_candidates = [s for s in scored if s[2] == top_score]
            chosen_spec, regime_tuple, _ = self.random.choice(top_candidates)

            selected.append(chosen_spec)
            seen_regimes.add(regime_tuple)
            remaining.remove(chosen_spec)

        return selected


class RegimeTagger:
    """Generate lightweight regime tags for an episode.

    All tagging is forward-only: only bars within the episode (and optionally
    trailing history *before* the episode start) are used.  No future data
    beyond ``episode.end_ts`` is ever accessed.

    Regime definitions
    ------------------
    trend : {"up", "down", "flat"}
        Based on percentage change from first to last close.
        up: change > +3%, down: change < -3%, flat: otherwise.

    vol_bucket : {"low", "mid", "high"}
        14-bar ATR as a percentage of close, compared to the trailing
        history ATR (if supplied).
        low: atr_pct < 0.75 * hist_atr, high: > 1.25 * hist_atr, else mid.

    chop_bucket : {"trending", "choppy"}
        Ratio of net price move to total price range within the episode.
        trending: ratio > 0.4, choppy: ratio <= 0.4.

    drawdown_state : {"in_drawdown", "recovering", "at_highs"}
        Based on trailing-max drawdown within the episode.
        in_drawdown: max dd > 10%, recovering: 3-10%, at_highs: <3%.
    """

    def tag_episode(self, df_episode: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> Dict[str, str]:
        close = df_episode["close"]
        trend = self._tag_trend(close)
        vol_bucket = self._tag_volatility(df_episode, history_df)
        chop_bucket = self._tag_choppiness(df_episode)
        dd_state = self._tag_drawdown(df_episode)
        return {
            "trend": trend,
            "vol_bucket": vol_bucket,
            "chop_bucket": chop_bucket,
            "drawdown_state": dd_state,
        }

    def _tag_trend(self, close: pd.Series) -> str:
        if len(close) < 2:
            return "flat"
        start_price = close.iloc[0]
        end_price = close.iloc[-1]

        # Use absolute change if starting price is zero or very small
        if abs(start_price) < 1e-6:
            abs_change = end_price - start_price
            if abs_change > 0.03:
                return "up"
            if abs_change < -0.03:
                return "down"
            return "flat"

        # Otherwise use percentage change
        change = (end_price - start_price) / start_price
        if change > 0.03:
            return "up"
        if change < -0.03:
            return "down"
        return "flat"

    def _tag_volatility(self, df_episode: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> str:
        atr_pct = self._compute_atr_pct(df_episode)
        threshold_low, threshold_high = 0.01, 0.02
        if history_df is not None and not history_df.empty:
            hist_atr = self._compute_atr_pct(history_df)
            threshold_low = hist_atr * 0.75
            threshold_high = hist_atr * 1.25

        if atr_pct < threshold_low:
            return "low"
        if atr_pct > threshold_high:
            return "high"
        return "mid"

    def _compute_atr_pct(self, df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window=14, min_periods=1).mean()
        avg = (atr / close).dropna()
        return float(avg.mean()) if not avg.empty else 0.0

    def _tag_choppiness(self, df_episode: pd.DataFrame) -> str:
        close = df_episode["close"]
        net_move = abs(close.iloc[-1] - close.iloc[0])
        total_range = close.max() - close.min()
        ratio = net_move / total_range if total_range > 0 else 0.0
        return "trending" if ratio > 0.4 else "choppy"

    def _tag_drawdown(self, df_episode: pd.DataFrame) -> str:
        """Tag drawdown state using only bars within the episode."""
        close = df_episode["close"]
        if len(close) < 2:
            return "at_highs"
        running_max = close.cummax()
        drawdown_pct = ((running_max - close) / running_max).max()
        if drawdown_pct > 0.10:
            return "in_drawdown"
        if drawdown_pct > 0.03:
            return "recovering"
        return "at_highs"


def compute_difficulty(tags: Dict[str, str]) -> float:
    """Compute a simple difficulty score from regime tags.

    Higher = harder.  Scale 0.0-1.0.
    """
    score = 0.0
    if tags.get("vol_bucket") == "high":
        score += 0.3
    elif tags.get("vol_bucket") == "mid":
        score += 0.1
    if tags.get("chop_bucket") == "choppy":
        score += 0.3
    if tags.get("trend") == "down":
        score += 0.2
    elif tags.get("trend") == "flat":
        score += 0.1
    if tags.get("drawdown_state") == "in_drawdown":
        score += 0.2
    elif tags.get("drawdown_state") == "recovering":
        score += 0.1
    return min(score, 1.0)


def slice_episode(df: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    return df.loc[start_ts:end_ts]
