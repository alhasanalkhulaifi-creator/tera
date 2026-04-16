import os

import routeros_api

connection = routeros_api.RouterOsApiPool(
    host=os.environ["MIKROTIK_HOST"],
    username=os.getenv("MIKROTIK_USER", "admin"),
    password=os.environ["MIKROTIK_PASSWORD"],
    port=int(os.getenv("MIKROTIK_PORT", "8728")),
    plaintext_login=True
)

api = connection.get_api()

users = api.get_resource('/tool/user-manager/user').get()
sessions = api.get_resource('/tool/user-manager/session').get()
try:
    limits = api.get_resource('/tool/user-manager/limitation').get()
except Exception:
    limits = []

print("=== ANALYSIS ===")

for s in sessions[-10:]:  # آخر 10 جلسات فقط
    username = s.get('user')

    user_data = next((u for u in users if u.get('username') == username), None)

    print("\n--- USER SESSION ---")
    print("CARD:", username)
    print("IP:", s.get('user-ip'))
    print("MAC:", s.get('calling-station-id'))
    print("DOWNLOAD:", s.get('download'))
    print("UPLOAD:", s.get('upload'))
    print("UPTIME:", s.get('uptime'))
    print("ACTIVE:", s.get('active'))

    if user_data:
        print("USER PROFILE:", user_data.get('actual-profile'))
