"""
Neutral UI pages for FranklinOps core (spoke-agnostic).

Spokes can inject additional pages via SpokeManager.get_ui_pages_for_tenant().

Pages now feature:
- Tailwind CSS with vivid, high-contrast design
- User-selectable color schemes (Dark, Neon, Ocean, Forest, Solar, Cyber)
- Local storage persistence for color preference
- Responsive, modern UI
"""

from __future__ import annotations

from typing import Any, Optional

# Tailwind CDN + custom color scheme JavaScript
TAILWIND_HEAD = """
<script src="https://cdn.tailwindcss.com"></script>
<script>
    tailwind.config = {
        theme: {
            extend: {
                colors: {
                    neon: {
                        pink: '#FF006E',
                        cyan: '#00F5FF',
                        lime: '#39FF14',
                        purple: '#B537F2',
                    },
                    ocean: {
                        dark: '#0a1628',
                        blue: '#00d4ff',
                        teal: '#00ffff',
                    },
                    forest: {
                        dark: '#0a2e1e',
                        green: '#00ff88',
                        lime: '#7fff00',
                    },
                    solar: {
                        dark: '#1a1410',
                        orange: '#ff8c00',
                        yellow: '#ffd700',
                    },
                    cyber: {
                        dark: '#0d0221',
                        pink: '#ec0868',
                        cyan: '#00d9ff',
                    }
                }
            }
        }
    }
</script>
<style>
    * { transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease; }
    
    /* Dark Theme (Default) */
    body.theme-dark {
        @apply bg-gray-950 text-gray-100;
    }
    body.theme-dark .accent { @apply text-amber-400; }
    body.theme-dark .card { @apply bg-gray-900 border-gray-700; }
    body.theme-dark .card:hover { @apply bg-gray-800 border-amber-400; }
    
    /* Neon Theme */
    body.theme-neon {
        @apply bg-gray-950 text-pink-100;
    }
    body.theme-neon .accent { @apply text-neon-cyan; }
    body.theme-neon .accent-secondary { @apply text-neon-pink; }
    body.theme-neon .card { @apply bg-gray-900 border-neon-cyan border-2; }
    body.theme-neon .card:hover { @apply bg-gray-800 border-neon-pink shadow-lg shadow-neon-pink/50; }
    body.theme-neon .btn { @apply bg-neon-pink text-white border-neon-pink hover:bg-neon-cyan hover:text-gray-950; }
    
    /* Ocean Theme */
    body.theme-ocean {
        @apply bg-ocean-dark text-ocean-teal;
    }
    body.theme-ocean .accent { @apply text-ocean-blue; }
    body.theme-ocean .card { @apply bg-gray-950 border-ocean-blue border-2; }
    body.theme-ocean .card:hover { @apply bg-gray-900 border-ocean-teal shadow-lg shadow-ocean-blue/50; }
    body.theme-ocean .btn { @apply bg-ocean-blue text-gray-950 border-ocean-blue hover:bg-ocean-teal; }
    
    /* Forest Theme */
    body.theme-forest {
        @apply bg-forest-dark text-forest-green;
    }
    body.theme-forest .accent { @apply text-forest-lime; }
    body.theme-forest .card { @apply bg-gray-900 border-forest-green border-2; }
    body.theme-forest .card:hover { @apply bg-gray-800 border-forest-lime shadow-lg shadow-forest-green/50; }
    body.theme-forest .btn { @apply bg-forest-lime text-gray-950 border-forest-lime hover:bg-forest-green; }
    
    /* Solar Theme */
    body.theme-solar {
        @apply bg-solar-dark text-solar-yellow;
    }
    body.theme-solar .accent { @apply text-solar-orange; }
    body.theme-solar .card { @apply bg-gray-900 border-solar-orange border-2; }
    body.theme-solar .card:hover { @apply bg-gray-800 border-solar-yellow shadow-lg shadow-solar-orange/50; }
    body.theme-solar .btn { @apply bg-solar-orange text-gray-950 border-solar-orange hover:bg-solar-yellow; }
    
    /* Cyber Theme */
    body.theme-cyber {
        @apply bg-cyber-dark text-cyber-cyan;
    }
    body.theme-cyber .accent { @apply text-cyber-pink; }
    body.theme-cyber .card { @apply bg-gray-950 border-cyber-cyan border-2; }
    body.theme-cyber .card:hover { @apply bg-gray-900 border-cyber-pink shadow-lg shadow-cyber-pink/50; }
    body.theme-cyber .btn { @apply bg-cyber-cyan text-cyber-dark border-cyber-cyan hover:bg-cyber-pink hover:text-white; }
    
    .btn {
        @apply inline-block px-4 py-2 rounded border font-semibold transition-all duration-300 cursor-pointer;
    }
    
    .card {
        @apply p-6 rounded-lg border transition-all duration-300;
    }
</style>
"""

COLOR_SCHEME_SELECTOR = """
<div class="fixed top-4 right-4 z-50 flex gap-2 p-3 bg-gray-800 rounded-lg border border-gray-700">
    <div class="text-xs text-gray-400 flex items-center">Theme:</div>
    <select id="themeSelector" class="bg-gray-700 text-white px-3 py-1 rounded text-sm border border-gray-600 cursor-pointer hover:border-amber-400">
        <option value="dark">Dark</option>
        <option value="neon">Neon</option>
        <option value="ocean">Ocean</option>
        <option value="forest">Forest</option>
        <option value="solar">Solar</option>
        <option value="cyber">Cyber</option>
    </select>
</div>

<script>
    // Load theme from localStorage
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.className = 'theme-' + savedTheme;
    document.getElementById('themeSelector').value = savedTheme;
    
    // Save theme preference when changed
    document.getElementById('themeSelector').addEventListener('change', (e) => {
        const theme = e.target.value;
        document.body.className = 'theme-' + theme;
        localStorage.setItem('theme', theme);
    });
</script>
"""


def generate_core_home_page() -> str:
    """Generate the core home page with Tailwind CSS and vivid color schemes."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FranklinOps — Universal Orchestration OS</title>
    {TAILWIND_HEAD}
</head>
<body class="theme-dark">
    {COLOR_SCHEME_SELECTOR}
    
    <div class="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-16">
                <h1 class="text-6xl font-bold accent mb-4">FranklinOps</h1>
                <p class="text-xl text-gray-400">Universal Orchestration OS</p>
                <p class="text-sm text-gray-500 mt-4">Data in. Decisions out. Full control.</p>
            </div>
            
            <!-- Welcome Banner -->
            <div class="card mb-12 border-2 border-current accent text-center">
                <div class="mb-4">
                    <h2 class="text-2xl font-bold accent mb-3">Welcome to the Future of Orchestration</h2>
                    <p class="text-gray-300 mb-4">
                        A universal, plug-in-first OS for any industry. Air-gapped by default. Deterministic. Traceable.
                    </p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-opacity-10 p-3 rounded">
                        <div class="font-semibold accent">🧠 Local LLM</div>
                        <p class="text-xs text-gray-400 mt-1">Ollama + Llama3</p>
                    </div>
                    <div class="bg-opacity-10 p-3 rounded">
                        <div class="font-semibold accent">🔒 Air-Gapped</div>
                        <p class="text-xs text-gray-400 mt-1">Default-deny internet</p>
                    </div>
                    <div class="bg-opacity-10 p-3 rounded">
                        <div class="font-semibold accent">⚡ Deterministic</div>
                        <p class="text-xs text-gray-400 mt-1">Frozen immutable hashes</p>
                    </div>
                </div>
            </div>
            
            <!-- Available Domains -->
            <div class="mb-16">
                <h2 class="text-3xl font-bold accent mb-8">Available Domains</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Construction -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-3xl">🏗️</span>
                            <h3 class="text-xl font-bold accent">Construction</h3>
                        </div>
                        <p class="text-sm text-gray-400 mb-4">
                            Pay apps, project controls, lien tracking, and bid management for construction workflows.
                        </p>
                        <a href="/ui/construction" class="btn">Explore →</a>
                    </div>
                    
                    <!-- Sales -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-3xl">📈</span>
                            <h3 class="text-xl font-bold accent">Sales</h3>
                        </div>
                        <p class="text-sm text-gray-400 mb-4">
                            Lead pipeline, opportunity tracking, and outbound campaign orchestration.
                        </p>
                        <a href="/ui/sales" class="btn">Explore →</a>
                    </div>
                    
                    <!-- Finance -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-3xl">💰</span>
                            <h3 class="text-xl font-bold accent">Finance</h3>
                        </div>
                        <p class="text-sm text-gray-400 mb-4">
                            AP/AR management, cash flow analysis, and accounting integrations.
                        </p>
                        <a href="/ui/finance" class="btn">Explore →</a>
                    </div>
                </div>
            </div>
            
            <!-- System Status -->
            <div class="mb-16">
                <h2 class="text-3xl font-bold accent mb-8">System Status</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- LLM Status -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-2xl">🤖</span>
                            <h3 class="text-lg font-bold">Local LLM</h3>
                        </div>
                        <div class="flex items-center gap-2 mb-3">
                            <span class="text-green-400 text-xl">●</span>
                            <span class="text-sm font-semibold">Running (Llama3)</span>
                        </div>
                        <p class="text-xs text-gray-400 mb-4">Powered by Ollama. No API key required.</p>
                        <a href="https://ollama.ai" target="_blank" rel="noopener" class="btn text-sm">Learn more →</a>
                    </div>
                    
                    <!-- Governance Status -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-2xl">🔐</span>
                            <h3 class="text-lg font-bold">Governance</h3>
                        </div>
                        <div class="flex items-center gap-2 mb-3">
                            <span class="text-green-400 text-xl">●</span>
                            <span class="text-sm font-semibold">Active & Frozen</span>
                        </div>
                        <p class="text-xs text-gray-400 mb-4">Immutable policy. Full audit trail.</p>
                        <a href="/api/governance/status" class="btn text-sm">Check →</a>
                    </div>
                    
                    <!-- Loop Status -->
                    <div class="card">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-2xl">🔄</span>
                            <h3 class="text-lg font-bold">Continuous Loop</h3>
                        </div>
                        <div class="flex items-center gap-2 mb-3">
                            <span class="text-green-400 text-xl">●</span>
                            <span class="text-sm font-semibold">Ready</span>
                        </div>
                        <p class="text-xs text-gray-400 mb-4">Compile → Compose → Recompile → Confirm → Distribute</p>
                        <a href="/ui/loop" class="btn text-sm">Monitor →</a>
                    </div>
                </div>
            </div>
            
            <!-- Architecture Overview -->
            <div class="card border-2 border-current">
                <h2 class="text-2xl font-bold accent mb-6">Architecture</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
                    <div>
                        <h3 class="font-bold accent mb-3">Core Features</h3>
                        <ul class="space-y-2 text-gray-400">
                            <li>✓ Universal core OS (not company-specific)</li>
                            <li>✓ Plug-in spokes for any vertical</li>
                            <li>✓ Air-gapped by default</li>
                            <li>✓ Deterministic builder with frozen hashes</li>
                            <li>✓ Full distributed tracing (trace_id)</li>
                        </ul>
                    </div>
                    <div>
                        <h3 class="font-bold accent mb-3">Orchestration Loop</h3>
                        <ol class="space-y-2 text-gray-400">
                            <li><span class="font-semibold accent">1. Compile</span> — Fetch incoming data</li>
                            <li><span class="font-semibold accent">2. Compose</span> — Dispatch to multiple ports</li>
                            <li><span class="font-semibold accent">3. Recompile</span> — Merge results</li>
                            <li><span class="font-semibold accent">4. Confirm</span> — Run approval gates</li>
                            <li><span class="font-semibold accent">5. Distribute</span> — Export to destinations</li>
                        </ol>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="text-center mt-16 text-gray-500 text-sm">
                <p>FranklinOps Universal Orchestration OS • Built with ❤️ for orchestration</p>
                <p class="mt-2 text-xs">Docs: <a href="/docs" class="accent hover:underline">Documentation</a> • Status: <a href="/api/status" class="accent hover:underline">API Status</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def generate_loop_page() -> str:
    """Generate the continuous loop status page with Tailwind CSS and vivid colors."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Continuous Loop — FranklinOps</title>
    {TAILWIND_HEAD}
</head>
<body class="theme-dark">
    {COLOR_SCHEME_SELECTOR}
    
    <div class="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="mb-12">
                <h1 class="text-5xl font-bold accent mb-4">Continuous Loop</h1>
                <p class="text-gray-400">Compile → Compose → Recompile → Confirm → Distribute</p>
            </div>
            
            <!-- Loop Phases Visualization -->
            <div class="card mb-12 border-2 border-current">
                <h2 class="text-2xl font-bold accent mb-8">Current Phase</h2>
                <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <div class="card border-2 border-current accent text-center py-4">
                        <div class="text-xs font-bold accent mb-2">COMPILE</div>
                        <div class="text-xl">📥</div>
                        <p class="text-xs text-gray-400 mt-2">Fetch Data</p>
                    </div>
                    <div class="card text-center py-4 opacity-50">
                        <div class="text-xs font-bold mb-2">COMPOSE</div>
                        <div class="text-xl">🔀</div>
                        <p class="text-xs text-gray-400 mt-2">Dispatch</p>
                    </div>
                    <div class="card text-center py-4 opacity-50">
                        <div class="text-xs font-bold mb-2">RECOMPILE</div>
                        <div class="text-xl">🔗</div>
                        <p class="text-xs text-gray-400 mt-2">Merge</p>
                    </div>
                    <div class="card text-center py-4 opacity-50">
                        <div class="text-xs font-bold mb-2">CONFIRM</div>
                        <div class="text-xl">✅</div>
                        <p class="text-xs text-gray-400 mt-2">Approve</p>
                    </div>
                    <div class="card text-center py-4 opacity-50">
                        <div class="text-xs font-bold mb-2">DISTRIBUTE</div>
                        <div class="text-xl">📤</div>
                        <p class="text-xs text-gray-400 mt-2">Export</p>
                    </div>
                </div>
            </div>
            
            <!-- Pending Approvals -->
            <div class="mb-12">
                <h2 class="text-2xl font-bold accent mb-6">Pending Approvals</h2>
                <div class="card border-2 border-yellow-500">
                    <p class="text-yellow-400 font-semibold">✓ No approvals pending</p>
                    <p class="text-sm text-gray-400 mt-2">All traces have been approved or exported.</p>
                </div>
            </div>
            
            <!-- Recent Traces -->
            <div class="mb-12">
                <h2 class="text-2xl font-bold accent mb-6">Recent Traces</h2>
                <div class="space-y-4">
                    <!-- Trace Item 1 -->
                    <div class="card">
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Trace ID</p>
                                <p class="font-mono text-sm accent">abc-123-def</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Status</p>
                                <p class="font-semibold text-green-400">✓ Distributed</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Duration</p>
                                <p class="text-sm text-gray-300">2.34s</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Exports</p>
                                <p class="text-sm text-gray-300">3 destinations</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Trace Item 2 -->
                    <div class="card">
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Trace ID</p>
                                <p class="font-mono text-sm accent">xyz-789-uvw</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Status</p>
                                <p class="font-semibold text-green-400">✓ Distributed</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Duration</p>
                                <p class="text-sm text-gray-300">1.87s</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-500 uppercase font-bold">Exports</p>
                                <p class="text-sm text-gray-300">2 destinations</p>
                            </div>
                        </div>
                    </div>
                </div>
                <p class="text-center text-gray-500 text-sm mt-8">
                    No traces yet. Start a loop with <code class="bg-gray-800 px-2 py-1 rounded text-xs">/api/loop/run</code>
                </p>
            </div>
            
            <!-- Control Center -->
            <div class="card border-2 border-current">
                <h2 class="text-2xl font-bold accent mb-6">Control Center</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <button class="btn bg-green-600 hover:bg-green-500 text-white border-green-600">
                        ▶ Start Loop
                    </button>
                    <button class="btn bg-blue-600 hover:bg-blue-500 text-white border-blue-600">
                        📊 View Traces
                    </button>
                    <button class="btn bg-purple-600 hover:bg-purple-500 text-white border-purple-600">
                        ⚙️ Settings
                    </button>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="text-center mt-16 text-gray-500 text-sm">
                <p>Real-time loop orchestration and monitoring</p>
                <p class="mt-2 text-xs"><a href="/" class="accent hover:underline">← Back to Home</a> • <a href="/api/loop/status" class="accent hover:underline">API Endpoint</a></p>
            </div>
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
