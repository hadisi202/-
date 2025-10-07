import threading
import time
import random
import traceback
from datetime import datetime

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Database from local project
from database import Database

"""
并发锁回归测试脚本：在独立测试数据库上并发执行以下操作，观察是否出现 database is locked：
- 移动包裹到其他托盘
- 从托盘移出包裹
- 创建托盘
- 删除托盘

避免影响生产库：使用 packing_system_test.db。
"""

TEST_DB_PATH = "packing_system_test.db"
ORDER_NUMBER = f"TEST-ORDER-{int(time.time())}"

lock_errors = 0
other_errors = 0
ops_done = 0
lock_errors_lock = threading.Lock()
ops_lock = threading.Lock()


def setup_initial_data(db: Database):
    conn = db.get_connection()
    cur = conn.cursor()
    # 创建订单
    cur.execute(
        """
        INSERT INTO orders (order_number, customer_name, status, created_at)
        VALUES (?, '测试客户', 'active', datetime('now'))
        """,
        (ORDER_NUMBER,),
    )
    cur.execute("SELECT id FROM orders WHERE order_number = ?", (ORDER_NUMBER,))
    order_id = cur.fetchone()[0]

    # 创建初始托盘 3 个
    pallet_ids = []
    for i in range(3):
        # 计算下一个 pallet_index（订单内最大+1）
        cur.execute(
            "SELECT COALESCE(MAX(CASE WHEN pallet_index IS NULL OR trim(pallet_index)='' THEN 0 ELSE CAST(pallet_index AS INTEGER) END), 0) + 1 FROM pallets WHERE order_id = ?",
            (order_id,),
        )
        next_index = cur.fetchone()[0]
        pallet_number = f"P-{i+1}-{int(time.time())}"
        cur.execute(
            """
            INSERT INTO pallets (pallet_number, pallet_type, status, created_at, order_id, pallet_index)
            VALUES (?, 'physical', 'open', datetime('now'), ?, ?)
            """,
            (pallet_number, order_id, str(next_index)),
        )
        cur.execute("SELECT id FROM pallets WHERE pallet_number = ?", (pallet_number,))
        pallet_ids.append(cur.fetchone()[0])

    # 创建包裹 60 个，随机分配到托盘
    for i in range(60):
        pkg_num = f"PKG-{i+1}-{int(time.time())}"
        status = random.choice(["completed", "sealed", "completed"])  # 大多 completed
        assigned = random.choice([True, False, True])  # 大多分配到托盘
        pallet_id = random.choice(pallet_ids) if assigned else None
        cur.execute(
            """
            INSERT INTO packages (package_number, order_id, component_count, pallet_id, created_at, status)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
            """,
            (pkg_num, order_id, random.randint(1, 12), pallet_id, status),
        )
    conn.commit()
    conn.close()
    return order_id, pallet_ids


def op_move_packages(db: Database, order_id: int):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        # 选择源托盘（有包裹且状态允许）
        cur.execute(
            """
            SELECT id FROM pallets WHERE order_id = ? AND status='open' ORDER BY RANDOM() LIMIT 1
            """,
            (order_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        src_id = row[0]
        # 选择目标托盘
        cur.execute(
            "SELECT id FROM pallets WHERE order_id = ? AND status='open' AND id<>? ORDER BY RANDOM() LIMIT 1",
            (order_id, src_id),
        )
        row = cur.fetchone()
        if not row:
            return
        tgt_id = row[0]
        # 选 1-3 个可移动的包裹（completed 或 sealed）
        cur.execute(
            """
            SELECT id FROM packages WHERE pallet_id = ? AND status IN ('completed','sealed') ORDER BY RANDOM() LIMIT ?
            """,
            (src_id, random.randint(1, 3)),
        )
        pkgs = cur.fetchall()
        for (pkg_id,) in pkgs:
            cur.execute("UPDATE packages SET pallet_id = ? WHERE id = ?", (tgt_id, pkg_id))
        conn.commit()
    except Exception as e:
        with lock_errors_lock:
            global lock_errors, other_errors
            if "database is locked" in str(e).lower():
                lock_errors += 1
            else:
                other_errors += 1
    finally:
        conn.close()
    with ops_lock:
        global ops_done
        ops_done += 1


def op_delete_packages(db: Database, order_id: int):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        # 选择托盘
        cur.execute(
            "SELECT id FROM pallets WHERE order_id = ? ORDER BY RANDOM() LIMIT 1",
            (order_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        pid = row[0]
        # 选 1-3 个包裹移出托盘
        cur.execute(
            "SELECT id, status FROM packages WHERE pallet_id = ? ORDER BY RANDOM() LIMIT ?",
            (pid, random.randint(1, 3)),
        )
        pkgs = cur.fetchall()
        for pkg_id, status in pkgs:
            new_status = "completed" if status == "sealed" else status
            cur.execute(
                "UPDATE packages SET pallet_id = NULL, status = ? WHERE id = ?",
                (new_status, pkg_id),
            )
        conn.commit()
    except Exception as e:
        with lock_errors_lock:
            global lock_errors, other_errors
            if "database is locked" in str(e).lower():
                lock_errors += 1
            else:
                other_errors += 1
    finally:
        conn.close()
    with ops_lock:
        global ops_done
        ops_done += 1


def op_create_pallet(db: Database, order_id: int):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COALESCE(MAX(CASE WHEN pallet_index IS NULL OR trim(pallet_index)='' THEN 0 ELSE CAST(pallet_index AS INTEGER) END), 0) + 1 FROM pallets WHERE order_id = ?",
            (order_id,),
        )
        next_index = cur.fetchone()[0]
        pallet_number = f"P-NEW-{random.randint(1000,9999)}-{int(time.time()*1000)}"
        cur.execute(
            """
            INSERT INTO pallets (pallet_number, pallet_type, status, created_at, order_id, pallet_index)
            VALUES (?, 'physical', 'open', datetime('now'), ?, ?)
            """,
            (pallet_number, order_id, str(next_index)),
        )
        conn.commit()
    except Exception as e:
        with lock_errors_lock:
            global lock_errors, other_errors
            if "database is locked" in str(e).lower():
                lock_errors += 1
            else:
                other_errors += 1
    finally:
        conn.close()
    with ops_lock:
        global ops_done
        ops_done += 1


def op_delete_pallet(db: Database, order_id: int):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        # 随机选一个托盘
        cur.execute(
            "SELECT id, pallet_number FROM pallets WHERE order_id = ? ORDER BY RANDOM() LIMIT 1",
            (order_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        pid, pnum = row
        # 移出其包裹
        cur.execute(
            "UPDATE packages SET pallet_id = NULL, status = CASE WHEN status='sealed' THEN 'completed' ELSE status END WHERE pallet_id = ?",
            (pid,),
        )
        # 删除托盘
        cur.execute("DELETE FROM pallets WHERE id = ?", (pid,))
        conn.commit()
    except Exception as e:
        with lock_errors_lock:
            global lock_errors, other_errors
            if "database is locked" in str(e).lower():
                lock_errors += 1
            else:
                other_errors += 1
    finally:
        conn.close()
    with ops_lock:
        global ops_done
        ops_done += 1


def worker_thread(db: Database, order_id: int, duration_sec: int = 10):
    end_time = time.time() + duration_sec
    ops = [op_move_packages, op_delete_packages, op_create_pallet, op_delete_pallet]
    while time.time() < end_time:
        op = random.choice(ops)
        op(db, order_id)
        # 小延迟促进交错
        time.sleep(random.uniform(0.005, 0.02))


def main():
     print("[并发锁回归测试] 初始化...")
     db = Database(TEST_DB_PATH)
     # 初始化表结构（Database.init_database 会调用 get_connection 并创建所有表）
     db.init_database()
     # 支持通过环境变量禁用 WAL 测试：TEST_DISABLE_WAL=1
     try:
         disable_wal = os.environ.get('TEST_DISABLE_WAL') == '1'
         if disable_wal:
             db.set_setting('enable_wal', 'false')
             print("已禁用 WAL 模式 (enable_wal=false)")
         else:
             # 显式启用，防止之前测试残留
             db.set_setting('enable_wal', 'true')
             print("已启用 WAL 模式 (enable_wal=true)")
     except Exception:
         pass
     order_id, pallet_ids = setup_initial_data(db)
     print(f"创建测试订单 {ORDER_NUMBER}，托盘数: {len(pallet_ids)}")
 
     threads = []
     thread_count = 6
     duration_sec = 15
     print(f"启动 {thread_count} 个线程，持续 {duration_sec} 秒进行并发操作...")
     for _ in range(thread_count):
         t = threading.Thread(target=worker_thread, args=(db, order_id, duration_sec))
         t.daemon = True
         t.start()
         threads.append(t)
     for t in threads:
         t.join()
 
     print("测试完成。")
     print(f"总操作数: {ops_done}")
     print(f"database is locked 错误次数: {lock_errors}")
     print(f"其他错误次数: {other_errors}")
     # 简要检查数据库基本计数
     conn = db.get_connection()
     cur = conn.cursor()
     cur.execute("SELECT COUNT(*) FROM pallets WHERE order_id = ?", (order_id,))
     pal_cnt = cur.fetchone()[0]
     cur.execute("SELECT COUNT(*) FROM packages WHERE order_id = ?", (order_id,))
     pkg_cnt = cur.fetchone()[0]
     conn.close()
     print(f"当前托盘数: {pal_cnt}，包裹数: {pkg_cnt}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
            print("测试运行异常:", e)
            traceback.print_exc()