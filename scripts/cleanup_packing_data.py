#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键清理本地打包系统数据：
- 备份数据库到 backup_YYYYMMDD_HHMMSS.db
- 将所有板件的 package_id 置为 NULL，并把状态置为 pending（如存在 status 字段）
- 清空托盘-包裹关联表 pallet_packages
- 删除所有包裹 packages
- 删除所有托盘 pallets
- 输出清理前后统计
使用方法：
  python scripts/cleanup_packing_data.py
"""
import sqlite3
import shutil
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'packing_system.db')
DB_PATH = os.path.abspath(DB_PATH)


def count_all(cur):
    def count(table):
        try:
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            return cur.fetchone()[0]
        except Exception:
            return None
    def breakdown_packages():
        try:
            cur.execute('SELECT status, COUNT(*) FROM packages GROUP BY status')
            return dict(cur.fetchall())
        except Exception:
            return None
    return {
        'components': count('components'),
        'packages': count('packages'),
        'pallets': count('pallets'),
        'orders': count('orders'),
        'pallet_packages': count('pallet_packages'),
        'packages_by_status': breakdown_packages(),
    }


def backup_db(db_path: str) -> str:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(os.path.dirname(db_path), f'backup_{ts}.db')
    shutil.copyfile(db_path, backup)
    return backup


def main():
    print(f'数据库路径: {DB_PATH}')
    if not os.path.exists(DB_PATH):
        print('❌ 未找到数据库文件')
        return
    backup = backup_db(DB_PATH)
    print(f'✅ 已备份数据库到: {backup}')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print('=== 清理前统计 ===')
    print(count_all(cur))

    try:
        cur.execute('BEGIN')
        # 1) 将所有板件解除包裹关联，并恢复状态
        try:
            cur.execute('UPDATE components SET package_id = NULL WHERE package_id IS NOT NULL')
            # 若存在 status 字段，置为 pending
            try:
                cur.execute("UPDATE components SET status = 'pending' WHERE status IS NOT NULL")
            except Exception:
                pass
        except Exception as e:
            print(f'组件解除包裹关联失败: {e}')

        # 2) 清空托盘-包裹关联表
        try:
            cur.execute('DELETE FROM pallet_packages')
        except Exception as e:
            print(f'清空 pallet_packages 失败: {e}')

        # 3) 删除所有包裹
        try:
            cur.execute('DELETE FROM packages')
        except Exception as e:
            print(f'删除 packages 失败: {e}')

        # 4) 删除所有托盘
        try:
            cur.execute('DELETE FROM pallets')
        except Exception as e:
            print(f'删除 pallets 失败: {e}')

        cur.execute('COMMIT')
        print('✅ 清理操作已提交')
    except Exception as e:
        conn.execute('ROLLBACK')
        print(f'❌ 清理失败，已回滚: {e}')
    finally:
        print('=== 清理后统计 ===')
        print(count_all(cur))
        conn.close()


if __name__ == '__main__':
    main()