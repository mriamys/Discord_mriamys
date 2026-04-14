import requests
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("TORRSERVER_USER")
password = os.getenv("TORRSERVER_PASS")
url = "http://127.0.0.1:8090/torrents"

auth = None
if user and password:
    auth = (user, password)

print(f"Testing connection to {url}...")
try:
    # Попробуем просто получить список торрентов
    data = {"action": "list"}
    resp = requests.post(url, json=data, auth=auth, timeout=5)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"FAILED: {e}")
