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
    # Default data
    data_2d = {
        "update_time": current_mm_time,
        "market_status": "Waiting",
        "live_set": "Waiting",
        "live_value": "Waiting",
        "main_result": "--"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        url = "https://www.set.or.th/en/market/product/stock/overview"
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ၁။ update_time နှင့် market_status ကို ရှာခြင်း (ပုံထဲက small tags များ)
        small_tags = soup.find_all('small', class_='fs-12px')
        if len(small_tags) >= 2:
            # ပထမ small tag က update_time (ဥပမာ- Mar 13, 2026 10:30:00)
            data_2d["update_time"] = small_tags[0].get_text(strip=True)
            # ဒုတိယ small tag က market_status (ဥပမာ- Closed သို့မဟုတ် Open)
            data_2d["market_status"] = small_tags[1].get_text(strip=True)

        # ၂။ Table ထဲမှ Col 2 (Set) နှင့် Col 8 (Value) ကို ရှာခြင်း
        set_row = soup.find('tr', {'indexselected': '0'})
        if set_row:
            col_2 = set_row.find('td', {'aria-colindex': '2'})
            col_8 = set_row.find('td', {'aria-colindex': '8'})
            
            if col_2 and col_8:
                set_val = col_2.get_text(strip=True).replace(',', '')
                val_mbaht = col_8.get_text(strip=True).replace(',', '')
                
                data_2d["live_set"] = set_val
                data_2d["live_value"] = val_mbaht
                
                # 2D Result Logic
                if set_val and val_mbaht and any(char.isdigit() for char in set_val):
                    res_2d = set_val[-1] + val_mbaht.split('.')[0][-1]
                    data_2d["main_result"] = res_2d

    except Exception as e:
        print(f">>> Scraping Error: {e}")

    return data_2d

def scraper_loop():
    print(">>> Final Scraper Loop Started! Syncing all fields...")
    while True:
        data = get_live_data()
        try:
            db.reference('live_2d').update(data)
            print(f">>> Updated: {data['update_time']} | Status: {data['market_status']}")
        except Exception as e:
            print(f">>> Firebase Error: {e}")
        time.sleep(15)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return "SET Scraper v3 is running with full field support!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
