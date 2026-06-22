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
    row_factory helps return rows as dictionary-like objects.
    """
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"[Database] Created directory: {DB_DIR}")
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Creates the 'prices', 'tracked_coins', and 'subscriptions' tables if they don't exist.
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
    
    # New Table: maps emails to specific coin alerts (Asset-Specific alerting)
    create_subscriptions_table = """
    CREATE TABLE IF NOT EXISTS subscriptions (
        email TEXT,
        coin_id TEXT,
        PRIMARY KEY (email, coin_id)
    );
    """
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute(create_prices_table)
        cursor.execute(create_tracked_coins_table)
        cursor.execute(create_subscriptions_table)
        conn.commit()
        print("[Database] Initialized tables: prices, tracked_coins, subscriptions.")
        
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

# --- Asset-Specific Subscriptions CRUD Helpers ---

def subscribe_email_to_coin(email, coin_id, coin_symbol):
    """
    Subscribes an email to alerts for a specific cryptocurrency.
    Automatically starts tracking the coin in the background if not already tracked.
    """
    email = email.lower().strip()
    coin_id = coin_id.lower().strip()
    coin_symbol = coin_symbol.upper().strip()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Map subscription
        cursor.execute(
            "INSERT OR REPLACE INTO subscriptions (email, coin_id) VALUES (?, ?);",
            (email, coin_id)
        )
        
        # 2. Add to active tracked list for background scheduling
        cursor.execute(
            "INSERT OR REPLACE INTO tracked_coins (coin_id, coin_symbol) VALUES (?, ?);",
            (coin_id, coin_symbol)
        )
        
        conn.commit()
        print(f"[Database] Subscribed {email} to {coin_id} alerts.")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error subscribing email to coin: {e}")
        return False
    finally:
        conn.close()

def unsubscribe_email_from_coin(email, coin_id):
    """
    Unsubscribes an email from alerts for a specific cryptocurrency.
    If no other active subscribers are left for this coin, automatically
    removes it from the background tracking list to save system API calls.
    """
    email = email.lower().strip()
    coin_id = coin_id.lower().strip()
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Delete subscription mapping
        cursor.execute(
            "DELETE FROM subscriptions WHERE email = ? AND coin_id = ?;",
            (email, coin_id)
        )
        
        # 2. Check if any subscribers remain for this coin
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE coin_id = ?;", (coin_id,))
        remaining = cursor.fetchone()[0]
        
        # If no subscribers are left, purge it from tracked_coins
        if remaining == 0:
            cursor.execute("DELETE FROM tracked_coins WHERE coin_id = ?;", (coin_id,))
            print(f"[Database] Stopped background tracking for {coin_id} (0 subscribers remaining).")
            
        conn.commit()
        print(f"[Database] Unsubscribed {email} from {coin_id} alerts.")
        return True
    except sqlite3.Error as e:
        print(f"[Database] Error unsubscribing email from coin: {e}")
        return False
    finally:
        conn.close()

def get_subscribers_for_coin(coin_id):
    """
    Retrieves all emails subscribed to a specific coin.
    """
    coin_id = coin_id.lower().strip()
    select_query = "SELECT email FROM subscriptions WHERE coin_id = ?;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(select_query, (coin_id,))
        rows = cursor.fetchall()
        return [row['email'] for row in rows]
    except sqlite3.Error as e:
        print(f"[Database] Error fetching subscribers for {coin_id}: {e}")
        return []
    finally:
        conn.close()

def get_all_subscriptions():
    """
    Retrieves all subscriptions mapping.
    """
    select_query = "SELECT email, coin_id FROM subscriptions;"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(select_query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[Database] Error fetching all subscriptions: {e}")
        return []
    finally:
        conn.close()

def get_active_subscribers():
    """
    Retrieves a list of all unique active subscriber email addresses.
    """
    select_query = "SELECT DISTINCT email FROM subscriptions;"
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
    print("Tracked Coins:", get_tracked_coins())
    print("All Subscriptions:", get_all_subscriptions())
