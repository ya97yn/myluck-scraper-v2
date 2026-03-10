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
            print(">>> Firebase: Connected")
            return True
        except Exception as e:
            print(f">>> Firebase Init Error: {e}")
            return False
    return True

def is_market_holiday():
    """ SET Holiday API မှ ယနေ့သည် ပိတ်ရက်ဟုတ်မဟုတ် စစ်ဆေးခြင်း """
    try:
        url = "https://www.set.or.th/api/cms/v1/holidays/holiday-remark"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            today_str = datetime.now(bkk_tz).strftime("%Y-%m-%d")
            # API မှလာသော holiday list ထဲတွင် ယနေ့ရက်စွဲ ပါမပါ စစ်မည်
            holidays = data.get('result', {}).get('holidays', [])
            for h in holidays:
                if h.get('holidayDate') == today_str:
                    return True, h.get('holidayNameEn', 'Public Holiday')
    except Exception as e:
        print(f">>> Holiday API Error: {e}")
    return False, ""

def get_2d_data():
    try:
        url = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.set.or.th/en/home'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            set_info = next((item for item in data if item.get('symbol') == 'SET'), None)
            if set_info:
                idx = "{:.2f}".format(set_info.get('last', 0))
                val = "{:.2f}".format(set_info.get('value', 0))
                res_2d = idx[-1] + val.split('.')[0][-1]
                return {"live_set": idx, "live_value": val, "main_result": res_2d}
    except Exception as e:
        print(f">>> SET API Error: {e}")
    return None

def get_3d_data():
    try:
        url = "https://www.glo.or.th/api/lottery/getLatestLottery"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            res_obj = data.get('response', {})
            p1 = res_obj.get('prize1', {}).get('number', "000000")
            dt = res_obj.get('date', datetime.now(bkk_tz).strftime("%Y-%m-%d"))
            return {"date": dt, "prize_first": p1, "result": p1[-3:]}
    except Exception as e:
        print(f">>> GLO API Error: {e}")
    return None

def main_worker():
    while True:
        try:
            now = datetime.now(bkk_tz)
            
            # ၁။ Holiday စစ်ဆေးခြင်း
            holiday_status, holiday_name = is_market_holiday()
            market_status = "Closed" if holiday_status or now.weekday() >= 5 else "Open"
            
            # ၂။ 2D Update
            data_2d = get_2d_data()
            if data_2d:
                data_2d["market_status"] = market_status
                if holiday_status:
                    data_2d["remark"] = f"Holiday: {holiday_name}"
                db.reference('live_2d').update(data_2d)
                db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})

            # ၃။ 3D Update
            data_3d = get_3d_data()
            if data_3d:
                clean_date = data_3d['date'].replace(" ", "_")
                db.reference(f"result_3d/{clean_date}").update(data_3d)

            print(f">>> Syncing: Market={market_status} | Time={now.strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f">>> Loop Error: {e}")
        
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Holiday-Aware Scraper Active")

if __name__ == "__main__":
    if initialize_firebase():
        port = int(os.environ.get("PORT", 10000))
        server = socketserver.TCPServer(("", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        main_worker()
