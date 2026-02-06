#!/usr/bin/env python3
"""Test that compile failures create proper artifacts."""

from evolution.darwin import run_darwin
from data.polygon_client import PolygonClient
from graph.schema import UniverseSpec, TimeConfig, DateRange
import config
import json

print("🧪 Testing compile failure artifact creation...")

client = PolygonClient()
data = client.get_bars('AAPL', '5m', '2024-10-01', '2024-12-31')
print(f"✓ Fetched {len(data)} bars")

# Use a deliberately bad NL prompt that will likely cause structural issues
nl_text = """Use a nonexistent node type called FakeNode. Also reference node IDs that don't exist."""

try:
    result = run_darwin(
        data=data,
        universe=UniverseSpec(type='explicit', symbols=['AAPL']),
        time_config=TimeConfig(timeframe='5m', date_range=DateRange(start='2024-10-01', end='2024-12-31')),
        nl_text=nl_text,
        depth=2,
        branching=2,
        survivors_per_layer=1,
        max_total_evals=5,
    )
    print("❌ Expected compilation to fail, but it succeeded")
    exit(1)
except ValueError as e:
    print(f"✓ Compilation failed as expected: {e}")

    # Find the most recent run directory
    runs_dir = config.RESULTS_DIR / "runs"
    run_dirs = sorted(runs_dir.glob("20*"), key=lambda p: p.name, reverse=True)
    if not run_dirs:
        print("❌ No run directory created")
        exit(1)

    latest_run = run_dirs[0]
    print(f"✓ Run directory created: {latest_run.name}")

    # Check for expected artifacts
    artifacts_to_check = [
        ("run_config.json", True),
        ("summary.json", True),
        ("lineage.jsonl", False),  # May or may not exist
    ]

    for artifact, required in artifacts_to_check:
        path = latest_run / artifact
        if path.exists():
            print(f"✓ {artifact} exists")
            if artifact == "summary.json":
                with open(path) as f:
                    summary = json.load(f)
                if summary.get("status") == "failed_compile":
                    print(f"✓ summary.json has status=failed_compile")
                elif summary.get("error"):
                    print(f"✓ summary.json has error field: {summary['error'][:50]}...")
        elif required:
            print(f"❌ Required artifact missing: {artifact}")
            exit(1)
        else:
            print(f"⚠️  Optional artifact missing: {artifact}")

    # Check for compile failure artifacts
    compile_failures_dir = latest_run / "compile_failures"
    if compile_failures_dir.exists():
        failures = list(compile_failures_dir.glob("*.json"))
        if failures:
            print(f"✓ Compile failure artifacts saved: {len(failures)} files")
        else:
            print("⚠️  compile_failures directory exists but is empty")
    else:
        print("⚠️  No compile_failures directory (may be expected)")

    # Check for transcripts
    llm_transcripts_dir = latest_run / "llm_transcripts"
    if llm_transcripts_dir.exists():
        transcripts = list(llm_transcripts_dir.glob("*.json"))
        if transcripts:
            print(f"✓ LLM transcripts saved: {len(transcripts)} files")
        else:
            print("⚠️  llm_transcripts directory exists but is empty")
    else:
        print("⚠️  No llm_transcripts directory")

print("\n✅ Compile failure artifact test complete!")
