let socket;
let isBotActive = false;
let currentTerminalTab = 'active';
let activeMarkets = [];

function updateUI(data) {
    try {
        if (data.demo_balance !== undefined || data.balance !== undefined) {
            const val = data.balance || data.demo_balance;
            const el = document.getElementById('balance-display');
            if (el) el.innerText = `$${Number(val).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        }
        
        if (data.equity !== undefined) {
            const el = document.getElementById('equity-display');
            if (el) el.innerText = `Free margin: $${Number(data.equity).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        }

        if (data.is_bot_active !== undefined) {
            const btn = document.getElementById('master-activation-btn');
            const text = document.getElementById('activation-text');
            if (btn && text) {
                btn.classList.toggle('active', data.is_bot_active);
                text.innerText = data.is_bot_active ? "MONITORING ACTIVE" : "INVOKE CORE ENGINE";
            }
        }

        renderTerminal(data);
        if (data.signals) renderSignals(data.signals);
        
    } catch (e) { console.error("UI Update Error:", e); }
}

function renderTerminal(data) {
    const body = document.getElementById('terminal-body');
    if (!body) return;
    
    let trades = [];
    if (currentTerminalTab === 'active') trades = data.active_trades || [];
    else if (currentTerminalTab === 'pending') trades = data.pending_orders || [];
    else trades = data.trade_history || [];

    body.innerHTML = trades.length ? trades.map(t => `
        <tr>
            <td style="font-weight: 800; font-size: 0.9rem;">${t.symbol}</td>
            <td><span class="direction-tag ${t.direction}">${t.direction}</span></td>
            <td style="color: var(--text-secondary); font-weight: 600;">${t.entry}</td>
            <td style="color: var(--text-secondary);">${t.tp}/${t.sl}</td>
            <td style="color: ${t.pnl >= 0 ? 'var(--success)' : 'var(--error)'}; font-weight: 800;">
                ${t.pnl > 0 ? '+' : ''}${t.pnl}$
            </td>
            <td><span class="status-tag active">${t.status}</span></td>
        </tr>
    `).join('') : `<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--text-secondary);">No ${currentTerminalTab} trades detected</td></tr>`;
}

function setTerminalTab(tab) {
    currentTerminalTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.innerText.toLowerCase().includes(tab)));
    fetch('/api/status').then(r => r.json()).then(updateUI);
}

function renderSignals(signals) {
    const list = document.getElementById('signal-list');
    if (!list) return;
    const sigArray = Array.isArray(signals) ? signals : Object.values(signals);
    list.innerHTML = sigArray.slice(0,5).map(sig => `
        <div class="signal-row glass">
            <div>
                <div style="font-weight: 800; font-size: 1rem; color: white;">${sig.symbol}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px;">${sig.pattern}</div>
            </div>
            <div class="direction-tag ${sig.direction}">${sig.direction}</div>
        </div>
    `).join('');
}

async function updateSettings(settings) {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    } catch (e) { console.error("Update Error:", e); }
}

async function toggleBot() {
    const current = document.getElementById('master-activation-btn').classList.contains('active');
    await updateSettings({ is_bot_active: !current });
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    socket.onmessage = (event) => updateUI(JSON.parse(event.data));
    socket.onclose = () => setTimeout(connectWebSocket, 5000);
}

function init() {
    connectWebSocket();
    fetch('/api/status').then(r => r.json()).then(updateUI);
}

window.onload = init;