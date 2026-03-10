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
            print(">>> Firebase: Connected")
            return True
        except Exception as e:
            print(f">>> Firebase: Error {e}")
            return False
    return True

def get_2d_set():
    try:
        url = "https://www.set.or.th/api/set/index/set/market-stat"
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.set.or.th/en/home'}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            d = res.json()
            idx, val = "{:.2f}".format(d.get('last', 0)), "{:.2f}".format(d.get('value', 0))
            return {"live_set": idx, "live_value": val, "main_result": idx[-1] + val.split('.')[0][-1]}
    except: return None

def get_3d_glo():
    try:
        url = "https://www.glo.or.th/home-page"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        p1 = soup.select_one('.prize1-number, #prize1').text.strip().replace(',', '')
        dt = soup.select_one('.draw-date, .date').text.strip()
        return {"date": dt, "prize_first": p1, "result": p1[-3:]}
    except: return None

def main_worker():
    while True:
        now = datetime.now(bkk_tz)
        # 2D Update
        data_2d = get_2d_set()
        if data_2d:
            db.reference('live_2d').update(data_2d)
            if now.hour == 16 and now.minute >= 30:
                db.reference('live_2d/evening/4:30PM').update({"set": data_2d['live_set'], "value": data_2d['live_value'], "result": data_2d['main_result']})
        # 3D Update
        data_3d = get_3d_glo()
        if data_3d:
            db.reference(f"result_3d/{data_3d['date'].replace(' ', '_')}").update({"prize_first": data_3d['prize_first'], "result": data_3d['result']})
        
        db.reference('live_2d').update({"update_time": now.strftime("%I:%M:%S %p")})
        print(f"Sync: {now.strftime('%H:%M:%S')}")
        time.sleep(60)

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Scraper Active")

if __name__ == "__main__":
    if initialize_firebase():
        threading.Thread(target=lambda: socketserver.TCPServer(("", int(os.environ.get("PORT", 10000))), HealthHandler).serve_forever(), daemon=True).start()
        main_worker()
