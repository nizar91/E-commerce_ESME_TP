import json
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")


def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return {}
    with open(ORDERS_FILE, "r", encoding="utf-8") as fp:
        return json.load(fp)


def save_orders(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=4)


def require_user():
    username = request.headers.get("X-User")
    if not username:
        return None, (jsonify({"error": "X-User header required"}), 401)
    return username, None


@app.route("/orders", methods=["GET"])
def list_orders():
    username, error = require_user()
    if error:
        return error

    orders = load_orders().get(username, [])
    return jsonify({"orders": orders})


@app.route("/orders", methods=["POST"])
def create_order():
    username, error = require_user()
    if error:
        return error

    payload = request.get_json() or {}
    item = payload.get("item")
    quantity = payload.get("quantity", 1)

    if not item:
        return jsonify({"error": "item is required"}), 400

    orders = load_orders()
    user_orders = orders.setdefault(username, [])
    order_id = len(user_orders) + 1
    new_order = {"id": order_id, "item": item, "quantity": quantity}
    user_orders.append(new_order)
    save_orders(orders)

    return jsonify(new_order), 201


if __name__ == "__main__":
    app.run(port=5003, debug=True)
