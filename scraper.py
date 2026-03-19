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
    if current_date_dt.weekday() >= 5: # စနေ၊ တနင်္ဂနွေ
        return True
    try:
        holidays_data = db.reference(f'holidays/{current_date_dt.year}').get()
        if holidays_data:
            formatted_date = current_date_dt.strftime('%d %b')
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
    
    # Scraping Time Windows စစ်ဆေးခြင်း
    current_time_val = now_mm.hour * 3600 + now_mm.minute * 60 + now_mm.second
    # 9:30:00 AM (34200) to 12:01:15 PM (43275)
    is_morning_window = 34200 <= current_time_val <= 43275
    # 1:30:00 PM (48600) to 4:30:15 PM (59415)
    is_evening_window = 48600 <= current_time_val <= 59415

    if is_morning_window or is_evening_window:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        try:
            res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=8)
            soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
            
            status_parent = soup_2d.find("div", class_="text-black")
            if status_parent:
                status_span = status_parent.find("span")
                if status_span: data_2d["market_status"] = status_span.get_text(strip=True)

            row = soup_2d.find("tr", {"indexselected": "0"})
            if row:
                c2 = row.find("td", {"aria-colindex": "2"})
                c5 = row.find("td", {"aria-colindex": "5"})
                if c2: data_2d["live_set"] = c2.get_text(strip=True).replace(',', '')
                if c5: data_2d["live_value"] = c5.get_text(strip=True).replace(',', '')

            if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
                s, v = data_2d["live_set"], data_2d["live_value"]
                data_2d["main_result"] = s[-1] + v.split('.')[0][-1]
        except Exception as e:
            print(f">>> Scraping Error: {e}")
    else:
        print(f">>> Out of Window: {now_mm.strftime('%I:%M:%S %p')} - Scraping Paused")

    return data_2d

def scraper_loop():
    print(">>> Scraper v28 (Exact Time Window) Started...")
    while True:
        if firebase_admin._apps:
            d2 = get_live_data()
            now_mm = datetime.now(mm_tz)
            today_date = now_mm.strftime('%Y-%m-%d')
            current_time = now_mm.strftime('%H:%M')
            current_time_val = now_mm.hour * 3600 + now_mm.minute * 60 + now_mm.second

            try:
                # ၁။ မနက် ၉:၀၀ နာရီ Reset & History သိမ်းခြင်း
                if current_time == "09:00":
                    if not is_thai_holiday(now_mm):
                        live_data = db.reference('live_2d').get()
                        if live_data and live_data.get('date') != today_date:
                            old_date = live_data.get('date', 'Unknown')
                            history_payload = {
                                "9:30AM": live_data.get('morning', {}).get('9:30AM', {"internet": "", "modern": ""}),
                                "12:01PM": live_data.get('morning', {}).get('12:01PM', {"result": "", "set": "", "value": ""}),
                                "2:00PM": live_data.get('evening', {}).get('2:00PM', {"internet": "", "modern": ""}),
                                "4:30PM": live_data.get('evening', {}).get('4:30PM', {"result": "", "set": "", "value": ""})
                            }
                            db.reference(f'2dhistory/{old_date}').update(history_payload)
                            db.reference('live_2d').update({
                                "date": today_date,
                                "morning": {"9:30AM": {"internet": "", "modern": ""}, "12:01PM": {"result": "", "set": "", "value": ""}},
                                "evening": {"2:00PM": {"internet": "", "modern": ""}, "4:30PM": {"result": "", "set": "", "value": ""}}
                            })
                            print(f">>> Data Archived for {old_date}")

                # ၂။ Live Section Update (Window အတွင်းသာ Update လုပ်မည်)
                # 9:30:00 AM to 12:01:15 PM
                if 34200 <= current_time_val <= 43275:
                    db.reference('live_2d/morning/12:01PM').update({
                        "set": d2["live_set"], "value": d2["live_value"], "result": d2["main_result"]
                    })
                # 1:30:00 PM (48600) to 4:30:15 PM (59415)
                elif 48600 <= current_time_val <= 59415:
                    db.reference('live_2d/evening/4:30PM').update({
                        "set": d2["live_set"], "value": d2["live_value"], "result": d2["main_result"]
                    })

                db.reference('live_2d').update({
                    "live_set": d2["live_set"], "live_value": d2["live_value"],
                    "main_result": d2["main_result"], "market_status": d2["market_status"],
                    "update_time": d2["update_time"]
                })
                
            except Exception as e:
                print(f">>> Update Error: {e}")
        
        time.sleep(8) # Window အတွင်း ၈ စက္ကန့်တစ်ခါ စစ်ပါမည်

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v28 Running - Accurate Windows", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
