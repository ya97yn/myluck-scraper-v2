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

    # --- 2D HTML Scraping ---
    try:
        url_2d = "https://www.set.or.th/en/market/product/stock/overview"
        res = requests.get(url_2d, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Table ထဲမှ SET row ကို ရှာဖွေခြင်း
        table = soup.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols and "SET" in cols[0].get_text(strip=True):
                    # သင်အလိုရှိသော Last နှင့် Value (M.Baht)
                    last_val = cols[1].get_text(strip=True).replace(',', '')
                    value_mbaht = cols[7].get_text(strip=True).replace(',', '')
                    
                    data_2d["live_set"] = last_val
                    data_2d["live_value"] = value_mbaht
                    # 2D Result တွက်ချက်ခြင်း (SET နောက်ဆုံးဂဏန်း + Value အစက်ရှေ့ နောက်ဆုံးဂဏန်း)
                    res_2d = last_val[-1] + value_mbaht.split('.')[0][-1]
                    data_2d["main_result"] = res_2d
                    break
    except Exception as e:
        print(f">>> 2D Scraping Error: {e}")

    # --- 3D HTML Scraping ---
    data_3d = {"live_3d": "Waiting", "last_date": "--"}
    try:
        url_3d = "https://www.thailotto.com/" # နမူနာ website
        res_3d = requests.get(url_3d, headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        # ဤနေရာတွင် 3D result ပါသော HTML tag ကို ရှာရပါမည်
        # ဥပမာ - results = soup_3d.find('div', class_='3d-result').text
        data_3d["live_3d"] = "123" # နမူနာဂဏန်း
        data_3d["last_date"] = "16-03-2026"
    except:
        pass

    return data_2d, data_3d

def scraper_loop():
    print(">>> Scraper Started (2D/3D HTML Syncing...)")
    while True:
        d2, d3 = get_live_data()
        try:
            # Firebase Structure အတိုင်း update လုပ်ခြင်း
            db.reference('live_2d').update(d2)
            db.reference('live_3d').update(d3)
            print(f">>> Sync OK: {d2['update_time']}")
        except Exception as e:
            print(f">>> Firebase Update Error: {e}")
        time.sleep(15)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return f"Live Scraper Active. Time: {datetime.now(mm_tz).strftime('%I:%M:%S %p')}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
