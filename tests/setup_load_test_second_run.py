import os
import requests
import time

BASE = 'http://127.0.0.1:8000'
HEADERS = {'Content-Type': 'application/json', 'Authorization': f'Bearer {os.environ["TEST_API_KEY"]}'}

# import 1000 new cards with different prefix
codes = [f'loadtest2-{i:06d}' for i in range(1, 1001)]
print('Importing 1000 cards (loadtest2)...')
r = requests.post(f'{BASE}/cards/import', json={'codes': codes, 'category': 'test', 'price': 1}, headers=HEADERS, timeout=60)
print('status', r.status_code, r.text)

# deposit to 100 users
print('Depositing to 100 users (second run)...')
for i in range(1, 101):
    phone = f'loadtest-user-{i}'
    ref = f'second-{phone}-{int(time.time())}'
    r2 = requests.post(f'{BASE}/wallet/deposit', json={'phone': phone, 'amount': 100000, 'reference_id': ref}, headers=HEADERS, timeout=30)
    if r2.status_code != 200:
        print('deposit failed', phone, r2.status_code, r2.text)
    if i % 10 == 0:
        print('deposited', i)
    time.sleep(0.01)
print('done')
