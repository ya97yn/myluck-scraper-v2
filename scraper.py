import requests
from bs4 import BeautifulSoup
import time
import os
import threading
import json
from datetime import datetime
from flask import Flask, jsonify
from google.oauth2 import service_account
import google.auth.transport.requests

# ========== Configuration ==========
FIREBASE_URL = os.environ.get("FIREBASE_URL", "https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app").rstrip('/')
SERVICE_ACCOUNT_INFO = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

if not SERVICE_ACCOUNT_INFO:
    raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable must be set.")

SET_URL = "https://www.set.or.th/en/market/product/stock/overview"
UPDATE_INTERVAL = 15  # seconds
SCOPES = ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/firebase.database"]
# ===================================

app = Flask(__name__)

# ---------- Firebase Access Token Generator ----------
def get_firebase_access_token():
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_INFO)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        print(f"[{datetime.now().isoformat()}] Access token obtained successfully.")
        return credentials.token
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Service account JSON is invalid: {e}")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Failed to get access token: {e}")
    return None

# ---------- SET Data Fetcher ----------
def fetch_set_data():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(SET_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Network error fetching SET: {e}")
        return None, None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = None
        for tbl in soup.find_all('table'):
            if any('index' in th.get_text(strip=True).lower() for th in tbl.find_all('th')):
                table = tbl
                break
        if not table:
            print(f"[{datetime.now().isoformat()}] ERROR: Table not found on SET page.")
            return None, None

        first_row = table.find('tbody').find('tr') if table.find('tbody') else table.find('tr')
        cells = first_row.find_all('td')
        if len(cells) < 8:
            print(f"[{datetime.now().isoformat()}] ERROR: Unexpected table structure.")
            return None, None

        last = cells[1].get_text(strip=True).replace(',', '')
        value = cells[7].get_text(strip=True).replace(',', '')
        print(f"[{datetime.now().isoformat()}] Fetched SET data: last={last}, value={value}")
        return last, value
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Parsing SET page: {e}")
        return None, None

def update_firebase(last, value):
    if last is None or value is None:
        return False

    access_token = get_firebase_access_token()
    if not access_token:
        return False

    headers = {"Authorization": f"Bearer {access_token}"}

    # Update live_set
    set_url = f"{FIREBASE_URL}/live_2d/live_set.json"
    try:
        r = requests.put(set_url, json=last, headers=headers)
        r.raise_for_status()
        print(f"[{datetime.now().isoformat()}] Firebase live_set updated successfully.")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: live_set update failed. Status: {r.status_code if 'r' in locals() else 'N/A'}, Response: {r.text if 'r' in locals() else 'N/A'}, Error: {e}")
        return False

    # Update live_value
    value_url = f"{FIREBASE_URL}/live_2d/live_value.json"
    try:
        r = requests.put(value_url, json=value, headers=headers)
        r.raise_for_status()
        print(f"[{datetime.now().isoformat()}] Firebase live_value updated successfully.")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: live_value update failed. Status: {r.status_code if 'r' in locals() else 'N/A'}, Response: {r.text if 'r' in locals() else 'N/A'}, Error: {e}")
        return False

    print(f"[{datetime.now().isoformat()}] Firebase updated: live_set={last}, live_value={value}")
    return True

# ---------- Background Scraper Thread ----------
def scraper_loop():
    while True:
        last, value = fetch_set_data()
        if last and value:
            update_firebase(last, value)
        else:
            print(f"[{datetime.now().isoformat()}] WARNING: No SET data to update.")
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
    thread = threading.Thread(target=scraper_loop, daemon=True)
    thread.start()
    print(f"[{datetime.now().isoformat()}] Scraper thread started. Web server running...")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
