import os
import sys
import threading
import time
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
    description="Backend API serving live price history and supporting dynamic configurations.",
    version="2.0.0"
)

# Enable CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. API Endpoints: Price Histories
@app.get("/api/prices/{coin_id}")
def get_prices(coin_id: str, limit: int = 50):
    """
    Returns the recent price logs for a specific coin from the SQLite database.
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

# 2. API Endpoints: Coin Management
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

# 3. API Endpoints: Email Subscribers
@app.get("/api/subscribers")
def list_subscribers():
    """
    Lists all email addresses currently subscribed to anomaly notifications.
    """
    return database.get_active_subscribers()

@app.post("/api/subscribers")
def subscribe(payload: dict):
    """
    Subscribes a new email address. Expects payload: {"email": "user@domain.com"}
    """
    email = payload.get("email")
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid 'email' address is required."
        )
        
    email = email.strip().lower()
    success = database.subscribe_email(email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database subscription write failed."
        )
    return {"message": f"Successfully subscribed: {email}"}

@app.delete("/api/subscribers/{email}")
def unsubscribe(email: str):
    """
    Unsubscribes an email address from alerts.
    """
    email = email.strip().lower()
    success = database.unsubscribe_email(email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database deletion failed."
        )
    return {"message": f"Successfully unsubscribed: {email}"}

# 4. Background Scheduler Daemon Setup
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
    
    import schedule
    schedule.every(5).minutes.do(run_pipeline)
    print("[Server] Automated background pipeline scheduler active (every 5 minutes).")
    
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

# 5. Serve Frontend Web Dashboard
# Mount static files to serve index.html, style.css, app.js at the server root /
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    # Start the server locally on port 8000
    print("Starting Crypto Tracker REST API server on http://localhost:8000...")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
