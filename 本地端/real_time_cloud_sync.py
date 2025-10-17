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
from cloud_sync import fetch_pallets, fetch_packages, fetch_components
from database import Database
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
        # 进度文件路径（供前端轮询显示百分比）
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._progress_file = os.path.join(base_dir, 'sync_progress.json')
        except Exception:
            self._progress_file = 'sync_progress.json'
        # 在进行任何直接 sqlite3.connect 之前，先用 Database 类修复/初始化无效文件
        try:
            Database(self.db_path)
        except Exception:
            pass
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
            # 追加到日志文件（带简单滚动）
            base_dir = os.path.dirname(os.path.abspath(__file__))
            log_path = os.path.join(base_dir, 'cloud_sync.log')
            # 简单日志滚动：超过5MB则备份为 cloud_sync.log.bak
            try:
                if os.path.exists(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:
                    bak_path = os.path.join(base_dir, 'cloud_sync.log.bak')
                    try:
                        if os.path.exists(bak_path):
                            os.remove(bak_path)
                    except Exception:
                        pass
                    os.replace(log_path, bak_path)
            except Exception:
                pass
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
        # 进程级互斥：通过锁文件避免多进程并发推送
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._lock_path = os.path.join(base_dir, 'sync.lock')
            try:
                self._lock_file = open(self._lock_path, 'x')
            except FileExistsError:
                try:
                    mtime = os.path.getmtime(self._lock_path)
                    age = time.time() - mtime
                    if age > 600:
                        os.remove(self._lock_path)
                        self._lock_file = open(self._lock_path, 'x')
                        self._log("发现过期锁文件，已清理并继续启动")
                    else:
                        self._log("检测到已有同步服务在运行（sync.lock 存在），已取消启动以避免多端并发冲突")
                        return
                except Exception as e:
                    self._log(f"检查/清理锁文件失败：{e}")
                    return
        except Exception as e:
            self._log(f"创建锁文件失败：{e}")
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
        # 避免在工作线程内 join 自身导致阻塞
        try:
            if self.sync_thread and threading.current_thread() is not self.sync_thread:
                self.sync_thread.join(timeout=5)
        except Exception:
            pass
        # 释放锁文件
        try:
            if hasattr(self, '_lock_file') and self._lock_file:
                self._lock_file.close()
            if hasattr(self, '_lock_path') and self._lock_path and os.path.exists(self._lock_path):
                os.remove(self._lock_path)
        except Exception:
            pass
        self._log("实时云数据库同步服务已停止")

    def _post_json(self, path: str, payload: Dict) -> Dict:
        """调用 packOps 接口：优先 HTTP，缺省走 CLI 兜底"""
        # 若未配置 HTTP，则直接走 CLI
        if not self.packops_base_url:
            return self._invoke_cli(path, payload)
        # 先尝试 HTTP，失败后自动兜底到 CLI
        try:
            base = self.packops_base_url.rstrip('/')
            # 将路由通过 query string 传递给 packOps（与 CLI 事件一致）
            route = path if path.startswith('/') else f'/{path}'
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.packops_api_key,
            }
            body = dict(payload)
            # 尝试方式一：仅映射到 /packOps 的场景（通过 ?path= 传递子路由）
            sep = '&' if ('?' in base) else '?'
            url_qs = f"{base}{sep}path={route}"
            self._log(f"HTTP 尝试1: {url_qs}")
            resp = requests.post(url_qs, headers=headers, data=json.dumps(body), timeout=30, verify=self.packops_verify)
            if 200 <= resp.status_code < 300:
                try:
                    return resp.json()
                except Exception:
                    return {'status': resp.status_code, 'text': resp.text}
            # 尝试方式二：直接拼接子路由（映射到 /packOps/** 的场景）
            url_direct = f"{base}{route}"
            self._log(f"HTTP 尝试2: {url_direct}（上次状态 {resp.status_code}）")
            resp2 = requests.post(url_direct, headers=headers, data=json.dumps(body), timeout=30, verify=self.packops_verify)
            if 200 <= resp2.status_code < 300:
                try:
                    return resp2.json()
                except Exception:
                    return {'status': resp2.status_code, 'text': resp2.text}
            # 两种方式均失败，转 CLI 兜底
            self._log(f"HTTP 调用均失败({resp.status_code}/{resp2.status_code})，尝试 CLI 兜底：{route}")
            return self._invoke_cli(path, payload)
        except Exception as e:
            self._log(f"HTTP 调用异常，尝试 CLI 兜底：{e}")
            return self._invoke_cli(path, payload)

    # 进度写入工具方法
    def _write_progress(self, data: Dict):
        try:
            tmp_path = f"{self._progress_file}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, self._progress_file)
        except Exception:
            # 非关键路径，忽略写入失败
            pass

    def _start_progress(self, operation: str, data_type: str, total_chunks: int):
        payload = {
            'operation': operation,
            'data_type': data_type,
            'status': 'in_progress',
            'percent': 0,
            'total_chunks': max(1, int(total_chunks)),
            'completed_chunks': 0,
            'failed_chunks': 0,
            'updated_at': datetime.now().isoformat(timespec='seconds')
        }
        self._write_progress(payload)

    def _update_progress(self, operation: str, data_type: str, completed_chunks: int, total_chunks: int, failed_chunks: int = 0):
        total = max(1, int(total_chunks))
        completed = max(0, int(completed_chunks))
        percent = int((completed / total) * 100)
        payload = {
            'operation': operation,
            'data_type': data_type,
            'status': 'in_progress',
            'percent': percent,
            'total_chunks': total,
            'completed_chunks': completed,
            'failed_chunks': max(0, int(failed_chunks)),
            'updated_at': datetime.now().isoformat(timespec='seconds')
        }
        self._write_progress(payload)

    def _finish_progress(self, operation: str, data_type: str, total_chunks: int, failed_chunks: int = 0):
        payload = {
            'operation': operation,
            'data_type': data_type,
            'status': 'completed' if failed_chunks == 0 else 'failed',
            'percent': 100,
            'total_chunks': max(1, int(total_chunks)),
            'completed_chunks': max(1, int(total_chunks)),
            'failed_chunks': max(0, int(failed_chunks)),
            'updated_at': datetime.now().isoformat(timespec='seconds')
        }
        self._write_progress(payload)

    def _sync_worker(self):
        """后台工作线程：消费队列并执行同步任务；空闲时做周期性检查"""
        self._log("同步工作线程已启动")
        idle_counter = 0
        while self.running:
            try:
                task = self.sync_queue.get(timeout=1)
                idle_counter = 0
            except Exception:
                task = None
                idle_counter += 1
            try:
                if not task:
                    # 每 ~30 秒做一次轻量的周期性检查
                    if idle_counter >= 30:
                        idle_counter = 0
                        self._periodic_sync_check()
                    continue
                t = (task.get('type') or '').strip()
                data = task.get('data') or {}
                if t == 'full_sync':
                    self._log('开始执行全量同步任务')
                    self._perform_full_sync()
                elif t == 'component':
                    self._log('处理最近板件更新任务')
                    self._sync_recent_components()
                elif t == 'package':
                    self._log('处理最近包裹更新任务')
                    self._sync_recent_packages()
                elif t == 'pallet':
                    self._log('处理最近托盘更新任务')
                    self._sync_recent_pallets()
                elif t == 'clear':
                    cols = data.get('collections') if isinstance(data, dict) else None
                    self._log(f'执行云端清理任务: {cols}')
                    out = self.clear_collections(cols)
                    self._log('云端清理结果: ' + json.dumps(out, ensure_ascii=False))
                else:
                    self._log(f'忽略未知任务类型: {t}')
            except Exception as e:
                self._log(f"工作线程处理任务失败: {e}")

    def _invoke_cli(self, path: str, payload: Dict) -> Dict:
        """CLI 兜底：使用 CloudBase CLI 调用 packOps，未安装则优雅失败"""
        try:
            env_id = (self.packops_env_id or 'cloud1-7grjr7usb5d86f59').strip()
            event = {
                'httpMethod': 'POST',
                'path': '/packOps',
                'headers': {
                    'X-API-Key': self.packops_api_key,
                    'Content-Type': 'application/json'
                },
                'queryStringParameters': {
                    'path': path if path.startswith('/') else f'/{path}'
                },
                'body': payload
            }
            args = ['tcb', 'fn', 'invoke', 'packOps', '-e', env_id, '--params', json.dumps(event, ensure_ascii=False)]
            res = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                try:
                    return json.loads(res.stdout.strip())
                except Exception:
                    return {'status': 200, 'text': res.stdout.strip()}
            return {'error': (res.stderr.strip() or res.stdout.strip() or 'CLI 调用失败')}
        except Exception as e:
            return {'error': str(e)}

    # 新增：最近更新的批量推送（带关联合并字段）
    def _sync_recent_components(self):
        try:
            conn = Database(self.db_path).get_connection()
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
            conn = Database(self.db_path).get_connection()
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
            conn = Database(self.db_path).get_connection()
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
            # 新增：一次性推送完成后立即终止当前推送流程，避免循环上传
            try:
                self._log('最近板件/包裹/托盘增量推送已完成，本轮推送流程终止以避免循环上传')
            except Exception:
                pass
            # 安全终止（在工作线程内调用）
            self.stop_sync_service()
        except Exception as e:
            self._log(f"定期检查同步失败: {e}")

    def trigger_sync(self, data_type: str, data: Dict, force: bool = False):
        """手动触发同步（仅在 force=True 时生效）"""
        # 仅允许手动触发，默认忽略所有非手动触发
        if not force:
            self._log(f"忽略非手动触发的同步: {data_type}")
            return
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
        """分片推送，兼容 CLI 兜底场景避免 --params 过大导致失败；带重试退避"""
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
        # 进度初始化
        data_type = 'components' if 'components' in path else ('packages' if 'packages' in path else ('pallets' if 'pallets' in path else 'other'))
        total_chunks = max(1, (len(items) + chunk_size - 1) // chunk_size)
        self._start_progress('upload', data_type, total_chunks)
        results = []
        failed_chunks = 0
        for i in range(0, len(items), chunk_size):
            part = items[i:i + chunk_size]
            part = self._sanitize_items(part)
            # 简单重试：最多3次，指数退避
            attempt = 0
            backoff = 1.0
            last_res = None
            while attempt < 3:
                res = self._post_json(path, {'items': part})
                last_res = res
                # 判断错误：有 error 或 HTTP状态非2xx
                status = res.get('status') if isinstance(res, dict) else None
                if isinstance(res, dict) and ('error' in res):
                    self._log(f"分片推送失败，重试中（{attempt+1}/3）：{res.get('error')}")
                    time.sleep(backoff)
                    backoff *= 2
                    attempt += 1
                elif status and (not str(status).startswith('2')):
                    self._log(f"分片推送HTTP错误{status}，重试中（{attempt+1}/3）")
                    time.sleep(backoff)
                    backoff *= 2
                    attempt += 1
                else:
                    break
            results.append(last_res)
            # 更新进度（按分片推进）
            completed_chunks = len(results)
            # 统计失败分片
            if isinstance(last_res, dict) and (('error' in last_res) or (last_res.get('status') and not str(last_res.get('status')).startswith('2'))):
                failed_chunks += 1
            self._update_progress('upload', data_type, completed_chunks, total_chunks, failed_chunks)
        # 完成进度
        self._finish_progress('upload', data_type, total_chunks, failed_chunks)
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