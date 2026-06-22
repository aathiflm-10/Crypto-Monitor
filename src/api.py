import os
import sys
import threading
import time
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Add parent directory to path to ensure modules import correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database
from main import run_pipeline

app = FastAPI(
    title="Crypto Tracker REST API",
    description="Backend API serving live price history, dynamic explorer, and supporting alert configurations.",
    version="2.2.0"
)

# Enable CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Caching System ---
# Essential for data engineering robustness to respect free-tier API rate limits.
market_cache = {
    "data": None,
    "timestamp": 0
}
chart_cache = {}  # Keys: (coin_id, days) -> {"data": data, "timestamp": timestamp}

# 1. API Endpoints: Market Explorer & Charting Proxy
@app.get("/api/market")
def get_market_data():
    """
    Fetches the Top 250 cryptocurrencies by market cap with sparklines from CoinGecko.
    Utilizes an in-memory cache to prevent throttling. Caches data for 2 minutes.
    """
    current_time = time.time()
    
    # Check if cache is valid (120 seconds)
    if market_cache["data"] and (current_time - market_cache["timestamp"] < 120):
        print("[API Cache] Serving market list from memory cache.")
        return market_cache["data"]
        
    url = "https://api.coingecko.com/api/v3/coins/markets"
    # per_page: increased from 100 to 250 to allow searching wider selection of coins
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "true"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        
        # Handle HTTP 429 Rate Limit
        if response.status_code == 429:
            print("[API] ERROR: Rate limit hit (HTTP 429) fetching market list.")
            if market_cache["data"]:
                print("[API Cache] Falling back to expired market cache.")
                return market_cache["data"]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="CoinGecko rate limit exceeded. Please try again in a few minutes."
            )
            
        response.raise_for_status()
        data = response.json()
        
        # Store in cache
        market_cache["data"] = data
        market_cache["timestamp"] = current_time
        print("[API] Successfully fetched fresh market list (Top 250) from CoinGecko.")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"[API] Request exception fetching market list: {e}")
        # Fallback to cache if available
        if market_cache["data"]:
            print("[API Cache] Connection error. Serving fallback expired market cache.")
            return market_cache["data"]
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch market data: {str(e)}"
        )

@app.get("/api/market/chart/{coin_id}")
def get_market_chart(coin_id: str, days: int = 7):
    """
    Fetches historical market chart data dynamically for chart rendering.
    Caches results for 5 minutes. Supports days = 1, 7, 30.
    """
    coin_id = coin_id.lower().strip()
    current_time = time.time()
    cache_key = (coin_id, days)
    
    # Check if cache is valid (300 seconds)
    if cache_key in chart_cache:
        cached = chart_cache[cache_key]
        if current_time - cached["timestamp"] < 300:
            print(f"[API Cache] Serving chart for {coin_id} ({days}d) from memory cache.")
            return cached["data"]
            
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": str(days)
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        
        if response.status_code == 429:
            print(f"[API] ERROR: Rate limit hit (HTTP 429) fetching chart for {coin_id}.")
            if cache_key in chart_cache:
                print("[API Cache] Serving expired chart cache fallback.")
                return chart_cache[cache_key]["data"]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="CoinGecko rate limit exceeded. Please try again shortly."
            )
            
        response.raise_for_status()
        raw_data = response.json()
        
        # Convert timestamp, price pairs into a simplified format
        prices = raw_data.get("prices", [])
        formatted_prices = [{"time": p[0], "price": p[1]} for p in prices]
        
        # Cache results
        chart_cache[cache_key] = {
            "data": formatted_prices,
            "timestamp": current_time
        }
        print(f"[API] Successfully fetched fresh chart data for {coin_id} ({days}d).")
        return formatted_prices
        
    except requests.exceptions.RequestException as e:
        print(f"[API] Request exception fetching chart for {coin_id}: {e}")
        if cache_key in chart_cache:
            print("[API Cache] Serving expired chart cache fallback after failure.")
            return chart_cache[cache_key]["data"]
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch historical chart data: {str(e)}"
        )

# 2. API Endpoints: Local Pipeline Watchlist Price Histories
@app.get("/api/prices/{coin_id}")
def get_prices(coin_id: str, limit: int = 50):
    """
    Returns the recent local pipeline price logs for a specific coin from the SQLite database.
    Used to display the active watchlist anomaly logs.
    """
    records = database.get_recent_prices(coin_id.lower(), limit=limit)
    if not records:
        return []
        
    # Format and return chronological order (oldest to newest) for chart plotting
    formatted_records = []
    for r in reversed(records):
        formatted_records.append({
            "timestamp": r["timestamp"],
            "price": r["price_usd"],
            "is_anomaly": int(r["is_anomaly"])
        })
    return formatted_records

# 3. API Endpoints: Watchlist Management
@app.get("/api/coins")
def list_coins():
    """
    Retrieves the list of active cryptocurrencies being monitored.
    """
    return database.get_tracked_coins()

@app.post("/api/coins")
def add_coin(payload: dict):
    """
    Adds a new coin to monitor. Expects payload: {"coin_id": "dogecoin", "coin_symbol": "DOGE"}
    """
    coin_id = payload.get("coin_id")
    coin_symbol = payload.get("coin_symbol")
    
    if not coin_id or not coin_symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'coin_id' or 'coin_symbol' parameters."
        )
        
    # Normalize inputs
    coin_id = coin_id.strip().lower()
    coin_symbol = coin_symbol.strip().upper()
    
    # Try calling dynamic database insert
    success = database.add_tracked_coin(coin_id, coin_symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database write failed."
        )
        
    # Trigger an immediate pipeline run in a separate thread so the user gets prices immediately!
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    return {"message": f"Successfully registered coin: {coin_id} ({coin_symbol})"}

@app.delete("/api/coins/{coin_id}")
def delete_coin(coin_id: str):
    """
    Stops monitoring a cryptocurrency.
    """
    coin_id = coin_id.strip().lower()
    
    # Check if coin is tracked
    coins = database.get_tracked_coins()
    if not any(c["coin_id"] == coin_id for c in coins):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coin '{coin_id}' is not currently being tracked."
        )
        
    success = database.remove_tracked_coin(coin_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database deletion failed."
        )
    return {"message": f"Successfully stopped tracking coin: {coin_id}"}

# 4. API Endpoints: Email Subscribers & Asset Mappings

@app.get("/api/subscribers")
def list_subscribers():
    """
    Lists all unique subscriber email addresses registered in the system.
    """
    return database.get_active_subscribers()

@app.get("/api/subscribers/{coin_id}")
def list_subscribers_for_coin(coin_id: str):
    """
    Lists email addresses subscribed to alerts for a specific cryptocurrency.
    """
    return database.get_subscribers_for_coin(coin_id.lower().strip())

@app.post("/api/subscribers")
def subscribe_to_coin(payload: dict):
    """
    Subscribes a user's email to alerts for a specific coin.
    Expects payload: {"email": "user@domain.com", "coin_id": "bitcoin", "coin_symbol": "BTC"}
    """
    email = payload.get("email")
    coin_id = payload.get("coin_id")
    coin_symbol = payload.get("coin_symbol")
    
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid 'email' address is required."
        )
    if not coin_id or not coin_symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'coin_id' and 'coin_symbol' parameters are required."
        )
        
    email = email.strip().lower()
    coin_id = coin_id.strip().lower()
    coin_symbol = coin_symbol.strip().upper()
    
    success = database.subscribe_email_to_coin(email, coin_id, coin_symbol)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database subscription write failed."
        )
        
    # Trigger an immediate pipeline run in a separate thread so prices ingest instantly
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    return {"message": f"Successfully subscribed {email} to {coin_id} alerts."}

@app.delete("/api/subscribers/{coin_id}/{email}")
def unsubscribe_from_coin(coin_id: str, email: str):
    """
    Unsubscribes an email address from alerts for a specific cryptocurrency.
    """
    email = email.strip().lower()
    coin_id = coin_id.strip().lower()
    
    success = database.unsubscribe_email_from_coin(email, coin_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database subscription deletion failed."
        )
    return {"message": f"Successfully unsubscribed {email} from {coin_id} alerts."}

# 5. Background Scheduler Daemon Setup
def run_scheduler_loop():
    """
    Loops continuously, running pending scheduled pipeline jobs.
    Runs on a daemon thread so it terminates when the main server exits.
    """
    # Ensure database is initialized
    database.init_db()
    
    # Run the pipeline once immediately on startup to ensure fresh data
    print("[Server] Launching initial pipeline execution cycle...")
    run_pipeline()
    
    # Read monitoring cycle gap dynamically from environmental configuration (in minutes)
    cycle_minutes = int(os.getenv("MONITOR_CYCLE_MINUTES", 5))
    
    import schedule
    schedule.every(cycle_minutes).minutes.do(run_pipeline)
    print(f"[Server] Automated background pipeline scheduler active (every {cycle_minutes} minutes).")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.on_event("startup")
def startup_event():
    """
    Start the pipeline scheduler in a separate background thread when the server boots.
    """
    scheduler_thread = threading.Thread(target=run_scheduler_loop, daemon=True)
    scheduler_thread.start()
    print("[Server] Background scheduler thread successfully spawned.")

# 6. Serve Frontend Web Dashboard
# Mount static files to serve index.html, style.css, app.js at the server root /
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    # Start the server locally on port 8000
    print("Starting Crypto Tracker REST API server on http://localhost:8000...")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
