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
    current_mm_time = datetime.now(mm_tz).strftime("%d %b %Y %I:%M:%S %p")
    data_2d = {"update_time": f"Last Update {current_mm_time}", "market_status": "Market Status : -"}
    data_3d = {"draw_date": "-", "first_prize": "-", "result_3d": "-"}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # --- 2D Scraping (SET) ---
    try:
        url_2d = "https://www.set.or.th/en/market/product/stock/overview"
        res_2d = requests.get(url_2d, headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # သင်ညွှန်ပြထားသော div class မှ update_time နှင့် market_status ကို ယူခြင်း
        target_div = soup_2d.find('div', class_='d-flex flex-column col-12 col-sm-auto')
        if target_div:
            smalls = target_div.find_all('small')
            if len(smalls) >= 2:
                data_2d["update_time"] = smalls[0].get_text(strip=True)
                data_2d["market_status"] = smalls[1].get_text(strip=True)

        # Table Data (Col 2 & 8)
        row = soup_2d.find('tr', {'indexselected': '0'})
        if row:
            c2 = row.find('td', {'aria-colindex': '2'})
            c8 = row.find('td', {'aria-colindex': '8'})
            if c2 and c8:
                sv = c2.get_text(strip=True).replace(',', '')
                vv = c8.get_text(strip=True).replace(',', '')
                data_2d.update({"live_set": sv, "live_value": vv})
                if sv and vv and any(c.isdigit() for c in sv):
                    data_2d["main_result"] = sv[-1] + vv.split('.')[0][-1]
    except: pass

    # --- 3D Scraping (GLO) ---
    try:
        url_3d = "https://www.glo.or.th/home-page"
        res_3d = requests.get(url_3d, headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # Draw Date အား h2 မှ ယူခြင်း
        h2_tag = soup_3d.find('h2', {'data-v-4d58a094': True})
        if h2_tag:
            data_3d["draw_date"] = h2_tag.get_text(strip=True)
            
        # First Prize အား p class award1-item-sub မှ ယူခြင်း
        p_prize = soup_3d.find('p', class_='award1-item-sub')
        if p_prize:
            full_num = "".join(filter(str.isdigit, p_prize.get_text()))
            if len(full_num) >= 6:
                data_3d["first_prize"] = full_num[:6]
                data_3d["result_3d"] = full_num[-3:]
    except: pass

    return data_2d, data_3d

def scraper_loop():
    while True:
        d2, d3 = get_live_data()
        try:
            db.reference('live_2d').update(d2)
            db.reference('result_3d').update(d3)
            print(f">>> Firebase Updated: {d2['update_time']}")
        except Exception as e:
            print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v6 Active", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
