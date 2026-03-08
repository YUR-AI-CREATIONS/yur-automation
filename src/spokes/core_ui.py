"""
Neutral UI pages for FranklinOps core (spoke-agnostic).

Spokes can inject additional pages via SpokeManager.get_ui_pages_for_tenant().
"""

from __future__ import annotations

from typing import Any, Optional


def generate_core_home_page() -> str:
    """Generate the core home page (neutral, no industry bias)."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FranklinOps</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif;
            background: #0a1b0f;
            color: #d4e8df;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 40px;
        }
        .logo {
            font-size: 32px;
            font-weight: 700;
            color: #e8c547;
        }
        .tagline {
            color: #9eb5a8;
            font-size: 14px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .card {
            background: rgba(18, 44, 33, 0.6);
            border: 1px solid rgba(232, 197, 71, 0.2);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .card:hover {
            background: rgba(18, 44, 33, 0.9);
            border-color: rgba(232, 197, 71, 0.5);
        }
        .card h3 {
            color: #e8c547;
            font-size: 18px;
            margin-bottom: 12px;
        }
        .card p {
            color: #9eb5a8;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 12px;
        }
        .card a {
            display: inline-block;
            padding: 8px 16px;
            background: rgba(232, 197, 71, 0.1);
            border: 1px solid rgba(232, 197, 71, 0.3);
            border-radius: 6px;
            color: #e8c547;
            text-decoration: none;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        .card a:hover {
            background: rgba(232, 197, 71, 0.2);
            border-color: rgba(232, 197, 71, 0.6);
        }
        .muted { color: #6b8982; font-size: 12px; }
        .status-ok { color: #52d662; }
        .status-warn { color: #f5a623; }
        .status-error { color: #d0021b; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">FranklinOps</div>
            <div class="tagline">Universal Orchestration OS</div>
        </div>
        
        <div class="card" style="margin-bottom: 30px; background: rgba(232, 197, 71, 0.08); border-color: rgba(232, 197, 71, 0.25);">
            <div style="font-weight: 600; font-size: 1.1rem; margin-bottom: 12px; color: #e8c547;">Welcome</div>
            <p style="color: #d4e8df; margin-bottom: 16px;">
                Data in. Decisions out. Full control. Choose your domain below, or explore the loop.
            </p>
            <p style="color: #9eb5a8; font-size: 12px;">
                <strong>New to FranklinOps?</strong> Start with the <a href="/ui/loop" style="color: #e8c547; text-decoration: underline;">Loop</a> to understand the orchestration flow.
            </p>
        </div>
        
        <h2 style="color: #e8c547; margin-bottom: 20px; font-size: 16px;">Available Domains</h2>
        <div class="grid">
            <div class="card">
                <h3>Construction</h3>
                <p>Pay apps, project controls, lien tracking, bid management.</p>
                <a href="/ui/construction">Explore →</a>
            </div>
            <div class="card">
                <h3>Sales</h3>
                <p>Lead pipeline, opportunity tracking, outbound campaigns.</p>
                <a href="/ui/sales">Explore →</a>
            </div>
            <div class="card">
                <h3>Finance</h3>
                <p>AP/AR, cash flow, accounting integrations.</p>
                <a href="/ui/finance">Explore →</a>
            </div>
        </div>
        
        <h2 style="color: #e8c547; margin-bottom: 20px; font-size: 16px;">System Status</h2>
        <div class="grid">
            <div class="card">
                <h3>Local LLM</h3>
                <div style="margin-bottom: 12px;">
                    <span class="status-ok">●</span> Running (Llama3)
                </div>
                <p class="muted">Powered by Ollama. No API key needed.</p>
                <a href="https://ollama.ai" target="_blank">Learn more →</a>
            </div>
            <div class="card">
                <h3>Governance</h3>
                <div style="margin-bottom: 12px;">
                    <span class="status-ok">●</span> Active
                </div>
                <p class="muted">Frozen immutable policy. Full audit trail.</p>
                <a href="/api/governance/status">Check →</a>
            </div>
            <div class="card">
                <h3>Continuous Loop</h3>
                <div style="margin-bottom: 12px;">
                    <span class="status-ok">●</span> Ready
                </div>
                <p class="muted">Compile → Compose → Recompile → Confirm → Distribute</p>
                <a href="/ui/loop">Monitor →</a>
            </div>
        </div>
    </div>
</body>
</html>
"""


def generate_loop_page() -> str:
    """Generate the continuous loop status page."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Continuous Loop — FranklinOps</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif;
            background: #0a1b0f;
            color: #d4e8df;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { margin-bottom: 40px; }
        .title { font-size: 28px; font-weight: 700; color: #e8c547; margin-bottom: 8px; }
        .subtitle { color: #9eb5a8; font-size: 14px; }
        .phases {
            display: flex;
            gap: 20px;
            margin-bottom: 40px;
            overflow-x: auto;
            padding-bottom: 20px;
        }
        .phase {
            flex-shrink: 0;
            padding: 16px 20px;
            background: rgba(18, 44, 33, 0.6);
            border: 2px solid rgba(232, 197, 71, 0.2);
            border-radius: 8px;
            text-align: center;
            min-width: 150px;
        }
        .phase.active {
            background: rgba(82, 214, 98, 0.1);
            border-color: rgba(82, 214, 98, 0.5);
        }
        .phase-name { font-weight: 600; color: #e8c547; font-size: 13px; }
        .phase-desc { color: #9eb5a8; font-size: 11px; margin-top: 8px; }
        .section { margin-bottom: 40px; }
        .section-title { font-size: 18px; font-weight: 600; color: #e8c547; margin-bottom: 16px; }
        .trace-item {
            background: rgba(18, 44, 33, 0.6);
            border: 1px solid rgba(232, 197, 71, 0.15);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 12px;
            font-size: 12px;
        }
        .trace-field { display: flex; flex-direction: column; }
        .trace-label { color: #9eb5a8; font-size: 10px; margin-bottom: 4px; }
        .trace-value { color: #d4e8df; font-weight: 500; }
        .status-complete { color: #52d662; }
        .status-pending { color: #f5a623; }
        .status-failed { color: #d0021b; }
        .approval-card {
            background: rgba(245, 166, 35, 0.08);
            border: 1px solid rgba(245, 166, 35, 0.25);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .button {
            padding: 8px 16px;
            border: 1px solid rgba(232, 197, 71, 0.3);
            background: rgba(232, 197, 71, 0.1);
            color: #e8c547;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }
        .button:hover {
            background: rgba(232, 197, 71, 0.2);
            border-color: rgba(232, 197, 71, 0.6);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Continuous Loop</div>
            <div class="subtitle">Compile → Compose → Recompile → Confirm → Distribute</div>
        </div>
        
        <div class="phases">
            <div class="phase active">
                <div class="phase-name">COMPILE</div>
                <div class="phase-desc">Fetch data</div>
            </div>
            <div class="phase">
                <div class="phase-name">COMPOSE</div>
                <div class="phase-desc">Dispatch to ports</div>
            </div>
            <div class="phase">
                <div class="phase-name">RECOMPILE</div>
                <div class="phase-desc">Merge results</div>
            </div>
            <div class="phase">
                <div class="phase-name">CONFIRM</div>
                <div class="phase-desc">Governance gates</div>
            </div>
            <div class="phase">
                <div class="phase-name">DISTRIBUTE</div>
                <div class="phase-desc">Export results</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">Pending Approvals</div>
            <p style="color: #9eb5a8; font-size: 12px; margin-bottom: 16px;">No approvals pending.</p>
        </div>
        
        <div class="section">
            <div class="section-title">Recent Traces</div>
            <p style="color: #9eb5a8; font-size: 12px; margin-bottom: 16px;">No traces yet. Start a loop with <code>/api/loop/run</code>.</p>
        </div>
    </div>
</body>
</html>
"""


# Expose as HTTP route templates for server.py
UI_PAGES = [
    {
        "path": "/ui",
        "title": "FranklinOps",
        "generator": generate_core_home_page,
    },
    {
        "path": "/ui/loop",
        "title": "Continuous Loop",
        "generator": generate_loop_page,
    },
]
