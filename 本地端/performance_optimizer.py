"""
性能优化模块
实现内存优化、网络请求减少、并行传输加速等功能
"""

import asyncio
import aiohttp
import threading
import time
import gc
import psutil
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import logging
from pathlib import Path
import weakref
import sys


@dataclass
class PerformanceMetrics:
    """性能指标"""
    memory_usage_mb: float
    cpu_usage_percent: float
    network_requests_count: int
    parallel_transfers: int
    transfer_speed_mbps: float
    cache_hit_rate: float
    compression_ratio: float
    timestamp: float


@dataclass
class TransferTask:
    """传输任务"""
    task_id: str
    item_type: str
    data: Dict[str, Any]
    chunk_size: int
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3


class MemoryManager:
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 512):
        self.max_memory_mb = max_memory_mb
        self.cache = weakref.WeakValueDictionary()
        self.logger = logging.getLogger('MemoryManager')
        
    def get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
        
    def check_memory_pressure(self) -> bool:
        """检查内存压力"""
        current_usage = self.get_memory_usage()
        return current_usage > self.max_memory_mb * 0.8
        
    def cleanup_memory(self):
        """清理内存"""
        if self.check_memory_pressure():
            self.logger.info("检测到内存压力，开始清理...")
            
            # 清理缓存
            self.cache.clear()
            
            # 强制垃圾回收
            gc.collect()
            
            # 清理大对象
            for obj in gc.get_objects():
                if isinstance(obj, (list, dict)) and sys.getsizeof(obj) > 1024 * 1024:  # 1MB
                    if hasattr(obj, 'clear'):
                        obj.clear()
                        
            self.logger.info(f"内存清理完成，当前使用: {self.get_memory_usage():.2f}MB")
            
    def cache_data(self, key: str, data: Any):
        """缓存数据"""
        if not self.check_memory_pressure():
            self.cache[key] = data
            
    def get_cached_data(self, key: str) -> Any:
        """获取缓存数据"""
        return self.cache.get(key)


class NetworkOptimizer:
    """网络优化器"""
    
    def __init__(self):
        self.request_cache = {}
        self.connection_pool = None
        self.session = None
        self.logger = logging.getLogger('NetworkOptimizer')
        
    async def create_session(self):
        """创建异步HTTP会话"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=100,  # 总连接池大小
                limit_per_host=20,  # 每个主机的连接数
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'OptimizedSyncClient/1.0'}
            )
            
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def cache_request(self, url: str, method: str, data: Any = None) -> Optional[Any]:
        """缓存请求结果"""
        cache_key = f"{method}:{url}:{hash(str(data))}"
        return self.request_cache.get(cache_key)
        
    def store_request_cache(self, url: str, method: str, data: Any, result: Any):
        """存储请求缓存"""
        cache_key = f"{method}:{url}:{hash(str(data))}"
        self.request_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        # 限制缓存大小
        if len(self.request_cache) > 1000:
            # 删除最旧的缓存项
            oldest_key = min(self.request_cache.keys(), 
                           key=lambda k: self.request_cache[k]['timestamp'])
            del self.request_cache[oldest_key]
            
    async def optimized_request(self, url: str, method: str = 'POST', 
                              data: Any = None, use_cache: bool = True) -> Any:
        """优化的网络请求"""
        # 检查缓存
        if use_cache:
            cached = self.cache_request(url, method, data)
            if cached and time.time() - cached['timestamp'] < 300:  # 5分钟缓存
                return cached['result']
                
        # 确保会话存在
        await self.create_session()
        
        try:
            if method.upper() == 'POST':
                async with self.session.post(url, json=data) as response:
                    result = await response.json()
            else:
                async with self.session.get(url) as response:
                    result = await response.json()
                    
            # 存储缓存
            if use_cache:
                self.store_request_cache(url, method, data, result)
                
            return result
            
        except Exception as e:
            self.logger.error(f"网络请求失败: {e}")
            raise


class ParallelTransferManager:
    """并行传输管理器"""
    
    def __init__(self, max_workers: int = 5, max_concurrent_transfers: int = 3):
        self.max_workers = max_workers
        self.max_concurrent_transfers = max_concurrent_transfers
        self.transfer_queue = Queue()
        self.active_transfers = {}
        self.completed_transfers = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger('ParallelTransfer')
        self.running = False
        
    def start(self):
        """启动并行传输管理器"""
        if not self.running:
            self.running = True
            threading.Thread(target=self._transfer_worker, daemon=True).start()
            self.logger.info("并行传输管理器已启动")
            
    def stop(self):
        """停止并行传输管理器"""
        self.running = False
        self.executor.shutdown(wait=True)
        self.logger.info("并行传输管理器已停止")
        
    def add_transfer_task(self, task: TransferTask):
        """添加传输任务"""
        self.transfer_queue.put(task)
        self.logger.info(f"添加传输任务: {task.task_id}")
        
    def _transfer_worker(self):
        """传输工作线程"""
        while self.running:
            try:
                # 检查是否可以启动新的传输
                if len(self.active_transfers) >= self.max_concurrent_transfers:
                    time.sleep(0.1)
                    continue
                    
                # 获取任务
                try:
                    task = self.transfer_queue.get(timeout=1.0)
                except Empty:
                    continue
                    
                # 启动传输
                future = self.executor.submit(self._execute_transfer, task)
                self.active_transfers[task.task_id] = {
                    'task': task,
                    'future': future,
                    'start_time': time.time()
                }
                
                # 清理已完成的传输
                self._cleanup_completed_transfers()
                
            except Exception as e:
                self.logger.error(f"传输工作线程错误: {e}")
                
    def _execute_transfer(self, task: TransferTask) -> bool:
        """执行传输任务"""
        try:
            self.logger.info(f"开始执行传输: {task.task_id}")
            
            # 模拟传输过程
            chunks = self._split_data_to_chunks(task.data, task.chunk_size)
            
            for i, chunk in enumerate(chunks):
                # 模拟网络传输
                time.sleep(0.1)  # 模拟网络延迟
                
                # 检查是否需要重试
                if task.retry_count < task.max_retries:
                    success = self._transfer_chunk(chunk, task.item_type)
                    if not success:
                        task.retry_count += 1
                        self.logger.warning(f"分片传输失败，重试 {task.retry_count}/{task.max_retries}")
                        if task.retry_count >= task.max_retries:
                            raise Exception(f"分片传输失败，已达最大重试次数")
                        continue
                        
            self.logger.info(f"传输完成: {task.task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"传输执行失败: {task.task_id}, 错误: {e}")
            return False
            
    def _split_data_to_chunks(self, data: Dict[str, Any], chunk_size: int) -> List[Dict[str, Any]]:
        """将数据分割为分片"""
        data_str = json.dumps(data, ensure_ascii=False)
        chunks = []
        
        for i in range(0, len(data_str), chunk_size):
            chunk_data = data_str[i:i + chunk_size]
            chunks.append({
                'chunk_index': len(chunks),
                'chunk_data': chunk_data,
                'total_chunks': (len(data_str) + chunk_size - 1) // chunk_size
            })
            
        return chunks
        
    def _transfer_chunk(self, chunk: Dict[str, Any], item_type: str) -> bool:
        """传输单个分片"""
        # 模拟网络传输
        import random
        return random.random() > 0.1  # 90%成功率
        
    def _cleanup_completed_transfers(self):
        """清理已完成的传输"""
        completed_ids = []
        
        for task_id, transfer_info in self.active_transfers.items():
            future = transfer_info['future']
            if future.done():
                completed_ids.append(task_id)
                
                # 记录完成信息
                self.completed_transfers[task_id] = {
                    'task': transfer_info['task'],
                    'success': future.result() if not future.exception() else False,
                    'error': str(future.exception()) if future.exception() else None,
                    'duration': time.time() - transfer_info['start_time']
                }
                
        # 移除已完成的传输
        for task_id in completed_ids:
            del self.active_transfers[task_id]
            
    def get_transfer_status(self) -> Dict[str, Any]:
        """获取传输状态"""
        return {
            'active_transfers': len(self.active_transfers),
            'queued_tasks': self.transfer_queue.qsize(),
            'completed_transfers': len(self.completed_transfers),
            'max_concurrent': self.max_concurrent_transfers
        }


class PerformanceOptimizer:
    """性能优化器主类"""
    
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.network_optimizer = NetworkOptimizer()
        self.parallel_manager = ParallelTransferManager()
        self.metrics_history = []
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('PerformanceOptimizer')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.FileHandler('e:/Trae/021/本地端/performance.log', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def start_optimization(self):
        """启动性能优化"""
        self.logger.info("启动性能优化...")
        self.parallel_manager.start()
        
        # 启动性能监控
        threading.Thread(target=self._performance_monitor, daemon=True).start()
        
    def stop_optimization(self):
        """停止性能优化"""
        self.logger.info("停止性能优化...")
        self.parallel_manager.stop()
        asyncio.run(self.network_optimizer.close_session())
        
    def _performance_monitor(self):
        """性能监控线程"""
        while True:
            try:
                metrics = self.collect_performance_metrics()
                self.metrics_history.append(metrics)
                
                # 保持最近1000条记录
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                    
                # 检查是否需要内存清理
                if metrics.memory_usage_mb > self.memory_manager.max_memory_mb * 0.8:
                    self.memory_manager.cleanup_memory()
                    
                time.sleep(30)  # 每30秒监控一次
                
            except Exception as e:
                self.logger.error(f"性能监控错误: {e}")
                time.sleep(60)
                
    def collect_performance_metrics(self) -> PerformanceMetrics:
        """收集性能指标"""
        process = psutil.Process()
        
        # 内存使用
        memory_usage = process.memory_info().rss / 1024 / 1024
        
        # CPU使用率
        cpu_usage = process.cpu_percent()
        
        # 网络请求数量
        network_requests = len(self.network_optimizer.request_cache)
        
        # 并行传输数量
        parallel_transfers = len(self.parallel_manager.active_transfers)
        
        # 传输速度（模拟）
        transfer_speed = self._calculate_transfer_speed()
        
        # 缓存命中率
        cache_hit_rate = self._calculate_cache_hit_rate()
        
        # 压缩比率（模拟）
        compression_ratio = 0.7  # 假设70%的压缩率
        
        return PerformanceMetrics(
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            network_requests_count=network_requests,
            parallel_transfers=parallel_transfers,
            transfer_speed_mbps=transfer_speed,
            cache_hit_rate=cache_hit_rate,
            compression_ratio=compression_ratio,
            timestamp=time.time()
        )
        
    def _calculate_transfer_speed(self) -> float:
        """计算传输速度"""
        if len(self.metrics_history) < 2:
            return 0.0
            
        # 基于最近的传输活动计算速度
        recent_transfers = len(self.parallel_manager.completed_transfers)
        if recent_transfers > 0:
            return min(recent_transfers * 0.5, 10.0)  # 模拟速度，最大10Mbps
        return 0.0
        
    def _calculate_cache_hit_rate(self) -> float:
        """计算缓存命中率"""
        cache_size = len(self.network_optimizer.request_cache)
        if cache_size == 0:
            return 0.0
        return min(cache_size / 100.0, 1.0)  # 模拟命中率
        
    def optimize_transfer_batch(self, items: List[Dict[str, Any]], item_type: str) -> List[str]:
        """优化批量传输"""
        self.logger.info(f"开始优化批量传输: {len(items)} 个 {item_type} 项目")
        
        task_ids = []
        
        # 根据优先级和大小排序
        sorted_items = sorted(items, key=lambda x: (
            -x.get('priority', 1),  # 优先级高的先传输
            len(str(x))  # 小的项目先传输
        ))
        
        for i, item in enumerate(sorted_items):
            task_id = f"{item_type}_{item.get('id', i)}_{int(time.time())}"
            
            # 动态调整分片大小
            optimal_chunk_size = self._calculate_optimal_chunk_size(item)
            
            task = TransferTask(
                task_id=task_id,
                item_type=item_type,
                data=item,
                chunk_size=optimal_chunk_size,
                priority=item.get('priority', 1)
            )
            
            self.parallel_manager.add_transfer_task(task)
            task_ids.append(task_id)
            
        return task_ids
        
    def _calculate_optimal_chunk_size(self, item: Dict[str, Any]) -> int:
        """计算最优分片大小"""
        item_size = len(json.dumps(item, ensure_ascii=False))
        
        # 基于项目大小和当前网络状况调整分片大小
        if item_size < 1024:  # 小于1KB
            return 512
        elif item_size < 10240:  # 小于10KB
            return 2048
        elif item_size < 102400:  # 小于100KB
            return 8192
        else:
            return 16384
            
    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        if not self.metrics_history:
            return {"error": "暂无性能数据"}
            
        latest_metrics = self.metrics_history[-1]
        
        # 计算平均值
        avg_memory = sum(m.memory_usage_mb for m in self.metrics_history) / len(self.metrics_history)
        avg_cpu = sum(m.cpu_usage_percent for m in self.metrics_history) / len(self.metrics_history)
        avg_speed = sum(m.transfer_speed_mbps for m in self.metrics_history) / len(self.metrics_history)
        
        return {
            "current_metrics": asdict(latest_metrics),
            "averages": {
                "memory_usage_mb": round(avg_memory, 2),
                "cpu_usage_percent": round(avg_cpu, 2),
                "transfer_speed_mbps": round(avg_speed, 2)
            },
            "transfer_status": self.parallel_manager.get_transfer_status(),
            "optimization_suggestions": self._generate_optimization_suggestions(latest_metrics)
        }
        
    def _generate_optimization_suggestions(self, metrics: PerformanceMetrics) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if metrics.memory_usage_mb > 400:
            suggestions.append("内存使用较高，建议减少缓存大小或清理不必要的数据")
            
        if metrics.cpu_usage_percent > 80:
            suggestions.append("CPU使用率较高，建议减少并行传输数量")
            
        if metrics.transfer_speed_mbps < 1.0:
            suggestions.append("传输速度较慢，建议检查网络连接或增加分片大小")
            
        if metrics.cache_hit_rate < 0.3:
            suggestions.append("缓存命中率较低，建议调整缓存策略")
            
        if not suggestions:
            suggestions.append("当前性能表现良好，无需特别优化")
            
        return suggestions


def test_performance_optimizer():
    """测试性能优化器"""
    print("测试性能优化器...")
    
    optimizer = PerformanceOptimizer()
    optimizer.start_optimization()
    
    try:
        # 模拟批量传输
        test_items = [
            {"id": i, "name": f"test_item_{i}", "data": "x" * (i * 100), "priority": i % 3}
            for i in range(10)
        ]
        
        print(f"\n1. 开始批量传输测试...")
        task_ids = optimizer.optimize_transfer_batch(test_items, "component")
        print(f"创建了 {len(task_ids)} 个传输任务")
        
        # 等待一些传输完成
        time.sleep(5)
        
        # 获取优化报告
        print(f"\n2. 性能优化报告:")
        report = optimizer.get_optimization_report()
        
        print(f"当前指标:")
        current = report.get("current_metrics", {})
        print(f"  内存使用: {current.get('memory_usage_mb', 0):.2f} MB")
        print(f"  CPU使用: {current.get('cpu_usage_percent', 0):.2f}%")
        print(f"  传输速度: {current.get('transfer_speed_mbps', 0):.2f} Mbps")
        print(f"  并行传输: {current.get('parallel_transfers', 0)}")
        
        print(f"\n传输状态:")
        status = report.get("transfer_status", {})
        print(f"  活跃传输: {status.get('active_transfers', 0)}")
        print(f"  队列任务: {status.get('queued_tasks', 0)}")
        print(f"  已完成: {status.get('completed_transfers', 0)}")
        
        print(f"\n优化建议:")
        suggestions = report.get("optimization_suggestions", [])
        for suggestion in suggestions:
            print(f"  - {suggestion}")
            
    finally:
        optimizer.stop_optimization()
        print(f"\n性能优化器已停止")


if __name__ == "__main__":
    test_performance_optimizer()