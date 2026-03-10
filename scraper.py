import os
import json
import time
import requests
import threading
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, db
import http.server
import socketserver

# Render Logs မှာ ချက်ချင်းမြင်ရစေရန်
os.environ['PYTHONUNBUFFERED'] = "1"
bkk_tz = pytz.timezone('Asia/Bangkok')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
            else:
                cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
            })
            print(">>> Firebase: Connected Successfully")
            return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
            return False
    return True

def get_2d_data():
    """ SET API (List Index) မှ 2D ဒေတာကို ထုတ်ယူခြင်း """
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.set.or.th/en/home'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # SET Index ကို ရှာဖွေခြင်း (ပုံမှန်အားဖြင့် index 0 တွင် ရှိတတ်သည်)
            set_index_info = next((item for item in data if item.get('symbol') == 'SET'), None)
            
            if set_index_info:
                idx = "{:.2f}".format(set_index_info.get('last', 0))
                val = "{:.2f}".format(set_index_info.get('value', 0))
                # 2D တွက်နည်း (SET နောက်ဆုံးဂဏန်း + Value အစက်ရှေ့ နောက်ဆုံးဂဏန်း)
                res_2d = idx[-1] + val.split('.')[0][-1]
                return {"live_set": idx, "live_value": val, "main_result": res_2d}
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return {"live_set": "Waiting", "live_value": "Waiting", "main_result": "--"}

def def get_3d_data():
    try:
        # GLO API ကို တိုက်ရိုက်ခေါ်ယူခြင်း
        url = "https://www.glo.or.th/api/lottery/getLatestLottery"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            res_obj = data.get('response', {})
            p1 = res_obj.get('prize1', {}).get('number', "000000")
            
            # API မှရလာသော ရက်စွဲကိုယူသည်
            dt = res_obj.get('date', datetime.now(bkk_tz).strftime("%Y-%m-%d"))
            
            # Firebase မှာ သိမ်းမည့် Object
            return {"date": dt, "prize_first": p1, "result": p1[-3:]}
    except Exception as e:
        print(f">>> GLO API Error: {e}")
    return None
def main_worker():
    print(">>> API Scraper Worker Started...")
    while True:
        try:
            now = datetime.now(bkk_tz)
            
            # 1. 2D Update
            data_2d = get_2d_data()
            db.reference('live_2d').update(data_2d)
            db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})
            
            # 2. 3D Update
            data_3d = get_3d_data()
            if data_3d:
                # ရက်စွဲကို Firebase key အဖြစ် သုံးရန် (Space ကို Underscore ပြောင်းသည်)
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update({
                    "prize_first": data_3d['prize_first'],
                    "result": data_3d['result']
                })
                
                # နေ့လည် ၄:၃၀ အပိတ်ဂဏန်း သိမ်းဆည်းရန် (2D အတွက်)
                if now.hour == 16 and now.minute >= 30:
                    db.reference('live_2d/evening/4:30PM').update({
                        "set": data_2d['live_set'],
                        "value": data_2d['live_value'],
                        "result": data_2d['main_result']
                    })

            print(f">>> Syncing OK: {now.strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f">>> Worker Loop Error: {e}")
        
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"MyLuck2D3D API Scraper is Online")

if __name__ == "__main__":
    if initialize_firebase():
        port = int(os.environ.get("PORT", 10000))
        server = socketserver.TCPServer(("", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        main_worker()
