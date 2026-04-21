let socket;
let currentStrategy = 'PATTERN';

function init() {
    connectWebSocket();
    fetchInitialData();
    setupEventListeners();
}

function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        logToConsole("G.A.B Cloud Sync Active");
        document.getElementById('connection-status').classList.remove('offline');
    };

    socket.onmessage = (event) => {
        const data = jsonParse(event.data);
        if (data) updateUI(data);
    };

    socket.onclose = () => {
        setTimeout(connectWebSocket, 5000);
    };
}

function jsonParse(str) {
    try { return JSON.parse(str); } catch (e) { return null; }
}

function updateUI(data) {
    if (data.prices) {
        for (const [symbol, price] of Object.entries(data.prices)) {
            document.getElementById('live-price').innerText = `$${price.toFixed(2)}`;
            document.getElementById('active-symbol').innerText = symbol;
        }
    }

    if (data.strategy_mode) {
        currentStrategy = data.strategy_mode;
        document.getElementById('current-mode').innerText = currentStrategy;
        updateTabSync(currentStrategy);
    }

    if (data.signals) {
        renderSignals(data.signals);
    }
}

async function setStrategy(mode) {
    logToConsole(`Mode Switch: ${mode}`);
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy_mode: mode })
        });
    } catch (e) {}
}

function updateTabSync(mode) {
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
        btn.classList.remove('active');
        if (btn.innerText === mode) btn.classList.add('active');
    });
}

function renderSignals(signals) {
    const list = document.getElementById('signal-list');
    list.innerHTML = signals.map(sig => `
        <div class="signal-row">
            <div>
                <div style="font-weight: 900;">${sig.symbol}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary);">${sig.created_at}</div>
            </div>
            <div class="direction-tag ${sig.direction}">${sig.direction}</div>
        </div>
    `).join('');
}

function logToConsole(msg) {
    const console = document.getElementById('diagnostic-console');
    const time = new Date().toLocaleTimeString();
    console.innerHTML += `<div>[${time}] ${msg}</div>`;
    console.scrollTop = console.scrollHeight;
}

function fetchInitialData() {
    fetch('/api/status').then(r => r.json()).then(updateUI);
}

function setupEventListeners() {
    document.getElementById('auto-trade-toggle').onchange = (e) => {
        updateSetting('auto_trade', e.target.checked);
    };
    document.getElementById('demo-toggle').onchange = (e) => {
        updateSetting('demo_mode', e.target.checked);
    };
}

async function updateSetting(key, value) {
    await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value })
    });
}

window.onload = init;