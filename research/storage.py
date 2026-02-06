"""Artifact persistence for Research Pack + Blue Memo + Red Verdict.

Follows existing patterns from evolution/storage.py and phase3_reports/.
"""

import json
from pathlib import Path
from typing import Optional

from research.models import ResearchPack, BlueMemo, RedVerdict
import config


class ResearchStorage:
    """Manages storage for research artifacts."""

    def __init__(self, run_id: Optional[str] = None):
        """Initialize research storage.

        Args:
            run_id: Run identifier (optional - for run-scoped artifacts)
        """
        self.run_id = run_id

        # Global research packs directory (shared across runs)
        self.packs_dir = config.RESULTS_DIR / "research_packs"
        self.packs_dir.mkdir(parents=True, exist_ok=True)

        # Run-scoped directories (if run_id provided)
        if run_id:
            self.run_dir = config.RESULTS_DIR / "runs" / run_id
            self.memos_dir = self.run_dir / "blue_memos"
            self.verdicts_dir = self.run_dir / "red_verdicts"
            self.triggered_dir = self.run_dir / "triggered_research"

            self.memos_dir.mkdir(parents=True, exist_ok=True)
            self.verdicts_dir.mkdir(parents=True, exist_ok=True)
            self.triggered_dir.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # Research Packs (global)
    # ========================================================================

    def save_research_pack(self, pack: ResearchPack) -> Path:
        """Save research pack (global, not run-scoped).

        Args:
            pack: ResearchPack to save

        Returns:
            Path to saved file
        """
        pack_path = self.packs_dir / f"{pack.id}.json"

        # Atomic write
        temp_path = pack_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(pack.model_dump(), f, indent=2, default=str)
        temp_path.rename(pack_path)

        return pack_path

    def load_research_pack(self, pack_id: str) -> Optional[ResearchPack]:
        """Load research pack by ID.

        Args:
            pack_id: Pack ID

        Returns:
            ResearchPack if found, None otherwise
        """
        pack_path = self.packs_dir / f"{pack_id}.json"
        if not pack_path.exists():
            return None

        try:
            with open(pack_path, "r") as f:
                data = json.load(f)
            return ResearchPack(**data)
        except Exception:
            return None

    # ========================================================================
    # Blue Memos (run-scoped)
    # ========================================================================

    def save_blue_memo(self, memo: BlueMemo) -> Path:
        """Save blue memo for a graph.

        Args:
            memo: BlueMemo to save

        Returns:
            Path to saved file

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for blue_memo storage")

        memo_path = self.memos_dir / f"{memo.graph_id}.json"

        # Atomic write
        temp_path = memo_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(memo.model_dump(), f, indent=2, default=str)
        temp_path.rename(memo_path)

        return memo_path

    def load_blue_memo(self, graph_id: str) -> Optional[BlueMemo]:
        """Load blue memo for a graph.

        Args:
            graph_id: Graph ID

        Returns:
            BlueMemo if found, None otherwise

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for blue_memo storage")

        memo_path = self.memos_dir / f"{graph_id}.json"
        if not memo_path.exists():
            return None

        try:
            with open(memo_path, "r") as f:
                data = json.load(f)
            return BlueMemo(**data)
        except Exception:
            return None

    # ========================================================================
    # Red Verdicts (run-scoped)
    # ========================================================================

    def save_red_verdict(self, verdict: RedVerdict) -> Path:
        """Save red verdict for a graph.

        Args:
            verdict: RedVerdict to save

        Returns:
            Path to saved file

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for red_verdict storage")

        verdict_path = self.verdicts_dir / f"{verdict.graph_id}.json"

        # Atomic write
        temp_path = verdict_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(verdict.model_dump(), f, indent=2, default=str)
        temp_path.rename(verdict_path)

        return verdict_path

    def load_red_verdict(self, graph_id: str) -> Optional[RedVerdict]:
        """Load red verdict for a graph.

        Args:
            graph_id: Graph ID

        Returns:
            RedVerdict if found, None otherwise

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for red_verdict storage")

        verdict_path = self.verdicts_dir / f"{graph_id}.json"
        if not verdict_path.exists():
            return None

        try:
            with open(verdict_path, "r") as f:
                data = json.load(f)
            return RedVerdict(**data)
        except Exception:
            return None

    # ========================================================================
    # Triggered Research (run-scoped, optional)
    # ========================================================================

    def save_triggered_research(self, graph_id: str, research_data: dict) -> Path:
        """Save triggered research for a specific graph kill.

        Args:
            graph_id: Graph ID
            research_data: Research result data

        Returns:
            Path to saved file

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for triggered_research storage")

        research_path = self.triggered_dir / f"{graph_id}.json"

        # Atomic write
        temp_path = research_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(research_data, f, indent=2, default=str)
        temp_path.rename(research_path)

        return research_path

    def load_triggered_research(self, graph_id: str) -> Optional[dict]:
        """Load triggered research for a graph.

        Args:
            graph_id: Graph ID

        Returns:
            Research data if found, None otherwise

        Raises:
            ValueError: if run_id not set
        """
        if not self.run_id:
            raise ValueError("run_id required for triggered_research storage")

        research_path = self.triggered_dir / f"{graph_id}.json"
        if not research_path.exists():
            return None

        try:
            with open(research_path, "r") as f:
                return json.load(f)
        except Exception:
            return None
