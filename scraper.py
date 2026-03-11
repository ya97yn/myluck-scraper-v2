import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import sys
import json
import os

JSON_FILE = "myluck2d3dresult-default-rtdb-export.json"

def fetch_set_data(url):
    """Fetch and parse SET data, return (last, value) or (None, None)"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().isoformat()}] Network error: {e}")
        return None, None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = None
        for tbl in soup.find_all('table'):
            if any('index' in th.get_text(strip=True).lower() for th in tbl.find_all('th')):
                table = tbl
                break
        if not table:
            print(f"[{datetime.now().isoformat()}] Table not found")
            return None, None

        first_row = table.find('tbody').find('tr') if table.find('tbody') else table.find('tr')
        cells = first_row.find_all('td')
        if len(cells) < 8:
            return None, None

        last = cells[1].get_text(strip=True).replace(',', '')
        value = cells[7].get_text(strip=True).replace(',', '')
        return last, value
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Parsing error: {e}")
        return None, None

def update_json_file(last, value):
    """Update live_set and live_value in the JSON file"""
    if last is None or value is None:
        return False

    try:
        # Read existing JSON
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Update the required fields
        if 'live_2d' in data:
            data['live_2d']['live_set'] = last
            data['live_2d']['live_value'] = value
        else:
            print(f"[{datetime.now().isoformat()}] 'live_2d' key not found in JSON")
            return False

        # Write back with pretty formatting (preserve original style)
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[{datetime.now().isoformat()}] JSON updated: live_set={last}, live_value={value}")
        return True
    except FileNotFoundError:
        print(f"[{datetime.now().isoformat()}] JSON file not found: {JSON_FILE}")
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().isoformat()}] Invalid JSON: {e}")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] File write error: {e}")
    return False

def main():
    url = "https://www.set.or.th/en/market/product/stock/overview"
    print(f"Starting SET scraper with JSON update. File: {JSON_FILE}\nPress Ctrl+C to stop.\n")

    while True:
        last, value = fetch_set_data(url)
        if last and value:
            update_json_file(last, value)
        else:
            print(f"[{datetime.now().isoformat()}] Failed to retrieve data, skipping update.")

        time.sleep(15)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScraper stopped by user.")
        sys.exit(0)
