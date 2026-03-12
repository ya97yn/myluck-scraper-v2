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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.set.or.th/en/market/product/stock/overview'
    }

    try:
        url_2d = "https://www.set.or.th/en/market/product/stock/overview"
        res = requests.get(url_2d, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # aria-colindex="2" (live_set) နှင့် aria-colindex="8" (live_value) ကို ရှာခြင်း
        set_row = soup.find('tr', {'indexselected': '0'})
        if set_row:
            # သင်ညွှန်ပြထားသော Column 2
            col_2 = set_row.find('td', {'aria-colindex': '2'})
            # သင်ညွှန်ပြထားသော Column 8
            col_8 = set_row.find('td', {'aria-colindex': '8'})
            
            if col_2 and col_8:
                # div ထဲမှာ ရှိနေရင်လည်း text ကို ဆွဲထုတ်ပေးပါလိမ့်မယ်
                set_val = col_2.get_text(strip=True).replace(',', '')
                val_mbaht = col_8.get_text(strip=True).replace(',', '')
                
                data_2d["live_set"] = set_val
                data_2d["live_value"] = val_mbaht
                
                # 2D Result တွက်ချက်ခြင်း (ဂဏန်းရှိမှ တွက်ပါမည်)
                if set_val and val_mbaht and any(char.isdigit() for char in set_val):
                    # ဒသမကိန်း၏ နောက်ဆုံးဂဏန်းကို ယူရန် logic
                    res_2d = set_val[-1] + val_mbaht.split('.')[0][-1]
                    data_2d["main_result"] = res_2d
    except Exception as e:
        print(f">>> Scraping Error: {e}")

    return data_2d

def scraper_loop():
    print(">>> HTML Scraper (Col 2 & 8) Started...")
    while True:
        d2 = get_live_data()
        try:
            db.reference('live_2d').update(d2)
            print(f">>> Sync: {d2['update_time']} | SET: {d2['live_set']} | VAL: {d2['live_value']}")
        except Exception as e:
            print(f">>> Firebase Update Error: {e}")
        time.sleep(15)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return f"SET Scraper Active. MM Time: {datetime.now(mm_tz).strftime('%I:%M:%S %p')}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
