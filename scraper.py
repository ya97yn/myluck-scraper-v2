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

def get_2d_3d_data():
    current_mm_time = datetime.now(mm_tz).strftime("%d %b %Y %I:%M:%S %p")
    data_2d = {"update_time": f"Last Update {current_mm_time}", "market_status": "Market Status : Closed"}
    data_3d = {"draw_date": "-", "first_prize": "-", "result_3d": "-"}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # --- 2D Scraping ---
    try:
        res_2d = requests.get("https://www.set.or.th/en/market/product/stock/overview", headers=headers, timeout=15)
        soup_2d = BeautifulSoup(res_2d.text, 'html.parser')
        
        # Market Status & Update Time (Small Tags targeting)
        # စာသားပါဝင်မှုဖြင့် ပိုမိုတိကျစွာ ရှာဖွေခြင်း
        for s in soup_2d.find_all('small'):
            txt = s.get_text(strip=True)
            if "Last Update" in txt:
                data_2d["update_time"] = txt
            if "Market Status" in txt:
                data_2d["market_status"] = txt

        # SET Index Table (Col 2 & Col 8)
        row = soup_2d.find('tr', {'indexselected': '0'})
        if row:
            c2 = row.find('td', {'aria-colindex': '2'})
            c8 = row.find('td', {'aria-colindex': '8'})
            if c2 and c8:
                sv, vv = c2.get_text(strip=True).replace(',', ''), c8.get_text(strip=True).replace(',', '')
                data_2d.update({"live_set": sv, "live_value": vv})
                if sv and vv and any(c.isdigit() for c in sv):
                    data_2d["main_result"] = sv[-1] + vv.split('.')[0][-1]
    except Exception as e: print(f">>> 2D Error: {e}")

    # --- 3D Scraping (glo.or.th) ---
    try:
        res_3d = requests.get("https://www.glo.or.th/home-page", headers=headers, timeout=15)
        soup_3d = BeautifulSoup(res_3d.text, 'html.parser')
        
        # ပုံထဲကအတိုင်း h2 အောက်က draw date ကို ရှာခြင်း
        h2_tag = soup_3d.find('h2')
        if h2_tag:
            data_3d["draw_date"] = h2_tag.get_text(strip=True)
            
        # First Prize (6 လုံးဂဏန်း) ရှာခြင်း
        # ပုံထဲကအတိုင်း p class="award1-item-sub" ကို ရှာခြင်း
        p_award = soup_3d.find('p', class_='award1-item-sub')
        if p_award:
            full_num = p_award.get_text(strip=True)
            data_3d["first_prize"] = full_num
            # 3D ဆိုသည်မှာ ပထမဆု၏ နောက်ဆုံး ၃ လုံးဖြစ်သည်
            if len(full_num) >= 3:
                data_3d["result_3d"] = full_num[-3:]
    except Exception as e: print(f">>> 3D Error: {e}")

    return data_2d, data_3d

def scraper_loop():
    while True:
        d2, d3 = get_2d_3d_data()
        try:
            db.reference('live_2d').update(d2)
            db.reference('result_3d').update(d3) # သင်ပြထားသော result_3d structure
            print(f">>> Updated: {d2['update_time']}")
        except Exception as e: print(f">>> FB Error: {e}")
        time.sleep(15)

if initialize_firebase():
    threading.Thread(target=scraper_loop, daemon=True).start()

@app.route('/')
def home(): return "Scraper v4 (2D/3D) is Active", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
