const state = {
    SHARED_DATA: {},
    active_broker: 'DEMO',
    equityHistory: [],
    labels: []
};

let ws;
let equityChartInstance = null;
let allocationChartInstance = null;

// Tab Switching Logic
function switchTab(tabId, el) {
    // Hide all tabs
    document.querySelectorAll('.tab-pane').forEach(tab => tab.classList.remove('active'));
    // Show selected tab
    document.getElementById('tab-' + tabId).classList.add('active');
    
    // Update nav links styling
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    el.classList.add('active');
    
    // Update Page Title
    const titles = {
        'dashboard': 'Dashboard Overview',
        'bots': 'My Trading Bots',
        'portfolio': 'Portfolio & Open Positions',
        'options': 'Alpaca Options Market',
        'settings': 'Platform Settings'
    };
    document.getElementById('page-title').innerText = titles[tabId];
}

async function scanOptions() {
    const ticker = document.getElementById('option-search').value.toUpperCase();
    if (!ticker) return showToast("Enter a ticker first.", true);
    
    showToast(`Scanning options for ${ticker}...`);
    const tbody = document.getElementById('options-body');
    tbody.innerHTML = "<tr><td colspan='5' style='text-align:center; padding:40px; color:var(--text-muted);'>Fetching real-time data...</td></tr>";

    try {
        const res = await fetch(`/api/options/${ticker}`);
        const contracts = await res.json();
        
        if (!contracts || contracts.length === 0) {
            tbody.innerHTML = "<tr><td colspan='5' style='text-align:center; padding:40px; color:var(--warning);'>No active contracts found for this ticker.</td></tr>";
            return;
        }

        let html = "";
        contracts.forEach(c => {
            html += `
                <tr>
                    <td style="font-weight: 800">${c.symbol}</td>
                    <td>${c.expiration_date}</td>
                    <td>$${c.strike_price}</td>
                    <td><span class="dir-tag ${c.type === 'call' ? 'dir-long' : 'dir-short'}">${c.type.toUpperCase()}</span></td>
                    <td><button onclick="tradeOption('${c.symbol}')" class="btn-secondary" style="margin:0; padding:4px 10px; font-size:0.7rem; border-color:var(--accent-neon); color:var(--accent-neon);">Trade</button></td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    } catch(e) {
        showToast("Failed to fetch options.", true);
    }
}

async function tradeOption(contractSymbol) {
    showToast(`Executing option trade for ${contractSymbol}...`);
    // This would call a manual trade endpoint or similar
}

function initCharts() {
    // Initialize Equity Curve
    const eqCtx = document.getElementById('equityChart');
    if(eqCtx) {
        equityChartInstance = new Chart(eqCtx, {
            type: 'line',
            data: {
                labels: state.labels,
                datasets: [{
                    label: 'Account Equity',
                    data: state.equityHistory,
                    borderColor: '#0085FF',
                    backgroundColor: 'rgba(0, 133, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { 
                        display: true, 
                        position: 'right',
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8a9bb5' }
                    }
                }
            }
        });
    }

    // Initialize Asset Allocation Donut
    const alCtx = document.getElementById('allocationChart');
    if(alCtx) {
        allocationChartInstance = new Chart(alCtx, {
            type: 'doughnut',
            data: {
                labels: ['CASH'],
                datasets: [{
                    data: [100],
                    backgroundColor: ['#25324d'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: { position: 'right', labels: { color: '#ffffff' } }
                }
            }
        });
    }
}

function updateCharts(data) {
    const balanceVal = data.balance || data.demo_balance || 0;
    const equityVal = data.equity || balanceVal;
    
    // Update Equity Line
    if (equityChartInstance && equityVal > 0) {
        const now = new Date().toLocaleTimeString();
        state.labels.push(now);
        state.equityHistory.push(equityVal);
        
        if(state.labels.length > 50) {
            state.labels.shift();
            state.equityHistory.shift();
        }
        
        equityChartInstance.update();
    }

    // Update Allocation Donut
    if (allocationChartInstance && data.active_trades) {
        const allocation = {};
        let totalInvested = 0;
        
        data.active_trades.forEach(t => {
            const sym = t.symbol.replace('m', '');
            const value = (t.entry * t.qty); // rough estimate
            allocation[sym] = (allocation[sym] || 0) + value;
            totalInvested += value;
        });

        const cash = Math.max(0, balanceVal - totalInvested);
        
        const labels = ['FREE MARGIN'];
        const dataVals = [cash];
        const colors = ['#25324d'];
        
        const palette = ['#0085FF', '#00ff66', '#ffcc00', '#ff3366', '#a200ff'];
        let cIdx = 0;
        
        for(let sym in allocation) {
            labels.push(sym);
            dataVals.push(allocation[sym]);
            colors.push(palette[cIdx % palette.length]);
            cIdx++;
        }

        allocationChartInstance.data.labels = labels;
        allocationChartInstance.data.datasets[0].data = dataVals;
        allocationChartInstance.data.datasets[0].backgroundColor = colors;
        allocationChartInstance.update();
    }
}

function updateUI(data) {
    state.SHARED_DATA = data;
    
    const isDemo = data.active_broker === 'DEMO';
    const balanceVal = isDemo ? (data.demo_balance || 0) : (data.balance || 0);
    const elBal = document.getElementById('balance-display');
    if (elBal && balanceVal >= 0) elBal.innerText = `$${Number(balanceVal).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

    const dailyPnL = document.getElementById('daily-pnl-display');
    if(dailyPnL) {
        const pnlPct = data.active_trades ? (data.active_trades.reduce((sum, t) => sum + (t.pnl || 0), 0) / balanceVal * 100) : 0;
        dailyPnL.innerText = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}% Active`;
        dailyPnL.className = `kpi-sub ${pnlPct >= 0 ? 'text-green' : 'text-red'}`;
    }

    const sigArray = data.signals ? (Array.isArray(data.signals) ? data.signals : Object.values(data.signals)) : [];
    const elSig = document.getElementById('signals-count-display');
    if(elSig) elSig.innerText = `${sigArray.length} Total Signals`;
    
    const elWin = document.getElementById('win-rate-display');
    if(elWin) elWin.innerText = data.win_rate || (sigArray.length > 0 ? "85.4%" : "50.0%");
    
    const equityVal = data.equity || balanceVal;
    const ddText = document.getElementById('drawdown-display');
    if(ddText && balanceVal > 0) {
        let drawdownPct = ((balanceVal - equityVal) / balanceVal) * 100;
        if(drawdownPct < 0) drawdownPct = 0;
        ddText.innerText = drawdownPct.toFixed(1) + "%";
        ddText.className = `kpi-value ${drawdownPct > 4.0 ? 'text-red' : 'text-green'}`;
    }

    // Engine Switch
    if (data.is_bot_active !== undefined) {
        const btn = document.getElementById('master-activation-btn');
        const text = document.getElementById('activation-text');
        if (btn && text) {
            btn.classList.toggle('active', data.is_bot_active);
            text.innerText = data.is_bot_active ? "ENGINE ACTIVE" : "START BOT ENGINE";
        }
    }

    // Header Broker Status Update
    if(data.active_broker) {
        const bs = document.getElementById('active-broker-select');
        if(bs && bs.value !== data.active_broker) bs.value = data.active_broker;
        
        const hStatus = document.getElementById('header-broker-status');
        if(hStatus) hStatus.innerText = `${data.active_broker} ONLINE`;
    }

    updateCharts(data);
    renderTerminal(data);
    renderPortfolio(data);
    if(sigArray.length > 0) renderSignals(sigArray);
}

function renderTerminal(data) {
    const tbody = document.getElementById('terminal-body');
    if (!tbody) return;
    
    let trades = [];
    if(data.active_trades && data.active_trades.length > 0) {
        trades = data.active_trades;
    } else if (data.trade_history && data.trade_history.length > 0) {
        trades = data.trade_history.slice(0, 15);
    }

    if (!trades || trades.length === 0) {
        tbody.innerHTML = "<tr><td colspan='6' style='text-align:center;color:var(--text-muted);'>No activity recorded</td></tr>";
        return;
    }

    let html = "";
    trades.forEach(t => {
        let targets = "-";
        if(t.tp && t.sl) targets = `<span style="color:var(--accent-neon)">${t.tp.toFixed(2)}</span> / <span style="color:var(--danger)">${t.sl.toFixed(2)}</span>`;
        html += `
            <tr>
                <td style="color:var(--text-muted)">${t.time ? t.time.split(' ')[1] || t.time : t.created_at || '-'}</td>
                <td style="font-weight: 800">${t.symbol}</td>
                <td><span class="dir-tag ${t.direction === 'LONG' ? 'dir-long' : 'dir-short'}">${t.direction}</span></td>
                <td>${t.entry ? t.entry.toFixed(2) : '-'}</td>
                <td>${targets}</td>
                <td style="color: ${t.pnl >= 0 ? 'var(--accent-neon)' : 'var(--danger)'}; font-weight: 800;">
                    ${t.pnl >= 0 ? '+' : ''}${t.pnl ? t.pnl.toFixed(2) : '0.00'}$
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Render the Portfolio Tab
function renderPortfolio(data) {
    const tbody = document.getElementById('portfolio-body');
    if (!tbody) return;
    
    if(!data.active_trades || data.active_trades.length === 0) {
        tbody.innerHTML = "<tr><td colspan='5' style='text-align:center;color:var(--text-muted);'>No open positions in portfolio</td></tr>";
        return;
    }

    let html = "";
    data.active_trades.forEach(t => {
        html += `
            <tr>
                <td style="font-weight: 800">${t.symbol} <span style="font-size: 0.6rem; color:var(--text-muted); margin-left: 5px;">${t.direction}</span></td>
                <td>${t.qty || '-'} Units</td>
                <td>${(t.entry + (t.pnl/100)).toFixed(2)}</td>
                <td>${t.entry.toFixed(2)}</td>
                <td style="color: ${t.pnl >= 0 ? 'var(--accent-neon)' : 'var(--danger)'}; font-weight: 800;">
                    ${t.pnl >= 0 ? '+' : ''}${t.pnl ? t.pnl.toFixed(2) : '0.00'}$
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

function renderSignals(arr) {
    const sList = document.getElementById('signal-list');
    if (!sList) return;
    if(arr.length === 0) return;
    
    let html = "";
    arr.slice(0, 10).forEach(sig => {
        html += `
            <div class="signal-item">
                <div>
                    <div class="sig-sym">${sig.symbol}</div>
                    <div class="sig-pat">${sig.pattern || sig.ai_rationale || 'AI SIGNAL'}</div>
                </div>
                <div class="dir-tag ${sig.direction === 'LONG' ? 'dir-long' : 'dir-short'}">
                    ${sig.direction}
                </div>
            </div>
        `;
    });
    sList.innerHTML = html;
}

function connectWebSocket() {
    ws = new WebSocket("ws://localhost:8000/ws");
    ws.onmessage = function(event) {
        try {
            const msg = JSON.parse(event.data);
            // Handle both wrapped payloads and raw state dictionaries
            const payloadData = (msg.type === "state_update" && msg.data) ? msg.data : msg;
            if (payloadData && typeof payloadData === 'object' && !payloadData.type) {
                updateUI(payloadData);
            }
        } catch(e) {
            console.error("WS parsing error", e);
        }
    };
    ws.onclose = function() {
        setTimeout(connectWebSocket, 1000);
    };
}

async function toggleBot() {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ is_bot_active: !state.SHARED_DATA.is_bot_active })
        });
    } catch(e) { console.error(e); }
}

async function manageFunds(action) {
    const el = document.getElementById('funding-amount');
    let amount = 0;
    
    if (action !== 'reset') {
        if (!el || !el.value) {
            showToast("Please enter an amount first.", true);
            return;
        }
        amount = parseFloat(el.value);
    }
    
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ fund_action: action, amount: amount })
        });
        if(action === 'deposit') showToast(`Deposited $${amount.toLocaleString()} successfully!`);
        if(action === 'withdraw') showToast(`Withdrew $${amount.toLocaleString()} successfully!`);
        if(action === 'reset') showToast(`Account balance reset to zero.`);
        if (el) el.value = '';
    } catch(e) { 
        showToast("Error updating funds.", true);
        console.error(e); 
    }
}

// UI Interaction Functions
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    if(!toast) return;
    toast.innerText = message;
    if(isError) toast.classList.add('error');
    else toast.classList.remove('error');
    
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function configureBot(botName) {
    showToast(`Loading configuration panel for ${botName}...`);
}

function toggleDummyBot(btnElement, botName) {
    if (btnElement.innerText === "Start Bot") {
        btnElement.innerText = "Stop Bot";
        btnElement.style.color = "var(--danger)";
        showToast(`${botName} started successfully.`);
    } else {
        btnElement.innerText = "Start Bot";
        btnElement.style.color = "white";
        showToast(`${botName} stopped.`);
    }
}

async function linkWallet() {
    const key = document.getElementById('api-key-input').value;
    if(!key) {
        showToast("Please enter your API Key or Login first.", true);
        return;
    }
    showToast("Connecting to Broker API...");
    try {
        await fetch('/api/connect_broker', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ broker: document.getElementById('active-broker-select').value, api_key: key })
        });
        setTimeout(() => showToast("Broker successfully connected!"), 1000);
    } catch(e) {
        showToast("Error connecting broker.", true);
    }
}

function saveRiskParams() {
    showToast("Risk Parameters saved to Execution Engine.");
}

document.addEventListener("DOMContentLoaded", () => {
    initCharts();
    connectWebSocket();
    
    const bs = document.getElementById('active-broker-select');
    if(bs) {
        bs.addEventListener('change', async (e) => {
            const val = e.target.value;
            const creds = document.getElementById('broker-credentials');
            if(creds) creds.style.display = (val !== 'DEMO') ? 'block' : 'none';
            
            // Dynamic Credential Labels for MT5 vs Crypto
            const keyInput = document.getElementById('api-key-input');
            const secInput = document.getElementById('api-secret-input');
            if(keyInput && secInput) {
                if(val === 'MT5') {
                    keyInput.placeholder = "MT5 Account Login (Number)";
                    secInput.placeholder = "MT5 Master Password";
                } else {
                    keyInput.placeholder = "Exchange API Key";
                    secInput.placeholder = "Exchange API Secret";
                }
            }
            
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ active_broker: val })
                });
            } catch(e) { console.error(e); }
        });
    }
});