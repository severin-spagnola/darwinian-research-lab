"""Storage and persistence for Darwin evolution runs."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from graph.schema import StrategyGraph
from validation.evaluation import StrategyEvaluationResult
from evolution.patches import PatchSet
import config


class RunStorage:
    """Manages storage for a Darwin evolution run."""

    def __init__(self, run_id: str = None):
        """Initialize run storage.

        Args:
            run_id: Unique run identifier (default: timestamp-based)
        """
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.run_id = run_id
        self.run_dir = config.RESULTS_DIR / "runs" / run_id

        # Create directories
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "graphs").mkdir(exist_ok=True)
        (self.run_dir / "patches").mkdir(exist_ok=True)
        (self.run_dir / "evals").mkdir(exist_ok=True)
        (self.run_dir / "phase3_reports").mkdir(exist_ok=True)

        # Lineage tracking
        self.lineage_file = self.run_dir / "lineage.jsonl"

    def save_config(self, config_dict: Dict[str, Any]):
        """Save run configuration.

        Args:
            config_dict: Configuration parameters
        """
        config_path = self.run_dir / "run_config.json"
        with open(config_path, 'w') as f:
            json.dump(config_dict, f, indent=2)

    def save_graph(self, graph: StrategyGraph):
        """Save strategy graph.

        Args:
            graph: StrategyGraph to save
        """
        graph_path = self.run_dir / "graphs" / f"{graph.graph_id}.json"
        with open(graph_path, 'w') as f:
            f.write(graph.model_dump_json(indent=2))

    def save_patch(self, patch: PatchSet):
        """Save patch set.

        Args:
            patch: PatchSet to save
        """
        patch_path = self.run_dir / "patches" / f"{patch.patch_id}.json"
        with open(patch_path, 'w') as f:
            f.write(patch.model_dump_json(indent=2))

    def save_evaluation(self, result: StrategyEvaluationResult):
        """Save evaluation result.

        Args:
            result: StrategyEvaluationResult to save
        """
        eval_path = self.run_dir / "evals" / f"{result.graph_id}.json"
        with open(eval_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    def save_phase3_report(self, result: StrategyEvaluationResult):
        """Save Phase 3 report for a graph (if present in validation_report).

        Extracts the 'phase3' sub-dict from the evaluation result and writes
        it to ``phase3_reports/<graph_id>.json``.  No-ops if the result does
        not contain Phase 3 data.
        """
        phase3_data = result.validation_report.get("phase3")
        if not phase3_data:
            return

        report = {
            "graph_id": result.graph_id,
            "strategy_name": result.strategy_name,
            "fitness": result.fitness,
            "decision": result.decision,
            "kill_reason": result.kill_reason,
            "timestamp": result.validation_report.get("timestamp"),
            "phase3": phase3_data,
        }

        report_path = self.run_dir / "phase3_reports" / f"{result.graph_id}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

    def append_lineage(
        self,
        parent_id: str,
        child_id: str,
        patch_id: str,
        depth: int,
        fitness: float,
    ):
        """Append lineage entry.

        Args:
            parent_id: Parent graph ID
            child_id: Child graph ID
            patch_id: Patch ID used
            depth: Generation depth
            fitness: Child fitness
        """
        entry = {
            'parent_id': parent_id,
            'child_id': child_id,
            'patch_id': patch_id,
            'depth': depth,
            'fitness': round(fitness, 4),
            'timestamp': datetime.now().isoformat(),
        }

        with open(self.lineage_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def save_summary(
        self,
        top_strategies: List[StrategyEvaluationResult],
        kill_stats: Dict[str, int],
        generation_stats: List[Dict[str, Any]],
        total_evals: int,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Save run summary.

        Args:
            top_strategies: Top N strategies by fitness
            kill_stats: Kill reason counts
            generation_stats: Per-generation statistics
            total_evals: Total evaluations run
            extra: Optional extra fields (e.g., error status, failure info)
        """
        summary = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'total_evaluations': total_evals,

            'top_strategies': [
                {
                    'graph_id': s.graph_id,
                    'fitness': round(s.fitness, 3),
                    'decision': s.decision,
                }
                for s in top_strategies
            ],

            'kill_stats': kill_stats,
            'generation_stats': generation_stats,
        }

        # Merge in any extra fields (for error states, etc.)
        if extra:
            summary.update(extra)

        summary_path = self.run_dir / "summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        return summary_path
