from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_PATH = 'packing_system.db'

# 在首次导入时尝试修复/初始化数据库文件，避免 unsupported file format
try:
    from database import Database as _DB
    _DB(DB_PATH)
except Exception:
    pass


def query_one(sql, params=()):
    try:
        conn = _DB(DB_PATH).get_connection()
    except Exception:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def query_all(sql, params=()):
    try:
        conn = _DB(DB_PATH).get_connection()
    except Exception:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
        '''SELECT c.*, o.order_number, o.customer_address 
           FROM components c 
           LEFT JOIN orders o ON c.order_id = o.id 
           WHERE c.component_code = ?''', (code,)
    )
    if comp:
        return jsonify({"ok": True, "type": "component", "data": comp})

    # Search package by package_number
    pkg = query_one(
        '''SELECT pk.*, o.order_number, o.customer_address, pal.pallet_number 
           FROM packages pk 
           LEFT JOIN orders o ON pk.order_id = o.id 
           LEFT JOIN pallets pal ON pk.pallet_id = pal.id 
           WHERE pk.package_number = ?''', (code,)
    )
    if pkg:
        return jsonify({"ok": True, "type": "package", "data": pkg})

    # Search pallet by pallet_number
    pal = query_one(
        '''SELECT p.*, o.order_number, o.customer_address 
           FROM pallets p 
           LEFT JOIN orders o ON p.order_id = o.id 
           WHERE p.pallet_number = ?''', (code,)
    )
    if pal:
        return jsonify({"ok": True, "type": "pallet", "data": pal})

    return jsonify({"ok": False, "error": "not found"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)