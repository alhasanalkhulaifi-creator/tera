import os

import routeros_api
from typing import Tuple, List, Dict


def fetch_usermanager_data() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    pool = routeros_api.RouterOsApiPool(
        host=os.environ["MIKROTIK_HOST"],
        username=os.getenv("MIKROTIK_USER", "admin"),
        password=os.environ["MIKROTIK_PASSWORD"],
        port=int(os.getenv("MIKROTIK_PORT", "8728")),
        plaintext_login=True
    )
    try:
        api = pool.get_api()
        users = api.get_resource('/tool/user-manager/user').get()
        sessions = api.get_resource('/tool/user-manager/session').get()
        try:
            limits = api.get_resource('/tool/user-manager/limitation').get()
        except Exception:
            limits = []
    finally:
        try:
            pool.disconnect()
        except Exception:
            pass
    return users, sessions, limits
