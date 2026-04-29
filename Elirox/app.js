/**
 * Sentinel Premium Dashboard Logic
 * Handles real-time backend updates via WebSockets
 */

class Dashboard {
    constructor() {
        this.ws = null;
        this.state = {
            is_bot_active: false,
            prices: {},
            active_trades: [],
            signals: [],
            balance: 0,
            demo_balance: 0,
            active_broker: 'DEMO',
            demo_mode: true
        };
        this.chart = null;
        
        this.init();
    }

    init() {
        console.log('Sentinel Dashboard Initializing...');
        this.connectWebSocket();
        this.bindEvents();
        this.initTradingView();
    }

    initTradingView(symbol = "XAUUSD") {
        // Clear previous content
        const container = document.getElementById('chart-container');
        if (!container) return;
        container.innerHTML = '';

        const script = document.createElement('script');
        script.src = "https://s3.tradingview.com/tv.js";
        script.async = true;
        script.onload = () => {
            new TradingView.widget({
                "autosize": true,
                "symbol": "FOREXCOM:XAUUSD",
                "interval": "15",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#f1f3f6",
                "enable_publishing": false,
                "hide_top_toolbar": false,
                "save_image": false,
                "container_id": "chart-container",
                "backgroundColor": "rgba(10, 10, 15, 1)",
                "gridColor": "rgba(42, 46, 57, 0.06)",
                "hide_side_toolbar": false
            });
        };
        document.head.appendChild(script);
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
                console.error("WS parsing error", e);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed. Reconnecting...');
            setTimeout(() => this.connectWebSocket(), 2000);
        };
    }

    updateState(data) {
        this.state = { ...this.state, ...data };
        this.renderUI();
    }

    renderUI() {
        // 1. Update Stats Row
        const isDemo = this.state.demo_mode;
        const balance = isDemo ? (this.state.demo_balance || 0) : (this.state.balance || 0);
        const totalPnl = this.state.active_trades ? this.state.active_trades.reduce((sum, t) => sum + (parseFloat(t.pnl) || 0), 0) : 0;
        const equity = balance + totalPnl;

        const equityEl = document.getElementById('total-equity');
        if (equityEl) equityEl.innerText = `$${equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

        const pnlEl = document.getElementById('total-pnl');
        if (pnlEl) {
            pnlEl.innerText = `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            pnlEl.style.color = totalPnl >= 0 ? 'var(--success)' : 'var(--danger)';
        }

        // 2. Update Win Rate
        const winRateEl = document.getElementById('win-rate');
        if (winRateEl) {
            const history = this.state.trade_history || [];
            if (history.length > 0) {
                const wins = history.filter(t => (t.status === 'CLOSED' && t.pnl > 0) || t.pnl > 0).length;
                const rate = (wins / history.length) * 100;
                winRateEl.innerText = `${rate.toFixed(1)}%`;
            } else {
                winRateEl.innerText = '0.0%';
            }
        }

        // 3. Update System Status
        const statusText = document.getElementById('system-status-text');
        const statusDot = document.getElementById('system-status-dot');
        const statusWrapper = document.getElementById('system-status-indicator');
        
        if (statusText && statusDot) {
            const status = this.state.status || 'OFFLINE';
            statusText.innerText = status === 'ONLINE' ? 'SYSTEM OPERATIONAL' : `SYSTEM ${status}`;
            
            if (status === 'ONLINE') {
                statusWrapper.style.color = 'var(--success)';
                statusDot.style.background = 'var(--success)';
                statusDot.style.boxShadow = '0 0 10px var(--success)';
            } else if (status === 'INITIALIZING') {
                statusWrapper.style.color = 'var(--warning)';
                statusDot.style.background = 'var(--warning)';
                statusDot.style.boxShadow = '0 0 10px var(--warning)';
            } else {
                statusWrapper.style.color = 'var(--danger)';
                statusDot.style.background = 'var(--danger)';
                statusDot.style.boxShadow = '0 0 10px var(--danger)';
            }
        }

        // 4. Update Mode Toggle
        const modeSwitch = document.getElementById('mode-switch');
        if (modeSwitch) {
            modeSwitch.checked = !this.state.demo_mode;
            document.getElementById('demo-label').className = this.state.demo_mode ? 'active' : '';
            document.getElementById('real-label').className = !this.state.demo_mode ? 'active' : '';
        }

        // 5. Render Multi-Bot Grid
        this.renderBotGrid();

        // 4. Render Active Positions Table
        const tbody = document.getElementById('positions-body');
        if (tbody) {
            if (!this.state.active_trades || this.state.active_trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 20px; color: var(--text-muted);">No active positions</td></tr>';
            } else {
                tbody.innerHTML = this.state.active_trades.map(trade => `
                    <tr>
                        <td style="font-weight: 600;">${trade.symbol}</td>
                        <td><span class="badge badge-${trade.direction === 'LONG' ? 'buy' : 'sell'}">${trade.direction === 'LONG' ? 'Buy' : 'Sell'}</span></td>
                        <td>${(trade.entry || 0).toFixed(trade.symbol.includes('EUR') ? 4 : 2)}</td>
                        <td>${(this.state.prices[trade.symbol] || trade.entry || 0).toFixed(trade.symbol.includes('EUR') ? 4 : 2)}</td>
                        <td>${trade.qty || 0.01} Lot</td>
                        <td style="color: ${trade.pnl >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight: 700;">
                            ${trade.pnl >= 0 ? '+' : ''}$${(trade.pnl || 0).toFixed(2)}
                        </td>
                        <td><button onclick="window.app.closePosition('${trade.symbol}')" class="btn-close">CLOSE</button></td>
                    </tr>
                `).join('');
            }
        }

        // 5. Update AI Signals
        const signalContainer = document.getElementById('ai-signals-container');
        if (signalContainer && this.state.signals) {
            signalContainer.innerHTML = this.state.signals.slice(0, 3).map(sig => `
                <div class="signal-item" style="background: rgba(255,255,255,0.03); border-radius: 10px; padding: 12px; border-left: 3px solid var(--accent); transition: transform 0.2s ease; margin-bottom: 8px;">
                    <div style="font-size: 11px; color: var(--accent); font-weight: 700; margin-bottom: 4px;">SENTINEL V4 ML</div>
                    <div style="font-size: 12px; font-weight: 600;">${sig.direction} SIGNAL: ${sig.symbol}</div>
                    <div style="font-size: 10px; color: var(--text-muted);">@ ${sig.entry} • TP: ${sig.tp}</div>
                </div>
            `).join('');
        }

        // 6. Update History Table
        const historyBody = document.getElementById('history-body');
        if (historyBody && this.state.trade_history) {
            if (this.state.trade_history.length === 0) {
                historyBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No trade history</td></tr>';
            } else {
                historyBody.innerHTML = this.state.trade_history.map(trade => `
                    <tr>
                        <td>${trade.time || trade.created_at || 'Recently'}</td>
                        <td style="font-weight: 600;">${trade.symbol}</td>
                        <td><span class="badge badge-${trade.direction === 'LONG' ? 'buy' : 'sell'}">${trade.direction === 'LONG' ? 'Buy' : 'Sell'}</span></td>
                        <td><span style="color: ${trade.pnl > 0 ? 'var(--success)' : 'var(--danger)'}">${trade.pnl > 0 ? 'WIN' : 'LOSS'}</span></td>
                        <td style="color: ${trade.pnl >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight: 700;">
                            ${trade.pnl >= 0 ? '+' : ''}$${(trade.pnl || 0).toFixed(2)}
                        </td>
                    </tr>
                `).join('');
            }
        }
    }

    async toggleMode() {
        const isReal = document.getElementById('mode-switch').checked;
        console.log(`Switching mode to ${isReal ? 'REAL' : 'DEMO'}`);
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ demo_mode: !isReal })
            });
        } catch (e) {
            console.error("Error toggling mode", e);
        }
    }

    async handleFunding(action) {
        const amount = prompt(`Enter amount to ${action}:`, "100");
        if (!amount || isNaN(amount)) return;

        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fund_action: action, amount: parseFloat(amount) })
            });
        } catch (e) {
            console.error("Funding error", e);
        }
    }

    async saveRiskSettings() {
        const lot = document.getElementById('risk-lot-size').value;
        const leverage = document.getElementById('risk-leverage').value;
        const drawdown = document.getElementById('risk-drawdown').value;
        const sl = document.getElementById('risk-sl').value;

        console.log("Saving Risk Settings...");
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    risk_config: {
                        default_lot_size: parseFloat(lot),
                        leverage: leverage,
                        max_drawdown: parseFloat(drawdown),
                        default_sl_pips: parseFloat(sl)
                    }
                })
            });
            const result = await response.json();
            if (result.status === 'success') alert("Risk Configuration Saved Successfully!");
        } catch (e) {
            console.error("Save risk error", e);
            alert("Failed to save settings.");
        }
    }

    switchTab(tabName) {
        // Update Nav UI
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.innerText.toLowerCase().includes(tabName.split('-')[0])) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Update Pane Visibility
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        const target = document.getElementById(`tab-${tabName}`);
        if (target) target.classList.add('active');

        // Hide chart if not on dashboard to save resources
        if (tabName !== 'dashboard') {
            document.getElementById('active-positions-section').style.display = 'block'; // Keep positions visible
        } else {
            document.getElementById('active-positions-section').style.display = 'block';
        }
    }

    renderBotGrid() {
        const grid = document.getElementById('active-bots-grid');
        if (!grid || !this.state.market_configs) return;

        const allMarkets = Object.keys(this.state.market_configs);
        
        grid.innerHTML = allMarkets.map(symbol => {
            const config = this.state.market_configs[symbol];
            const isActive = config.enabled && this.state.is_bot_active;
            const price = this.state.prices[symbol] || 0.0;
            const trades = this.state.active_trades ? this.state.active_trades.filter(t => t.symbol === symbol) : [];
            const pnl = trades.reduce((sum, t) => sum + (parseFloat(t.pnl) || 0), 0);

            return `
                <div class="bot-card ${isActive ? 'active' : 'inactive'}">
                    <div class="bot-card-header">
                        <div>
                            <div class="bot-symbol">${symbol}</div>
                            <div class="bot-strategy">${config.strategy || 'JEWEL_ELITE'}</div>
                        </div>
                        <div class="status-indicator" style="color: ${isActive ? 'var(--success)' : 'var(--text-muted)'}">
                            <div class="status-dot" style="background: ${isActive ? 'var(--success)' : 'var(--text-muted)'}; box-shadow: ${isActive ? '0 0 10px var(--success)' : 'none'}; animation: ${isActive ? 'pulse 2s infinite' : 'none'}"></div>
                            ${isActive ? 'RUNNING' : 'STOPPED'}
                        </div>
                    </div>
                    
                    <div class="bot-stats">
                        <div class="bot-stat-item">
                            <span class="bot-stat-label">Market Price</span>
                            <span class="bot-stat-value">${price.toFixed(symbol.includes('EUR') ? 4 : 2)}</span>
                        </div>
                        <div class="bot-stat-item">
                            <span class="bot-stat-label">Profit/Loss</span>
                            <span class="bot-stat-value" style="color: ${pnl >= 0 ? 'var(--success)' : 'var(--danger)'}">
                                ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}
                            </span>
                        </div>
                    </div>

                    <div class="bot-controls">
                        <button class="btn-toggle ${config.enabled ? '' : 'off'}" onclick="window.app.toggleMarket('${symbol}')">
                            ${config.enabled ? 'DISABLE' : 'ENABLE'}
                        </button>
                        <button class="btn-close" style="padding: 8px;" onclick="window.app.removeMarket('${symbol}')">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    async addMarket() {
        const input = document.getElementById('new-market-input');
        const symbol = input.value.trim();
        if (!symbol) return;

        try {
            const response = await fetch('/api/market/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
            const result = await response.json();
            if (result.status === 'success') {
                input.value = '';
                console.log(`Added market: ${symbol}`);
            }
        } catch (e) {
            console.error("Error adding market", e);
        }
    }

    async toggleMarket(symbol) {
        try {
            await fetch('/api/market/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
        } catch (e) {
            console.error("Error toggling market", e);
        }
    }

    async removeMarket(symbol) {
        if (!confirm(`Remove bot instance for ${symbol}?`)) return;
        try {
            await fetch('/api/market/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
        } catch (e) {
            console.error("Error removing market", e);
        }
    }

    async closePosition(symbol) {
        console.log(`Requesting close for ${symbol}`);
        try {
            const response = await fetch('/api/close_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
            const result = await response.json();
            if (result.status === 'success') {
                console.log(`Successfully closed ${symbol}`);
            }
        } catch (e) {
            console.error("Error closing position", e);
        }
    }

    async panicClose() {
        if (!confirm("Are you sure you want to close ALL positions?")) return;
        try {
            await fetch('/api/panic_close', { method: 'POST' });
        } catch (e) {
            console.error("Panic close error", e);
        }
    }

    bindEvents() {
        // Navigation Interactivity
        const tabMap = {
            'Dashboard': 'dashboard',
            'Risk Manager': 'risk-manager',
            'History': 'history',
            'Settings': 'risk-manager' // Map settings to risk for now
        };

        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const tabText = item.innerText.trim();
                const tabKey = tabMap[tabText];
                if (tabKey) this.switchTab(tabKey);
            });
        });
    }
}

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
    window.app = new Dashboard();
});
