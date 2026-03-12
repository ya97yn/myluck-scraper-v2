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
    current_mm_time = datetime.now(mm_tz).strftime("%I:%M:%S %p")
    data_2d = {
        "update_time": current_mm_time,
        "live_set": "Waiting",
        "live_value": "Waiting",
        "main_result": "--"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        url_2d = "https://www.set.or.th/en/market/product/stock/overview"
        res = requests.get(url_2d, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ပုံထဲကအတိုင်း aria-colindex ကို သုံးပြီး တိုက်ရိုက်ရှာခြင်း
        # SET Row သည် ပထမဆုံး tr (index 0) တွင် ရှိသည်
        set_row = soup.find('tr', {'indexselected': '0'})
        if set_row:
            # aria-colindex="5" (Last) ကို ယူခြင်း
            col_5 = set_row.find('td', {'aria-colindex': '5'})
            # aria-colindex="8" (Value) ကို ယူခြင်း
            col_8 = set_row.find('td', {'aria-colindex': '8'})
            
            if col_5 and col_8:
                last_val = col_5.get_text(strip=True).replace(',', '')
                value_mbaht = col_8.get_text(strip=True).replace(',', '')
                
                data_2d["live_set"] = last_val
                data_2d["live_value"] = value_mbaht
                
                # 2D Result တွက်ချက်ခြင်း
                if last_val != "" and value_mbaht != "":
                    res_2d = last_val[-1] + value_mbaht.split('.')[0][-1]
                    data_2d["main_result"] = res_2d
    except Exception as e:
        print(f">>> Scraping Error: {e}")

    # 3D အတွက် (ယခင်ကဲ့သို့ပင် ထည့်သွင်းထားသည်)
    data_3d = {"live_3d": "---", "last_date": "---"}
    try:
        # ဒီနေရာမှာ သင်အသုံးပြုလိုတဲ့ 3D website ကို ပြောင်းလဲနိုင်ပါတယ်
        pass
    except:
        pass

    return data_2d, data_3d

def scraper_loop():
    print(">>> HTML Column Scraper Started...")
    while True:
        d2, d3 = get_live_data()
        try:
            db.reference('live_2d').update(d2)
            db.reference('live_3d').update(d3)
            print(f">>> Syncing... Time: {d2['update_time']} | SET: {d2['live_set']}")
        except Exception as e:
            print(f">>> Firebase Update Error: {e}")
        time.sleep(15)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return f"SET Scraper is Live. MM Time: {datetime.now(mm_tz).strftime('%I:%M:%S %p')}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
