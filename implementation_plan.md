# Autocoder Execution Plan: TradeBot Institutional Restoration

This plan is optimized for autonomous execution. Each step is a direct instruction with specific file targets and verification criteria.

## 0. Pre-Execution Constraints
- **Workspace Root**: `f:\TradeBot`
- **Environment**: Python 3.10+, MetaTrader 5 Terminal (Simulated/Live), Node.js (for Flutter/Web).
- **Style Priority**: Elirox Dark (Glassmorphism, #0D0D0D backgrounds, #00FFA3 accents).

## 1. System Integrity & Restoration
Critical repair of files corrupted during drive migration.

- [ ] **TASK 1.1: Verify & Repair `execution_layer.py`**
  - **Target**: `f:\TradeBot\execution_layer.py`
  - **Action**: Check if file is whitespace-only. If corrupted, restore from `core/signals.py` and `platforms/mt5_adapter.py` logic (template restoration).
  - **Verification**: `python -m py_compile f:\TradeBot\execution_layer.py`

- [ ] **TASK 1.2: Restore `strategy.py` Core Logic**
  - **Target**: `f:\TradeBot\strategy.py`
  - **Action**: Re-implement the `StrategyManager` class to interface with `GodModeEngine`.
  - **Verification**: Check for class definition `class StrategyManager:`.

- [ ] **TASK 1.3: Validate SQLite Schema**
  - **Target**: `f:\TradeBot\said alalawi.db`
  - **Action**: Run `sqlite3 "said alalawi.db" "PRAGMA table_info(signals);"`
  - **Verification**: Ensure columns `id`, `symbol`, `direction`, `entry`, `tp`, `sl`, `outcome` exist.

## 2. Backend Optimization (Cortex & Core)
Refining the intelligence and risk modules.

- [ ] **TASK 2.1: Enhance `cortex/optimizer.py`**
  - **Target**: `f:\TradeBot\cortex\optimizer.py`
  - **Action**: Update `analyze_performance` to include Sharpe Ratio calculation using `pandas_ta`.
  - **Logic**: `sharpe = (returns.mean() / returns.std()) * sqrt(252)`

- [ ] **TASK 2.2: Bridge GodMode to MT5**
  - **Target**: `f:\TradeBot\main.py`
  - **Action**: Ensure `MarketBot` correctly dispatches `GodModeEngine` signals to `MT5Adapter.place_order`.
  - **Verification**: Run `python main.py` in test mode and look for "Signal Dispatched" in logs.

## 3. Institutional UI Overhaul (Elirox Style)
Transforming the dashboard into a premium experience.

- [ ] **TASK 3.1: CSS Token System**
  - **Target**: `f:\TradeBot\web\style.css` (NEW)
  - **Action**: Define CSS variables for:
    ```css
    :root {
      --bg-dark: #050505;
      --glass-bg: rgba(255, 255, 255, 0.05);
      --accent-neon: #00FFA3;
      --font-main: 'Inter', sans-serif;
    }
    ```

- [ ] **TASK 3.2: Glassmorphic Component Library**
  - **Target**: `f:\TradeBot\web\index.html`
  - **Action**: Rewrite the dashboard container using `backdrop-filter: blur(10px)`.
  - **Feature**: Add a "Live Heatmap" section using SVG gradients.

- [ ] **TASK 3.3: WebSocket Latency Optimization**
  - **Target**: `f:\TradeBot\web_server.py`
  - **Action**: Reduce `broadcast_data` sleep interval to `0.1s` for high-frequency updates.

## 4. Multi-Platform Deployment
Automating the distribution pipeline.

- [ ] **TASK 4.1: Update GitHub Action for Node 24**
  - **Target**: `f:\TradeBot\.github\workflows\multi_platform_deploy.yml`
  - **Action**: Set `node-version: 24` and update `actions/setup-node@v4`.
  - **Verification**: Trigger a manual run and check for build success on Windows/iOS runners.

---

## Verification Suite (Run after all tasks)
```powershell
# 1. Syntax Check
python -m compileall .

# 2. Server Boot
uvicorn web_server:app --port 8000 --reload

# 3. Database Check
sqlite3 "said alalawi.db" "SELECT COUNT(*) FROM signals;"
```
