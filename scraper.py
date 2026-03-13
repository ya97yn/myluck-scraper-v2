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
# Render logs များတွင် စာသားများ ချက်ချင်းပေါ်လာစေရန်
os.environ['PYTHONUNBUFFERED'] = "1"
# ဗန်ကောက်စံတော်ချိန် သတ်မှတ်ခြင်း (SET Index အချိန်နှင့် ကိုက်ညီစေရန်)
bkk_tz = pytz.timezone('Asia/Bangkok')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            # Render Environment Variable မှ Key ကို ယူခြင်း
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
        
        # ၁။ Market Status ကို Website မှ တိုက်ရိုက်ဖတ်ခြင်း (Pre-Open2 စသည်)
        status_tag = soup.find('div', class_=lambda x: x and 'market-status' in x)
        if status_tag:
            data_2d["market_status"] = status_tag.get_text(strip=True)
        
        # ၂။ SET Index (Last) နှင့် Value (M.Baht) ကို Table မှ ရှာဖွေခြင်း
        row = soup.find('tr', {'indexselected': '0'})
        if row:
            cells = row.find_all('td')
            if len(cells) >= 8:
                # ဒေတာများကို သန့်စင်ပြီး Format ချခြင်း
                raw_last = cells[1].get_text(strip=True).replace(',', '')
                raw_value = cells[7].get_text(strip=True).replace(',', '')
                
                live_set = "{:.2f}".format(float(raw_last))
                live_value = "{:.2f}".format(float(raw_value))
                
                # 2D Result တွက်ချက်ခြင်း
                main_result = live_set[-1] + live_value.split('.')[0][-1]
                
                data_2d.update({
                    "live_set": live_set,
                    "live_value": live_value,
                    "main_result": main_result
                })
                
                # ၃။ Morning/Evening Structure အလိုက် ဒေတာခွဲထည့်ခြင်း
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
    print(">>> BeautifulSoup Scraper v9 Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            try:
                # live_2d node အောက်သို့ update လုပ်ခြင်း
                db.reference('live_2d').update(d2)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> Firebase Update Error: {e}")
        # ၂၀ စက္ကန့်တစ်ခါ ဒေတာအသစ်စစ်ဆေးမည်
        time.sleep(20)

if initialize_firebase():
    # Scraper ကို Thread တစ်ခုအနေဖြင့် နောက်ကွယ်တွင် ပတ်ခိုင်းထားခြင်း
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return "Scraper v9 is Live and Running", 200

if __name__ == "__main__":
    # Render ၏ Port သတ်မှတ်ချက်ကို ယူခြင်း
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
