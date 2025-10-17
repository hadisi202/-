# -*- coding: utf-8 -*-
"""
恢复主数据库 packing_system.db 的历史订单数据：
- 自动检测目录下可能的旧数据库或备份文件
- 优先选择包含 orders 表且订单数量最多的候选库
- 将该候选库复制覆盖为当前主库（packing_system.db）
- 保留当前主库为备份文件 packing_system.db.pre_recover_YYYYMMDD_HHMMSS.bak
注意：请确保应用未在运行，避免文件锁导致恢复失败。
"""
import os
import sqlite3
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_DB = os.path.join(BASE_DIR, 'packing_system.db')

CANDIDATE_NAMES = [
    'packaging.db',
    'packing_system_new.db',
    'packing_system_test.db',
]

def is_sqlite3(path: str) -> bool:
    try:
        if not os.path.exists(path):
            return False
        with open(path, 'rb') as f:
            hdr = f.read(16)
        return hdr.startswith(b'SQLite format 3')
    except Exception:
        return False

def get_orders_count(path: str):
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        count = None
        if 'orders' in tables:
            cur.execute('SELECT COUNT(*) FROM orders')
            count = cur.fetchone()[0]
        conn.close()
        return count, tables
    except Exception:
        return None, []

def find_backup_files():
    backups = []
    for f in os.listdir(BASE_DIR):
        if f.startswith('packing_system.db.invalid_') and f.endswith('.bak'):
            backups.append(os.path.join(BASE_DIR, f))
        if f.startswith('packing_system.db.pre_recover_') and f.endswith('.bak'):
            backups.append(os.path.join(BASE_DIR, f))
    backups.sort(reverse=True)
    return backups

def choose_best_candidate():
    candidates = []
    # predefined names
    for name in CANDIDATE_NAMES:
        path = os.path.join(BASE_DIR, name)
        if is_sqlite3(path):
            oc, tables = get_orders_count(path)
            candidates.append({'path': path, 'orders': oc or 0, 'tables': tables})
    # backups
    for path in find_backup_files():
        if is_sqlite3(path):
            oc, tables = get_orders_count(path)
            candidates.append({'path': path, 'orders': oc or 0, 'tables': tables})
    # pick by max orders
    candidates.sort(key=lambda x: x['orders'], reverse=True)
    return candidates[0] if candidates else None

def backup_current():
    if os.path.exists(CURRENT_DB):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        bak = os.path.join(BASE_DIR, f'packing_system.db.pre_recover_{ts}.bak')
        try:
            os.replace(CURRENT_DB, bak)
            print(f'[recover] Backed up current db to: {bak}')
            return bak
        except Exception as e:
            print(f'[recover] Failed to backup current db: {e}')
    return None

def restore_from(path: str):
    try:
        shutil.copy2(path, CURRENT_DB)
        print(f'[recover] Restored db from candidate: {path} -> {CURRENT_DB}')
    except Exception as e:
        print(f'[recover] Failed to restore from {path}: {e}')

def verify_current():
    if not is_sqlite3(CURRENT_DB):
        print('[verify] Current db is not a valid SQLite file.')
        return
    oc, tables = get_orders_count(CURRENT_DB)
    print(f'[verify] Current orders count: {oc}')
    print(f'[verify] Current tables: {tables}')

if __name__ == '__main__':
    print('[recover] Base dir:', BASE_DIR)
    best = choose_best_candidate()
    if best and best['orders'] > 0:
        print(f"[recover] Found candidate with orders: {best['orders']} -> {best['path']}")
        backup_current()
        restore_from(best['path'])
        verify_current()
    else:
        print('[recover] No suitable candidate database found (with orders > 0).')
        # 仍做一次验证输出当前库信息
        verify_current()