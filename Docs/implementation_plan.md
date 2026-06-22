# Implementation Plan: Upgrading to a Dynamic Database-Driven REST API Pipeline

This plan outlines the architecture and modifications required to upgrade the Crypto Tracker project from a static local script to a dynamic database-driven application with a FastAPI backend, subscriber-based alerting, and interactive management panels in the UI.

## User Review Required

> [!IMPORTANT]
> This upgrade changes the serving mechanism: instead of Python's static `http.server`, we will use **FastAPI** and **Uvicorn** to run a live REST API backend. The webpage will load data directly from SQLite via endpoints, and the scheduler will run on a background thread inside the API server process, meaning you only need to run one command to start the entire system.

---

## Proposed Changes

### 1. Database Schema Extensions

#### [MODIFY] [database.py](file:///d:/Projects/Mine/Crypto%20Tracker/src/database.py)
We will add tables to store configurations dynamically in SQLite:
* `tracked_coins` table:
  * `coin_id` (TEXT PRIMARY KEY) - e.g., 'bitcoin'
  * `coin_symbol` (TEXT NOT NULL) - e.g., 'BTC'
* `subscribers` table:
  * `email` (TEXT PRIMARY KEY) - e.g., 'subscriber@gmail.com'
  * `is_active` (INTEGER DEFAULT 1) - Flag to easily toggle subscription

We will also:
* Add helper functions: `add_tracked_coin()`, `remove_tracked_coin()`, `get_tracked_coins()`, `subscribe_email()`, `unsubscribe_email()`, `get_active_subscribers()`.
* Update `init_db()` to automatically seed default coins (`bitcoin`, `ethereum`, `solana`) if the table is empty so the project works immediately on launch.

---

### 2. Ingestion & Alerting Updates

#### [MODIFY] [fetcher.py](file:///d:/Projects/Mine/Crypto%20Tracker/src/fetcher.py)
* Refactor `fetch_raw_prices()` to query `get_tracked_coins()` from the database instead of using a hardcoded `TRACKED_COINS` list.

#### [MODIFY] [notifier.py](file:///d:/Projects/Mine/Crypto%20Tracker/src/notifier.py)
* Refactor `send_alert()` to pull a list of active email addresses using `get_active_subscribers()` and dispatch the email to all of them, instead of reading a single hardcoded receiver email from `.env`.

---

### 3. FastAPI REST Backend Creation

#### [NEW] [api.py](file:///d:/Projects/Mine/Crypto%20Tracker/src/api.py)
We will create a FastAPI app to expose these endpoints:
* **Prices:**
  * `GET /api/prices/{coin_id}`: Retrieves recent prices for a coin (replaces reading `prices.json`).
* **Coin Management:**
  * `GET /api/coins`: Gets list of all currently tracked coins.
  * `POST /api/coins`: Adds a new coin to track (verifies symbol/validity against CoinGecko if possible, or adds to database).
  * `DELETE /api/coins/{coin_id}`: Removes a coin from tracking.
* **Alert Subscription:**
  * `GET /api/subscribers`: Lists all subscribed emails.
  * `POST /api/subscribers`: Subscribes a new email address.
  * `DELETE /api/subscribers/{email}`: Unsubscribes an email address.
* **Orchestration Integration:**
  * Use FastAPI startup event handler to spin up our pipeline scheduler loop in a background thread using Python's `threading` library, so that the API and scheduler execute within a single process.

---

### 4. Frontend Enhancements

#### [MODIFY] [index.html](file:///d:/Projects/Mine/Crypto%20Tracker/web/index.html)
We will add two administrative forms in the side control panel:
* **Manage Tracked Coins:** Text input and button to register new tokens (e.g. `cardano`, `dogecoin`) with a listing of currently active coins showing "Remove" buttons.
* **Manage Alerts:** Email input and buttons to "Subscribe" or "Unsubscribe" from anomaly alerts.

#### [MODIFY] [app.js](file:///d:/Projects/Mine/Crypto%20Tracker/web/app.js)
* Refactor JavaScript `fetch()` calls to target our REST API endpoints (`/api/prices/...`, `/api/coins`, `/api/subscribers`) rather than the static `prices.json` file.
* Implement UI logic to fetch and update the coin selector buttons and subscription table dynamically based on API responses.
* Attach event handlers to submit POST and DELETE requests when adding/removing coins and email subscribers.

#### [MODIFY] [style.css](file:///d:/Projects/Mine/Crypto%20Tracker/web/style.css)
* Add styling for management panels, text inputs, action buttons, list badges, and delete icons.

---

### 5. Dependency Additions

#### [MODIFY] [requirements.txt](file:///d:/Projects/Mine/Crypto%20Tracker/requirements.txt)
Append web-framework dependencies:
* `fastapi==0.110.0`
* `uvicorn==0.28.0`

---

## Verification Plan

### Automated/Manual Verification
1. Run `pip install -r requirements.txt` to install FastAPI and Uvicorn.
2. Launch the backend API + background scheduler with a single command:
   ```powershell
   python -u src/api.py
   ```
3. Load `http://localhost:8000` in the browser.
4. **Test Dynamic Tracking:**
   * Enter a new coin ID (e.g., `dogecoin` or `cardano`) and verify that it appears in the coin list, updates the selector buttons, and that the database starts logging prices for it.
   * Delete a coin and verify that it disappears and fetches stop.
5. **Test Dynamic Alerting:**
   * Subscribe an email address in the panel, and verify it updates the subscribers table.
   * Trigger a mock anomaly (or temporarily lower the threshold in `api.py`) to verify it logs dispatch calls to the new subscriber.
