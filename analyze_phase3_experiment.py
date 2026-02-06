#!/usr/bin/env python3
"""
Analyze Phase 3 Darwin Evolution Experiment Results

Generates a comprehensive research report from the Darwin run artifacts.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

def load_evaluation(eval_path: Path) -> Dict[str, Any]:
    """Load a strategy evaluation from JSON."""
    with open(eval_path, 'r') as f:
        return json.load(f)

def characterize_strategy(eval_data: Dict[str, Any]) -> str:
    """Generate natural language characterization of strategy."""
    phase3 = eval_data['validation_report'].get('phase3', {})

    median_fitness = phase3.get('median_fitness', 0)
    worst_fitness = phase3.get('worst_fitness', 0)
    best_fitness = phase3.get('best_fitness', 0)
    unique_regimes = phase3.get('regime_coverage', {}).get('unique_regimes', 0)
    single_regime_penalty = phase3.get('single_regime_penalty', 0)

    episodes = phase3.get('episodes', [])
    n_trades_list = phase3.get('n_trades_per_episode', [])
    total_trades = sum(n_trades_list)

    # Characterize based on metrics
    chars = []

    # Fitness level
    if median_fitness > 0.5:
        chars.append("high-performing")
    elif median_fitness > 0:
        chars.append("profitable")
    elif median_fitness > -0.5:
        chars.append("marginally-negative")
    else:
        chars.append("poor-performing")

    # Stability
    if best_fitness - worst_fitness < 0.3:
        chars.append("stable")
    elif best_fitness - worst_fitness > 0.8:
        chars.append("volatile")

    # Regime coverage
    if unique_regimes >= 5:
        chars.append(f"regime-diverse ({unique_regimes} regimes)")
    elif unique_regimes <= 2:
        chars.append(f"regime-limited ({unique_regimes} regimes)")

    # Single regime dependency
    if single_regime_penalty > 0:
        chars.append("regime-dependent")

    # Trading activity
    if total_trades == 0:
        chars.append("non-trading")
    elif total_trades < 10:
        chars.append("low-activity")
    elif total_trades > 50:
        chars.append("high-activity")

    return ", ".join(chars) if chars else "unknown"

def analyze_generation(gen_num: int, evals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze a single generation."""
    survivors = [e for e in evals if e['decision'] == 'survive']
    killed = [e for e in evals if e['decision'] == 'kill']

    analysis = {
        "generation": gen_num,
        "total_evaluated": len(evals),
        "survivors": len(survivors),
        "killed": len(killed),
        "survivor_details": [],
        "killed_details": [],
        "regime_diversity_stats": {},
        "penalty_stats": {},
    }

    # Analyze survivors
    for s in survivors:
        phase3 = s['validation_report'].get('phase3', {})
        analysis["survivor_details"].append({
            "id": s['graph_id'],
            "fitness": s['fitness'],
            "median": phase3.get('median_fitness', 0),
            "worst": phase3.get('worst_fitness', 0),
            "unique_regimes": phase3.get('regime_coverage', {}).get('unique_regimes', 0),
            "single_regime_penalty": phase3.get('single_regime_penalty', 0),
            "characterization": characterize_strategy(s),
        })

    # Analyze killed
    for k in killed:
        phase3 = k['validation_report'].get('phase3', {})
        analysis["killed_details"].append({
            "id": k['graph_id'],
            "fitness": k['fitness'],
            "kill_reason": k.get('kill_reason', []),
            "median": phase3.get('median_fitness', 0),
            "worst": phase3.get('worst_fitness', 0),
            "unique_regimes": phase3.get('regime_coverage', {}).get('unique_regimes', 0),
            "single_regime_penalty": phase3.get('single_regime_penalty', 0),
            "characterization": characterize_strategy(k),
        })

    # Aggregate stats
    all_unique_regimes = [
        e['validation_report'].get('phase3', {}).get('regime_coverage', {}).get('unique_regimes', 0)
        for e in evals
    ]
    all_single_regime_penalties = [
        e['validation_report'].get('phase3', {}).get('single_regime_penalty', 0)
        for e in evals
    ]

    analysis["regime_diversity_stats"] = {
        "mean_unique_regimes": sum(all_unique_regimes) / len(all_unique_regimes) if all_unique_regimes else 0,
        "max_unique_regimes": max(all_unique_regimes) if all_unique_regimes else 0,
        "min_unique_regimes": min(all_unique_regimes) if all_unique_regimes else 0,
    }

    analysis["penalty_stats"] = {
        "strategies_with_regime_penalty": sum(1 for p in all_single_regime_penalties if p > 0),
        "mean_regime_penalty": sum(all_single_regime_penalties) / len(all_single_regime_penalties) if all_single_regime_penalties else 0,
    }

    return analysis

def generate_report(run_dir: Path) -> str:
    """Generate comprehensive research report."""
    report_lines = []

    report_lines.append("="*80)
    report_lines.append("PHASE 3 PART 2 DARWIN EVOLUTION: RESEARCH EXPERIMENT REPORT")
    report_lines.append("="*80)
    report_lines.append("")

    # Load config
    config_path = run_dir / "run_config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)

    report_lines.append("## EXPERIMENTAL CONFIGURATION")
    report_lines.append(f"Run ID: {run_dir.name}")
    report_lines.append(f"Generations: {config['depth']}")
    report_lines.append(f"Population per generation: {config['branching']}")
    report_lines.append(f"Survivors per generation: {config['survivors_per_layer']}")
    report_lines.append(f"Rescue mode: {config['rescue_mode']}")
    report_lines.append("")

    # Load all evaluations
    evals_dir = run_dir / "evals"
    all_evals = []
    for eval_file in evals_dir.glob("*.json"):
        all_evals.append(load_evaluation(eval_file))

    report_lines.append(f"## OVERVIEW")
    report_lines.append(f"Total strategies evaluated: {len(all_evals)}")
    report_lines.append("")

    # Group by generation (would need metadata, for now analyze all)
    report_lines.append("## GENERATION-BY-GENERATION ANALYSIS")
    report_lines.append("")

    # For now, analyze Adam separately and then all children
    adam_evals = [e for e in all_evals if 'adam' in e['graph_id'].lower() or e['graph_id'] == 'mean_reversion_rsi_strategy']
    child_evals = [e for e in all_evals if e not in adam_evals]

    if adam_evals:
        report_lines.append("### GENERATION 0: ADAM")
        adam = adam_evals[0]
        phase3 = adam['validation_report'].get('phase3', {})

        report_lines.append(f"Strategy ID: {adam['graph_id']}")
        report_lines.append(f"Decision: {adam['decision'].upper()}")
        report_lines.append(f"Final Fitness: {adam['fitness']:.3f}")
        report_lines.append("")

        report_lines.append("Phase 3 Metrics:")
        report_lines.append(f"  Median fitness: {phase3.get('median_fitness', 0):.3f}")
        report_lines.append(f"  Worst fitness: {phase3.get('worst_fitness', 0):.3f}")
        report_lines.append(f"  Best fitness: {phase3.get('best_fitness', 0):.3f}")
        report_lines.append(f"  Unique regimes: {phase3.get('regime_coverage', {}).get('unique_regimes', 0)}")
        report_lines.append(f"  Single-regime penalty: {phase3.get('single_regime_penalty', 0):.3f}")
        report_lines.append(f"  Worst-case penalty: {phase3.get('worst_case_penalty', 0):.3f}")
        report_lines.append("")

        report_lines.append(f"Characterization: {characterize_strategy(adam)}")
        report_lines.append("")

        report_lines.append("Per-Episode Breakdown:")
        for ep in phase3.get('episodes', []):
            report_lines.append(f"  {ep['label']}: fitness={ep['fitness']:.3f}, regime={ep['tags']}")
        report_lines.append("")

    # Analyze children
    if child_evals:
        report_lines.append(f"### GENERATIONS 1-{config['depth']}: EVOLVED STRATEGIES")
        report_lines.append(f"Total children evaluated: {len(child_evals)}")
        report_lines.append("")

        survivors = [e for e in child_evals if e['decision'] == 'survive']
        killed = [e for e in child_evals if e['decision'] == 'kill']

        report_lines.append(f"Survivors: {len(survivors)}")
        report_lines.append(f"Killed: {len(killed)}")
        report_lines.append("")

        if survivors:
            report_lines.append("#### SURVIVORS")
            for s in sorted(survivors, key=lambda x: x['fitness'], reverse=True):
                phase3 = s['validation_report'].get('phase3', {})
                report_lines.append(f"\n{s['graph_id']}:")
                report_lines.append(f"  Final Fitness: {s['fitness']:.3f}")
                report_lines.append(f"  Median: {phase3.get('median_fitness', 0):.3f}, Worst: {phase3.get('worst_fitness', 0):.3f}")
                report_lines.append(f"  Unique Regimes: {phase3.get('regime_coverage', {}).get('unique_regimes', 0)}")
                report_lines.append(f"  Single-Regime Penalty: {phase3.get('single_regime_penalty', 0):.3f}")
                report_lines.append(f"  Characterization: {characterize_strategy(s)}")

                # Why did it survive?
                reasons = []
                if phase3.get('median_fitness', 0) > 0:
                    reasons.append("positive median fitness")
                if phase3.get('regime_coverage', {}).get('unique_regimes', 0) >= 4:
                    reasons.append("good regime diversity")
                if phase3.get('single_regime_penalty', 0) == 0:
                    reasons.append("no regime dependence")
                if phase3.get('worst_fitness', 0) > -0.5:
                    reasons.append("no catastrophic episodes")

                report_lines.append(f"  Survival Factors: {', '.join(reasons) if reasons else 'unknown'}")

        if killed:
            report_lines.append("\n#### KILLED STRATEGIES (Sample)")
            for k in sorted(killed, key=lambda x: x['fitness'], reverse=True)[:5]:  # Top 5
                phase3 = k['validation_report'].get('phase3', {})
                report_lines.append(f"\n{k['graph_id']}:")
                report_lines.append(f"  Final Fitness: {k['fitness']:.3f}")
                report_lines.append(f"  Kill Reason: {', '.join(k.get('kill_reason', []))}")
                report_lines.append(f"  Median: {phase3.get('median_fitness', 0):.3f}, Worst: {phase3.get('worst_fitness', 0):.3f}")
                report_lines.append(f"  Unique Regimes: {phase3.get('regime_coverage', {}).get('unique_regimes', 0)}")
                report_lines.append(f"  Single-Regime Penalty: {phase3.get('single_regime_penalty', 0):.3f}")
                report_lines.append(f"  Characterization: {characterize_strategy(k)}")

    # Summary statistics
    report_lines.append("\n" + "="*80)
    report_lines.append("## AGGREGATE STATISTICS")
    report_lines.append("="*80)
    report_lines.append("")

    all_regime_counts = [
        e['validation_report'].get('phase3', {}).get('regime_coverage', {}).get('unique_regimes', 0)
        for e in all_evals
    ]
    all_regime_penalties = [
        e['validation_report'].get('phase3', {}).get('single_regime_penalty', 0)
        for e in all_evals
    ]

    report_lines.append(f"Mean unique regimes per strategy: {sum(all_regime_counts) / len(all_regime_counts):.2f}")
    report_lines.append(f"Strategies with regime penalty: {sum(1 for p in all_regime_penalties if p > 0)}/{len(all_regime_penalties)}")
    report_lines.append("")

    # Best strategy
    best = max(all_evals, key=lambda x: x['fitness'])
    report_lines.append(f"Best Strategy: {best['graph_id']}")
    report_lines.append(f"  Fitness: {best['fitness']:.3f}")
    report_lines.append(f"  Decision: {best['decision']}")
    phase3 = best['validation_report'].get('phase3', {})
    report_lines.append(f"  Unique Regimes: {phase3.get('regime_coverage', {}).get('unique_regimes', 0)}")
    report_lines.append(f"  Characterization: {characterize_strategy(best)}")
    report_lines.append("")

    return "\n".join(report_lines)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_dir = Path(sys.argv[1])
    else:
        # Find most recent phase3_exp run
        runs_dir = Path("results/runs")
        phase3_runs = sorted([d for d in runs_dir.glob("phase3_exp_*")], key=lambda x: x.stat().st_mtime, reverse=True)
        if not phase3_runs:
            print("No phase3_exp runs found")
            sys.exit(1)
        run_dir = phase3_runs[0]

    print(f"Analyzing run: {run_dir}")
    print("")

    report = generate_report(run_dir)
    print(report)

    # Save report
    report_path = run_dir / "EXPERIMENT_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n\nReport saved to: {report_path}")
