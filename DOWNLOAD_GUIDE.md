# FranklinOps - Download & Run Guide

## For End Users (Non-Technical)

### Step 1: Download
Click here: https://github.com/YUR-AI-CREATIONS/pipeline-/archive/refs/heads/main.zip

This downloads the entire system (~50MB).

### Step 2: Extract
- Right-click the ZIP file
- Select **"Extract All..."** 
- Choose a folder (like `C:\Users\YourName\Downloads\FranklinOps`)
- Click Extract

### Step 3: Run
Open the extracted folder and **double-click `RUN.bat`**

That's it. Your browser will open automatically to the system.

---

## What Happens When You Click RUN.bat

1. Checks if Python is installed (installs if needed)
2. Downloads the 4 tiny dependencies (4 seconds)
3. Starts the server (2 seconds)
4. Opens your browser to http://localhost:8844/ui
5. System is ready to use

**Total time: 30 seconds on first run. 5 seconds after that.**

---

## If Something Goes Wrong

### Python Not Found Error
**Solution:** Install Python
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or 3.12
3. **IMPORTANT:** During installation, **CHECK the box that says "Add Python to PATH"**
4. Complete the installation
5. Double-click `RUN.bat` again

### Port 8844 Already In Use
**Solution:** Close the other app using that port
1. Press `Ctrl+Shift+Esc` to open Task Manager
2. Find "python" in the list
3. Right-click and select "End Task"
4. Try `RUN.bat` again

### Still Broken?
1. Delete the `data/` folder (just for testing)
2. Try `RUN.bat` again
3. If it still fails, use Docker instead (see below)

---

## Better Way: Docker (Works 100%)

If you have **Docker Desktop** installed:

1. Open Command Prompt or PowerShell in the extracted folder
2. Type: `docker-compose up`
3. Wait 30 seconds
4. Open: http://localhost:8844/ui

Done. This way always works, even if Python is broken or ports are weird.

**Docker download:** https://www.docker.com/products/docker-desktop

---

## For Developers

### Option A: Clone from Git
```bash
git clone https://github.com/YUR-AI-CREATIONS/pipeline-.git
cd pipeline-
python -m pip install -r requirements-ultra-minimal.txt
python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844
```

### Option B: Docker
```bash
git clone https://github.com/YUR-AI-CREATIONS/pipeline-.git
cd pipeline-
docker-compose up
```

### Option C: Docker Directly
```bash
docker pull yur-ai-creations/franklinops:latest
docker run -p 8844:8844 yur-ai-creations/franklinops:latest
```

---

## Support

**Having trouble?**

1. Check [QUICKSTART.md](QUICKSTART.md) for common issues
2. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed help
3. Check [README_INSTALLATION.md](README_INSTALLATION.md) for setup options

**None of that helps?**

- Make sure you followed Step 1 and Step 2 exactly
- Try Docker instead - it bypasses all environment issues
- If Docker also fails, something else is wrong on your system

---

## What You Get After Running

A beautiful, modern OS interface showing:

- **4 Phases** - Incoming, Outgoing, Collection, Regenerating (the circle)
- **Live Metrics** - Construction, Sales, Finance numbers
- **Economic Intelligence** - Regional growth, market data
- **Control Modes** - Shadow (watch), Assist (approve), Autopilot (run)
- **Theme Selector** - Dark, Neon, Ocean themes

All your business data in one place. No more scattered tools.

---

## Next Steps After Running

1. **Explore the Dashboard** - See your metrics
2. **Read the Docs** - Understand how the system works
3. **Choose Your Control Mode** - Start with "Assist"
4. **Connect Your Data** - Plug in Construction/Sales/Finance
5. **Watch It Work** - The circle never stops

---

**That's it. You're ready to go.**

Questions? See the troubleshooting section above or check the docs folder.
