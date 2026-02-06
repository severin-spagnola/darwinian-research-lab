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


class EpisodeSampler:
    """Randomly sample contiguous episodes from time series data."""

    MAX_RETRIES = 30
    MAX_STRATIFIED_CANDIDATES = 100

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
            sampling_mode: "random" or "stratified_by_regime"

        Returns:
            List of EpisodeSpec with regime tags
        """
        if sampling_mode == "stratified_by_regime":
            return self._sample_stratified(df, n_episodes, min_months, max_months, min_bars)
        else:
            return self._sample_random(df, n_episodes, min_months, max_months, min_bars)

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
    """Generate lightweight regime tags for an episode."""

    def tag_episode(self, df_episode: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> Dict[str, str]:
        close = df_episode["close"]
        trend = self._tag_trend(close)
        vol_bucket = self._tag_volatility(df_episode, history_df)
        chop_bucket = self._tag_choppiness(df_episode)
        return {"trend": trend, "vol_bucket": vol_bucket, "chop_bucket": chop_bucket}

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


def slice_episode(df: pd.DataFrame, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    return df.loc[start_ts:end_ts]
