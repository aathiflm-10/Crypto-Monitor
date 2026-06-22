// App State Machine
let currentView = 'explorer'; // 'explorer' | 'detail'
let selectedCoinId = 'bitcoin';
let chartDays = 7;
let marketCoins = []; // Stores the top 250 coins
let watchlistIds = []; // Active watchlist coin IDs from database
let mainChart = null; // Chart.js instance for detailed view
let sparklineCharts = []; // Array of active sparkline Chart instances

// API Base URL (blank since frontend is served from root)
const API_BASE = "";

// DOM Elements
const explorerView = document.getElementById('explorer-view');
const detailView = document.getElementById('detail-view');
const searchInput = document.getElementById('search-input');
const marketTableBody = document.getElementById('market-table-body');
const subscribersList = document.getElementById('subscribers-list');

// Detail Page Elements
const detailCoinImage = document.getElementById('detail-coin-image');
const detailCoinName = document.getElementById('detail-coin-name');
const detailCoinSymbol = document.getElementById('detail-coin-symbol');
const detailCoinPrice = document.getElementById('detail-coin-price');
const detailCoinPct = document.getElementById('detail-coin-pct');
const watchlistToggleBtn = document.getElementById('watchlist-toggle-btn');
const backBtn = document.getElementById('back-btn');

// Detail Subscription Elements
const subscribeCoinForm = document.getElementById('subscribe-coin-form');
const subscriberCoinEmail = document.getElementById('subscriber-coin-email');
const unsubscribeCoinBtn = document.getElementById('unsubscribe-coin-btn');
const coinSubscribersList = document.getElementById('coin-subscribers-list');

// Stats Elements
const statMarketCap = document.getElementById('stat-market-cap');
const statVolume = document.getElementById('stat-volume');
const statHigh = document.getElementById('stat-high');
const statLow = document.getElementById('stat-low');
const statSupply = document.getElementById('stat-supply');
const statMaxSupply = document.getElementById('stat-max-supply');

// 1. App Initialization
document.addEventListener("DOMContentLoaded", () => {
    // Initial fetch sequence
    loadInitialData();
    
    // Setup Search Filter listener
    searchInput.addEventListener('input', handleSearch);
    
    // Setup Navigation Listeners
    backBtn.addEventListener('click', showExplorerView);
    watchlistToggleBtn.addEventListener('click', toggleWatchlistStatus);
    
    // Setup Time Filter Buttons
    document.querySelectorAll('.time-filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.time-filter-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            chartDays = parseInt(e.currentTarget.dataset.days);
            loadDetailChart();
        });
    });
    
    // Setup Coin-Specific Email Alert Listeners
    subscribeCoinForm.addEventListener('submit', handleSubscribeCoin);
    unsubscribeCoinBtn.addEventListener('click', handleUnsubscribeCoin);
    
    // Set auto refresh intervals (2 minutes for market, 30 seconds for watchlist status/subscribers/logs)
    setInterval(loadMarketDataOnly, 120000);
    setInterval(refreshActivePanelDetails, 30000);
});

// Load everything on start
async function loadInitialData() {
    await fetchWatchlist();
    await loadMarketDataOnly();
    await loadGlobalSubscribers();
    await fetchWatchlistLogs();
}

// Background poller updates
async function refreshActivePanelDetails() {
    await fetchWatchlist();
    await loadGlobalSubscribers();
    await fetchWatchlistLogs();
    if (currentView === 'detail' && selectedCoinId) {
        // Soft refresh of the details/chart/subscribers
        loadDetailDataOnly();
    }
}

// 2. Fetch Market Explorer list (Top 250)
async function loadMarketDataOnly() {
    try {
        const response = await fetch(`${API_BASE}/api/market`);
        if (!response.ok) throw new Error("Failed to fetch market data.");
        marketCoins = await response.json();
        
        renderMarketTable(marketCoins);
    } catch (error) {
        console.error("[App] Error loading market data:", error);
    }
}

// Render market table with sparklines
function renderMarketTable(coins) {
    // Clean up previous sparkline instances to prevent memory leaks
    destroySparklines();
    
    if (coins.length === 0) {
        marketTableBody.innerHTML = `<tr><td colspan="8" class="no-data">No cryptocurrencies match your search.</td></tr>`;
        return;
    }
    
    marketTableBody.innerHTML = coins.map((coin, index) => {
        const priceChange = coin.price_change_percentage_24h || 0;
        const colorClass = priceChange >= 0 ? 'success-text' : 'danger-text';
        const sign = priceChange >= 0 ? '+' : '';
        
        return `
            <tr data-id="${coin.id}">
                <td>${coin.market_cap_rank || index + 1}</td>
                <td>
                    <div class="coin-info-cell">
                        <img class="coin-logo" src="${coin.image}" alt="${coin.name}" loading="lazy">
                        <span class="coin-name-bold">${coin.name}</span>
                        <span class="coin-symbol-dim">${coin.symbol}</span>
                    </div>
                </td>
                <td><strong>${formatCurrency(coin.current_price)}</strong></td>
                <td class="${colorClass}">${sign}${priceChange.toFixed(2)}%</td>
                <td>${formatCompact(coin.market_cap)}</td>
                <td>${formatCompact(coin.total_volume)}</td>
                <td>${formatCompact(coin.circulating_supply)} ${coin.symbol.toUpperCase()}</td>
                <td class="sparkline-col">
                    <canvas id="spark-${coin.id}" class="sparkline-canvas" width="120" height="35"></canvas>
                </td>
            </tr>
        `;
    }).join('');
    
    // Attach click listeners to rows to navigate to details
    marketTableBody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.tagName.toLowerCase() === 'canvas') return;
            const coinId = row.dataset.id;
            showDetailView(coinId);
        });
    });
    
    // Render sparklines
    coins.forEach(coin => {
        const canvas = document.getElementById(`spark-${coin.id}`);
        if (canvas && coin.sparkline_in_7d && coin.sparkline_in_7d.price) {
            renderSparkline(canvas, coin.sparkline_in_7d.price, coin.price_change_percentage_24h || 0);
        }
    });
}

// Render sparkline chart inside table cell
function renderSparkline(canvas, prices, priceChange24h) {
    const ctx = canvas.getContext('2d');
    const color = priceChange24h >= 0 ? '#3fb950' : '#f85149';
    
    // Downsample prices array if it's too dense (reduce to 30 points)
    const step = Math.ceil(prices.length / 30);
    const sampledPrices = prices.filter((_, idx) => idx % step === 0);
    
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sampledPrices.map((_, idx) => idx),
            datasets: [{
                data: sampledPrices,
                borderColor: color,
                borderWidth: 1.5,
                fill: false,
                pointRadius: 0,
                tension: 0.2
            }]
        },
        options: {
            responsive: false,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            }
        }
    });
    
    sparklineCharts.push(chart);
}

function destroySparklines() {
    sparklineCharts.forEach(c => c.destroy());
    sparklineCharts = [];
}

// 3. Search and filtering logic
function handleSearch() {
    const query = searchInput.value.toLowerCase().trim();
    if (!query) {
        renderMarketTable(marketCoins);
        return;
    }
    
    const filtered = marketCoins.filter(coin => 
        coin.name.toLowerCase().includes(query) || 
        coin.symbol.toLowerCase().includes(query)
    );
    renderMarketTable(filtered);
}

// 4. Detail View Navigation & Dynamic Ingestion
function showExplorerView() {
    currentView = 'explorer';
    detailView.style.display = 'none';
    explorerView.style.display = 'block';
    
    if (mainChart) {
        mainChart.destroy();
        mainChart = null;
    }
    
    renderMarketTable(marketCoins);
}

async function showDetailView(coinId) {
    currentView = 'detail';
    selectedCoinId = coinId;
    explorerView.style.display = 'none';
    detailView.style.display = 'block';
    
    // Reset subscription form
    subscriberCoinEmail.value = '';
    
    // Load detail info and chart
    loadDetailDataOnly();
}

async function loadDetailDataOnly() {
    const coin = marketCoins.find(c => c.id === selectedCoinId);
    if (!coin) return;
    
    // Render Statistics & Text
    detailCoinImage.src = coin.image;
    detailCoinImage.alt = coin.name;
    detailCoinName.innerText = coin.name;
    detailCoinSymbol.innerText = coin.symbol.toUpperCase();
    detailCoinPrice.innerText = formatCurrency(coin.current_price);
    
    const pct = coin.price_change_percentage_24h || 0;
    detailCoinPct.innerText = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
    detailCoinPct.className = `detail-pct-badge ${pct >= 0 ? 'success-btn' : 'danger-btn'}`;
    
    statMarketCap.innerText = formatCurrency(coin.market_cap);
    statVolume.innerText = formatCurrency(coin.total_volume);
    statHigh.innerText = formatCurrency(coin.high_24h);
    statLow.innerText = formatCurrency(coin.low_24h);
    statSupply.innerText = `${formatCompact(coin.circulating_supply)} ${coin.symbol.toUpperCase()}`;
    statMaxSupply.innerText = coin.max_supply ? `${formatCompact(coin.max_supply)} ${coin.symbol.toUpperCase()}` : 'N/A';
    
    // Sync Watchlist Button Active Class
    syncWatchlistButtonUI();
    
    // Fetch coin-specific subscribers list
    loadCoinSubscribers(selectedCoinId);
    
    // Load historical chart data
    loadDetailChart();
}

// Sync Watchlist Toggle Button State
function syncWatchlistButtonUI() {
    const isWatchlisted = watchlistIds.includes(selectedCoinId);
    if (isWatchlisted) {
        watchlistToggleBtn.innerHTML = `<span>🚨</span> Stop Monitoring`;
        watchlistToggleBtn.classList.add('active');
    } else {
        watchlistToggleBtn.innerHTML = `<span>🚨</span> Add to Alert Watchlist`;
        watchlistToggleBtn.classList.remove('active');
    }
}

// Load historical prices chart for detailed coin
async function loadDetailChart() {
    if (!selectedCoinId) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/market/chart/${selectedCoinId}?days=${chartDays}`);
        if (!response.ok) throw new Error("Failed to fetch historical chart data.");
        const chartData = await response.json();
        
        renderMainChart(chartData);
    } catch (error) {
        console.error(`[App] Error loading chart for ${selectedCoinId}:`, error);
    }
}

function renderMainChart(chartPoints) {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    const labels = chartPoints.map(p => {
        const date = new Date(p.time);
        if (chartDays === 1) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        }
    });
    
    const prices = chartPoints.map(p => p.price);
    
    if (mainChart) {
        mainChart.destroy();
    }
    
    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Price (USD)',
                data: prices,
                borderColor: '#58a6ff',
                borderWidth: 2.5,
                backgroundColor: 'rgba(88, 166, 255, 0.04)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 8
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
                            return formatCurrency(context.parsed.y);
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

// 5. Watchlist Actions (Add / Remove)
async function fetchWatchlist() {
    try {
        const response = await fetch(`${API_BASE}/api/coins`);
        if (!response.ok) throw new Error("Failed to load watchlist.");
        const watchlist = await response.json(); // Array of {coin_id, coin_symbol}
        
        watchlistIds = watchlist.map(item => item.coin_id);
    } catch (error) {
        console.error("[App] Error loading watchlist:", error);
    }
}

async function toggleWatchlistStatus() {
    const isWatchlisted = watchlistIds.includes(selectedCoinId);
    if (isWatchlisted) {
        await removeWatchlistCoin(selectedCoinId);
    } else {
        await addWatchlistCoin(selectedCoinId);
    }
}

async function addWatchlistCoin(coinId) {
    const coinObj = marketCoins.find(c => c.id === coinId);
    const symbol = coinObj ? coinObj.symbol : coinId;
    
    try {
        const response = await fetch(`${API_BASE}/api/coins`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coin_id: coinId, coin_symbol: symbol })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to add to watchlist.");
        
        await fetchWatchlist();
        syncWatchlistButtonUI();
        await fetchWatchlistLogs();
    } catch (error) {
        alert(`Error adding to watchlist: ${error.message}`);
    }
}

async function removeWatchlistCoin(coinId) {
    try {
        const response = await fetch(`${API_BASE}/api/coins/${coinId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to remove from watchlist.");
        
        await fetchWatchlist();
        syncWatchlistButtonUI();
        await fetchWatchlistLogs();
    } catch (error) {
        alert(`Error removing from watchlist: ${error.message}`);
    }
}

// 6. Coin-Specific Subscriptions Management
async function loadCoinSubscribers(coinId) {
    try {
        const response = await fetch(`${API_BASE}/api/subscribers/${coinId}`);
        if (!response.ok) throw new Error("Failed to load coin subscribers.");
        const subscribers = await response.json(); // Array of strings
        
        if (subscribers.length === 0) {
            coinSubscribersList.innerHTML = `<li>No email alerts active for this asset.</li>`;
            return;
        }
        
        coinSubscribersList.innerHTML = subscribers.map(email => `
            <li>
                <span>📧 ${email}</span>
            </li>
        `).join('');
    } catch (error) {
        console.error(`[App] Error loading subscribers for ${coinId}:`, error);
        coinSubscribersList.innerHTML = `<li>Error loading subscribers.</li>`;
    }
}

async function handleSubscribeCoin(e) {
    e.preventDefault();
    const email = subscriberCoinEmail.value.trim().toLowerCase();
    if (!email) return;
    
    const coinObj = marketCoins.find(c => c.id === selectedCoinId);
    const symbol = coinObj ? coinObj.symbol : selectedCoinId;
    
    try {
        const response = await fetch(`${API_BASE}/api/subscribers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, coin_id: selectedCoinId, coin_symbol: symbol })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to subscribe.");
        
        subscriberCoinEmail.value = '';
        await loadCoinSubscribers(selectedCoinId);
        await fetchWatchlist(); // Sync watchlist as DB auto-adds coin
        await loadGlobalSubscribers();
        await fetchWatchlistLogs();
        alert(`Subscribed successfully to ${selectedCoinId.toUpperCase()} alerts: ${email}`);
    } catch (error) {
        alert(`Error subscribing: ${error.message}`);
    }
}

async function handleUnsubscribeCoin() {
    const email = subscriberCoinEmail.value.trim().toLowerCase();
    if (!email) {
        alert("Please type your email address first.");
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/subscribers/${selectedCoinId}/${email}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to unsubscribe.");
        
        subscriberCoinEmail.value = '';
        await loadCoinSubscribers(selectedCoinId);
        await fetchWatchlist(); // Sync watchlist as DB auto-purges if empty
        await loadGlobalSubscribers();
        await fetchWatchlistLogs();
        alert(`Unsubscribed successfully from ${selectedCoinId.toUpperCase()} alerts: ${email}`);
    } catch (error) {
        alert(`Error unsubscribing: ${error.message}`);
    }
}

// 7. Global Subscribers List (Bottom Summary Panel)
async function loadGlobalSubscribers() {
    try {
        const response = await fetch(`${API_BASE}/api/subscribers`);
        if (!response.ok) throw new Error("Failed to load subscriber list.");
        const subscribers = await response.json();
        
        if (subscribers.length === 0) {
            subscribersList.innerHTML = `<li>No active system subscribers.</li>`;
            return;
        }
        
        subscribersList.innerHTML = subscribers.map(email => `
            <li>
                <span>📧 ${email}</span>
            </li>
        `).join('');
    } catch (error) {
        console.error("[App] Error loading global subscribers:", error);
    }
}

// 8. Watchlist Pipeline anomaly log logs fetching
async function fetchWatchlistLogs() {
    const tbody = document.getElementById('logs-table-body');
    if (watchlistIds.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="no-data">No assets on alert watchlist. Subscribe to alert emails or add assets manually to trigger tracking.</td></tr>`;
        return;
    }
    
    try {
        const allLogs = [];
        for (const coinId of watchlistIds) {
            const response = await fetch(`${API_BASE}/api/prices/${coinId}`);
            if (response.ok) {
                const logs = await response.json();
                logs.forEach(l => {
                    allLogs.push({
                        coin_id: coinId,
                        ...l
                    });
                });
            }
        }
        
        // Sort logs chronological descending (newest first)
        allLogs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        if (allLogs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="no-data">Awaiting background pipeline run logs for watchlisted assets.</td></tr>`;
            return;
        }
        
        tbody.innerHTML = allLogs.slice(0, 30).map(log => {
            const logDate = new Date(log.timestamp + " UTC");
            const statusBadge = log.is_anomaly === 1 
                ? `<span class="badge anomaly">Anomaly</span>` 
                : `<span class="badge normal">Normal</span>`;
                
            // Find coin symbol & name
            const coinObj = marketCoins.find(c => c.id === log.coin_id);
            const symbol = coinObj ? coinObj.symbol.toUpperCase() : log.coin_id.toUpperCase();
            const name = coinObj ? coinObj.name : log.coin_id.toUpperCase();
            
            const anomalyText = log.is_anomaly === 1 
                ? `<span class="danger-text">VOLATILITY</span>` 
                : `<span style="color: var(--text-secondary);">-</span>`;
                
            return `
                <tr>
                    <td><strong>${name} (${symbol})</strong></td>
                    <td>${logDate.toLocaleString()}</td>
                    <td><strong>${formatCurrency(log.price)}</strong></td>
                    <td>${statusBadge}</td>
                    <td>${anomalyText}</td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error("[App] Error loading watchlist logs:", error);
        tbody.innerHTML = `<tr><td colspan="5" class="no-data">Error fetching pipeline logs.</td></tr>`;
    }
}

// 9. Dynamic Formatting Helpers
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: value < 2 ? 4 : 2,
        maximumFractionDigits: value < 2 ? 4 : 2
    }).format(value);
}

function formatCompact(value) {
    if (!value && value !== 0) return 'N/A';
    return new Intl.NumberFormat('en-US', {
        notation: 'compact',
        compactDisplay: 'short'
    }).format(value);
}
