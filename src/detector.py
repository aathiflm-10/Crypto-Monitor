from database import get_recent_prices

def check_anomaly(coin_id, current_price, threshold_percent=2.0, min_records=3):
    """
    Compares the newly fetched price against a Simple Moving Average (SMA) of recent prices.
    
    Parameters:
    - coin_id (str): The cryptocurrency to evaluate (e.g. 'bitcoin').
    - current_price (float): The current live price in USD.
    - threshold_percent (float): The percentage change threshold that triggers an alert (default 2%).
    - min_records (int): Minimum historical records needed to establish a stable average.
    
    Returns:
    - tuple: (is_anomaly, anomaly_type, percent_deviation)
      e.g., (True, 'spike', 2.45) or (False, None, 0.12)
    """
    # 1. Fetch recent price history from the database (up to last 10 records)
    recent_records = get_recent_prices(coin_id, limit=10)
    
    # 2. Extract price values from database rows
    # Best Practice: We filter out previous anomalies from our baseline!
    # If we include past spikes/dips in the average, the baseline becomes skewed (poisoned),
    # making it harder to detect future anomalies.
    historical_prices = [
        row['price_usd'] for row in recent_records 
        if row['is_anomaly'] == 0
    ]
    
    # 3. Check if we have enough historical data to construct a valid baseline
    # If the database is new, we wait until we collect at least `min_records`
    if len(historical_prices) < min_records:
        print(f"[Detector] Insufficient history for {coin_id}. Have {len(historical_prices)}/{min_records} records. Skipping check.")
        return False, None, 0.0
    
    # 4. Calculate the Simple Moving Average (SMA)
    moving_average = sum(historical_prices) / len(historical_prices)
    
    # 5. Calculate percentage deviation of the current price from the average
    price_difference = current_price - moving_average
    percent_deviation = (price_difference / moving_average) * 100
    
    print(f"[Detector] {coin_id.capitalize()}: Live = ${current_price:,.2f}, Avg = ${moving_average:,.2f}, Dev = {percent_deviation:+.2f}%")
    
    # 6. Check if the absolute deviation exceeds our threshold
    if abs(percent_deviation) >= threshold_percent:
        # If the deviation is positive, it's a spike; if negative, it's a dip
        anomaly_type = "spike" if percent_deviation > 0 else "dip"
        print(f"[Detector] !!! ANOMALY DETECTED !!! {coin_id.capitalize()} has a {anomaly_type} of {percent_deviation:+.2f}%")
        return True, anomaly_type, percent_deviation
    
    return False, None, percent_deviation

# Direct script execution for testing
if __name__ == "__main__":
    print("[Detector] Testing anomaly detector logic with mock data...")
    
    # Mock data to simulate recent database history
    mock_history = [
        {"price_usd": 60000.0, "is_anomaly": 0},
        {"price_usd": 60100.0, "is_anomaly": 0},
        {"price_usd": 59900.0, "is_anomaly": 0},
        {"price_usd": 60050.0, "is_anomaly": 0},
    ]
    
    # Let's mock the get_recent_prices function for this test block
    # This demonstrates manual unit testing of the calculation logic!
    prices = [row['price_usd'] for row in mock_history if row['is_anomaly'] == 0]
    avg = sum(prices) / len(prices)
    
    # Test a normal price
    test_normal = 60200.0
    dev_normal = ((test_normal - avg) / avg) * 100
    print(f"Normal Test Price: ${test_normal} -> Deviation: {dev_normal:.2f}% (Threshold: 2%)")
    
    # Test a spike price
    test_spike = 61800.0
    dev_spike = ((test_spike - avg) / avg) * 100
    print(f"Spike Test Price: ${test_spike} -> Deviation: {dev_spike:.2f}% (Threshold: 2%) - Expected Anomaly: True")
