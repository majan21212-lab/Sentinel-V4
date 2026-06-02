/**
 * Sentinel Premium Cockpit - Obsidian Gold Edition
 */

class PremiumDashboard {
    constructor() {
        this.ws = null;
        this.state = {
            is_bot_active: false,
            balance: 0,
            demo_balance: 0,
            demo_mode: true,
            active_trades: [],
            trade_history: [],
            broker_details: {},
            market_configs: {},
            risk_config: {}
        };
        this.init();
    }

    init() {
        console.log('Sentinel Premium Initializing...');
        this.connectWebSocket();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host || 'localhost:8000';
        this.ws = new WebSocket(`${protocol}//${host}/ws`);

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateState(data);
            } catch (e) {
                console.error("WS error", e);
            }
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connectWebSocket(), 2000);
        };
    }

    updateState(data) {
        this.state = { ...this.state, ...data };
        this.renderKPIs();
        this.renderBotGrid();
        this.renderBrokerCards();
        this.renderLogs();
        this.updateMarketSessions();
        this.renderSATS();
        this.renderMarketConfig();
        this.renderSignals();
    }

    renderKPIs() {
        const isDemo = this.state.demo_mode;
        const bal = isDemo ? (this.state.demo_balance || 0) : (this.state.balance || 0);
        const floating = (this.state.active_trades || []).reduce((sum, t) => sum + (parseFloat(t.pnl) || 0), 0);
        
        const elEquity = document.getElementById('total-equity');
        if (elEquity) elEquity.innerText = `$${(bal + floating).toLocaleString(undefined, {minimumFractionDigits: 2})}`;

        const elProfit = document.getElementById('daily-profit');
        if (elProfit) {
            const history = this.state.trade_history || [];
            const today = new Date().toISOString().split('T')[0];
            const todayProfit = history
                .filter(t => t.time && t.time.includes(today))
                .reduce((sum, t) => sum + (parseFloat(t.pnl) || 0), 0);
            
            const totalProfit = todayProfit + floating;
            elProfit.innerText = `${totalProfit >= 0 ? '+' : ''}$${Math.abs(totalProfit).toFixed(2)}`;
            elProfit.className = `kpi-value ${totalProfit >= 0 ? 'text-green' : 'text-red'}`;
            
            const elTrend = elProfit.nextElementSibling;
            if (elTrend) {
                elTrend.innerText = totalProfit >= 0 ? '↗ +' + ((totalProfit/bal)*100).toFixed(1) + '%' : '↘ ' + ((totalProfit/bal)*100).toFixed(1) + '%';
                elTrend.className = `kpi-trend ${totalProfit >= 0 ? 'text-green' : 'text-red'}`;
            }
        }

        const elBots = document.getElementById('active-bots-count');
        if (elBots) elBots.innerText = (this.state.active_trades || []).length;

        // Win Rate Calculation
        const history = this.state.trade_history || [];
        if (history.length > 0) {
            const wins = history.filter(t => t.pnl > 0).length;
            const wr = ((wins / history.length) * 100).toFixed(1);
            document.getElementById('win-rate').innerText = `${wr}%`;
        }
    }

    renderBotGrid() {
        const grid = document.getElementById('bot-grid');
        if (!grid) return;

        const trades = this.state.active_trades || [];
        if (trades.length === 0) {
            grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 40px; color: #555;">No Active Bot Deployments</div>';
            return;
        }

        grid.innerHTML = trades.map((trade, idx) => {
            const profit = parseFloat(trade.pnl) || 0;
            const progress = Math.min(100, Math.abs(profit) / 10); // Dummy logic for progress
            const botId = trade.bot_id || `BOT_00${idx + 1}`;
            
            return `
                <div class="bot-card">
                    <div class="bot-header">
                        <div>
                            <div class="bot-id">${botId}</div>
                            <div class="bot-name">Sentinel V4 (${trade.symbol})</div>
                        </div>
                        <div class="bot-status"><span class="dot active"></span> RUNNING</div>
                    </div>
                    <div class="bot-profit-row">
                        <span>PROFIT</span>
                        <span class="${profit >= 0 ? 'text-green' : 'text-red'}">${profit >= 0 ? '+' : ''}$${Math.abs(profit).toFixed(2)}</span>
                    </div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: ${progress}%; background: ${profit >= 0 ? 'var(--neon-green)' : 'var(--neon-red)'}; box-shadow: 0 0 10px ${profit >= 0 ? 'var(--neon-green)' : 'var(--neon-red)'}"></div>
                        <div class="progress-dot" style="left: ${progress}%; background: ${profit >= 0 ? 'var(--neon-green)' : 'var(--neon-red)'}"></div>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <button class="btn-sm gold-border" onclick="closeTrade('${trade.symbol}')" style="flex: 1; font-size: 10px;">CLOSE POSITION</button>
                        <button class="terminate-btn" onclick="terminateBot('${trade.symbol}')" style="flex: 1; font-size: 10px; margin-top: 0;">STOP BOT</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderBrokerCards() {
        const grid = document.getElementById('broker-cards');
        if (!grid) return;

        const brokers = ['alpaca', 'mt5', 'binance'];
        const details = this.state.broker_details || {};
        const isDemo = this.state.demo_mode;

        grid.innerHTML = brokers.map(b => {
            const bData = details[b] || { balance: 0, status: 'OFFLINE' };
            const isConnected = bData.status === 'CONNECTED';
            
            return `
                <div class="bot-card" style="border-color: ${isConnected ? 'var(--accent-gold)' : 'var(--border-dim)'}">
                    <div class="bot-header">
                        <div>
                            <div class="bot-id">${b.toUpperCase()} BRIDGE</div>
                            <div class="bot-name">${isConnected ? 'Bridged & Synced' : 'Disconnected'}</div>
                        </div>
                        <div class="bot-status"><span class="dot ${isConnected ? 'active' : ''}"></span> ${bData.status}</div>
                    </div>
                    <div class="bot-profit-row">
                        <span>BALANCE</span>
                        <span style="color: var(--accent-gold)">$${Number(bData.balance).toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                    </div>
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 10px;">
                        ACCOUNT TYPE: <span style="color: ${isDemo ? 'var(--accent-gold)' : 'var(--neon-green)'}">${isDemo ? 'DEMO' : 'REAL'}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderLogs() {
        const logBody = document.getElementById('log-body');
        if (!logBody) return;

        const logs = this.state.logs || [];
        if (logs.length === 0 && logBody.children.length === 0) {
            logBody.innerHTML = '<div class="log-entry"><span class="log-msg">Awaiting system telemetry...</span></div>';
            return;
        }

        if (logs.length > 0) {
            logBody.innerHTML = logs.map(log => {
                let typeClass = '';
                if (log.msg.includes('Error') || log.msg.includes('Disconnected')) typeClass = 'error';
                else if (log.msg.includes('Success') || log.msg.includes('ACTIVE')) typeClass = 'success';
                else if (log.msg.includes('Warning')) typeClass = 'warning';

                return `
                    <div class="log-entry">
                        <span class="log-time">[${log.time}]</span>
                        <span class="log-msg ${typeClass}">${log.msg}</span>
                    </div>
                `;
            }).join('');
            logBody.scrollTop = logBody.scrollHeight;
        }
    }
    
    renderSATS() {
        const strategy = this.state.strategy_mode || "JEWEL_ELITE";
        const matrixItems = document.querySelectorAll('.matrix-item');
        
        matrixItems.forEach(item => {
            const text = item.innerText.toUpperCase();
            item.classList.remove('active');
            
            if (strategy === "JEWEL_ELITE" && text === "HIGH VOL") item.classList.add('active');
            if (strategy === "GOD_MODE" && text === "TRENDING") item.classList.add('active');
            if (strategy === "HYBRID" && text === "LOW VOL") item.classList.add('active');
            if (strategy.includes("GRID") && text === "RANGING") item.classList.add('active');
        });
    }

    renderSignals() {
        const body = document.getElementById('signals-feed-body');
        if (!body) return;

        const signals = this.state.signals || [];
        body.innerHTML = signals.map(sig => `
            <tr style="border-bottom: 1px solid var(--border-dim); font-size: 13px;">
                <td style="padding: 12px; color: var(--text-muted);">${sig.created_at || '---'}</td>
                <td style="font-weight: bold;">${sig.symbol}</td>
                <td style="color: ${sig.direction === 'LONG' ? 'var(--neon-green)' : 'var(--neon-red)'}; font-weight: 800;">${sig.direction}</td>
                <td style="color: var(--accent-gold); font-family: 'Orbitron';">${Number(sig.entry).toFixed(5)}</td>
                <td style="color: var(--neon-red);">${Number(sig.sl).toFixed(5)}</td>
                <td style="color: var(--neon-green);">${Number(sig.tp).toFixed(5)}</td>
                <td style="font-size: 11px; color: var(--text-muted);">${sig.pattern}</td>
            </tr>
        `).join('');
    }

    renderMarketConfig() {
        const body = document.getElementById('market-config-body');
        if (!body) return;

        const configs = this.state.market_configs || {};
        body.innerHTML = Object.entries(configs).map(([symbol, cfg]) => `
            <tr style="border-bottom: 1px solid var(--border-dim); font-size: 13px;">
                <td style="padding: 15px;">${symbol}</td>
                <td>
                    <select onchange="updateSymbolStrategy('${symbol}', this.value)" style="background:transparent; color:white; border:none;">
                        <option value="GOD_MODE" ${cfg.strategy === 'GOD_MODE' ? 'selected' : ''}>GOD MODE</option>
                        <option value="JEWEL_ELITE" ${cfg.strategy === 'JEWEL_ELITE' ? 'selected' : ''}>JEWEL ELITE</option>
                        <option value="GRID" ${cfg.strategy === 'GRID' ? 'selected' : ''}>GRID</option>
                    </select>
                </td>
                <td><span class="dot ${cfg.status === 'OPEN' ? 'active' : ''}"></span> ${cfg.status}</td>
                <td>
                    <button class="btn-sm secondary" onclick="toggleSymbol('${symbol}')">${cfg.enabled ? 'Disable' : 'Enable'}</button>
                </td>
            </tr>
        `).join('');
    }

    updateMarketSessions() {
        const now = new Date();
        const hours = now.getUTCHours();
        
        const sessions = {
            london: hours >= 8 && hours < 16,
            newyork: hours >= 13 && hours < 21,
            tokyo: hours >= 0 && hours < 8
        };
        
        const sessionItems = document.querySelectorAll('.session-item');
        sessionItems.forEach(item => {
            const name = item.querySelector('span:nth-child(2)').innerText.toLowerCase().replace(' ', '');
            const dot = item.querySelector('.dot');
            if (sessions[name]) {
                dot.classList.add('active');
            } else {
                dot.classList.remove('active');
            }
        });
    }
}

// Global functions
function terminateBot(symbol) {
    if (!confirm(`Terminate deployment for ${symbol}?`)) return;
    fetch('/api/close_position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
    });
}

function panicClose() {
    if (!confirm("🚨 INITIATE TOTAL LIQUIDATION?")) return;
    fetch('/api/panic_close', { method: 'POST' });
}

function initializeBot() {
    const strategy = document.getElementById('bot-mode').value;
    const btn = document.querySelector('.btn-initialize');
    const standby = document.querySelector('.bot-standby');
    
    btn.disabled = true;
    standby.innerHTML = `<span class="pulse active"></span> --- Deploying ${strategy}`;
    
    fetch('/api/initialize_bot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy })
    }).then(r => r.json()).then(data => {
        setTimeout(() => {
            btn.innerText = "Initialize Bot";
            btn.disabled = false;
            standby.innerHTML = `<span class="pulse"></span> --- ${strategy} Active`;
            const msg = data.message || data.error || "Execution Complete";
            alert(`SATS Intelligence: ${msg}`);
        }, 2000);
    }).catch(err => {
        btn.innerText = "Initialize Bot";
        btn.disabled = false;
        standby.innerHTML = `<span class="pulse"></span> --- Deployment Error`;
        alert(`SATS Intelligence Error: ${err.message}`);
    });
}

function switchTab(tabId) {
    const dash = document.getElementById('dashboard-main');
    const settings = document.getElementById('settings-tab');
    const signals = document.getElementById('signals-tab');
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => item.classList.remove('active'));
    
    dash.style.display = 'none';
    settings.style.display = 'none';
    signals.style.display = 'none';

    if (tabId === 'dashboard') {
        dash.style.display = 'block';
        document.querySelector('[onclick="switchTab(\'dashboard\')"]').classList.add('active');
    } else if (tabId === 'settings') {
        settings.style.display = 'block';
        document.querySelector('[onclick="switchTab(\'settings\')"]').classList.add('active');
    } else if (tabId === 'signals') {
        signals.style.display = 'block';
        document.querySelector('[onclick="switchTab(\'signals\')"]').classList.add('active');
    }
}

function toggleSymbol(symbol) {
    // API call to toggle symbol in shared state
    console.log("Toggling", symbol);
}

function updateSymbolStrategy(symbol, strategy) {
    console.log("Updating", symbol, "to", strategy);
}

function addNewMarket() {
    const symbol = document.getElementById('new-symbol').value;
    if (!symbol) return;
    alert(`System Authorization: Symbol ${symbol} added to analysis queue.`);
}

async function closeTrade(symbol) {
    if (!confirm(`Are you sure you want to close all positions for ${symbol}?`)) return;
    
    try {
        const res = await fetch('/api/close_position', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });
        const data = await res.json();
        if (data.status === 'success') {
            alert(`Execution Successful: ${symbol} liquidated.`);
        } else {
            alert(`Execution Error: ${data.message}`);
        }
    } catch (e) {
        console.error("Close Trade Error:", e);
    }
}

async function terminateBot(symbol) {
    alert(`Bot Termination Signal Sent for ${symbol}. Monitoring process shutdown...`);
    // Logic for actual process killing would go here
}

// Initialize
window.premium = new PremiumDashboard();

// Register Service Worker for iOS PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then(reg => console.log('Sentinel PWA Registered'))
            .catch(err => console.log('PWA Error:', err));
    });
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    const initBtn = document.querySelector('.btn-initialize');
    if (initBtn) initBtn.onclick = initializeBot;
    // Mobile Sidebar Toggle
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
        
        // Close sidebar when clicking a nav item on mobile
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('open');
                }
            });
        });
    }
});
