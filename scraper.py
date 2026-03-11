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
            print(">>> Firebase: Connected Successfully")
            return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
            return False
    return True

def get_2d_data():
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.set.or.th/en/home'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            sectors = data.get('indexIndustrySectors', [])
            set_info = next((item for item in sectors if item.get('symbol') == 'SET'), None)
            
            if set_info:
                last_raw = set_info.get('last', 0)
                value_raw = set_info.get('value', 0)
                # marketDateTime (ဥပမာ- "2026-03-12T00:50:52...") ကို ယူခြင်း
                raw_time = set_info.get('marketDateTime', "")
                
                # အချိန်ကို Format ချခြင်း (T နှင့် အစက်ကြားရှိ အချိန်အပိုင်းအစကို ယူသည်)
                try:
                    formatted_time = raw_time.split('T')[1].split('.')[0] # 00:50:52
                except:
                    formatted_time = datetime.now(bkk_tz).strftime("%H:%M:%S")

                idx = "{:.2f}".format(float(last_raw))
                val_million = float(value_raw) / 1000000
                val_str = "{:.2f}".format(val_million) 
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown'),
                    "update_time": formatted_time # API မှ အချိန်ကို တိုက်ရိုက်သုံးခြင်း
                }
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return None

def main_worker():
    while True:
        try:
            data_2d = get_2d_data()
            if data_2d:
                # သင်၏ Database structure အတိုင်း update လုပ်ခြင်း
                db.reference('live_2d').update(data_2d)
                print(f">>> Syncing OK: {data_2d['update_time']} | 2D={data_2d['main_result']}")
            else:
                print(">>> Waiting for API Data...")
        except Exception as e:
            print(f">>> Loop Error: {e}")
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Scraper Active")

if __name__ == "__main__":
    if initialize_firebase():
        port = int(os.environ.get("PORT", 10000))
        server = socketserver.TCPServer(("", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        main_worker()
