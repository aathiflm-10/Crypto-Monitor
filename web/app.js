// State variables for the application
let activeCoin = '';
let priceChart = null;

// Selectors for DOM elements
const latestPriceEl = document.getElementById('latest-price');
const priceUpdatedEl = document.getElementById('price-updated');
const rollingAvgEl = document.getElementById('rolling-avg');
const latestDeviationEl = document.getElementById('latest-deviation');
const deviationStatusEl = document.getElementById('deviation-status');
const logsTableBody = document.getElementById('logs-table-body');
const coinSelectorEl = document.getElementById('coin-selector');

// Admin panel selectors
const activeCoinsListEl = document.getElementById('active-coins-list');
const subscribersListEl = document.getElementById('subscribers-list');
const addCoinForm = document.getElementById('add-coin-form');
const subscribeForm = document.getElementById('subscribe-form');
const unsubscribeBtn = document.getElementById('unsubscribe-btn');

// Base API URL (empty because page is served from same server root)
const API_BASE = "";

// 1. Initial Page Load & Event Handlers
document.addEventListener("DOMContentLoaded", () => {
    // Load dynamic settings directories
    loadTrackedCoins();
    loadSubscribers();
    
    // Auto refresh data every 30 seconds
    setInterval(refreshActiveCoinData, 30000);
    setInterval(loadSubscribers, 30000);
    
    // Add Coin form listener
    addCoinForm.addEventListener("submit", handleAddCoin);
    
    // Subscribe form listener
    subscribeForm.addEventListener("submit", handleSubscribe);
    
    // Unsubscribe button listener
    unsubscribeBtn.addEventListener("click", handleUnsubscribe);
});

// 2. Fetch tracked coins and update asset selectors
async function loadTrackedCoins() {
    try {
        const response = await fetch(`${API_BASE}/api/coins`);
        if (!response.ok) throw new Error("Failed to load tracked coins.");
        const coins = await response.json();
        
        // Render Selector Buttons in sidebar
        renderSelectorButtons(coins);
        
        // Render Administration active list in sidebar
        renderActiveCoinsList(coins);
        
        // Set default active coin if not set yet, or if previous active coin was deleted
        if (coins.length > 0) {
            const stillExists = coins.some(c => c.coin_id === activeCoin);
            if (!activeCoin || !stillExists) {
                // Default to first coin in list
                setActiveCoin(coins[0].coin_id);
            } else {
                // If it still exists, just refresh its data
                refreshActiveCoinData();
            }
        } else {
            activeCoin = '';
            clearDashboardData();
        }
    } catch (error) {
        console.error("[App] Error loading tracked coins:", error);
    }
}

// 3. Render asset selection buttons
function renderSelectorButtons(coins) {
    if (coins.length === 0) {
        coinSelectorEl.innerHTML = `<div class="no-data">No assets tracked. Add one below!</div>`;
        return;
    }
    
    coinSelectorEl.innerHTML = coins.map(coin => {
        const isActive = coin.coin_id === activeCoin ? 'active' : '';
        let icon = '🪙';
        if (coin.coin_id === 'bitcoin') icon = '₿';
        else if (coin.coin_id === 'ethereum') icon = 'Ξ';
        else if (coin.coin_id === 'solana') icon = '☀️';
        
        return `
            <button class="selector-btn ${isActive}" data-coin="${coin.coin_id}">
                <span class="coin-icon">${icon}</span> ${coin.coin_symbol} (${coin.coin_id})
            </button>
        `;
    }).join('');
    
    // Attach listener to new buttons
    document.querySelectorAll('.selector-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const coinId = e.currentTarget.dataset.coin;
            setActiveCoin(coinId);
        });
    });
}

// Set active coin and trigger fetch
function setActiveCoin(coinId) {
    activeCoin = coinId;
    
    // Update active class on buttons
    document.querySelectorAll('.selector-btn').forEach(btn => {
        if (btn.dataset.coin === coinId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    refreshActiveCoinData();
}

// 4. Render Admin active tracking list
function renderActiveCoinsList(coins) {
    if (coins.length === 0) {
        activeCoinsListEl.innerHTML = `<li>No active assets</li>`;
        return;
    }
    
    activeCoinsListEl.innerHTML = coins.map(coin => `
        <li>
            <span><strong>${coin.coin_symbol}</strong> (${coin.coin_id})</span>
            <button class="delete-btn" data-coin="${coin.coin_id}" title="Stop tracking">🗑️</button>
        </li>
    `).join('');
    
    // Attach deletion listeners
    activeCoinsListEl.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const coinId = e.currentTarget.dataset.coin;
            handleDeleteCoin(coinId);
        });
    });
}

// 5. Fetch and Render Price histories for Active Coin
async function refreshActiveCoinData() {
    if (!activeCoin) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/prices/${activeCoin}`);
        if (!response.ok) throw new Error(`Failed to load prices for ${activeCoin}`);
        const sortedRecords = await response.json(); // API already returns chronological list
        
        updateMetricsAndChart(sortedRecords);
    } catch (error) {
        console.error(`[App] Error updating dashboard for ${activeCoin}:`, error);
    }
}

function updateMetricsAndChart(sortedRecords) {
    if (sortedRecords.length === 0) {
        clearDashboardData("No price logs registered. Wait for next schedule fetch.");
        return;
    }
    
    // Latest record is the last element
    const latestRecord = sortedRecords[sortedRecords.length - 1];
    
    // Render Latest Price Card
    latestPriceEl.innerText = formatCurrency(latestRecord.price);
    const lastUpdateDate = new Date(latestRecord.timestamp + " UTC");
    priceUpdatedEl.innerText = `Updated at ${lastUpdateDate.toLocaleTimeString()}`;
    
    // Calculate rolling average of the last 10 normal records (preventing baseline poisoning!)
    const normalRecords = sortedRecords.filter(r => r.is_anomaly === 0);
    const baselineRecords = normalRecords.slice(-10);
    
    if (baselineRecords.length > 0) {
        const sum = baselineRecords.reduce((acc, r) => acc + r.price, 0);
        const avg = sum / baselineRecords.length;
        rollingAvgEl.innerText = formatCurrency(avg);
        
        // Deviation percentage
        const deviation = ((latestRecord.price - avg) / avg) * 100;
        latestDeviationEl.innerText = `${deviation >= 0 ? '+' : ''}${deviation.toFixed(2)}%`;
        
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
    
    // Render Line Chart
    renderChart(sortedRecords, rollingAvgEl.innerText);
    
    // Render Data Log Table (Newest first)
    const tableRecords = [...sortedRecords].reverse();
    logsTableBody.innerHTML = tableRecords.map(record => {
        const recordDate = new Date(record.timestamp + " UTC");
        const statusBadge = record.is_anomaly === 1 
            ? `<span class="badge anomaly">Anomaly</span>` 
            : `<span class="badge normal">Normal</span>`;
            
        // Calculate dynamic label
        const avgValue = parseFloat(rollingAvgEl.innerText.replace(/[^0-9.]/g, '')) || record.price;
        const anomalyType = record.is_anomaly === 1 
            ? `<span style="color: var(--accent-red); font-weight: bold;">${record.price > avgValue ? 'SPIKE' : 'DIP'}</span>` 
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

// 6. Chart.js Plotting
function renderChart(records, rollingAvgText) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    const labels = records.map(r => {
        const d = new Date(r.timestamp + " UTC");
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    
    const prices = records.map(r => r.price);
    const pointBackgroundColors = records.map(r => r.is_anomaly === 1 ? '#f85149' : '#58a6ff');
    const pointBorderColors = records.map(r => r.is_anomaly === 1 ? '#ff7b72' : '#2188ff');
    const pointRadius = records.map(r => r.is_anomaly === 1 ? 7 : 3);
    
    if (priceChart) {
        priceChart.destroy();
    }
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: `${activeCoin.toUpperCase()} Price`,
                data: prices,
                borderColor: '#58a6ff',
                borderWidth: 2,
                backgroundColor: 'rgba(88, 166, 255, 0.05)',
                fill: true,
                tension: 0.15,
                pointBackgroundColor: pointBackgroundColors,
                pointBorderColor: pointBorderColors,
                pointRadius: pointRadius,
                pointHoverRadius: 9,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = formatCurrency(context.parsed.y);
                            if (records[context.dataIndex].is_anomaly === 1) {
                                label += ' 🚨 [ANOMALY]';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(48, 54, 61, 0.2)' },
                    ticks: { color: '#8b949e', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(48, 54, 61, 0.2)' },
                    ticks: {
                        color: '#8b949e',
                        font: { family: 'Outfit' },
                        callback: formatCurrency
                    }
                }
            }
        }
    });
}

// 7. Dynamic Actions: Add / Delete Coins
async function handleAddCoin(e) {
    e.preventDefault();
    const idInput = document.getElementById('new-coin-id');
    const symbolInput = document.getElementById('new-coin-symbol');
    
    const coin_id = idInput.value.trim().toLowerCase();
    const coin_symbol = symbolInput.value.trim().toUpperCase();
    
    if (!coin_id || !coin_symbol) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/coins`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coin_id, coin_symbol })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to add asset.");
        
        // Reset form inputs
        idInput.value = '';
        symbolInput.value = '';
        
        // Reload selectors and make the newly added coin active
        activeCoin = coin_id;
        loadTrackedCoins();
        
    } catch (error) {
        alert(`Error adding asset: ${error.message}`);
    }
}

async function handleDeleteCoin(coinId) {
    if (!confirm(`Are you sure you want to stop tracking ${coinId.toUpperCase()}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/coins/${coinId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to delete asset.");
        
        // Reload list
        loadTrackedCoins();
    } catch (error) {
        alert(`Error removing asset: ${error.message}`);
    }
}

// 8. Dynamic Actions: Manage alert subscriptions
async function loadSubscribers() {
    try {
        const response = await fetch(`${API_BASE}/api/subscribers`);
        if (!response.ok) throw new Error("Failed to load subscriber list.");
        const subscribers = await response.json();
        
        renderSubscribersList(subscribers);
    } catch (error) {
        console.error("[App] Error loading subscribers:", error);
    }
}

function renderSubscribersList(subscribers) {
    if (subscribers.length === 0) {
        subscribersListEl.innerHTML = `<li>No active subscribers</li>`;
        return;
    }
    
    subscribersListEl.innerHTML = subscribers.map(email => `
        <li>
            <span>📧 ${email}</span>
        </li>
    `).join('');
}

async function handleSubscribe(e) {
    e.preventDefault();
    const emailInput = document.getElementById('subscriber-email');
    const email = emailInput.value.trim().toLowerCase();
    
    if (!email) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/subscribers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to subscribe.");
        
        emailInput.value = '';
        loadSubscribers();
        alert(`Subscribed successfully: ${email}`);
    } catch (error) {
        alert(`Error subscribing: ${error.message}`);
    }
}

async function handleUnsubscribe() {
    const emailInput = document.getElementById('subscriber-email');
    const email = emailInput.value.trim().toLowerCase();
    
    if (!email) {
        alert("Please enter your email address to unsubscribe.");
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/subscribers/${email}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to unsubscribe.");
        
        emailInput.value = '';
        loadSubscribers();
        alert(`Unsubscribed successfully: ${email}`);
    } catch (error) {
        alert(`Error unsubscribing: ${error.message}`);
    }
}

// 9. UI Helper Methods
function clearDashboardData(message = "No price logs available.") {
    latestPriceEl.innerText = "$0.00";
    priceUpdatedEl.innerText = "-";
    rollingAvgEl.innerText = "$0.00";
    latestDeviationEl.innerText = "0.00%";
    latestDeviationEl.style.color = "var(--text-primary)";
    deviationStatusEl.innerText = "Awaiting data";
    logsTableBody.innerHTML = `<tr><td colspan="4" class="no-data">${message}</td></tr>`;
    if (priceChart) {
        priceChart.destroy();
        priceChart = null;
    }
}

function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: value < 10 ? 4 : 2,
        maximumFractionDigits: value < 10 ? 4 : 2
    }).format(value);
}
