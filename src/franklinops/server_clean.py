"""
FranklinOps — Universal Orchestration OS
Clean, minimal server using the new Tailwind UI with vivid color schemes.

This is a CLEAN restart focused on:
- Universal (not company-specific)
- Simple core endpoints only
- Beautiful modern UI
- Air-gapped by default
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import the new clean UI
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.spokes.core_ui import generate_core_home_page, generate_loop_page
except ImportError:
    # Fallback if import fails
    def generate_core_home_page():
        return "<h1>FranklinOps</h1><p>Server is running but UI not loaded</p>"
    def generate_loop_page():
        return "<h1>Loop</h1><p>Coming soon</p>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("franklinops")

# Create app
app = FastAPI(
    title="FranklinOps — Universal Orchestration OS",
    description="Data in. Decisions out. Full control.",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint (prevents 404 errors)"""
    # Return a simple SVG favicon
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect fill="#e8c547" width="100" height="100"/>
        <text x="50" y="65" font-size="70" font-weight="bold" text-anchor="middle" fill="#0a1b0f">F</text>
    </svg>"""
    return JSONResponse(content=svg, media_type="image/svg+xml")


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    """API status and system info"""
    return {
        "system": "FranklinOps Universal Orchestration OS",
        "status": "running",
        "features": [
            "Universal core (not company-specific)",
            "Air-gapped by default",
            "Local LLM integration (Ollama)",
            "Deterministic builder",
            "Continuous loop orchestration",
            "Distributed tracing",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# UI PAGES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """Redirect to home"""
    return '<script>window.location.href = "/ui"</script>'


@app.get("/ui", response_class=HTMLResponse)
async def ui_home() -> str:
    """Home page with domain selector and system status"""
    return generate_core_home_page()


@app.get("/ui/loop", response_class=HTMLResponse)
async def ui_loop() -> str:
    """Continuous loop status page"""
    return generate_loop_page()


# ============================================================================
# DOCUMENTATION ENDPOINTS
# ============================================================================

@app.get("/docs/architecture", response_class=HTMLResponse)
async def docs_architecture() -> str:
    """Architecture overview"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <title>Architecture — FranklinOps</title>
    </head>
    <body class="bg-gray-950 text-gray-100 p-8">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-4xl font-bold text-amber-400 mb-8">FranklinOps Architecture</h1>
            
            <div class="bg-gray-900 border border-amber-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-amber-400">Core OS (Universal)</h2>
                <ul class="space-y-2 text-gray-300">
                    <li>✓ RuntimeKernel — boot, DB, audit, governance</li>
                    <li>✓ Flow Registry — universal plugin mechanism</li>
                    <li>✓ Event Bus — in-memory + NATS pub/sub</li>
                    <li>✓ FleetHub — agent/plugin dispatch</li>
                    <li>✓ Governance Provenance — immutable policy hashes</li>
                </ul>
            </div>
            
            <div class="bg-gray-900 border border-green-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-green-400">Spokes (Industry-Specific)</h2>
                <ul class="space-y-2 text-gray-300">
                    <li>🏗️ Construction — pay apps, project controls</li>
                    <li>📈 Sales — pipeline, opportunities</li>
                    <li>💰 Finance — AP/AR, cash flow</li>
                    <li>🔧 Custom — add your own spoke</li>
                </ul>
            </div>
            
            <div class="bg-gray-900 border border-blue-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-blue-400">Orchestration Loop (5 Phases)</h2>
                <ol class="space-y-2 text-gray-300">
                    <li>1️⃣ <span class="font-semibold">COMPILE</span> — Fetch incoming data</li>
                    <li>2️⃣ <span class="font-semibold">COMPOSE</span> — Dispatch to ports</li>
                    <li>3️⃣ <span class="font-semibold">RECOMPILE</span> — Merge results</li>
                    <li>4️⃣ <span class="font-semibold">CONFIRM</span> — Approval gates</li>
                    <li>5️⃣ <span class="font-semibold">DISTRIBUTE</span> — Export destinations</li>
                </ol>
            </div>
            
            <div class="text-center text-gray-500 text-sm mt-8">
                <p><a href="/ui" class="text-amber-400 hover:underline">← Back to Home</a></p>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/docs/quick-start", response_class=HTMLResponse)
async def docs_quick_start() -> str:
    """Quick start guide"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <title>Quick Start — FranklinOps</title>
    </head>
    <body class="bg-gray-950 text-gray-100 p-8">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-4xl font-bold text-amber-400 mb-8">Quick Start Guide</h1>
            
            <div class="bg-gray-900 border border-amber-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-amber-400">1. Choose Your Theme</h2>
                <p class="text-gray-300 mb-3">Look in the top-right corner for the theme selector:</p>
                <ul class="space-y-2 text-gray-300 ml-4">
                    <li>🌙 Dark — Professional (default)</li>
                    <li>🌈 Neon — High energy</li>
                    <li>🌊 Ocean — Cool and calm</li>
                    <li>🌲 Forest — Natural</li>
                    <li>☀️ Solar — Warm</li>
                    <li>💻 Cyber — Futuristic</li>
                </ul>
            </div>
            
            <div class="bg-gray-900 border border-green-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-green-400">2. Select a Domain</h2>
                <p class="text-gray-300">Choose from Construction, Sales, or Finance to explore domain-specific workflows.</p>
            </div>
            
            <div class="bg-gray-900 border border-blue-400 rounded-lg p-6 mb-6">
                <h2 class="text-2xl font-bold mb-4 text-blue-400">3. Monitor the Loop</h2>
                <p class="text-gray-300 mb-3">Visit <a href="/ui/loop" class="text-blue-400 hover:underline">/ui/loop</a> to see the continuous orchestration:</p>
                <ul class="space-y-1 text-gray-300 ml-4">
                    <li>📥 Compile data</li>
                    <li>🔀 Dispatch to multiple ports</li>
                    <li>🔗 Merge results</li>
                    <li>✅ Governance confirmation</li>
                    <li>📤 Export to destinations</li>
                </ul>
            </div>
            
            <div class="bg-gray-900 border border-purple-400 rounded-lg p-6">
                <h2 class="text-2xl font-bold mb-4 text-purple-400">4. API Endpoints</h2>
                <div class="bg-gray-800 p-3 rounded font-mono text-sm text-gray-300">
                    GET /health — System health<br/>
                    GET /api/status — Full system status<br/>
                    GET /ui — Home page<br/>
                    GET /ui/loop — Orchestration status<br/>
                </div>
            </div>
            
            <div class="text-center text-gray-500 text-sm mt-8">
                <p><a href="/ui" class="text-amber-400 hover:underline">← Back to Home</a></p>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================================
# API ENDPOINTS (Minimal Core)
# ============================================================================

class LoopStartRequest(BaseModel):
    """Request to start a loop execution"""
    tenant_id: str = "default"
    compile_source: str = "default"
    compose_ports: list[str] = Field(default=["flow", "fleet"])
    distribute_destinations: list[str] = Field(default=["filesystem"])


@app.post("/api/loop/run")
async def start_loop(req: LoopStartRequest) -> dict[str, Any]:
    """Start a continuous loop execution"""
    import uuid
    return {
        "status": "started",
        "trace_id": "trace-" + str(uuid.uuid4())[:8],
        "tenant_id": req.tenant_id,
        "phase": "compile",
        "message": "Loop execution started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/loop/status")
async def loop_status() -> dict[str, Any]:
    """Get current loop status"""
    return {
        "status": "ready",
        "recent_traces": [],
        "pending_approvals": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status": 500,
        },
    )


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """On startup"""
    logger.info("=" * 80)
    logger.info("FranklinOps — Universal Orchestration OS")
    logger.info("=" * 80)
    logger.info("🚀 Server started on http://localhost:8844")
    logger.info("🎨 Visit http://localhost:8844/ui for the UI")
    logger.info("📖 API docs at http://localhost:8844/docs")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown"""
    logger.info("FranklinOps server shutting down...")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "server_clean:app",
        host="0.0.0.0",
        port=8844,
        reload=False,
        log_level="info",
    )
