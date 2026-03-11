import requests
from bs4 import BeautifulSoup
import time
import json
import os
import threading
from datetime import datetime
from flask import Flask, Response

# ========== Configuration ==========
JSON_FILE = "myluck2d3dresult-default-rtdb-export.json"
URL = "https://www.set.or.th/en/market/product/stock/overview"
UPDATE_INTERVAL = 15  # seconds
# ===================================

app = Flask(__name__)

# ---------- SET Data Fetcher ----------
def fetch_set_data():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(URL, headers=headers, timeout=10)
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

def update_json_file(last, value):
    if last is None or value is None:
        return False
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'live_2d' in data:
            data['live_2d']['live_set'] = last
            data['live_2d']['live_value'] = value
        else:
            return False
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[{datetime.now().isoformat()}] Updated JSON: live_set={last}, live_value={value}")
        return True
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] File error: {e}")
        return False

# ---------- Background Scraper Thread ----------
def scraper_loop():
    """Run in a separate thread, updates JSON every 15 seconds."""
    while True:
        last, value = fetch_set_data()
        if last and value:
            update_json_file(last, value)
        else:
            print(f"[{datetime.now().isoformat()}] Failed to fetch data.")
        time.sleep(UPDATE_INTERVAL)

# ---------- Flask Routes ----------
@app.route('/')
def home():
    return "SET Scraper is running. JSON is being updated every 15 seconds.", 200

@app.route('/health')
def health():
    # Optional: return current status as JSON
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        live_set = data.get('live_2d', {}).get('live_set', 'unknown')
        live_value = data.get('live_2d', {}).get('live_value', 'unknown')
        return {
            "status": "ok",
            "last_update": datetime.now().isoformat(),
            "live_set": live_set,
            "live_value": live_value
        }
    except:
        return {"status": "error", "message": "Cannot read JSON"}, 500

# ---------- Main ----------
if __name__ == "__main__":
    # Start the background scraper thread
    thread = threading.Thread(target=scraper_loop, daemon=True)
    thread.start()
    print(f"[{datetime.now().isoformat()}] Scraper thread started. Web server running...")

    # Get port from environment (Render provides PORT)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
