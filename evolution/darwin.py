"""Darwin evolution engine - multi-generation strategy evolution."""

import pandas as pd
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from graph.schema import StrategyGraph, UniverseSpec, TimeConfig
from validation.evaluation import (
    evaluate_strategy,
    evaluate_strategy_phase3,
    apply_schedule_override,
    Phase3Config,
    Phase3ScheduleConfig,
    StrategyEvaluationResult,
)
from llm import compile_nl_to_graph, propose_child_patches, create_results_summary
from evolution.patches import apply_patch
from evolution.population import prune_top_k, kill_stats_by_label, get_generation_stats
from evolution.storage import RunStorage
from research.integration import save_research_artifacts


@dataclass
class RunSummary:
    """Summary of a Darwin evolution run."""
    run_id: str
    total_evaluations: int
    best_strategy: StrategyEvaluationResult
    top_strategies: List[StrategyEvaluationResult]
    kill_stats: Dict[str, int]
    generation_stats: List[Dict[str, Any]]
    run_dir: str


def run_darwin(
    data: pd.DataFrame,
    universe: UniverseSpec,
    time_config: TimeConfig,
    nl_text: Optional[str] = None,
    seed_graph: Optional[StrategyGraph] = None,
    depth: int = 3,
    branching: int = 3,
    survivors_per_layer: int = 5,
    min_survivors_floor: int = 1,
    max_total_evals: int = 200,
    compile_provider: str = "openai",
    compile_model: str = "gpt-4o-mini",
    mutate_provider: str = "openai",
    mutate_model: str = "gpt-4o-mini",
    rescue_mode: bool = False,
    initial_capital: float = 100000.0,
    run_id: Optional[str] = None,
    phase3_config: Optional[Phase3Config] = None,
) -> RunSummary:
    """Run Darwin evolution on a strategy.

    Args:
        data: OHLCV DataFrame for backtesting
        universe: LOCKED universe specification
        time_config: LOCKED time configuration
        nl_text: Natural language strategy (compiled if provided)
        seed_graph: Pre-compiled seed graph (alternative to nl_text)
        depth: Number of generations (layers)
        branching: Children per parent (default 3)
        survivors_per_layer: Max survivors per generation
        min_survivors_floor: Minimum survivors to force-select even if killed (default 1)
        max_total_evals: Hard limit on total evaluations
        compile_provider: LLM provider for compilation
        mutate_provider: LLM provider for mutations
        rescue_mode: Allow mutations even if Adam is killed
        initial_capital: Starting capital for backtests
        run_id: Optional run identifier
        phase3_config: Optional Phase 3 configuration

    Returns:
        RunSummary with results

    Raises:
        ValueError: If neither nl_text nor seed_graph provided
    """
    # Initialize storage
    storage = RunStorage(run_id=run_id)

    # Save run config
    config_dict = {
        'universe': universe.model_dump(),
        'time_config': time_config.model_dump(),
        'nl_text': nl_text,
        'depth': depth,
        'branching': branching,
        'survivors_per_layer': survivors_per_layer,
        'min_survivors_floor': min_survivors_floor,
        'max_total_evals': max_total_evals,
        'compile_provider': compile_provider,
        'compile_model': compile_model,
        'mutate_provider': mutate_provider,
        'mutate_model': mutate_model,
        'rescue_mode': rescue_mode,
    }
    # Include Phase 3 config for reproducibility
    if phase3_config:
        from dataclasses import asdict
        p3_dict = asdict(phase3_config)
        # Serialize schedule sub-config
        if phase3_config.schedule:
            p3_dict['schedule'] = phase3_config.schedule.to_dict()
        # sampling_mode_schedule already serializes as list[str] via asdict
        config_dict['phase3_config'] = p3_dict
    storage.save_config(config_dict)

    # Compile or use seed graph
    if nl_text:
        print(f"\n🤖 Compiling NL strategy using {compile_provider}...")
        try:
            adam = compile_nl_to_graph(
                nl_text=nl_text,
                universe=universe,
                time_config=time_config,
                provider=compile_provider,
                model=compile_model,
                run_id=run_id,
            )
            print(f"✓ Adam compiled: {adam.graph_id}")
        except (ValueError, Exception) as e:
            # Compilation failed - save error summary and exit gracefully
            print(f"❌ Compilation failed: {e}")
            error_summary = {
                "status": "failed_compile",
                "error": str(e),
                "total_evaluations": 0,
                "best_fitness": None,
                "best_strategy": None,
                "top_strategies": [],
                "kill_stats": {},
                "generation_stats": [],
            }
            storage.save_summary(
                top_strategies=[],
                kill_stats={},
                generation_stats=[],
                total_evals=0,
                extra=error_summary,
            )
            raise ValueError(f"Compilation failed: {e}") from e
    elif seed_graph:
        adam = seed_graph
        print(f"\n📈 Using seed graph: {adam.graph_id}")
    else:
        raise ValueError("Must provide either nl_text or seed_graph")

    storage.save_graph(adam)

    phase3_active = bool(phase3_config and phase3_config.enabled and phase3_config.mode == "episodes")

    # Resolve schedule: use explicit schedule, or default when Phase 3 active
    schedule = None
    if phase3_config and phase3_config.schedule:
        schedule = phase3_config.schedule
    elif phase3_active:
        # Sensible default schedule when Phase 3 is on but no schedule provided
        schedule = Phase3ScheduleConfig()

    def _evaluate_target(graph, generation=0):
        if phase3_active:
            result = evaluate_strategy_phase3(
                strategy=graph,
                data=data,
                initial_capital=initial_capital,
                phase3_config=phase3_config,
                generation=generation,
            )
        else:
            result = evaluate_strategy(graph, data, initial_capital=initial_capital)
        # Apply schedule override (grace period, etc.)
        if schedule:
            result = apply_schedule_override(result, schedule, generation)
        return result

    # Evaluate Adam (generation 0)
    print(f"\n🔬 Evaluating Adam...")
    adam_result = _evaluate_target(adam, generation=0)
    storage.save_evaluation(adam_result)
    if phase3_active:
        storage.save_phase3_report(adam_result)
        # Generate Blue Memo + Red Verdict
        save_research_artifacts(
            run_id=run_id,
            evaluation_result=adam_result,
            phase3_config=phase3_config,
            parent_graph_id=None,
            generation=0,
            patch=None,
        )

    print(f"✓ Adam: {adam_result.decision.upper()} (fitness={adam_result.fitness:.3f})")

    # Track all evaluations and generations
    all_evaluations = [adam_result]
    generation_stats_list = []

    # Store graph mapping for parent lookup
    graph_map = {adam.graph_id: adam}

    # Check if Adam survived (or can mutate via grace period)
    if not adam_result.is_survivor() and not adam_result.can_mutate():
        print(f"⚠️  Adam was KILLED: {', '.join(adam_result.kill_reason)}")
        if not rescue_mode:
            print("❌ Rescue mode disabled - cannot evolve killed strategies")
            # Return early with just Adam
            return _build_summary(
                storage, all_evaluations, generation_stats_list, adam_result
            )
        else:
            print("🔧 Rescue mode enabled - attempting mutations anyway...")
    elif adam_result.decision == "mutate_only":
        print(f"⚠️  Adam was KILLED but in grace period - allowing mutations"
              f" (labels: {', '.join(adam_result.kill_reason)})")

    # Current generation (starts with Adam)
    current_gen = [adam_result]

    # Evolution loop
    for gen in range(depth):
        print(f"\n{'='*80}")
        print(f"GENERATION {gen+1}/{depth}")
        print(f"{'='*80}")

        # Select parents: survivors + mutate_only (grace period) strategies
        mutable = [r for r in current_gen if r.can_mutate()]
        mutable_ranked = sorted(mutable, key=lambda r: r.fitness, reverse=True)
        parents = mutable_ranked[:survivors_per_layer]

        # SURVIVOR FLOOR: If no survivors, force-select top N by fitness (even if killed)
        survivor_floor_triggered = False
        rescue_from_best_dead_triggered = False

        if not parents and current_gen:
            # Try survivor floor first (if configured)
            if min_survivors_floor > 0:
                print(f"⚠️  No natural survivors - applying survivor floor (min={min_survivors_floor})")
                survivor_floor_triggered = True

                # Sort by fitness (stable sort by fitness then graph_id for determinism)
                sorted_gen = sorted(
                    current_gen,
                    key=lambda x: (x.fitness, x.graph_id),
                    reverse=True
                )

                # Take top min_survivors_floor
                parents = sorted_gen[:min_survivors_floor]

                # Mark these with survivor override flag
                for p in parents:
                    if not hasattr(p, '_survivors_override'):
                        p._survivors_override = True

                print(f"🔧 Survivor floor: selected top {len(parents)} by fitness:")
                for i, p in enumerate(parents, 1):
                    print(f"  {i}. {p.graph_id:40s} fitness={p.fitness:.3f} (FORCED)")

            # If still no parents and rescue mode enabled, rescue from best dead
            elif rescue_mode:
                print(f"⚠️  No natural survivors - applying rescue-from-best-dead (rescue_mode=True)")
                rescue_from_best_dead_triggered = True

                # Select top 2 by Phase 3 fitness for mutation
                N_RESCUE = 2
                sorted_gen = sorted(
                    current_gen,
                    key=lambda x: (x.fitness, x.graph_id),
                    reverse=True
                )

                parents = sorted_gen[:N_RESCUE]

                # Mark with rescue flag
                for p in parents:
                    if not hasattr(p, '_rescue_from_dead'):
                        p._rescue_from_dead = True

                print(f"🔧 Rescue-from-best-dead: selected top {len(parents)} by fitness:")
                for i, p in enumerate(parents, 1):
                    print(f"  {i}. {p.graph_id:40s} fitness={p.fitness:.3f} (RESCUED)")

        if not parents:
            print("❌ No survivors to mutate - evolution terminated")
            break

        print(f"\n📊 Selected {len(parents)} parents:")
        for i, p in enumerate(parents, 1):
            print(f"  {i}. {p.graph_id:40s} fitness={p.fitness:.3f}")

        # Generate children for each parent
        next_gen = []

        for parent_idx, parent_result in enumerate(parents, 1):
            # Check eval budget
            if len(all_evaluations) >= max_total_evals:
                print(f"\n⚠️  Hit max_total_evals ({max_total_evals}) - stopping")
                break

            print(f"\n[Parent {parent_idx}/{len(parents)}] {parent_result.graph_id}")

            # Get parent graph from map
            parent_graph = graph_map.get(parent_result.graph_id)
            if not parent_graph:
                print(f"  ❌ Parent graph not found in map - skipping")
                continue

            # Create results summary
            results_summary = create_results_summary(parent_result)

            # Propose child patches
            print(f"  🤖 Generating {branching} mutations...")
            try:
                patches = propose_child_patches(
                    parent_graph=parent_graph,
                    results_summary=results_summary,
                    num_children=branching,
                    provider=mutate_provider,
                    model=mutate_model,
                    run_id=run_id,
                )
            except Exception as e:
                print(f"  ❌ Mutation generation failed: {e}")
                continue

            # Apply patches and evaluate children
            for patch_idx, patch in enumerate(patches, 1):
                # Check eval budget again
                if len(all_evaluations) >= max_total_evals:
                    break

                print(f"  [{patch_idx}/{len(patches)}] Applying patch {patch.patch_id}...")

                try:
                    # Apply patch
                    child = apply_patch(parent_graph, patch)
                    graph_map[child.graph_id] = child  # Store for future parent lookup
                    storage.save_graph(child)
                    storage.save_patch(patch)

                    # Evaluate child (pass generation index for schedule)
                    child_result = _evaluate_target(child, generation=gen)
                    storage.save_evaluation(child_result)
                    if phase3_active:
                        storage.save_phase3_report(child_result)
                        # Generate Blue Memo + Red Verdict
                        save_research_artifacts(
                            run_id=run_id,
                            evaluation_result=child_result,
                            phase3_config=phase3_config,
                            parent_graph_id=parent_result.graph_id,
                            generation=gen,
                            patch=patch,
                        )
                    all_evaluations.append(child_result)

                    # Log lineage
                    storage.append_lineage(
                        parent_id=parent_result.graph_id,
                        child_id=child_result.graph_id,
                        patch_id=patch.patch_id,
                        depth=gen + 1,
                        fitness=child_result.fitness,
                    )

                    # Add to next generation
                    next_gen.append(child_result)

                    status = "✓" if child_result.is_survivor() else "✗"
                    print(f"    {status} {child_result.decision.upper()} (fitness={child_result.fitness:.3f})")

                except Exception as e:
                    print(f"    ❌ Failed: {e}")

        # Generation stats
        gen_stats = get_generation_stats(next_gen)
        gen_stats['generation'] = gen + 1
        gen_stats['survivor_floor_triggered'] = survivor_floor_triggered
        gen_stats['rescue_from_best_dead_triggered'] = rescue_from_best_dead_triggered
        generation_stats_list.append(gen_stats)

        print(f"\n📊 Generation {gen+1} Summary:")
        print(f"  Evaluated: {gen_stats['total']}")
        print(f"  Survivors: {gen_stats['survivors']} ({gen_stats['survivor_rate']:.1%})")
        if survivor_floor_triggered:
            print(f"  Survivor Floor: TRIGGERED")
        if rescue_from_best_dead_triggered:
            print(f"  Rescue-from-Best-Dead: TRIGGERED")
        print(f"  Best:      {gen_stats['best_fitness']:.3f}")
        print(f"  Mean:      {gen_stats['mean_fitness']:.3f}")
        if phase3_active and next_gen:
            median_fitness = sorted([r.fitness for r in next_gen])[len(next_gen)//2]
            print(f"  Median:    {median_fitness:.3f}")

        # Move to next generation
        current_gen = next_gen

        if not current_gen:
            print("\n❌ No children produced - evolution terminated")
            break

    # Build final summary
    return _build_summary(storage, all_evaluations, generation_stats_list, adam_result)


def _build_summary(
    storage: RunStorage,
    all_evaluations: List[StrategyEvaluationResult],
    generation_stats: List[Dict[str, Any]],
    adam_result: StrategyEvaluationResult,
) -> RunSummary:
    """Build final run summary."""
    from evolution.population import rank_by_fitness

    # Get top strategies
    top_strategies = rank_by_fitness(all_evaluations)[:10]
    best_strategy = top_strategies[0] if top_strategies else adam_result

    # Kill stats
    kill_stats = kill_stats_by_label(all_evaluations)

    # Save summary to storage
    summary_path = storage.save_summary(
        top_strategies=top_strategies,
        kill_stats=kill_stats,
        generation_stats=generation_stats,
        total_evals=len(all_evaluations),
        extra={"best_fitness": best_strategy.fitness if best_strategy else None},
    )

    print(f"\n💾 Results saved to: {storage.run_dir}")

    return RunSummary(
        run_id=storage.run_id,
        total_evaluations=len(all_evaluations),
        best_strategy=best_strategy,
        top_strategies=top_strategies[:5],
        kill_stats=kill_stats,
        generation_stats=generation_stats,
        run_dir=str(storage.run_dir),
    )
