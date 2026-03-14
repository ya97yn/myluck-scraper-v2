import os
import json
import time
import requests
import threading
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask

app = Flask(__name__)
os.environ['PYTHONUNBUFFERED'] = "1"
mm_tz = pytz.timezone('Asia/Yangon')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
                print(">>> Firebase: Connected Successfully")
                return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
    return firebase_admin._apps is not None

def get_live_data():
    data_2d = {
        "update_time": "-",
        "market_status": "Waiting",
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
        'User-Agent': 'Mozilla/5.0'
    }

    # ---------------- 2D SET ----------------
    try:
        res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        text = soup_2d.get_text(" ", strip=True)

        # Market Status
        if "Market Status" in text:
            idx = text.find("Market Status")
            data_2d["market_status"] = text[idx:idx+50].split(":")[-1].split()[0]

        # Update Time
        if "Last Update" in text:
            idx = text.find("Last Update")
            update = text[idx:idx+40]
            data_2d["update_time"] = update.replace("Last Update", "").replace(":", "").strip()

        # SET Index Value
        import re
        match_set = re.search(r'SET Index\s+([\d,]+\.\d+)', text)
        if match_set:
            data_2d["live_set"] = match_set.group(1).replace(",", "")

        # Trading Value
        match_val = re.search(r'Value\s+\(M.Baht\)\s+([\d,]+\.\d+)', text)
        if match_val:
            data_2d["live_value"] = match_val.group(1).replace(",", "")

        # 2D Result
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s = data_2d["live_set"]
            v = data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]

    except Exception as e:
        print("2D Error:", e)

    # ---------------- 3D GLO ----------------
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        text = soup_3d.get_text(" ", strip=True)

        import re

        # First Prize 6 digit
        prize = re.search(r'รางวัลที่ 1\s+.*?\s+(\d{6})', text)
        if prize:
            number = prize.group(1)
            last_draw["first_prize"] = number
            last_draw["result"] = number[-3:]

        # Draw Date
        date = re.search(r'วันที่\s+([0-9/]+)', text)
        if date:
            last_draw["date"] = date.group(1)

    except Exception as e:
        print("3D Error:", e)

    return data_2d, last_draw


def scraper_loop():
    print(">>> Scraper v22 (Final Precise Fix) Started...")
    while True:
        if firebase_admin._apps:
            d2, d3 = get_live_data()
            try:
                db.reference('live_2d').update(d2)
                db.reference('result_3d/last_draw').update(d3)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v22 Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
