// State variables for the application
let activeCoin = 'bitcoin';
let priceChart = null;
let pipelineData = {};

// Selectors for DOM elements
const latestPriceEl = document.getElementById('latest-price');
const priceUpdatedEl = document.getElementById('price-updated');
const rollingAvgEl = document.getElementById('rolling-avg');
const latestDeviationEl = document.getElementById('latest-deviation');
const deviationStatusEl = document.getElementById('deviation-status');
const logsTableBody = document.getElementById('logs-table-body');
const coinSelectorEl = document.getElementById('coin-selector');

// 1. Fetch data from the exported JSON file
async function loadPipelineData() {
    try {
        // Fetch the prices.json file relative to index.html
        const response = await fetch('prices.json');
        if (!response.ok) {
            throw new Error(`Failed to load prices.json: Status ${response.status}`);
        }
        
        pipelineData = await response.json();
        
        // Render dashboard elements with the new data
        updateDashboard();
        
    } catch (error) {
        console.error("[Dashboard] Error fetching pipeline data:", error);
        logsTableBody.innerHTML = `
            <tr>
                <td colspan="4" class="no-data" style="color: var(--accent-red)">
                    Error reading data. Make sure the Python pipeline has run at least once to generate 'prices.json' and you are running a local web server.
                </td>
            </tr>
        `;
    }
}

// 2. Main renderer function
function updateDashboard() {
    const coinRecords = pipelineData[activeCoin] || [];
    
    if (coinRecords.length === 0) {
        // Handle empty database case
        latestPriceEl.innerText = "$0.00";
        priceUpdatedEl.innerText = "No records found";
        rollingAvgEl.innerText = "$0.00";
        latestDeviationEl.innerText = "0.00%";
        latestDeviationEl.style.color = "var(--text-primary)";
        deviationStatusEl.innerText = "Insufficient data";
        logsTableBody.innerHTML = `<tr><td colspan="4" class="no-data">No price records found for this coin. Run the pipeline!</td></tr>`;
        if (priceChart) priceChart.destroy();
        return;
    }
    
    // Sort records chronologically (ascending) for rendering the chart
    // Our Python script already outputs chronological order, but sorting ensures correctness.
    const sortedRecords = [...coinRecords].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    // Get the most recent record (which is the last element in sortedRecords)
    const latestRecord = sortedRecords[sortedRecords.length - 1];
    
    // 3. Render Card 1: Latest Price
    latestPriceEl.innerText = formatCurrency(latestRecord.price);
    // Format UTC timestamp for readability
    const lastUpdateDate = new Date(latestRecord.timestamp + " UTC");
    priceUpdatedEl.innerText = `Updated at ${lastUpdateDate.toLocaleTimeString()}`;
    
    // 4. Calculate Rolling Average & Deviation
    // We compute the average on the last 10 normal (non-anomalous) points
    const normalRecords = sortedRecords.filter(r => r.is_anomaly === 0);
    const baselineRecords = normalRecords.slice(-10); // get last 10 normal records
    
    if (baselineRecords.length > 0) {
        const sum = baselineRecords.reduce((acc, r) => acc + r.price, 0);
        const avg = sum / baselineRecords.length;
        rollingAvgEl.innerText = formatCurrency(avg);
        
        // Calculate deviation percentage
        const deviation = ((latestRecord.price - avg) / avg) * 100;
        latestDeviationEl.innerText = `${deviation >= 0 ? '+' : ''}${deviation.toFixed(2)}%`;
        
        // Update color and text based on status
        if (latestRecord.is_anomaly === 1) {
            latestDeviationEl.style.color = "var(--accent-red)";
            deviationStatusEl.innerText = "⚠️ Anomaly Detected!";
            deviationStatusEl.style.color = "var(--accent-red)";
        } else {
            latestDeviationEl.style.color = deviation >= 0 ? "var(--accent-green)" : "var(--accent-blue)";
            deviationStatusEl.innerText = "Within normal range";
            deviationStatusEl.style.color = "var(--text-secondary)";
        }
    } else {
        rollingAvgEl.innerText = "N/A";
        latestDeviationEl.innerText = "N/A";
        deviationStatusEl.innerText = "Awaiting baseline records";
    }
    
    // 5. Render Chart
    renderChart(sortedRecords);
    
    // 6. Render Data Log Table (Newest records first)
    const tableRecords = [...sortedRecords].reverse();
    logsTableBody.innerHTML = tableRecords.map(record => {
        const recordDate = new Date(record.timestamp + " UTC");
        const statusBadge = record.is_anomaly === 1 
            ? `<span class="badge anomaly">Anomaly</span>` 
            : `<span class="badge normal">Normal</span>`;
        const anomalyType = record.is_anomaly === 1 
            ? `<span style="color: var(--accent-red); font-weight: bold;">${record.price > (parseFloat(rollingAvgEl.innerText.replace(/[^0-9.]/g, '')) || record.price) ? 'SPIKE' : 'DIP'}</span>` 
            : `<span style="color: var(--text-secondary);">-</span>`;
            
        return `
            <tr>
                <td>${recordDate.toLocaleString()}</td>
                <td><strong>${formatCurrency(record.price)}</strong></td>
                <td>${statusBadge}</td>
                <td>${anomalyType}</td>
            </tr>
        `;
    }).join('');
}

// 7. Chart.js Plotting function
function renderChart(records) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    // Map timestamps to simpler labels (e.g. HH:MM:SS)
    const labels = records.map(r => {
        const d = new Date(r.timestamp + " UTC");
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    
    const prices = records.map(r => r.price);
    
    // Set custom dot colors and sizes for anomalies
    const pointBackgroundColors = records.map(r => r.is_anomaly === 1 ? '#f85149' : '#58a6ff');
    const pointBorderColors = records.map(r => r.is_anomaly === 1 ? '#ff7b72' : '#2188ff');
    const pointRadius = records.map(r => r.is_anomaly === 1 ? 7 : 3);
    const pointHoverRadius = records.map(r => r.is_anomaly === 1 ? 9 : 5);
    
    // If a chart already exists, destroy it before creating a new one to prevent overlay bugs
    if (priceChart) {
        priceChart.destroy();
    }
    
    // Create new line chart
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: `${activeCoin.toUpperCase()} Price (USD)`,
                data: prices,
                borderColor: '#58a6ff',
                borderWidth: 2,
                backgroundColor: 'rgba(88, 166, 255, 0.05)',
                fill: true,
                tension: 0.15,
                pointBackgroundColor: pointBackgroundColors,
                pointBorderColor: pointBorderColors,
                pointRadius: pointRadius,
                pointHoverRadius: pointHoverRadius,
                pointBorderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false // We use our own HTML legend
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += formatCurrency(context.parsed.y);
                            
                            // Check if this data point was flagged as an anomaly
                            const index = context.dataIndex;
                            if (records[index].is_anomaly === 1) {
                                label += ' 🚨 [ANOMALY DETECTED]';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(48, 54, 61, 0.3)'
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            family: 'Outfit'
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(48, 54, 61, 0.3)'
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            family: 'Outfit'
                        },
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Helper: Format number into USD currency text
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: value < 100 ? 4 : 2,
        maximumFractionDigits: value < 100 ? 4 : 2
    }).format(value);
}

// 8. Event Listener for coin selection buttons
coinSelectorEl.addEventListener('click', (e) => {
    // Traverse up to find the button if clicked inside child span
    const btn = e.target.closest('.selector-btn');
    if (!btn) return;
    
    // Toggle active state
    document.querySelectorAll('.selector-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // Update active coin state and redraw
    activeCoin = btn.dataset.coin;
    updateDashboard();
});

// 9. Startup Operations
loadPipelineData();

// Poll prices.json file every 30 seconds for real-time updates
setInterval(loadPipelineData, 30000);
