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

resource = api.get_resource('/ip/hotspot/user')
print(resource.get())
