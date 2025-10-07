# 实时云数据库同步服务
# 监听本地SQLite数据库变化，实时同步到微信云开发数据库

import sqlite3
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import threading
import queue
# 新增：HTTP调用依赖与全量同步工具函数
import requests
from cloud_sync import fetch_pallets, fetch_packages, fetch_components, Database
# 新增：CLI 兜底所需
import subprocess
import re
import sys

class RealTimeCloudSync:
    def __init__(self, db_path: str = 'packing_system.db'):
        self.db_path = db_path
        self.sync_queue = queue.Queue()
        self.running = False
        self.sync_thread = None
        self.last_sync_time = {}
        # 新增：读取 packOps 配置（环境变量）
        self.packops_base_url = os.environ.get('PACKOPS_BASE_URL', '').strip()
        self.packops_api_key = os.environ.get('PACKOPS_API_KEY', '').strip()
        self.packops_env_id = os.environ.get('PACKOPS_ENV_ID', 'cloud1-7grjr7usb5d86f59').strip()
        verify_env = os.environ.get('PACKOPS_VERIFY', 'true').strip().lower()
        self.packops_verify = verify_env not in ('false', '0', 'no')
        # 兜底：从 invoke_packops_get_search.json 读取 API Key
        if not self.packops_api_key:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                fp = os.path.join(base_dir, 'invoke_packops_get_search.json')
                with open(fp, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                headers = cfg.get('headers') or {}
                key = headers.get('X-API-Key') or headers.get('x-api-key')
                if isinstance(key, str) and key.strip():
                    self.packops_api_key = key.strip()
                    self._log('已从 invoke_packops_get_search.json 读取到 API Key')
            except Exception:
                pass

    # 新增：统一日志方法（控制台 + 文件），便于在 GUI 模式下查看
    def _log(self, msg: str):
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            line = f'[{ts}] {msg}'
            # 控制台输出（如有）
            print(line)
            # 追加到日志文件
            base_dir = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(base_dir, 'cloud_sync.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            try:
                print(msg)
            except Exception:
                pass

    def start_sync_service(self):
        """启动同步服务"""
        if self.running:
            self._log("同步服务已在运行中")
            return
        # 检查必要配置
        if not self.packops_api_key:
            self._log("错误：未配置 PACKOPS_API_KEY 环境变量，且未在 invoke_packops_get_search.json 中找到 API Key，无法推送到云端。")
            return
        if not self.packops_base_url and not self.packops_env_id:
            self._log("错误：未配置 PACKOPS_BASE_URL 或 PACKOPS_ENV_ID，无法推送到云端。")
            return
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_worker)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        self._log("实时云数据库同步服务已启动 " + ("(HTTP)" if self.packops_base_url else "(CLI 兜底)"))

    def stop_sync_service(self):
        """停止同步服务"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        self._log("实时云数据库同步服务已停止")

    def _post_json(self, path: str, payload: Dict) -> Dict:
        """调用 packOps 接口：优先 HTTP，缺省走 CLI 兜底"""
        if not self.packops_base_url:
            return self._invoke_cli(path, payload)
        try:
            url = self.packops_base_url.rstrip('/')
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.packops_api_key,
            }
            body = dict(payload)
            body['path'] = path if path.startswith('/') else f'/{path}'
            resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=30, verify=self.packops_verify)
            try:
                return resp.json()
            except Exception:
                return {'status': resp.status_code, 'text': resp.text}
        except Exception as e:
            return {'error': str(e)}

    def _invoke_cli(self, path: str, payload: Dict) -> Dict:
        """使用 CloudBase CLI 直接调用 packOps 云函数（无 HTTP 域名时兜底）"""
        try:
            payload2 = dict(payload)
            payload2['path'] = path if path.startswith('/') else f'/{path}'
            event = {
                "httpMethod": "POST",
                "path": "/packOps",
                "headers": {"X-API-Key": self.packops_api_key, "Content-Type": "application/json"},
                "queryStringParameters": {"path": payload2['path']},
                "body": payload2
            }
            params = json.dumps(event, ensure_ascii=True)
            # Windows 下 tcb 为 .cmd，需通过 shell 调用并转义引号；使用字节输出并自适应解码
            if os.name == 'nt':
                escaped = params.replace('"', '\\"')
                cmd_str = f"tcb fn invoke packOps -e {self.packops_env_id} --params \"{escaped}\""
                res = subprocess.run(cmd_str, shell=True, capture_output=True, text=False, timeout=90)
                out_bytes = res.stdout or b''
                err_bytes = res.stderr or b''
                def _decode(b: bytes) -> str:
                    for enc in ('utf-8', 'gbk', 'latin-1'):
                        try:
                            return b.decode(enc)
                        except Exception:
                            continue
                    return b.decode('utf-8', errors='ignore')
                out = _decode(out_bytes)
                err = _decode(err_bytes)
            else:
                cmd = ["tcb", "fn", "invoke", "packOps", "-e", self.packops_env_id, "--params", params]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                out = res.stdout or ''
                err = res.stderr or ''
            if res.returncode != 0:
                return {"error": (err or out).strip()}
            # 更健壮的输出解析：优先直接定位最外层 JSON；否则兼容中文“返回结果：”
            start = out.find('{')
            end = out.rfind('}')
            json_text = out[start:end+1] if start != -1 and end != -1 and end > start else out.strip()
            try:
                wrapper = json.loads(json_text)
                body_str = wrapper.get("body")
                if isinstance(body_str, str):
                    try:
                        return json.loads(body_str)
                    except Exception:
                        return {"raw": wrapper}
                elif isinstance(body_str, dict):
                    return body_str
                else:
                    return wrapper
            except Exception:
                m = re.search(r'返回结果：(.+)', out, re.S)
                if m:
                    try:
                        return json.loads(m.group(1).strip())
                    except Exception:
                        pass
                return {"stdout": out}
        except Exception as e:
            return {"error": str(e)}

    def _sync_worker(self):
        """同步工作线程"""
        while self.running:
            try:
                # 处理同步队列中的任务
                if not self.sync_queue.empty():
                    task = self.sync_queue.get(timeout=1)
                    self._process_sync_task(task)
                else:
                    # 定期同步：将最近更新的数据批量推送到云端
                    self._periodic_sync_check()
                    # 等待片刻，避免过于频繁
                    time.sleep(10)
            except queue.Empty:
                continue
            except Exception as e:
                self._log(f"同步工作线程错误: {e}")
                time.sleep(5)

    def _process_sync_task(self, task: Dict):
        """处理同步任务"""
        try:
            task_type = task.get('type')
            data = task.get('data')
            # 将单个更新合并为批量推送，避免频繁调用
            if task_type == 'component':
                self._sync_recent_components()
            elif task_type == 'package':
                self._sync_recent_packages()
            elif task_type == 'pallet':
                self._sync_recent_pallets()
            elif task_type == 'full_sync':
                self._perform_full_sync()
            # 新增：云端删除与清空集合
            elif task_type == 'delete_components':
                try:
                    items = data.get('items') if isinstance(data, dict) else []
                    codes = [it.get('component_code') for it in items if isinstance(it, dict) and it.get('component_code')]
                    if codes:
                        payload = [{'component_code': c} for c in codes]
                        out = self._post_items_in_chunks('/delete/components', payload)
                        self._log('云端删除板件结果: ' + json.dumps(out, ensure_ascii=False))
                except Exception as e:
                    self._log(f"触发云端删除板件失败: {e}")
            elif task_type == 'delete_packages':
                try:
                    items = data.get('items') if isinstance(data, dict) else []
                    pkgs = [it.get('package_number') for it in items if isinstance(it, dict) and it.get('package_number')]
                    if pkgs:
                        payload = [{'package_number': p} for p in pkgs]
                        out = self._post_items_in_chunks('/delete/packages', payload)
                        self._log('云端删除包裹结果: ' + json.dumps(out, ensure_ascii=False))
                except Exception as e:
                    self._log(f"触发云端删除包裹失败: {e}")
            elif task_type == 'delete_pallets':
                try:
                    items = data.get('items') if isinstance(data, dict) else []
                    pals = [it.get('pallet_number') for it in items if isinstance(it, dict) and it.get('pallet_number')]
                    if pals:
                        payload = [{'pallet_number': p} for p in pals]
                        out = self._post_items_in_chunks('/delete/pallets', payload)
                        self._log('云端删除托盘结果: ' + json.dumps(out, ensure_ascii=False))
                except Exception as e:
                    self._log(f"触发云端删除托盘失败: {e}")
            elif task_type == 'clear':
                try:
                    cols = []
                    if isinstance(data, dict):
                        cols = data.get('collections') or []
                    out = self._post_json('/clear', {'collections': cols})
                    self._log('云端清空集合结果: ' + json.dumps(out, ensure_ascii=False))
                except Exception as e:
                    self._log(f"触发云端清空集合失败: {e}")
        except Exception as e:
            self._log(f"处理同步任务失败: {e}")

    # 新增：最近更新的批量推送（带关联合并字段）
    def _sync_recent_components(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute('PRAGMA busy_timeout = 5000')
                cur.execute('PRAGMA journal_mode = WAL')
                cur.execute('PRAGMA synchronous = NORMAL')
            except Exception:
                pass
            cur.execute(
                """
                SELECT c.component_code, c.component_name, o.order_number, pk.package_number, c.status
                FROM components AS c
                LEFT JOIN orders AS o ON c.order_id = o.id
                LEFT JOIN packages AS pk ON c.package_id = pk.id
                ORDER BY c.id DESC
                LIMIT 200
                """
            )
            rows = cur.fetchall()
            conn.close()
            items = [
                {
                    'component_code': r[0] or '',
                    'component_name': r[1] or '',
                    'order_number': r[2] or '',
                    'package_number': r[3] or '',
                    'status': r[4] or 'pending',
                }
                for r in rows
            ]
            if items:
                out = self._post_items_in_chunks('/sync/components', items)
                self._log('推送最近板件更新到云端: ' + json.dumps(out, ensure_ascii=False))
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            self._log(f"推送最近板件更新失败: {e}")

    def _sync_recent_packages(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute('PRAGMA busy_timeout = 5000')
                cur.execute('PRAGMA journal_mode = WAL')
                cur.execute('PRAGMA synchronous = NORMAL')
            except Exception:
                pass
            cur.execute(
                """
                SELECT pk.package_number, pk.package_index, o.order_number, pal.pallet_number, pk.component_count, pk.status, pk.notes
                FROM packages AS pk
                LEFT JOIN orders AS o ON pk.order_id = o.id
                LEFT JOIN pallets AS pal ON pk.pallet_id = pal.id
                ORDER BY pk.id DESC
                LIMIT 100
                """
            )
            rows = cur.fetchall()
            conn.close()
            items = [
                {
                    'package_number': r[0] or '',
                    'package_index': r[1],
                    'order_number': r[2] or '',
                    'pallet_number': r[3] or '',
                    'component_count': r[4] or 0,
                    'status': r[5] or 'open',
                    'notes': r[6] or '',
                }
                for r in rows
            ]
            if items:
                out = self._post_items_in_chunks('/sync/packages', items)
                self._log('推送最近包裹更新到云端: ' + json.dumps(out, ensure_ascii=False))
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            self._log(f"推送最近包裹更新失败: {e}")

    def _sync_recent_pallets(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute('PRAGMA busy_timeout = 5000')
                cur.execute('PRAGMA journal_mode = WAL')
                cur.execute('PRAGMA synchronous = NORMAL')
            except Exception:
                pass
            cur.execute(
                """
                SELECT p.pallet_number, p.pallet_index, o.order_number, p.package_count, p.status, p.notes
                FROM pallets AS p
                LEFT JOIN orders AS o ON p.order_id = o.id
                ORDER BY p.id DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
            conn.close()
            items = [
                {
                    'pallet_number': r[0] or '',
                    'pallet_index': r[1],
                    'order_number': r[2] or '',
                    'package_count': r[3] or 0,
                    'status': r[4] or 'open',
                    'notes': r[5] or '',
                }
                for r in rows
            ]
            if items:
                out = self._post_items_in_chunks('/sync/pallets', items)
                self._log('推送最近托盘更新到云端: ' + json.dumps(out, ensure_ascii=False))
        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            self._log(f"推送最近托盘更新失败: {e}")

    def _periodic_sync_check(self):
        """定期检查需要同步的数据"""
        try:
            # 最近更新的类型分别推送（批量）
            self._sync_recent_components()
            self._sync_recent_packages()
            self._sync_recent_pallets()
        except Exception as e:
            self._log(f"定期检查同步失败: {e}")

    def trigger_sync(self, data_type: str, data: Dict):
        """手动触发同步"""
        self.sync_queue.put({
            'type': data_type,
            'data': data,
            'timestamp': time.time()
        })
        self._log(f"手动触发同步: {data_type} - {data.get('id', 'unknown')}")

    def perform_full_sync(self):
        """执行全量同步（入队）"""
        self.sync_queue.put({
            'type': 'full_sync',
            'timestamp': time.time()
        })
        self._log("全量同步任务已添加到队列")

    def _sanitize_items(self, items: List[Dict]) -> List[Dict]:
        """将可能为 None 的字符串字段标准化为空字符串，避免云端正则/字符串处理报错"""
        string_keys = {
            'barcode', 'remarks', 'remark', 'custom_field1', 'custom_field2',
            'packing_method', 'pallet_code', 'package_code', 'component_code',
            'material', 'spec', 'name', 'type'
        }
        sanitized = []
        for it in items:
            if not isinstance(it, dict):
                sanitized.append(it)
                continue
            new_it = {}
            for k, v in it.items():
                if v is None and (k in string_keys or isinstance(v, str)):
                    new_it[k] = ''
                else:
                    new_it[k] = v
            # 归一化 component_code：去除首尾空白，若末位为小写 q 则改为大写 Q
            if 'component_code' in new_it and isinstance(new_it['component_code'], str):
                code = new_it['component_code'].strip()
                if code.endswith('q'):
                    code = code[:-1] + 'Q'
                new_it['component_code'] = code
            sanitized.append(new_it)
        return sanitized

    def _post_items_in_chunks(self, path: str, items: List[Dict], chunk_size: int = 300) -> Dict:
        """分片推送，兼容 CLI 兜底场景避免 --params 过大导致失败"""
        # CLI 模式下使用更小的分片以规避 Windows 命令行长度限制
        if not self.packops_base_url:
            if '/components' in path:
                chunk_size = 2
            elif '/packages' in path:
                chunk_size = 3
            elif '/pallets' in path:
                chunk_size = 3
            else:
                chunk_size = 2
        results = []
        for i in range(0, len(items), chunk_size):
            part = items[i:i + chunk_size]
            part = self._sanitize_items(part)
            res = self._post_json(path, {'items': part})
            results.append(res)
        return {'ok': True, 'chunks': results, 'total_chunks': len(results)}

    def _perform_full_sync(self):
        """真正执行全量同步：调用 cloud_sync 的 fetch_* 并推送到 packOps"""
        try:
            db = Database(self.db_path)
            pallets = fetch_pallets(db)
            packages = fetch_packages(db)
            components = fetch_components(db)
            out_pallets = self._post_items_in_chunks('/sync/pallets', pallets)
            out_packages = self._post_items_in_chunks('/sync/packages', packages)
            out_components = self._post_items_in_chunks('/sync/components', components)
            self._log('全量同步结果: ' + json.dumps({
                'pallets': out_pallets,
                'packages': out_packages,
                'components': out_components,
            }, ensure_ascii=False))
        except Exception as e:
            self._log(f"全量同步失败: {e}")

    def delete_components(self, component_codes: List[str]) -> Dict:
        """云端删除板件：传入 component_code 列表"""
        items = [{'component_code': c} for c in component_codes if isinstance(c, str) and c.strip()]
        if not items:
            return {'ok': True, 'chunks': [], 'total_chunks': 0}
        return self._post_items_in_chunks('/delete/components', items)

    def delete_packages(self, package_numbers: List[str]) -> Dict:
        """云端删除包裹：传入 package_number 列表（云端会自动解除关联板件）"""
        items = [{'package_number': p} for p in package_numbers if isinstance(p, str) and p.strip()]
        if not items:
            return {'ok': True, 'chunks': [], 'total_chunks': 0}
        return self._post_items_in_chunks('/delete/packages', items)

    def delete_pallets(self, pallet_numbers: List[str]) -> Dict:
        """云端删除托盘：传入 pallet_number 列表（云端会自动解除关联包裹）"""
        items = [{'pallet_number': p} for p in pallet_numbers if isinstance(p, str) and p.strip()]
        if not items:
            return {'ok': True, 'chunks': [], 'total_chunks': 0}
        return self._post_items_in_chunks('/delete/pallets', items)

    def clear_collections(self, collections: Optional[List[str]] = None) -> Dict:
        """云端清空集合：collections 可为 ['components','packages','pallets']，为空默认全清"""
        cols = collections or []
        return self._post_json('/clear', {'collections': cols})

if __name__ == '__main__':
    # 支持一次性运行模式，便于在命令行触发全量或增量推送
    if '--full-once' in sys.argv:
        svc = RealTimeCloudSync()
        svc._perform_full_sync()
    elif '--recent-once' in sys.argv:
        svc = RealTimeCloudSync()
        try:
            svc._sync_recent_components()
            svc._sync_recent_packages()
            svc._sync_recent_pallets()
        except Exception as e:
            print(f"一次性增量推送失败: {e}")
    else:
        # 测试实时同步服务
        sync_service = RealTimeCloudSync()

        try:
            # 启动同步服务
            sync_service.start_sync_service()
            # 立即触发一次全量同步，确保首次运行即可推送数据
            sync_service.perform_full_sync()

            print("实时云数据库同步服务正在运行...")
            print("按 Ctrl+C 停止服务")

            # 保持服务运行
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            sync_service.stop_sync_service()
            print('已退出')

# 单例访问：确保全局只有一个同步服务实例
_sync_singleton: Optional[RealTimeCloudSync] = None

def get_sync_service(db_path: Optional[str] = None) -> RealTimeCloudSync:
    global _sync_singleton
    if _sync_singleton is None:
        _sync_singleton = RealTimeCloudSync(db_path or 'packing_system.db')
        try:
            _sync_singleton.start_sync_service()
        except Exception:
            pass
    else:
        # 若传入 db_path 与现有不同，则更新实例的数据库路径并记录日志
        if isinstance(db_path, str) and db_path.strip() and _sync_singleton.db_path != db_path:
            _sync_singleton.db_path = db_path
            try:
                _sync_singleton._log(f'同步服务数据库路径已更新为: {db_path}')
            except Exception:
                pass
    return _sync_singleton