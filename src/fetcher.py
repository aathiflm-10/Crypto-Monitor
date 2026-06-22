import requests

# CoinGecko API URL for fetching simple prices
COINGECKO_API_URL = "https://api.coingecko.com/api/v3/simple/price"

# List of target cryptocurrencies to track: (coin_id, coin_symbol)
TRACKED_COINS = [
    ("bitcoin", "BTC"),
    ("ethereum", "ETH"),
    ("solana", "SOL")
]

def fetch_raw_prices():
    """
    Hits the CoinGecko API and returns a dictionary containing the current
    prices in USD for all tracked coins.
    
    Returns:
    - dict: A dictionary like {"bitcoin": 64058.0, "ethereum": 1733.13, "solana": 73.79}
            or None if the request failed.
    """
    # Join all coin IDs into a comma-separated string for the API query parameter
    coin_ids = ",".join([coin[0] for coin in TRACKED_COINS])
    params = {
        "ids": coin_ids,
        "vs_currencies": "usd"
    }
    
    headers = {
        "accept": "application/json",
        "User-Agent": "CryptoPriceTrackerPipeline/1.0"
    }
    
    try:
        # Make the API request with a 10-second timeout
        response = requests.get(COINGECKO_API_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse the JSON response into a simple coin_id -> price_usd dictionary
        prices = {}
        for coin_id, coin_symbol in TRACKED_COINS:
            if coin_id in data:
                price = data[coin_id].get("usd")
                if price is not None:
                    prices[coin_id] = float(price)
                    
        return prices
        
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 429:
            print("[Fetcher] Error 429: Rate limit hit. CoinGecko free API allows only a few requests per minute.")
        else:
            print(f"[Fetcher] HTTP error occurred: {http_err}")
        return None
    except Exception as e:
        print(f"[Fetcher] Network or unexpected error: {e}")
        return None

# Quick manual test run
if __name__ == "__main__":
    print("[Fetcher] Testing raw price fetcher...")
    prices = fetch_raw_prices()
    if prices:
        print(f"[Fetcher] Successfully fetched prices: {prices}")
    else:
        print("[Fetcher] Failed to fetch prices.")
