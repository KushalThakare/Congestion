/* ==========================================================================
   GLOBAL VARIABLES & CHART CONFIGURATION
   ========================================================================== */
let socket = null;
let mode = 'live';
let isRunning = false;
let threshold = 0.50;

// Rolling data buffers
const maxHistory = 50;
let packetCount = 0;
let congestedCount = 0;
const probHistory = [];
const labelsHistory = [];
const timeHistory = [];

// DOM Elements
const tsharkPathInput = document.getElementById('tshark-path');
const networkIfaceInput = document.getElementById('network-interface');
const sliderThreshold = document.getElementById('threshold-slider');
const valThreshold = document.getElementById('threshold-val');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const connDot = document.getElementById('conn-dot');
const connText = document.getElementById('conn-text');
const alertBanner = document.getElementById('alert-banner');
const terminalBody = document.getElementById('terminal-body');
const btnClearTerminal = document.getElementById('btn-clear-terminal');

// Stat Card elements
const statTotal = document.getElementById('stat-total');
const statRate = document.getElementById('stat-rate');
const statFlagged = document.getElementById('stat-flagged');
const statAvg = document.getElementById('stat-avg');
const statLast = document.getElementById('stat-last');
const statLastLabel = document.getElementById('stat-last-label');
const statRto = document.getElementById('stat-rto');
const statRtt = document.getElementById('stat-rtt');

// Color schemes - Nordic Minimalist
const colors = {
    sage: '#5c7f76',
    crimson: '#cc4e4e',
    forest: '#3ea06b',
    amber: '#d9822b',
    fjord: '#446e8c',
    gray: '#8d9891',
    greyLight: '#e5e2d9',
    border: '#e5e2d9'
};

/* ==========================================================================
   INITIALIZE CHARTS
   ========================================================================== */
// Chart.js Default styling overriding
Chart.defaults.color = '#606863';
Chart.defaults.font.family = "'Outfit', sans-serif";

// 1. Timeline Line Chart
const ctxTimeline = document.getElementById('timelineChart').getContext('2d');
const timelineChart = new Chart(ctxTimeline, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Congestion Probability',
            data: [],
            borderColor: colors.sage,
            borderWidth: 2.5,
            pointRadius: 0,
            fill: true,
            backgroundColor: 'rgba(92, 127, 118, 0.05)',
            tension: 0.15
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: colors.border },
                ticks: { font: { family: "'Space Mono', monospace", size: 9 } }
            },
            y: {
                min: 0,
                max: 1,
                grid: { color: colors.border },
                ticks: { stepSize: 0.2, font: { family: "'Space Mono', monospace", size: 9 } }
            }
        }
    }
});

// 2. Horizontal Feature Bar Chart
const ctxFeatures = document.getElementById('featuresChart').getContext('2d');
const featuresChart = new Chart(ctxFeatures, {
    type: 'bar',
    data: {
        labels: ['Packet Size (B)', 'RTO (ms)', 'Retransmissions', 'Window Size (KB)', 'Rate (pkts/s)', 'RTT (ms)'],
        datasets: [{
            data: [0, 0, 0, 0, 0, 0],
            backgroundColor: [colors.fjord, colors.sage, colors.amber, colors.crimson, colors.sage, colors.crimson],
            borderRadius: 4,
            barThickness: 12
        }]
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: colors.border },
                ticks: { display: false }
            },
            y: {
                grid: { display: false },
                ticks: { font: { size: 10 } }
            }
        }
    }
});

// 3. Doughnut Probability Gauge
const ctxGauge = document.getElementById('gaugeChart').getContext('2d');
const gaugeChart = new Chart(ctxGauge, {
    type: 'doughnut',
    data: {
        labels: ['Congested', 'Normal'],
        datasets: [{
            data: [0, 100],
            backgroundColor: [colors.crimson, colors.greyLight],
            borderWidth: 0,
            circumference: 180,
            rotation: 270,
            cutout: '80%'
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        }
    }
});

/* ==========================================================================
   UI CONTROLS & STATE INTERACTION
   ========================================================================== */


// Threshold Slider
sliderThreshold.addEventListener('input', (e) => {
    threshold = parseFloat(e.target.value);
    valThreshold.innerText = threshold.toFixed(2);
    
    // Send threshold update to backend if connected
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: 'set_threshold',
            threshold: threshold
        }));
    }
});

// Start button
btnStart.addEventListener('click', () => {
    if (isRunning) return;
    startCapture();
});

// Stop button
btnStop.addEventListener('click', () => {
    if (!isRunning) return;
    stopCapture();
});

// Clear log
btnClearTerminal.addEventListener('click', () => {
    terminalBody.innerHTML = '';
});

/* ==========================================================================
   WEBSOCKETS & DATA FLOW
   ========================================================================== */
function connectWebSocket() {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        connDot.className = 'dot dot-ok';
        connText.innerText = 'Connected';
        appendLog('[SYSTEM] Socket connection established.', 'error');
    };
    
    socket.onclose = () => {
        connDot.className = 'dot dot-error';
        connText.innerText = 'Disconnected';
        appendLog('[SYSTEM] Socket connection lost.', 'error');
        if (isRunning) {
            handleSystemStop();
        }
        // Auto-reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };
    
    socket.onerror = (err) => {
        console.error('WebSocket Error:', err);
    };
    
    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'packet') {
            processPacket(msg);
        } else if (msg.type === 'status') {
            handleStatusUpdate(msg);
        } else if (msg.type === 'error') {
            appendLog(`[ERROR] ${msg.message}`, 'error');
            stopCapture();
        }
    };
}

function startCapture() {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        appendLog('[SYSTEM] Cannot start: WebSockets not connected.', 'error');
        return;
    }
    
    // Clear previous simulation run stats
    resetStats();
    
    const config = {
        action: 'start',
        mode: mode,
        threshold: threshold,
        tshark_path: tsharkPathInput.value,
        interface: networkIfaceInput.value
    };
    
    socket.send(JSON.stringify(config));
}

function stopCapture() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: 'stop' }));
    }
}

function handleStatusUpdate(msg) {
    if (msg.running) {
        isRunning = true;
        btnStart.disabled = true;
        btnStop.disabled = false;
        tsharkPathInput.disabled = true;
        networkIfaceInput.disabled = true;
        
        statusDot.className = 'dot dot-running';
        statusText.innerText = 'Capturing Live';
        
        alertBanner.className = 'alert-box alert-healthy';
        alertBanner.innerText = 'Scanning network packets. Pipeline active...';
        appendLog(`[SYSTEM] Started in ${mode} mode.`, 'normal');
    } else {
        handleSystemStop();
    }
}

function handleSystemStop() {
    isRunning = false;
    btnStart.disabled = false;
    btnStop.disabled = true;
    tsharkPathInput.disabled = false;
    networkIfaceInput.disabled = false;
    
    statusDot.className = 'dot dot-idle';
    statusText.innerText = 'System Idle';
    
    alertBanner.className = 'alert-box alert-idle';
    alertBanner.innerText = 'System is idle. Click "Start Analysis" to begin capturing.';
    appendLog('[SYSTEM] Stopped monitoring.', 'error');
}

function resetStats() {
    packetCount = 0;
    congestedCount = 0;
    probHistory.length = 0;
    labelsHistory.length = 0;
    timeHistory.length = 0;
    
    statTotal.innerText = '0';
    statRate.innerText = '0.0%';
    statFlagged.innerText = '0 packets flagged';
    statAvg.innerText = '0.000';
    statLast.innerText = '0.000';
    statLastLabel.innerText = 'No data yet';
    statRto.innerHTML = '0 <span class="stat-unit">ms</span>';
    statRtt.innerHTML = '0 <span class="stat-unit">ms</span>';
    
    // Clear charts
    timelineChart.data.labels = [];
    timelineChart.data.datasets[0].data = [];
    timelineChart.update();
    
    gaugeChart.data.datasets[0].data = [0, 100];
    gaugeChart.update();
    
    featuresChart.data.datasets[0].data = [0, 0, 0, 0, 0, 0];
    featuresChart.update();
}

/* ==========================================================================
   STATISTICAL PROCESSING & DATA PRESENTATION
   ========================================================================== */
function processPacket(msg) {
    const pkt = msg.data;
    const prob = msg.probability;
    const label = msg.label;
    const timestamp = msg.timestamp;
    
    packetCount++;
    if (label === 1) {
        congestedCount++;
    }
    
    // Save to history buffers
    probHistory.push(prob);
    labelsHistory.push(label);
    timeHistory.push(timestamp);
    
    if (probHistory.length > maxHistory) {
        probHistory.shift();
        labelsHistory.shift();
        timeHistory.shift();
    }
    
    // Update core statistics display
    statTotal.innerText = packetCount.toLocaleString();
    
    const rate = (congestedCount / packetCount) * 100;
    statRate.innerText = `${rate.toFixed(1)}%`;
    statFlagged.innerText = `${congestedCount.toLocaleString()} packets flagged`;
    
    const sum = probHistory.reduce((a, b) => a + b, 0);
    const avg = sum / probHistory.length;
    statAvg.innerText = avg.toFixed(3);
    
    statLast.innerText = prob.toFixed(3);
    statLastLabel.innerText = label === 1 ? 'CONGESTED' : 'NORMAL';
    
    // Colors of indicator state card
    const lastCard = document.getElementById('card-last');
    const rateCard = document.getElementById('card-rate');
    
    if (label === 1) {
        lastCard.className = 'stat-card c-purple';
        statLastLabel.style.color = colors.crimson;
    } else {
        lastCard.className = 'stat-card c-green';
        statLastLabel.style.color = colors.forest;
    }
    
    // Colors for average congestion rate
    const windowCongestionRate = labelsHistory.reduce((a, b) => a + b, 0) / labelsHistory.length;
    if (windowCongestionRate > 0.6) {
        rateCard.className = 'stat-card c-purple';
        alertBanner.className = 'alert-box alert-danger';
        alertBanner.innerText = 'CRITICAL CONGESTION DETECTED — Heavy load on connection.';
    } else if (windowCongestionRate > 0.3) {
        rateCard.className = 'stat-card c-yellow';
        alertBanner.className = 'alert-box alert-warning';
        alertBanner.innerText = 'ELEVATED NETWORK CONGESTION — Queueing delay observed.';
    } else {
        rateCard.className = 'stat-card c-green';
        alertBanner.className = 'alert-box alert-healthy';
        alertBanner.innerText = 'NETWORK HEALTHY — Latency and queue sizes within baseline parameters.';
    }
    
    // Set network metrics
    statRto.innerHTML = `${pkt.rto.toFixed(0)} <span class="stat-unit">ms</span>`;
    statRtt.innerHTML = `${pkt.rtt.toFixed(0)} <span class="stat-unit">ms</span>`;
    
    // Update Timeline Chart
    timelineChart.data.labels = timeHistory;
    timelineChart.data.datasets[0].data = probHistory;
    // Highlight points above threshold in crimson
    timelineChart.data.datasets[0].pointBackgroundColor = probHistory.map(p => p >= threshold ? colors.crimson : colors.sage);
    timelineChart.data.datasets[0].pointRadius = probHistory.map(p => p >= threshold ? 3 : 0);
    timelineChart.update('none'); // Update without animation for performance
    
    // Update Gauge Chart
    const probPct = prob * 100;
    gaugeChart.data.datasets[0].data = [probPct, 100 - probPct];
    gaugeChart.data.datasets[0].backgroundColor = [prob >= threshold ? colors.crimson : colors.sage, colors.greyLight];
    gaugeChart.update('none');
    
    // Update Features Chart
    // Normalize window size to KB, packet size to bytes, retransmissions, RTO, rate, rtt
    const normalizedData = [
        pkt.packet_size,
        pkt.rto,
        pkt.retransmission * 100, // amplify retransmissions to make them visible on bar
        pkt.window_size / 1024,
        pkt.packet_rate,
        pkt.rtt
    ];
    featuresChart.data.datasets[0].data = normalizedData;
    featuresChart.update('none');
    
    // Append to Terminal Log
    const labelStr = label === 1 ? 'CONGESTED' : 'NORMAL';
    const logClass = label === 1 ? 'congested' : 'normal';
    const logText = `[${timestamp}] ${labelStr} | size=${pkt.packet_size.toFixed(0)}B | rto=${pkt.rto.toFixed(0)}ms | win=${pkt.window_size.toFixed(0)} | rate=${pkt.packet_rate.toFixed(0)}pkts/s | rtt=${pkt.rtt.toFixed(0)}ms | prob=${prob.toFixed(3)}`;
    appendLog(logText, logClass);
}

function appendLog(text, className) {
    const row = document.createElement('div');
    row.className = `terminal-row ${className}`;
    row.innerText = text;
    terminalBody.appendChild(row);
    terminalBody.scrollTop = terminalBody.scrollHeight;
}

// Connect immediately on page load
connectWebSocket();
