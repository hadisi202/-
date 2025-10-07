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


def query_all(sql, params=()):
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
           WHERE c.component_code = ?''',
        (code,)
    )
    if comp:
        # Get package info if component has package_id (排除deleted状态)
        package = None
        pallet = None
        if comp.get('package_id'):
            package = query_one(
                '''SELECT p.*, o.order_number, o.customer_address 
                   FROM packages p 
                   LEFT JOIN orders o ON p.order_id = o.id 
                   WHERE p.id = ? ''',
                (comp['package_id'],)
            )
            # Get pallet info through pallet_packages关联
            if package and package.get('id'):
                pallet = query_one(
                    '''SELECT pal.* FROM pallets pal 
                       INNER JOIN pallet_packages pp ON pal.id = pp.pallet_id 
                       WHERE pp.package_id = ?''',
                    (package['id'],)
                )
        
        return jsonify({
            "type": "component", 
            "data": comp,
            "package": package,
            "pallet": pallet
        })

    # Search package by package_number (排除deleted状态)
    pkg = query_one(
        '''SELECT p.*, o.order_number, o.customer_address 
           FROM packages p 
           LEFT JOIN orders o ON p.order_id = o.id 
           WHERE p.package_number = ? ''',
        (code,)
    )
    if pkg:
        # Get components in this package
        components = query_all(
            '''SELECT c.*, o.order_number, o.customer_address 
               FROM components c 
               LEFT JOIN orders o ON c.order_id = o.id 
               WHERE c.package_id = ?''',
            (pkg['id'],)
        )
        return jsonify({"type": "package", "data": pkg, "components": components})

    # Search pallet by pallet_number
    pal = query_one(
        'SELECT * FROM pallets WHERE pallet_number = ?',
        (code,)
    )
    if pal:
        # Get packages in this pallet through pallet_packages关联 (排除deleted状态)
        packages = query_all(
            '''SELECT p.*, o.order_number, o.customer_address 
               FROM packages p 
               INNER JOIN pallet_packages pp ON p.id = pp.package_id
               LEFT JOIN orders o ON p.order_id = o.id 
               WHERE pp.pallet_id = ? ''',
            (pal['id'],)
        )
        
        # Get components for each package
        for package in packages:
            components = query_all(
                '''SELECT c.*, o.order_number, o.customer_address 
                   FROM components c 
                   LEFT JOIN orders o ON c.order_id = o.id 
                   WHERE c.package_id = ?''',
                (package['id'],)
            )
            package['components'] = components
        
        return jsonify({"type": "pallet", "data": pal, "packages": packages})

    return jsonify({"type": "unknown", "data": {}}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)