# -*- coding: utf-8 -*-
from database import db
import sqlite3
print('db_path:', db.db_path)
conn = db.get_connection()
cur = conn.cursor()
for t in ['orders','components','packages','pallets','operation_logs']:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(t, cur.fetchone()[0])
    except Exception as e:
        print(t, 'error:', e)
conn.close()