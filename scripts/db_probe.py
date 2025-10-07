import sqlite3
import json


def probe(db_path='packing_system.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    res = {}
    # 基本表计数
    for name in ['components', 'packages', 'pallets', 'orders', 'pallet_packages']:
        try:
            cur.execute(f'SELECT COUNT(*) AS cnt FROM {name}')
            res[name] = cur.fetchone()['cnt']
        except Exception as e:
            res[name] = {'error': str(e)}

    # 状态分布
    breakdown = {}
    try:
        cur.execute('SELECT status, COUNT(*) AS cnt FROM packages GROUP BY status')
        breakdown['packages_by_status'] = {r['status'] if r['status'] is not None else 'NULL': r['cnt'] for r in cur.fetchall()}
    except Exception as e:
        breakdown['packages_by_status'] = {'error': str(e)}
    try:
        cur.execute('SELECT status, COUNT(*) AS cnt FROM pallets GROUP BY status')
        breakdown['pallets_by_status'] = {r['status'] if r['status'] is not None else 'NULL': r['cnt'] for r in cur.fetchall()}
    except Exception as e:
        breakdown['pallets_by_status'] = {'error': str(e)}

    # 样本数据
    samples = {}
    try:
        cur.execute("SELECT component_code FROM components WHERE component_code IS NOT NULL AND TRIM(component_code) <> '' LIMIT 3")
        samples['component_codes'] = [r['component_code'] for r in cur.fetchall()]
    except Exception as e:
        samples['component_codes'] = {'error': str(e)}
    try:
        cur.execute("SELECT package_number, status, order_id, pallet_id FROM packages ORDER BY id DESC LIMIT 5")
        samples['packages_recent'] = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        samples['packages_recent'] = {'error': str(e)}
    try:
        cur.execute("SELECT pallet_number, status, order_id FROM pallets ORDER BY id DESC LIMIT 5")
        samples['pallets_recent'] = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        samples['pallets_recent'] = {'error': str(e)}
    try:
        cur.execute("SELECT pallet_id, package_id FROM pallet_packages ORDER BY rowid DESC LIMIT 5")
        samples['pallet_packages_recent'] = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        samples['pallet_packages_recent'] = {'error': str(e)}

    conn.close()
    return {'counts': res, 'breakdown': breakdown, 'samples': samples}


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False, indent=2))