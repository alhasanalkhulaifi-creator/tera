import os
import requests
import time

BASE = 'http://127.0.0.1:8000'
HEADERS = {'Content-Type': 'application/json', 'Authorization': f'Bearer {os.environ["TEST_API_KEY"]}'}

print('Depositing to 100 users...')
for i in range(1, 101):
    phone = f'loadtest-user-{i}'
    ref = f'init-deposit-{phone}-{int(time.time())}'
    r = requests.post(f'{BASE}/wallet/deposit', json={'phone': phone, 'amount': 100000, 'reference_id': ref}, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        print('deposit failed', phone, r.status_code, r.text)
    else:
        if i % 10 == 0:
            print('deposited', i)
    time.sleep(0.01)
print('done')
