"""
Modern FranklinOps OS Dashboard
Consumer-facing interface - no tech showing unless they dig into settings
"""

import json
from datetime import datetime, timezone


def generate_os_dashboard():
    """Main OS dashboard - what users see when they open FranklinOps"""
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FranklinOps OS</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
        <style>
            * { transition: all 0.3s ease; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }
            
            .glass { backdrop-filter: blur(10px); background: rgba(255,255,255,0.1); }
            .card-hover { cursor: pointer; }
            .card-hover:hover { transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
            
            .status-pulse { animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            
            .theme-dark { --bg: #0f172a; --bg-secondary: #1e293b; --text: #e2e8f0; --accent: #3b82f6; }
            .theme-neon { --bg: #0a0e27; --bg-secondary: #1a1a3e; --text: #00ff9f; --accent: #ff006e; }
            .theme-ocean { --bg: #0d1b2a; --bg-secondary: #1b3a52; --text: #a8d5ff; --accent: #0099ff; }
            
            body { background-color: var(--bg); color: var(--text); }
            .card { background-color: var(--bg-secondary); }
        </style>
    </head>
    <body class="theme-dark">
        <!-- Header -->
        <div class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700 glass">
            <div class="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center font-bold text-white">F</div>
                    <div>
                        <h1 class="text-xl font-bold text-white">FranklinOps</h1>
                        <p class="text-xs text-gray-400">The circle never stops</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-4">
                    <div class="text-sm text-gray-400">
                        <p id="timeDisplay"></p>
                        <p class="text-xs text-green-400 flex items-center gap-1"><span class="inline-block w-2 h-2 bg-green-400 rounded-full status-pulse"></span>System Online</p>
                    </div>
                    <select id="themeSelect" class="bg-gray-800 text-white px-3 py-2 rounded text-sm border border-gray-700 cursor-pointer">
                        <option value="dark">Dark</option>
                        <option value="neon">Neon</option>
                        <option value="ocean">Ocean</option>
                    </select>
                </div>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="pt-24 pb-12 px-6 max-w-7xl mx-auto">
            
            <!-- Welcome Section -->
            <div class="mb-12">
                <h2 class="text-4xl font-bold text-white mb-4">Welcome Back</h2>
                <p class="text-gray-400">The system is running. Four phases. One loop. Everything connected.</p>
            </div>
            
            <!-- System Status Grid -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-12">
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">INCOMING</p>
                    <p class="text-3xl font-bold text-white">1,247</p>
                    <p class="text-xs text-gray-500 mt-2">Documents processed today</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-blue-500 h-full" style="width: 78%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">OUTGOING</p>
                    <p class="text-3xl font-bold text-white">892</p>
                    <p class="text-xs text-gray-500 mt-2">Actions completed</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-green-500 h-full" style="width: 92%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">COLLECTION</p>
                    <p class="text-3xl font-bold text-white">15.2GB</p>
                    <p class="text-xs text-gray-500 mt-2">Indexed and verified</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-purple-500 h-full" style="width: 65%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">REGENERATING</p>
                    <p class="text-3xl font-bold text-white">156</p>
                    <p class="text-xs text-gray-500 mt-2">Metrics computed</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-orange-500 h-full" style="width: 84%"></div>
                    </div>
                </div>
            </div>
            
            <!-- The Loop Visualization -->
            <div class="card rounded-lg p-8 border border-gray-700 mb-12">
                <h3 class="text-xl font-bold text-white mb-8">The Circle Never Stops</h3>
                
                <div class="grid grid-cols-4 gap-4">
                    <!-- Incoming Phase -->
                    <div class="relative">
                        <div class="bg-blue-900 rounded-lg p-6 border-2 border-blue-500 text-center">
                            <p class="text-2xl mb-2">📥</p>
                            <h4 class="font-bold text-white mb-2">INCOMING</h4>
                            <p class="text-xs text-gray-300">Documents • Leads • Invoices</p>
                            <p class="text-sm text-blue-400 mt-3 font-mono">Active</p>
                        </div>
                        <div class="absolute -right-2 top-1/2 transform -translate-y-1/2 text-2xl">→</div>
                    </div>
                    
                    <!-- Outgoing Phase -->
                    <div class="relative">
                        <div class="bg-green-900 rounded-lg p-6 border-2 border-green-500 text-center">
                            <p class="text-2xl mb-2">📤</p>
                            <h4 class="font-bold text-white mb-2">OUTGOING</h4>
                            <p class="text-xs text-gray-300">Emails • Reports • Approvals</p>
                            <p class="text-sm text-green-400 mt-3 font-mono">Active</p>
                        </div>
                        <div class="absolute -right-2 top-1/2 transform -translate-y-1/2 text-2xl">→</div>
                    </div>
                    
                    <!-- Collection Phase -->
                    <div class="relative">
                        <div class="bg-purple-900 rounded-lg p-6 border-2 border-purple-500 text-center">
                            <p class="text-2xl mb-2">📦</p>
                            <h4 class="font-bold text-white mb-2">COLLECTION</h4>
                            <p class="text-xs text-gray-300">Store • Index • Audit</p>
                            <p class="text-sm text-purple-400 mt-3 font-mono">Active</p>
                        </div>
                        <div class="absolute -right-2 top-1/2 transform -translate-y-1/2 text-2xl">→</div>
                    </div>
                    
                    <!-- Regenerating Phase -->
                    <div class="relative">
                        <div class="bg-orange-900 rounded-lg p-6 border-2 border-orange-500 text-center">
                            <p class="text-2xl mb-2">🔄</p>
                            <h4 class="font-bold text-white mb-2">REGENERATING</h4>
                            <p class="text-xs text-gray-300">Metrics • Learning • Evolution</p>
                            <p class="text-sm text-orange-400 mt-3 font-mono">Active</p>
                        </div>
                    </div>
                </div>
                
                <div class="mt-8 text-center text-sm text-gray-400">
                    <p>↻ Loop cycles continuously • Data flows in circle • System improves itself</p>
                </div>
            </div>
            
            <!-- Domains / Industry Modules -->
            <div class="mb-12">
                <h3 class="text-xl font-bold text-white mb-6">Your Modules</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Construction -->
                    <div class="card rounded-lg p-6 border border-gray-700 card-hover cursor-pointer" onclick="loadDomain('construction')">
                        <div class="flex items-start justify-between mb-4">
                            <div>
                                <h4 class="text-lg font-bold text-white">Construction</h4>
                                <p class="text-xs text-gray-400">Land → Build → Warranty</p>
                            </div>
                            <span class="text-3xl">🏗️</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-4">
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-blue-400">128</p>
                                <p class="text-xs text-gray-500">Projects</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400">847</p>
                                <p class="text-xs text-gray-500">Pay Apps</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400">23</p>
                                <p class="text-xs text-gray-500">Alerts</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Sales -->
                    <div class="card rounded-lg p-6 border border-gray-700 card-hover cursor-pointer" onclick="loadDomain('sales')">
                        <div class="flex items-start justify-between mb-4">
                            <div>
                                <h4 class="text-lg font-bold text-white">Sales</h4>
                                <p class="text-xs text-gray-400">Pipeline → Opportunity → Close</p>
                            </div>
                            <span class="text-3xl">📈</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-4">
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-blue-400">156</p>
                                <p class="text-xs text-gray-500">Pipeline</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400">$4.2M</p>
                                <p class="text-xs text-gray-500">Forecast</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400">42</p>
                                <p class="text-xs text-gray-500">Qualified</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Finance -->
                    <div class="card rounded-lg p-6 border border-gray-700 card-hover cursor-pointer" onclick="loadDomain('finance')">
                        <div class="flex items-start justify-between mb-4">
                            <div>
                                <h4 class="text-lg font-bold text-white">Finance</h4>
                                <p class="text-xs text-gray-400">AP → AR → Cash Flow</p>
                            </div>
                            <span class="text-3xl">💰</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-4">
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-blue-400">$2.1M</p>
                                <p class="text-xs text-gray-500">Payables</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400">$3.8M</p>
                                <p class="text-xs text-gray-500">Receivables</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400">34d</p>
                                <p class="text-xs text-gray-500">DSO</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Economic Intelligence -->
            <div class="card rounded-lg p-8 border border-gray-700 mb-12">
                <h3 class="text-xl font-bold text-white mb-4">Economic Intelligence</h3>
                <p class="text-gray-400 text-sm mb-6">Real-time market data • Regional growth • Infrastructure signals</p>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="border border-gray-700 rounded p-4">
                        <p class="text-gray-400 text-xs mb-2">GROWTH INDEX</p>
                        <p class="text-2xl font-bold text-green-400">87.3</p>
                        <p class="text-xs text-gray-500 mt-2">+4.2% from last month</p>
                    </div>
                    <div class="border border-gray-700 rounded p-4">
                        <p class="text-gray-400 text-xs mb-2">MIGRATION PREDICTION</p>
                        <p class="text-2xl font-bold text-blue-400">+2.1%</p>
                        <p class="text-xs text-gray-500 mt-2">Inbound population flow</p>
                    </div>
                    <div class="border border-gray-700 rounded p-4">
                        <p class="text-gray-400 text-xs mb-2">ABSORPTION MONTHS</p>
                        <p class="text-2xl font-bold text-purple-400">4.2</p>
                        <p class="text-xs text-gray-500 mt-2">Market absorption rate</p>
                    </div>
                </div>
            </div>
            
            <!-- Control Modes -->
            <div class="mb-12">
                <h3 class="text-xl font-bold text-white mb-6">How You Control It</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="card rounded-lg p-6 border border-gray-700">
                        <p class="text-3xl mb-3">👁️</p>
                        <h4 class="font-bold text-white mb-2">Shadow</h4>
                        <p class="text-sm text-gray-400">Watch what the system does. Observe. Learn. No changes yet.</p>
                    </div>
                    <div class="card rounded-lg p-6 border border-gray-700">
                        <p class="text-3xl mb-3">🤝</p>
                        <h4 class="font-bold text-white mb-2">Assist</h4>
                        <p class="text-sm text-gray-400">System suggests. You approve. Human + AI together.</p>
                    </div>
                    <div class="card rounded-lg p-6 border border-gray-700">
                        <p class="text-3xl mb-3">🚀</p>
                        <h4 class="font-bold text-white mb-2">Autopilot</h4>
                        <p class="text-sm text-gray-400">System runs. You audit. Full speed, completely audited.</p>
                    </div>
                </div>
            </div>
            
            <!-- Recent Activity -->
            <div class="card rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-bold text-white mb-4">Recent Activity</h3>
                <div class="space-y-3">
                    <div class="flex items-center justify-between py-2 border-b border-gray-700">
                        <div class="flex items-center gap-3">
                            <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
                            <div>
                                <p class="text-sm text-white">847 invoices processed</p>
                                <p class="text-xs text-gray-500">2 hours ago</p>
                            </div>
                        </div>
                        <p class="text-xs text-gray-400">OUTGOING</p>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-gray-700">
                        <div class="flex items-center gap-3">
                            <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                            <div>
                                <p class="text-sm text-white">Pay apps reconciled</p>
                                <p class="text-xs text-gray-500">4 hours ago</p>
                            </div>
                        </div>
                        <p class="text-xs text-gray-400">COLLECTION</p>
                    </div>
                    <div class="flex items-center justify-between py-2">
                        <div class="flex items-center gap-3">
                            <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
                            <div>
                                <p class="text-sm text-white">System metrics refreshed</p>
                                <p class="text-xs text-gray-500">6 hours ago</p>
                            </div>
                        </div>
                        <p class="text-xs text-gray-400">REGENERATING</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Modal for domain views -->
        <div id="modal" class="hidden fixed inset-0 bg-black bg-opacity-75 z-40 flex items-center justify-center">
            <div class="bg-gray-900 rounded-lg max-w-2xl w-full mx-4 p-8 border border-gray-700">
                <div class="flex justify-between items-center mb-6">
                    <h2 id="modalTitle" class="text-2xl font-bold text-white"></h2>
                    <button onclick="document.getElementById('modal').classList.add('hidden')" class="text-gray-400 hover:text-white text-2xl">×</button>
                </div>
                <div id="modalContent" class="text-gray-300"></div>
            </div>
        </div>
        
        <script>
            // Time display
            function updateTime() {
                const now = new Date();
                document.getElementById('timeDisplay').textContent = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' });
            }
            setInterval(updateTime, 1000);
            updateTime();
            
            // Theme switching
            document.getElementById('themeSelect').addEventListener('change', (e) => {
                document.body.className = 'theme-' + e.target.value;
                localStorage.setItem('theme', e.target.value);
            });
            
            const saved = localStorage.getItem('theme') || 'dark';
            document.body.className = 'theme-' + saved;
            document.getElementById('themeSelect').value = saved;
            
            // Domain modal
            function loadDomain(domain) {
                const titles = {
                    'construction': 'Construction Operations',
                    'sales': 'Sales Pipeline',
                    'finance': 'Financial Management'
                };
                
                const content = {
                    'construction': '<p>Projects, pay applications, document flow, inspections, and warranty tracking - all in the circle.</p><p class="mt-4 text-sm text-gray-400">Coming soon: Deep drill-down views for each project phase.</p>',
                    'sales': '<p>Pipeline stages, opportunity tracking, probability weighting, and forecast updates - continuously regenerating.</p><p class="mt-4 text-sm text-gray-400">Coming soon: Territory management and team performance metrics.</p>',
                    'finance': '<p>Accounts payable, accounts receivable, cash flow forecasting, and financial modeling - always audited.</p><p class="mt-4 text-sm text-gray-400">Coming soon: Scenario analysis and what-if modeling.</p>'
                };
                
                document.getElementById('modalTitle').textContent = titles[domain];
                document.getElementById('modalContent').innerHTML = content[domain];
                document.getElementById('modal').classList.remove('hidden');
            }
        </script>
    </body>
    </html>
    """
    
    return html


def generate_settings_page():
    """Settings page - advanced options hidden here"""
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FranklinOps Settings</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; }
        </style>
    </head>
    <body>
        <div class="max-w-3xl mx-auto px-6 py-12">
            <a href="/" class="text-blue-400 hover:underline mb-8 inline-block">&larr; Back to Dashboard</a>
            
            <h1 class="text-3xl font-bold text-white mb-8">Settings & Configuration</h1>
            
            <div class="space-y-8">
                <!-- Control Mode -->
                <section class="border border-gray-700 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-white mb-4">Control Mode</h2>
                    <p class="text-gray-400 mb-4">Choose how much automation you want</p>
                    <div class="space-y-3">
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="shadow" class="w-4 h-4">
                            <div>
                                <p class="text-white font-semibold">Shadow</p>
                                <p class="text-sm text-gray-500">Watch only. No automation.</p>
                            </div>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="assist" checked class="w-4 h-4">
                            <div>
                                <p class="text-white font-semibold">Assist</p>
                                <p class="text-sm text-gray-500">System suggests, you approve. (Recommended)</p>
                            </div>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="autopilot" class="w-4 h-4">
                            <div>
                                <p class="text-white font-semibold">Autopilot</p>
                                <p class="text-sm text-gray-500">Full automation, fully audited.</p>
                            </div>
                        </label>
                    </div>
                </section>
                
                <!-- Modules -->
                <section class="border border-gray-700 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-white mb-4">Active Modules</h2>
                    <div class="space-y-3">
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="checkbox" checked class="w-4 h-4">
                            <span class="text-white">Construction</span>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="checkbox" checked class="w-4 h-4">
                            <span class="text-white">Sales</span>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="checkbox" checked class="w-4 h-4">
                            <span class="text-white">Finance</span>
                        </label>
                    </div>
                </section>
                
                <!-- Data & Privacy -->
                <section class="border border-gray-700 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-white mb-4">Data & Privacy</h2>
                    <div class="space-y-3 text-sm text-gray-400">
                        <p><strong>Data Location:</strong> Fully local. Nothing leaves your system.</p>
                        <p><strong>LLM:</strong> Ollama (Llama 3). Runs locally on your machine.</p>
                        <p><strong>Air-Gapped:</strong> No external API calls. Complete privacy.</p>
                        <p><strong>Audit:</strong> Every action is logged and cryptographically verified.</p>
                    </div>
                </section>
                
                <!-- Advanced (Hidden by Default) -->
                <details class="border border-gray-700 rounded-lg p-6">
                    <summary class="text-lg font-bold text-white cursor-pointer mb-4">Advanced Configuration</summary>
                    <div class="space-y-4 text-sm mt-4">
                        <div>
                            <label class="text-gray-400 mb-2 block">Hub Port</label>
                            <input type="text" value="8844" class="bg-gray-800 text-white px-3 py-2 rounded w-full border border-gray-700">
                        </div>
                        <div>
                            <label class="text-gray-400 mb-2 block">Event Bus</label>
                            <select class="bg-gray-800 text-white px-3 py-2 rounded w-full border border-gray-700">
                                <option>In-Memory (Default)</option>
                                <option>NATS</option>
                                <option>Redis</option>
                            </select>
                        </div>
                        <div>
                            <label class="text-gray-400 mb-2 block">Database</label>
                            <select class="bg-gray-800 text-white px-3 py-2 rounded w-full border border-gray-700">
                                <option>SQLite (Default)</option>
                                <option>PostgreSQL</option>
                                <option>MySQL</option>
                            </select>
                        </div>
                    </div>
                </details>
                
                <!-- Support -->
                <section class="border border-gray-700 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-white mb-4">Help & Support</h2>
                    <div class="space-y-2 text-sm text-gray-400">
                        <p><a href="#" class="text-blue-400 hover:underline">Documentation</a></p>
                        <p><a href="#" class="text-blue-400 hover:underline">API Reference</a></p>
                        <p><a href="#" class="text-blue-400 hover:underline">Technical Architecture (for nerds)</a></p>
                    </div>
                </section>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
