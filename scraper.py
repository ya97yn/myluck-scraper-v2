import os
import json
import time
import requests
import threading
import re
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
    current_mm_time = datetime.now(mm_tz).strftime("%d %b %Y %I:%M:%S %p")
    data_2d = {
        "update_time": f"Last Update {current_mm_time}", 
        "market_status": "Market Status : Closed",
        "live_set": "Waiting",
        "live_value": "Waiting"
    }
    data_3d = {"draw_date": "-", "first_prize": "-", "result_3d": "-"}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.set.or.th/'
    }

    # --- 2D Scraping (SET Index) ---
    try:
        res_2d = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # Market Status နှင့် Update Time ကို Regex ဖြင့် ရှာဖွေခြင်း (BS4 နဲ့ ရှာမရလျှင် ပိုစိတ်ချရသည်)
        page_text = res_2d.text
        m_status = re.search(r'Market Status\s*:\s*\w+', page_text)
        if m_status:
            data_2d["market_status"] = m_status.group(0)
            
        m_update = re.search(r'Last Update\s*[\d\w\s,:]+', page_text)
        if m_update:
            data_2d["update_time"] = m_update.group(0)

        # SET Row Targeting (Col 2 & Col 8)
        set_row = soup_2d.find('tr', {'indexselected': '0'})
        if set_row:
            col_2 = set_row.find('td', {'aria-colindex': '2'})
            col_8 = set_row.find('td', {'aria-colindex': '8'})
            if col_2 and col_8:
                sv = col_2.get_text(strip=True).replace(',', '')
                vv = col_8.get_text(strip=True).replace(',', '')
                data_2d.update({"live_set": sv, "live_value": vv})
                if sv and vv and any(c.isdigit() for c in sv):
                    data_2d["main_result"] = sv[-1] + vv.split('.')[0][-1]
    except Exception as e:
        print(f">>> 2D Error: {e}")

    # --- 3D Scraping (GLO Home Page) ---
    try:
        # GLO Website သည် တိုက်ရိုက် scraping ခွင့်မပြုလျှင် Proxy သို့မဟုတ် Headers အပြည့်အစုံ လိုအပ်နိုင်ပါသည်
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # ၁။ Draw Date ရှာဖွေခြင်း (ပုံထဲကအတိုင်း h2 ကို ယူသည်)
        h2_date = soup_3d.find('h2')
        if h2_date:
            data_3d["draw_date"] = h2_date.get_text(strip=True)
            
        # ၂။ First Prize ရှာဖွေခြင်း (p class="award1-item-sub")
        p_prize = soup_3d.find('p', class_='award1-item-sub')
        if p_prize:
            fp_text = p_prize.get_text(strip=True)
            # ဂဏန်း ၆ လုံးကိုသာ သန့်စင်ယူခြင်း
            fp_digits = re.sub(r'\D', '', fp_text)
            if len(fp_digits) >= 6:
                data_3d["first_prize"] = fp_digits[:6]
                data_3d["result_3d"] = fp_digits[-3:] # နောက်ဆုံး ၃ လုံး
    except Exception as e:
        print(f">>> 3D Error: {e}")

    return data_2d, data_3d

def scraper_loop():
    print(">>> Final Scraper (v5) Started! Syncing 2D/3D...")
    while True:
        d2, d3 = get_live_data()
        try:
            db.reference('live_2d').update(d2)
            db.reference('result_3d').update(d3)
            print(f">>> Sync OK: {d2['update_time']} | 3D: {d3['result_3d']}")
        except Exception as e:
            print(f">>> Firebase Update Error: {e}")
        time.sleep(20) # Server load သက်သာစေရန် စက္ကန့် ၂၀ ထားပါသည်

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home():
    return "SET & GLO Scraper is Running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
