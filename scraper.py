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

def is_thai_holiday(current_date_dt):
    # စနေ (5) ၊ တနင်္ဂနွေ (6) စစ်ခြင်း
    if current_date_dt.weekday() >= 5:
        return True
    
    # Firebase မှ holidays ဖတ်ခြင်း
    try:
        holidays_data = db.reference(f'holidays/{current_date_dt.year}').get()
        if holidays_data:
            formatted_date = current_date_dt.strftime('%d %b') # "17 Mar"
            for h in holidays_data:
                if h['date'] == formatted_date:
                    return True
    except: pass
    return False

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
    print(">>> Scraper v27 (Holiday Aware & Auto-Reset) Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            now_mm = datetime.now(mm_tz)
            today_date = now_mm.strftime('%Y-%m-%d')
            current_time = now_mm.strftime('%H:%M')

            try:
                # ၁။ မနက် ၉:၀၀ နာရီ Reset & History သိမ်းခြင်း (ရုံးဖွင့်ရက်မှသာ)
                if current_time == "09:00":
                    if not is_thai_holiday(now_mm):
                        live_data = db.reference('live_2d').get()
                        if live_data and live_data.get('date') != today_date:
                            old_date = live_data.get('date', 'Unknown')
                            # History သို့ ရွှေ့ခြင်း
                            history_payload = {
                                "9:30AM": live_data.get('morning', {}).get('9:30AM', {"internet": "", "modern": ""}),
                                "12:01PM": live_data.get('morning', {}).get('12:01PM', {"result": "", "set": "", "value": ""}),
                                "2:00PM": live_data.get('evening', {}).get('2:00PM', {"internet": "", "modern": ""}),
                                "4:30PM": live_data.get('evening', {}).get('4:30PM', {"result": "", "set": "", "value": ""})
                            }
                            db.reference(f'2dhistory/{old_date}').update(history_payload)
                            
                            # Live Data ကို Clear လုပ်ခြင်း
                            db.reference('live_2d').update({
                                "date": today_date,
                                "morning": {"9:30AM": {"internet": "", "modern": ""}, "12:01PM": {"result": "", "set": "", "value": ""}},
                                "evening": {"2:00PM": {"internet": "", "modern": ""}, "4:30PM": {"result": "", "set": "", "value": ""}}
                            })
                            print(f">>> History Saved for {old_date} and Live Data Reset.")

                # ၂။ Live Update လုပ်ခြင်း
                live_payload = {
                    "live_set": d2["live_set"],
                    "live_value": d2["live_value"],
                    "main_result": d2["main_result"],
                    "market_status": d2["market_status"],
                    "update_time": d2["update_time"]
                }
                
                # မနက်ပိုင်း Live (9:30 AM to 12:05 PM)
                if "09:30" <= current_time <= "12:05":
                    db.reference('live_2d/morning/12:01PM').update({
                        "set": d2["live_set"], "value": d2["live_value"], "result": d2["main_result"]
                    })
                
                # ညနေပိုင်း Live (02:00 PM to 04:35 PM)
                elif "14:00" <= current_time <= "16:35":
                    db.reference('live_2d/evening/4:30PM').update({
                        "set": d2["live_set"], "value": d2["live_value"], "result": d2["main_result"]
                    })

                db.reference('live_2d').update(live_payload)
                print(f">>> Log: {d2['update_time']} | 2D: {d2['main_result']}")

            except Exception as e:
                print(f">>> FB Error: {e}")
        
        time.sleep(5)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v27 Running - Holiday & Reset Logic Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
