# Superagents Fleet — Plugin Architecture

Each agent is a **plugin** with its own **API** and **database**. Private data stays local.

## Security & Reliability

- **PrivacyFilter**: Recursive sanitization; `sanitize()` for external, `sanitize_for_learning()` for local DB
- **route_document**: Only `DOC_ROUTE_SAFE_KEYS` passed to agents; PII never forwarded
- **agent_id validation**: `^[a-z][a-z0-9_]*$`; rejects path traversal
- **External plugins**: Path validated against `FRANKLINOPS_FLEET_PLUGINS_DIR`; no arbitrary load
- **Thread safety**: `PluginRegistry` uses `RLock` for concurrent load/get
- **Error handling**: Hub wraps `execute_task` in try/except; audit on success and failure

## Structure

```
src/superagents_fleet/
├── plugin/
│   ├── interface.py    # AgentPlugin ABC: get_router(), get_schema_sql(), execute_task(), learn()
│   ├── registry.py    # PluginRegistry, BUILTIN_PLUGINS
│   └── privacy.py     # PrivacyFilter — redact before external calls
├── plugins/
│   ├── land_feasibility/   # Full example: API, DB, learning
│   ├── bid_scraping/
│   ├── financial_analyst/
│   ├── bookkeeper/
│   ├── file_keeper/
│   ├── project_manager/
│   ├── logistics_fleet/
│   ├── social_marketing/
│   └── internal_audit/
└── hub.py             # FleetHub — orchestrates, mounts plugin routers
```

## Per-Agent Database

Each plugin gets its own SQLite file:

```
data/franklinops/fleet/agents/
├── land_feasibility.db
├── bid_scraping.db
├── bookkeeper.db
└── ...
```

## Per-Agent API

Each plugin exposes a FastAPI router. Mounted at:

```
GET  /api/fleet/agents/{agent_id}/health
GET  /api/fleet/agents/{agent_id}/tasks      (if implemented)
POST /api/fleet/agents/{agent_id}/due_diligence  (land_feasibility)
...
```

## Privacy

- **PrivacyFilter**: Redacts private fields before any external/LLM call
- **get_private_fields()**: Agent-specific PII keys (owner_email, SSN, etc.)
- **Learning**: Stored only in local agent DB; never sent out

## Adding a New Plugin

1. Create `plugins/my_agent/plugin.py` with `Plugin(AgentPlugin)` class
2. Implement: `get_router()`, `get_schema_sql()`, `execute_task()`
3. Optionally: `learn()`, `get_private_fields()`
4. Add to `BUILTIN_PLUGINS` in `plugin/registry.py`

## External Plugins

Set `FRANKLINOPS_FLEET_PLUGINS_DIR` to a directory containing custom agent packages:

```
/path/to/plugins/
  my_custom_agent/
    plugin.py    # or __init__.py with Plugin(AgentPlugin) class
```

Each subdirectory with `plugin.py` or `__init__.py` exposing a `Plugin` class is discovered.
Use `PluginRegistry.load_external(Path(...), agent_id)` to load.

## Scaling

- Each agent can run as a **separate process** (future: microservices)
- DB per agent enables independent backup/restore
- Plugin discovery loads from built-in + external paths
