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
# တိကျသော အချိန်ရရှိရန် Bangkok Time သုံးပါသည်
bkk_tz = pytz.timezone('Asia/Bangkok')

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
    now = datetime.now(bkk_tz)
    data_2d = {
        "update_time": now.strftime("%I:%M:%S %p"),
        "market_status": "Open",
        "live_set": "Waiting",
        "live_value": "Waiting"
    }
    
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        # API ကို တိုက်ရိုက်သုံးခြင်းက ပိုမိုမြန်ဆန်ပြီး တိကျပါသည်
        res = requests.get("https://www.set.or.th/api/set/index/info/list?type=INDEX", headers=headers, timeout=15)
        if res.status_code == 200:
            sectors = res.json().get('indexIndustrySectors', [])
            set_info = next((item for item in sectors if item.get('symbol') == 'SET'), None)
            
            if set_info:
                idx = "{:.2f}".format(float(set_info.get('last', 0)))
                val_million = float(set_info.get('value', 0)) / 1000000
                val_str = "{:.2f}".format(val_million)
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                data_2d.update({
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown')
                })
                
                # Morning/Evening structure အလိုက် ဒေတာခွဲထည့်ခြင်း
                if now.hour < 13:
                    data_2d["morning"] = {"update_time": data_2d["update_time"]}
                else:
                    data_2d["evening"] = {"live_set": idx, "live_value": val_str, "main_result": res_2d}
    except Exception as e:
        print(f">>> Scraping Error: {e}")
    
    return data_2d

def scraper_loop():
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            try:
                db.reference('live_2d').update(d2)
                print(f">>> Updated Firebase: {d2['update_time']}")
            except Exception as e:
                print(f">>> DB Update Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper is Running", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
