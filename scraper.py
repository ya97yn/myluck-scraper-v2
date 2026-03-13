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
    data_2d = {
        "update_time": now_mm.strftime("%d %b %Y %H:%M:%S"),
        "market_status": "Waiting",
        "live_set": "-", "live_value": "-", "main_result": "--"
    }
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Market Status ရှာဖွေခြင်း (Pre-Open2 အစရှိသည်)
        status_tag = soup.find(class_=lambda x: x and 'market-status' in x)
        if status_tag:
            data_2d["market_status"] = status_tag.get_text(strip=True).replace("Market Status:", "").strip()

        row = soup.find('tr', {'indexselected': '0'})
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
    return data_2d

def scraper_loop():
    print(">>> Scraper Started (Port Fix)...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            try:
                db.reference('live_2d').update(d2)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper is Active", 200

if __name__ == "__main__":
    # Port error ရှင်းရန်
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
