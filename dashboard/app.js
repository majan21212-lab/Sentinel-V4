const API_TOKEN = 'sentinel_debug_key';
const POLL_INTERVAL = 3000;

const botStatus = document.getElementById('bot-status');
const totalEquity = document.getElementById('total-equity');
const dailyPnl = document.getElementById('daily-pnl');
const signalsList = document.getElementById('signals-list');
const killBtn = document.getElementById('kill-switch');

async function apiFetch(endpoint, method = 'GET', body = None) {
    const headers = {
        'X-Token': API_TOKEN,
        'Content-Type': 'application/json'
    };
    
    try {
        const response = await fetch(endpoint, {
            method,
            headers,
            body: body ? JSON.stringify(body) : null
        });
        if (!response.ok) throw new Error('API Error');
        return await response.json();
    } catch (err) {
        console.error(err);
        return null;
    }
}

async function updateDashboard() {
    // 1. Get Status
    const status = await apiFetch('/status');
    if (status) {
        botStatus.classList.add('online');
        botStatus.querySelector('.status-text').innerText = 'ONLINE';
    } else {
        botStatus.classList.remove('online');
        botStatus.querySelector('.status-text').innerText = 'OFFLINE';
    }

    // 2. Get Account
    const account = await apiFetch('/account');
    if (account) {
        // Find the first platform's equity for demo
        const firstPlatform = Object.values(account)[0];
        if (firstPlatform && !firstPlatform.error) {
            const total = firstPlatform.total?.USDT || firstPlatform.equity || 0;
            totalEquity.innerText = `$${parseFloat(total).toLocaleString()}`;
        }
    }

    // 3. Get History
    const signals = await apiFetch('/history?limit=10');
    if (signals) {
        signalsList.innerHTML = signals.length ? '' : '<div class="placeholder">No signals yet.</div>';
        signals.forEach(sig => {
            const item = document.createElement('div');
            item.className = 'signal-item';
            item.innerHTML = `
                <div class="signal-info">
                    <h4>${sig.symbol}</h4>
                    <p>${new Date(sig.timestamp).toLocaleTimeString()}</p>
                </div>
                <div class="direction ${sig.direction}">${sig.direction}</div>
            `;
            signalsList.appendChild(item);
        });
    }
}

killBtn.addEventListener('click', async () => {
    if (confirm('🚨 ARE YOU SURE YOU WANT TO KILL ALL TRADES?')) {
        // Implement kill logic in API if needed
        alert('Emergency Stop Signal Sent!');
    }
});

// Initial Load & Loop
updateDashboard();
setInterval(updateDashboard, POLL_INTERVAL);
