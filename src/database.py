import os
import sqlite3
import json
from datetime import datetime

# Define the database directory and file path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "crypto_prices.db")

def get_connection():
    """
    Establishes and returns a connection to the SQLite database.
    SQLite stores database data in a single file specified by DB_PATH.
    If the file does not exist, SQLite will automatically create it.
    """
    # Check if the data directory exists, if not, create it
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"[Database] Created directory: {DB_DIR}")
        
    # Connect to the database. row_factory helps return rows as dictionary-like objects
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Creates the 'prices' table in the database if it doesn't already exist.
    We define schema columns for storing coin metrics and anomaly detection flags.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        coin_id TEXT NOT NULL,
        coin_symbol TEXT NOT NULL,
        price_usd REAL NOT NULL,
        is_anomaly INTEGER DEFAULT 0,
        anomaly_type TEXT DEFAULT NULL
    );
    """
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Execute the SQL script to create the table
        cursor.execute(create_table_query)
        # Commit the transaction to save changes
        conn.commit()
        print("[Database] Successfully initialized database and created 'prices' table.")
    except sqlite3.Error as e:
        print(f"[Database] Error initializing database: {e}")
    finally:
        # Always close connections to prevent database locking and free up memory
        conn.close()

def insert_price(coin_id, coin_symbol, price_usd, is_anomaly=0, anomaly_type=None):
    """
    Inserts a new price record into the database.
    
    Parameters:
    - coin_id (str): The unique identifier of the coin (e.g. 'bitcoin')
    - coin_symbol (str): The ticker symbol (e.g. 'btc')
    - price_usd (float): The price of the coin in USD
    - is_anomaly (int): Flag indicating anomaly (0 = Normal, 1 = Anomaly)
    - anomaly_type (str): Description of anomaly (e.g. 'spike', 'dip', or None)
    """
    insert_query = """
    INSERT INTO prices (timestamp, coin_id, coin_symbol, price_usd, is_anomaly, anomaly_type)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    
    # Generate the current UTC timestamp in standard ISO format
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Use parameterized queries (?) to prevent SQL injection and handle formatting safely
        cursor.execute(insert_query, (timestamp, coin_id, coin_symbol.upper(), price_usd, is_anomaly, anomaly_type))
        conn.commit()
        print(f"[Database] Inserted: {coin_id.capitalize()} (${price_usd:,.2f}) at {timestamp}")
    except sqlite3.Error as e:
        print(f"[Database] Error inserting price: {e}")
    finally:
        conn.close()

def get_recent_prices(coin_id, limit=100):
    """
    Fetches the most recent price records for a specific coin.
    Used for anomaly detection calculations and graph rendering.
    """
    select_query = """
    SELECT timestamp, price_usd, is_anomaly 
    FROM prices 
    WHERE coin_id = ? 
    ORDER BY timestamp DESC 
    LIMIT ?;
    """
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(select_query, (coin_id, limit))
        rows = cursor.fetchall()
        # Convert sqlite3.Row objects to standard Python dictionaries
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[Database] Error fetching recent prices: {e}")
        return []
    finally:
        conn.close()

def export_prices_to_json(limit=100):
    """
    Queries the database for recent prices of all tracked coins and exports
    the structured history to 'prices.json' in both the data and web folders.
    
    Parameters:
    - limit (int): The number of recent records to export per coin.
    """
    # Define paths for the JSON file
    data_json_path = os.path.join(DB_DIR, "prices.json")
    web_json_path = os.path.join(os.path.dirname(DB_DIR), "web", "prices.json")
    
    # We query all records, but order by timestamp ascending so charts draw chronologically.
    # We want to group by coin_id.
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get the unique coin IDs currently stored
        cursor.execute("SELECT DISTINCT coin_id FROM prices;")
        coins = [row['coin_id'] for row in cursor.fetchall()]
        
        export_data = {}
        for coin_id in coins:
            # For each coin, fetch the last N records, order ascending chronologically
            query = """
            SELECT timestamp, coin_symbol, price_usd, is_anomaly 
            FROM prices 
            WHERE coin_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?;
            """
            cursor.execute(query, (coin_id, limit))
            rows = cursor.fetchall()
            
            # Since we fetched sorted DESC (newest first), reverse it for chronological charts
            records = []
            for row in reversed(rows):
                records.append({
                    "timestamp": row['timestamp'],
                    "symbol": row['coin_symbol'],
                    "price": row['price_usd'],
                    "is_anomaly": int(row['is_anomaly'])
                })
            export_data[coin_id] = records
            
        # Write to JSON files
        for json_path in [data_json_path, web_json_path]:
            # Ensure the parent folder exists
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(export_data, f, indent=4)
        print(f"[Database] Price history successfully exported to JSON in both data/ and web/ directories.")
        
    except sqlite3.Error as e:
        print(f"[Database] SQLite error exporting to JSON: {e}")
    except Exception as e:
        print(f"[Database] Unexpected error exporting to JSON: {e}")
    finally:
        conn.close()

# If you execute this script directly (e.g., `python src/database.py`),
# it will initialize the database and test JSON export.
if __name__ == "__main__":
    init_db()
    # Test JSON export function
    export_prices_to_json()
