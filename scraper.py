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

# Render Logs တွင် ချက်ချင်းမြင်ရစေရန်
os.environ['PYTHONUNBUFFERED'] = "1"
bkk_tz = pytz.timezone('Asia/Bangkok')

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
            elif os.path.exists("serviceAccountKey.json"):
                cred = credentials.Certificate("serviceAccountKey.json")
            else:
                print(">>> Firebase: No Credentials Found")
                return False
                
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
    """ SET API မှ 2D ဒေတာကို ထုတ်ယူခြင်း """
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.set.or.th/en/home'
        }
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            # 'SET' symbol ကို ရှာဖွေခြင်း
            set_info = next((item for item in data if item.get('symbol') == 'SET'), None)
            
            if set_info:
                last = set_info.get('last')
                value = set_info.get('value')
                
                # ဒေတာရှိလျှင် format ချသည်
                if last and value:
                    idx = "{:.2f}".format(float(last))
                    val = "{:.2f}".format(float(value))
                    res_2d = idx[-1] + val.split('.')[0][-1]
                    return {"live_set": idx, "live_value": val, "main_result": res_2d}
        print(f">>> SET API Debug: Status {res.status_code}")
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return {"live_set": "Waiting", "live_value": "Waiting", "main_result": "--"}

def get_3d_data():
    """ GLO API မှ 3D ဒေတာကို ထုတ်ယူခြင်း """
    try:
        url = "https://www.glo.or.th/api/lottery/getLatestLottery"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            result = data.get('response', {})
            p1 = result.get('prize1', {}).get('number')
            dt = result.get('date')
            
            if p1 and dt:
                return {
                    "date": str(dt).strip(),
                    "prize_first": str(p1).strip(),
                    "result": str(p1).strip()[-3:]
                }
    except Exception as e:
        print(f">>> GLO API Error: {e}")
    return {"date": "Searching", "prize_first": "Waiting", "result": "---"}

def main_worker():
    print(">>> Scraper Worker Active...")
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
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update({
                    "prize_first": data_3d['prize_first'],
                    "result": data_3d['result']
                })

            print(f">>> Syncing OK: 2D={data_2d['main_result']} | 3D={data_3d['result'] if data_3d else 'None'}")
            
        except Exception as e:
            print(f">>> Worker Loop Error: {e}")
        
        # ၁ မိနစ်တစ်ခါ စစ်ဆေးမည်
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
                    
