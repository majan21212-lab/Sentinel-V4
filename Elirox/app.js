/**
 * Sentinel V4 Cockpit Dashboard Logic
 */

class Dashboard {
    constructor() {
        this.ws = null;
        this.state = {
            is_bot_active: false,
            prices: {},
            active_trades: [],
            trade_history: [],
            signals: [],
            balance: 0,
            demo_balance: 0,
            demo_mode: true,
            status: 'OFFLINE',
            strategy: 'JEWEL_ELITE',
            active_markets: [],
            market_configs: {}
        };
        this.lastInteractionUpdate = 0;
        this.init();
    }

    init() {
        console.log('Sentinel Cockpit Initializing...');
        this.connectWebSocket();
        this.logMessage("System Initialized. Awaiting Broker Connection...", "info");
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
            this.logMessage("WebSocket Disconnected. Reconnecting...", "error");
            setTimeout(() => this.connectWebSocket(), 2000);
        };
    }

    updateState(data) {
        // Detect state changes for logging
        if (data.is_bot_active !== undefined && data.is_bot_active !== this.state.is_bot_active) {
            this.logMessage(`Bot Status Changed: ${data.is_bot_active ? 'ACTIVE' : 'PAUSED'}`, data.is_bot_active ? 'success' : 'warn');
        }

        this.state = { ...this.state, ...data };
        this.renderUI();
        this.renderProfile();
    }

    renderUI() {
        // Core Updates
        const now = Date.now();
        const isRecentlyUpdated = (now - this.lastInteractionUpdate) < 2000;

        this.renderStats();
        this.renderPositions();
        this.renderHistory();
        this.renderMarketConfig();
        
        // Update Mode Buttons in Modal
        const btnDemo = document.getElementById('btn-demo');
        const btnReal = document.getElementById('btn-real');
        if (btnDemo && btnReal && !isRecentlyUpdated) {
            btnDemo.classList.toggle('active', this.state.demo_mode);
            btnReal.classList.toggle('active', !this.state.demo_mode);
        }

        // 2. System Control Buttons
        const btnActivate = document.getElementById('btn-activate');
        const btnPause = document.getElementById('btn-pause');
        
        if (this.state.is_bot_active) {
            if (btnActivate) {
                btnActivate.classList.add('active');
                btnActivate.style.boxShadow = 'var(--glow-green)';
            }
            if (btnPause) btnPause.style.boxShadow = 'none';
        } else {
            if (btnActivate) {
                btnActivate.classList.remove('active');
                btnActivate.style.boxShadow = 'none';
            }
            if (btnPause) btnPause.style.boxShadow = '0 0 15px rgba(255, 157, 0, 0.3)';
        }

        // 4. Strategy Buttons (Global)
        if (!isRecentlyUpdated) {
            document.querySelectorAll('.strat-btn').forEach(btn => {
                if (btn.innerText.includes(this.state.strategy)) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
        
        // --- Risk Sliders Sync ---
        const risk = this.state.risk_config || {};
        
        const sliderDD = document.getElementById('slider-drawdown');
        if (sliderDD && !sliderDD.matches(':active') && !isRecentlyUpdated) {
            const val = risk.max_daily_loss_pct || 3;
            sliderDD.value = val;
            document.getElementById('drawdown-val').innerText = val + '%';
        }
        
        const sliderExp = document.getElementById('slider-exposure');
        if (sliderExp && !sliderExp.matches(':active') && !isRecentlyUpdated) {
            const val = (risk.risk_per_asset && risk.risk_per_asset.DEFAULT) || 2;
            sliderExp.value = val;
            document.getElementById('exposure-val').innerText = val + '%';
        }
        
        const sliderConf = document.getElementById('slider-confidence');
        if (sliderConf && !sliderConf.matches(':active') && !isRecentlyUpdated) {
            const val = Math.round((risk.min_ml_confidence || 0.45) * 100);
            sliderConf.value = val;
            document.getElementById('confidence-val').innerText = val + '%';
        }
    }

    renderPositions() {
        const body = document.getElementById('positions-body');
        if (!body) return;

        if (!this.state.active_trades || this.state.active_trades.length === 0) {
            body.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 40px;">No Active Market Exposure</td></tr>';
            return;
        }

        body.innerHTML = this.state.active_trades.map(trade => {
            const side = (trade.direction || 'LONG').toUpperCase();
            const pnl = parseFloat(trade.pnl) || 0;
            const currentPrice = this.state.prices[trade.symbol] || trade.entry || 0;
            
            return `
                <tr>
                    <td><div class="symbol-tag">${trade.symbol}</div></td>
                    <td class="${side === 'LONG' ? 'side-buy' : 'side-sell'}">${side === 'LONG' ? 'Buy' : 'Sell'}</td>
                    <td>$${(trade.entry || 0).toFixed(2)}</td>
                    <td style="font-size: 11px; color: var(--text-dim);">
                        <span style="color: var(--neon-green);">$${(trade.tp || 0).toFixed(2)}</span><br>
                        <span style="color: var(--neon-red);">$${(trade.sl || 0).toFixed(2)}</span>
                    </td>
                    <td class="${pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</td>
                    <td style="color: var(--text-muted); font-size: 11px;">0h 15m</td>
                    <td><button class="icon-btn" style="width: auto; padding: 4px 8px; font-size: 10px;" onclick="window.app.closePosition('${trade.symbol}')">CLOSE</button></td>
                </tr>
            `;
        }).join('');
    }

    renderMarketConfig() {
        const body = document.getElementById('market-config-body');
        if (!body) return;

        // PREVENTION: Don't re-render the table if the user is currently interacting with a dropdown
        if (body.contains(document.activeElement) && (document.activeElement.tagName === 'SELECT' || document.activeElement.tagName === 'INPUT')) {
            return;
        }

        const configs = this.state.market_configs || {};
        const active_markets = this.state.active_markets || [];

        if (active_markets.length === 0) {
            body.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--text-muted); padding: 20px;">No Assets Monitored</td></tr>';
            return;
        }

        body.innerHTML = active_markets.map(symbol => {
            const config = configs[symbol] || { strategy: 'JEWEL_ELITE', enabled: true, status: 'OPEN' };
            const isClosed = config.status === 'CLOSED';
            
            return `
                <tr>
                    <td style="padding: 10px 15px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="font-weight: 700; color: white;">${symbol}</div>
                            ${isClosed ? `<span style="font-size: 7px; background: rgba(255, 62, 62, 0.1); color: var(--neon-red); padding: 2px 4px; border-radius: 2px; font-weight: 800; border: 1px solid rgba(255, 62, 62, 0.2);">CLOSED</span>` : ''}
                        </div>
                        <div style="font-size: 9px; color: var(--text-muted);">Institutional Feed</div>
                    </td>
                    <td style="padding: 10px 15px;">
                        <select onchange="window.app.updateMarketStrategy('${symbol}', this.value)" style="background: rgba(10, 18, 25, 1); border: 1px solid rgba(0,210,255,0.2); color: var(--neon-blue); font-size: 10px; padding: 4px; border-radius: 4px; width: 100%; outline: none;">
                            <option value="JEWEL_ELITE" ${config.strategy === 'JEWEL_ELITE' ? 'selected' : ''}>JEWEL ELITE</option>
                            <option value="GOD_MODE" ${config.strategy === 'GOD_MODE' ? 'selected' : ''}>GOD MODE</option>
                            <option value="HYBRID" ${config.strategy === 'HYBRID' ? 'selected' : ''}>HYBRID AI</option>
                        </select>
                    </td>
                    <td style="padding: 10px 15px; text-align: right;">
                        <button onclick="window.app.removeMarket('${symbol}')" style="background: none; border: none; color: var(--neon-red); cursor: pointer; font-size: 16px; transition: 0.3s;" onmouseover="this.style.color='white'" onmouseout="this.style.color='var(--neon-red)'">×</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    calculateWinRate() {
        const history = this.state.trade_history || [];
        if (history.length === 0) return "0.0";
        const wins = history.filter(t => t.pnl > 0).length;
        return ((wins / history.length) * 100).toFixed(1);
    }

    logMessage(msg, type = "info") {
        const feed = document.getElementById('log-feed');
        if (!feed) return;

        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const time = new Date().toLocaleTimeString([], { hour12: false });
        
        let colorClass = "";
        if (type === "success") colorClass = "log-msg-success";
        if (type === "error") colorClass = "pnl-negative";
        if (type === "warn") colorClass = "side-sell";

        entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="${colorClass}">${msg}</span>`;
        
        feed.prepend(entry);
        if (feed.children.length > 50) feed.lastChild.remove();
    }

    // --- API Calls ---

    async toggleBot(active) {
        this.logMessage(`Requesting System ${active ? 'Activation' : 'Pause'}...`, "info");
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_bot_active: active })
            });
        } catch (e) {
            this.logMessage("Command Failed: Connection Error", "error");
        }
    }

    async setStrategy(strat) {
        this.lastInteractionUpdate = Date.now();
        this.state.strategy = strat;
        this.logMessage(`Switching Global Strategy to ${strat}...`, "info");
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy_mode: strat })
            });
            this.renderUI();
        } catch (e) {
            this.logMessage("Failed to Switch Strategy", "error");
        }
    }

    async updateMarketStrategy(symbol, strategy) {
        this.logMessage(`Updating ${symbol} to ${strategy} Mode...`, "info");
        try {
            await fetch('/api/market/strategy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, strategy })
            });
        } catch (e) { console.error(e); }
    }

    async closePosition(symbol) {
        this.logMessage(`Liquidation Request: ${symbol}`, "warn");
        try {
            const res = await fetch('/api/close_position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
            if (res.ok) {
                this.logMessage(`Liquidation Success: ${symbol}`, "success");
            } else {
                const err = await res.json();
                this.logMessage(`Liquidation Failed: ${err.message}`, "error");
            }
        } catch (e) {
            this.logMessage(`Liquidation Failed: Connection Error`, "error");
        }
    }

    async panicClose() {
        if (!confirm("🚨 WARNING: INITIATE TOTAL GLOBAL LIQUIDATION?")) return;
        this.logMessage("🚨 PANIC PROTOCOL INITIATED", "error");
        try {
            const res = await fetch('/api/panic_close', { method: 'POST' });
            const data = await res.json();
            if (data.status === "success") {
                this.logMessage("✅ GLOBAL LIQUIDATION COMPLETED", "success");
            } else if (data.status === "partial") {
                this.logMessage("⚠️ PARTIAL LIQUIDATION COMPLETED", "warn");
            } else {
                this.logMessage("❌ PANIC CLOSE REJECTED BY BROKER", "error");
            }
        } catch (e) {
            this.logMessage("Panic Protocol Failed!", "error");
        }
    }

    async removeMarket(symbol) {
        if (!confirm(`Remove ${symbol} from active scanning?`)) return;
        this.logMessage(`Decommissioning ${symbol}...`, "warn");
        try {
            await fetch('/api/market/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
        } catch (e) { console.error(e); }
    }

    // --- Modal Management ---
    openModal(type) {
        this.closeModals();
        const backdrop = document.getElementById('modal-backdrop');
        const modal = document.getElementById(`modal-${type}`);
        if (backdrop && modal) {
            backdrop.style.display = 'block';
            modal.style.display = 'flex';
        }

        if (type === 'analysis') {
            this.initTradingView();
        }
    }

    closeModals() {
        document.getElementById('modal-backdrop').style.display = 'none';
        document.querySelectorAll('.cockpit-modal').forEach(m => m.style.display = 'none');
    }

    initTradingView(symbol = "XAUUSD") {
        const container = document.getElementById('modal-chart-container');
        if (!container) return;
        container.innerHTML = '';

        const script = document.createElement('script');
        script.src = "https://s3.tradingview.com/tv.js";
        script.async = true;
        script.onload = () => {
            new TradingView.widget({
                "autosize": true,
                "symbol": `FOREXCOM:${symbol}`,
                "interval": "15",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "container_id": "modal-chart-container",
                "backgroundColor": "rgba(10, 18, 25, 1)",
                "gridColor": "rgba(42, 46, 57, 0.06)",
                "hide_side_toolbar": false
            });
        };
        document.head.appendChild(script);
    }

    renderHistory() {
        const body = document.getElementById('history-body');
        if (!body) return;

        const history = this.state.trade_history || [];
        if (history.length === 0) {
            body.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">No Trade History Recorded</td></tr>';
            return;
        }

        body.innerHTML = history.map(trade => `
            <tr>
                <td style="font-size: 10px;">${trade.closed_at || trade.time}</td>
                <td style="font-weight: 700;">${trade.symbol}</td>
                <td><span class="badge" style="background: ${trade.pnl > 0 ? 'rgba(0,255,204,0.1)' : 'rgba(255,62,62,0.1)'}; color: ${trade.pnl > 0 ? 'var(--neon-green)' : 'var(--neon-red)'}">${trade.pnl > 0 ? 'WIN' : 'LOSS'}</span></td>
                <td class="${trade.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">${trade.pnl >= 0 ? '+' : ''}$${Math.abs(trade.pnl).toFixed(2)}</td>
            </tr>
        `).join('');
    }

    renderStats() {
        const metrics = this.getAccountMetrics();
        
        const balEl = document.getElementById('snap-total-bal');
        if (balEl) balEl.innerText = `$${metrics.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        
        const wrEl = document.getElementById('snap-win-rate');
        if (wrEl) wrEl.innerText = `${metrics.winRate}%`;
        
        const stateEl = document.getElementById('snap-bot-state');
        if (stateEl) {
            stateEl.innerText = this.state.is_bot_active ? 'LIVE - ACTIVE' : 'SYSTEM PAUSED';
            stateEl.style.color = this.state.is_bot_active ? 'var(--neon-green)' : 'var(--neon-orange)';
        }
        
        const dailyPnlEl = document.getElementById('snap-daily-pnl');
        if (dailyPnlEl) {
            dailyPnlEl.innerText = `${metrics.floatingPnl >= 0 ? '+' : ''}$${Math.abs(metrics.floatingPnl).toFixed(2)}`;
            dailyPnlEl.style.color = metrics.floatingPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
        }

        const statusEl = document.getElementById('snap-broker-status');
        if (statusEl) {
            const status = this.state.broker_status || 'DISCONNECTED';
            statusEl.innerText = status === 'CONNECTED' ? '● SYNCED' : '● OFFLINE';
            statusEl.style.color = status === 'CONNECTED' ? 'var(--neon-green)' : 'var(--text-muted)';
            
            // --- New: Update Individual Broker Cards ---
            const brokers = ['alpaca', 'mt5', 'binance'];
            const details = this.state.broker_details || {};
            const isDemo = this.state.demo_mode;

            brokers.forEach(b => {
                const bData = details[b] || { balance: 0, status: 'OFFLINE' };
                const typeEl = document.getElementById(`${b}-type`);
                const balEl = document.getElementById(`${b}-balance`);
                const pulseEl = document.getElementById(`${b}-pulse`);
                const statusEl = document.getElementById(`${b}-status`);

                if (typeEl) {
                    typeEl.innerText = isDemo ? "DEMO" : "REAL";
                    typeEl.style.color = isDemo ? 'var(--neon-blue)' : 'var(--neon-green)';
                    typeEl.style.background = isDemo ? 'rgba(0,210,255,0.1)' : 'rgba(0,255,204,0.1)';
                }
                if (balEl) balEl.innerText = `$${Number(bData.balance).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                if (pulseEl) {
                    pulseEl.style.background = bData.status === 'CONNECTED' ? 'var(--neon-green)' : 'var(--text-muted)';
                    pulseEl.style.boxShadow = bData.status === 'CONNECTED' ? '0 0 8px var(--neon-green)' : 'none';
                }
                if (statusEl) {
                    statusEl.innerText = bData.status;
                    statusEl.style.color = bData.status === 'CONNECTED' ? 'var(--neon-green)' : 'var(--text-muted)';
                }
            });
        }
    }

    getAccountMetrics() {
        const isDemo = this.state.demo_mode;
        const balance = isDemo ? (this.state.demo_balance || 0) : (this.state.balance || 0);
        const floatingPnl = (this.state.active_trades || []).reduce((sum, t) => sum + (parseFloat(t.pnl) || 0), 0);
        const equity = balance + floatingPnl;
        const winRate = this.calculateWinRate();
        
        return {
            balance,
            floatingPnl,
            equity,
            winRate,
            isDemo
        };
    }

    renderProfile() {
        const metrics = this.getAccountMetrics();
        const brokerEl = document.getElementById('prof-broker');
        const envEl = document.getElementById('prof-env');
        const equityEl = document.getElementById('prof-equity');
        const floatingEl = document.getElementById('prof-floating');
        const bridgeEl = document.getElementById('prof-bridge-stats');

        if (!brokerEl || !equityEl) return;

        const risk = this.state.risk_config || {};
        const weights = risk.bridge_weighting || { mt5: 1, binance: 0.3, alpaca: 0 };

        brokerEl.innerText = this.state.active_broker || "EXNESS MT5";
        envEl.innerText = metrics.isDemo ? "DEMO" : "LIVE";
        envEl.style.color = metrics.isDemo ? 'var(--neon-blue)' : 'var(--neon-green)';
        
        equityEl.innerText = `$${metrics.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        floatingEl.innerText = `${metrics.floatingPnl >= 0 ? '+' : ''}$${metrics.floatingPnl.toFixed(2)}`;
        floatingEl.style.color = metrics.floatingPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';

        // Render Bridge Weighting Bars
        bridgeEl.innerHTML = Object.entries(weights).map(([broker, weight]) => {
            const pct = Math.min(100, weight * 100);
            return `
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 9px; margin-bottom: 4px;">
                        <span style="text-transform: uppercase; letter-spacing: 1px;">${broker}</span>
                        <span style="color: white; font-weight: 800;">${pct.toFixed(0)}% Allocation</span>
                    </div>
                    <div style="height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; overflow: hidden;">
                        <div style="height: 100%; width: ${pct}%; background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue);"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    async toggleDemo(isDemo) {
        // Now just a helper to sync the state without opening modal
        this.lastInteractionUpdate = Date.now();
        this.state.demo_mode = isDemo;
        this.renderUI();
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ demo_mode: isDemo })
            });
        } catch (e) { console.error(e); }
    }

    openBrokerConnect(mode) {
        this.pendingBrokerMode = mode;
        const title = document.getElementById('broker-modal-title');
        if (title) title.innerText = `REGISTER ${mode} ACCOUNT`;
        
        // Pre-fill if possible or just clear
        document.getElementById('broker-account-id').value = '';
        document.getElementById('broker-password').value = '';
        
        this.openModal('broker');
    }

    async submitBrokerRegistration() {
        const platform = document.getElementById('broker-platform').value;
        const accountId = document.getElementById('broker-account-id').value;
        const server = document.getElementById('broker-server').value;
        const password = document.getElementById('broker-password').value;

        if (!accountId || !password) {
            alert("Credentials Required for Bridge Initialization");
            return;
        }

        this.logMessage(`Initializing ${this.pendingBrokerMode} Bridge via ${platform}...`, "info");
        
        try {
            const payload = {
                demo_mode: this.pendingBrokerMode === 'DEMO',
                active_broker: platform,
                credentials: {
                    [platform]: {
                        key: accountId,
                        secret: password,
                        server: server
                    }
                }
            };

            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                this.logMessage("Bridge Initialization Failed: Server Error", "error");
                return;
            }

            this.logMessage(`Bridge Successfully Established: ${platform}`, "success");
            this.closeModals();
            
            if (this.pendingBrokerMode === 'REAL') {
                this.state.demo_mode = false;
            } else {
                this.state.demo_mode = true;
            }
            
            try {
                this.renderUI();
                this.renderProfile();
            } catch (uiErr) {
                console.error("UI Update Error after Bridge Registration", uiErr);
            }
        } catch (e) {
            this.logMessage("Bridge Error: Network Connection Refused", "error");
            console.error(e);
        }
    }

    async addAsset() {
        const input = document.getElementById('add-asset-input');
        const stratSelect = document.getElementById('add-asset-strategy');
        const symbol = input.value.trim();
        const strategy = stratSelect ? stratSelect.value : 'JEWEL_ELITE';
        
        if (!symbol) return;
        
        this.logMessage(`Deploying ${strategy} Intelligence to: ${symbol}`, "info");
        try {
            const res = await fetch('/api/market/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, strategy })
            });
            if (res.ok) {
                input.value = '';
                this.logMessage(`Asset Deployed: ${symbol}`, "success");
            }
        } catch (e) { console.error(e); }
    }

    async updateRiskSettings() {
        this.lastInteractionUpdate = Date.now();
        const drawdown = document.getElementById('slider-drawdown').value;
        const exposure = document.getElementById('slider-exposure').value;
        const confidence = document.getElementById('slider-confidence').value;
        
        this.logMessage(`Updating Risk Matrix: DD:${drawdown}% | Exp:${exposure}% | ML:${confidence}%`, "info");
        
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_daily_loss_pct: drawdown,
                    default_exposure: exposure,
                    min_ml_confidence: confidence
                })
            });
        } catch (e) { console.error(e); }
    }
}

// Initialize
window.app = new Dashboard();
