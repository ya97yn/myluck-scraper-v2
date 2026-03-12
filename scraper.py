import os
import json
import time
import requests
import threading
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, jsonify

# Configuration
app = Flask(__name__)
os.environ['PYTHONUNBUFFERED'] = "1"
bkk_tz = pytz.timezone('Asia/Bangkok')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
            else:
                cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
            })
            print(">>> Firebase: Connected Successfully")
            return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
            return False
    return True

def get_2d_data():
    try:
        # သင်ပေးထားသော တရားဝင် API Endpoint ကို သုံးထားပါသည်
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
                raw_time = set_info.get('marketDateTime', "")

                # ၁။ SET Index (live_set)
                idx = "{:.2f}".format(float(last_raw))
                
                # ၂။ Value ကို Million ပြောင်းခြင်း (သန်း)
                val_million = float(value_raw) / 1000000
                val_str = "{:.2f}".format(val_million) 
                
                # ၃။ 2D Result တွက်ချက်ခြင်း
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                # ၄။ API အချိန်ကို format ချခြင်း
                try:
                    formatted_time = raw_time.split('T')[1].split('.')[0] # ဥပမာ- 00:50:52
                except:
                    formatted_time = datetime.now(bkk_tz).strftime("%H:%M:%S")

                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown'),
                    "update_time": formatted_time
                }
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return None

def scraper_loop():
    while True:
        data = get_2d_data()
        if data:
            db.reference('live_2d').update(data)
            print(f">>> Updated: {data['update_time']} | Result={data['main_result']}")
        time.sleep(15)

@app.route('/')
def home():
    return "SET Scraper Active (API Version)", 200

if __name__ == "__main__":
    if initialize_firebase():
        # Scraper ကို thread အဖြစ် နောက်ကွယ်မှာ ပတ်ခိုင်းထားသည်
        threading.Thread(target=scraper_loop, daemon=True).start()
        
        # Flask Server စတင်ခြင်း
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
        
