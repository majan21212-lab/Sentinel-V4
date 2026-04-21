let socket;
let isBotActive = false;
let currentBias = 'TREND';
let currentTerminalTab = 'active';
let activeMarkets = [];
let currentCategory = 'all';

const MARKET_LIST = {
    forex: [
        { v: "EURUSDm", n: "EUR/USD" }, { v: "GBPUSDm", n: "GBP/USD" },
        { v: "USDJPYm", n: "USD/JPY" }, { v: "AUDUSDm", n: "AUD/USD" },
        { v: "USDCADm", n: "USD/CAD" }, { v: "XAUUSDm", n: "Gold (XAU)" }
    ],
    crypto: [
        { v: "BTCUSDm", n: "Bitcoin" }, { v: "ETHUSDm", n: "Ethereum" },
        { v: "SOLUSDm", n: "Solana" }, { v: "BNBUSDm", n: "Binance Coin" }
    ],
    indices: [
        { v: "US30m", n: "Dow Jones 30" }, { v: "NAS100m", n: "Nasdaq 100" },
        { v: "SP500m", n: "S&P 500" }, { v: "DAX40m", n: "DAX 40" }
    ],
    stocks: [
        { v: "TSLAm", n: "Tesla" }, { v: "AAPLm", n: "Apple" },
        { v: "NVDAm", n: "NVIDIA" }, { v: "AMZNm", n: "Amazon" }
    ]
};

function setMarketCategory(cat) {
    currentCategory = cat;
    document.querySelectorAll('.cat-btn').forEach(b => b.classList.toggle('active', b.innerText.toLowerCase() === cat));
    renderMarketSelect();
}

function renderMarketSelect() {
    const select = document.getElementById('market-select');
    if (!select) return;
    
    let options = [];
    if (currentCategory === 'all') {
        Object.values(MARKET_LIST).forEach(list => options = options.concat(list));
    } else {
        options = MARKET_LIST[currentCategory] || [];
    }
    
    select.innerHTML = options.map(o => `<option value="${o.v}">${o.n} (${o.v})</option>`).join('');
}

async function updateConfig(key, value) {
    const settings = {};
    settings[key] = value;
    await updateSettings(settings);
}

async function setTimeframe(tf) {
    document.querySelectorAll('.tf-btn').forEach(b => b.classList.toggle('active', b.innerText === tf.toLowerCase().replace('m', '') + (tf.includes('M') ? 'm' : 'h')));
    await updateConfig('primary_timeframe', tf);
}

function updateUI(data) {
    try {
        if (data.demo_balance !== undefined) {
            const el = document.getElementById('balance-display');
            if (el) el.innerText = `$${Number(data.demo_balance).toFixed(2)}`;
        }

        if (data.strategy_mode) document.getElementById('strategy-mode-select').value = data.strategy_mode;
        if (data.active_profile) document.getElementById('risk-profile-select').value = data.active_profile;

        if (data.is_bot_active !== undefined) {
            const btn = document.getElementById('master-activation-btn');
            const text = document.getElementById('activation-text');
            if (btn && text) {
                btn.classList.toggle('active', data.is_bot_active);
                text.innerText = data.is_bot_active ? "BOT ACTIVE" : "ACTIVATE BOT";
            }
        }

        if (data.kill_switch !== undefined) {
            const btn = document.getElementById('kill-switch-btn');
            if (btn) btn.classList.toggle('active', data.kill_switch);
        }

        if (data.active_markets) {
            activeMarkets = data.active_markets;
            renderMarketChips();
        }

        renderTerminal(data);
        if (data.signals) renderSignals(data.signals);
        
        const statusEl = document.getElementById('system-status');
        if (statusEl) {
            statusEl.innerText = data.kill_switch ? "EMERGENCY STOP" : (data.is_bot_active ? "MONITORING" : "STANDBY");
            statusEl.style.color = data.kill_switch ? "#EF4444" : (data.is_bot_active ? "#10B981" : "#94A3B8");
        }
    } catch (e) { console.error("UI Update Error:", e); }
}

function renderMarketChips() {
    const container = document.getElementById('market-chips');
    if (!container) return;
    container.innerHTML = activeMarkets.map(m => `
        <div class="chip">
            <span style="opacity: 0.5; font-size: 0.5rem;">BOT</span> ${m} 
            <span class="bot-stop-btn" onclick="removeMarket('${m}')" title="Kill this Bot">STOP</span>
        </div>
    `).join('');
}

function renderTerminal(data) {
    const body = document.getElementById('terminal-body');
    if (!body) return;
    
    let trades = [];
    if (currentTerminalTab === 'active') trades = data.active_trades || [];
    else if (currentTerminalTab === 'pending') trades = data.pending_orders || [];
    else trades = data.trade_history || [];

    body.innerHTML = trades.map(t => `
        <tr>
            <td style="font-weight: bold;">${t.symbol}</td>
            <td class="${t.direction}">${t.direction}</td>
            <td>${t.entry}</td>
            <td>${t.tp}/${t.sl}</td>
            <td style="color: ${t.pnl >= 0 ? '#10B981' : '#EF4444'}">${t.pnl > 0 ? '+' : ''}${t.pnl}</td>
            <td style="opacity: 0.6;">${t.status}</td>
        </tr>
    `).join('');
}

function setTerminalTab(tab) {
    currentTerminalTab = tab;
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(b => b.classList.toggle('active', b.innerText.toLowerCase() === tab));
}

async function addMarket() {
    const select = document.getElementById('market-select');
    const symbol = select.value;
    if (!activeMarkets.includes(symbol)) {
        activeMarkets.push(symbol);
        await updateSettings({ active_markets: activeMarkets });
    }
}

async function removeMarket(symbol) {
    activeMarkets = activeMarkets.filter(m => m !== symbol);
    await updateSettings({ active_markets: activeMarkets });
}

async function toggleKillSwitch() {
    const current = document.getElementById('kill-switch-btn').classList.contains('active');
    await updateSettings({ kill_switch: !current });
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

async function setBias(bias) {
    await updateSettings({ execution_bias: bias });
}

function renderSignals(signals) {
    const list = document.getElementById('signal-list');
    if (!list) return;
    const sigArray = Array.isArray(signals) ? signals : Object.values(signals);
    list.innerHTML = sigArray.slice(0,5).map(sig => `
        <div class="signal-row">
            <div>
                <div style="font-weight: 900; font-size: 0.9rem;">${sig.symbol}</div>
                <div style="font-size: 0.6rem; color: #94A3B8;">${sig.pattern}</div>
            </div>
            <div class="direction-tag ${sig.direction}">${sig.direction}</div>
        </div>
    `).join('');
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    socket.onmessage = (event) => updateUI(JSON.parse(event.data));
    socket.onclose = () => setTimeout(connectWebSocket, 5000);
}

function showConnectModal() { document.getElementById('connect-modal').style.display = 'flex'; }
function hideConnectModal() { document.getElementById('connect-modal').style.display = 'none'; }

async function submitConnection() {
    const broker = document.getElementById('broker-type').value;
    const apiKey = document.getElementById('broker-api-key').value;
    const apiSecret = document.getElementById('broker-api-secret').value;
    
    if (!apiKey) return alert("API Key is required");
    
    try {
        const response = await fetch('/api/connect_broker', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ broker, api_key: apiKey, api_secret: apiSecret })
        });
        const result = await response.json();
        if (result.status === 'success') {
            alert(`Link established with ${broker}!`);
            hideConnectModal();
        } else {
            alert(`Error: ${result.message}`);
        }
    } catch (e) { console.error("Link Error:", e); }
}

function init() {
    renderMarketSelect();
    connectWebSocket();
    fetch('/api/status').then(r => r.json()).then(updateUI);
}


window.onload = init;