# Universal Flow Interface — The Main OS

**Any system with IN and OUT can instantly plug in.**

---

## Philosophy

The circle: **Incoming → Outgoing → Collection → Regenerating → Incoming**.

Every flow has:
- **IN**: inputs (JSON, validated, sanitized)
- **OUT**: outputs (JSON, validated)

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/flows` | GET | List all plugged flows |
| `POST /api/flows/plug` | POST | Instant plug: register flow |
| `POST /api/flows/{id}/invoke` | POST | Invoke with input |
| `DELETE /api/flows/{id}` | DELETE | Unplug |

### Plug Request Body

```json
{
  "flow_id": "my_flow",
  "name": "My Flow",
  "direction": "incoming",
  "scope": "internal",
  "handler_type": "passthrough",
  "webhook_url": "https://example.com/hook"
}
```

- `flow_id`: Required. `[a-z][a-z0-9_-]*`, max 64 chars
- `name`: Optional. Display name
- `direction`: `incoming` | `outgoing` | `collection` | `regenerating`
- `scope`: `internal` | `external_low` | `external_medium` | `external_high` | `restricted`
- `handler_type`: `passthrough` (echo) | `webhook` (POST to URL)
- `webhook_url`: Required when `handler_type=webhook`. Must be http/https

### Invoke Request Body

Any JSON object. Passed as input to the flow handler.

```json
{"key": "value", "nested": {"a": 1}}
```

---

## Hardening (Every Invocation)

| Layer | Default | Env Override |
|-------|---------|--------------|
| Input sanitization | On | `FRANKLINOPS_FLOW_SANITIZE` |
| Payload size | 1MB max | `FlowSpec.max_payload_bytes` |
| Rate limit | 120/min | `FRANKLINOPS_FLOW_RATE_LIMIT` |
| Circuit breaker | 5 failures, 60s recovery | `FRANKLINOPS_FLOW_CB_*` |
| Retry | 2 retries | `FRANKLINOPS_FLOW_MAX_RETRIES` |
| Timeout | Per-flow (60s default) | `FlowSpec.timeout_seconds` |
| Audit | Every invocation | `FRANKLINOPS_FLOW_AUDIT` |

---

## Examples

### Python: Register and invoke

```python
from src.core.flow_interface import FlowRegistry, FlowSpec, FlowDirection, flow_handler
from src.core.flow_hardening import execute_flow_hardened

registry = FlowRegistry()
registry.plug(
    FlowSpec(flow_id="echo", name="Echo", direction=FlowDirection.INCOMING),
    flow_handler(lambda inp: {"out": inp}),
)
spec, handler = registry.get("echo")
result = execute_flow_hardened("echo", spec, handler.process, {"x": 1})
```

