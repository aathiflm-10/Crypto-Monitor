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
    Creates the 'prices', 'tracked_coins', and 'subscribers' tables if they don't exist.
    Seeds the 'tracked_coins' table with default crypto assets on first boot.
    """
    create_prices_table = """
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
    
    create_tracked_coins_table = """
    CREATE TABLE IF NOT EXISTS tracked_coins (
        coin_id TEXT PRIMARY KEY,
        coin_symbol TEXT NOT NULL
    );
    """
    
    create_subscribers_table = """
    CREATE TABLE IF NOT EXISTS subscribers (
        email TEXT PRIMARY KEY,
        is_active INTEGER DEFAULT 1
    );
    """
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Create tables
        cursor.execute(create_prices_table)
        cursor.execute(create_tracked_coins_table)
        cursor.execute(create_subscribers_table)
        conn.commit()
        print("[Database] Initialized tables: prices, tracked_coins, subscribers.")
        
        # 2. Seed default coins if table is completely empty
        cursor.execute("SELECT COUNT(*) FROM tracked_coins;")
        if cursor.fetchone()[0] == 0:
            default_coins = [
                ("bitcoin", "BTC"),
                ("ethereum", "ETH"),
                ("solana", "SOL")
            ]
            cursor.executemany(
                "INSERT INTO tracked_coins (coin_id, coin_symbol) VALUES (?, ?);",
                default_coins
            )
            conn.commit()
            print("[Database] Seeded default tracked coins (Bitcoin, Ethereum, Solana).")
            
    except sqlite3.Error as e:
        print(f"[Database] Error initializing database: {e}")
    finally:
        conn.close()

# --- Dynamic Configuration Helper Functions ---

def add_tracked_coin(coin_id, coin_symbol):
    """
    Adds a new coin to be monitored by the background pipeline.
    """
    insert_query = "INSERT OR REPLACE INTO tracked_coins (coin_id, coin_symbol) VALUES (?, ?);"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(insert_query, (coin_id.lower(), coin_symbol.upper()))
        conn.commit()
        print(f"[Database] Started tracking: {coin_id} ({coin_symbol.upper()})")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error adding coin: {e}")
        return False
    finally:
        conn.close()

def remove_tracked_coin(coin_id):
    """
    Stops monitoring a specific coin and removes it from the configuration.
    """
    delete_query = "DELETE FROM tracked_coins WHERE coin_id = ?;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(delete_query, (coin_id.lower(),))
        conn.commit()
        print(f"[Database] Stopped tracking: {coin_id}")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error removing coin: {e}")
        return False
    finally:
        conn.close()

def get_tracked_coins():
    """
    Retrieves all coins that are currently being monitored by the pipeline.
    """
    select_query = "SELECT coin_id, coin_symbol FROM tracked_coins;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(select_query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[Database] Error fetching tracked coins: {e}")
        return []
    finally:
        conn.close()

def subscribe_email(email):
    """
    Adds a new email subscriber to receive price anomaly notifications.
    """
    insert_query = "INSERT OR REPLACE INTO subscribers (email, is_active) VALUES (?, 1);"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(insert_query, (email.lower(),))
        conn.commit()
        print(f"[Database] Subscribed email: {email.lower()}")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error subscribing email: {e}")
        return False
    finally:
        conn.close()

def unsubscribe_email(email):
    """
    Removes an email from receiving price anomaly notifications.
    """
    delete_query = "DELETE FROM subscribers WHERE email = ?;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(delete_query, (email.lower(),))
        conn.commit()
        print(f"[Database] Unsubscribed email: {email.lower()}")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error unsubscribing email: {e}")
        return False
    finally:
        conn.close()

def get_active_subscribers():
    """
    Retrieves a list of all active subscriber email addresses.
    """
    select_query = "SELECT email FROM subscribers WHERE is_active = 1;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(select_query)
        rows = cursor.fetchall()
        return [row['email'] for row in rows]
    except sqlite3.Error as e:
        print(f"[Database] Error fetching subscribers: {e}")
        return []
    finally:
        conn.close()

# --- Core Pipeline Operations ---

def insert_price(coin_id, coin_symbol, price_usd, is_anomaly=0, anomaly_type=None):
    """
    Inserts a new price record into the database.
    """
    insert_query = """
    INSERT INTO prices (timestamp, coin_id, coin_symbol, price_usd, is_anomaly, anomaly_type)
    VALUES (?, ?, ?, ?, ?, ?);
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        cursor = conn.cursor()
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
    """
    data_json_path = os.path.join(DB_DIR, "prices.json")
    web_json_path = os.path.join(os.path.dirname(DB_DIR), "web", "prices.json")
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Get the unique coin IDs currently stored
        cursor.execute("SELECT DISTINCT coin_id FROM prices;")
        coins = [row['coin_id'] for row in cursor.fetchall()]
        
        export_data = {}
        for coin_id in coins:
            query = """
            SELECT timestamp, coin_symbol, price_usd, is_anomaly 
            FROM prices 
            WHERE coin_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?;
            """
            cursor.execute(query, (coin_id, limit))
            rows = cursor.fetchall()
            
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
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(export_data, f, indent=4)
        print(f"[Database] Price history successfully exported to JSON.")
        
    except sqlite3.Error as e:
        print(f"[Database] SQLite error exporting to JSON: {e}")
    except Exception as e:
        print(f"[Database] Unexpected error exporting to JSON: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    # Test queries
    print("Tracked Coins:", get_tracked_coins())
    print("Active Subscribers:", get_active_subscribers())
