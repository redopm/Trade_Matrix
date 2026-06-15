import requests
import json
url = "http://35.200.254.44/api/v1/fno/predict"
data = {"symbol": "NSE:NIFTY24MAY23000CE", "pred_len": 5, "range_from": "2024-01-01"}
res = requests.post(url, json=data)
print(res.status_code)
print(res.json())
