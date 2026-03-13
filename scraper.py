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

def get_live_data():
    now = datetime.now(bkk_tz)
    current_time = now.strftime("%I:%M:%S %p")
    
    data_2d = {
        "update_time": current_time,
        "market_status": "Waiting",
        "live_set": "-",
        "live_value": "-",
        "main_result": "--"
    }
    
    url = "https://www.set.or.th/en/market/product/stock/overview"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ၁။ Market Status ကို ပိုမိုတိကျစွာ ရှာဖွေခြင်း
        # class ထဲတွင် 'market-status' ပါဝင်သည့် မည်သည့် tag ကိုမဆို ရှာပါသည်
        status_tag = soup.find(lambda tag: tag.name in ['div', 'span'] and tag.has_attr('class') and any('market-status' in c for c in tag['class']))
        
        if status_tag:
            # Website မှရသော စာသားကို သန့်စင်ခြင်း
            status_text = status_tag.get_text(strip=True)
            if status_text:
                data_2d["market_status"] = status_text
        
        # ၂။ SET Index နှင့် Value ကို ရှာဖွေခြင်း
        row = soup.find('tr', {'indexselected': '0'})
        if row:
            cells = row.find_all('td')
            if len(cells) >= 8:
                last_val = cells[1].get_text(strip=True).replace(',', '')
                value_mbat = cells[7].get_text(strip=True).replace(',', '')
                
                if last_val and value_mbat:
                    live_set = "{:.2f}".format(float(last_val))
                    live_value = "{:.2f}".format(float(value_mbat))
                    main_result = live_set[-1] + live_value.split('.')[0][-1]
                    
                    data_2d.update({
                        "live_set": live_set,
                        "live_value": live_value,
                        "main_result": main_result
                    })
                    
                    # Firebase structure အလိုက် ဒေတာခွဲပို့ခြင်း
                    if now.hour < 13:
                        data_2d["morning"] = {"update_time": current_time}
                    else:
                        data_2d["evening"] = {
                            "live_set": live_set, 
                            "live_value": live_value, 
                            "main_result": main_result
                        }
    except Exception as e:
        print(f">>> Scraping Error: {e}")

    return data_2d

def scraper_loop():
    print(">>> Scraper v11 (Status Deep Search) Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            try:
                db.reference('live_2d').update(d2)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> FB Update Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v11 Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
