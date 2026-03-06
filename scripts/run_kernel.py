#!/usr/bin/env python3
"""
Standalone runtime kernel — run without HTTP.

Boots the kernel, plugs built-in flows, then runs a simple REPL or one-shot invoke.
Usage:
  python scripts/run_kernel.py              # Interactive: invoke flows at prompt
  python scripts/run_kernel.py echo '{"x":1}'  # One-shot: invoke flow with JSON input
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from src.core.kernel import create_kernel
    from src.core.flow_interface import FlowSpec, FlowDirection, flow_handler

    kernel = create_kernel()
    kernel.boot()

    # Plug built-in flows
    kernel.plug(
        FlowSpec(flow_id="echo", name="Echo", direction=FlowDirection.INCOMING),
        flow_handler(lambda inp: {"out": inp, "flow_id": "echo"}),
    )
    kernel.plug(
        FlowSpec(flow_id="reverse", name="Reverse", direction=FlowDirection.REGENERATING),
        flow_handler(lambda inp: {"out": {str(v): k for k, v in (inp or {}).items()}, "flow_id": "reverse"}),
    )
    try:
        from src.integration.nyse_simulation import process as nyse_process
        kernel.plug(
            FlowSpec(flow_id="nyse_sim", name="NYSE Simulation", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=30),
            flow_handler(nyse_process),
        )
    except ImportError:
        pass
    try:
        from src.integration.construction_flows import pay_app_tracker, construction_dashboard
        kernel.plug(
            FlowSpec(flow_id="pay_app_tracker", name="Pay App Tracker", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=30),
            flow_handler(pay_app_tracker),
        )
        kernel.plug(
            FlowSpec(flow_id="construction_dashboard", name="Construction Dashboard", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=30),
            flow_handler(construction_dashboard),
        )
    except ImportError:
        pass
    try:
        from src.integration.development_intelligence_flows import monte_carlo_flow, policy_evaluate_flow
        kernel.plug(
            FlowSpec(flow_id="monte_carlo", name="Monte Carlo", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=60),
            flow_handler(monte_carlo_flow),
        )
        kernel.plug(
            FlowSpec(flow_id="policy_evaluate", name="Policy Evaluate", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=10),
            flow_handler(policy_evaluate_flow),
        )
        from src.integration.development_intelligence_flows import development_pipeline_flow
        kernel.plug(
            FlowSpec(flow_id="development_pipeline", name="Development Pipeline", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=120),
            flow_handler(development_pipeline_flow),
        )
    except ImportError:
        pass
    try:
        from src.geo_economic import scan_corridors
        def corridor_scan_handler(inp):
            regions = inp.get("regions", [{"region_id": "r1", "migration_score": 0.7, "permit_growth": 0.6, "infrastructure_investment": 0.5, "employment_expansion": 0.6, "land_price_trend": 0.5}])
            return scan_corridors(regions, trace_id=inp.get("trace_id"), tenant_id=inp.get("tenant_id", "default"))
        kernel.plug(
            FlowSpec(flow_id="corridor_scan", name="Corridor Scanner", direction=FlowDirection.INCOMING, scope="internal", timeout_seconds=30),
            flow_handler(corridor_scan_handler),
        )
    except ImportError:
        pass

    if len(sys.argv) >= 2:
        # One-shot: run_kernel.py <flow_id> [json|'-' for stdin]
        flow_id = sys.argv[1]
        inp_str = sys.argv[2] if len(sys.argv) >= 3 else "{}"
        if inp_str == "-":
            inp_str = sys.stdin.read()
        try:
            inp = json.loads(inp_str) if inp_str.strip() else {}
        except json.JSONDecodeError:
            print(f"Invalid JSON: {inp_str[:80]}...", file=sys.stderr)
            kernel.shutdown()
            return 1
        result = kernel.invoke(flow_id, inp)
        print(json.dumps(result.to_dict(), indent=2))
        kernel.shutdown()
        return 0 if result.ok else 1

    # Interactive REPL
    print("FranklinOps Runtime Kernel — flow invoke REPL")
    print("  flows: echo, reverse, nyse_sim, pay_app_tracker, construction_dashboard, monte_carlo, policy_evaluate, development_pipeline")
    print("  invoke <flow_id> <json>  or  quit")
    print()
    while True:
        try:
            line = input("kernel> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line or line.lower() in ("q", "quit", "exit"):
            break
        parts = line.split(maxsplit=1)
        flow_id = parts[0].lower()
        inp_str = parts[1] if len(parts) > 1 else "{}"
        try:
            inp = json.loads(inp_str) if inp_str.strip() else {}
        except json.JSONDecodeError:
            print(f"  Invalid JSON: {inp_str}")
            continue
        result = kernel.invoke(flow_id, inp)
        print(f"  {json.dumps(result.to_dict())}")

    kernel.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
