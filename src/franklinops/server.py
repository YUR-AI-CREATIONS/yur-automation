from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from .approvals import ApprovalService, build_default_gate
from .audit import AuditLogger
from .autonomy import AutonomySettingsStore
from .doc_ingestion import ingest_roots
from .doc_index import rebuild_doc_index, search_doc_index
from .hub_config import get_roots_from_env
from .finance_spokes import (
    cashflow_forecast,
    import_cashflow_waterfall_csv,
    import_procore_invoices_export_csv,
    run_ap_intake,
    run_ar_reminders,
)
from .conversational_ui import generate_conversational_welcome, generate_smart_suggestions
from .customer_service import ProactiveCustomerService
from .onboarding import OnboardingOrchestrator, create_welcome_message
from .opsdb import OpsDB
from .ops_chat import ops_chat
from .settings import FranklinOpsSettings
from .smart_notifications import SmartNotificationSystem


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomyUpdateIn(BaseModel):
    mode: str = Field(..., description="shadow | assist | autopilot")
    scope: Optional[str] = Field(default=None, description="internal | external_low | external_medium | external_high | restricted")


class ApprovalRequestIn(BaseModel):
    workflow: str
    requested_by: str = Field(default="human")
    intent: str
    scope: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    blake_birthmark: str = Field(default="N/A")
    cost_estimate: float = Field(default=0.0)


class ApprovalDecisionIn(BaseModel):
    decision: str  # approved | denied
    decision_by: str = Field(default="human")
    notes: str = Field(default="")


class TaskCreateIn(BaseModel):
    kind: str = Field(default="general")
    title: str
    description: str = Field(default="")
    priority: int = Field(default=0)
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    due_at: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class TaskStatusUpdateIn(BaseModel):
    status: str


class IngestRunIn(BaseModel):
    roots: Optional[dict[str, str]] = None


class DocIndexRebuildIn(BaseModel):
    embeddings_preference: str = Field(default="sentence-transformers:all-MiniLM-L6-v2")
    chunk_max_chars: int = Field(default=1400)
    chunk_overlap: int = Field(default=200)


class DocIndexSearchIn(BaseModel):
    query: str
    k: int = Field(default=5)


class OpsChatIn(BaseModel):
    question: str
    k: int = Field(default=5)
    temperature: float = Field(default=0.2)


class FinanceAPIntakeRunIn(BaseModel):
    limit: int = Field(default=50)


class FinanceCashflowImportIn(BaseModel):
    artifact_id: str


class FinanceCashflowForecastIn(BaseModel):
    start_week: Optional[str] = None
    weeks: int = Field(default=8)


class FinanceARRemindersRunIn(BaseModel):
    as_of: Optional[str] = None
    limit: int = Field(default=50)


class FinanceProcoreInvoicesImportIn(BaseModel):
    artifact_id: str
    limit: int = Field(default=5000)


class FleetDispatchIn(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    task: dict[str, Any] = Field(default_factory=dict)


class FleetRouteDocumentIn(BaseModel):
    type: str = Field(default="unknown", description="invoice|ap|ar|bid|rfp|project|subcontract")
    id: str = Field(default="unknown")
    source: Optional[str] = None


class FleetProcoreImportIn(BaseModel):
    artifact_id: str


class ProcoreRawGetIn(BaseModel):
    path: str = Field(..., description="Procore REST path starting with /rest/ (read-only GET).")
    params: dict[str, Any] = Field(default_factory=dict)


class AccountingExportInvoicesIn(BaseModel):
    kind: Optional[str] = None
    status: Optional[str] = None


class AccountingExportCashflowLinesIn(BaseModel):
    start_week: Optional[str] = None


class AccountingImportInvoicesIn(BaseModel):
    artifact_id: str
    default_kind: Optional[str] = Field(default=None, description="Optional: AP or AR")
    limit: int = Field(default=5000)
    source: str = Field(default="accounting_import")


class AccountingImportPaymentsIn(BaseModel):
    artifact_id: str


def create_app() -> FastAPI:
    app = FastAPI(title="FranklinOpsHub", version="0.1.0")

    @app.on_event("startup")
    def _startup() -> None:
        settings = FranklinOpsSettings()
        db = OpsDB(settings.db_path)
        audit = AuditLogger(db, settings.audit_jsonl_path)
        autonomy = AutonomySettingsStore(
            db,
            default_mode="shadow",
            default_scope=settings.default_governance_scope,
        )
        gate = build_default_gate(
            authority_level=settings.default_authority_level,
            default_scope=settings.default_governance_scope,
            rate_limit_per_hour=settings.rate_limit_per_hour,
            max_cost_per_mission=settings.max_cost_per_mission,
        )
        approvals = ApprovalService(db, autonomy, gate)

        app.state.settings = settings
        app.state.db = db
        app.state.audit = audit
        app.state.autonomy = autonomy
        app.state.approvals = approvals
        app.state.onboarding = OnboardingOrchestrator(db, audit, settings)
        app.state.customer_service = ProactiveCustomerService(db, audit, settings)
        app.state.notifications = SmartNotificationSystem(db, audit, settings)

        audit.append(actor="system", action="hub_startup", details={"db_path": str(settings.db_path)})

    @app.on_event("shutdown")
    def _shutdown() -> None:
        db: OpsDB = app.state.db
        try:
            app.state.audit.append(actor="system", action="hub_shutdown", details={})
        except Exception:
            pass
        db.close()

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        db: OpsDB = app.state.db
        row = db.conn.execute("SELECT 1 AS ok").fetchone()
        return {"ok": bool(row and row["ok"] == 1)}

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        return {
            "data_dir": str(s.data_dir),
            "db_path": str(s.db_path),
            "audit_jsonl_path": str(s.audit_jsonl_path),
            "onedrive_projects_root": s.onedrive_projects_root,
            "onedrive_bidding_root": s.onedrive_bidding_root,
            "onedrive_attachments_root": s.onedrive_attachments_root,
            "superagents_root": s.superagents_root,
            "bid_zone_root": s.bid_zone_root,
            "roots": get_roots_from_env(),
            "default_authority_level": s.default_authority_level,
            "default_governance_scope": s.default_governance_scope,
            "rate_limit_per_hour": s.rate_limit_per_hour,
            "max_cost_per_mission": s.max_cost_per_mission,
            "ollama_api_url": s.ollama_api_url,
            "ollama_model": s.ollama_model,
        }

    @app.get("/api/autonomy")
    def list_autonomy() -> list[dict[str, Any]]:
        autonomy: AutonomySettingsStore = app.state.autonomy
        return [a.__dict__ for a in autonomy.list_all()]

    @app.put("/api/autonomy/{workflow}")
    def set_autonomy(workflow: str, body: AutonomyUpdateIn) -> dict[str, Any]:
        autonomy: AutonomySettingsStore = app.state.autonomy
        audit: AuditLogger = app.state.audit
        updated = autonomy.set(workflow, mode=body.mode, scope=body.scope)
        audit.append(
            actor="human",
            action="autonomy_setting_updated",
            scope=updated.scope,
            entity_type="workflow",
            entity_id=workflow,
            details={"mode": updated.mode, "scope": updated.scope},
        )
        return updated.__dict__

    @app.get("/api/approvals")
    def list_approvals(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        approvals: ApprovalService = app.state.approvals
        return [a.__dict__ for a in approvals.list(status=status, limit=limit)]

    @app.post("/api/approvals/request")
    def request_approval(body: ApprovalRequestIn) -> dict[str, Any]:
        approvals: ApprovalService = app.state.approvals
        audit: AuditLogger = app.state.audit
        record, gate_reason = approvals.request(
            workflow=body.workflow,
            requested_by=body.requested_by,
            payload=body.payload,
            intent=body.intent,
            scope=body.scope,
            blake_birthmark=body.blake_birthmark,
            cost_estimate=body.cost_estimate,
        )
        audit.append(
            actor=body.requested_by,
            action="approval_requested",
            scope=record.scope,
            entity_type="approval",
            entity_id=record.id,
            details={"workflow": record.workflow, "status": record.status, "gate_reason": gate_reason},
        )
        return record.__dict__

    @app.post("/api/approvals/{approval_id}/decide")
    def decide_approval(approval_id: str, body: ApprovalDecisionIn) -> dict[str, Any]:
        approvals: ApprovalService = app.state.approvals
        audit: AuditLogger = app.state.audit
        try:
            record = approvals.decide(
                approval_id=approval_id,
                decision=body.decision,
                decision_by=body.decision_by,
                notes=body.notes,
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        audit.append(
            actor=body.decision_by,
            action="approval_decided",
            scope=record.scope,
            entity_type="approval",
            entity_id=record.id,
            details={"decision": record.status, "workflow": record.workflow},
        )

        executed: Optional[dict[str, Any]] = None
        try:
            import os

            auto_send = (os.getenv("FRANKLINOPS_SALES_OUTBOUND_AUTO_SEND") or "true").strip().lower() in {"1", "true", "yes", "y", "on"}
        except Exception:
            auto_send = True

        if auto_send and record.status == "approved" and record.workflow == SalesSpokes.WORKFLOW_OUTBOUND_EMAIL:
            try:
                sales: SalesSpokes = app.state.sales
                executed = sales.send_outbound_for_approval(approval_id=record.id, actor=body.decision_by)
            except Exception as e:
                executed = {"ok": False, "error": str(e)}

        out = record.__dict__
        if executed is not None:
            out = {**out, "executed": executed}
        return out

    @app.get("/api/audit")
    def list_audit(limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        rows = db.conn.execute(
            """
            SELECT id, ts, actor, action, scope, entity_type, entity_id, details_json
            FROM audit_events
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "actor": r["actor"],
                    "action": r["action"],
                    "scope": r["scope"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "details": json.loads(r["details_json"]) if r["details_json"] else {},
                }
            )
        return out

    @app.get("/api/tasks")
    def list_tasks(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        params: list[Any] = []
        sql = """
        SELECT id, kind, title, description, status, priority, related_entity_type, related_entity_id,
               created_at, updated_at, due_at, evidence_json
        FROM tasks
        """
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = db.conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "title": r["title"],
                    "description": r["description"],
                    "status": r["status"],
                    "priority": r["priority"],
                    "related_entity_type": r["related_entity_type"],
                    "related_entity_id": r["related_entity_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "due_at": r["due_at"],
                    "evidence": json.loads(r["evidence_json"]) if r["evidence_json"] else {},
                }
            )
        return out

    @app.post("/api/tasks")
    def create_task(body: TaskCreateIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        task_id = uuid.uuid4().hex
        now = utcnow_iso()
        with db.tx() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                  id, kind, title, description, status, priority,
                  related_entity_type, related_entity_id,
                  created_at, updated_at, due_at, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    body.kind,
                    body.title,
                    body.description,
                    "open",
                    body.priority,
                    body.related_entity_type,
                    body.related_entity_id,
                    now,
                    now,
                    body.due_at,
                    json.dumps(body.evidence, ensure_ascii=False),
                ),
            )
        audit.append(actor="system", action="task_created", entity_type="task", entity_id=task_id, details={"kind": body.kind, "title": body.title})
        return {"id": task_id}

    @app.post("/api/tasks/{task_id}/status")
    def update_task_status(task_id: str, body: TaskStatusUpdateIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        now = utcnow_iso()
        with db.tx() as conn:
            cur = conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (body.status, now, task_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="task not found")
        audit.append(actor="human", action="task_status_updated", entity_type="task", entity_id=task_id, details={"status": body.status})
        return {"ok": True}

    @app.post("/api/ingest/run")
    def run_ingest(body: Optional[IngestRunIn] = None) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        roots = (body.roots if body and body.roots else None) or get_roots_from_env()
        roots = {k: v for k, v in roots.items() if v}
        result = ingest_roots(db, audit, roots=roots)
        audit.append(actor="system", action="ingest_run_complete", scope="internal", details=result["counts"])
        return result

    @app.post("/api/doc_index/rebuild")
    def rebuild_index(body: Optional[DocIndexRebuildIn] = None) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        body = body or DocIndexRebuildIn()
        return rebuild_doc_index(
            db,
            audit,
            data_dir=s.data_dir,
            embeddings_preference=body.embeddings_preference,
            chunk_max_chars=body.chunk_max_chars,
            chunk_overlap=body.chunk_overlap,
        )

    @app.post("/api/doc_index/search")
    def search_index(body: DocIndexSearchIn) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        try:
            hits = search_doc_index(db, data_dir=s.data_dir, query=body.query, k=body.k)
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"hits": hits}

    @app.post("/api/ops_chat")
    def ops_chat_endpoint(body: OpsChatIn) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        try:
            return ops_chat(
                db,
                data_dir=s.data_dir,
                question=body.question,
                k=body.k,
                openai_api_key=s.openai_api_key,
                openai_model=s.openai_model,
                openai_temperature=s.openai_temperature,
                ollama_api_url=s.ollama_api_url,
                ollama_model=s.ollama_model,
                user_context={"experience_level": s.user_experience_level}
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/finance/ap_intake/run")
    def finance_ap_intake(body: Optional[FinanceAPIntakeRunIn] = None) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        approvals: ApprovalService = app.state.approvals
        body = body or FinanceAPIntakeRunIn()
        return run_ap_intake(db, audit, approvals, limit=body.limit)

    @app.post("/api/finance/cashflow/import_waterfall")
    def finance_cashflow_import(body: FinanceCashflowImportIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        try:
            return import_cashflow_waterfall_csv(db, audit, artifact_id=body.artifact_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/finance/cashflow/forecast")
    def finance_cashflow_forecast(body: Optional[FinanceCashflowForecastIn] = None) -> dict[str, Any]:
        db: OpsDB = app.state.db
        body = body or FinanceCashflowForecastIn()
        return cashflow_forecast(db, start_week=body.start_week, weeks=body.weeks)

    @app.post("/api/finance/ar_reminders/run")
    def finance_ar_reminders(body: Optional[FinanceARRemindersRunIn] = None) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        approvals: ApprovalService = app.state.approvals
        body = body or FinanceARRemindersRunIn()
        return run_ar_reminders(db, audit, approvals, as_of=body.as_of, limit=body.limit)

    @app.post("/api/finance/procore/import_invoices_export")
    def finance_procore_import_invoices(body: FinanceProcoreInvoicesImportIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        try:
            return import_procore_invoices_export_csv(db, audit, artifact_id=body.artifact_id, limit=body.limit)
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    # -------------------------
    # GROKSTMATE (autonomous construction agents)
    # -------------------------
    @app.get("/api/grokstmate/status")
    def grokstmate_status() -> dict[str, Any]:
        try:
            from src.integration import GROKSTMATE_AVAILABLE
            return {"available": GROKSTMATE_AVAILABLE}
        except Exception:
            return {"available": False}

    @app.post("/api/grokstmate/estimate")
    def grokstmate_estimate(body: dict[str, Any]) -> dict[str, Any]:
        try:
            from src.integration import IntegrationBridge, GovernanceAdapter
            db: OpsDB = app.state.db
            audit: AuditLogger = app.state.audit
            approvals: ApprovalService = app.state.approvals
            bridge = IntegrationBridge(db=db, audit=audit, approvals=approvals)
            adapter = GovernanceAdapter(bridge, audit=audit, approvals=approvals)
            return adapter.estimate_project(body or {}, actor="api")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()
 

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from .approvals import ApprovalService, build_default_gate
from .audit import AuditLogger
from .autonomy import AutonomySettingsStore
from .doc_ingestion import ingest_roots
from .doc_index import rebuild_doc_index, search_doc_index
from .hub_config import get_roots_from_env
from .finance_spokes import FinanceSpokes
from .opsdb import OpsDB
from .ops_chat import ops_chat
from .sales_spokes import SalesSpokes
from .settings import FranklinOpsSettings


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomyUpdateIn(BaseModel):
    mode: str = Field(..., description="shadow | assist | autopilot")
    scope: Optional[str] = Field(default=None, description="internal | external_low | external_medium | external_high | restricted")


class ApprovalRequestIn(BaseModel):
    workflow: str
    requested_by: str = Field(default="human")
    intent: str
    scope: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    blake_birthmark: str = Field(default="N/A")
    cost_estimate: float = Field(default=0.0)


class ApprovalDecisionIn(BaseModel):
    decision: str  # approved | denied
    decision_by: str = Field(default="human")
    notes: str = Field(default="")


class TaskCreateIn(BaseModel):
    kind: str = Field(default="general")
    title: str
    description: str = Field(default="")
    priority: int = Field(default=0)
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    due_at: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class TaskStatusUpdateIn(BaseModel):
    status: str


class IngestRunIn(BaseModel):
    roots: Optional[dict[str, str]] = None


class DocIndexRebuildIn(BaseModel):
    embeddings_preference: str = Field(default="sentence-transformers:all-MiniLM-L6-v2")
    chunk_max_chars: int = Field(default=1400)
    chunk_overlap: int = Field(default=200)


class DocIndexSearchIn(BaseModel):
    query: str
    k: int = Field(default=5)


class OpsChatIn(BaseModel):
    question: str
    k: int = Field(default=5)
    temperature: float = Field(default=0.2)


class SalesInboundScanIn(BaseModel):
    source: str = Field(default="onedrive_bidding")
    limit: int = Field(default=250)


class SalesFolderScanIn(BaseModel):
    source: str = Field(default="onedrive_bidding")
    limit_artifacts: int = Field(default=5000)


class SalesPipelineRefreshIn(BaseModel):
    horizon_days: int = Field(default=21)


class SalesOutboundDraftIn(BaseModel):
    lead_id: str
    opportunity_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    scope: str = Field(default="external_low")
    requested_by: str = Field(default="human")


class SalesLeadSuppressIn(BaseModel):
    suppressed: bool = Field(default=True)
    actor: str = Field(default="human")


class FinanceAPIntakeRunIn(BaseModel):
    source: str = Field(default="onedrive_attachments")
    limit: int = Field(default=250)


class FinanceCashflowImportIn(BaseModel):
    artifact_id: str
    source: str = Field(default="csv_cashflow")


class FinanceCashflowImportLatestIn(BaseModel):
    source: str = Field(default="onedrive_projects")


class FinanceCashflowForecastIn(BaseModel):
    start_week: Optional[str] = None
    weeks: int = Field(default=12)
    create_alert_tasks: bool = Field(default=True)


class FinanceARRemindersRunIn(BaseModel):
    as_of: Optional[str] = None
    limit: int = Field(default=100)
    days_overdue: int = Field(default=1)

class FinanceProcoreInvoicesImportIn(BaseModel):
    artifact_id: str
    limit: int = Field(default=5000)


# Onboarding models
class OnboardingBusinessTypeIn(BaseModel):
    business_description: str = ""
    industry: str = ""
    company_name: str = ""
    role: str = ""


class OnboardingStepCompleteIn(BaseModel):
    step_id: str
    step_data: dict[str, Any] = Field(default_factory=dict)


class OnboardingPreferencesIn(BaseModel):
    preferences: dict[str, Any]


# Notification models
class NotificationActionIn(BaseModel):
    notification_id: int
    action_type: str = "click"  # click, read, dismiss


# Cache-busting headers for UI (avoids stale styles)
UI_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}

# Glassmorphism + vivid navy forest green & matte gold — Webflow-quality
THEME_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { box-sizing: border-box; }
  body {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    margin: 0; padding: 24px;
    background: linear-gradient(135deg, #051a12 0%, #0a2818 25%, #0d2e1c 50%, #082418 75%, #051a12 100%);
    color: #f0f4f2;
    min-height: 100vh;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }
  a { color: #e8c547; text-decoration: none; transition: color 0.2s, text-shadow 0.2s; }
  a:hover { color: #f5d96b; text-decoration: underline; text-shadow: 0 0 20px rgba(232, 197, 71, 0.3); }
  h1, h2 { color: #f5f7f5; font-weight: 600; letter-spacing: -0.03em; }
  h2 { border-bottom: 1px solid rgba(232, 197, 71, 0.4); padding-bottom: 10px; margin-bottom: 4px; }
  .card {
    background: rgba(18, 45, 32, 0.35);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(232, 197, 71, 0.2);
    border-radius: 16px;
    padding: 20px 24px;
    margin: 16px 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.05);
    transition: border-color 0.25s, box-shadow 0.25s, transform 0.2s;
  }
  .card:hover {
    border-color: rgba(232, 197, 71, 0.45);
    box-shadow: 0 12px 40px rgba(0,0,0,0.3), 0 0 0 1px rgba(232, 197, 71, 0.1), inset 0 1px 0 rgba(255,255,255,0.06);
  }
  button {
    padding: 12px 22px;
    background: rgba(26, 58, 42, 0.5);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(232, 197, 71, 0.5);
    border-radius: 12px;
    color: #f0f4f2;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.25s;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  }
  button:hover {
    background: rgba(232, 197, 71, 0.15);
    border-color: #e8c547;
    box-shadow: 0 6px 24px rgba(232, 197, 71, 0.2), 0 0 0 1px rgba(232, 197, 71, 0.1);
    transform: translateY(-1px);
  }
  .pill {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    background: rgba(232, 197, 71, 0.12);
    backdrop-filter: blur(8px);
    color: #e8c547;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid rgba(232, 197, 71, 0.35);
    letter-spacing: 0.02em;
  }
  .muted { color: #9eb5a8; font-size: 13px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  code {
    background: rgba(8, 28, 18, 0.7);
    backdrop-filter: blur(8px);
    padding: 4px 10px;
    border-radius: 8px;
    color: #e8c547;
    font-size: 13px;
    border: 1px solid rgba(232, 197, 71, 0.25);
    font-weight: 500;
  }
  pre {
    background: rgba(5, 22, 14, 0.8);
    backdrop-filter: blur(12px);
    color: #c8e0d0;
    padding: 18px;
    border-radius: 12px;
    overflow: auto;
    font-size: 12px;
    border: 1px solid rgba(232, 197, 71, 0.15);
    white-space: pre-wrap;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);
  }
  input, select {
    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid rgba(232, 197, 71, 0.35);
    background: rgba(8, 28, 18, 0.5);
    backdrop-filter: blur(8px);
    color: #f0f4f2;
    margin: 4px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  input:focus, select:focus {
    outline: none;
    border-color: #e8c547;
    box-shadow: 0 0 0 3px rgba(232, 197, 71, 0.2);
  }
  .ok { color: #5dd68a; }
  .warn { color: #e8c547; }
  .err { color: #e86b6b; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid rgba(232, 197, 71, 0.12); vertical-align: top; }
  th { font-size: 11px; color: #9eb5a8; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
  .agent-cell, .grid-cell {
    background: rgba(12, 35, 24, 0.4);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(232, 197, 71, 0.2);
    border-radius: 12px;
    padding: 14px 18px;
    transition: all 0.25s;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  }
  .agent-cell:hover, .grid-cell:hover {
    border-color: rgba(232, 197, 71, 0.45);
    box-shadow: 0 8px 28px rgba(0,0,0,0.2), 0 0 0 1px rgba(232, 197, 71, 0.08);
  }
  .grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 16px; }
  @media (min-width: 1050px) { .grid { grid-template-columns: 1fr 1fr; } }
  .mono { font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; }
"""


def create_app() -> FastAPI:
    app = FastAPI(title="FranklinOpsHub", version="0.1.0")

    @app.on_event("startup")
    def _startup() -> None:
        settings = FranklinOpsSettings()
        db = OpsDB(settings.db_path)
        audit = AuditLogger(db, settings.audit_jsonl_path)
        autonomy = AutonomySettingsStore(
            db,
            default_mode="shadow",
            default_scope=settings.default_governance_scope,
        )
        gate = build_default_gate(
            authority_level=settings.default_authority_level,
            default_scope=settings.default_governance_scope,
            rate_limit_per_hour=settings.rate_limit_per_hour,
            max_cost_per_mission=settings.max_cost_per_mission,
        )
        approvals = ApprovalService(db, autonomy, gate)
        sales = SalesSpokes(db, audit, approvals)
        finance = FinanceSpokes(db, audit, approvals)

        app.state.settings = settings
        app.state.db = db
        app.state.audit = audit
        app.state.autonomy = autonomy
        app.state.approvals = approvals
        app.state.onboarding = OnboardingOrchestrator(db, audit, settings)
        app.state.customer_service = ProactiveCustomerService(db, audit, settings)
        app.state.notifications = SmartNotificationSystem(db, audit, settings)
        app.state.sales = sales
        app.state.finance = finance
        try:
            from src.superagents_fleet import FleetHub
            data_dir = settings.data_dir / "fleet"
            app.state.fleet_hub = FleetHub(db=db, audit=audit, data_dir=data_dir)
            for prefix, router in app.state.fleet_hub.get_all_plugin_routers():
                app.include_router(router, prefix=prefix)
        except ImportError:
            app.state.fleet_hub = None
        app.state.procore_oauth_state = {}
        app.state.procore_tokens = None

        audit.append(actor="system", action="hub_startup", details={"db_path": str(settings.db_path)})

    @app.on_event("shutdown")
    def _shutdown() -> None:
        db: OpsDB = app.state.db
        try:
            app.state.audit.append(actor="system", action="hub_shutdown", details={})
        except Exception:
            pass
        db.close()

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        db: OpsDB = app.state.db
        row = db.conn.execute("SELECT 1 AS ok").fetchone()
        return {"ok": bool(row and row["ok"] == 1)}

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        return {
            "data_dir": str(s.data_dir),
            "db_path": str(s.db_path),
            "audit_jsonl_path": str(s.audit_jsonl_path),
            "onedrive_projects_root": s.onedrive_projects_root,
            "onedrive_bidding_root": s.onedrive_bidding_root,
            "onedrive_attachments_root": s.onedrive_attachments_root,
            "superagents_root": s.superagents_root,
            "bid_zone_root": s.bid_zone_root,
            "roots": get_roots_from_env(),
            "default_authority_level": s.default_authority_level,
            "default_governance_scope": s.default_governance_scope,
            "rate_limit_per_hour": s.rate_limit_per_hour,
            "max_cost_per_mission": s.max_cost_per_mission,
        }

    @app.get("/api/autonomy")
    def list_autonomy() -> list[dict[str, Any]]:
        autonomy: AutonomySettingsStore = app.state.autonomy
        return [a.__dict__ for a in autonomy.list_all()]

    @app.put("/api/autonomy/{workflow}")
    def set_autonomy(workflow: str, body: AutonomyUpdateIn) -> dict[str, Any]:
        autonomy: AutonomySettingsStore = app.state.autonomy
        audit: AuditLogger = app.state.audit
        updated = autonomy.set(workflow, mode=body.mode, scope=body.scope)
        audit.append(
            actor="human",
            action="autonomy_setting_updated",
            scope=updated.scope,
            entity_type="workflow",
            entity_id=workflow,
            details={"mode": updated.mode, "scope": updated.scope},
        )
        return updated.__dict__

    @app.get("/api/approvals")
    def list_approvals(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        approvals: ApprovalService = app.state.approvals
        return [a.__dict__ for a in approvals.list(status=status, limit=limit)]

    @app.post("/api/approvals/request")
    def request_approval(body: ApprovalRequestIn) -> dict[str, Any]:
        approvals: ApprovalService = app.state.approvals
        audit: AuditLogger = app.state.audit
        record, gate_reason = approvals.request(
            workflow=body.workflow,
            requested_by=body.requested_by,
            payload=body.payload,
            intent=body.intent,
            scope=body.scope,
            blake_birthmark=body.blake_birthmark,
            cost_estimate=body.cost_estimate,
        )
        audit.append(
            actor=body.requested_by,
            action="approval_requested",
            scope=record.scope,
            entity_type="approval",
            entity_id=record.id,
            details={"workflow": record.workflow, "status": record.status, "gate_reason": gate_reason},
        )
        return record.__dict__

    @app.post("/api/approvals/{approval_id}/decide")
    def decide_approval(approval_id: str, body: ApprovalDecisionIn) -> dict[str, Any]:
        approvals: ApprovalService = app.state.approvals
        audit: AuditLogger = app.state.audit
        try:
            record = approvals.decide(
                approval_id=approval_id,
                decision=body.decision,
                decision_by=body.decision_by,
                notes=body.notes,
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        audit.append(
            actor=body.decision_by,
            action="approval_decided",
            scope=record.scope,
            entity_type="approval",
            entity_id=record.id,
            details={"decision": record.status, "workflow": record.workflow},
        )

        executed: Optional[dict[str, Any]] = None

        # Optional auto-execution hooks (safe-by-default).
        try:
            import os

            auto_send = (os.getenv("FRANKLINOPS_SALES_OUTBOUND_AUTO_SEND") or "true").strip().lower() in {"1", "true", "yes", "y", "on"}
        except Exception:
            auto_send = True

        # 1) Sales outbound: if approved, send the draft(s) tied to this approval.
        if auto_send and record.status == "approved" and record.workflow == SalesSpokes.WORKFLOW_OUTBOUND_EMAIL:
            try:
                sales: SalesSpokes = app.state.sales
                executed = sales.send_outbound_for_approval(approval_id=record.id, actor=body.decision_by)
            except Exception as e:
                executed = {"ok": False, "error": str(e)}

        # 2) Finance workflows: apply state transitions after approval/denial.
        if record.workflow in {"finance.ap_intake", "finance.ar_reminder"} and record.status in {"approved", "denied", "auto_approved"}:
            try:
                from .finance_spokes import apply_finance_approval_decision

                db: OpsDB = app.state.db
                executed = apply_finance_approval_decision(
                    db,
                    audit,
                    workflow=record.workflow,
                    approval_id=record.id,
                    approval_status=record.status,
                    actor=body.decision_by,
                    payload=record.payload,
                )
            except Exception as e:
                executed = {"ok": False, "error": str(e)}

        out = record.__dict__
        if executed is not None:
            out = {**out, "executed": executed}
        return out

    @app.get("/api/audit")
    def list_audit(limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        rows = db.conn.execute(
            """
            SELECT id, ts, actor, action, scope, entity_type, entity_id, details_json
            FROM audit_events
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "actor": r["actor"],
                    "action": r["action"],
                    "scope": r["scope"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "details": json.loads(r["details_json"]) if r["details_json"] else {},
                }
            )
        return out

    @app.get("/api/tasks")
    def list_tasks(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        params: list[Any] = []
        sql = """
        SELECT id, kind, title, description, status, priority, related_entity_type, related_entity_id,
               created_at, updated_at, due_at, evidence_json
        FROM tasks
        """
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = db.conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "title": r["title"],
                    "description": r["description"],
                    "status": r["status"],
                    "priority": r["priority"],
                    "related_entity_type": r["related_entity_type"],
                    "related_entity_id": r["related_entity_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "due_at": r["due_at"],
                    "evidence": json.loads(r["evidence_json"]) if r["evidence_json"] else {},
                }
            )
        return out

    @app.post("/api/tasks")
    def create_task(body: TaskCreateIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        task_id = uuid.uuid4().hex
        now = utcnow_iso()
        with db.tx() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                  id, kind, title, description, status, priority,
                  related_entity_type, related_entity_id,
                  created_at, updated_at, due_at, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    body.kind,
                    body.title,
                    body.description,
                    "open",
                    body.priority,
                    body.related_entity_type,
                    body.related_entity_id,
                    now,
                    now,
                    body.due_at,
                    json.dumps(body.evidence, ensure_ascii=False),
                ),
            )
        audit.append(
            actor="system",
            action="task_created",
            entity_type="task",
            entity_id=task_id,
            details={"kind": body.kind, "title": body.title},
        )
        return {"id": task_id}

    @app.post("/api/tasks/{task_id}/status")
    def update_task_status(task_id: str, body: TaskStatusUpdateIn) -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        now = utcnow_iso()
        with db.tx() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (body.status, now, task_id),
            )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="task not found")
        audit.append(
            actor="human",
            action="task_status_updated",
            entity_type="task",
            entity_id=task_id,
            details={"status": body.status},
        )
        return {"ok": True}

    @app.post("/api/ingest/run")
    def run_ingest(body: Optional[IngestRunIn] = None) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit

        roots = (body.roots if body and body.roots else None) or get_roots_from_env()
        roots = {k: v for k, v in roots.items() if v}
        result = ingest_roots(db, audit, roots=roots)
        audit.append(actor="system", action="ingest_run_complete", scope="internal", details=result["counts"])
        return result

    @app.post("/api/doc_index/rebuild")
    def rebuild_index(body: Optional[DocIndexRebuildIn] = None) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        body = body or DocIndexRebuildIn()
        return rebuild_doc_index(
            db,
            audit,
            data_dir=s.data_dir,
            embeddings_preference=body.embeddings_preference,
            chunk_max_chars=body.chunk_max_chars,
            chunk_overlap=body.chunk_overlap,
        )

    @app.post("/api/doc_index/search")
    def search_index(body: DocIndexSearchIn) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        try:
            hits = search_doc_index(db, data_dir=s.data_dir, query=body.query, k=body.k)
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"hits": hits}

    @app.post("/api/ops_chat")
    def ops_chat_endpoint(body: OpsChatIn) -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        db: OpsDB = app.state.db
        try:
            return ops_chat(
                db,
                data_dir=s.data_dir,
                question=body.question,
                k=body.k,
                openai_api_key=s.openai_api_key,
                openai_model=s.openai_model,
                openai_temperature=s.openai_temperature,
                ollama_api_url=s.ollama_api_url,
                ollama_model=s.ollama_model,
                user_context={"experience_level": s.user_experience_level}
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # -------------------------
    # SalesSpokes (JCK)
    # -------------------------

    @app.get("/api/sales/leads")
    def list_sales_leads(limit: int = 200) -> list[dict[str, Any]]:
        sales: SalesSpokes = app.state.sales
        return sales.list_leads(limit=limit)

    @app.get("/api/sales/opportunities")
    def list_sales_opps(limit: int = 200) -> list[dict[str, Any]]:
        sales: SalesSpokes = app.state.sales
        return sales.list_opportunities(limit=limit)

    @app.get("/api/sales/outbound")
    def list_sales_outbound(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        sales: SalesSpokes = app.state.sales
        return sales.list_outbound_messages(status=status, limit=limit)

    @app.post("/api/sales/inbound/scan")
    def run_sales_inbound_scan(body: Optional[SalesInboundScanIn] = None) -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        body = body or SalesInboundScanIn()
        return sales.scan_inbound_itbs(source=body.source, limit=body.limit)

    @app.post("/api/sales/inbound/scan_folders")
    def run_sales_folder_scan(body: Optional[SalesFolderScanIn] = None) -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        body = body or SalesFolderScanIn()
        return sales.scan_bidding_folders(source=body.source, limit_artifacts=body.limit_artifacts)

    @app.post("/api/sales/pipeline/refresh")
    def refresh_sales_pipeline(body: Optional[SalesPipelineRefreshIn] = None) -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        body = body or SalesPipelineRefreshIn()
        return sales.refresh_pipeline_queue(horizon_days=body.horizon_days)

    @app.post("/api/sales/outbound/draft")
    def draft_sales_outbound(body: SalesOutboundDraftIn) -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        try:
            return sales.draft_outbound_email(
                lead_id=body.lead_id,
                opportunity_id=body.opportunity_id,
                subject=body.subject,
                body=body.body,
                scope=body.scope,
                requested_by=body.requested_by,
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/sales/outbound/{message_id}/send")
    def send_sales_outbound(message_id: str, actor: str = "human") -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        try:
            return sales.send_outbound_email(message_id=message_id, actor=actor)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/sales/outbound/send_ready")
    def send_ready_sales_outbound(limit: int = 50, actor: str = "system") -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        return sales.send_ready_outbound(limit=limit, actor=actor)

    @app.post("/api/sales/leads/{lead_id}/suppress")
    def suppress_lead(lead_id: str, body: SalesLeadSuppressIn) -> dict[str, Any]:
        sales: SalesSpokes = app.state.sales
        try:
            return sales.set_lead_suppressed(lead_id=lead_id, suppressed=body.suppressed, actor=body.actor)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/api/sales/trinity/sync")
    def sync_trinity_leads(limit: int = 200) -> dict[str, Any]:
        from .integrations.trinity_sync import sync_trinity_leads as do_sync

        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        return do_sync(db, audit, limit=limit)

    # -------------------------
    # FinanceSpokes
    # -------------------------

    @app.post("/api/finance/ap_intake/run")
    def finance_ap_intake(body: Optional[FinanceAPIntakeRunIn] = None) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        body = body or FinanceAPIntakeRunIn()
        return finance.scan_ap_intake(source=body.source, limit=body.limit)

    @app.post("/api/finance/cashflow/import_waterfall")
    def finance_cashflow_import(body: FinanceCashflowImportIn) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        try:
            return finance.import_cashflow_csv_from_artifact(artifact_id=body.artifact_id, source=body.source)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/finance/cashflow/import_latest")
    def finance_cashflow_import_latest(body: Optional[FinanceCashflowImportLatestIn] = None) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        body = body or FinanceCashflowImportLatestIn()
        return finance.import_latest_cashflow_waterfall(source=body.source)

    @app.post("/api/finance/cashflow/forecast")
    def finance_cashflow_forecast(body: Optional[FinanceCashflowForecastIn] = None) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        body = body or FinanceCashflowForecastIn()
        return finance.forecast_cashflow(start_week=body.start_week, weeks=body.weeks, create_alert_tasks=body.create_alert_tasks)

    @app.post("/api/finance/ar_reminders/run")
    def finance_ar_reminders(body: Optional[FinanceARRemindersRunIn] = None) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        body = body or FinanceARRemindersRunIn()
        return finance.run_ar_reminders(as_of=body.as_of, max_records=body.limit, days_overdue=body.days_overdue)

    @app.post("/api/finance/procore/import_invoices_export")
    def finance_procore_import_invoices(body: FinanceProcoreInvoicesImportIn) -> dict[str, Any]:
        finance: FinanceSpokes = app.state.finance
        try:
            return finance.import_procore_export_csv_from_artifact(artifact_id=body.artifact_id)
        except (KeyError, ValueError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    # -------------------------
    # GROKSTMATE (autonomous construction agents)
    # -------------------------
    @app.get("/api/grokstmate/status")
    def grokstmate_status() -> dict[str, Any]:
        try:
            from src.integration import GROKSTMATE_AVAILABLE
            return {"available": GROKSTMATE_AVAILABLE}
        except Exception:
            return {"available": False}

    @app.post("/api/grokstmate/estimate")
    def grokstmate_estimate(body: dict[str, Any]) -> dict[str, Any]:
        try:
            from src.integration import IntegrationBridge, GovernanceAdapter
            db: OpsDB = app.state.db
            audit: AuditLogger = app.state.audit
            approvals: ApprovalService = app.state.approvals
            bridge = IntegrationBridge(db=db, audit=audit, approvals=approvals)
            adapter = GovernanceAdapter(bridge, audit=audit, approvals=approvals)
            return adapter.estimate_project(body or {}, actor="api")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/grokstmate/project")
    def grokstmate_create_project(body: dict[str, Any]) -> dict[str, Any]:
        try:
            from src.integration import IntegrationBridge, GovernanceAdapter
            db: OpsDB = app.state.db
            audit: AuditLogger = app.state.audit
            approvals: ApprovalService = app.state.approvals
            bridge = IntegrationBridge(db=db, audit=audit, approvals=approvals)
            adapter = GovernanceAdapter(bridge, audit=audit, approvals=approvals)
            return adapter.create_project_plan(
                project_id=body.get("project_id", "proj_new"),
                project_name=body.get("project_name", "New Project"),
                project_spec=body.get("project_spec", body),
                actor="api",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # -------------------------
    # Superagents Fleet (construction & development agents)
    # -------------------------
    @app.get("/api/fleet/status")
    def fleet_status() -> dict[str, Any]:
        hub = getattr(app.state, "fleet_hub", None)
        if not hub:
            return {"available": False, "error": "Fleet hub not loaded"}
        return {"available": True, **hub.get_status()}

    @app.get("/api/fleet/agents")
    def fleet_list_agents(phase: Optional[str] = None) -> list[dict[str, Any]]:
        hub = getattr(app.state, "fleet_hub", None)
        if not hub:
            return []
        return hub.list_agents(phase=phase)

    @app.post("/api/fleet/dispatch", tags=["Superagents Fleet"])
    async def fleet_dispatch(body: FleetDispatchIn) -> dict[str, Any]:
        hub = getattr(app.state, "fleet_hub", None)
        if not hub:
            raise HTTPException(status_code=503, detail="Fleet hub not available")
        return await hub.dispatch(body.agent_id, body.task)

    @app.post("/api/fleet/route_document", tags=["Superagents Fleet"])
    async def fleet_route_document(body: FleetRouteDocumentIn) -> dict[str, Any]:
        hub = getattr(app.state, "fleet_hub", None)
        if not hub:
            raise HTTPException(status_code=503, detail="Fleet hub not available")
        doc = {"type": body.type, "id": body.id, "source": body.source or "api"}
        tasks = hub.route_document(doc)
        results = await hub.dispatch_multi(tasks)
        return {"routed": len(tasks), "results": results}

    @app.post("/api/fleet/integrations/onedrive/ingest", tags=["Superagents Fleet"])
    def fleet_onedrive_ingest() -> dict[str, Any]:
        """Ingest documents from OneDrive/Project Controls roots into FranklinOps + file_keeper."""
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        try:
            from src.superagents_fleet.integrations.onedrive_docs import OneDriveDocBridge
            bridge = OneDriveDocBridge(db=db, audit=audit)
            roots = bridge.get_roots_from_env()
            if not roots:
                return {"error": "No OneDrive/PC roots configured", "roots": []}
            result = bridge.ingest_from_roots(roots)
            if "error" in result:
                return result
            return {"counts": result.get("counts", {}), "roots_used": list(roots.keys())}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/fleet/integrations/procore/import", tags=["Superagents Fleet"])
    def fleet_procore_import(body: FleetProcoreImportIn) -> dict[str, Any]:
        """Import Procore invoices from artifact (CSV) into FranklinOps + bookkeeper."""
        finance = getattr(app.state, "finance", None)
        db: OpsDB = app.state.db
        try:
            from src.superagents_fleet.integrations.procore_invoices import ProcoreInvoiceBridge
            bridge = ProcoreInvoiceBridge(db=db, finance=finance)
            result = bridge.import_from_artifact(body.artifact_id)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # -------------------------
    # BID-ZONE (sales portal) — stub, bridge to build
    # -------------------------
    @app.get("/api/bidzone/status")
    def bidzone_status() -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        return {"available": False, "root": s.bid_zone_root, "note": "Bridge to build — inspect d-XAI-BID-ZONE/src/interfaces/franklin_os.py"}

    @app.post("/api/bidzone/estimate")
    def bidzone_estimate(body: dict[str, Any]) -> dict[str, Any]:
        return {"error": "BID-ZONE bridge not yet built", "action": "Inspect franklin_os.py for API"}

    # -------------------------
    # Project Controls — stub, CRUD to build
    # -------------------------
    @app.get("/api/project_controls/sources")
    def project_controls_sources() -> dict[str, Any]:
        roots = get_roots_from_env()
        pc_sources = {k: v for k, v in roots.items() if k.startswith("pc_")}
        return {"sources": pc_sources, "note": "CRUD endpoints to build"}

    @app.get("/api/project_controls/artifacts")
    def project_controls_artifacts(source: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        params: list[Any] = []
        sql = "SELECT id, source, path, status, ingested_at FROM artifacts WHERE source LIKE 'pc_%'"
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY ingested_at DESC LIMIT ?"
        params.append(limit)
        rows = db.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # -------------------------
    # Franklin OS — stub, bridge to find
    # -------------------------
    @app.get("/api/franklin_os/status")
    def franklin_os_status() -> dict[str, Any]:
        s: FranklinOpsSettings = app.state.settings
        return {"available": False, "root": s.franklin_os_root, "note": "Bridge to find — inspect d-Franklin-OS-local"}

    @app.get("/api/finance/ar_reminders")
    def list_finance_ar_reminders(status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        params: list[Any] = ["finance.ar_reminder"]
        sql = """
        SELECT id, workflow, invoice_id, channel, to_email, subject, body, status,
               approval_id, provider, created_at, updated_at, sent_at, error, metadata_json
        FROM outbound_messages
        WHERE workflow = ?
        """
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = db.conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append({
                "id": r["id"],
                "workflow": r["workflow"],
                "invoice_id": r["invoice_id"],
                "channel": r["channel"],
                "to_email": r["to_email"],
                "subject": r["subject"],
                "body": r["body"],
                "status": r["status"],
                "approval_id": r["approval_id"],
                "provider": r["provider"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "sent_at": r["sent_at"],
                "error": r["error"],
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
            })
        return out

    @app.get("/api/finance/invoices")
    def list_invoices(kind: Optional[str] = None, status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        db: OpsDB = app.state.db
        params: list[Any] = []
        sql = """
        SELECT id, kind, vendor_id, customer_id, project_id, invoice_number, invoice_date, due_date,
               amount_cents, currency, status, source_artifact_id, created_at, updated_at
        FROM invoices
        WHERE 1=1
        """
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = db.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # -------------------------
    # Integrations (Procore OAuth, accounting export/import)
    # -------------------------

    @app.get("/api/integrations/procore/oauth/authorize_url")
    def procore_authorize_url() -> dict[str, Any]:
        from .integrations.procore import ProcoreOAuth, ProcoreOAuthConfig, ProcoreTokenStore

        cfg = ProcoreOAuthConfig.from_env()
        oauth = ProcoreOAuth(cfg, ProcoreTokenStore())
        state = oauth.build_state()
        try:
            url = oauth.authorization_url(state=state)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        app.state.procore_oauth_state[state] = utcnow_iso()
        return {"authorize_url": url, "state": state, "redirect_uri": cfg.redirect_uri, "env": cfg.env}

    @app.get("/api/integrations/procore/oauth/callback")
    def procore_oauth_callback(code: str = "", state: str = "") -> HTMLResponse:
        from .integrations.procore import ProcoreOAuth, ProcoreOAuthConfig, ProcoreTokenStore

        audit: AuditLogger = app.state.audit
        cfg = ProcoreOAuthConfig.from_env()
        oauth = ProcoreOAuth(cfg, ProcoreTokenStore())

        if not code:
            raise HTTPException(status_code=400, detail="missing code")
        if state and state not in app.state.procore_oauth_state:
            raise HTTPException(status_code=400, detail="invalid state")

        tokens = oauth.exchange_code(code=code)
        app.state.procore_tokens = tokens
        audit.append(actor="human", action="procore_oauth_connected", scope="external_low", details={"env": cfg.env})

        html = f"""
        <!doctype html>
        <html><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;margin:24px;">
          <h3>Procore connected</h3>
          <div>Env: <code>{cfg.env}</code></div>
          <div>Company: <code>{cfg.company_id or "(missing PROCORE_COMPANY_ID)"}</code></div>
          <div style="margin-top:10px;">
            Refresh token was stored to OS keychain if <code>keyring</code> is installed; otherwise set <code>PROCORE_REFRESH_TOKEN</code>.
          </div>
          <div style="margin-top:10px;"><a href="/ui/ops">Back to Ops UI</a></div>
        </body></html>
        """
        return HTMLResponse(content=html)

    @app.post("/api/integrations/procore/token/refresh")
    def procore_refresh_token() -> dict[str, Any]:
        from .integrations.procore import ProcoreOAuth, ProcoreOAuthConfig, ProcoreTokenStore

        cfg = ProcoreOAuthConfig.from_env()
        oauth = ProcoreOAuth(cfg, ProcoreTokenStore())
        tokens = oauth.refresh_access_token()
        app.state.procore_tokens = tokens
        return {"ok": True, "expires_at_epoch": tokens.expires_at_epoch}

    def _get_procore_access_token() -> str:
        from .integrations.procore import ProcoreOAuth, ProcoreOAuthConfig, ProcoreTokenStore, ProcoreTokens

        cfg = ProcoreOAuthConfig.from_env()
        oauth = ProcoreOAuth(cfg, ProcoreTokenStore())
        tok: Optional[ProcoreTokens] = app.state.procore_tokens
        if tok is None or tok.is_expired:
            tok = oauth.refresh_access_token()
            app.state.procore_tokens = tok
        return tok.access_token

    @app.get("/api/integrations/procore/projects")
    def procore_list_projects() -> Any:
        from .integrations.procore import ProcoreClient, ProcoreOAuthConfig

        cfg = ProcoreOAuthConfig.from_env()
        access = _get_procore_access_token()
        client = ProcoreClient(api_base_url=cfg.api_base_url, access_token=access, company_id=cfg.company_id)
        return client.list_company_projects()

    @app.post("/api/integrations/procore/get")
    def procore_raw_get(body: ProcoreRawGetIn) -> Any:
        """
        Read-only escape hatch for REST resources not yet modeled.

        Example path: /rest/v1.0/projects
        """
        from .integrations.procore import ProcoreClient, ProcoreOAuthConfig

        path = (body.path or "").strip()
        if not path.startswith("/rest/"):
            raise HTTPException(status_code=400, detail="path must start with /rest/")

        cfg = ProcoreOAuthConfig.from_env()
        access = _get_procore_access_token()
        client = ProcoreClient(api_base_url=cfg.api_base_url, access_token=access, company_id=cfg.company_id)
        return client.get(path, params=body.params or {})

    @app.post("/api/integrations/procore/sync/projects")
    def procore_sync_projects() -> dict[str, Any]:
        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        projects = procore_list_projects()
        now = utcnow_iso()

        created = 0
        updated = 0
        with db.tx() as conn:
            for p in projects or []:
                pid = str(p.get("id") or "").strip()
                name = str(p.get("name") or "").strip()
                if not pid or not name:
                    continue
                ext = f"procore:{pid}"
                row = conn.execute("SELECT id FROM projects WHERE external_ref = ?", (ext,)).fetchone()
                if row:
                    conn.execute("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?", (name, now, row["id"]))
                    updated += 1
                else:
                    proj_id = uuid.uuid4().hex
                    conn.execute(
                        "INSERT INTO projects (id, name, status, customer_id, external_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (proj_id, name, "active", None, ext, now, now),
                    )
                    created += 1

        audit.append(actor="system", action="procore_projects_synced", scope="external_low", details={"created": created, "updated": updated})
        return {"created": created, "updated": updated}

    @app.post("/api/integrations/accounting/export/invoices")
    def accounting_export_invoices(body: Optional[AccountingExportInvoicesIn] = None) -> dict[str, Any]:
        from pathlib import Path
        from .integrations.accounting import export_invoices_csv

        s: FranklinOpsSettings = app.state.settings
        body = body or AccountingExportInvoicesIn()
        ts = utcnow_iso().replace(":", "").replace("-", "").split(".")[0]
        out_path = Path(s.data_dir) / "exports" / f"invoices_{ts}.csv"
        return export_invoices_csv(app.state.db, out_path=out_path, kind=body.kind, status=body.status)

    @app.post("/api/integrations/accounting/export/cashflow_lines")
    def accounting_export_cashflow(body: Optional[AccountingExportCashflowLinesIn] = None) -> dict[str, Any]:
        from pathlib import Path
        from .integrations.accounting import export_cashflow_lines_csv

        s: FranklinOpsSettings = app.state.settings
        body = body or AccountingExportCashflowLinesIn()
        ts = utcnow_iso().replace(":", "").replace("-", "").split(".")[0]
        out_path = Path(s.data_dir) / "exports" / f"cashflow_lines_{ts}.csv"
        return export_cashflow_lines_csv(app.state.db, out_path=out_path, start_week=body.start_week)

    @app.post("/api/integrations/accounting/import/invoices")
    def accounting_import_invoices(body: AccountingImportInvoicesIn) -> dict[str, Any]:
        from .integrations.accounting import import_invoices_csv_from_artifact

        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        try:
            return import_invoices_csv_from_artifact(
                db,
                audit,
                artifact_id=body.artifact_id,
                source=body.source,
                default_kind=body.default_kind,
                limit=body.limit,
            )
        except (KeyError, FileNotFoundError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/integrations/accounting/import/payments")
    def accounting_import_payments(body: AccountingImportPaymentsIn) -> dict[str, Any]:
        from .integrations.accounting import import_payments_csv_from_artifact

        db: OpsDB = app.state.db
        audit: AuditLogger = app.state.audit
        try:
            return import_payments_csv_from_artifact(db, audit, artifact_id=body.artifact_id)
        except (KeyError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    # -------------------------
    # Rollout + metrics ("tire" loop)
    # -------------------------

    @app.post("/api/pilot/run")
    def run_pilot() -> dict[str, Any]:
        from .run_pilot import run_pilot as do_run

        return do_run()

    @app.get("/api/metrics/summary")
    def metrics_summary(days: int = 7) -> dict[str, Any]:
        from .metrics import (
            approvals_stats,
            audit_action_counts,
            drafts_created_count,
            outbound_stats,
            pilot_runs_count,
            tasks_stats,
            time_saved_estimate_minutes,
        )

        db: OpsDB = app.state.db
        approvals = approvals_stats(db, days=days)
        actions = audit_action_counts(db, days=days)
        drafts = drafts_created_count(db, days=days)
        tasks = tasks_stats(db, days=days)
        outbound = outbound_stats(db, days=days)
        pilot_runs = pilot_runs_count(db, days=30)

        auto = int((approvals.get("totals") or {}).get("auto_approved", 0))
        est_minutes = time_saved_estimate_minutes(approvals_auto_approved=auto, drafts_created=int(drafts))
        return {
            "approvals": approvals,
            "audit": actions,
            "drafts_created": int(drafts),
            "tasks": tasks,
            "outbound": outbound,
            "pilot_runs_last_30_days": int(pilot_runs),
            "estimated_time_saved_minutes": est_minutes,
        }

    @app.get("/api/tire/recommendations")
    def tire_next(days: int = 30, limit: int = 10) -> dict[str, Any]:
        from .metrics import tire_recommendations

        db: OpsDB = app.state.db
        return tire_recommendations(db, days=days, limit=limit)

    # -------------------------
    # Onboarding & User Experience
    # -------------------------

    @app.get("/api/onboarding/state")
    def get_onboarding_state(user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        return onboarding.get_onboarding_progress(user_id)

    @app.post("/api/onboarding/detect_business_type")
    def detect_business_type(body: OnboardingBusinessTypeIn, user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        detection_result = onboarding.detect_business_type(body.dict())
        
        # Update user state with detected business type
        onboarding.update_onboarding_state(
            user_id=user_id,
            business_type=detection_result["detected_type"]
        )
        
        # Generate welcome message
        welcome = create_welcome_message(
            business_type=detection_result["detected_type"],
            user_name=""
        )
        
        return {
            **detection_result,
            "welcome_message": welcome
        }

    @app.post("/api/onboarding/auto_detect_folders") 
    def auto_detect_folders(user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        detection_result = onboarding.auto_detect_folders()
        
        # Update progress if folders were found
        if detection_result["detected_folders"]:
            current_progress = onboarding.get_onboarding_state(user_id)["setup_progress"]
            current_progress["detected_folders"] = detection_result["detected_folders"]
            
            onboarding.update_onboarding_state(
                user_id=user_id,
                setup_progress=current_progress
            )
        
        return detection_result

    @app.post("/api/onboarding/complete_step")
    def complete_onboarding_step(body: OnboardingStepCompleteIn, user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        state = onboarding.get_onboarding_state(user_id)
        
        completed_steps = state.get("completed_steps", [])
        if body.step_id not in completed_steps:
            completed_steps.append(body.step_id)
            
            # Record achievement
            onboarding.record_achievement(
                user_id=user_id,
                achievement_type="step_completed",
                achievement_data={"step_id": body.step_id, "step_data": body.step_data}
            )
        
        # Update progress
        setup_progress = state.get("setup_progress", {})
        setup_progress.update(body.step_data)
        
        # Check if onboarding is complete
        total_steps = 4  # Based on our setup plan
        onboarding_completed = len(completed_steps) >= total_steps
        
        updated_state = onboarding.update_onboarding_state(
            user_id=user_id,
            completed_steps=completed_steps,
            setup_progress=setup_progress,
            onboarding_completed=onboarding_completed
        )
        
        if onboarding_completed and not state.get("onboarding_completed", False):
            onboarding.record_achievement(
                user_id=user_id,
                achievement_type="onboarding_completed",
                achievement_data={"total_steps": len(completed_steps)}
            )
        
        return {
            "success": True,
            "state": updated_state,
            "progress_percentage": len(completed_steps) / total_steps * 100
        }

    @app.post("/api/onboarding/preferences")
    def update_onboarding_preferences(body: OnboardingPreferencesIn, user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        return onboarding.update_onboarding_state(
            user_id=user_id,
            preferences=body.preferences
        )

    @app.get("/api/onboarding/setup_plan") 
    def get_setup_plan(user_id: str = "default") -> dict[str, Any]:
        onboarding: OnboardingOrchestrator = app.state.onboarding
        return onboarding.generate_setup_plan(user_id)

    # -------------------------
    # Customer Service & Support
    # -------------------------

    @app.post("/api/support/scan")
    def run_proactive_scan() -> dict[str, Any]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.run_proactive_scan()

    @app.get("/api/support/issues")
    def get_active_issues(limit: int = 20) -> list[dict[str, Any]]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.get_active_issues(limit=limit)

    @app.get("/api/support/suggestions") 
    def get_suggestions(limit: int = 10) -> list[dict[str, Any]]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.get_active_suggestions(limit=limit)

    @app.post("/api/support/issues/{issue_id}/resolve")
    def resolve_issue(issue_id: int, resolution_note: str = "") -> dict[str, Any]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.resolve_issue(issue_id, resolution_note)

    @app.post("/api/support/suggestions/{suggestion_id}/dismiss")
    def dismiss_suggestion(suggestion_id: int) -> dict[str, Any]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.dismiss_suggestion(suggestion_id)

    @app.post("/api/support/translate_error")
    def translate_error(error_message: str, context: dict[str, Any] = None) -> dict[str, Any]:
        customer_service: ProactiveCustomerService = app.state.customer_service
        return customer_service.translate_error(error_message, context or {})

    # -------------------------
    # Smart Notifications
    # -------------------------

    @app.post("/api/notifications/generate")
    def generate_notifications(user_id: str = "default") -> dict[str, Any]:
        notifications: SmartNotificationSystem = app.state.notifications
        return notifications.generate_smart_notifications(user_id)

    @app.get("/api/notifications")
    def get_notifications(user_id: str = "default", limit: int = 20) -> list[dict[str, Any]]:
        notifications: SmartNotificationSystem = app.state.notifications
        return notifications.get_active_notifications(user_id, limit)

    @app.get("/api/notifications/summary")
    def get_notification_summary(user_id: str = "default") -> dict[str, Any]:
        notifications: SmartNotificationSystem = app.state.notifications
        return notifications.get_notification_summary(user_id)

    @app.post("/api/notifications/{notification_id}/action")
    def notification_action(notification_id: int, body: NotificationActionIn, user_id: str = "default") -> dict[str, Any]:
        notifications: SmartNotificationSystem = app.state.notifications
        
        success = False
        if body.action_type == "read":
            success = notifications.mark_notification_read(notification_id, user_id)
        elif body.action_type == "click":
            success = notifications.mark_notification_clicked(notification_id, user_id)
        elif body.action_type == "dismiss":
            success = notifications.dismiss_notification(notification_id, user_id)
        
        return {"success": success, "action": body.action_type}

    # -------------------------
    # Enhanced Conversational UI
    # -------------------------

    @app.get("/ui/enhanced")
    def enhanced_ui() -> HTMLResponse:
        """Enhanced conversational UI with smart notifications."""
        html = """
        <!DOCTYPE html>
        <html>
          <head>
            <title>FranklinOps - Your Business Intelligence Assistant</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
""" + THEME_CSS + """
              .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
              .header { background: rgba(18, 45, 32, 0.35); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(232, 197, 71, 0.25); border-radius: 16px; padding: 28px; margin-bottom: 28px; box-shadow: 0 8px 32px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.05); }
              .welcome-message { font-size: 20px; margin-bottom: 18px; color: #f5f7f5; font-weight: 500; }
              .suggestions { display: flex; flex-wrap: wrap; gap: 12px; }
              .suggestion { background: rgba(232, 197, 71, 0.1); backdrop-filter: blur(8px); border: 1px solid rgba(232, 197, 71, 0.35); padding: 10px 18px; border-radius: 24px; font-size: 14px; cursor: pointer; transition: all 0.25s; color: #f0f4f2; font-weight: 500; }
              .suggestion:hover { background: rgba(232, 197, 71, 0.2); border-color: #e8c547; transform: translateY(-2px); box-shadow: 0 4px 20px rgba(232, 197, 71, 0.15); }
              .suggestion.high { background: rgba(232, 107, 107, 0.2); border-color: rgba(232, 107, 107, 0.5); color: #e86b6b; }
              .suggestion.medium { background: rgba(232, 197, 71, 0.2); border-color: #e8c547; color: #e8c547; }
              .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 28px; }
              .left-panel, .right-panel { display: flex; flex-direction: column; gap: 24px; }
              .card-title { font-size: 20px; font-weight: 600; margin-bottom: 18px; display: flex; align-items: center; color: #f5f7f5; }
              .card-title .icon { margin-right: 10px; }
              .chat-container { min-height: 400px; }
              .chat-messages { height: 300px; overflow-y: auto; border: 1px solid rgba(232, 197, 71, 0.25); border-radius: 12px; padding: 18px; margin-bottom: 18px; background: rgba(8, 28, 18, 0.5); backdrop-filter: blur(16px); box-shadow: inset 0 2px 8px rgba(0,0,0,0.15); }
              .chat-input-container { display: flex; gap: 14px; }
              .chat-input { flex: 1; padding: 14px 18px; border: 1px solid rgba(232, 197, 71, 0.35); border-radius: 12px; font-size: 16px; background: rgba(8, 28, 18, 0.5); backdrop-filter: blur(8px); color: #f0f4f2; }
              .chat-send { padding: 14px 28px; background: rgba(26, 58, 42, 0.5); backdrop-filter: blur(12px); border: 1px solid rgba(232, 197, 71, 0.5); border-radius: 12px; cursor: pointer; font-size: 16px; font-weight: 600; color: #f0f4f2; transition: all 0.25s; }
              .chat-send:hover { background: rgba(232, 197, 71, 0.2); box-shadow: 0 6px 24px rgba(232, 197, 71, 0.2); transform: translateY(-1px); }
              .message { margin-bottom: 18px; padding: 14px 18px; border-radius: 12px; backdrop-filter: blur(12px); }
              .message.user { background: rgba(232, 197, 71, 0.12); text-align: right; border: 1px solid rgba(232, 197, 71, 0.25); }
              .message.assistant { background: rgba(18, 45, 32, 0.4); border: 1px solid rgba(232, 197, 71, 0.2); }
              .message .sender { font-weight: 600; margin-bottom: 6px; font-size: 14px; color: #e8c547; }
              .notifications-list { max-height: 400px; overflow-y: auto; }
              .notification { padding: 18px; border-left: 4px solid rgba(232, 197, 71, 0.5); margin-bottom: 14px; background: rgba(18, 45, 32, 0.35); backdrop-filter: blur(16px); border-radius: 0 12px 12px 0; border: 1px solid rgba(232, 197, 71, 0.15); }
              .notification.high { border-left-color: #e86b6b; }
              .notification.medium { border-left-color: #e8c547; }
              .notification.low { border-left-color: #5dd68a; }
              .notification-title { font-weight: 600; margin-bottom: 6px; color: #f5f7f5; }
              .notification-message { font-size: 14px; color: #9eb5a8; margin-bottom: 10px; }
              .notification-actions { display: flex; gap: 10px; }
              .notification-action { padding: 6px 14px; background: rgba(232, 197, 71, 0.12); backdrop-filter: blur(8px); border: 1px solid rgba(232, 197, 71, 0.35); border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 500; color: #f0f4f2; transition: all 0.2s; }
              .notification-action:hover { background: rgba(232, 197, 71, 0.25); }
              .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 18px; }
              .stat { text-align: center; padding: 20px; background: rgba(18, 45, 32, 0.4); backdrop-filter: blur(16px); border: 1px solid rgba(232, 197, 71, 0.2); border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
              .stat-number { font-size: 28px; font-weight: 700; color: #e8c547; }
              .stat-label { font-size: 14px; color: #9eb5a8; margin-top: 6px; }
              .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
              .quick-action { padding: 20px; background: rgba(18, 45, 32, 0.35); backdrop-filter: blur(16px); border: 1px solid rgba(232, 197, 71, 0.25); border-radius: 12px; cursor: pointer; text-align: center; transition: all 0.25s; color: #f0f4f2; }
              .quick-action:hover { background: rgba(232, 197, 71, 0.15); border-color: #e8c547; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(232, 197, 71, 0.15); }
              .quick-action .icon { font-size: 28px; margin-bottom: 10px; }
              .quick-action .text { font-size: 14px; font-weight: 600; }
              .loading { text-align: center; padding: 24px; color: #9eb5a8; }
              .error { color: #e86b6b; background: rgba(232, 107, 107, 0.15); backdrop-filter: blur(8px); padding: 18px; border-radius: 12px; margin: 18px 0; border: 1px solid rgba(232, 107, 107, 0.4); }
              @media (max-width: 768px) {
                .main-grid { grid-template-columns: 1fr; }
                .suggestions { flex-direction: column; }
                .stats-grid { grid-template-columns: repeat(2, 1fr); }
                .quick-actions { grid-template-columns: repeat(2, 1fr); }
              }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <div class="welcome-message" id="welcomeMessage">Loading...</div>
                <div class="suggestions" id="suggestions"></div>
              </div>
              
              <div class="main-grid">
                <div class="left-panel">
                  <div class="card chat-container">
                    <div class="card-title">
                      <span class="icon">💬</span>
                      Ask me anything about your business
                    </div>
                    <div class="chat-messages" id="chatMessages">
                      <div class="message assistant">
                        <div class="sender">FranklinOps Assistant</div>
                        <div>Hi! I can help you find information, automate tasks, and optimize your business operations. Try asking me something like "Show me overdue invoices" or "What projects need attention?"</div>
                      </div>
                    </div>
                    <div class="chat-input-container">
                      <input type="text" class="chat-input" id="chatInput" placeholder="Ask me about your business..." />
                      <button class="chat-send" onclick="sendChatMessage()">Send</button>
                    </div>
                  </div>
                  
                  <div class="card">
                    <div class="card-title">
                      <span class="icon">📊</span>
                      Business Overview
                    </div>
                    <div class="stats-grid" id="statsGrid">
                      <div class="loading">Loading stats...</div>
                    </div>
                  </div>
                </div>
                
                <div class="right-panel">
                  <div class="card">
                    <div class="card-title">
                      <span class="icon">🔔</span>
                      Smart Notifications
                    </div>
                    <div class="notifications-list" id="notificationsList">
                      <div class="loading">Loading notifications...</div>
                    </div>
                  </div>
                  
                  <div class="card">
                    <div class="card-title">
                      <span class="icon">⚡</span>
                      Quick Actions
                    </div>
                    <div class="quick-actions">
                      <button class="quick-action" onclick="runPilot()">
                        <div class="icon">🚀</div>
                        <div class="text">Run Automation</div>
                      </button>
                      <button class="quick-action" onclick="showApprovals()">
                        <div class="icon">✅</div>
                        <div class="text">Approvals</div>
                      </button>
                      <button class="quick-action" onclick="showTasks()">
                        <div class="icon">📋</div>
                        <div class="text">Tasks</div>
                      </button>
                      <button class="quick-action" onclick="showMetrics()">
                        <div class="icon">📈</div>
                        <div class="text">Analytics</div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <script>
              // Utility functions
              async function apiGet(url) {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
              }
              
              async function apiPost(url, data = {}) {
                const response = await fetch(url, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(data)
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
              }
              
              // Load initial data
              async function loadDashboard() {
                try {
                  // Generate smart notifications
                  await apiPost('/api/notifications/generate');
                  
                  // Load all dashboard data in parallel
                  const [notifications, approvals, tasks, metrics] = await Promise.all([
                    apiGet('/api/notifications'),
                    apiGet('/api/approvals?status=pending&limit=5'),
                    apiGet('/api/tasks?status=pending&limit=5'),
                    apiGet('/api/metrics/summary?days=7')
                  ]);
                  
                  // Update welcome message with context
                  const context = {
                    pending_approvals: approvals.length,
                    overdue_tasks: tasks.filter(t => t.due_date && new Date(t.due_date) < new Date()).length,
                    new_notifications: notifications.filter(n => !n.read).length,
                    recent_automations: metrics.automated_actions || 0,
                    time_of_day: getTimeOfDay()
                  };
                  
                  updateWelcomeMessage(context);
                  updateNotifications(notifications);
                  updateStats(metrics, approvals.length, tasks.length);
                  
                } catch (error) {
                  console.error('Error loading dashboard:', error);
                  document.getElementById('welcomeMessage').textContent = 'Welcome back! Some features may be loading...';
                }
              }
              
              function getTimeOfDay() {
                const hour = new Date().getHours();
                if (hour < 12) return 'morning';
                if (hour < 17) return 'afternoon';
                return 'evening';
              }
              
              function updateWelcomeMessage(context) {
                const greeting = {
                  morning: 'Good morning',
                  afternoon: 'Good afternoon', 
                  evening: 'Good evening'
                }[context.time_of_day] || 'Hello';
                
                let message = `${greeting}! `;
                
                if (context.recent_automations > 0) {
                  message += `I automated ${context.recent_automations} tasks recently. `;
                }
                
                if (context.pending_approvals > 0) {
                  message += `You have ${context.pending_approvals} item${context.pending_approvals > 1 ? 's' : ''} awaiting approval. `;
                }
                
                if (context.overdue_tasks > 0) {
                  message += `${context.overdue_tasks} task${context.overdue_tasks > 1 ? 's are' : ' is'} overdue. `;
                }
                
                if (context.pending_approvals === 0 && context.overdue_tasks === 0) {
                  message += 'Everything looks good! What would you like to work on today?';
                } else {
                  message += 'What would you like to tackle first?';
                }
                
                document.getElementById('welcomeMessage').textContent = message;
                
                // Update suggestions
                updateSuggestions(context);
              }
              
              function updateSuggestions(context) {
                const suggestionsEl = document.getElementById('suggestions');
                suggestionsEl.innerHTML = '';
                
                const suggestions = [];
                
                if (context.pending_approvals > 0) {
                  suggestions.push({
                    text: `⏳ Review ${context.pending_approvals} approval${context.pending_approvals > 1 ? 's' : ''}`,
                    action: 'showApprovals',
                    priority: 'high'
                  });
                }
                
                if (context.overdue_tasks > 0) {
                  suggestions.push({
                    text: `🚨 Update ${context.overdue_tasks} overdue task${context.overdue_tasks > 1 ? 's' : ''}`,
                    action: 'showTasks',
                    priority: 'high'
                  });
                }
                
                suggestions.push(
                  { text: '💬 Ask me about your business', action: 'focusChat', priority: 'low' },
                  { text: '⚡ Run automation scan', action: 'runPilot', priority: 'low' },
                  { text: '📊 View business insights', action: 'showMetrics', priority: 'low' }
                );
                
                suggestions.slice(0, 6).forEach(suggestion => {
                  const el = document.createElement('div');
                  el.className = `suggestion ${suggestion.priority}`;
                  el.textContent = suggestion.text;
                  el.onclick = () => window[suggestion.action] && window[suggestion.action]();
                  suggestionsEl.appendChild(el);
                });
              }
              
              function updateNotifications(notifications) {
                const listEl = document.getElementById('notificationsList');
                listEl.innerHTML = '';
                
                if (notifications.length === 0) {
                  listEl.innerHTML = '<div class="loading">No new notifications</div>';
                  return;
                }
                
                notifications.slice(0, 10).forEach(notification => {
                  const el = document.createElement('div');
                  el.className = `notification ${notification.priority >= 4 ? 'high' : notification.priority >= 3 ? 'medium' : 'low'}`;
                  
                  el.innerHTML = `
                    <div class="notification-title">${notification.title}</div>
                    <div class="notification-message">${notification.message}</div>
                    <div class="notification-actions">
                      ${notification.action_data.type ? `<button class="notification-action" onclick="handleNotificationAction(${notification.id}, '${notification.action_data.type}')">Take Action</button>` : ''}
                      <button class="notification-action" onclick="dismissNotification(${notification.id})">Dismiss</button>
                    </div>
                  `;
                  
                  listEl.appendChild(el);
                });
              }
              
              function updateStats(metrics, approvals, tasks) {
                const statsEl = document.getElementById('statsGrid');
                statsEl.innerHTML = `
                  <div class="stat">
                    <div class="stat-number">${approvals}</div>
                    <div class="stat-label">Pending Approvals</div>
                  </div>
                  <div class="stat">
                    <div class="stat-number">${tasks}</div>
                    <div class="stat-label">Active Tasks</div>
                  </div>
                  <div class="stat">
                    <div class="stat-number">${metrics.automated_actions || 0}</div>
                    <div class="stat-label">Automated This Week</div>
                  </div>
                  <div class="stat">
                    <div class="stat-number">${Math.round((metrics.time_saved_minutes || 0) / 60)}h</div>
                    <div class="stat-label">Time Saved</div>
                  </div>
                `;
              }
              
              // Chat functionality
              async function sendChatMessage() {
                const input = document.getElementById('chatInput');
                const message = input.value.trim();
                if (!message) return;
                
                input.value = '';
                addChatMessage('user', 'You', message);
                
                try {
                  const response = await apiPost('/api/ops_chat', { question: message });
                  
                  if (response.status === 'ok' && response.answer) {
                    addChatMessage('assistant', 'FranklinOps', response.answer);
                    
                    // Show citations if available
                    if (response.citations && response.citations.length > 0) {
                      const citationText = response.citations.slice(0, 3).map(c => 
                        `📄 ${c.source}: ${c.path}`
                      ).join('\\n');
                      addChatMessage('assistant', 'Sources', citationText);
                    }
                  } else {
                    addChatMessage('assistant', 'FranklinOps', response.answer || 'I encountered an issue processing your request.');
                  }
                } catch (error) {
                  addChatMessage('assistant', 'FranklinOps', 'Sorry, I encountered an error. Please try again.');
                }
              }
              
              function addChatMessage(type, sender, message) {
                const messagesEl = document.getElementById('chatMessages');
                const messageEl = document.createElement('div');
                messageEl.className = `message ${type}`;
                messageEl.innerHTML = `
                  <div class="sender">${sender}</div>
                  <div>${message}</div>
                `;
                messagesEl.appendChild(messageEl);
                messagesEl.scrollTop = messagesEl.scrollHeight;
              }
              
              // Action handlers
              async function runPilot() {
                try {
                  addChatMessage('assistant', 'FranklinOps', 'Running automation scan...');
                  const result = await apiPost('/api/pilot/run');
                  const summary = Object.entries(result).map(([key, value]) => {
                    if (typeof value === 'object' && value !== null) {
                      const counts = Object.values(value).filter(v => typeof v === 'number');
                      return `${key}: ${counts.join(', ')} items processed`;
                    }
                    return `${key}: ${value}`;
                  }).join('\\n');
                  addChatMessage('assistant', 'FranklinOps', `Automation complete!\\n${summary}`);
                } catch (error) {
                  addChatMessage('assistant', 'FranklinOps', 'Error running automation scan.');
                }
              }
              
              function showApprovals() { window.open('/ui/ops', '_blank'); }
              function showTasks() { window.open('/ui/ops', '_blank'); }
              function showMetrics() { window.open('/ui', '_blank'); }
              function focusChat() { document.getElementById('chatInput').focus(); }
              
              async function handleNotificationAction(notificationId, actionType) {
                try {
                  await apiPost(`/api/notifications/${notificationId}/action`, { 
                    notification_id: notificationId,
                    action_type: 'click'
                  });
                  // Reload notifications
                  const notifications = await apiGet('/api/notifications');
                  updateNotifications(notifications);
                } catch (error) {
                  console.error('Error handling notification action:', error);
                }
              }
              
              async function dismissNotification(notificationId) {
                try {
                  await apiPost(`/api/notifications/${notificationId}/action`, {
                    notification_id: notificationId,
                    action_type: 'dismiss'
                  });
                  // Reload notifications
                  const notifications = await apiGet('/api/notifications');
                  updateNotifications(notifications);
                } catch (error) {
                  console.error('Error dismissing notification:', error);
                }
              }
              
              // Enter key support for chat
              document.getElementById('chatInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendChatMessage();
              });
              
              // Load dashboard on page load
              loadDashboard();
              
              // Auto-refresh every 5 minutes
              setInterval(loadDashboard, 5 * 60 * 1000);
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    # -------------------------
    # Lightweight UI (no extra deps)
    # -------------------------

    @app.get("/ui")
    def ui_home() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>FranklinOpsHub</title>
            <style>
""" + THEME_CSS + """
              .dashboard-grid { display: grid; grid-template-columns: 1fr 340px; gap: 24px; margin-top: 20px; }
              @media (max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } }
              .chat-container { min-height: 320px; }
              .chat-messages { height: 220px; overflow-y: auto; border: 1px solid rgba(232, 197, 71, 0.25); border-radius: 12px; padding: 14px; margin-bottom: 12px; background: rgba(8, 28, 18, 0.5); backdrop-filter: blur(16px); }
              .chat-input-container { display: flex; gap: 10px; }
              .chat-input { flex: 1; padding: 12px 14px; border: 1px solid rgba(232, 197, 71, 0.35); border-radius: 10px; font-size: 15px; background: rgba(8, 28, 18, 0.5); color: #f0f4f2; }
              .chat-send { padding: 12px 20px; background: rgba(26, 58, 42, 0.5); border: 1px solid rgba(232, 197, 71, 0.5); border-radius: 10px; cursor: pointer; font-weight: 600; color: #f0f4f2; }
              .chat-send:hover { background: rgba(232, 197, 71, 0.2); }
              .message { margin-bottom: 12px; padding: 10px 14px; border-radius: 10px; font-size: 14px; }
              .message.user { background: rgba(232, 197, 71, 0.12); text-align: right; }
              .message.assistant { background: rgba(18, 45, 32, 0.4); }
              .message .sender { font-weight: 600; margin-bottom: 4px; font-size: 12px; color: #e8c547; }
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">FranklinOpsHub</h2>
              <span class="pill">Dashboard</span>
              <a class="muted" href="/ui/ops">ops</a>
              <a class="muted" href="/docs">api</a>
            </div>

            <div class="dashboard-grid">
              <div>
                <div class="card chat-container">
                  <div style="font-weight:600;margin-bottom:12px;color:#f5f7f5;">💬 Ask me anything about your business</div>
                  <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                      <div class="sender">FranklinOps</div>
                      <div>Hi! I can help you find information, automate tasks, and answer questions. Try "Show me overdue invoices" or "What needs attention today?"</div>
                    </div>
                  </div>
                  <div class="chat-input-container">
                    <input type="text" class="chat-input" id="chatInput" placeholder="Ask me about your business..." />
                    <button class="chat-send" onclick="sendChatMessage()">Send</button>
                  </div>
                </div>

                <div class="card">
                  <div><b>Today queue</b> <span class="muted">(calls, invoices, approvals)</span></div>
                  <div id="todayQueue" class="muted" style="margin-top:6px;">Loading...</div>
                  <div style="margin-top:8px;"><a href="/ui/ops">View full Ops dashboard →</a></div>
                </div>
              </div>

              <div>
                <div class="card">
                  <div><b>Navigate</b></div>
                  <div style="margin-top:8px;"><a href="/ui/ops">Ops dashboard</a></div>
                  <div><a href="/ui/sales">SalesSpokes pipeline</a></div>
                  <div><a href="/ui/finance">FinanceSpokes</a></div>
                  <div><a href="/ui/grokstmate">GROKSTMATE</a></div>
                  <div><a href="/ui/fleet">Superagents Fleet</a></div>
                  <div><a href="/ui/bidzone">BID-ZONE</a></div>
                  <div><a href="/ui/project_controls">Project Controls</a></div>
                  <div><a href="/ui/rollout">Rollout pilot</a></div>
                  <div style="margin-top:8px;"><a href="/docs">API docs</a></div>
                </div>
                <div class="card">
                  <div><b>Quick tips</b></div>
                  <div style="margin-top:6px;"><code>POST /api/ingest/run</code></div>
                  <div><code>POST /api/sales/inbound/scan</code></div>
                  <div><code>POST /api/finance/ap_intake/run</code></div>
                </div>
              </div>
            </div>

            <script>
              document.getElementById('chatInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendChatMessage();
              });

              async function sendChatMessage() {
                const input = document.getElementById('chatInput');
                const msg = input.value.trim();
                if (!msg) return;
                input.value = '';
                addChatMessage('user', 'You', msg);
                try {
                  const r = await fetch('/api/ops_chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: msg })
                  });
                  const data = r.ok ? await r.json() : {};
                  addChatMessage('assistant', 'FranklinOps', data.answer || 'Sorry, I encountered an error.');
                } catch (e) {
                  addChatMessage('assistant', 'FranklinOps', 'Sorry, I encountered an error.');
                }
              }

              function addChatMessage(type, sender, text) {
                const el = document.createElement('div');
                el.className = 'message ' + type;
                el.innerHTML = '<div class="sender">' + sender + '</div><div>' + text + '</div>';
                document.getElementById('chatMessages').appendChild(el);
                document.getElementById('chatMessages').scrollTop = 99999;
              }

              (async function() {
                try {
                  const [approvals, tasks, invoices] = await Promise.all([
                    fetch("/api/approvals?status=pending&limit=10").then(r => r.ok ? r.json() : []),
                    fetch("/api/tasks?status=open&limit=10").then(r => r.ok ? r.json() : []),
                    fetch("/api/finance/invoices?kind=AP&status=pending&limit=10").then(r => r.ok ? r.json() : []),
                  ]);
                  const pending = Array.isArray(approvals) ? approvals.length : 0;
                  const openTasks = Array.isArray(tasks) ? tasks.length : 0;
                  const apInvoices = Array.isArray(invoices) ? invoices.length : 0;
                  const parts = [];
                  if (pending > 0) parts.push(pending + " approval(s) pending");
                  if (openTasks > 0) parts.push(openTasks + " open task(s)");
                  if (apInvoices > 0) parts.push(apInvoices + " AP invoice(s) pending");
                  document.getElementById("todayQueue").textContent = parts.length ? parts.join(" • ") : "No pending items";
                } catch (e) {
                  document.getElementById("todayQueue").textContent = "Could not load";
                }
              })();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/ops")
    def ui_ops() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>FranklinOpsHub — Ops</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">Ops</h2>
              <span class="pill">tasks • approvals • autonomy</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/docs">api</a>
            </div>

            <div class="row" style="margin-top:10px;">
              <button onclick="runIngest()">Run ingest</button>
              <button onclick="rebuildIndex()">Rebuild doc index</button>
              <button onclick="runPilot()">Run full pilot</button>
              <button onclick="reloadAll()">Reload</button>
              <span id="status" class="muted"></span>
            </div>

            <div class="grid">
              <div class="card">
                <div class="row"><b>Pending approvals</b> <span class="muted">(actionable)</span></div>
                <div id="approvals"></div>
              </div>

              <div class="card">
                <div class="row"><b>Open tasks</b> <span class="muted">(all kinds)</span></div>
                <div id="tasks"></div>
              </div>

              <div class="card">
                <div class="row"><b>Recent audit events</b> <span class="muted">(evidence trail)</span></div>
                <div id="audit"></div>
              </div>

              <div class="card">
                <div class="row"><b>Autonomy settings</b> <span class="muted">(per workflow)</span></div>
                <div id="autonomy"></div>
              </div>

              <div class="card">
                <div class="row"><b>Evidence / details</b> <span class="muted">(click “view”)</span></div>
                <pre id="evidence">(select an approval/task)</pre>
              </div>
            </div>

            <script>
              const elStatus = () => document.getElementById("status");
              const setStatus = (msg, cls="muted") => { const el = elStatus(); el.className = cls; el.textContent = msg; };
              const setEvidence = (obj) => { document.getElementById("evidence").textContent = JSON.stringify(obj, null, 2); };

              async function jget(url) {
                const r = await fetch(url);
                if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
                return await r.json();
              }
              async function jpost(url, body=null) {
                const r = await fetch(url, {
                  method: "POST",
                  headers: {"Content-Type": "application/json"},
                  body: body ? JSON.stringify(body) : null
                });
                if (!r.ok) throw new Error(`${r.status} ${r.statusText} :: ${(await r.text()).slice(0,200)}`);
                return await r.json();
              }
              async function jput(url, body) {
                const r = await fetch(url, {
                  method: "PUT",
                  headers: {"Content-Type": "application/json"},
                  body: JSON.stringify(body)
                });
                if (!r.ok) throw new Error(`${r.status} ${r.statusText} :: ${(await r.text()).slice(0,200)}`);
                return await r.json();
              }

              function renderTable(targetId, rows, cols) {
                const el = document.getElementById(targetId);
                if (!rows || rows.length === 0) { el.innerHTML = "<div class='muted'>None</div>"; return; }
                let html = "<table><thead><tr>";
                for (const c of cols) html += `<th>${c.label}</th>`;
                html += "</tr></thead><tbody>";
                for (const row of rows) {
                  html += "<tr>";
                  for (const c of cols) html += `<td>${c.render(row)}</td>`;
                  html += "</tr>";
                }
                html += "</tbody></table>";
                el.innerHTML = html;
              }

              async function runIngest() {
                try {
                  setStatus("Running ingest...", "warn");
                  const r = await jpost("/api/ingest/run", {});
                  setStatus(`Ingest complete: ${JSON.stringify(r.counts)}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Ingest error: ${e}`, "err");
                }
              }

              async function rebuildIndex() {
                try {
                  setStatus("Rebuilding doc index...", "warn");
                  const r = await jpost("/api/doc_index/rebuild", {});
                  setStatus(`Index rebuilt: chunks=${r.chunks_indexed} backend=${r.index_backend}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Index error: ${e}`, "err");
                }
              }

              async function runPilot() {
                try {
                  setStatus("Running full pilot...", "warn");
                  const r = await jpost("/api/pilot/run", {});
                  setStatus("Pilot complete: " + JSON.stringify(r).slice(0, 120) + "...", "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Pilot error: ${e}`, "err");
                }
              }

              async function decideApproval(id, decision) {
                const notes = prompt(`${decision.toUpperCase()} approval ${id}\\nOptional notes:`) || "";
                try {
                  setStatus("Submitting decision...", "warn");
                  await jpost(`/api/approvals/${id}/decide`, {decision: decision, decision_by: "human", notes: notes});
                  setStatus("Decision saved.", "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Decision error: ${e}`, "err");
                }
              }

              async function updateTaskStatus(id, status) {
                try {
                  setStatus("Updating task...", "warn");
                  await jpost(`/api/tasks/${id}/status`, {status: status});
                  setStatus("Task updated.", "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Task error: ${e}`, "err");
                }
              }

              async function setAutonomy(workflow) {
                const modeSel = document.getElementById(`mode_${workflow}`);
                const scopeSel = document.getElementById(`scope_${workflow}`);
                try {
                  setStatus("Updating autonomy...", "warn");
                  await jput(`/api/autonomy/${encodeURIComponent(workflow)}`, {mode: modeSel.value, scope: scopeSel.value});
                  setStatus("Autonomy updated.", "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Autonomy error: ${e}`, "err");
                }
              }

              async function reloadAll() {
                setStatus("Loading...", "muted");
                try {
                  const [approvals, tasks, autonomy, auditEvents] = await Promise.all([
                    jget("/api/approvals?status=pending&limit=200"),
                    jget("/api/tasks?status=open&limit=200"),
                    jget("/api/autonomy"),
                    jget("/api/audit?limit=200"),
                  ]);

                  renderTable("approvals", approvals, [
                    {label: "Workflow", render: r => `<b>${r.workflow}</b><div class='muted'>scope=${r.scope} mode=${r.mode_at_request}</div>`},
                    {label: "Intent", render: r => `<div class='muted'>${(r.evidence && r.evidence.intent) ? r.evidence.intent : ""}</div>`},
                    {label: "Actions", render: r => `<div class='actions'>
                      <button onclick='setEvidence(${JSON.stringify(r)})'>view</button>
                      <button onclick="decideApproval('${r.id}','approved')">approve</button>
                      <button onclick="decideApproval('${r.id}','denied')">deny</button>
                    </div>`},
                  ]);

                  renderTable("tasks", tasks, [
                    {label: "Title", render: r => `<div><b>${r.title}</b></div><div class='muted'>${(r.description||"").replaceAll("\\n","<br>")}</div>`},
                    {label: "Kind", render: r => `<span class='mono'>${r.kind}</span>`},
                    {label: "Actions", render: r => `<div class='actions'>
                      <button onclick='setEvidence(${JSON.stringify(r)})'>view</button>
                      <button onclick="updateTaskStatus('${r.id}','in_progress')">in progress</button>
                      <button onclick="updateTaskStatus('${r.id}','done')">done</button>
                    </div>`},
                  ]);

                  renderTable("audit", auditEvents, [
                    {label: "When", render: r => `<span class='mono'>${r.ts || ""}</span>`},
                    {label: "Action", render: r => `<b>${r.action || ""}</b><div class='muted'>actor=${r.actor || ""} scope=${r.scope || "-"}</div>`},
                    {label: "Entity", render: r => `<span class='mono'>${(r.entity_type || "")}${r.entity_id ? ":" + r.entity_id : ""}</span>`},
                    {label: "Actions", render: r => `<div class='actions'><button onclick='setEvidence(${JSON.stringify(r)})'>view</button></div>`},
                  ]);

                  renderTable("autonomy", autonomy, [
                    {label: "Workflow", render: r => `<span class='mono'>${r.workflow}</span>`},
                    {label: "Mode", render: r => `<select id="mode_${r.workflow}">
                      ${["shadow","assist","autopilot"].map(m => `<option value="${m}" ${m===r.mode?"selected":""}>${m}</option>`).join("")}
                    </select>`},
                    {label: "Scope", render: r => `<select id="scope_${r.workflow}">
                      ${["internal","external_low","external_medium","external_high","restricted"].map(s => `<option value="${s}" ${s===r.scope?"selected":""}>${s}</option>`).join("")}
                    </select>`},
                    {label: "Save", render: r => `<button onclick="setAutonomy('${r.workflow}')">save</button>`},
                  ]);

                  setStatus("Loaded.", "ok");
                } catch (e) {
                  setStatus(`Load error: ${e}`, "err");
                }
              }

              reloadAll();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/sales")
    def ui_sales() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>SalesSpokes — Pipeline Queue</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">SalesSpokes</h2>
              <span class="pill">pipeline queue</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/docs">api</a>
            </div>

            <div class="row" style="margin-top:10px;">
              <button onclick="runIngest()">Run ingest</button>
              <button onclick="runInboundScan()">Scan inbound ITBs</button>
              <button onclick="runFolderScan()">Scan bidding folders</button>
              <button onclick="refreshPipeline()">Refresh pipeline tasks</button>
              <button onclick="syncTrinity()">Sync Trinity leads</button>
              <button onclick="sendReadyOutbound()">Send ready outbound</button>
              <button onclick="reloadAll()">Reload</button>
              <span id="status" class="muted"></span>
            </div>

            <div class="grid">
              <div class="card">
                <div class="row"><b>Open tasks</b> <span class="muted">(kind=sales)</span></div>
                <div id="tasks"></div>
              </div>

              <div class="card">
                <div class="row"><b>Opportunities</b></div>
                <div id="opps"></div>
              </div>

              <div class="card">
                <div class="row"><b>Leads</b></div>
                <div id="leads"></div>
              </div>

              <div class="card">
                <div class="row"><b>Pending approvals</b> <span class="muted">(all workflows)</span></div>
                <div id="approvals"></div>
              </div>

              <div class="card">
                <div class="row"><b>Outbound drafts</b> <span class="muted">(sales_outbound_email)</span></div>
                <div id="outbound"></div>
              </div>

              <div class="card">
                <div class="row"><b>Preview</b> <span class="muted">(click “view”)</span></div>
                <pre id="preview">(select an outbound message)</pre>
              </div>
            </div>

            <script>
              const elStatus = () => document.getElementById("status");
              const setStatus = (msg, cls="muted") => { const el = elStatus(); el.className = cls; el.textContent = msg; };
              const setPreview = (txt) => { document.getElementById("preview").textContent = txt || ""; };
              window._outbound = [];

              async function jget(url) {
                const r = await fetch(url);
                if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
                return await r.json();
              }
              async function jpost(url, body=null) {
                const r = await fetch(url, {
                  method: "POST",
                  headers: {"Content-Type": "application/json"},
                  body: body ? JSON.stringify(body) : null
                });
                if (!r.ok) throw new Error(`${r.status} ${r.statusText} :: ${(await r.text()).slice(0,200)}`);
                return await r.json();
              }

              function renderTable(targetId, rows, cols) {
                const el = document.getElementById(targetId);
                if (!rows || rows.length === 0) { el.innerHTML = "<div class='muted'>None</div>"; return; }
                let html = "<table><thead><tr>";
                for (const c of cols) html += `<th>${c.label}</th>`;
                html += "</tr></thead><tbody>";
                for (const row of rows) {
                  html += "<tr>";
                  for (const c of cols) html += `<td>${c.render(row)}</td>`;
                  html += "</tr>";
                }
                html += "</tbody></table>";
                el.innerHTML = html;
              }

              async function runIngest() {
                try {
                  setStatus("Running ingest...", "warn");
                  const r = await jpost("/api/ingest/run", {});
                  setStatus(`Ingest complete: ${JSON.stringify(r.counts)}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Ingest error: ${e}`, "err");
                }
              }

              async function runInboundScan() {
                try {
                  setStatus("Scanning inbound ITBs...", "warn");
                  const r = await jpost("/api/sales/inbound/scan", {});
                  setStatus(`Inbound scan: ${JSON.stringify(r.counts)}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Scan error: ${e}`, "err");
                }
              }

              async function runFolderScan() {
                try {
                  setStatus("Scanning bidding folders...", "warn");
                  const r = await jpost("/api/sales/inbound/scan_folders", {});
                  setStatus(`Folder scan: ${JSON.stringify(r.counts)}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Folder scan error: ${e}`, "err");
                }
              }

              async function refreshPipeline() {
                try {
                  setStatus("Refreshing pipeline tasks...", "warn");
                  const r = await jpost("/api/sales/pipeline/refresh", {});
                  setStatus(`Pipeline refresh: tasks_created=${r.tasks_created}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Refresh error: ${e}`, "err");
                }
              }

              async function syncTrinity() {
                try {
                  setStatus("Syncing Trinity leads...", "warn");
                  const r = await jpost("/api/sales/trinity/sync", {});
                  if (r.ok) {
                    setStatus(`Trinity sync: created=${r.created} updated=${r.updated}`, "ok");
                  } else {
                    setStatus(`Trinity sync: ${r.error || "failed"}`, "err");
                  }
                  await reloadAll();
                } catch (e) {
                  setStatus(`Sync error: ${e}`, "err");
                }
              }

              function viewOutbound(messageId) {
                const msg = (window._outbound || []).find(m => m.id === messageId);
                if (!msg) { setPreview("(not found)"); return; }
                const lines = [
                  `To: ${msg.to_email || ""}`,
                  `Subject: ${msg.subject || ""}`,
                  `Status: ${msg.status || ""}`,
                  `Approval: ${msg.approval_id || ""}`,
                  "",
                  (msg.body || "")
                ];
                setPreview(lines.join("\\n"));
              }

              async function sendOutbound(messageId) {
                try {
                  setStatus("Sending outbound email...", "warn");
                  const r = await jpost(`/api/sales/outbound/${messageId}/send?actor=human`, {});
                  if (r.ok) {
                    setStatus(`Sent: provider=${r.provider || "-"} id=${r.provider_message_id || "-"}`, "ok");
                  } else {
                    setStatus(`Send failed: ${r.error || "unknown"}`, "err");
                  }
                  await reloadAll();
                } catch (e) {
                  setStatus(`Send error: ${e}`, "err");
                }
              }

              async function sendReadyOutbound() {
                try {
                  setStatus("Sending ready outbound...", "warn");
                  const r = await jpost(`/api/sales/outbound/send_ready?limit=50&actor=human`, {});
                  setStatus(`Send ready: attempted=${r.attempted} sent=${(r.sent||[]).length} skipped=${r.skipped}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Send ready error: ${e}`, "err");
                }
              }

              async function draftEmail(leadId, oppId) {
                try {
                  setStatus("Drafting email (governed)...", "warn");
                  const r = await jpost("/api/sales/outbound/draft", {lead_id: leadId, opportunity_id: oppId, requested_by: "human"});
                  setStatus(`Draft created: status=${r.status} approval=${r.approval.id}`, "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Draft error: ${e}`, "err");
                }
              }

              async function suppressLead(leadId, suppressed) {
                try {
                  setStatus("Updating suppression...", "warn");
                  await jpost(`/api/sales/leads/${leadId}/suppress`, {suppressed: suppressed, actor: "human"});
                  setStatus("Updated.", "ok");
                  await reloadAll();
                } catch (e) {
                  setStatus(`Suppression error: ${e}`, "err");
                }
              }

              async function reloadAll() {
                setStatus("Loading...", "muted");
                try {
                  const [tasks, opps, leads, approvals, outbound] = await Promise.all([
                    jget("/api/tasks?status=open&limit=200").then(xs => xs.filter(t => t.kind === "sales")),
                    jget("/api/sales/opportunities?limit=200"),
                    jget("/api/sales/leads?limit=200"),
                    jget("/api/approvals?status=pending&limit=200"),
                    jget("/api/sales/outbound?limit=200"),
                  ]);
                  window._outbound = outbound || [];

                  renderTable("tasks", tasks, [
                    {label: "Title", render: r => `<div><b>${r.title}</b></div><div class='muted'>${(r.description||"").replaceAll("\\n","<br>")}</div>`},
                    {label: "Priority", render: r => `<span class="mono">${r.priority}</span>`},
                    {label: "Updated", render: r => `<span class="mono">${r.updated_at}</span>`},
                  ]);

                  renderTable("opps", opps, [
                    {label: "Project", render: r => `<div><b>${r.project_name}</b></div><div class='muted'>stage=${r.stage} due=${r.bid_due_date||"-"}</div>`},
                    {label: "Lead", render: r => `<span class="mono">${r.lead_id}</span>`},
                    {label: "Actions", render: r => `<div class="actions"><button onclick="draftEmail('${r.lead_id}','${r.id}')">Draft email</button></div>`},
                  ]);

                  renderTable("leads", leads, [
                    {label: "Company", render: r => `<div><b>${r.company||""}</b></div><div class='muted'>${r.name||""}</div>`},
                    {label: "Email", render: r => `<span class="mono">${r.email||""}</span>`},
                    {label: "Status", render: r => `<span class="mono">${r.status}</span> ${r.suppressed ? "<span class='pill' style='background:#fee2e2;color:#991b1b;'>suppressed</span>" : ""}`},
                    {label: "Actions", render: r => r.suppressed
                      ? `<button onclick="suppressLead('${r.id}', false)">Unsuppress</button>`
                      : `<button onclick="suppressLead('${r.id}', true)">Suppress</button>`},
                  ]);

                  renderTable("approvals", approvals, [
                    {label: "Workflow", render: r => `<b>${r.workflow}</b><div class='muted'>scope=${r.scope} mode=${r.mode_at_request}</div>`},
                    {label: "Requested", render: r => `<span class="mono">${r.requested_at}</span>`},
                    {label: "Intent", render: r => `<div class='muted'>${(r.evidence && r.evidence.intent) ? r.evidence.intent : ""}</div>`},
                  ]);

                  renderTable("outbound", outbound, [
                    {label: "To", render: r => `<span class="mono">${r.to_email}</span>`},
                    {label: "Subject", render: r => `<b>${r.subject}</b><div class='muted'>status=${r.status} approval=${r.approval_id||"-"}</div>`},
                    {label: "Created", render: r => `<span class="mono">${r.created_at}</span>`},
                    {label: "Actions", render: r => `<div class="actions">
                      <button onclick="viewOutbound('${r.id}')">view</button>
                      <button onclick="sendOutbound('${r.id}')">send</button>
                    </div>`},
                  ]);

                  setStatus("Loaded.", "ok");
                } catch (e) {
                  setStatus(`Load error: ${e}`, "err");
                }
              }

              reloadAll();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/finance")
    def ui_finance() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>FinanceSpokes</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">FinanceSpokes</h2>
              <span class="pill">AP / AR / cashflow</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/docs">api</a>
            </div>

            <div class="row" style="margin-top:10px;">
              <button onclick="runAPIntake()">Run AP intake</button>
              <button onclick="runARReminders()">Run AR reminders</button>
              <button onclick="importLatestWaterfall()">Import latest waterfall</button>
              <button onclick="runCashflowForecast()">Cashflow forecast</button>
              <button onclick="connectProcore()">Connect Procore</button>
              <button onclick="syncProcoreProjects()">Sync Procore projects</button>
              <button onclick="exportInvoices()">Export invoices</button>
              <button onclick="exportCashflow()">Export cashflow</button>
              <button onclick="reloadAll()">Reload</button>
              <span id="status" class="muted"></span>
            </div>

            <div class="grid">
              <div class="card">
                <div class="row"><b>Open tasks</b> <span class="muted">(finance)</span></div>
                <div id="tasks"></div>
              </div>

              <div class="card">
                <div class="row"><b>AR reminder drafts</b></div>
                <div id="arReminders"></div>
              </div>

              <div class="card">
                <div class="row"><b>Invoices</b> <span class="muted">(AP)</span></div>
                <div id="invoices"></div>
              </div>

              <div class="card">
                <div class="row"><b>Cashflow forecast</b></div>
                <pre id="forecast" style="font-size:11px;max-height:200px;overflow:auto;">(run forecast)</pre>
              </div>
            </div>

            <script>
              const elStatus = () => document.getElementById("status");
              const setStatus = (msg, cls="muted") => { const el = elStatus(); el.className = cls; el.textContent = msg; };

              async function jget(url) {
                const r = await fetch(url);
                if (!r.ok) throw new Error(r.status + " " + r.statusText);
                return await r.json();
              }
              async function jpost(url, body=null) {
                const r = await fetch(url, { method: "POST", headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : null });
                if (!r.ok) throw new Error(r.status + " " + r.statusText);
                return await r.json();
              }

              function renderTable(targetId, rows, cols) {
                const el = document.getElementById(targetId);
                if (!rows || rows.length === 0) { el.innerHTML = "<div class='muted'>None</div>"; return; }
                let html = "<table><thead><tr>";
                for (const c of cols) html += "<th>" + c.label + "</th>";
                html += "</tr></thead><tbody>";
                for (const row of rows) {
                  html += "<tr>";
                  for (const c of cols) html += "<td>" + c.render(row) + "</td>";
                  html += "</tr>";
                }
                html += "</tbody></table>";
                el.innerHTML = html;
              }

              async function runAPIntake() {
                try {
                  setStatus("Running AP intake...", "warn");
                  const r = await jpost("/api/finance/ap_intake/run", {});
                  setStatus("AP intake: " + JSON.stringify(r), "ok");
                  await reloadAll();
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function runARReminders() {
                try {
                  setStatus("Running AR reminders...", "warn");
                  const r = await jpost("/api/finance/ar_reminders/run", {});
                  setStatus("AR reminders: drafted=" + (r.drafted ? r.drafted.length : 0), "ok");
                  await reloadAll();
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function importLatestWaterfall() {
                try {
                  setStatus("Importing latest waterfall...", "warn");
                  const r = await jpost("/api/finance/cashflow/import_latest", {});
                  if (r.ok) {
                    setStatus("Imported " + (r.inserted || 0) + " lines from " + (r.artifact_path || "(unknown)"), "ok");
                  } else {
                    setStatus(r.error || "No waterfall found", "err");
                  }
                  await reloadAll();
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function runCashflowForecast() {
                try {
                  setStatus("Running forecast...", "warn");
                  const r = await jpost("/api/finance/cashflow/forecast", { weeks: 8 });
                  document.getElementById("forecast").textContent = JSON.stringify(r, null, 2);
                  setStatus("Forecast loaded.", "ok");
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function connectProcore() {
                try {
                  setStatus("Getting Procore auth URL...", "warn");
                  const r = await jget("/api/integrations/procore/oauth/authorize_url");
                  if (r.authorize_url) {
                    window.location.href = r.authorize_url;
                  } else {
                    setStatus("Procore not configured (set PROCORE_CLIENT_ID, etc.)", "err");
                  }
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function syncProcoreProjects() {
                try {
                  setStatus("Syncing Procore projects...", "warn");
                  const r = await jpost("/api/integrations/procore/sync/projects", {});
                  setStatus("Procore sync: created=" + r.created + " updated=" + r.updated, "ok");
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function exportInvoices() {
                try {
                  setStatus("Exporting invoices...", "warn");
                  const r = await jpost("/api/integrations/accounting/export/invoices", {});
                  setStatus("Exported " + r.rows + " rows to " + r.path, "ok");
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function exportCashflow() {
                try {
                  setStatus("Exporting cashflow...", "warn");
                  const r = await jpost("/api/integrations/accounting/export/cashflow_lines", {});
                  setStatus("Exported " + r.rows + " rows to " + r.path, "ok");
                } catch (e) { setStatus("Error: " + e, "err"); }
              }

              async function reloadAll() {
                setStatus("Loading...", "muted");
                try {
                  const [tasks, arReminders, invoices] = await Promise.all([
                    jget("/api/tasks?status=open&limit=200").then(xs => xs.filter(t => t.kind && t.kind.startsWith("finance"))),
                    jget("/api/finance/ar_reminders?limit=200"),
                    jget("/api/finance/invoices?kind=AP&limit=100"),
                  ]);
                  renderTable("tasks", tasks, [
                    {label: "Title", render: r => "<div><b>" + r.title + "</b></div><div class='muted'>" + (r.description||"").replace(/\\n/g,"<br>") + "</div>"},
                    {label: "Kind", render: r => "<span class='mono'>" + r.kind + "</span>"},
                  ]);
                  renderTable("arReminders", arReminders, [
                    {label: "To", render: r => "<span class='mono'>" + r.to_email + "</span>"},
                    {label: "Subject", render: r => "<b>" + r.subject + "</b><div class='muted'>status=" + r.status + "</div>"},
                  ]);
                  renderTable("invoices", invoices, [
                    {label: "Invoice", render: r => "<span class='mono'>" + (r.invoice_number||"-") + "</span>"},
                    {label: "Amount", render: r => "$" + ((r.amount_cents||0)/100).toFixed(2)},
                    {label: "Status", render: r => r.status},
                  ]);
                  setStatus("Loaded.", "ok");
                } catch (e) { setStatus("Load error: " + e, "err"); }
              }

              reloadAll();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/grokstmate")
    def ui_grokstmate() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>GROKSTMATE — Autonomous Construction Agents</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">GROKSTMATE</h2>
              <span class="pill">Autonomous Construction Agents</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/ui/ops">ops</a>
              <a class="muted" href="/ui/sales">sales</a>
              <a class="muted" href="/ui/finance">finance</a>
            </div>
            <div class="card">
              <div><b>Status</b> <span id="grokStatus" class="muted">Loading...</span></div>
            </div>
            <div class="card">
              <div><b>Cost Estimate</b></div>
              <div style="margin-top:8px;">
                <input id="estName" placeholder="Project name" value="Office Building" />
                <select id="estType"><option value="residential">Residential</option><option value="commercial" selected>Commercial</option><option value="industrial">Industrial</option></select>
                <input id="estSize" type="number" placeholder="Size sq ft" value="5000" />
                <select id="estComplexity"><option value="simple">Simple</option><option value="moderate" selected>Moderate</option><option value="complex">Complex</option></select>
                <button onclick="runEstimate()">Get Estimate</button>
              </div>
              <pre id="estimateResult" style="margin-top:10px;min-height:60px;">—</pre>
            </div>
            <div class="card">
              <div><b>Create Project Plan</b></div>
              <div style="margin-top:8px;">
                <input id="projId" placeholder="Project ID" value="proj_001" />
                <input id="projName" placeholder="Project name" value="New Construction" />
                <button onclick="runCreateProject()">Create Plan</button>
              </div>
              <pre id="projectResult" style="margin-top:10px;min-height:60px;">—</pre>
            </div>
            <script>
              async function jget(u) { const r = await fetch(u); return r.ok ? r.json() : null; }
              async function jpost(u, b) { const r = await fetch(u, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(b||{}) }); return r.ok ? r.json() : null; }
              async function loadStatus() {
                const r = await jget('/api/grokstmate/status');
                document.getElementById('grokStatus').textContent = r && r.available ? 'Available' : 'Not installed (pip install -e GROKSTMATE)';
              }
              async function runEstimate() {
                const result = document.getElementById('estimateResult');
                result.textContent = 'Running...';
                try {
                  const r = await jpost('/api/grokstmate/estimate', {
                    name: document.getElementById('estName').value,
                    type: document.getElementById('estType').value,
                    size: parseInt(document.getElementById('estSize').value) || 5000,
                    complexity: document.getElementById('estComplexity').value,
                  });
                  result.textContent = JSON.stringify(r, null, 2);
                } catch (e) { result.textContent = 'Error: ' + e; }
              }
              async function runCreateProject() {
                const result = document.getElementById('projectResult');
                result.textContent = 'Running...';
                try {
                  const r = await jpost('/api/grokstmate/project', {
                    project_id: document.getElementById('projId').value,
                    project_name: document.getElementById('projName').value,
                    project_spec: { type: 'commercial', size: 5000, complexity: 'moderate' },
                  });
                  result.textContent = JSON.stringify(r, null, 2);
                } catch (e) { result.textContent = 'Error: ' + e; }
              }
              loadStatus();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/fleet")
    def ui_fleet() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Superagents Fleet — Construction & Development</title>
            <style>
""" + THEME_CSS + """
              .agent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
              .agent-cell .phase { font-size: 11px; color: #9eb5a8; }
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">Superagents Fleet</h2>
              <span class="pill">Construction & Development</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/ui/grokstmate">grokstmate</a>
              <a class="muted" href="/ui/ops">ops</a>
            </div>
            <div class="card">
              <div><b>Status</b> <span id="fleetStatus" class="muted">Loading...</span> <span class="pill" id="archBadge">plugin</span></div>
              <div id="fleetStats" class="muted" style="margin-top:6px;"></div>
              <div style="margin-top:8px;"><a href="/docs#/Superagents%20Fleet" class="muted">API docs</a></div>
            </div>
            <div class="card">
              <div><b>Agents by Phase</b></div>
              <div style="margin-top:8px;">
                <select id="phaseFilter" onchange="loadAgents()">
                  <option value="">All phases</option>
                  <option value="land">Land</option>
                  <option value="bid">Bid</option>
                  <option value="ops">Operations</option>
                  <option value="finance">Finance</option>
                  <option value="marketing">Marketing</option>
                  <option value="governance">Governance</option>
                  <option value="roadmap">Roadmap</option>
                </select>
              </div>
              <div id="agentGrid" class="agent-grid" style="margin-top:12px;"></div>
            </div>
            <div class="card">
              <div><b>Dispatch Task</b></div>
              <div style="margin-top:8px;">
                <select id="dispatchAgent">
                  <option value="land_feasibility">Land & Feasibility</option>
                  <option value="bid_scraping">Bid Scraping</option>
                  <option value="financial_analyst">Financial Analyst</option>
                  <option value="bookkeeper">Bookkeeper</option>
                  <option value="file_keeper">File Keeper</option>
                  <option value="project_manager">Project Manager</option>
                  <option value="logistics_fleet">Logistics & Fleet</option>
                  <option value="social_marketing">Social Marketing</option>
                  <option value="internal_audit">Internal Audit</option>
                </select>
                <select id="dispatchType">
                  <option value="due_diligence">Due Diligence</option>
                  <option value="feasibility_study">Feasibility Study</option>
                  <option value="invoice_in">Invoice In</option>
                  <option value="daily_post">Daily Post</option>
                  <option value="generic">Generic</option>
                </select>
                <button onclick="runDispatch()">Dispatch</button>
              </div>
              <pre id="dispatchResult" style="margin-top:10px;min-height:60px;">—</pre>
            </div>
            <script>
              async function jget(u) { const r = await fetch(u); return r.ok ? r.json() : null; }
              async function jpost(u, b) { const r = await fetch(u, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(b||{}) }); return r.ok ? r.json() : null; }
              async function loadStatus() {
                const r = await jget('/api/fleet/status');
                const el = document.getElementById('fleetStatus');
                const stats = document.getElementById('fleetStats');
                if (!r || !r.available) {
                  el.textContent = 'Not available';
                  return;
                }
                el.textContent = 'Available';
                stats.textContent = (r.plugins_loaded || r.agents_loaded) + ' plugins, ' + r.tasks_dispatched + ' tasks. Data: ' + (r.data_dir || 'local');
              }
              async function loadAgents() {
                const phase = document.getElementById('phaseFilter').value;
                const r = await jget('/api/fleet/agents' + (phase ? '?phase=' + phase : ''));
                const grid = document.getElementById('agentGrid');
                if (!Array.isArray(r)) { grid.innerHTML = '<span class="muted">No agents</span>'; return; }
                grid.innerHTML = r.map(a => '<div class="agent-cell"><b>' + a.name + '</b><div class="phase">' + a.phase + (a.has_api ? ' • <a href="/api/fleet/agents/' + a.agent_id + '/health" target="_blank">API</a>' : '') + '</div></div>').join('');
              }
              async function runDispatch() {
                const result = document.getElementById('dispatchResult');
                result.textContent = 'Running...';
                try {
                  const r = await jpost('/api/fleet/dispatch', {
                    agent_id: document.getElementById('dispatchAgent').value,
                    task: {
                      task_id: 'ui_' + Date.now(),
                      type: document.getElementById('dispatchType').value,
                      description: 'Test from UI',
                    },
                  });
                  result.textContent = JSON.stringify(r, null, 2);
                  loadStatus();
                } catch (e) { result.textContent = 'Error: ' + e; }
              }
              loadStatus();
              loadAgents();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/bidzone")
    def ui_bidzone() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
            <title>BID-ZONE — Sales Portal</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <h2>BID-ZONE</h2>
            <span class="pill">Sales Portal — Bridge to build</span>
            <a href="/ui" style="margin-left:12px;">home</a>
            <div class="card">
              <b>Status</b> — BID-ZONE exists at d-XAI-BID-ZONE. API bridge not yet built.
            </div>
            <div class="card">
              <b>Next step</b> — Inspect <code>d-XAI-BID-ZONE/src/interfaces/franklin_os.py</code> for integration points.
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/project_controls")
    def ui_project_controls() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
            <title>Project Controls</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <h2>Project Controls</h2>
            <a href="/ui">home</a>
            <div class="card">
              <b>Ingested artifacts</b> <span class="muted">(from c-00-Project-Controls-*)</span>
              <div id="artifacts" style="margin-top:8px;">Loading...</div>
            </div>
            <script>
              fetch('/api/project_controls/artifacts?limit=50').then(r=>r.json()).then(d=>{
                const el=document.getElementById('artifacts');
                if(!d.length){el.innerHTML='<span class="muted">No artifacts yet. Run ingest.</span>';return;}
                el.innerHTML='<table><tr><th>Source</th><th>Path</th><th>Status</th></tr>'+
                  d.map(a=>'<tr><td>'+a.source+'</td><td>'+a.path+'</td><td>'+a.status+'</td></tr>').join('')+'</table>';
              }).catch(()=>document.getElementById('artifacts').textContent='Error loading');
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    @app.get("/ui/rollout")
    def ui_rollout() -> HTMLResponse:
        html = """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Rollout Pilot</title>
            <style>
""" + THEME_CSS + """
            </style>
          </head>
          <body>
            <div class="row">
              <h2 style="margin:0;">Rollout Pilot</h2>
              <span class="pill">shadow / assist / autopilot</span>
              <a class="muted" href="/ui">home</a>
              <a class="muted" href="/ui/ops">ops</a>
            </div>

            <div class="row" style="margin-top:10px;">
              <button onclick="runPilot()">Run full pilot</button>
              <span id="pilotStatus" class="muted"></span>
            </div>

            <div class="card">
              <div><b>KPI summary</b> <span class="muted">(last 7 days)</span></div>
              <pre id="metrics">Loading...</pre>
            </div>

            <div class="card">
              <div><b>Tire recommendations</b> <span class="muted">(prioritize automation)</span></div>
              <pre id="tire">Loading...</pre>
            </div>

            <div class="card">
              <div><b>Autonomy settings</b> <span class="muted">(per workflow)</span></div>
              <div id="autonomy"></div>
              <div class="muted" style="margin-top:8px;">Change modes in <a href="/ui/ops">Ops dashboard</a>.</div>
            </div>

            <script>
              async function jget(url) {
                const r = await fetch(url);
                if (!r.ok) throw new Error(r.status + " " + r.statusText);
                return await r.json();
              }
              async function jpost(url, body) {
                const r = await fetch(url, { method: "POST", headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : "{}" });
                if (!r.ok) throw new Error(r.status + " " + r.statusText);
                return await r.json();
              }

              async function runPilot() {
                const el = document.getElementById("pilotStatus");
                el.textContent = "Running pilot...";
                el.className = "muted";
                try {
                  const r = await jpost("/api/pilot/run", {});
                  el.textContent = "Pilot complete: " + Object.keys(r).length + " steps";
                  el.className = "ok";
                  load();
                } catch (e) {
                  el.textContent = "Error: " + e;
                  el.className = "err";
                }
              }

              async function load() {
                try {
                  const [metrics, tire, autonomy] = await Promise.all([
                    jget("/api/metrics/summary?days=7"),
                    jget("/api/tire/recommendations?days=30"),
                    jget("/api/autonomy"),
                  ]);
                  document.getElementById("metrics").textContent = JSON.stringify(metrics, null, 2);
                  document.getElementById("tire").textContent = JSON.stringify(tire, null, 2);
                  let html = "<div style='margin-top:8px;'>";
                  for (const a of autonomy) {
                    html += "<div><span class='mono'>" + a.workflow + "</span> &rarr; <b>" + a.mode + "</b> (" + a.scope + ")</div>";
                  }
                  html += "</div>";
                  document.getElementById("autonomy").innerHTML = html || "<div class='muted'>None</div>";
                } catch (e) {
                  document.getElementById("metrics").textContent = "Error: " + e;
                }
              }
              load();
            </script>
          </body>
        </html>
        """
        return HTMLResponse(content=html, headers=UI_NO_CACHE)

    return app


app = create_app()

