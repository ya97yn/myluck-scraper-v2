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
bkk_tz = pytz.timezone('Asia/Bangkok')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            # Render Environment Variable မှ Key ကို ယူခြင်း
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
            if sa_json:
                cred_dict = json.loads(sa_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
                print(">>> Firebase: Connected Successfully")
                return True
            else:
                print(">>> Firebase Error: FIREBASE_SERVICE_ACCOUNT not found in environment")
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
    return firebase_admin._apps is not None

def get_2d_data():
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.set.or.th/en/home'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            sectors = data.get('indexIndustrySectors', [])
            set_info = next((item for item in sectors if item.get('symbol') == 'SET'), None)
            
            if set_info:
                last_raw = set_info.get('last', 0)
                value_raw = set_info.get('value', 0)
                
                # ဒေတာများကို format ချခြင်း
                idx = "{:.2f}".format(float(last_raw))
                val_million = float(value_raw) / 1000000
                val_str = "{:.2f}".format(val_million)
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown'),
                    "update_time": datetime.now(bkk_tz).strftime("%I:%M:%S %p")
                }
    except Exception as e:
        print(f">>> API Fetch Error: {e}")
    return None

def scraper_loop():
    print(">>> Scraper Loop Started...")
    while True:
        try:
            data = get_2d_data()
            if data:
                # သင်၏ JSON export အရ live_2d အောက်သို့ တိုက်ရိုက် update လုပ်ခြင်း
                db.reference('live_2d').update(data)
                print(f">>> Firebase Updated: {data['update_time']} | {data['main_result']}")
            else:
                print(">>> Waiting for valid API data...")
        except Exception as e:
            print(f">>> Update Error: {e}")
        time.sleep(15)

@app.route('/')
def home():
    return "Scraper Connection Active", 200

if __name__ == "__main__":
    if initialize_firebase():
        # Scraper ကို သီးသန့် thread ဖြင့် ပတ်ခိုင်းခြင်း
        thread = threading.Thread(target=scraper_loop, daemon=True)
        thread.start()
        
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
        
