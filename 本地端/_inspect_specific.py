# -*- coding: utf-8 -*-
import os, sqlite3
BASE = os.path.dirname(os.path.abspath(__file__))
for name in ['packaging.db', 'packing_system_new.db', 'packing_system_test.db']:
    p = os.path.join(BASE, name)
    print('===', p)
    print('exists:', os.path.exists(p))
    if not os.path.exists(p):
        continue
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print('tables:', tables)
        for t in tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM {t}')
                print(f'count({t}):', cur.fetchone()[0])
            except Exception as e:
                print('count error for', t, ':', e)
        conn.close()
    except Exception as e:
        print('open error:', e)