import os
import requests
import json
import time

BASE = 'http://127.0.0.1:8000'
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {os.environ["TEST_API_KEY"]}',
}

# Enough inventory for high concurrency / 30s load (idempotent on re-run via ON CONFLICT)
BATCH = 5000
all_codes = [f'loadtest-{i:08d}' for i in range(1, 50001)]
print(f'Importing {len(all_codes)} cards in batches of {BATCH}...')
inserted_total = 0
for start in range(0, len(all_codes), BATCH):
    chunk = all_codes[start : start + BATCH]
    r = requests.post(
        f'{BASE}/cards/import',
        json={'codes': chunk, 'category': 'test', 'price': 1},
        headers=HEADERS,
        timeout=120,
    )
    print('batch', start // BATCH + 1, 'status', r.status_code, r.text[:200] if r.text else '')
    if r.status_code == 200:
        inserted_total += r.json().get('inserted', 0)
print('inserted (this run, new rows):', inserted_total)

# create/deposit user with large balance
phone = 'loadtest-user'
ref = f'init-deposit-{int(time.time())}'
print('Depositing balance to', phone)
r2 = requests.post(f'{BASE}/wallet/deposit', json={'phone': phone, 'amount': 100000, 'reference_id': ref}, headers=HEADERS, timeout=30)
print('status', r2.status_code, r2.text)

# discover user_id for the load test (API now requires user_id)
r3 = requests.get(f'{BASE}/wallet/{phone}', headers=HEADERS, timeout=30)
if r3.status_code == 200:
    user_id = r3.json().get('transactions', [{}])[0].get('user_id')
    if not user_id:
        # fallback: wallet/{phone} includes no direct user_id, so extract from any tx entry if present
        user_id = r3.json().get('user_id')
    print('loadtest user_id:', user_id)
    print('Run: USER_ID=%s USER_PHONE=%s k6 run tests/load_test.js' % (user_id, phone))
else:
    print('Failed to fetch wallet info for user_id:', r3.status_code, r3.text[:200] if r3.text else '')
