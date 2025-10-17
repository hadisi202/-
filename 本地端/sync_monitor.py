# 云同步监控和分析模块
# 实时分析cloud_sync.log，生成传输成功率、速度等关键指标报告

import os
import re
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
import sqlite3
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class TransferMetrics:
    """传输指标数据类"""
    timestamp: float
    operation_type: str  # sync, delete, clear, full_sync
    data_type: str      # component, package, pallet
    chunk_size: int
    success: bool
    duration: float     # 传输耗时（秒）
    error_message: Optional[str] = None
    retry_count: int = 0
    data_size: int = 0  # 数据大小（字节）

@dataclass
class NetworkCondition:
    """网络状况评估"""
    avg_latency: float      # 平均延迟（毫秒）
    success_rate: float     # 成功率
    avg_throughput: float   # 平均吞吐量（KB/s）
    optimal_chunk_size: int # 推荐分片大小
    last_updated: float

class SyncMonitor:
    def __init__(self, log_path: str = None, db_path: str = None):
        self.log_path = log_path or os.path.join(os.path.dirname(__file__), 'cloud_sync.log')
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), 'sync_monitor.db')
        
        # 实时监控数据
        self.recent_metrics = deque(maxlen=1000)  # 最近1000条记录
        self.network_conditions = {}  # 按数据类型存储网络状况
        
        # 监控线程控制
        self.monitoring = False
        self.monitor_thread = None
        self.last_log_position = 0
        
        # 性能统计
        self.performance_stats = {
            'total_transfers': 0,
            'successful_transfers': 0,
            'failed_transfers': 0,
            'total_data_size': 0,
            'total_duration': 0.0,
            'avg_chunk_size': 0,
            'last_reset': time.time()
        }
        
        self._init_database()
        self._load_existing_metrics()

    def _init_database(self):
        """初始化监控数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS transfer_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        operation_type TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        chunk_size INTEGER NOT NULL,
                        success INTEGER NOT NULL,
                        duration REAL NOT NULL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        data_size INTEGER DEFAULT 0
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS network_conditions (
                        data_type TEXT PRIMARY KEY,
                        avg_latency REAL NOT NULL,
                        success_rate REAL NOT NULL,
                        avg_throughput REAL NOT NULL,
                        optimal_chunk_size INTEGER NOT NULL,
                        last_updated REAL NOT NULL
                    )
                ''')
                
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS transfer_progress (
                        transfer_id TEXT PRIMARY KEY,
                        operation_type TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        total_chunks INTEGER NOT NULL,
                        completed_chunks INTEGER NOT NULL,
                        failed_chunks INTEGER NOT NULL,
                        start_time REAL NOT NULL,
                        last_update REAL NOT NULL,
                        status TEXT NOT NULL,
                        checksum TEXT
                    )
                ''')
                
                # 创建索引提升查询性能
                conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON transfer_metrics(timestamp)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_data_type ON transfer_metrics(data_type)')
                conn.commit()
        except Exception as e:
            print(f"初始化监控数据库失败: {e}")

    def _load_existing_metrics(self):
        """加载现有的监控数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 加载最近的传输记录
                cursor = conn.execute('''
                    SELECT * FROM transfer_metrics 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC LIMIT 1000
                ''', (time.time() - 86400,))  # 最近24小时
                
                for row in cursor:
                    metric = TransferMetrics(
                        timestamp=row[1],
                        operation_type=row[2],
                        data_type=row[3],
                        chunk_size=row[4],
                        success=bool(row[5]),
                        duration=row[6],
                        error_message=row[7],
                        retry_count=row[8] or 0,
                        data_size=row[9] or 0
                    )
                    self.recent_metrics.append(metric)
                
                # 加载网络状况
                cursor = conn.execute('SELECT * FROM network_conditions')
                for row in cursor:
                    self.network_conditions[row[0]] = NetworkCondition(
                        avg_latency=row[1],
                        success_rate=row[2],
                        avg_throughput=row[3],
                        optimal_chunk_size=row[4],
                        last_updated=row[5]
                    )
        except Exception as e:
            print(f"加载现有监控数据失败: {e}")

    def start_monitoring(self):
        """开始实时监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("云同步监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("云同步监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._parse_new_log_entries()
                self._update_network_conditions()
                time.sleep(1)  # 每秒检查一次
            except Exception as e:
                print(f"监控循环错误: {e}")
                time.sleep(5)

    def _parse_new_log_entries(self):
        """解析新的日志条目"""
        if not os.path.exists(self.log_path):
            return
        
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                f.seek(self.last_log_position)
                new_lines = f.readlines()
                self.last_log_position = f.tell()
            
            for line in new_lines:
                self._parse_log_line(line.strip())
        except Exception as e:
            print(f"解析日志失败: {e}")

    def _parse_log_line(self, line: str):
        """解析单行日志"""
        if not line:
            return
        
        # 解析时间戳
        timestamp_match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if not timestamp_match:
            return
        
        timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S').timestamp()
        
        # 解析不同类型的日志
        if '分片推送失败' in line:
            self._parse_chunk_failure(line, timestamp)
        elif '分片推送HTTP错误' in line:
            self._parse_http_error(line, timestamp)
        elif '手动触发同步' in line:
            self._parse_manual_sync(line, timestamp)
        elif '全量同步结果' in line:
            self._parse_full_sync_result(line, timestamp)

    def _parse_chunk_failure(self, line: str, timestamp: float):
        """解析分片推送失败"""
        retry_match = re.search(r'重试中（(\d+)/3）', line)
        retry_count = int(retry_match.group(1)) if retry_match else 1
        
        error_match = re.search(r'：(.+)$', line)
        error_message = error_match.group(1) if error_match else "未知错误"
        
        metric = TransferMetrics(
            timestamp=timestamp,
            operation_type='sync',
            data_type='unknown',
            chunk_size=0,
            success=False,
            duration=0.0,
            error_message=error_message,
            retry_count=retry_count
        )
        
        self._record_metric(metric)

    def _parse_http_error(self, line: str, timestamp: float):
        """解析HTTP错误"""
        status_match = re.search(r'HTTP错误(\d+)', line)
        status_code = status_match.group(1) if status_match else "unknown"
        
        metric = TransferMetrics(
            timestamp=timestamp,
            operation_type='sync',
            data_type='unknown',
            chunk_size=0,
            success=False,
            duration=0.0,
            error_message=f"HTTP {status_code}",
            retry_count=1
        )
        
        self._record_metric(metric)

    def _parse_manual_sync(self, line: str, timestamp: float):
        """解析手动同步触发"""
        sync_match = re.search(r'手动触发同步: (\w+) - (\w+)', line)
        if sync_match:
            data_type = sync_match.group(1)
            operation_type = 'sync' if data_type != 'full_sync' else 'full_sync'
            
            metric = TransferMetrics(
                timestamp=timestamp,
                operation_type=operation_type,
                data_type=data_type,
                chunk_size=0,
                success=True,
                duration=0.0
            )
            
            self._record_metric(metric)

    def _parse_full_sync_result(self, line: str, timestamp: float):
        """解析全量同步结果"""
        try:
            result_start = line.find('{')
            if result_start != -1:
                result_json = line[result_start:]
                result_data = json.loads(result_json)
                
                for data_type, result in result_data.items():
                    if isinstance(result, dict) and 'chunks' in result:
                        chunks = result.get('chunks', [])
                        total_chunks = result.get('total_chunks', 0)
                        
                        success_count = sum(1 for chunk in chunks if not chunk.get('error'))
                        
                        metric = TransferMetrics(
                            timestamp=timestamp,
                            operation_type='full_sync',
                            data_type=data_type,
                            chunk_size=total_chunks,
                            success=success_count == total_chunks,
                            duration=0.0,
                            data_size=len(str(result_json))
                        )
                        
                        self._record_metric(metric)
        except Exception as e:
            print(f"解析全量同步结果失败: {e}")

    def _record_metric(self, metric: TransferMetrics):
        """记录传输指标"""
        self.recent_metrics.append(metric)
        
        # 更新性能统计
        self.performance_stats['total_transfers'] += 1
        if metric.success:
            self.performance_stats['successful_transfers'] += 1
        else:
            self.performance_stats['failed_transfers'] += 1
        
        self.performance_stats['total_data_size'] += metric.data_size
        self.performance_stats['total_duration'] += metric.duration
        
        # 保存到数据库
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO transfer_metrics 
                    (timestamp, operation_type, data_type, chunk_size, success, 
                     duration, error_message, retry_count, data_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metric.timestamp, metric.operation_type, metric.data_type,
                    metric.chunk_size, int(metric.success), metric.duration,
                    metric.error_message, metric.retry_count, metric.data_size
                ))
                conn.commit()
        except Exception as e:
            print(f"保存传输指标失败: {e}")

    def _update_network_conditions(self):
        """更新网络状况评估"""
        current_time = time.time()
        
        # 按数据类型分组分析最近的传输记录
        recent_window = current_time - 300  # 最近5分钟
        recent_by_type = defaultdict(list)
        
        for metric in self.recent_metrics:
            if metric.timestamp > recent_window:
                recent_by_type[metric.data_type].append(metric)
        
        for data_type, metrics in recent_by_type.items():
            if len(metrics) < 3:  # 数据不足，跳过
                continue
            
            # 计算成功率
            success_count = sum(1 for m in metrics if m.success)
            success_rate = success_count / len(metrics)
            
            # 计算平均延迟（基于重试次数估算）
            avg_latency = sum(m.retry_count * 1000 for m in metrics) / len(metrics)
            
            # 计算平均吞吐量
            successful_metrics = [m for m in metrics if m.success and m.duration > 0]
            if successful_metrics:
                avg_throughput = sum(m.data_size / m.duration for m in successful_metrics) / len(successful_metrics) / 1024
            else:
                avg_throughput = 0.0
            
            # 推荐分片大小（基于成功率和吞吐量）
            optimal_chunk_size = self._calculate_optimal_chunk_size(success_rate, avg_throughput, data_type)
            
            condition = NetworkCondition(
                avg_latency=avg_latency,
                success_rate=success_rate,
                avg_throughput=avg_throughput,
                optimal_chunk_size=optimal_chunk_size,
                last_updated=current_time
            )
            
            self.network_conditions[data_type] = condition
            
            # 保存到数据库
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT OR REPLACE INTO network_conditions
                        (data_type, avg_latency, success_rate, avg_throughput, 
                         optimal_chunk_size, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        data_type, condition.avg_latency, condition.success_rate,
                        condition.avg_throughput, condition.optimal_chunk_size,
                        condition.last_updated
                    ))
                    conn.commit()
            except Exception as e:
                print(f"保存网络状况失败: {e}")

    def _calculate_optimal_chunk_size(self, success_rate: float, throughput: float, data_type: str) -> int:
        """计算最优分片大小"""
        # 基础分片大小
        base_sizes = {
            'component': 300,
            'package': 300,
            'pallet': 300,
            'full_sync': 100
        }
        
        base_size = base_sizes.get(data_type, 300)
        
        # 根据成功率调整
        if success_rate > 0.95:
            size_factor = 1.5  # 成功率高，增大分片
        elif success_rate > 0.8:
            size_factor = 1.0  # 成功率中等，保持原样
        else:
            size_factor = 0.5  # 成功率低，减小分片
        
        # 根据吞吐量调整
        if throughput > 100:  # KB/s
            size_factor *= 1.2
        elif throughput < 10:
            size_factor *= 0.8
        
        optimal_size = int(base_size * size_factor)
        return max(1, min(optimal_size, 1000))  # 限制在1-1000之间

    def get_performance_report(self, hours: int = 24) -> Dict:
        """生成性能报告"""
        cutoff_time = time.time() - (hours * 3600)
        recent_metrics = [m for m in self.recent_metrics if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {
                'period_hours': hours,
                'total_transfers': 0,
                'success_rate': 0.0,
                'avg_duration': 0.0,
                'total_data_size': 0,
                'avg_throughput': 0.0,
                'error_summary': {},
                'recommendations': []
            }
        
        # 基础统计
        total_transfers = len(recent_metrics)
        successful_transfers = sum(1 for m in recent_metrics if m.success)
        success_rate = successful_transfers / total_transfers
        
        # 平均传输时间
        durations = [m.duration for m in recent_metrics if m.duration > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # 数据大小和吞吐量
        total_data_size = sum(m.data_size for m in recent_metrics)
        total_duration = sum(durations)
        avg_throughput = (total_data_size / total_duration / 1024) if total_duration > 0 else 0.0
        
        # 错误汇总
        error_summary = defaultdict(int)
        for m in recent_metrics:
            if not m.success and m.error_message:
                error_summary[m.error_message] += 1
        
        # 生成建议
        recommendations = self._generate_recommendations(recent_metrics)
        
        return {
            'period_hours': hours,
            'total_transfers': total_transfers,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'total_data_size': total_data_size,
            'avg_throughput': avg_throughput,
            'error_summary': dict(error_summary),
            'recommendations': recommendations,
            'network_conditions': {k: asdict(v) for k, v in self.network_conditions.items()}
        }

    def _generate_recommendations(self, metrics: List[TransferMetrics]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if not metrics:
            return recommendations
        
        success_rate = sum(1 for m in metrics if m.success) / len(metrics)
        
        if success_rate < 0.8:
            recommendations.append("传输成功率较低，建议检查网络连接或减小分片大小")
        
        retry_metrics = [m for m in metrics if m.retry_count > 0]
        if len(retry_metrics) > len(metrics) * 0.3:
            recommendations.append("重试次数较多，建议优化网络环境或调整重试策略")
        
        # 检查分片大小分布
        chunk_sizes = [m.chunk_size for m in metrics if m.chunk_size > 0]
        if chunk_sizes:
            avg_chunk_size = sum(chunk_sizes) / len(chunk_sizes)
            if avg_chunk_size > 500:
                recommendations.append("分片大小较大，可能影响传输稳定性")
            elif avg_chunk_size < 10:
                recommendations.append("分片大小过小，可能影响传输效率")
        
        return recommendations

    def get_optimal_chunk_size(self, data_type: str) -> int:
        """获取指定数据类型的最优分片大小"""
        condition = self.network_conditions.get(data_type)
        if condition and time.time() - condition.last_updated < 600:  # 10分钟内的数据
            return condition.optimal_chunk_size
        
        # 返回默认值
        defaults = {
            'component': 300,
            'package': 300,
            'pallet': 300,
            'full_sync': 100
        }
        return defaults.get(data_type, 300)

# 全局监控实例
_monitor_instance: Optional[SyncMonitor] = None

def get_sync_monitor() -> SyncMonitor:
    """获取全局监控实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SyncMonitor()
        _monitor_instance.start_monitoring()
    return _monitor_instance

if __name__ == '__main__':
    # 测试监控功能
    monitor = SyncMonitor()
    monitor.start_monitoring()
    
    try:
        print("云同步监控测试运行中...")
        print("按 Ctrl+C 停止")
        
        while True:
            time.sleep(10)
            report = monitor.get_performance_report(1)  # 最近1小时
            print(f"\n性能报告: 成功率 {report['success_rate']:.2%}, "
                  f"平均吞吐量 {report['avg_throughput']:.2f} KB/s")
            
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("\n监控已停止")