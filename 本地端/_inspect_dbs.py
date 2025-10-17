# -*- coding: utf-8 -*-
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

paths = [
    os.path.join(BASE_DIR, 'packaging.db'),
    os.path.join(BASE_DIR, 'packing_system.db'),
    os.path.join(BASE_DIR, 'packing_system_new.db'),
    os.path.join(BASE_DIR, 'packing_system_test.db'),
]
# include backups
for f in os.listdir(BASE_DIR):
    if f.startswith('packing_system.db') and f.endswith('.bak'):
        paths.append(os.path.join(BASE_DIR, f))


def is_sqlite3(path):
    try:
        with open(path, 'rb') as f:
            return f.read(16).startswith(b'SQLite format 3')
    except Exception:
        return False


for p in paths:
    if not os.path.exists(p):
        continue
    print('===', p)
    print('valid sqlite:', is_sqlite3(p))
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print('tables:', tables)
        if 'orders' in tables:
            cur.execute('SELECT COUNT(*) FROM orders')
            print('orders count:', cur.fetchone()[0])
        conn.close()
    except Exception as e:
        print('open error:', e)