# 智能分片调整和断点续传模块
# 根据网络环境动态调整分片大小，实现断点续传功能

import os
import json
import time
import hashlib
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import requests
from sync_monitor import get_sync_monitor, TransferMetrics

@dataclass
class TransferState:
    """传输状态记录"""
    transfer_id: str
    operation_type: str  # sync, delete, clear, full_sync
    data_type: str      # component, package, pallet
    total_items: int
    completed_items: int
    failed_items: int
    chunk_size: int
    start_time: float
    last_update: float
    checksum: str
    status: str         # pending, in_progress, completed, failed, paused
    error_message: Optional[str] = None

@dataclass
class ChunkTransferResult:
    """分片传输结果"""
    success: bool
    duration: float
    data_size: int
    error_message: Optional[str] = None
    retry_count: int = 0

class AdaptiveSync:
    def __init__(self, db_path: str = None, state_db_path: str = None):
        self.db_path = db_path or 'packing_system.db'
        self.state_db_path = state_db_path or os.path.join(os.path.dirname(__file__), 'transfer_state.db')
        
        # 获取监控实例
        self.monitor = get_sync_monitor()
        
        # 传输状态管理
        self.active_transfers = {}  # transfer_id -> TransferState
        self.transfer_lock = threading.Lock()
        
        # 网络性能评估
        self.network_metrics = {
            'latency_samples': [],
            'throughput_samples': [],
            'error_rate_samples': [],
            'last_evaluation': 0
        }
        
        # 自适应参数
        self.adaptive_config = {
            'min_chunk_size': 1,
            'max_chunk_size': 1000,
            'initial_chunk_size': 300,
            'adjustment_factor': 0.2,
            'evaluation_interval': 60,  # 秒
            'success_rate_threshold': 0.85,
            'latency_threshold': 5000,  # 毫秒
            'throughput_threshold': 10  # KB/s
        }
        
        self._init_state_database()
        self._load_pending_transfers()

    def _init_state_database(self):
        """初始化传输状态数据库"""
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS transfer_states (
                        transfer_id TEXT PRIMARY KEY,
                        operation_type TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        total_items INTEGER NOT NULL,
                        completed_items INTEGER NOT NULL,
                        failed_items INTEGER NOT NULL,
                        chunk_size INTEGER NOT NULL,
                        start_time REAL NOT NULL,
                        last_update REAL NOT NULL,
                        checksum TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        data_snapshot TEXT
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS chunk_progress (
                        transfer_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_data TEXT NOT NULL,
                        status TEXT NOT NULL,
                        attempts INTEGER DEFAULT 0,
                        last_attempt REAL,
                        error_message TEXT,
                        PRIMARY KEY (transfer_id, chunk_index)
                    )
                ''')
                
                conn.commit()
        except Exception as e:
            print(f"初始化传输状态数据库失败: {e}")

    def _load_pending_transfers(self):
        """加载未完成的传输任务"""
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                cursor = conn.execute('''
                    SELECT * FROM transfer_states 
                    WHERE status IN ('pending', 'in_progress', 'paused')
                ''')
                
                for row in cursor:
                    transfer_state = TransferState(
                        transfer_id=row[0],
                        operation_type=row[1],
                        data_type=row[2],
                        total_items=row[3],
                        completed_items=row[4],
                        failed_items=row[5],
                        chunk_size=row[6],
                        start_time=row[7],
                        last_update=row[8],
                        checksum=row[9],
                        status=row[10],
                        error_message=row[11]
                    )
                    
                    self.active_transfers[transfer_state.transfer_id] = transfer_state
                    print(f"恢复传输任务: {transfer_state.transfer_id}")
        except Exception as e:
            print(f"加载未完成传输任务失败: {e}")

    def start_adaptive_transfer(self, operation_type: str, data_type: str, items: List[Dict]) -> str:
        """开始自适应传输"""
        if not items:
            return ""
        
        # 生成传输ID
        transfer_id = self._generate_transfer_id(operation_type, data_type, items)
        
        # 计算数据校验和
        checksum = self._calculate_checksum(items)
        
        # 获取最优分片大小
        optimal_chunk_size = self._get_optimal_chunk_size(data_type)
        
        # 创建传输状态
        transfer_state = TransferState(
            transfer_id=transfer_id,
            operation_type=operation_type,
            data_type=data_type,
            total_items=len(items),
            completed_items=0,
            failed_items=0,
            chunk_size=optimal_chunk_size,
            start_time=time.time(),
            last_update=time.time(),
            checksum=checksum,
            status='pending'
        )
        
        with self.transfer_lock:
            self.active_transfers[transfer_id] = transfer_state
        
        # 保存到数据库
        self._save_transfer_state(transfer_state, items)
        
        # 开始传输
        threading.Thread(
            target=self._execute_transfer,
            args=(transfer_id, items),
            daemon=True
        ).start()
        
        return transfer_id

    def _generate_transfer_id(self, operation_type: str, data_type: str, items: List[Dict]) -> str:
        """生成传输ID"""
        content = f"{operation_type}_{data_type}_{len(items)}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _calculate_checksum(self, items: List[Dict]) -> str:
        """计算数据校验和"""
        content = json.dumps(items, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_optimal_chunk_size(self, data_type: str) -> int:
        """获取最优分片大小"""
        # 从监控模块获取推荐值
        monitor_recommendation = self.monitor.get_optimal_chunk_size(data_type)
        
        # 结合自适应评估
        current_time = time.time()
        if current_time - self.network_metrics['last_evaluation'] > self.adaptive_config['evaluation_interval']:
            self._evaluate_network_performance()
        
        # 根据网络状况调整
        if self.network_metrics['error_rate_samples']:
            recent_error_rate = sum(self.network_metrics['error_rate_samples'][-10:]) / min(10, len(self.network_metrics['error_rate_samples']))
            if recent_error_rate > (1 - self.adaptive_config['success_rate_threshold']):
                monitor_recommendation = int(monitor_recommendation * 0.7)  # 降低分片大小
        
        if self.network_metrics['latency_samples']:
            recent_latency = sum(self.network_metrics['latency_samples'][-10:]) / min(10, len(self.network_metrics['latency_samples']))
            if recent_latency > self.adaptive_config['latency_threshold']:
                monitor_recommendation = int(monitor_recommendation * 0.8)  # 降低分片大小
        
        # 限制在合理范围内
        return max(
            self.adaptive_config['min_chunk_size'],
            min(monitor_recommendation, self.adaptive_config['max_chunk_size'])
        )

    def _evaluate_network_performance(self):
        """评估网络性能"""
        # 从监控模块获取最近的性能数据
        report = self.monitor.get_performance_report(1)  # 最近1小时
        
        # 更新网络指标
        if report['total_transfers'] > 0:
            error_rate = 1 - report['success_rate']
            self.network_metrics['error_rate_samples'].append(error_rate)
            
            # 估算延迟（基于重试和错误率）
            estimated_latency = error_rate * 2000  # 简化估算
            self.network_metrics['latency_samples'].append(estimated_latency)
            
            # 记录吞吐量
            self.network_metrics['throughput_samples'].append(report['avg_throughput'])
            
            # 保持样本数量在合理范围
            for key in ['error_rate_samples', 'latency_samples', 'throughput_samples']:
                if len(self.network_metrics[key]) > 100:
                    self.network_metrics[key] = self.network_metrics[key][-50:]
        
        self.network_metrics['last_evaluation'] = time.time()

    def _save_transfer_state(self, transfer_state: TransferState, items: List[Dict]):
        """保存传输状态"""
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                # 保存传输状态
                conn.execute('''
                    INSERT OR REPLACE INTO transfer_states
                    (transfer_id, operation_type, data_type, total_items, completed_items,
                     failed_items, chunk_size, start_time, last_update, checksum, status,
                     error_message, data_snapshot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transfer_state.transfer_id, transfer_state.operation_type,
                    transfer_state.data_type, transfer_state.total_items,
                    transfer_state.completed_items, transfer_state.failed_items,
                    transfer_state.chunk_size, transfer_state.start_time,
                    transfer_state.last_update, transfer_state.checksum,
                    transfer_state.status, transfer_state.error_message,
                    json.dumps(items, ensure_ascii=False)
                ))
                
                # 保存分片数据
                chunks = self._split_into_chunks(items, transfer_state.chunk_size)
                for i, chunk in enumerate(chunks):
                    conn.execute('''
                        INSERT OR REPLACE INTO chunk_progress
                        (transfer_id, chunk_index, chunk_data, status, attempts, last_attempt)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        transfer_state.transfer_id, i,
                        json.dumps(chunk, ensure_ascii=False),
                        'pending', 0, None
                    ))
                
                conn.commit()
        except Exception as e:
            print(f"保存传输状态失败: {e}")

    def _split_into_chunks(self, items: List[Dict], chunk_size: int) -> List[List[Dict]]:
        """将数据分割成分片"""
        chunks = []
        for i in range(0, len(items), chunk_size):
            chunks.append(items[i:i + chunk_size])
        return chunks

    def _execute_transfer(self, transfer_id: str, items: List[Dict]):
        """执行传输任务"""
        transfer_state = self.active_transfers.get(transfer_id)
        if not transfer_state:
            return
        
        try:
            # 更新状态为进行中
            transfer_state.status = 'in_progress'
            transfer_state.last_update = time.time()
            self._update_transfer_state(transfer_state)
            
            # 获取未完成的分片
            pending_chunks = self._get_pending_chunks(transfer_id)
            
            for chunk_index, chunk_data in pending_chunks:
                if transfer_state.status == 'paused':
                    break
                
                # 执行分片传输
                result = self._transfer_chunk(
                    transfer_state.operation_type,
                    transfer_state.data_type,
                    chunk_data,
                    chunk_index
                )
                
                # 更新分片状态
                self._update_chunk_status(transfer_id, chunk_index, result)
                
                # 更新传输进度
                if result.success:
                    transfer_state.completed_items += len(chunk_data)
                else:
                    transfer_state.failed_items += len(chunk_data)
                
                transfer_state.last_update = time.time()
                self._update_transfer_state(transfer_state)
                
                # 记录传输指标
                metric = TransferMetrics(
                    timestamp=time.time(),
                    operation_type=transfer_state.operation_type,
                    data_type=transfer_state.data_type,
                    chunk_size=len(chunk_data),
                    success=result.success,
                    duration=result.duration,
                    error_message=result.error_message,
                    retry_count=result.retry_count,
                    data_size=result.data_size
                )
                self.monitor._record_metric(metric)
                
                # 动态调整分片大小
                if self._should_adjust_chunk_size(result, transfer_state):
                    new_chunk_size = self._calculate_new_chunk_size(result, transfer_state)
                    if new_chunk_size != transfer_state.chunk_size:
                        transfer_state.chunk_size = new_chunk_size
                        print(f"调整分片大小: {transfer_state.chunk_size}")
            
            # 检查传输完成状态
            if transfer_state.completed_items + transfer_state.failed_items >= transfer_state.total_items:
                if transfer_state.failed_items == 0:
                    transfer_state.status = 'completed'
                else:
                    transfer_state.status = 'failed'
                    transfer_state.error_message = f"传输失败: {transfer_state.failed_items}/{transfer_state.total_items} 项失败"
            
            self._update_transfer_state(transfer_state)
            
        except Exception as e:
            transfer_state.status = 'failed'
            transfer_state.error_message = str(e)
            self._update_transfer_state(transfer_state)
            print(f"传输执行失败: {e}")

    def _get_pending_chunks(self, transfer_id: str) -> List[Tuple[int, List[Dict]]]:
        """获取未完成的分片"""
        pending_chunks = []
        
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                cursor = conn.execute('''
                    SELECT chunk_index, chunk_data FROM chunk_progress
                    WHERE transfer_id = ? AND status IN ('pending', 'failed')
                    ORDER BY chunk_index
                ''', (transfer_id,))
                
                for row in cursor:
                    chunk_index = row[0]
                    chunk_data = json.loads(row[1])
                    pending_chunks.append((chunk_index, chunk_data))
        except Exception as e:
            print(f"获取未完成分片失败: {e}")
        
        return pending_chunks

    def _transfer_chunk(self, operation_type: str, data_type: str, chunk_data: List[Dict], chunk_index: int) -> ChunkTransferResult:
        """传输单个分片"""
        start_time = time.time()
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # 这里需要调用实际的传输方法
                # 为了演示，我们模拟传输过程
                data_size = len(json.dumps(chunk_data, ensure_ascii=False).encode())
                
                # 模拟网络传输延迟
                time.sleep(0.1 + retry_count * 0.05)
                
                # 模拟成功率（实际应该调用真实的API）
                import random
                if random.random() > 0.1:  # 90%成功率
                    duration = time.time() - start_time
                    return ChunkTransferResult(
                        success=True,
                        duration=duration,
                        data_size=data_size,
                        retry_count=retry_count
                    )
                else:
                    raise Exception("模拟网络错误")
                    
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    duration = time.time() - start_time
                    return ChunkTransferResult(
                        success=False,
                        duration=duration,
                        data_size=0,
                        error_message=str(e),
                        retry_count=retry_count
                    )
                
                # 指数退避
                time.sleep(2 ** retry_count)

    def _update_chunk_status(self, transfer_id: str, chunk_index: int, result: ChunkTransferResult):
        """更新分片状态"""
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                status = 'completed' if result.success else 'failed'
                conn.execute('''
                    UPDATE chunk_progress
                    SET status = ?, attempts = ?, last_attempt = ?, error_message = ?
                    WHERE transfer_id = ? AND chunk_index = ?
                ''', (
                    status, result.retry_count, time.time(),
                    result.error_message, transfer_id, chunk_index
                ))
                conn.commit()
        except Exception as e:
            print(f"更新分片状态失败: {e}")

    def _update_transfer_state(self, transfer_state: TransferState):
        """更新传输状态"""
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                conn.execute('''
                    UPDATE transfer_states
                    SET completed_items = ?, failed_items = ?, chunk_size = ?,
                        last_update = ?, status = ?, error_message = ?
                    WHERE transfer_id = ?
                ''', (
                    transfer_state.completed_items, transfer_state.failed_items,
                    transfer_state.chunk_size, transfer_state.last_update,
                    transfer_state.status, transfer_state.error_message,
                    transfer_state.transfer_id
                ))
                conn.commit()
        except Exception as e:
            print(f"更新传输状态失败: {e}")

    def _should_adjust_chunk_size(self, result: ChunkTransferResult, transfer_state: TransferState) -> bool:
        """判断是否需要调整分片大小"""
        # 如果传输失败且重试次数较多，考虑减小分片
        if not result.success and result.retry_count >= 2:
            return True
        
        # 如果传输成功且速度较快，考虑增大分片
        if result.success and result.duration > 0:
            throughput = result.data_size / result.duration / 1024  # KB/s
            if throughput > 50:  # 高吞吐量
                return True
        
        return False

    def _calculate_new_chunk_size(self, result: ChunkTransferResult, transfer_state: TransferState) -> int:
        """计算新的分片大小"""
        current_size = transfer_state.chunk_size
        adjustment_factor = self.adaptive_config['adjustment_factor']
        
        if not result.success:
            # 传输失败，减小分片大小
            new_size = int(current_size * (1 - adjustment_factor))
        else:
            # 传输成功，根据性能决定是否增大
            if result.duration > 0:
                throughput = result.data_size / result.duration / 1024
                if throughput > 50:
                    new_size = int(current_size * (1 + adjustment_factor))
                else:
                    new_size = current_size
            else:
                new_size = current_size
        
        # 限制在合理范围内
        return max(
            self.adaptive_config['min_chunk_size'],
            min(new_size, self.adaptive_config['max_chunk_size'])
        )

    def pause_transfer(self, transfer_id: str) -> bool:
        """暂停传输"""
        with self.transfer_lock:
            transfer_state = self.active_transfers.get(transfer_id)
            if transfer_state and transfer_state.status == 'in_progress':
                transfer_state.status = 'paused'
                transfer_state.last_update = time.time()
                self._update_transfer_state(transfer_state)
                return True
        return False

    def resume_transfer(self, transfer_id: str) -> bool:
        """恢复传输"""
        with self.transfer_lock:
            transfer_state = self.active_transfers.get(transfer_id)
            if transfer_state and transfer_state.status == 'paused':
                transfer_state.status = 'in_progress'
                transfer_state.last_update = time.time()
                self._update_transfer_state(transfer_state)
                
                # 重新启动传输线程
                threading.Thread(
                    target=self._resume_transfer_execution,
                    args=(transfer_id,),
                    daemon=True
                ).start()
                return True
        return False

    def _resume_transfer_execution(self, transfer_id: str):
        """恢复传输执行"""
        try:
            # 重新加载数据
            with sqlite3.connect(self.state_db_path) as conn:
                cursor = conn.execute('''
                    SELECT data_snapshot FROM transfer_states WHERE transfer_id = ?
                ''', (transfer_id,))
                row = cursor.fetchone()
                if row:
                    items = json.loads(row[0])
                    self._execute_transfer(transfer_id, items)
        except Exception as e:
            print(f"恢复传输执行失败: {e}")

    def get_transfer_status(self, transfer_id: str) -> Optional[Dict]:
        """获取传输状态"""
        transfer_state = self.active_transfers.get(transfer_id)
        if transfer_state:
            progress = 0.0
            if transfer_state.total_items > 0:
                progress = transfer_state.completed_items / transfer_state.total_items
            
            return {
                'transfer_id': transfer_state.transfer_id,
                'operation_type': transfer_state.operation_type,
                'data_type': transfer_state.data_type,
                'progress': progress,
                'completed_items': transfer_state.completed_items,
                'failed_items': transfer_state.failed_items,
                'total_items': transfer_state.total_items,
                'status': transfer_state.status,
                'start_time': transfer_state.start_time,
                'last_update': transfer_state.last_update,
                'error_message': transfer_state.error_message
            }
        return None

    def list_active_transfers(self) -> List[Dict]:
        """列出所有活跃的传输任务"""
        with self.transfer_lock:
            return [self.get_transfer_status(tid) for tid in self.active_transfers.keys()]

    def cleanup_completed_transfers(self, older_than_hours: int = 24):
        """清理已完成的传输记录"""
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        try:
            with sqlite3.connect(self.state_db_path) as conn:
                # 删除旧的已完成传输
                conn.execute('''
                    DELETE FROM transfer_states
                    WHERE status IN ('completed', 'failed') AND last_update < ?
                ''', (cutoff_time,))
                
                # 删除对应的分片记录
                conn.execute('''
                    DELETE FROM chunk_progress
                    WHERE transfer_id NOT IN (SELECT transfer_id FROM transfer_states)
                ''')
                
                conn.commit()
                
                # 从内存中移除
                to_remove = []
                with self.transfer_lock:
                    for tid, state in self.active_transfers.items():
                        if state.status in ['completed', 'failed'] and state.last_update < cutoff_time:
                            to_remove.append(tid)
                    
                    for tid in to_remove:
                        del self.active_transfers[tid]
                
                print(f"清理了 {len(to_remove)} 个已完成的传输记录")
        except Exception as e:
            print(f"清理传输记录失败: {e}")

# 全局自适应同步实例
_adaptive_sync_instance: Optional[AdaptiveSync] = None

def get_adaptive_sync() -> AdaptiveSync:
    """获取全局自适应同步实例"""
    global _adaptive_sync_instance
    if _adaptive_sync_instance is None:
        _adaptive_sync_instance = AdaptiveSync()
    return _adaptive_sync_instance

if __name__ == '__main__':
    # 测试自适应同步功能
    adaptive_sync = AdaptiveSync()
    
    # 模拟传输任务
    test_items = [{'id': i, 'data': f'test_data_{i}'} for i in range(100)]
    
    transfer_id = adaptive_sync.start_adaptive_transfer('sync', 'component', test_items)
    print(f"开始传输: {transfer_id}")
    
    # 监控传输进度
    while True:
        status = adaptive_sync.get_transfer_status(transfer_id)
        if status:
            print(f"传输进度: {status['progress']:.2%}, 状态: {status['status']}")
            if status['status'] in ['completed', 'failed']:
                break
        time.sleep(2)
    
    print("传输完成")