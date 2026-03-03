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
        roots = (body.roots if body and body.roots else None) or {
            "onedrive_projects": s.onedrive_projects_root,
            "onedrive_bidding": s.onedrive_bidding_root,
            "onedrive_attachments": s.onedrive_attachments_root,
        }
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

        roots = (body.roots if body and body.roots else None) or {
            "onedrive_projects": s.onedrive_projects_root,
            "onedrive_bidding": s.onedrive_bidding_root,
            "onedrive_attachments": s.onedrive_attachments_root,
        }
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
              * { margin: 0; padding: 0; box-sizing: border-box; }
              body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; color: #1a202c; line-height: 1.6; }
              
              .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
              .header { background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
              .welcome-message { font-size: 18px; margin-bottom: 16px; color: #2d3748; }
              .suggestions { display: flex; flex-wrap: wrap; gap: 12px; }
              .suggestion { background: #e2e8f0; padding: 8px 16px; border-radius: 20px; font-size: 14px; cursor: pointer; transition: all 0.2s; }
              .suggestion:hover { background: #cbd5e0; transform: translateY(-1px); }
              .suggestion.high { background: #fed7d7; color: #9c1b1b; }
              .suggestion.medium { background: #feebcb; color: #c05621; }
              
              .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }
              .left-panel { display: flex; flex-direction: column; gap: 24px; }
              .right-panel { display: flex; flex-direction: column; gap: 24px; }
              
              .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
              .card-title { font-size: 20px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; }
              .card-title .icon { margin-right: 8px; }
              
              .chat-container { min-height: 400px; }
              .chat-messages { height: 300px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #f7fafc; }
              .chat-input-container { display: flex; gap: 12px; }
              .chat-input { flex: 1; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 16px; }
              .chat-send { padding: 12px 24px; background: #3182ce; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; }
              .chat-send:hover { background: #2c5aa0; }
              
              .message { margin-bottom: 16px; padding: 12px; border-radius: 8px; }
              .message.user { background: #ebf8ff; text-align: right; }
              .message.assistant { background: #f0f9ff; }
              .message .sender { font-weight: 600; margin-bottom: 4px; font-size: 14px; }
              
              .notifications-list { max-height: 400px; overflow-y: auto; }
              .notification { padding: 16px; border-left: 4px solid #cbd5e0; margin-bottom: 12px; background: #f7fafc; border-radius: 0 8px 8px 0; }
              .notification.high { border-left-color: #f56565; }
              .notification.medium { border-left-color: #ed8936; }
              .notification.low { border-left-color: #48bb78; }
              .notification-title { font-weight: 600; margin-bottom: 4px; }
              .notification-message { font-size: 14px; color: #4a5568; margin-bottom: 8px; }
              .notification-actions { display: flex; gap: 8px; }
              .notification-action { padding: 4px 12px; background: #e2e8f0; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
              .notification-action:hover { background: #cbd5e0; }
              
              .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
              .stat { text-align: center; padding: 16px; background: #f7fafc; border-radius: 8px; }
              .stat-number { font-size: 24px; font-weight: 700; color: #2d3748; }
              .stat-label { font-size: 14px; color: #4a5568; margin-top: 4px; }
              
              .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
              .quick-action { padding: 16px; background: #edf2f7; border: none; border-radius: 8px; cursor: pointer; text-align: center; transition: all 0.2s; }
              .quick-action:hover { background: #e2e8f0; transform: translateY(-2px); }
              .quick-action .icon { font-size: 24px; margin-bottom: 8px; }
              .quick-action .text { font-size: 14px; font-weight: 500; }
              
              .loading { text-align: center; padding: 20px; color: #4a5568; }
              .error { color: #e53e3e; background: #fed7d7; padding: 16px; border-radius: 8px; margin: 16px 0; }
              
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
        return HTMLResponse(content=html)

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
            <title>FranklinOpsHub UI</title>
            <style>
              body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color: #111; }
              a { color: #0a58ca; text-decoration: none; }
              a:hover { text-decoration: underline; }
              .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; margin: 12px 0; }
              code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
              .muted { color: #64748b; font-size: 13px; }
            </style>
          </head>
          <body>
            <h2>FranklinOpsHub</h2>
            <div class="card">
              <div><b>Today queue</b> <span class="muted">(calls, invoices, approvals)</span></div>
              <div id="todayQueue" class="muted" style="margin-top:6px;">Loading...</div>
              <div style="margin-top:8px;"><a href="/ui/ops">View full Ops dashboard →</a></div>
            </div>
            <div class="card">
              <div><a href="/ui/ops">Ops dashboard (tasks / approvals / autonomy)</a></div>
              <div><a href="/ui/sales">SalesSpokes pipeline queue</a></div>
              <div><a href="/ui/finance">FinanceSpokes (AP / AR / cashflow)</a></div>
              <div><a href="/ui/rollout">Rollout pilot (shadow / assist / autopilot)</a></div>
              <div style="margin-top:8px;"><a href="/docs">API docs</a></div>
            </div>
            <div class="card">
              <div><b>Quick tips</b></div>
              <div style="margin-top:6px;">Run ingestion: <code>POST /api/ingest/run</code></div>
              <div>Sales inbound scan: <code>POST /api/sales/inbound/scan</code></div>
              <div>Finance AP scan: <code>POST /api/finance/ap_intake/run</code></div>
            </div>
            <script>
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
        return HTMLResponse(content=html)

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
              body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; color: #111; }
              .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
              button { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; background: #fff; cursor: pointer; }
              button:hover { background: #f9fafb; }
              .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #ecfeff; color: #155e75; font-size: 12px; }
              .grid { display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 14px; }
              @media (min-width: 1050px) { .grid { grid-template-columns: 1fr 1fr; } }
              .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
              table { width: 100%; border-collapse: collapse; }
              th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
              th { font-size: 12px; color: #334155; text-transform: uppercase; letter-spacing: .04em; }
              .muted { color: #64748b; font-size: 12px; }
              .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; }
              pre { white-space: pre-wrap; background: #0b1220; color: #e5e7eb; padding: 10px; border-radius: 12px; overflow:auto; }
              .ok { color: #166534; }
              .warn { color: #92400e; }
              .err { color: #991b1b; }
              select { padding: 6px 8px; border-radius: 10px; border: 1px solid #d1d5db; }
              .actions { display: flex; gap: 8px; flex-wrap: wrap; }
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
        return HTMLResponse(content=html)

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
              body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; color: #111; }
              .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
              button { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; background: #fff; cursor: pointer; }
              button:hover { background: #f9fafb; }
              .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; }
              .grid { display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 14px; }
              .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
              table { width: 100%; border-collapse: collapse; }
              th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
              th { font-size: 12px; color: #334155; text-transform: uppercase; letter-spacing: .04em; }
              .muted { color: #64748b; font-size: 12px; }
              .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 12px; }
              .actions { display: flex; gap: 8px; flex-wrap: wrap; }
              .ok { color: #166534; }
              .warn { color: #92400e; }
              .err { color: #991b1b; }
              pre { white-space: pre-wrap; background: #0b1220; color: #e5e7eb; padding: 10px; border-radius: 12px; overflow:auto; font-size: 12px; }
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
        return HTMLResponse(content=html)

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
              body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; color: #111; }
              .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
              button { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; background: #fff; cursor: pointer; }
              button:hover { background: #f9fafb; }
              .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #dcfce7; color: #166534; font-size: 12px; }
              .grid { display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 14px; }
              @media (min-width: 1050px) { .grid { grid-template-columns: 1fr 1fr; } }
              .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
              table { width: 100%; border-collapse: collapse; }
              th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
              th { font-size: 12px; color: #334155; text-transform: uppercase; letter-spacing: .04em; }
              .muted { color: #64748b; font-size: 12px; }
              .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
              .actions { display: flex; gap: 8px; flex-wrap: wrap; }
              .ok { color: #166534; }
              .warn { color: #92400e; }
              .err { color: #991b1b; }
              a { color: #0a58ca; text-decoration: none; }
              a:hover { text-decoration: underline; }
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
        return HTMLResponse(content=html)

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
              body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; color: #111; }
              .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
              .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; margin: 12px 0; }
              .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; }
              .muted { color: #64748b; font-size: 12px; }
              .ok { color: #166534; font-size: 12px; }
              .err { color: #991b1b; font-size: 12px; }
              .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
              pre { background: #0b1220; color: #e5e7eb; padding: 10px; border-radius: 12px; overflow: auto; font-size: 12px; }
              a { color: #0a58ca; text-decoration: none; }
              a:hover { text-decoration: underline; }
              select { padding: 6px 8px; border-radius: 10px; border: 1px solid #d1d5db; }
              button { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 10px; background: #fff; cursor: pointer; }
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
        return HTMLResponse(content=html)

    return app


app = create_app()

