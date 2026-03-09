# FranklinOps - Quick Start Guide

## Option 1: Docker (Recommended - Just Works)

**Prerequisites:** Docker Desktop installed

```bash
docker run -p 8844:8844 yur-ai-creations/franklinops:latest
# Opens: http://localhost:8844/ui
```

Done. That's it. No Python install, no dependencies, no pain.

---

## Option 2: Windows - Portable ZIP (Download & Run)

**Download:** `FranklinOps-Portable.zip` (50MB)

1. Extract to any folder
2. Double-click `RUN.bat`
3. Browser opens automatically to `http://localhost:8844/ui`
4. System ready in 30 seconds

No installation. No dependencies. Just works.

---

## Option 3: Manual Setup (For Developers)

### Requirements
- Python 3.11+ 
- Git

### Steps

```powershell
# 1. Clone
git clone https://github.com/YUR-AI-CREATIONS/pipeline-.git
cd pipeline-

# 2. Install
python -m pip install -r requirements-ultra-minimal.txt

# 3. Run
python -m uvicorn src.franklinops.server_clean:app --host 127.0.0.1 --port 8844

# 4. Open
# http://localhost:8844/ui
```

---

## Troubleshooting

**Port 8844 already in use?**
```powershell
netstat -ano | findstr :8844
taskkill /PID <PID> /F
```

**Python not found?**
- Download: https://www.python.org/downloads/
- During install: CHECK "Add Python to PATH"
- Restart terminal

**Dependencies failing?**
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-ultra-minimal.txt --no-cache-dir
```

**Still broken?**
- Run: `python -m pip install fastapi uvicorn python-dotenv requests --no-deps`
- If that fails, use Docker instead

---

## Recommended: Docker

Why Docker is best:
- No environment issues
- Works on Windows, Mac, Linux identically  
- 1 command to start
- 1 command to stop
- Reproducible every time

```bash
# Start
docker run -d -p 8844:8844 --name franklinops yur-ai-creations/franklinops:latest

# Stop
docker stop franklinops

# View logs
docker logs franklinops

# Remove
docker rm franklinops
```
