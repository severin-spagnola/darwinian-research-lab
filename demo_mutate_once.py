#!/usr/bin/env python3
"""Demo: Single Generation Mutation

Takes a known survivor strategy, generates 3 mutation patches via LLM,
applies them to create 3 children, and evaluates each child.

Demonstrates Phase 5 mutation pipeline (one generation).
"""

import sys
from graph.schema import StrategyGraph, Node, UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from validation import evaluate_strategy
from llm import propose_child_patches, create_results_summary
from evolution.patches import apply_patch
import config


def create_parent_survivor() -> StrategyGraph:
    """Create a known good strategy (SMA crossover) as parent."""
    nodes = [
        Node(id="market_data", type="MarketData", params={}, inputs={}),
        Node(
            id="sma_fast",
            type="SMA",
            params={"period": 10},
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="sma_slow",
            type="SMA",
            params={"period": 50},
            inputs={"series": ("market_data", "close")}
        ),
        Node(
            id="entry_condition",
            type="Compare",
            params={"op": "cross_up"},
            inputs={"a": ("sma_fast", "sma"), "b": ("sma_slow", "sma")}
        ),
        Node(
            id="exit_condition",
            type="Compare",
            params={"op": "cross_down"},
            inputs={"a": ("sma_fast", "sma"), "b": ("sma_slow", "sma")}
        ),
        Node(
            id="entry_signal",
            type="EntrySignal",
            params={},
            inputs={"condition": ("entry_condition", "result")}
        ),
        Node(
            id="exit_signal",
            type="ExitSignal",
            params={},
            inputs={"condition": ("exit_condition", "result")}
        ),
        Node(
            id="atr",
            type="ATR",
            params={"period": 14},
            inputs={
                "high": ("market_data", "high"),
                "low": ("market_data", "low"),
                "close": ("market_data", "close")
            }
        ),
        Node(
            id="stop_loss",
            type="StopLossATR",
            params={"mult": 1.5},
            inputs={"atr": ("atr", "atr")}
        ),
        Node(
            id="take_profit",
            type="TakeProfitATR",
            params={"mult": 3.0},
            inputs={"atr": ("atr", "atr")}
        ),
        Node(
            id="position_size",
            type="PositionSizingFixed",
            params={"dollars": 10000.0},
            inputs={}
        ),
        Node(
            id="orders",
            type="BracketOrder",
            params={},
            inputs={
                "entry_signal": ("entry_signal", "signal"),
                "exit_signal": ("exit_signal", "signal"),
                "stop_config": ("stop_loss", "stop_config"),
                "tp_config": ("take_profit", "tp_config"),
                "size_config": ("position_size", "size_config")
            }
        ),
    ]

    return StrategyGraph(
        graph_id="parent_sma_10_50",
        name="Parent SMA Crossover (10/50)",
        version="1.0",
        universe=UniverseSpec(type="explicit", symbols=["AAPL"]),
        time=TimeConfig(
            timeframe="5m",
            date_range=DateRange(start="2024-10-01", end="2025-01-01")
        ),
        nodes=nodes,
        outputs={"orders": ("orders", "orders")},
        metadata={"description": "Parent survivor for mutation"}
    )


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)


def main():
    """Main mutation demo."""
    print_section("SINGLE GENERATION MUTATION DEMO")

    # Check API keys
    if not config.POLYGON_API_KEY:
        print("\n❌ ERROR: POLYGON_API_KEY not set")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        print("\n❌ ERROR: ANTHROPIC_API_KEY needed for mutations")
        sys.exit(1)

    # Create parent strategy
    print("\n📈 Creating parent survivor strategy...")
    parent = create_parent_survivor()
    print(f"✓ Parent: {parent.name} ({parent.graph_id})")
    print(f"  Nodes: {len(parent.nodes)}")

    # Fetch data
    print(f"\n📊 Fetching AAPL 5m data...")
    client = PolygonClient()

    try:
        data = client.get_bars("AAPL", "5m", "2024-10-01", "2025-01-01")
        print(f"✓ Fetched {len(data)} bars")
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        sys.exit(1)

    # Evaluate parent
    print_section("EVALUATING PARENT")

    print("\n🔬 Running parent evaluation...")
    try:
        parent_result = evaluate_strategy(parent, data)
        print(f"✓ Parent evaluation complete")
    except Exception as e:
        print(f"❌ Parent evaluation failed: {e}")
        sys.exit(1)

    print(f"\n  Parent Decision:  {parent_result.decision.upper()}")
    print(f"  Parent Fitness:   {parent_result.fitness:.3f}")

    if not parent_result.is_survivor():
        print(f"\n❌ Parent was killed: {', '.join(parent_result.kill_reason)}")
        print("Cannot mutate killed strategies.")
        sys.exit(1)

    # Create results summary
    print("\n📊 Creating results summary for LLM...")
    results_summary = create_results_summary(parent_result)
    print(f"✓ Summary size: ~{len(str(results_summary))} chars")

    # Generate mutation patches
    print_section("GENERATING MUTATIONS")

    print("\n🤖 Calling Anthropic to generate 3 mutation patches...")
    print("  (Mutation budget: max 3 ops/patch, max +5 nodes total)")

    try:
        patches = propose_child_patches(
            parent_graph=parent,
            results_summary=results_summary,
            num_children=3,
            provider="anthropic",
            temperature=0.8,
        )
        print(f"✓ Generated {len(patches)} patches")
    except Exception as e:
        print(f"❌ Patch generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print patch summaries
    print("\n  Patches:")
    for i, patch in enumerate(patches, 1):
        print(f"\n  [{i}] {patch.patch_id}")
        print(f"      Description: {patch.description}")
        print(f"      Ops: {len(patch.ops)}")
        for j, op in enumerate(patch.ops, 1):
            print(f"        {j}. {op.op_type} on {op.node_id or 'new node'}")

    # Apply patches to create children
    print_section("CREATING CHILDREN")

    children = []
    for i, patch in enumerate(patches, 1):
        print(f"\n[{i}] Applying patch {patch.patch_id}...")
        try:
            child = apply_patch(parent, patch)
            children.append(child)
            print(f"✓ Child created: {child.graph_id}")
            print(f"  Nodes: {len(child.nodes)} ({len(child.nodes) - len(parent.nodes):+d} vs parent)")
        except Exception as e:
            print(f"❌ Patch application failed: {e}")
            children.append(None)

    # Evaluate children
    print_section("EVALUATING CHILDREN")

    child_results = []
    for i, child in enumerate(children, 1):
        if child is None:
            print(f"\n[{i}] Skipping (patch failed)")
            child_results.append(None)
            continue

        print(f"\n[{i}] Evaluating {child.graph_id}...")
        try:
            result = evaluate_strategy(child, data)
            child_results.append(result)
            print(f"✓ {result.decision.upper()} (fitness={result.fitness:.3f})")
        except Exception as e:
            print(f"❌ Evaluation failed: {e}")
            child_results.append(None)

    # Summary
    print_section("GENERATION SUMMARY")

    survivors = [r for r in child_results if r and r.is_survivor()]
    killed = [r for r in child_results if r and r.decision == "kill"]
    failed = [r for r in child_results if r is None]

    print(f"\n  Parent:      {parent_result.decision.upper()} (fitness={parent_result.fitness:.3f})")
    print(f"\n  Children:    {len(children)} generated")
    print(f"    Survivors: {len(survivors)}")
    print(f"    Killed:    {len(killed)}")
    print(f"    Failed:    {len(failed)}")

    # Detailed child results
    print(f"\n  Child Details:")
    for i, result in enumerate(child_results, 1):
        if result is None:
            print(f"    [{i}] FAILED")
        else:
            status = "✓" if result.is_survivor() else "✗"
            reasons = f" ({', '.join(result.kill_reason[:2])})" if result.kill_reason else ""
            print(f"    [{i}] {status} {result.decision.upper():8s} fitness={result.fitness:>6.3f}{reasons}")

    # Best child
    if survivors:
        best = max(survivors, key=lambda r: r.fitness)
        improvement = best.fitness - parent_result.fitness
        print(f"\n  🏆 Best Child:")
        print(f"      {best.graph_id}")
        print(f"      Fitness: {best.fitness:.3f} ({improvement:+.3f} vs parent)")

    print_section("DEMO COMPLETE")

    print(f"\n✅ One generation complete!")
    print(f"   - Parent fitness: {parent_result.fitness:.3f}")
    print(f"   - {len(survivors)}/{len(children)} children survived")
    if survivors:
        print(f"   - Best child fitness: {max(s.fitness for s in survivors):.3f}\n")
    else:
        print(f"   - No survivors (all children killed)\n")


if __name__ == "__main__":
    main()
