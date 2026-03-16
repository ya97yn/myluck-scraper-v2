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
    # မြန်မာစံတော်ချိန်ကို ယူခြင်း
    now_mm = datetime.now(mm_tz)
    
    data_2d = {
        "update_time": now_mm.strftime('%I:%M:%S %p'), # မြန်မာစံတော်ချိန်ပြောင်းလဲခြင်း
        "market_status": "Waiting",
        "live_set": "-", 
        "live_value": "-", 
        "main_result": "--",
        "date": now_mm.strftime('%Y-%m-%d')
    }
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

    try:
        res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # ၁။ Market Status
        status_parent = soup_2d.find("div", class_="text-black")
        if status_parent:
            status_span = status_parent.find("span")
            if status_span:
                data_2d["market_status"] = status_span.get_text(strip=True)

        # ၂။ Live SET & Value
        row = soup_2d.find("tr", {"indexselected": "0"})
        if row:
            c2 = row.find("td", {"aria-colindex": "2"})
            c5 = row.find("td", {"aria-colindex": "5"})
            if c2: data_2d["live_set"] = c2.get_text(strip=True).replace(',', '')
            if c5: data_2d["live_value"] = c5.get_text(strip=True).replace(',', '')

        # 2D Result တွက်ချက်ခြင်း
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s, v = data_2d["live_set"], data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]
            
    except Exception as e:
        print(f">>> Scraping Error: {e}")

    return data_2d

def scraper_loop():
    print(">>> Scraper v24 (Custom Logic) Started...")
    last_saved_result = "" # ထပ်နေတာတွေမသိမ်းမိအောင်

    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            now_mm = datetime.now(mm_tz)
            current_time_str = now_mm.strftime('%H:%M') # ၂၄ နာရီ format နဲ့ စစ်မယ်
            today_date = now_mm.strftime('%Y-%m-%d')

            try:
                # ၁။ လက်ရှိ Live Data ကို အမြဲ Update လုပ်မယ်
                # (Modern/Internet တွေကို Manual ရိုက်ထားတာ မပျက်စေဖို့ update ပဲသုံးပါမယ်)
                db.reference('live_2d').update(d2)

                # ၂။ History သိမ်းဆည်းခြင်း (Result ပြောင်းလဲမှသာ သိမ်းမယ်)
                if d2["main_result"] != "--" and d2["main_result"] != last_saved_result:
                    history_ref = db.reference(f'history_2d/{today_date}/{now_mm.strftime("%H-%M-%S")}')
                    history_ref.set(d2)
                    last_saved_result = d2["main_result"]

                # ၃။ Morning သိမ်းဆည်းခြင်း (12:02 PM)
                if current_time_str == "12:02":
                    db.reference('live_2d/Morning').update({
                        "set": d2["live_set"],
                        "value": d2["live_value"],
                        "result": d2["main_result"]
                    })
                    print(">>> Morning Data Saved at 12:02 PM")

                # ၄။ Evening သိမ်းဆည်းခြင်း (16:35 PM)
                if current_time_str == "16:35":
                    db.reference('live_2d/Evening').update({
                        "set": d2["live_set"],
                        "value": d2["live_value"],
                        "result": d2["main_result"]
                    })
                    print(">>> Evening Data Saved at 16:35 PM")

                print(f">>> Updated FB: {d2['update_time']} | Result: {d2['main_result']}")

            except Exception as e:
                print(f">>> FB Update Error: {e}")
        
        time.sleep(10) # ၂၀ စက္ကန့်တစ်ခါ စစ်ဆေးမယ်

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v24 is Running (Custom Logic)", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
