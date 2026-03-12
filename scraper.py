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
    current_mm_time = datetime.now(mm_tz).strftime("%d %b %Y %H:%M:%S")
    data_2d = {
        "update_time": current_mm_time,
        "market_status": "Closed",
        "live_set": "-",
        "live_value": "-"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # --- 2D Scraping (SET) ---
    try:
        res_2d = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # Market Status (Closed/Open)
        status_div = soup_2d.find('div', class_=lambda x: x and 'market-status' in x)
        if status_div:
            data_2d["market_status"] = status_div.get_text(strip=True)
            
        # Update Time
        time_span = soup_2d.find('span', class_='market-datetime')
        if time_span:
            data_2d["update_time"] = time_span.get_text(strip=True)

        # SET Row (Col 2 & 8)
        row = soup_2d.find('tr', {'indexselected': '0'})
        if row:
            c2 = row.find('td', {'aria-colindex': '2'})
            c8 = row.find('td', {'aria-colindex': '8'})
            if c2 and c8:
                sv, vv = c2.get_text(strip=True).replace(',', ''), c8.get_text(strip=True).replace(',', '')
                data_2d.update({"live_set": sv, "live_value": vv})
                if sv and vv and any(c.isdigit() for c in sv):
                    data_2d["main_result"] = sv[-1] + vv.split('.')[0][-1]
    except: pass

    # --- 3D Scraping (GLO - last_draw structure) ---
    last_draw = {"date": "-", "first_prize": "-", "result": "-"}
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # Draw Date
        h2_date = soup_3d.find('h2', {'data-v-4d58a094': True})
        if h2_date:
            last_draw["date"] = h2_date.get_text(strip=True)
            
        # First Prize
        p_prize = soup_3d.find('p', class_='award1-item-sub')
        if p_prize:
            full_num = "".join(filter(str.isdigit, p_prize.get_text()))
            if len(full_num) >= 6:
                last_draw["first_prize"] = full_num
                last_draw["result"] = full_num[-3:] # ၃ လုံးဂဏန်း
    except: pass

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v7 (Final Structure) Started...")
    while True:
        d2, d3_last = get_live_data()
        try:
            # 2D update
            db.reference('live_2d').update(d2)
            # 3D update (result_3d/last_draw အောက်သို့ ပို့ခြင်း)
            db.reference('result_3d/last_draw').update(d3_last)
            print(f">>> Sync: {d2['update_time']} | 3D Date: {d3_last['date']}")
        except Exception as e:
            print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v7 is Active", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
