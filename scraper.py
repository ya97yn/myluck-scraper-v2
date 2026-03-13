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
    now_mm = datetime.now(mm_tz)
    current_time = now_mm.strftime("%d %b %Y %H:%M:%S")
    
    data_2d = {
        "update_time": current_time,
        "market_status": "Waiting",
        "live_set": "-",
        "live_value": "-",
        "main_result": "--"
    }
    last_draw = {"date": "-", "first_prize": "-", "result": "-"}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # --- 2D & Status Scraping ---
    try:
        res_2d = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # Market Status ကို Website ထဲကအတိုင်း အတိအကျရှာခြင်း
        # class ထဲမှာ 'market-status' ပါတဲ့ tag ကို ရှာပါမယ်
        status_tag = soup_2d.find(class_=lambda x: x and 'market-status' in x)
        if status_tag:
            # "Market Status: Pre-Open2" ထဲက "Pre-Open2" ကိုပဲ ယူပါမယ်
            status_text = status_tag.get_text(strip=True).replace("Market Status:", "").strip()
            data_2d["market_status"] = status_text if status_text else "Waiting"

        row = soup_2d.find('tr', {'indexselected': '0'})
        if row:
            c2 = row.find('td', {'aria-colindex': '2'})
            c8 = row.find('td', {'aria-colindex': '8'})
            if c2 and c8:
                sv = c2.get_text(strip=True).replace(',', '')
                vv = c8.get_text(strip=True).replace(',', '')
                if sv and vv and sv != "-":
                    data_2d.update({"live_set": sv, "live_value": vv})
                    data_2d["main_result"] = sv[-1] + vv.split('.')[0][-1]
    except: pass

    # --- 3D Scraping (GLO Website) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        h2_date = soup_3d.find('h2', {'data-v-4d58a094': True})
        if h2_date:
            last_draw["date"] = h2_date.get_text(strip=True)
            
        award_div = soup_3d.find('div', class_='award1-item')
        if award_div:
            p_tag = award_div.find('p', class_='award1-item-sub')
            if p_tag:
                clean_prize = "".join(filter(str.isdigit, p_tag.get_text(strip=True)))
                if len(clean_prize) >= 6:
                    last_draw["first_prize"] = clean_prize
                    last_draw["result"] = clean_prize[-3:]
    except: pass

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v14 (Final Status Fix) Started...")
    while True:
        if firebase_admin._apps:
            d2, d3 = get_live_data()
            try:
                # Firebase သို့ ဒေတာပို့ခြင်း
                db.reference('live_2d').update(d2)
                db.reference('result_3d/last_draw').update(d3)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v14 is Live and Running", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
        
