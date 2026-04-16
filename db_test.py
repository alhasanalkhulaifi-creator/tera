import os

import psycopg2
import routeros_api

# اتصال MikroTik
connection = routeros_api.RouterOsApiPool(
    host=os.environ["MIKROTIK_HOST"],
    username=os.getenv("MIKROTIK_USER", "admin"),
    password=os.environ["MIKROTIK_PASSWORD"],
    port=int(os.getenv("MIKROTIK_PORT", "8728")),
    plaintext_login=True
)
api = connection.get_api()

sessions = api.get_resource('/tool/user-manager/session').get()

# اتصال قاعدة البيانات
conn = psycopg2.connect(os.environ["DATABASE_URL"])

cur = conn.cursor()

# إنشاء جدول بسيط
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    card VARCHAR(50),
    ip VARCHAR(50),
    mac VARCHAR(50),
    download BIGINT,
    upload BIGINT,
    uptime VARCHAR(50),
    active BOOLEAN
)
""")

# إدخال البيانات
for s in sessions[-20:]:
    download = s.get('download') or '0'
    upload = s.get('upload') or '0'
    try:
        d = int(download)
    except Exception:
        d = 0
    try:
        u = int(upload)
    except Exception:
        u = 0
    active = True if s.get('active') in ['true', True] else False

    cur.execute("""
    INSERT INTO sessions (card, ip, mac, download, upload, uptime, active)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        s.get('user'),
        s.get('user-ip'),
        s.get('calling-station-id'),
        d,
        u,
        s.get('uptime'),
        active
    ))

conn.commit()
cur.close()
conn.close()

print("DONE")
