import os
import json
import time
import threading
import requests
import re
from flask import Flask
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# ---------------- Firebase ----------------
def initialize_firebase():
    if not firebase_admin._apps:
        try:
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
            cred = credentials.Certificate(json.loads(sa_json))
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
            })
            print("Firebase Connected")
            return True
        except Exception as e:
            print("Firebase Error:", e)
            return False
    return True


# ---------------- Scraping ----------------
def get_live_data():
    data_2d = {
        "update_time": "-",
        "market_status": "_",
        "live_set": "-",
        "live_value": "-",
        "main_result": "--"
    }

    last_draw = {
        "date": "-",
        "first_prize": "-",
        "result": "-"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # ---------- SET ----------
    try:
        r = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Market Status
        status = re.search(r'Market Status\s+(\w+)', text)
        if status:
            data_2d["market_status"] = status.group(1)

        # Last Update
        update = re.search(r'Last Update\s+([0-9]{1,2}\s+\w+\s+[0-9]{4}\s+[0-9:]+)', text)
        if update:
            data_2d["update_time"] = update.group(1)

        # SET index row
        set_match = re.search(r'SET\s+([\d,]+\.\d+).*?([\d,]+\.\d+)', text)
        if set_match:
            data_2d["live_set"] = set_match.group(1).replace(",", "")
            data_2d["live_value"] = set_match.group(2).replace(",", "")

        # Result
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s = data_2d["live_set"]
            v = data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split(".")[0][-1]

    except Exception as e:
        print("SET Error:", e)

    # ---------- GLO ----------
    try:
        r = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        prize = re.search(r'(\d{6})', text)
        if prize:
            number = prize.group(1)
            last_draw["first_prize"] = number
            last_draw["result"] = number[-3:]

    except Exception as e:
        print("GLO Error:", e)

    return data_2d, last_draw


# ---------------- Loop ----------------
def scraper_loop():
    while True:
        try:
            d2, d3 = get_live_data()

            db.reference("live_2d").update(d2)
            db.reference("result_3d/last_draw").update(d3)

            print("Updated:", d2["main_result"], d3["result"])

        except Exception as e:
            print("Loop Error:", e)

        time.sleep(20)


# ---------------- Flask ----------------
@app.route('/')
def home():
    return "Scraper Running", 200


# ---------------- Main ----------------
if __name__ == "__main__":
    if initialize_firebase():
        threading.Thread(target=scraper_loop, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
