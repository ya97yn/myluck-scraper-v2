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
        
        # ၁။ Market Status နှင့် Update Time
        # raw-html class ပါသော div အောက်ရှိ div များကို ရှာပါမည်
        parent_div = soup_2d.select_one(".d-flex.justify-content-between.justify-content-md-start.fs-12px.raw-html")
        if parent_div:
            child_divs = parent_div.find_all("div", recursive=False)
            if len(child_divs) >= 2:
                # ပထမ div (text-black) ထဲက market_status ယူခြင်း
                status_span = child_divs[0].find("span")
                if status_span:
                    data_2d["market_status"] = status_span.get_text(strip=True)
                
                # ဒုတိယ div ထဲက update_time ယူခြင်း (မြှားအဝါရောင်နေရာ)
                time_text = child_divs[1].get_text(strip=True)
                data_2d["update_time"] = time_text.replace("Last updated", "").strip()

        # ၂။ Live SET (SVG ပါသော div ထဲမှ)
        set_container = soup_2d.find("div", class_="d-flex justify-content-between")
        if set_container and set_container.find("svg"):
            set_val = set_container.find("span").get_text(strip=True).replace(',', '')
            data_2d["live_set"] = set_val

        # ၃။ Live Value (aria-colindex="5" ပါသော td ထဲမှ)
        val_td = soup_2d.find("td", {"aria-colindex": "5"})
        if val_td:
            val_text = val_td.get_text(strip=True).replace(',', '')
            data_2d["live_value"] = val_text

        # ၄။ 2D Result တွက်ချက်ခြင်း
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s, v = data_2d["live_set"], data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]
    except: pass

    # --- 3D Scraping (GLO) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # ၅။ Date (col-12 class ပါသော div ထဲမှ ဒုတိယမြောက် h2)
        date_div = soup_3d.find("div", class_="col-12 col-md-6 col-lg-8")
        if date_div:
            target_h2 = date_div.find("h2")
            if target_h2:
                last_draw["date"] = target_h2.get_text(strip=True).replace("Draw dated", "").strip()
            
        # ၆။ First Prize (col-12 d-flex flex-column... ထဲမှ)
        prize_container = soup_3d.find("div", class_="col-12 d-flex flex-column flex-md-row")
        if prize_container:
            award_p = prize_container.find("p", class_="award1-item-sub")
            if award_p:
                clean_prize = "".join(filter(str.isdigit, award_p.get_text(strip=True)))
                if len(clean_prize) >= 6:
                    last_draw["first_prize"] = clean_prize
                    last_draw["result"] = clean_prize[-3:]
    except: pass

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v19 (Tag-Specific Target) Started...")
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
def home(): return "Scraper v19 Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
