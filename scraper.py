import requests
from bs4 import BeautifulSoup
import time
import os
import threading
from datetime import datetime
from flask import Flask, jsonify

# ========== Configuration ==========
FIREBASE_URL = os.environ.get("FIREBASE_URL")
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")
if not FIREBASE_URL or not FIREBASE_SECRET:
    raise ValueError("FIREBASE_URL and FIREBASE_SECRET environment variables must be set.")

SET_URL = "https://www.set.or.th/en/market/product/stock/overview"
UPDATE_INTERVAL = 15  # seconds
# ===================================

app = Flask(__name__)

# ---------- SET Data Fetcher ----------
def fetch_set_data():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(SET_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Network error: {e}")
        return None, None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = None
        for tbl in soup.find_all('table'):
            if any('index' in th.get_text(strip=True).lower() for th in tbl.find_all('th')):
                table = tbl
                break
        if not table:
            return None, None

        first_row = table.find('tbody').find('tr') if table.find('tbody') else table.find('tr')
        cells = first_row.find_all('td')
        if len(cells) < 8:
            return None, None

        last = cells[1].get_text(strip=True).replace(',', '')
        value = cells[7].get_text(strip=True).replace(',', '')
        return last, value
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Parsing error: {e}")
        return None, None

def update_firebase(last, value):
    """Update live_set and live_value in Firebase using REST API."""
    if last is None or value is None:
        return False

    # Firebase REST endpoint with auth
    auth_param = f"auth={FIREBASE_SECRET}"
    
    # Update live_set
    set_url = f"{FIREBASE_URL}/live_2d/live_set.json?{auth_param}"
    try:
        r = requests.put(set_url, json=last)
        r.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Firebase set update failed: {e}")
        return False

    # Update live_value
    value_url = f"{FIREBASE_URL}/live_2d/live_value.json?{auth_param}"
    try:
        r = requests.put(value_url, json=value)
        r.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Firebase value update failed: {e}")
        return False

    print(f"[{datetime.now().isoformat()}] Firebase updated: live_set={last}, live_value={value}")
    return True

# ---------- Background Scraper Thread ----------
def scraper_loop():
    """Run in a separate thread, updates Firebase every 15 seconds."""
    while True:
        last, value = fetch_set_data()
        if last and value:
            update_firebase(last, value)
        else:
            print(f"[{datetime.now().isoformat()}] Failed to fetch SET data.")
        time.sleep(UPDATE_INTERVAL)

# ---------- Flask Routes ----------
@app.route('/')
def home():
    return "SET Scraper is running. Firebase is being updated every 15 seconds.", 200

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "last_update": datetime.now().isoformat(),
        "firebase_url": FIREBASE_URL
    })

# ---------- Main ----------
if __name__ == "__main__":
    # Start background scraper thread
    thread = threading.Thread(target=scraper_loop, daemon=True)
    thread.start()
    print(f"[{datetime.now().isoformat()}] Scraper thread started. Web server running...")

    # Get port from environment (Render provides PORT)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
