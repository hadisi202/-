from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_PATH = 'packing_system.db'


def query_one(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@app.after_request
def add_cors_headers(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return resp


@app.get('/')
def index():
    return jsonify({"status": "ok", "service": "packing-system-api"})


@app.get('/api/search')
def search():
    code = (request.args.get('code') or '').strip()
    if not code:
        return jsonify({"error": "code is required"}), 400

    # Search component by component_code
    comp = query_one(
        'SELECT c.*, o.order_number FROM components c LEFT JOIN orders o ON c.order_id = o.id WHERE c.component_code = ?',
        (code,)
    )
    if comp:
        return jsonify({"type": "component", "data": comp})

    # Search package by package_number
    pkg = query_one(
        'SELECT p.*, o.order_number FROM packages p LEFT JOIN orders o ON p.order_id = o.id WHERE p.package_number = ?',
        (code,)
    )
    if pkg:
        return jsonify({"type": "package", "data": pkg})

    # Search pallet by pallet_number
    pal = query_one(
        'SELECT * FROM pallets WHERE pallet_number = ?',
        (code,)
    )
    if pal:
        return jsonify({"type": "pallet", "data": pal})

    return jsonify({"type": "unknown", "data": {}}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)