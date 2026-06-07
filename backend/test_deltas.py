import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/v1/fno/chain/NIFTY') as url:
        d = json.loads(url.read().decode())
        print(f"SPOT: {d.get('spot_price')}")
        print(f"ATM: {d.get('atm_strike')}")
        for q in d['quotes']:
            if q['type'] == 'CE' and q['ltp'] > 0:
                print(f"{q['strike']} CE -> Delta: {q.get('delta')}")
except Exception as e:
    print(e)
