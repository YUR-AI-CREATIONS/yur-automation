# FranklinOps - Universal Business Automation OS

The circle never stops.

## Get Started in 30 Seconds

### Windows
1. Download this repo
2. **Double-click `RUN.bat`**
3. Browser opens automatically
4. Done.

### Docker
```bash
docker-compose up
# Then: http://localhost:8844/ui
```

### Manual (Python 3.11+)
```bash
python -m pip install -r requirements-ultra-minimal.txt
python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844
# Then: http://localhost:8844/ui
```

---

## What is FranklinOps?

A **modern operating system for business automation**. Not a tool. An OS.

- **Incoming:** Documents, leads, data
- **Outgoing:** Actions, reports, decisions  
- **Collection:** Everything stored, indexed, verified
- **Regenerating:** Metrics, learning, continuous improvement

The four phases run in a **continuous circle**. The system improves itself.

Built for construction. Works for any business.

---

## Features

✓ **Local AI** - Ollama + Llama3 (air-gapped, no cloud)  
✓ **Three Control Modes** - Shadow (watch), Assist (approve), Autopilot (run)  
✓ **Real-time Metrics** - Construction, Sales, Finance dashboards  
✓ **Economic Intelligence** - Regional growth, permits, migration signals  
✓ **Fully Audited** - Every action logged and cryptographically verified  
✓ **No Dependencies** - Runs on Windows, Mac, Linux with Docker  

---

## Modules (Spokes)

- **Construction** - Projects, pay apps, inspections, warranty
- **Sales** - Pipeline, opportunities, forecasting  
- **Finance** - AP/AR, cash flow, reporting
- **Custom** - Add your own spoke

---

## Control Modes

### Shadow
Watch what the system does. Observe only. No changes.

### Assist (Recommended)
System suggests actions. You approve. Human + AI together.

### Autopilot
System runs automatically. You audit. Fully logged.

---

## How to Get It Running

See [QUICKSTART.md](QUICKSTART.md) for detailed setup options.

**TL;DR:**
- Windows: `RUN.bat`
- Docker: `docker-compose up`
- Manual: `python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844`

---

## Architecture (Technical Details)

- **Hub-Spoke:** Core runtime kernel + industry-specific modules
- **Runtime Kernel:** Manages DB, audit, governance, flow registry
- **Event Bus:** In-memory or NATS for event-driven orchestration
- **Flows:** Universal plugin mechanism (can add any automation)
- **Collection Spine:** Immutable audit trail, governance enforcement
- **Deterministic Builder:** Headless builder for reproducible outputs

See [docs/](docs/) for full technical documentation.

---

## Data & Privacy

- **Fully Local** - Nothing leaves your system
- **Air-Gapped** - No external API calls
- **SQLite** - Database lives in `/data/franklinops/`
- **Audit Trail** - Every action logged with timestamps + hashes
- **Your Control** - You choose: Shadow, Assist, or Autopilot

---

## Troubleshooting

**Port 8844 in use?**
```bash
# Windows
netstat -ano | findstr :8844
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :8844
kill -9 <PID>
```

**Python not found?**
- Download: https://www.python.org/downloads/
- During install: **CHECK "Add Python to PATH"**
- Restart terminal

**Dependencies fail?**
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-ultra-minimal.txt --no-cache-dir
```

**Still broken?**
Use Docker instead - it just works:
```bash
docker-compose up
```

---

## What's Next?

- [ ] Connect your data sources
- [ ] Choose your control mode (start with Assist)
- [ ] Load your first module (Construction/Sales/Finance)
- [ ] Watch it work
- [ ] Dive into the docs

---

## Support

- **Documentation:** See [docs/](docs/) folder
- **Troubleshooting:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Quick Start:** See [QUICKSTART.md](QUICKSTART.md)

---

**Built by:** YUR AI Creations  
**License:** See LICENSE file  
**Version:** 1.0.0
