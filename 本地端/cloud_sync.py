"""
cloud_sync.py
本地同步脚本：从本地 SQLite 读取托盘/包裹/板件数据，批量推送到云函数 packOps。

用法示例：
  python cloud_sync.py --base-url https://<your-function-domain>/packOps/ --api-key <API_KEY> --full

也可分别指定：--sync pallets / --sync packages / --sync components
"""

import argparse
import json
import sys
from typing import List, Dict, Iterable

import requests
from urllib.parse import urlencode

from database import Database
import os
import datetime


def fetch_pallets(db: Database) -> List[Dict]:
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.pallet_number, o.order_number, p.package_count, p.status, p.notes, p.pallet_index, o.customer_address
            FROM pallets AS p
            LEFT JOIN orders AS o ON p.order_id = o.id
            ORDER BY p.id ASC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "pallet_number": r[0] or "",
                "order_number": r[1] or "",
                "package_count": r[2] or 0,
                "status": r[3] or "open",
                "notes": r[4] or "",
                "pallet_index": (r[5] if r[5] is not None else None),
                "customer_address": r[6] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()


def fetch_packages(db: Database) -> List[Dict]:
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT pk.package_number, o.order_number, pal.pallet_number, pk.component_count, pk.status, pk.notes, pk.package_index, o.customer_address
            FROM packages AS pk
            LEFT JOIN orders AS o ON pk.order_id = o.id
            LEFT JOIN pallets AS pal ON pk.pallet_id = pal.id
            ORDER BY pk.id ASC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "package_number": r[0] or "",
                "order_number": r[1] or "",
                "pallet_number": r[2] or "",
                "component_count": r[3] or 0,
                "status": r[4] or "open",
                "notes": r[5] or "",
                "package_index": (r[6] if r[6] is not None else None),
                "customer_address": r[7] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()


def fetch_components(db: Database) -> List[Dict]:
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.component_code, c.component_name, o.order_number, pk.package_number, c.status, c.material, c.finished_size, c.room_number, c.cabinet_number, o.customer_address
            FROM components AS c
            LEFT JOIN orders AS o ON c.order_id = o.id
            LEFT JOIN packages AS pk ON c.package_id = pk.id
            ORDER BY c.id ASC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "component_code": r[0] or "",
                "component_name": r[1] or "",
                "order_number": r[2] or "",
                "package_number": r[3] or "",
                "status": r[4] or "pending",
                "material": r[5] or "",
                "finished_size": r[6] or "",
                "room_number": r[7] or "",
                "cabinet_number": r[8] or "",
                "customer_address": r[9] or "",
            }
            for r in rows
        ]
    finally:
        conn.close()


def _build_url(base_url: str) -> str:
    """基础 /packOps/ 路径必须与 HTTP 访问服务配置完全一致，需保留末尾斜杠"""
    return base_url if base_url.endswith('/') else base_url + '/'


def _chunk(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]

# 简单文件日志工具
def _log(msg: str):
    try:
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{ts}] {msg}'
        print(line)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(base_dir, 'cloud_sync.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        try:
            print(msg)
        except Exception:
            pass


def post_json(base_url: str, path: str, api_key: str, payload: Dict, verify: bool = True) -> Dict:
    url = _build_url(base_url)
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }
    body = dict(payload)
    body['path'] = path if path.startswith('/') else f'/{path}'
    _log(f"POST {url} path={body['path']} items={(len(body.get('items', [])) if isinstance(body.get('items'), list) else 0)} verify={verify}")
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60, verify=verify)
    except requests.exceptions.RequestException as e:
        _log(f"ERR requests {e.__class__.__name__}: {e}")
        return {"ok": False, "error": str(e), "type": e.__class__.__name__}
    try:
        out = resp.json()
        _log(f"RESP {resp.status_code} len={len(json.dumps(out, ensure_ascii=False))}")
        return out
    except Exception:
        _log(f"RESP {resp.status_code} text={resp.text[:200]}")
        return {"status": resp.status_code, "text": resp.text}


def post_items_in_chunks(base_url: str, path: str, api_key: str, items: List[Dict], verify: bool = True, chunk_size: int = 300) -> Dict:
    """分片推送，避免云函数的最大请求体限制"""
    results = []
    for part in _chunk(items, chunk_size):
        res = post_json(base_url, path, api_key, {"items": part}, verify=verify)
        results.append(res)
    return {"ok": True, "chunks": results, "total_chunks": len(results)}


def do_sync(db: Database, base_url: str, api_key: str, target: str, verify: bool = True):
    if target == "pallets":
        items = fetch_pallets(db)
        return post_items_in_chunks(base_url, "/sync/pallets", api_key, items, verify=verify)
    elif target == "packages":
        items = fetch_packages(db)
        return post_items_in_chunks(base_url, "/sync/packages", api_key, items, verify=verify)
    elif target == "components":
        items = fetch_components(db)
        return post_items_in_chunks(base_url, "/sync/components", api_key, items, verify=verify)
    else:
        raise ValueError("unknown sync target: " + target)


def main():
    parser = argparse.ArgumentParser(description="Sync local SQLite data to cloud database via packOps")
    parser.add_argument("--base-url", required=True, help="HTTP base url of packOps cloud function, e.g. https://service-XXXX.tcloudbaseapp.com/packOps/ (注意末尾斜杠)")
    parser.add_argument("--api-key", required=True, help="API key configured in cloud function env")
    parser.add_argument("--full", action="store_true", help="Sync pallets, packages, and components sequentially")
    parser.add_argument("--sync", choices=["pallets", "packages", "components"], help="Sync a single target")
    parser.add_argument("--verify", dest="verify", type=lambda v: str(v).lower() != 'false', default=True,
                        help="TLS certificate verification (set to false to disable, e.g. --verify false)")

    args = parser.parse_args()
    db = Database("packing_system.db")

    if args.full:
        outputs = {}
        for t in ["pallets", "packages", "components"]:
            outputs[t] = do_sync(db, args.base_url, args.api_key, t, verify=args.verify)
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return

    if args.sync:
        out = do_sync(db, args.base_url, args.api_key, args.sync, verify=args.verify)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("请使用 --full 或者 --sync <target>")
        sys.exit(2)


if __name__ == "__main__":
    main()