// Advanced Diagnostics for Mobile Connectivity
function logToUI(msg, isError = true) {
    console.log(`[UI LOG] ${msg}`);
    const consoleEl = document.getElementById('debug-console');
    if (consoleEl) {
        consoleEl.style.display = 'block';
        const line = document.createElement('div');
        line.style.color = isError ? '#FF3B30' : '#34C759';
        line.innerHTML = `[${new Date().toLocaleTimeString()}] ${msg}`;
        consoleEl.appendChild(line);
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }
}

window.onerror = function(message, source, lineno, colno, error) {
    logToUI(`CRITICAL ERROR: ${message} (Line: ${lineno})`);
    return false;
};

let charts = {};
const series = {};

// Initialize Patterns Engine Symbols
const symbols = ['XAUUSDm', 'BTCUSDm'];

function initCharts() {
    try {
        if (typeof LightweightCharts === 'undefined') {
            logToUI("CHART ERROR: Library not loaded (Blocked by VPN?)");
            return;
        }
        
        symbols.forEach(symbol => {
        const container = document.getElementById(`chart-${symbol}`);
        if (!container) return;

        const chart = LightweightCharts.createChart(container, {
            layout: {
                backgroundColor: 'transparent',
                textColor: '#8E8E93',
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.05)' },
                horzLines: { color: 'rgba(255,255,255,0.05)' },
            },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
            timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true },
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: '#34C759',
            downColor: '#FF3B30',
            borderVisible: false,
            wickUpColor: '#34C759',
            wickDownColor: '#FF3B30',
        });

        charts[symbol] = chart;
        series[symbol] = candleSeries;
        
        // Resize listener
        window.addEventListener('resize', () => {
            chart.applyOptions({ width: container.clientWidth });
        });
    });
    } catch (e) {
        logToUI(`CHART INIT ERROR: ${e.message}`);
        console.error("Chart initialization failed", e);
    }
}

function updateSignals() {
    fetch('/api/signals')
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('signal-list');
            if (!data.length) return;
            
            list.innerHTML = data.map(sig => `
                <div class="signal-item">
                    <div class="signal-info">
                        <h3>${sig.symbol}</h3>
                        <p>${sig.created_at} | ${sig.timeframe}</p>
                    </div>
                    <div class="signal-side ${sig.direction}">
                        ${sig.direction}
                    </div>
                </div>
            `).join('');
        });
}

function connectWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        logToUI("WebSocket Connected Successfully", false);
        document.getElementById('status-badge').className = 'status-badge online';
        document.getElementById('status-badge').innerText = 'ONLINE';
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            processDashboardData(data);
        } catch (e) {
            console.error("Failed to parse WS data", e);
        }
    };

    ws.onclose = () => {
        logToUI("WebSocket Disconnected - Retrying...");
        document.getElementById('status-badge').className = 'status-badge offline';
        document.getElementById('status-badge').innerText = 'OFFLINE (Retrying...)';
        
        // Fallback polling if WS closed
        setTimeout(pollStatus, 5000);
        // Reconnect WS after 10s
        setTimeout(connectWS, 10000);
    };
    
    ws.onerror = (e) => {
        logToUI(`WebSocket Data Error: ${e.message || 'Check Firewall'}`);
        console.error("WebSocket error:", e);
    };
}

async function pollStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        processDashboardData(data);
        
        // Update status badge for polling mode
        const badge = document.getElementById('status-badge');
        if (badge.innerText.includes('OFFLINE')) {
            badge.innerText = 'ONLINE (Polling)';
            badge.className = 'status-badge online';
        }
    } catch (e) {
        logToUI(`Polling Failed: ${e.message}`);
        console.error("Polling failed", e);
    }
}

function processDashboardData(data) {
    // Update Status Badge if status is in data
    const statusBadge = document.getElementById('status-badge');
    if (data.status && !statusBadge.innerText.includes('Polling')) {
        statusBadge.innerText = data.status;
        statusBadge.className = `status-badge ${data.status.toLowerCase()}`;
    }

    // Update Auto-Trade Toggle
    if (data.hasOwnProperty('auto_trade')) {
        const toggle = document.getElementById('auto-trade-toggle');
        if (toggle) toggle.checked = data.auto_trade;
    }

    // Sync Risk Configuration UI
    if (data.risk_config) {
        syncRiskUI(data.risk_config);
    }

    // Update Prices
    if (data.prices) {
        Object.keys(data.prices).forEach(symbol => {
            const el = document.getElementById(`price-${symbol}`);
            if (el) {
                const newPrice = data.prices[symbol];
                const oldPrice = parseFloat(el.innerText);
                el.innerText = typeof newPrice === 'number' ? newPrice.toFixed(2) : newPrice;
                
                // Pulsing effect
                if (newPrice > oldPrice) {
                    el.classList.add('price-up');
                    setTimeout(() => el.classList.remove('price-up'), 500);
                } else if (newPrice < oldPrice) {
                    el.classList.add('price-down');
                    setTimeout(() => el.classList.remove('price-down'), 500);
                }
            }
        });
    }
}

// Start everything
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connectWS();
    updateSignals();
    setInterval(updateSignals, 10000);
});

function toggleAutoTrade(el) {
    const status = el.checked;
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_trade: status })
    })
    .then(res => res.json())
    .then(data => {
        console.log("Auto-Trade set to:", data.auto_trade);
    });
}

function showTab(tabId) {
    // Switch active tab content
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');

    // Switch active nav icon
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.getElementById(`nav-${tabId}`).classList.add('active');
}

function syncRiskUI(config) {
    if (!config || !config.risk_per_asset) return;

    // Update Daily Loss
    const dlInput = document.getElementById('input-daily-loss');
    const dlLabel = document.getElementById('label-daily-loss');
    if (dlInput && !dlInput.isSameNode(document.activeElement)) {
        dlInput.value = config.max_daily_loss_pct || 2.0;
        dlLabel.innerText = (config.max_daily_loss_pct || 2.0) + '%';
    }

    // Update Asset Risks
    ['XAUUSDm', 'BTCUSDm'].forEach(asset => {
        const input = document.getElementById('input-risk-' + asset);
        const label = document.getElementById('label-risk-' + asset);
        if (input && !input.isSameNode(document.activeElement)) {
            const val = config.risk_per_asset[asset] || config.risk_per_asset['DEFAULT'] || 1.0;
            input.value = val;
            label.innerText = val + '%';
        }
    });
}

function updateRiskSettings() {
    const dailyLoss = document.getElementById('input-daily-loss').value;
    const goldRisk = document.getElementById('input-risk-XAUUSDm').value;
    const btcRisk = document.getElementById('input-risk-BTCUSDm').value;

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            max_daily_loss: parseFloat(dailyLoss),
            asset: 'XAUUSDm',
            risk_pct: parseFloat(goldRisk)
        })
    }).then(() => {
        // Send second request for BTC (simplified for this demo)
        fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asset: 'BTCUSDm',
                risk_pct: parseFloat(btcRisk)
            })
        });
    });

    // Immediate UI update for smooth sliding
    document.getElementById('label-daily-loss').innerText = dailyLoss + '%';
    document.getElementById('label-risk-XAUUSDm').innerText = goldRisk + '%';
    document.getElementById('label-risk-BTCUSDm').innerText = btcRisk + '%';
}

async function updateAnalytics() {
    try {
        const response = await fetch('/api/analytics');
        const data = await response.json();
        renderAnalytics(data);
    } catch (e) {
        console.error("Failed to update analytics", e);
    }
}

function renderAnalytics(data) {
    const container = document.getElementById('analytics-container');
    if (!container) return;
    
    if (Object.keys(data).length === 0) {
        container.innerHTML = '<div class="empty-state">No historical results yet...</div>';
        return;
    }
    
    let html = '';
    for (const [pattern, winrate] of Object.entries(data)) {
        let colorClass = 'mid';
        if (winrate >= 60) colorClass = 'high';
        if (winrate < 45) colorClass = 'low';
        
        html += `
            <div class="stat-row">
                <span class="stat-name">${pattern.replace(/_/g, ' ')}</span>
                <span class="stat-value ${colorClass}">${winrate}%</span>
            </div>
        `;
    }
    container.innerHTML = html;
}

async function updateSettings(type, value, asset = 'DEFAULT') {
    const payload = {};
    if (type === 'auto_trade') payload.auto_trade = value;
    if (type === 'risk_pct') {
        payload.risk_pct = value;
        payload.asset = asset;
    }
    if (type === 'max_daily_loss') payload.max_daily_loss = value;

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.status === 'success') {
            console.log("Settings updated successfully");
        }
    } catch (e) {
        console.error("Failed to update settings", e);
    }
}

async function toggleAutoTrade(enabled) {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ auto_trade: enabled })
        });
    } catch (e) {
        console.error("Failed to toggle auto-trade:", e);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connectWS();
    updateSignals();
    updateAnalytics();
    
    // Refresh signals every minute
    setInterval(updateSignals, 60000);
    // Refresh analytics every 30 seconds
    setInterval(updateAnalytics, 30000);
    
    // Auto-trade toggle listener
    const toggle = document.getElementById('auto-trade-toggle');
    if (toggle) {
        toggle.addEventListener('change', (e) => toggleAutoTrade(e.target.checked));
    }
});

function closeAll() {
    if (confirm("Close all active positions?")) {
        fetch('/api/trade', { method: 'POST', body: JSON.stringify({action: 'close_all'}) });
    }
}
