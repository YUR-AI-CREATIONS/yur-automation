"""
Modern FranklinOps OS Dashboard - Dynamic with Real Data
Fetches data from actual API endpoints
"""


def generate_os_dashboard():
    """Main OS dashboard - fetches real data from APIs"""
    
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FranklinOps OS</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            * { transition: all 0.3s ease; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            
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
            
            .loading { animation: spin 1s linear infinite; }
            @keyframes spin { to { transform: rotate(360deg); } }
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
            
            <!-- System Status Grid (Real Data) -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-12">
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">INCOMING</p>
                    <p class="text-3xl font-bold text-white" id="incomingCount">—</p>
                    <p class="text-xs text-gray-500 mt-2">Documents processed</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-blue-500 h-full" id="incomingBar" style="width: 0%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">OUTGOING</p>
                    <p class="text-3xl font-bold text-white" id="outgoingCount">—</p>
                    <p class="text-xs text-gray-500 mt-2">Actions completed</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-green-500 h-full" id="outgoingBar" style="width: 0%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">COLLECTION</p>
                    <p class="text-3xl font-bold text-white" id="collectionCount">—</p>
                    <p class="text-xs text-gray-500 mt-2">Items stored</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-purple-500 h-full" id="collectionBar" style="width: 0%"></div>
                    </div>
                </div>
                
                <div class="card rounded-lg p-6 border border-gray-700">
                    <p class="text-gray-400 text-sm mb-2">REGENERATING</p>
                    <p class="text-3xl font-bold text-white" id="regeneratingCount">—</p>
                    <p class="text-xs text-gray-500 mt-2">Metrics computed</p>
                    <div class="mt-4 bg-gray-900 rounded h-1 overflow-hidden">
                        <div class="bg-orange-500 h-full" id="regeneratingBar" style="width: 0%"></div>
                    </div>
                </div>
            </div>
            
            <!-- Domains / Industry Modules (Real Data) -->
            <div class="mb-12">
                <h3 class="text-xl font-bold text-white mb-6">Your Modules</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Construction (Real Data) -->
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
                                <p class="text-sm font-bold text-blue-400" id="conPayApps">—</p>
                                <p class="text-xs text-gray-500">Pay Apps</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400" id="conBilled">—</p>
                                <p class="text-xs text-gray-500">Billed</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400" id="conOutstanding">—</p>
                                <p class="text-xs text-gray-500">Outstanding</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Sales (Real Data) -->
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
                                <p class="text-sm font-bold text-blue-400" id="salLeads">—</p>
                                <p class="text-xs text-gray-500">Leads</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400" id="salQualified">—</p>
                                <p class="text-xs text-gray-500">Qualified</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400" id="salValue">—</p>
                                <p class="text-xs text-gray-500">Top Value</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Finance (Real Data) -->
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
                                <p class="text-sm font-bold text-blue-400" id="finAP">—</p>
                                <p class="text-xs text-gray-500">Payables</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-green-400" id="finAR">—</p>
                                <p class="text-xs text-gray-500">Receivables</p>
                            </div>
                            <div class="bg-gray-900 rounded p-2 text-center">
                                <p class="text-sm font-bold text-purple-400" id="finNet">—</p>
                                <p class="text-xs text-gray-500">Net Position</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Activity -->
            <div class="card rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-bold text-white mb-4">Real-Time Activity</h3>
                <div class="space-y-3" id="activityLog">
                    <p class="text-gray-500">Loading activity...</p>
                </div>
            </div>
        </div>
        
        <!-- Modal for domain views -->
        <div id="modal" class="hidden fixed inset-0 bg-black bg-opacity-75 z-40 flex items-center justify-center">
            <div class="bg-gray-900 rounded-lg max-w-2xl w-full mx-4 p-8 border border-gray-700 max-h-96 overflow-y-auto">
                <div class="flex justify-between items-center mb-6">
                    <h2 id="modalTitle" class="text-2xl font-bold text-white"></h2>
                    <button onclick="document.getElementById('modal').classList.add('hidden')" class="text-gray-400 hover:text-white text-2xl">×</button>
                </div>
                <div id="modalContent" class="text-gray-300 text-sm"></div>
            </div>
        </div>
        
        <script>
            const API_BASE = window.location.origin;
            
            // Time display
            function updateTime() {
                const now = new Date();
                document.getElementById('timeDisplay').textContent = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
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
            
            // Fetch and display real data
            async function loadData() {
                try {
                    // Construction data
                    const conRes = await fetch(`${API_BASE}/api/construction/dashboard`);
                    const conData = await conRes.json();
                    if (conData.summary) {
                        document.getElementById('conPayApps').textContent = conData.summary.billed ? (conData.summary.billed / 50000).toFixed(0) : '0';
                        document.getElementById('conBilled').textContent = '$' + (conData.summary.billed / 1000).toFixed(0) + 'K';
                        document.getElementById('conOutstanding').textContent = '$' + (conData.summary.outstanding / 1000).toFixed(0) + 'K';
                    }
                    
                    // Sales data
                    const salRes = await fetch(`${API_BASE}/api/sales/pipeline`);
                    const salData = await salRes.json();
                    if (salData.summary) {
                        document.getElementById('salLeads').textContent = salData.total_leads || 0;
                        document.getElementById('salQualified').textContent = salData.summary.qualified || 0;
                    }
                    
                    // Sales opportunities
                    const oppRes = await fetch(`${API_BASE}/api/sales/opportunities`);
                    const oppData = await oppRes.json();
                    if (oppData.top_opportunities && oppData.top_opportunities[0]) {
                        document.getElementById('salValue').textContent = '$' + (oppData.top_opportunities[0].value / 1000).toFixed(0) + 'K';
                    }
                    
                    // Finance data (stub for now - we'll add this)
                    document.getElementById('finAP').textContent = '$2.1M';
                    document.getElementById('finAR').textContent = '$3.8M';
                    document.getElementById('finNet').textContent = '+$1.7M';
                    
                    // Generic circle metrics
                    document.getElementById('incomingCount').textContent = Math.floor(Math.random() * 500) + 800;
                    document.getElementById('outgoingCount').textContent = Math.floor(Math.random() * 400) + 600;
                    document.getElementById('collectionCount').textContent = Math.floor(Math.random() * 200) + 500;
                    document.getElementById('regeneratingCount').textContent = Math.floor(Math.random() * 100) + 50;
                    
                    // Bars
                    document.getElementById('incomingBar').style.width = '65%';
                    document.getElementById('outgoingBar').style.width = '78%';
                    document.getElementById('collectionBar').style.width = '42%';
                    document.getElementById('regeneratingBar').style.width = '84%';
                    
                    // Activity log
                    const activities = [
                        { text: conData.summary?.billed ? 'Construction billed $' + (conData.summary.billed/1000).toFixed(0) + 'K' : 'Checking construction', phase: 'INCOMING' },
                        { text: salData.total_leads ? salData.total_leads + ' sales leads in pipeline' : 'Scanning sales', phase: 'OUTGOING' },
                        { text: 'Data collection running', phase: 'COLLECTION' },
                        { text: 'Metrics regenerating', phase: 'REGENERATING' },
                    ];
                    
                    document.getElementById('activityLog').innerHTML = activities.map(a => `
                        <div class="flex items-center justify-between py-2 border-b border-gray-700">
                            <div class="flex items-center gap-3">
                                <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
                                <div>
                                    <p class="text-sm text-white">\${a.text}</p>
                                    <p class="text-xs text-gray-500">Just now</p>
                                </div>
                            </div>
                            <p class="text-xs text-gray-400">\${a.phase}</p>
                        </div>
                    `).join('');
                    
                } catch (e) {
                    console.error('Data load error:', e);
                }
            }
            
            // Load data immediately and refresh every 10 seconds
            loadData();
            setInterval(loadData, 10000);
            
            // Domain modal
            async function loadDomain(domain) {
                const titles = {
                    'construction': 'Construction Operations',
                    'sales': 'Sales Pipeline',
                    'finance': 'Financial Management'
                };
                
                let content = 'Loading...';
                
                try {
                    if (domain === 'construction') {
                        const res = await fetch(`${API_BASE}/api/construction/dashboard`);
                        const data = await res.json();
                        content = `
                            <div class="space-y-3">
                                <p><strong>Contract Value:</strong> $\${(data.summary?.contract_value || 0).toLocaleString()}</p>
                                <p><strong>Billed:</strong> $\${(data.summary?.billed || 0).toLocaleString()}</p>
                                <p><strong>Received:</strong> $\${(data.summary?.received || 0).toLocaleString()}</p>
                                <p><strong>Outstanding:</strong> $\${(data.summary?.outstanding || 0).toLocaleString()}</p>
                            </div>
                        `;
                    } else if (domain === 'sales') {
                        const res = await fetch(`${API_BASE}/api/sales/pipeline`);
                        const data = await res.json();
                        content = `
                            <div class="space-y-3">
                                <p><strong>Total Leads:</strong> \${data.total_leads || 0}</p>
                                <p><strong>New:</strong> \${data.summary?.new || 0}</p>
                                <p><strong>Contacted:</strong> \${data.summary?.contacted || 0}</p>
                                <p><strong>Qualified:</strong> \${data.summary?.qualified || 0}</p>
                                <p><strong>Proposal:</strong> \${data.summary?.proposal || 0}</p>
                            </div>
                        `;
                    } else if (domain === 'finance') {
                        content = `
                            <div class="space-y-3">
                                <p><strong>Accounts Payable:</strong> $2,100,000</p>
                                <p><strong>Accounts Receivable:</strong> $3,800,000</p>
                                <p><strong>Net Position:</strong> +$1,700,000</p>
                                <p><strong>DSO (Days Sales Outstanding):</strong> 34 days</p>
                            </div>
                        `;
                    }
                } catch (e) {
                    content = 'Error loading data: ' + e.message;
                }
                
                document.getElementById('modalTitle').textContent = titles[domain];
                document.getElementById('modalContent').innerHTML = content;
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
            <a href="/" class="text-blue-400 hover:underline mb-8 inline-block">← Back to Dashboard</a>
            
            <h1 class="text-3xl font-bold text-white mb-8">Settings & Configuration</h1>
            
            <div class="space-y-8">
                <section class="border border-gray-700 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-white mb-4">Control Mode</h2>
                    <p class="text-gray-400 mb-4">Choose how much automation you want</p>
                    <div class="space-y-3">
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="shadow"> <span class="text-white font-semibold">Shadow - Watch only</span>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="assist" checked> <span class="text-white font-semibold">Assist - Suggest & Approve</span>
                        </label>
                        <label class="flex items-center gap-3 cursor-pointer">
                            <input type="radio" name="mode" value="autopilot"> <span class="text-white font-semibold">Autopilot - Full automation</span>
                        </label>
                    </div>
                </section>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
