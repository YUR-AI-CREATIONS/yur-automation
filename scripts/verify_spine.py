#!/usr/bin/env python3
"""
Universal Spine Verification — Phase 1 + Phase 2.

Verifies integrity, orchestration, LLM layers, ports, and flow components.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from src.spine import (
        GovernanceCore,
        compute_governance_hash,
        AuditSpine,
        EvidenceVault,
        UniversalFlowRegistry,
        UniversalOrchestrator,
        PortManager,
        HeadlessEngine,
        DataPort,
        TaskPort,
        FlowPort,
        APIPort,
        ContinuousProcessor,
        HubCollector,
        DistributionManager,
    )
    from src.core.flow_interface import FlowSpec, FlowDirection
    from src.spine.orchestration.port_manager import PortType
    from src.spine.integrity.evidence_vault import create_evidence

    errors: list[str] = []

    # Integrity
    gc = GovernanceCore()
    h = compute_governance_hash()
    if not h.get("hash"):
        errors.append("Governance hash missing")
    if not gc.get_scope("internal"):
        errors.append("Governance scope internal missing")

    ev = EvidenceVault()
    e = create_evidence(blake_birthmark="test", intent="verify")
    eid = ev.put(e)
    if not ev.get(eid):
        errors.append("Evidence vault get failed")

    # Orchestration
    reg = UniversalFlowRegistry()
    reg.plug(
        FlowSpec(flow_id="spine_verify", name="Spine Verify", direction=FlowDirection.INCOMING),
        lambda x: {"verified": True},
        domain="generic",
    )
    if not reg.has("spine_verify"):
        errors.append("Flow registry plug failed")

    orch = UniversalOrchestrator(reg)
    r = orch.invoke("spine_verify", {})
    if not r.ok or not r.out.get("verified"):
        errors.append("Orchestrator invoke failed")

    pm = PortManager()
    pm.register("verify_port", PortType.DATA, lambda p: {"ok": True})
    route_out = pm.route({"test": 1})
    if "verify_port" not in route_out or not route_out["verify_port"].get("ok"):
        errors.append("Port manager route failed")

    # LLM (status only, no API call)
    eng = HeadlessEngine()
    st = eng.status()
    if st.status not in ("ok", "warning", "not_configured", "error", "unknown"):
        errors.append("LLM status invalid")

    # Phase 2: Distribution Ports
    dp = DataPort("verify_data", ingest_fn=lambda p: {"ingested": p})
    if dp.ingest({"x": 1}).get("ingested", {}).get("x") != 1:
        errors.append("DataPort ingest failed")

    tp = TaskPort("verify_task", worker_fn=lambda t: {"done": t})
    enq = tp.enqueue({"task": "test"})
    if not enq.get("enqueued"):
        errors.append("TaskPort enqueue failed")
    proc = tp.process_one()
    if not proc or not proc.get("processed"):
        errors.append("TaskPort process failed")

    fp = FlowPort("verify_flow", orch)
    fp_result = fp.execute({"flow_id": "spine_verify"})
    if not fp_result.get("ok"):
        errors.append("FlowPort execute failed")

    ap = APIPort("verify_api", request_fn=lambda p: {"response": p})
    ap_result = ap.call({"req": 1})
    if not ap_result.get("ok"):
        errors.append("APIPort call failed")

    # Phase 2: Flow components
    source_items: list[dict | None] = [{"n": 1}, {"n": 2}]
    def source() -> dict | None:
        return source_items.pop(0) if source_items else None
    from src.spine.flow.continuous_processor import ProcessorConfig
    cp = ContinuousProcessor(source, lambda t: {"processed": t}, ProcessorConfig(max_iterations=2))
    cp_out = cp.run()
    if cp_out.get("processed", 0) < 2:
        errors.append("ContinuousProcessor run failed")

    hub = HubCollector()
    rid = hub.collect("test", {"data": 1})
    if not rid or hub.count() < 1:
        errors.append("HubCollector collect failed")
    recent = hub.get_recent(5)
    if not recent:
        errors.append("HubCollector get_recent failed")

    dm = DistributionManager(pm)
    dist_out = dm.distribute({"payload": 1})
    if "verify_port" not in dist_out:
        errors.append("DistributionManager distribute failed")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("Spine Phase 1 + Phase 2 verification PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
