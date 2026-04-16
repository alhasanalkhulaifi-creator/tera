import os

from flask import Flask, request, jsonify
import routeros_api

app = Flask(__name__)

def connect():
    return routeros_api.RouterOsApiPool(
        host=os.environ["MIKROTIK_HOST"],
        username=os.getenv("MIKROTIK_USER", "admin"),
        password=os.environ["MIKROTIK_PASSWORD"],
        port=int(os.getenv("MIKROTIK_PORT", "8728")),
        plaintext_login=True
    ).get_api()

@app.route("/users", methods=["GET"])
def get_users():
    api = connect()
    users = api.get_resource('/ip/hotspot/user')
    return jsonify(users.get())

@app.route("/disable", methods=["POST"])
def disable_user():
    data = request.json
    api = connect()
    users = api.get_resource('/ip/hotspot/user')
    users.set(id=data["id"], disabled="true")
    return {"status": "disabled"}

app.run(host="0.0.0.0", port=5000)
