let socket;
let isBotActive = false;
let currentBias = 'TREND';

function init() {
    try {
        connectWebSocket();
        fetchInitialData();
    } catch (e) { console.error("JE Init Error:", e); }
}

function connectWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        socket = new WebSocket(wsUrl);

        socket.onopen = () => console.log("Jewel Elite Sync Active");
        socket.onmessage = (event) => {
            const data = jsonParse(event.data);
            if (data) updateUI(data);
        };
        socket.onclose = () => setTimeout(connectWebSocket, 5000);
    } catch (e) { console.error("WS Error:", e); }
}

function jsonParse(str) { try { return JSON.parse(str); } catch (e) { return null; } }

function updateUI(data) {
    try {
        if (data.demo_balance !== undefined) {
            const el = document.getElementById('balance-display');
            if (el) el.innerText = `$${Number(data.demo_balance).toFixed(2)}`;
        }

        if (data.is_bot_active !== undefined) {
            isBotActive = data.is_bot_active;
            const btn = document.getElementById('master-activation-btn');
            const text = document.getElementById('activation-text');
            const status = document.getElementById('system-status');
            
            if (btn && text && status) {
                if (isBotActive) {
                    btn.classList.add('active');
                    text.innerText = "BOT ACTIVE";
                    status.innerText = "MONITORING";
                    status.style.color = "#10B981";
                } else {
                    btn.classList.remove('active');
                    text.innerText = "ACTIVATE BOT";
                    status.innerText = "STANDBY";
                    status.style.color = "#94A3B8";
                }
            }
        }

        if (data.execution_bias) {
            currentBias = data.execution_bias;
            const bTrend = document.getElementById('bias-trend');
            const bAi = document.getElementById('bias-ai');
            if (bTrend && bAi) {
                bTrend.classList.toggle('active', currentBias === 'TREND');
                bAi.classList.toggle('active', currentBias === 'AI_BILATERAL');
            }
            
            const desc = document.getElementById('bias-desc');
            if (desc) {
                desc.innerText = (currentBias === 'TREND') 
                    ? "*Trend Mode: Only follows institutional flow (EMA200)." 
                    : "*AI Bilateral: DeepSeek determines entries on both sides (Hedged).";
            }
        }

        if (data.signals) renderSignals(data.signals);
        const modeEl = document.getElementById('current-mode');
        if (modeEl && data.strategy_mode) modeEl.innerText = data.strategy_mode;
    } catch (e) { console.error("UI Update Error:", e); }
}

async function toggleBot() {
    isBotActive = !isBotActive;
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_bot_active: isBotActive })
        });
    } catch (e) { console.error("Toggle Error:", e); }
}

async function setBias(bias) {
    currentBias = bias;
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ execution_bias: bias })
        });
    } catch (e) { console.error("Bias Error:", e); }
}

function renderSignals(signals) {
    try {
        const list = document.getElementById('signal-list');
        if (!list) return;
        
        // Ensure signals is an array
        const sigArray = Array.isArray(signals) ? signals : Object.values(signals);
        
        list.innerHTML = sigArray.slice(0,5).map(sig => `
            <div class="signal-row">
                <div>
                    <div style="font-weight: 900; font-size: 0.9rem;">${sig.symbol || '??'}</div>
                    <div style="font-size: 0.6rem; color: #94A3B8;">${sig.pattern || 'Pattern Detected'}</div>
                </div>
                <div class="direction-tag ${sig.direction}">${sig.direction}</div>
            </div>
        `).join('');
    } catch (e) { console.error("Signal Render Error:", e); }
}

function fetchInitialData() {
    fetch('/api/status')
        .then(r => r.json())
        .then(updateUI)
        .catch(e => console.error("Data Fetch Error:", e));
}

window.onload = init;