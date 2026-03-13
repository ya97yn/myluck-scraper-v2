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
# Render logs အတွက် ပတ်ဝန်းကျင် ပြင်ဆင်ခြင်း
os.environ['PYTHONUNBUFFERED'] = "1"
# ဗန်ကောက်စံတော်ချိန် သတ်မှတ်ခြင်း
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
    # လက်ရှိအချိန်ကို ယူခြင်း
    now = datetime.now(bkk_tz)
    current_time = now.strftime("%I:%M:%S %p")
    
    data_2d = {
        "update_time": current_time,
        "market_status": "Closed",
        "live_set": "Waiting",
        "live_value": "Waiting",
        "main_result": "--"
    }
    
    url = "https://www.set.or.th/en/market/product/stock/overview"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Table ထဲမှ SET row ကို ရှာဖွေခြင်း (indexselected='0' သည် SET row ဖြစ်သည်)
        row = soup.find('tr', {'indexselected': '0'})
        
        if row:
            # Column 2 (Last) နှင့် Column 8 (Value M.Baht) ကို ယူခြင်း
            cells = row.find_all('td')
            if len(cells) >= 8:
                # ဒေတာများကို သန့်စင်ခြင်း (ကော်မာများ ဖယ်ထုတ်ခြင်း)
                last_val = cells[1].get_text(strip=True).replace(',', '')
                value_mbat = cells[7].get_text(strip=True).replace(',', '')
                
                # ဒေတာများကို format ချခြင်း
                live_set = "{:.2f}".format(float(last_val))
                live_value = "{:.2f}".format(float(value_mbat))
                
                # 2D Result တွက်ချက်ခြင်း (SET နောက်ဆုံးဂဏန်း + Value အစက်ရှေ့ နောက်ဆုံးဂဏန်း)
                main_result = live_set[-1] + live_value.split('.')[0][-1]
                
                data_2d.update({
                    "live_set": live_set,
                    "live_value": live_value,
                    "main_result": main_result,
                    "market_status": "Open"
                })
                
                # သင်၏ Firebase structure (morning/evening) ထဲသို့ အချိန်အလိုက် ထည့်သွင်းခြင်း
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
    print(">>> BeautifulSoup Scraper Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            try:
                # live_2d node အောက်သို့ ဒေတာများကို update လုပ်ခြင်း
                db.reference('live_2d').update(d2)
                print(f">>> Updated: {d2['update_time']} | 2D: {d2.get('main_result', '--')}")
            except Exception as e:
                print(f">>> Firebase Update Error: {e}")
        time.sleep(20) # ၂၀ စက္ကန့်တစ်ခါ ပတ်မည်

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return "BeautifulSoup Scraper Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
