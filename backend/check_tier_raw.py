import os
import sys
import json
import threading
from dotenv import load_dotenv
import urllib.request
import urllib.error

load_dotenv(".env")
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found.")
    sys.exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}
data = json.dumps({"contents": [{"parts": [{"text": "hello"}]}]}).encode('utf-8')

successes = 0
failures = 0
status_codes = []
lock = threading.Lock()

def make_request():
    global successes, failures, status_codes
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            with lock:
                successes += 1
                status_codes.append(response.status)
    except urllib.error.HTTPError as e:
        with lock:
            failures += 1
            status_codes.append(e.code)
    except Exception as e:
        with lock:
            failures += 1
            status_codes.append(0)

# Fire 25 concurrent requests
threads = [threading.Thread(target=make_request) for _ in range(25)]
for t in threads: t.start()
for t in threads: t.join()

print(f"Success: {successes}, Failures: {failures}")
print(f"Status codes seen: {set(status_codes)}")

if 429 in status_codes:
    print("\nRESULT: ❌ FREE TIER (Rate limited at 15 RPM)")
else:
    print("\nRESULT: ✅ PAID TIER")
