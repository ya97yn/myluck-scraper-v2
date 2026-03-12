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

def get_2d_data():
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {'User-Agent': 'Mozilla/5.0'}
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
                formatted_time = datetime.now(bkk_tz).strftime("%I:%M:%S %p")

                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown'),
                    "update_time": formatted_time
                }
    except Exception as e:
        print(f">>> API Error: {e}")
    return None

def scraper_loop():
    print(">>> Scraper Background Thread Started! Data syncing...")
    while True:
        data = get_2d_data()
        if data:
            db.reference('live_2d').update(data)
            print(f">>> Firebase Updated: {data['update_time']} | Result: {data['main_result']}")
        time.sleep(15)

# ==========================================
# အဓိက ပြင်ဆင်ချက် (Gunicorn အတွက်)
# Scraper Loop ကို __main__ အပြင်ဘက်တွင် တိုက်ရိုက် စတင်ပေးခြင်း
# ==========================================
if initialize_firebase():
    thread = threading.Thread(target=scraper_loop, daemon=True)
    thread.start()

@app.route('/')
def home():
    return "SET Scraper is successfully running in the background!", 200

# လောလောဆယ် Local မှာ Run ဖို့အတွက်သာ (Render တွင် gunicorn က ဤအပိုင်းကို ကျော်သွားမည်)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
