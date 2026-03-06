# Runtime Kernel

**The minimal substrate everything runs on.**

---

## What It Is

The FranklinOps Runtime Kernel is the core of the system. Like an OS kernel:

- **Boot** — Initialize DB, run migrations, create audit, load governance, create flow registry
- **Invoke** — The core syscall: dispatch a flow with full hardening
- **Shutdown** — Close DB, audit final event

Everything else (HTTP server, Sales, Finance, GROKSTMATE, etc.) runs **on top** of the kernel.

---

## Lifecycle

```
boot() → [run] → shutdown()
```

- **boot()** — Idempotent. Safe to call multiple times. Creates: OpsDB, AuditLogger, FlowRegistry, governance provenance.
- **invoke(flow_id, inp)** — Dispatch a flow. Passes through: circuit breaker → rate limit → sanitize → execute → audit.
- **shutdown()** — Audit kernel_shutdown, close DB.

---

## Kernel Services

| Service | Purpose |
|---------|---------|
| `kernel.db` | OpsDB — SQLite, all tables |
| `kernel.audit` | Append-only audit logger |
| `kernel.flows` | FlowRegistry — plug/unplug flows |
| `kernel.governance` | Version + hash of governance-policies.json |
| `kernel.invoke()` | Dispatch flows with hardening |

---

## Usage

```python
from src.core.kernel import create_kernel

kernel = create_kernel()
kernel.boot()

# Plug a flow
kernel.plug(FlowSpec(flow_id="my_flow", ...), handler)

# Invoke
result = kernel.invoke("my_flow", {"input": "data"})

# Shutdown
kernel.shutdown()
```

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/kernel` | Kernel status: booted, governance, flow_count |
| `GET /api/governance/hash` | Governance provenance |
| `GET /api/flows` | List plugged flows |
| `POST /api/flows/plug` | Plug a flow (via kernel) |
| `POST /api/flows/{id}/invoke` | Invoke a flow (via kernel.invoke) |
| `DELETE /api/flows/{id}` | Unplug a flow (via kernel.unplug) |

---

## Design

The kernel is **minimal**. It does not know about:
- HTTP
- Sales, Finance, GROKSTMATE
- Doc ingestion, Procore, etc.

Those are **drivers** and **flows** that plug in. The kernel provides:
- Storage (DB)
- Audit (append-only)
- Flow dispatch (invoke with hardening)
- Governance provenance

**The kernel is the OS. Flows are processes. Invoke is the syscall.**

---

## Standalone Runner

Run the kernel without HTTP:

```bash
# Interactive REPL
python scripts/run_kernel.py

# One-shot invoke (JSON from arg or stdin with -)
python scripts/run_kernel.py echo -
echo '{"x": 42}' | python scripts/run_kernel.py echo -
```
