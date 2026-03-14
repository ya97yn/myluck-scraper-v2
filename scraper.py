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
    data_2d = {
        "update_time": "-",
        "market_status": "Waiting",
        "live_set": "-", "live_value": "-", "main_result": "--"
    }
    last_draw = {"date": "-", "first_prize": "-", "result": "-"}
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

    # --- 2D Scraping (SET Home) ---
    try:
        res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # ၁။ Market Status (မြှားအစိမ်းရောင်နေရာ)
        status_div = soup_2d.find("div", class_="text-black")
        if status_div:
            status_span = status_div.find("span")
            if status_span:
                data_2d["market_status"] = status_span.get_text(strip=True)

        # ၂။ Update Time (မြှားအဝါရောင်နေရာ - "Last update" စာသားဖယ်ထုတ်ခြင်း)
        # raw-html class ပါသော parent div ထဲက ဒုတိယမြောက် div ကို ယူပါမည်
        parent_raw = soup_2d.select_one(".raw-html")
        if parent_raw:
            all_divs = parent_raw.find_all("div", recursive=False)
            if len(all_divs) >= 2:
                time_raw = all_divs[1].get_text(strip=True)
                # စာသားထဲမှ ရှေ့ဆက်များကို အကုန်ဖယ်ထုတ်ပါသည်
                for word in ["Last updated", "Last update"]:
                    time_raw = time_raw.replace(word, "")
                data_2d["update_time"] = time_raw.strip()

        # ၃။ Live SET & Value (tr indexselected="0" မှ ယူခြင်း)
        row = soup_2d.find("tr", {"indexselected": "0"})
        if row:
            # Live SET
            c2 = row.find("td", {"aria-colindex": "2"})
            if c2: data_2d["live_set"] = c2.get_text(strip=True).replace(',', '')
            # Live Value
            c5 = row.find("td", {"aria-colindex": "5"})
            if c5: data_2d["live_value"] = c5.get_text(strip=True).replace(',', '')

        # 2D Result တွက်ချက်ခြင်း
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s, v = data_2d["live_set"], data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]
    except: pass

    # --- 3D Scraping (GLO - Exact HTML Target) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # ၄။ 3D Date (col-12 col-md-6 col-lg-8 ထဲမှ h2)
        date_container = soup_3d.find("div", class_="col-12 col-md-6 col-lg-8")
        if date_container:
            h2_tag = date_container.find("h2")
            if h2_tag:
                last_draw["date"] = h2_tag.get_text(strip=True).replace("Draw dated", "").strip()
            
        # ၅။ First Prize (col-12 d-flex flex-column flex-md-row အောက်ရှိ award1-item-sub)
        prize_container = soup_3d.find("div", class_="col-12 d-flex flex-column flex-md-row")
        if prize_container:
            award_p = prize_container.find("p", class_="award1-item-sub")
            if award_p:
                val = "".join(filter(str.isdigit, award_p.get_text(strip=True)))
                if len(val) >= 6:
                    last_draw["first_prize"] = val
                    last_draw["result"] = val[-3:]
    except: pass

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v22 (Final Precise Fix) Started...")
    while True:
        if firebase_admin._apps:
            d2, d3 = get_live_data()
            try:
                db.reference('live_2d').update(d2)
                db.reference('result_3d/last_draw').update(d3)
                print(f">>> Updated: {d2['update_time']} | Status: {d2['market_status']}")
            except Exception as e:
                print(f">>> FB Error: {e}")
        time.sleep(20)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v22 Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
