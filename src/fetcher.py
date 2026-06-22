import requests
from database import get_tracked_coins

def fetch_raw_prices():
    """
    Dynamically queries the database for tracked coins, calls the CoinGecko Simple Price API,
    and returns a raw dictionary of price values: {'coin_id': price_usd}.
    """
    # 1. Fetch configured coins from SQLite
    tracked = get_tracked_coins()
    if not tracked:
        print("[Fetcher] WARNING: No coins registered for tracking in database.")
        return {}
        
    # Extract IDs (for the API request) and mapping of ID to symbol
    coin_ids = [item['coin_id'] for item in tracked]
    
    # 2. Configure HTTP API Request
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(coin_ids),
        "vs_currencies": "usd"
    }
    
    # Set headers to look like a standard browser request (helps prevent HTTP 403/429 blocks)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        # Fetch prices with a timeout of 10 seconds (important for data engineering robustness!)
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        # Check HTTP Status Code
        if response.status_code == 429:
            print("[Fetcher] ERROR: Rate limit hit (HTTP 429). CoinGecko is throttling requests.")
            return {}
        response.raise_for_status()
        
        data = response.json()
        
        # 3. Restructure and return data
        prices = {}
        for coin_id in coin_ids:
            if coin_id in data and "usd" in data[coin_id]:
                prices[coin_id] = float(data[coin_id]["usd"])
                
        print(f"[Fetcher] Successfully fetched prices: {prices}")
        return prices
        
    except requests.exceptions.Timeout:
        print("[Fetcher] ERROR: Request timed out. CoinGecko API is unresponsive.")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"[Fetcher] ERROR: Connection failed: {e}")
        return {}

if __name__ == "__main__":
    print("[Fetcher] Testing dynamic price fetcher...")
    # Initialize database tables and seed values first if running standalone
    from database import init_db
    init_db()
    fetch_raw_prices()
