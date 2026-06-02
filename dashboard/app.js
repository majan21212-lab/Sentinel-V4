// Lightweight Charts Setup
const chartOptions = {
    layout: {
        background: { color: '#0d1117' },
        textColor: '#c9d1d9',
        fontSize: 12,
    },
    grid: {
        vertLines: { color: '#30363d' },
        horzLines: { color: '#30363d' },
    },
    crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
        borderColor: '#30363d',
    },
    timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
    },
};

const chartContainer = document.getElementById('chart-container');
const chart = LightweightCharts.createChart(chartContainer, chartOptions);
const candlestickSeries = chart.addCandlestickSeries({
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderVisible: false,
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
});

// Technical Indicators
const sma9Series = chart.addLineSeries({ color: '#58a6ff', lineWidth: 2, title: 'SMA 9' });
const sma21Series = chart.addLineSeries({ color: '#da3633', lineWidth: 2, title: 'SMA 21' });

// RSI Chart Setup
const rsiContainer = document.getElementById('rsi-container');
const rsiChart = LightweightCharts.createChart(rsiContainer, {
    ...chartOptions,
    height: 150,
});
const rsiSeries = rsiChart.addLineSeries({ color: '#ab7fe6', lineWidth: 2, title: 'RSI' });

// Mock Generator (Simulating historical data for strategy visualization)
function generateData() {
    let price = 50000;
    let time = Math.floor(Date.now() / 1000) - 200 * 3600;
    const data = [];
    
    for (let i = 0; i < 200; i++) {
        const open = price + (Math.random() - 0.5) * 200;
        const high = open + Math.random() * 300;
        const low = open - Math.random() * 300;
        const close = (high + low) / 2 + (Math.random() - 0.5) * 100;
        
        data.push({ time: time, open, high, low, close });
        price = close;
        time += 3600;
    }
    return data;
}

// Indicator Calculation
function calculateSMA(data, period) {
    const sma = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            sma.push({ time: data[i].time, value: NaN });
            continue;
        }
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += data[i - j].close;
        }
        sma.push({ time: data[i].time, value: sum / period });
    }
    return sma.filter(d => !isNaN(d.value));
}

function calculateRSI(data, period = 14) {
    const rsi = [];
    let gains = 0;
    let losses = 0;

    for (let i = 1; i < data.length; i++) {
        const diff = data[i].close - data[i - 1].close;
        const gain = diff > 0 ? diff : 0;
        const loss = diff < 0 ? Math.abs(diff) : 0;
        
        if (i <= period) {
            gains += gain;
            losses += loss;
            if (i === period) {
                const rs = (gains / period) / (losses / period);
                rsi.push({ time: data[i].time, value: 100 - (100 / (1 + rs)) });
            } else {
                rsi.push({ time: data[i].time, value: NaN });
            }
        } else {
            gains = (gains * (period - 1) + gain) / period;
            losses = (losses * (period - 1) + loss) / period;
            const rs = gains / losses;
            rsi.push({ time: data[i].time, value: 100 - (100 / (1 + rs)) });
        }
    }
    return rsi.filter(d => !isNaN(d.value));
}

// Global variable for marker labels
const markers = [];

function runStrategy(data, sma9, sma21, rsi) {
    const signalsContainer = document.getElementById('signals-container');
    signalsContainer.innerHTML = '';
    
    for (let i = 1; i < sma9.length; i++) {
        const time = sma9[i].time;
        const currentCandle = data.find(d => d.time === time);
        const prevSma9 = sma9[i-1].value;
        const currSma9 = sma9[i].value;
        const prevSma21 = sma21.find(d => d.time === sma9[i-1].time)?.value;
        const currSma21 = sma21[i]?.value;
        const currRsi = rsi.find(d => d.time === time)?.value;

        if (!prevSma21 || !currSma21 || !currRsi) continue;

        // Long Signal: SMA Cross Up + RSI < 70
        if (prevSma9 <= prevSma21 && currSma9 > currSma21 && currRsi < 70) {
            markers.push({
                time: time,
                position: 'belowBar',
                color: '#26a69a',
                shape: 'arrowUp',
                text: 'BUY'
            });
            logSignal('LONG', currentCandle.close, time);
            drawTPSLBox(currentCandle.close, 'buy', time);
        }

        // Short Signal: SMA Cross Down + RSI > 30
        if (prevSma9 >= prevSma21 && currSma9 < currSma21 && currRsi > 30) {
            markers.push({
                time: time,
                position: 'aboveBar',
                color: '#ef5350',
                shape: 'arrowDown',
                text: 'SELL'
            });
            logSignal('SHORT', currentCandle.close, time);
            drawTPSLBox(currentCandle.close, 'sell', time);
        }
    }
    candlestickSeries.setMarkers(markers);
}

function logSignal(type, price, time) {
    const signalsContainer = document.getElementById('signals-container');
    const row = document.createElement('div');
    row.className = 'signal-row';
    const timeStr = new Date(time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    row.innerHTML = `
        <span class="signal-type-${type.toLowerCase()}">${type}</span>
        <span>$${price.toFixed(2)}</span>
        <span style="opacity: 0.5;">${timeStr}</span>
    `;
    signalsContainer.prepend(row);
}

// In the dashboard (v2), we use markers instead of complex boxes for performance, 
// But we'll display targets in the values.
function drawTPSLBox(price, type, time) {
    const tp = type === 'buy' ? price * 1.02 : price * 0.98;
    const sl = type === 'buy' ? price * 0.99 : price * 1.01;
}

// Initialization Logic
function init() {
    const rawData = generateData();
    const sma9 = calculateSMA(rawData, 9);
    const sma21 = calculateSMA(rawData, 21);
    const rsi = calculateRSI(rawData, 14);

    candlestickSeries.setData(rawData);
    sma9Series.setData(sma9);
    sma21Series.setData(sma21);
    rsiSeries.setData(rsi);

    // Sync charts
    chart.timeScale().subscribeVisibleTimeRangeChange(range => {
        rsiChart.timeScale().setVisibleRange(range);
    });

    runStrategy(rawData, sma9, sma21, rsi);
    
    // Update live metrics (last values)
    document.getElementById('val-sma9').textContent = sma9[sma9.length-1].value.toFixed(2);
    document.getElementById('val-sma21').textContent = sma21[sma21.length-1].value.toFixed(2);
    document.getElementById('val-rsi').textContent = rsi[rsi.length-1].value.toFixed(2);
}

window.addEventListener('resize', () => {
    chart.applyOptions({ width: chartContainer.clientWidth, height: chartContainer.clientHeight });
    rsiChart.applyOptions({ width: rsiContainer.clientWidth, height: rsiContainer.clientHeight });
});

document.getElementById('refresh-btn').addEventListener('click', () => {
    markers.length = 0;
    init();
});

init();
