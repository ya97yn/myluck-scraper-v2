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
            print(">>> Firebase: Connected Successfully")
            return True
        except Exception as e:
            print(f">>> Firebase: Init Error {e}")
            return False
    return True

def get_2d_set():
    try:
        url = "https://www.set.or.th/api/set/market/index/SET/overview"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
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
        print(f">>> SET Error: {e}")
    return {"live_set": "Waiting", "live_value": "Waiting", "main_result": "--"}

def get_3d_glo():
    try:
        url = "https://thai-lotto.net"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        # Selector အသစ်များဖြင့် ကြိုးစားရှာဖွေခြင်း
        p1_tag = soup.find(class_="prize1-number") or soup.select_one('#prize1')
        p1 = p1_tag.text.strip().replace(',', '') if p1_tag else "000000"
        dt_tag = soup.find(class_="draw-date") or soup.select_one('.date')
        dt = dt_tag.text.strip() if dt_tag else "No Date"
        return {"date": dt, "prize_first": p1, "result": p1[-3:]}
    except Exception as e:
        print(f">>> GLO Error: {e}")
    return {"date": "Searching", "prize_first": "Waiting", "result": "---"}

def main_worker():
    print(">>> Worker Started: Forcing first sync...")
    while True:
        try:
            now = datetime.now(bkk_tz)
            
            # 2D Update
            data_2d = get_2d_set()
            db.reference('live_2d').update(data_2d)
            db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})
            
            # 3D Update
            data_3d = get_3d_glo()
            if data_3d:
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update({
                    "prize_first": data_3d['prize_first'],
                    "result": data_3d['result']
                })

            print(f">>> Syncing: 2D={data_2d['main_result']}, 3D={data_3d['result']}")
            
        except Exception as e:
            print(f">>> Main Loop Error: {e}")
        
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Scraper is Active")

if __name__ == "__main__":
    if initialize_firebase():
        port = int(os.environ.get("PORT", 10000))
        server = socketserver.TCPServer(("", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        main_worker()
