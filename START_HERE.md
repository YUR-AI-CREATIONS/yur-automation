# START HERE - FranklinOps Installation

## The Fastest Way to Get Running

### For Windows Users (30 seconds)
1. Download: https://github.com/YUR-AI-CREATIONS/pipeline-/archive/refs/heads/main.zip
2. Extract anywhere
3. **Double-click `RUN.bat`**
4. Browser opens automatically
5. Done.

### For Docker Users (Works Everywhere)
```bash
docker-compose up
# Open: http://localhost:8844/ui
```

### For Developers
```bash
python -m pip install -r requirements-ultra-minimal.txt
python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844
# Open: http://localhost:8844/ui
```

---

## Full Documentation

- **[DOWNLOAD_GUIDE.md](DOWNLOAD_GUIDE.md)** - Step-by-step for non-technical users
- **[QUICKSTART.md](QUICKSTART.md)** - Setup options with troubleshooting
- **[README_INSTALLATION.md](README_INSTALLATION.md)** - Detailed installation guide
- **[README.md](README.md)** - Full technical documentation

---

## What You're Getting

A **modern operating system for business automation** with:

✓ **The Circle** - Incoming → Outgoing → Collection → Regenerating (repeat)  
✓ **Real Metrics** - Construction, Sales, Finance dashboards  
✓ **Economic Intelligence** - Growth signals, market data  
✓ **Local AI** - Ollama + Llama3 (no cloud)  
✓ **Full Control** - Shadow, Assist, or Autopilot mode  
✓ **Audited** - Every action logged  

---

## Questions?

1. **Stuck on installation?** → See [DOWNLOAD_GUIDE.md](DOWNLOAD_GUIDE.md)
2. **Need troubleshooting?** → See [QUICKSTART.md](QUICKSTART.md)  
3. **Want technical details?** → See [README.md](README.md) and [docs/](docs/)
4. **Something else?** → Check the docs folder

---

## One More Thing

After `RUN.bat` (or `docker-compose up`), your system is running.

**You don't need to do anything else.**

The browser will open to `http://localhost:8844/ui` automatically.

You'll see:
- Beautiful dashboard with your business metrics
- The 4-phase circle visualization
- Your modules (Construction, Sales, Finance)
- Control mode selector (start with "Assist")
- Theme selector (Dark, Neon, Ocean)

That's it. The system is working. Click around and explore.

---

**Need help?** See the docs. It's all there.

**Ready to go?** Double-click `RUN.bat` or run `docker-compose up`.

**The circle never stops.**
