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
            print(">>> Firebase: Connected via API Access")
            return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
            return False
    return True

def get_2d_via_api():
    """ SET Official API ကို တိုက်ရိုက်ခေါ်ယူခြင်း """
    try:
        # ဤ URL သည် SET Website က ဒေတာပြရန် သုံးသော Backend API ဖြစ်သည်
        url = "https://www.set.or.th/api/set/index/set/market-stat"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.set.or.th/en/home'
        }
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            d = res.json()
            idx = "{:.2f}".format(d.get('last', 0))
            val = "{:.2f}".format(d.get('value', 0))
            res_2d = idx[-1] + val.split('.')[0][-1]
            return {"live_set": idx, "live_value": val, "main_result": res_2d}
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return {"live_set": "Market Closed", "live_value": "Market Closed", "main_result": "--"}

def get_3d_via_api():
    """ GLO Official API ကို တိုက်ရိုက်ခေါ်ယူခြင်း """
    try:
        # GLO ၏ နောက်ဆုံးထွက် ထီဒေတာများကို ပေးသော API Endpoint
        url = "https://www.glo.or.th/api/lottery/get_last_lottery"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # API response structure ပေါ်မူတည်၍ ဒေတာထုတ်ယူခြင်း
            # မှတ်ချက် - GLO API သည် များသောအားဖြင့် JSON object ပြန်ပေးသည်
            result_data = data.get('response', {})
            p1 = result_data.get('prize1', "000000")
            dt = result_data.get('display_date', datetime.now(bkk_tz).strftime("%Y-%m-%d"))
            
            return {"date": dt, "prize_first": p1, "result": p1[-3:]}
    except Exception as e:
        print(f">>> GLO API Error: {e}")
    return {"date": "Searching", "prize_first": "Waiting", "result": "---"}

def main_worker():
    print(">>> API Worker Active. Fetching Real-time Data...")
    while True:
        try:
            now = datetime.now(bkk_tz)
            
            # 2D API Sync
            data_2d = get_2d_via_api()
            db.reference('live_2d').update(data_2d)
            db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})
            
            # 3D API Sync
            data_3d = get_3d_via_api()
            if data_3d:
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update({
                    "prize_first": data_3d['prize_first'],
                    "result": data_3d['result']
                })

            print(f">>> API Sync Success: 2D={data_2d['main_result']}, 3D={data_3d['result']}")
            
        except Exception as e:
            print(f">>> Main Loop Error: {e}")
        
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"API Scraper Active")

if __name__ == "__main__":
    if initialize_firebase():
        port = int(os.environ.get("PORT", 10000))
        server = socketserver.TCPServer(("", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        main_worker()
