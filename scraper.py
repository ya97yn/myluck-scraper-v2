import os
import json
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask

app = Flask(__name__)

def test_connection():
    try:
        sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if sa_json:
            cred = credentials.Certificate(json.loads(sa_json))
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://myluck2d3dresult-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
            # Firebase ထဲကို စမ်းသပ်စာသား ပို့ကြည့်ခြင်း
            db.reference('debug').set({"status": "Connected", "time": str(os.urandom(4).hex())})
            print(">>> Connection Test: Success!")
            return True
    except Exception as e:
        print(f">>> Connection Test Failed: {e}")
    return False

@app.route('/')
def home():
    status = "Connected" if firebase_admin._apps else "Disconnected"
    return f"Service is Live. Firebase Status: {status}", 200

if __name__ == "__main__":
    test_connection()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
