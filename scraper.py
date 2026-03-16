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
        "update_time": now_mm.strftime('%I:%M:%S %p'),
        "market_status": "Waiting",
        "live_set": "-", "live_value": "-", "main_result": "--"
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

    try:
        res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        status_parent = soup_2d.find("div", class_="text-black")
        if status_parent:
            status_span = status_parent.find("span")
            if status_span:
                data_2d["market_status"] = status_span.get_text(strip=True)

        row = soup_2d.find("tr", {"indexselected": "0"})
        if row:
            c2 = row.find("td", {"aria-colindex": "2"})
            c5 = row.find("td", {"aria-colindex": "5"})
            if c2: data_2d["live_set"] = c2.get_text(strip=True).replace(',', '')
            if c5: data_2d["live_value"] = c5.get_text(strip=True).replace(',', '')

        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s, v = data_2d["live_set"], data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]
    except: pass
    return data_2d

def scraper_loop():
    print(">>> Scraper v25 (2dhistory Format Fix) Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            now_mm = datetime.now(mm_tz)
            today_date = now_mm.strftime('%Y-%m-%d')
            current_time = now_mm.strftime('%H:%M')

            try:
                # ၁။ လက်ရှိ Live Data ကို Update လုပ်ခြင်း
                db.reference('live_2d').update({
                    "live_set": d2["live_set"],
                    "live_value": d2["live_value"],
                    "main_result": d2["main_result"],
                    "market_status": d2["market_status"],
                    "update_time": d2["update_time"],
                    "date": today_date
                })

                # ၂။ 2dhistory ထဲသို့ သတ်မှတ်ချိန်အလိုက် သိမ်းဆည်းခြင်း
                history_ref = db.reference(f'2dhistory/{today_date}')

                # Morning Result (12:01 PM)
                if current_time == "12:01":
                    history_ref.child("12:01PM").update({
                        "set": d2["live_set"],
                        "value": d2["live_value"],
                        "result": d2["main_result"]
                    })

                # Evening Result (16:30 PM - or 4:30PM)
                elif current_time == "16:30":
                    history_ref.child("4:30PM").update({
                        "set": d2["live_set"],
                        "value": d2["live_value"],
                        "result": d2["main_result"]
                    })

                # 9:30 AM နဲ့ 2:00 PM အတွက် Manual ရိုက်ရန် နေရာလွတ်ကြိုဖန်တီးခြင်း (မရှိသေးရင်)
                if current_time == "09:30":
                    if not history_ref.child("9:30AM").get():
                        history_ref.child("9:30AM").update({"internet": "", "modern": ""})
                
                if current_time == "14:00":
                    if not history_ref.child("2:00PM").get():
                        history_ref.child("2:00PM").update({"internet": "", "modern": ""})

                print(f">>> Log: {d2['update_time']} | SET: {d2['live_set']} | 2D: {d2['main_result']}")

            except Exception as e:
                print(f">>> FB Update Error: {e}")
        
        time.sleep(30)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v25 Running - 2dhistory Updated", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
            
