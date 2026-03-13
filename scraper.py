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
    # 3D structure အသစ်
    last_draw = {"date": "-", "first_prize": "-", "result": "-"}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # --- 2D Scraping ---
    try:
        res_2d = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        status_div = soup_2d.find('div', class_=lambda x: x and 'market-status' in x)
        if status_div:
            data_2d["market_status"] = status_div.get_text(strip=True)
            
        time_span = soup_2d.find('span', class_='market-datetime')
        if time_span:
            data_2d["update_time"] = time_span.get_text(strip=True)

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

    # --- 3D Scraping (Nesting Fix) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # Draw Date ရှာဖွေခြင်း (h2 tag အောက်က font tag ထဲအထိ ဖတ်မည်)
        h2_date_tag = soup_3d.find('h2', {'data-v-4d58a094': True})
        if h2_date_tag:
            # get_text() သည် tag ပေါင်းစုံထဲက စာသားအားလုံးကို စုစည်းပေးပါသည်
            last_draw["date"] = h2_date_tag.get_text(strip=True)
            
        # First Prize ရှာဖွေခြင်း (award1-item class အောက်က p tag ကို ယူသည်)
        award_div = soup_3d.find('div', class_='award1-item')
        if award_div:
            p_tag = award_div.find('p', class_='award1-item-sub')
            if p_tag:
                # ဂဏန်းသက်သက်ကိုပဲ ယူရန် (820866)
                raw_prize = p_tag.get_text(strip=True)
                clean_prize = "".join(filter(str.isdigit, raw_prize))
                if len(clean_prize) >= 6:
                    last_draw["first_prize"] = clean_prize
                    last_draw["result"] = clean_prize[-3:] # 866
    except: pass

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v8 (Nesting Fix) Started...")
    while True:
        d2, d3_last = get_live_data()
        try:
            db.reference('live_2d').update(d2)
            db.reference('result_3d/last_draw').update(d3_last)
            print(f">>> Updated: {d2['update_time']} | 3D Prize: {d3_last['first_prize']}")
        except Exception as e:
            print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v8 Active", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
