import time
import sys
import os

# Add the current directory to Python's search path to ensure imports work correctly
# regardless of where the terminal command is run from.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import schedule
from database import init_db, insert_price, export_prices_to_json, get_tracked_coins
from fetcher import fetch_raw_prices
from detector import check_anomaly
from notifier import send_alert

def run_pipeline():
    """
    Orchestrates one complete cycle of our data engineering pipeline:
    1. Fetch live prices from the API.
    2. Loop through each coin, check for spikes/dips, and store in SQLite.
    3. Dispatch email notifications if anomalies are found.
    4. Export recent database history to a JSON file for the frontend dashboard.
    """
    print("\n==============================================")
    print("      RUNNING PIPELINE EXECUTION CYCLE        ")
    print("==============================================")
    
    # 1. Extraction: Fetch live rates from the CoinGecko API
    prices = fetch_raw_prices()
    if not prices:
        print("[Pipeline] WARNING: No prices fetched. Skipping this cycle.")
        return
        
    # 2. Transformation & Loading: Process each coin individually
    tracked_coins = get_tracked_coins()
    for item in tracked_coins:
        coin_id = item['coin_id']
        coin_symbol = item['coin_symbol']
        if coin_id not in prices:
            print(f"[Pipeline] WARNING: {coin_id} missing from API results.")
            continue
            
        current_price = prices[coin_id]
        
        # Check if the price movement constitutes an anomaly
        is_anomaly, anomaly_type, percent_deviation = check_anomaly(
            coin_id=coin_id,
            current_price=current_price,
            threshold_percent=2.0,  # 2.0% threshold (e.g. price change compared to average)
            min_records=3           # Wait until 3 historical data points exist before flagging
        )
        
        # Convert boolean is_anomaly to SQLite integer flag (1 = True, 0 = False)
        anomaly_flag = 1 if is_anomaly else 0
        
        # Save record in SQLite database
        insert_price(
            coin_id=coin_id,
            coin_symbol=coin_symbol,
            price_usd=current_price,
            is_anomaly=anomaly_flag,
            anomaly_type=anomaly_type
        )
        
        # 3. Alerting: Dispatch email if anomalous activity is flagged
        if is_anomaly:
            send_alert(
                coin_id=coin_id,
                price_usd=current_price,
                anomaly_type=anomaly_type,
                percent_deviation=percent_deviation
            )
            
    # 4. Serving: Export SQLite database history to JSON files for the dashboard
    export_prices_to_json(limit=50)
    print("==============================================")
    print("      PIPELINE EXECUTION CYCLE COMPLETED      ")
    print("==============================================")

def main():
    """
    Entry point of the program. Initializes database tables, triggers an
    immediate run, and configures the automated scheduler loop.
    """
    print("Starting Crypto Price Tracker Pipeline...")
    
    # Ensure database tables exist
    init_db()
    
    # Best Practice: Run the pipeline once immediately on startup.
    # Otherwise, you have to wait for the first scheduled 5-minute interval.
    run_pipeline()
    
    # Schedule the task to run every 5 minutes
    # (For local testing, you can change .minutes to .seconds or .minutes to 1)
    schedule.every(5).minutes.do(run_pipeline)
    print("Pipeline scheduler active. Running in background... Press Ctrl+C to exit.")
    
    try:
        # Keep the program running in an infinite loop
        while True:
            # Check if any scheduled tasks are pending and execute them
            schedule.run_pending()
            # Sleep for 1 second between checks to keep CPU usage low
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nPipeline scheduler stopped by user. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()
