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

# Render Logs အတွက် setup
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
    """ SET API မှ indexIndustrySectors ကို ရှာဖွေပြီး Million format ဖြင့် ထုတ်ယူခြင်း """
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.set.or.th/en/home'
        }
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            # indexIndustrySectors list ထဲတွင် 'SET' ကို ရှာပါသည်
            sectors = data.get('indexIndustrySectors', [])
            set_info = next((item for item in sectors if item.get('symbol') == 'SET'), None)
            
            if set_info:
                last_raw = set_info.get('last', 0)
                value_raw = set_info.get('value', 0)
                
                # ၁။ SET Index (live_set) ကို သိမ်းဆည်းခြင်း
                idx = "{:.2f}".format(float(last_raw))
                
                # ၂။ Value ကို Million (သန်း) သို့ ပြောင်းလဲခြင်း (66700424367 -> 66700.42)
                val_million = float(value_raw) / 1000000
                val_str = "{:.2f}".format(val_million) 
                
                # ၃။ 2D Result တွက်ချက်ခြင်း (SET နောက်ဆုံးဂဏန်း + Value အစက်ရှေ့ နောက်ဆုံးဂဏန်း)
                res_2d = idx[-1] + val_str.split('.')[0][-1]
                
                return {
                    "live_set": idx,
                    "live_value": val_str,
                    "main_result": res_2d,
                    "market_status": set_info.get('marketStatus', 'Unknown')
                }
    except Exception as e:
        print(f">>> SET API Error: {e}")
    
    return {"live_set": "Waiting", "live_value": "Waiting", "main_result": "--", "market_status": "Closed"}

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
                return {"date": str(dt).strip(), "prize_first": str(p1), "result": str(p1)[-3:]}
    except: pass
    return None

def main_worker():
    print(">>> Worker Started: Syncing Real-time Data...")
    while True:
        try:
            now = datetime.now(bkk_tz)
            
            # 2D Sync
            data_2d = get_2d_data()
            db.reference('live_2d').update(data_2d)
            db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})
            
            # 3D Sync
            data_3d = get_3d_data()
            if data_3d:
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update({
                    "prize_first": data_3d['prize_first'],
                    "result": data_3d['result']
                })

            print(f">>> Syncing OK: 2D={data_2d['main_result']} | Time={now.strftime('%H:%M:%S')}")
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
