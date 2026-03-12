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

def get_data_from_html():
    current_mm_time = datetime.now(mm_tz).strftime("%I:%M:%S %p")
    results = {"update_time": current_mm_time}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # --- 2D Scraping (SET Index Table) ---
    try:
        set_url = "https://www.set.or.th/en/market/product/stock/overview"
        res = requests.get(set_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Table 0 ထဲက SET row ကို ရှာခြင်း
        table = soup.find('table')
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if cols and 'SET' in cols[0].text:
                last_val = cols[1].text.strip().replace(',', '') # 1,429.80
                m_baht = cols[7].text.strip().replace(',', '')  # 64,496.48
                
                results['live_set'] = last_val
                results['live_value'] = m_baht
                # 2D Result တွက်ချက်ခြင်း
                res_2d = last_val[-1] + m_baht.split('.')[0][-1]
                results['main_result'] = res_2d
                break
    except Exception as e:
        print(f">>> 2D HTML Error: {e}")

    # --- 3D Scraping (Lotto) ---
    try:
        # 3D အတွက် Thai Lotto website တစ်ခုခုမှ ယူခြင်း (ဥပမာပေးထားခြင်းဖြစ်ပါသည်)
        lotto_url = "https://www.glo.or.th/home-page" 
        # မှတ်ချက် - 3D က တစ်လ ၂ ကြိမ်သာ ထွက်သဖြင့် ပုံသေ ဒေတာ သို့မဟုတ် အခြား Source သုံးရန် လိုအပ်နိုင်ပါသည်
        results['live_3d'] = "---" # 3D result logic 
    except Exception as e:
        print(f">>> 3D HTML Error: {e}")

    return results

def scraper_loop():
    print(">>> HTML Scraper Started (Myanmar Time)")
    while True:
        data = get_data_from_html()
        try:
            # Firebase ရဲ့ live_2d node အောက်ကို update လုပ်ခြင်း
            db.reference('live_2d').update(data)
            print(f">>> Firebase HTML Sync: {data['update_time']}")
        except Exception as e:
            print(f">>> Firebase Update Error: {e}")
        time.sleep(15)

if initialize_firebase():
    thread = threading.Thread(target=scraper_loop, daemon=True)
    thread.start()

@app.route('/')
def home():
    return f"HTML Scraper is Active. Time: {datetime.now(mm_tz).strftime('%I:%M:%S %p')}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
