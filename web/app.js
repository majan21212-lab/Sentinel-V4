console.log("JEWEL ELITE BOOT: v1.0.5");
let socket;
let isBotActive = false;
let currentTerminalTab = 'active';
let activeMarkets = [];
let lastTerminalData = "";
let lastSignalsData = "";
let lastSignalArray = [];
const AVAILABLE_MARKETS = ['EURUSDm', 'GBPUSDm', 'USDJPYm', 'XAUUSDm', 'XAGUSDm', 'BTCUSDm', 'ETHUSDm', 'AAPLm', 'TSLAm', 'US30m', 'NAS100m', 'USOILm'];

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
        renderMarkets(data.active_markets || []);
        if (data.signals) {
            lastSignalArray = Array.isArray(data.signals) ? data.signals : Object.values(data.signals);
            renderSignals(lastSignalArray);
        }
        
    } catch (e) { console.error("UI Update Error:", e); }
}

function renderTerminal(data) {
    const body = document.getElementById('terminal-body');
    if (!body) return;
    
    let trades = [];
    if (currentTerminalTab === 'active') trades = data.active_trades || [];
    else if (currentTerminalTab === 'pending') trades = data.pending_orders || [];
    else trades = data.trade_history || [];

    const dataStr = JSON.stringify(trades);
    if (dataStr === lastTerminalData) return;
    lastTerminalData = dataStr;

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
    
    const filter = document.getElementById('signal-filter');
    const filterVal = filter ? filter.value : 'ALL';
    
    let filtered = signals;
    if(filterVal !== 'ALL') {
        filtered = signals.filter(s => s.direction === filterVal);
    }
    
    const topSignals = filtered.slice(0,5);
    
    const dataStr = JSON.stringify(topSignals);
    if (dataStr === lastSignalsData) return;
    lastSignalsData = dataStr;

    list.innerHTML = topSignals.map(sig => {
        const dirText = sig.direction === 'LONG' ? 'LONG (BUY)' : 'SHORT (SELL)';
        return `
        <div class="signal-row glass">
            <div>
                <div style="font-weight: 800; font-size: 1rem; color: white;">${sig.symbol}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px;">${sig.pattern}</div>
            </div>
            <div class="direction-tag ${sig.direction}">${dirText}</div>
        </div>
    `}).join('');
}

function renderMarkets(active) {
    const container = document.getElementById('market-checkboxes');
    if (!container) return;
    
    if(container.children.length === 0) {
        container.innerHTML = AVAILABLE_MARKETS.map(m => `
            <label style="display: flex; align-items: center; gap: 8px; font-size: 0.8rem;">
                <input type="checkbox" value="${m}" class="market-cb" ${active.includes(m) ? 'checked' : ''}>
                ${m}
            </label>
        `).join('');
    }
}

async function saveMarkets() {
    const checkboxes = document.querySelectorAll('.market-cb');
    const selected = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
    await updateSettings({ active_markets: selected });
}

async function depositFunds() {
    const amt = document.getElementById('deposit-amount').value;
    if(!amt || isNaN(amt)) return;
    await updateSettings({ demo_deposit: parseFloat(amt) });
    document.getElementById('deposit-amount').value = '';
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

function switchBroker(val) {
    console.log("Switching Broker to:", val);
    const creds = document.getElementById('broker-credentials');
    if (!creds) {
        console.error("Credentials div not found!");
        return;
    }
    if (val === 'DEMO') {
        creds.style.display = 'none';
        const depContainer = document.getElementById('demo-deposit-container');
        if(depContainer) depContainer.style.display = 'flex';
        updateSettings({ demo_mode: true });
    } else {
        creds.style.display = 'block';
        const depContainer = document.getElementById('demo-deposit-container');
        if(depContainer) depContainer.style.display = 'none';
        updateSettings({ demo_mode: false, active_broker: val });
    }
}

async function saveCredentials() {
    const broker = document.getElementById('active-broker-select').value;
    const key = document.getElementById('api-key-input').value;
    const secret = document.getElementById('api-secret-input').value;
    
    if (!key || !secret) {
        alert("Please enter both API Key and Secret.");
        return;
    }
    
    const settings = {
        credentials: {
            [broker]: { key, secret }
        }
    };
    
    await updateSettings(settings);
    alert(`${broker} Wallet Linked Successfully!`);
}

function init() {
    connectWebSocket();
    
    const brokerSelect = document.getElementById('active-broker-select');
    if (brokerSelect) {
        brokerSelect.addEventListener('change', (e) => switchBroker(e.target.value));
    }
    
    fetch('/api/status').then(r => r.json()).then(data => {
        updateUI(data);
        if (data.active_broker) {
            const select = document.getElementById('active-broker-select');
            if (select) {
                select.value = data.active_broker;
                if (data.active_broker !== 'DEMO') {
                    document.getElementById('broker-credentials').style.display = 'block';
                    const depContainer = document.getElementById('demo-deposit-container');
                    if(depContainer) depContainer.style.display = 'none';
                } else {
                    const depContainer = document.getElementById('demo-deposit-container');
                    if(depContainer) depContainer.style.display = 'flex';
                }
            }
        }
    });
}

window.onload = init;