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
        # Website ထက် ပိုမိုမြန်ဆန်တည်ငြိမ်သော API ကို အသုံးပြုထားပါသည်
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
                # သင်အလိုရှိသော Column (Last) နှင့် Column Value (M.Baht) တို့ကို ယူခြင်း
                last_raw = set_info.get('last', 0)
                value_raw = set_info.get('value', 0)
                raw_time = set_info.get('marketDateTime', "")

                # ၁။ live_set (Index Last)
                idx = "{:.2f}".format(float(last_raw))
                
                # ၂။ live_value (Million format သို့ တိုက်ရိုက်ပြောင်းခြင်း)
                # API မှလာသော Value သည် 64496480000 ပုံစံဖြစ်သဖြင့် Million ပြောင်းရန် ၁ သန်းနှင့် စားပါသည်
                val_million = float(value_raw) / 1000000
                val_str = "{:.2f}".format(val_million) 
                
                # ၃။ 2D Result တွက်ချက်ခြင်း (SET နောက်ဆုံးဂဏန်း + Value အစက်ရှေ့ နောက်ဆုံးဂဏန်း)
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                # ၄။ Market Time ကို AM/PM format သို့ ပြောင်းလဲခြင်း
                try:
                    dt_obj = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                    formatted_time = dt_obj.astimezone(bkk_tz).strftime("%I:%M:%S %p")
                except:
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
    while True:
        data = get_2d_data()
        if data:
            # သင်၏ Firebase Structure အတိုင်း live_2d အောက်သို့ update လုပ်ခြင်း
            db.reference('live_2d').update(data)
            print(f">>> Firebase Updated: {data['update_time']} | {data['main_result']}")
        time.sleep(15)

@app.route('/')
def home():
    return "SET Scraper Online", 200

if __name__ == "__main__":
    if initialize_firebase():
        threading.Thread(target=scraper_loop, daemon=True).start()
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
