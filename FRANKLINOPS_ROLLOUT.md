## FranklinOps Pilot Rollout (Shadow → Assist → Autopilot)

This repo supports a gradual autonomy ramp per workflow, with audit + evidence preserved for every step.

### Modes

- **shadow**: agents draft only (creates tasks/approvals, no auto-approval)
- **assist**: low-risk actions can auto-approve via `AutonomyGate` (still escalates medium/high risk)
- **autopilot**: same as assist, plus **sampled audit tasks** for auto-approved actions

### Where to control it

- **UI**: open `GET /ui/ops` and edit workflow autonomy settings
- **API**: `PUT /api/autonomy/{workflow}` with `{ "mode": "...", "scope": "..." }`

### Evidence + approvals

- **Approvals**: `GET /api/approvals?status=pending`
- **Decisions**: `POST /api/approvals/{id}/decide`
- **Audit log**: `GET /api/audit`

### Autopilot sampled audits

Set:

- `FRANKLINOPS_AUTOPILOT_AUDIT_SAMPLE_RATE=0.10` (10% of auto-approved actions create a human review task)
- `TRINITY_SIGNING_SECRET=...` (required for evidence signature verification; otherwise actions remain pending)

Sample audit tasks appear in `GET /api/tasks?status=open` with kind `audit.sample`.

### KPI / “tire loop”

- **Metrics**: `GET /api/metrics/summary`
- **What to automate next** (based on manual-approval load): `GET /api/tire/recommendations`

