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
os.environ['PYTHONUNBUFFERED'] = "1" # Logs များ ချက်ချင်းတက်လာစေရန်
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
        "live_set": "-",
        "live_value": "-",
        "main_result": "--"
    }
    last_draw = {"date": "-", "first_prize": "-", "result": "-"}
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

    # --- 2D Scraping (SET Home) ---
    try:
        res_2d = requests.get("https://www.set.or.th/th/home", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # ၁။ Market Status (မြှားအစိမ်းရောင်နေရာ)
        status_tag = soup_2d.find("div", class_="text-black")
        if status_tag and status_tag.find("span"):
            data_2d["market_status"] = status_tag.find("span").get_text(strip=True)

        # ၂။ Update Time (မြှားအဝါရောင်နေရာ)
        time_div1 = soup_2d.find("div", class_="d-flex justify-content-between justify-content-md-start fs-12px raw-html")
        if time_div = time_div1.find(string=lambda text: "Last updated" in text if text else False)
            if time_div:
                data_2d["update_time"] = time_div.strip().replace("Last updated", "").strip()

        # ၃။ Live SET (SVG ပါဝင်သော Div ထဲမှ)
        set_container = soup_2d.find("div", class_="d-flex justify-content-between")
        if set_container and set_container.find("svg"):
            set_val = set_container.find("span").get_text(strip=True).replace(',', '')
            data_2d["live_set"] = set_val

        # ၄။ Live Value (aria-colindex="5" ပါသော TD ထဲမှ)
        val_td = soup_2d.find('tr', {'indexselected': '0'})
        if val_td:
            if val_tda = val_td.find('td', {'aria-colindex': '5'})
            val_text = val_tda.get_text(strip=True).replace(',', '')
            data_2d["live_value"] = val_text

        # ၅။ 2D Result တွက်ချက်ခြင်း
        if data_2d["live_set"] != "-" and data_2d["live_value"] != "-":
            s = data_2d["live_set"]
            v = data_2d["live_value"]
            data_2d["main_result"] = s[-1] + v.split('.')[0][-1]

    except Exception as e:
        print(f">>> 2D Error: {e}")

    # --- 3D Scraping (GLO) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # Date: "Draw dated March 1, 2026" မှ "March 1, 2026" ကိုသာယူခြင်း
        h2_div = soup_3d.find("div", class_="col-12 col-md-6 col-lg-8")
            h2_date = soup_3d.find('h2')
            if h2_date:
                date_text = h2_date.get_text(strip=True).replace("Draw dated", "").strip()
                last_draw["date"] = date_text
            
        # First Prize & 3D Result
        award_p = soup_3d.select_one(".award1-item p.award1-item-sub")
        if award_p:
            clean_prize = "".join(filter(str.isdigit, award_p.get_text(strip=True)))
            if len(clean_prize) >= 6:
                last_draw["first_prize"] = clean_prize
                last_draw["result"] = clean_prize[-3:]
    except Exception as e:
        print(f">>> 3D Error: {e}")

    return data_2d, last_draw

def scraper_loop():
    print(">>> Scraper v18 (Exact Structure Fix) Started...")
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
def home(): return "Scraper v18 Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
