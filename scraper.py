import os
import json
import time
import requests
import threading
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask

app = Flask(__name__)
os.environ['PYTHONUNBUFFERED'] = "1"
# မြန်မာစံတော်ချိန် (Myanmar Time) အတွက် သတ်မှတ်ခြင်း
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

def get_2d_data():
    current_mm_time = datetime.now(mm_tz).strftime("%I:%M:%S %p")
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.set.or.th/en/market/product/stock/overview'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            sectors = data.get('indexIndustrySectors', [])
            set_info = next((item for item in sectors if item.get('symbol') == 'SET'), None)
            
            if set_info:
                idx = "{:.2f}".format(float(set_info.get('last', 0)))
                val_million = float(set_info.get('value', 0)) / 1000000
                val_str = "{:.2f}".format(val_million) 
                res_2d = idx[-1] + val_str.split('.')[0][-1]

                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2_d,
                    "market_status": set_info.get('marketStatus', 'Unknown'),
                    "update_time": current_mm_time # မြန်မာစံတော်ချိန်
                }
    except Exception as e:
        print(f">>> API Error: {e}")
    
    # API မှ ဒေတာမရလျှင်လည်း အချိန်ကိုသာ Update လုပ်ရန် ပို့ပေးခြင်း
    return {
        "update_time": current_mm_time,
        "market_status": "Waiting for Market..."
    }

def scraper_loop():
    print(">>> Scraper Background Thread Started! Syncing with Myanmar Time...")
    while True:
        data = get_2d_data()
        if data:
            try:
                # ဒေတာအကုန်မရလျှင်လည်း ရှိသလောက် (အထူးသဖြင့် အချိန်) ကို Update လုပ်မည်
                db.reference('live_2d').update(data)
                print(f">>> Firebase Sync: {data['update_time']}")
            except Exception as e:
                print(f">>> Firebase Update Error: {e}")
        time.sleep(15)

# Scraper ကို စတင်ခြင်း
if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    mm_now = datetime.now(mm_tz).strftime("%I:%M:%S %p")
    return f"SET Scraper Active. Current Myanmar Time: {mm_now}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
