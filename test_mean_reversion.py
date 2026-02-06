#!/usr/bin/env python3
"""Test the default mean reversion strategy to verify Series ambiguity fix."""

import requests
import time
import json

# The default mean reversion strategy
nl_text = """Trade mean reversion on 5-minute bars. Entry: Buy when RSI(14) drops below 30 (oversold). Exit: Sell when RSI rises above 70 (overbought). Use ATR-based risk management: - Stop loss: 2x ATR below entry - Take profit: 3x ATR above entry. Position size: $10,000 per trade. Risk limits: Max 5 trades per day, max 2% daily loss"""

# Start a Darwin run
print("🚀 Starting Darwin run with mean reversion strategy...")
response = requests.post("http://localhost:8050/api/run", json={
    "nl_text": nl_text,
    "universe_symbols": ["AAPL"],
    "timeframe": "5m",
    "start_date": "2024-10-01",
    "end_date": "2024-12-31",
    "depth": 2,
    "branching": 2,
    "survivors_per_layer": 1,
    "max_total_evals": 10,
    "robust_mode": False
})

if response.status_code != 200:
    print(f"❌ Failed to start run: {response.status_code}")
    print(response.text)
    exit(1)

result = response.json()
run_id = result["run_id"]
print(f"✓ Started run: {run_id}")
print(f"📊 Monitoring events at: http://localhost:8050/api/run/{run_id}/events")

# Stream events
print("\n" + "="*60)
print("EVENT STREAM")
print("="*60 + "\n")

try:
    with requests.get(f"http://localhost:8050/api/run/{run_id}/events", stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith('data: '):
                    data_str = decoded[6:]  # Remove 'data: ' prefix
                    try:
                        event = json.loads(data_str)
                        event_type = event.get('type', 'unknown')

                        if event_type == 'complete':
                            print("\n✅ Run completed successfully!")
                            summary = event.get('data', {})
                            print(f"\nSummary:")
                            print(f"  Total Evaluations: {summary.get('total_evals', 0)}")
                            print(f"  Best Fitness: {summary.get('best_fitness', 'N/A')}")
                            print(f"  Best Graph ID: {summary.get('best_graph_id', 'N/A')}")
                            break
                        elif event_type == 'error':
                            print(f"\n❌ Run failed with error:")
                            print(f"  {event.get('data', {}).get('error', 'Unknown error')}")
                            break
                        elif event_type == 'progress':
                            data = event.get('data', {})
                            print(f"⏳ Progress: {data.get('message', '')}")
                        elif event_type == 'generation':
                            data = event.get('data', {})
                            print(f"🧬 Generation {data.get('generation', '?')}")
                        elif event_type == 'eval':
                            data = event.get('data', {})
                            decision = data.get('decision', 'unknown')
                            graph_id = data.get('graph_id', 'unknown')
                            fitness = data.get('fitness', 'N/A')
                            emoji = "✓" if decision == "PASS" else "✗"
                            print(f"  {emoji} {graph_id}: {decision} (fitness: {fitness})")

                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

except KeyboardInterrupt:
    print("\n\n⚠️  Interrupted by user")
except Exception as e:
    print(f"\n\n❌ Error streaming events: {e}")

print("\n" + "="*60)
print("Test complete")
print("="*60)
