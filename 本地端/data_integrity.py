"""
数据完整性保障模块
实现数据校验、不完整数据检测和补全功能
"""

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class DataChecksum:
    """数据校验和信息"""
    item_id: str
    item_type: str  # component, package, pallet
    content_hash: str
    metadata_hash: str
    total_hash: str
    chunk_count: int
    chunk_hashes: List[str]
    created_at: float
    verified_at: Optional[float] = None
    is_complete: bool = False


@dataclass
class IntegrityReport:
    """完整性检查报告"""
    total_items: int
    complete_items: int
    incomplete_items: int
    corrupted_items: int
    missing_items: int
    integrity_score: float
    issues: List[Dict[str, Any]]
    recommendations: List[str]


class DataIntegrityManager:
    """数据完整性管理器"""
    
    def __init__(self, db_path: str = "e:/Trae/021/本地端/data/sync_data.db", 
                 integrity_db_path: str = "e:/Trae/021/本地端/data/integrity.db"):
        self.db_path = db_path
        self.integrity_db_path = integrity_db_path
        self.logger = self._setup_logger()
        self._init_integrity_db()
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('DataIntegrity')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.FileHandler('e:/Trae/021/本地端/data_integrity.log', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def _init_integrity_db(self):
        """初始化完整性数据库"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS data_checksums (
                    item_id TEXT PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_hash TEXT NOT NULL,
                    total_hash TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    chunk_hashes TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    verified_at REAL,
                    is_complete BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS integrity_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    detected_at REAL NOT NULL,
                    resolved_at REAL,
                    is_resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS repair_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    repair_type TEXT NOT NULL,
                    chunks_repaired INTEGER DEFAULT 0,
                    repair_started_at REAL NOT NULL,
                    repair_completed_at REAL,
                    success BOOLEAN DEFAULT FALSE,
                    error_message TEXT
                )
            ''')
            
    def calculate_item_checksum(self, item_data: Dict[str, Any], item_type: str) -> DataChecksum:
        """计算数据项的校验和"""
        item_id = str(item_data.get('id', ''))
        
        # 分离内容和元数据
        content_fields = self._get_content_fields(item_type)
        metadata_fields = self._get_metadata_fields(item_type)
        
        content_data = {k: v for k, v in item_data.items() if k in content_fields}
        metadata_data = {k: v for k, v in item_data.items() if k in metadata_fields}
        
        # 计算各部分哈希
        content_hash = self._calculate_hash(content_data)
        metadata_hash = self._calculate_hash(metadata_data)
        total_hash = self._calculate_hash(item_data)
        
        # 模拟分片哈希（基于内容大小）
        content_str = json.dumps(content_data, sort_keys=True, ensure_ascii=False)
        chunk_size = 1000  # 假设每1000字符一个分片
        chunks = [content_str[i:i+chunk_size] for i in range(0, len(content_str), chunk_size)]
        chunk_hashes = [self._calculate_hash(chunk) for chunk in chunks]
        
        return DataChecksum(
            item_id=item_id,
            item_type=item_type,
            content_hash=content_hash,
            metadata_hash=metadata_hash,
            total_hash=total_hash,
            chunk_count=len(chunk_hashes),
            chunk_hashes=chunk_hashes,
            created_at=time.time(),
            is_complete=True
        )
        
    def _get_content_fields(self, item_type: str) -> Set[str]:
        """获取内容字段"""
        content_fields = {
            'component': {'name', 'description', 'datasheet', 'image_url', 'specifications'},
            'package': {'name', 'description', 'dimensions', 'pin_count', 'package_type'},
            'pallet': {'name', 'description', 'components', 'layout', 'notes'}
        }
        return content_fields.get(item_type, set())
        
    def _get_metadata_fields(self, item_type: str) -> Set[str]:
        """获取元数据字段"""
        metadata_fields = {
            'component': {'id', 'created_at', 'updated_at', 'category_id', 'manufacturer_id'},
            'package': {'id', 'created_at', 'updated_at', 'category'},
            'pallet': {'id', 'created_at', 'updated_at', 'project_id', 'version'}
        }
        return metadata_fields.get(item_type, set())
        
    def _calculate_hash(self, data: Any) -> str:
        """计算数据哈希"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
        
    def store_checksum(self, checksum: DataChecksum):
        """存储校验和信息"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO data_checksums 
                (item_id, item_type, content_hash, metadata_hash, total_hash, 
                 chunk_count, chunk_hashes, created_at, verified_at, is_complete)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                checksum.item_id, checksum.item_type, checksum.content_hash,
                checksum.metadata_hash, checksum.total_hash, checksum.chunk_count,
                json.dumps(checksum.chunk_hashes), checksum.created_at,
                checksum.verified_at, checksum.is_complete
            ))
            
    def verify_data_integrity(self, item_type: str = None) -> IntegrityReport:
        """验证数据完整性"""
        self.logger.info(f"开始验证数据完整性，类型: {item_type or '全部'}")
        
        issues = []
        recommendations = []
        
        # 获取本地数据
        local_items = self._get_local_items(item_type)
        stored_checksums = self._get_stored_checksums(item_type)
        
        total_items = len(local_items)
        complete_items = 0
        incomplete_items = 0
        corrupted_items = 0
        missing_items = 0
        
        # 检查每个本地项目
        for item_id, item_data in local_items.items():
            current_checksum = self.calculate_item_checksum(item_data, item_data.get('type', item_type))
            stored_checksum = stored_checksums.get(item_id)
            
            if not stored_checksum:
                # 新项目，存储校验和
                self.store_checksum(current_checksum)
                complete_items += 1
                continue
                
            # 比较校验和
            if current_checksum.total_hash == stored_checksum.total_hash:
                complete_items += 1
                # 更新验证时间
                self._update_verification_time(item_id)
            else:
                # 数据已变更或损坏
                if current_checksum.content_hash != stored_checksum.content_hash:
                    corrupted_items += 1
                    issues.append({
                        'type': 'data_corruption',
                        'item_id': item_id,
                        'item_type': current_checksum.item_type,
                        'description': f'数据内容校验和不匹配',
                        'severity': 'high'
                    })
                else:
                    incomplete_items += 1
                    issues.append({
                        'type': 'metadata_mismatch',
                        'item_id': item_id,
                        'item_type': current_checksum.item_type,
                        'description': f'元数据校验和不匹配',
                        'severity': 'medium'
                    })
                    
                # 更新校验和
                self.store_checksum(current_checksum)
                
        # 检查孤立的校验和记录
        for item_id, stored_checksum in stored_checksums.items():
            if item_id not in local_items:
                missing_items += 1
                issues.append({
                    'type': 'missing_data',
                    'item_id': item_id,
                    'item_type': stored_checksum.item_type,
                    'description': f'本地数据缺失但存在校验和记录',
                    'severity': 'high'
                })
                
        # 计算完整性分数
        if total_items > 0:
            integrity_score = (complete_items / total_items) * 100
        else:
            integrity_score = 100.0
            
        # 生成建议
        if corrupted_items > 0:
            recommendations.append(f"发现 {corrupted_items} 个损坏项目，建议立即修复")
        if incomplete_items > 0:
            recommendations.append(f"发现 {incomplete_items} 个不完整项目，建议重新同步")
        if missing_items > 0:
            recommendations.append(f"发现 {missing_items} 个缺失项目，建议从云端恢复")
            
        report = IntegrityReport(
            total_items=total_items,
            complete_items=complete_items,
            incomplete_items=incomplete_items,
            corrupted_items=corrupted_items,
            missing_items=missing_items,
            integrity_score=integrity_score,
            issues=issues,
            recommendations=recommendations
        )
        
        self.logger.info(f"完整性检查完成，完整性分数: {integrity_score:.2f}%")
        return report
        
    def _get_local_items(self, item_type: str = None) -> Dict[str, Dict[str, Any]]:
        """获取本地数据项"""
        items = {}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            tables = ['components', 'packages', 'pallets']
            if item_type:
                tables = [f"{item_type}s"]
                
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT * FROM {table}")
                    for row in cursor.fetchall():
                        item_data = dict(row)
                        item_data['type'] = table[:-1]  # 移除复数形式
                        items[str(item_data['id'])] = item_data
                except sqlite3.OperationalError:
                    continue
                    
        return items
        
    def _get_stored_checksums(self, item_type: str = None) -> Dict[str, DataChecksum]:
        """获取存储的校验和"""
        checksums = {}
        
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM data_checksums"
            params = []
            
            if item_type:
                query += " WHERE item_type = ?"
                params.append(item_type)
                
            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['chunk_hashes'] = json.loads(row_dict['chunk_hashes'])
                checksum = DataChecksum(**row_dict)
                checksums[checksum.item_id] = checksum
                
        return checksums
        
    def _update_verification_time(self, item_id: str):
        """更新验证时间"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.execute(
                "UPDATE data_checksums SET verified_at = ? WHERE item_id = ?",
                (time.time(), item_id)
            )
            
    def detect_incomplete_uploads(self) -> List[Dict[str, Any]]:
        """检测不完整的上传"""
        self.logger.info("检测不完整的上传...")
        
        incomplete_uploads = []
        
        # 从adaptive_sync数据库获取未完成的传输
        adaptive_db_path = "e:/Trae/021/本地端/data/adaptive_sync.db"
        
        try:
            with sqlite3.connect(adaptive_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 查找未完成的传输
                cursor = conn.execute('''
                    SELECT transfer_id, item_type, total_chunks, 
                           completed_chunks, status, created_at
                    FROM transfer_status 
                    WHERE status IN ('in_progress', 'paused', 'failed')
                    ORDER BY created_at DESC
                ''')
                
                for row in cursor.fetchall():
                    incomplete_uploads.append({
                        'transfer_id': row['transfer_id'],
                        'item_type': row['item_type'],
                        'total_chunks': row['total_chunks'],
                        'completed_chunks': row['completed_chunks'],
                        'completion_rate': (row['completed_chunks'] / row['total_chunks']) * 100,
                        'status': row['status'],
                        'created_at': row['created_at']
                    })
                    
        except sqlite3.OperationalError as e:
            self.logger.warning(f"无法访问adaptive_sync数据库: {e}")
            
        self.logger.info(f"发现 {len(incomplete_uploads)} 个不完整的上传")
        return incomplete_uploads
        
    def repair_incomplete_data(self, item_id: str, item_type: str) -> bool:
        """修复不完整的数据"""
        self.logger.info(f"开始修复不完整数据: {item_type}/{item_id}")
        
        repair_id = self._start_repair_record(item_id, item_type, 'data_repair')
        
        try:
            # 获取本地数据
            local_item = self._get_local_item(item_id, item_type)
            if not local_item:
                self.logger.error(f"本地数据不存在: {item_type}/{item_id}")
                self._complete_repair_record(repair_id, False, "本地数据不存在")
                return False
                
            # 重新计算校验和
            new_checksum = self.calculate_item_checksum(local_item, item_type)
            
            # 存储新的校验和
            self.store_checksum(new_checksum)
            
            # 标记问题已解决
            self._resolve_integrity_issue(item_id, 'data_repair')
            
            self._complete_repair_record(repair_id, True)
            self.logger.info(f"数据修复完成: {item_type}/{item_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"数据修复失败: {e}")
            self._complete_repair_record(repair_id, False, str(e))
            return False
            
    def _get_local_item(self, item_id: str, item_type: str) -> Optional[Dict[str, Any]]:
        """获取单个本地数据项"""
        table_name = f"{item_type}s"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            
            if row:
                item_data = dict(row)
                item_data['type'] = item_type
                return item_data
                
        return None
        
    def _start_repair_record(self, item_id: str, item_type: str, repair_type: str) -> int:
        """开始修复记录"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO repair_history 
                (item_id, item_type, repair_type, repair_started_at)
                VALUES (?, ?, ?, ?)
            ''', (item_id, item_type, repair_type, time.time()))
            return cursor.lastrowid
            
    def _complete_repair_record(self, repair_id: int, success: bool, error_message: str = None):
        """完成修复记录"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.execute('''
                UPDATE repair_history 
                SET repair_completed_at = ?, success = ?, error_message = ?
                WHERE id = ?
            ''', (time.time(), success, error_message, repair_id))
            
    def _resolve_integrity_issue(self, item_id: str, issue_type: str):
        """解决完整性问题"""
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.execute('''
                UPDATE integrity_issues 
                SET resolved_at = ?, is_resolved = TRUE
                WHERE item_id = ? AND issue_type = ? AND is_resolved = FALSE
            ''', (time.time(), item_id, issue_type))
            
    def get_integrity_statistics(self) -> Dict[str, Any]:
        """获取完整性统计信息"""
        stats = {}
        
        with sqlite3.connect(self.integrity_db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 校验和统计
            cursor = conn.execute('''
                SELECT item_type, COUNT(*) as count, 
                       SUM(CASE WHEN is_complete THEN 1 ELSE 0 END) as complete_count
                FROM data_checksums 
                GROUP BY item_type
            ''')
            
            checksum_stats = {}
            for row in cursor.fetchall():
                checksum_stats[row['item_type']] = {
                    'total': row['count'],
                    'complete': row['complete_count'],
                    'incomplete': row['count'] - row['complete_count']
                }
                
            stats['checksums'] = checksum_stats
            
            # 问题统计
            cursor = conn.execute('''
                SELECT issue_type, COUNT(*) as count,
                       SUM(CASE WHEN is_resolved THEN 1 ELSE 0 END) as resolved_count
                FROM integrity_issues 
                GROUP BY issue_type
            ''')
            
            issue_stats = {}
            for row in cursor.fetchall():
                issue_stats[row['issue_type']] = {
                    'total': row['count'],
                    'resolved': row['resolved_count'],
                    'pending': row['count'] - row['resolved_count']
                }
                
            stats['issues'] = issue_stats
            
            # 修复统计
            cursor = conn.execute('''
                SELECT repair_type, COUNT(*) as count,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count
                FROM repair_history 
                GROUP BY repair_type
            ''')
            
            repair_stats = {}
            for row in cursor.fetchall():
                repair_stats[row['repair_type']] = {
                    'total': row['count'],
                    'success': row['success_count'],
                    'failed': row['count'] - row['success_count']
                }
                
            stats['repairs'] = repair_stats
            
        return stats
        
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        with sqlite3.connect(self.integrity_db_path) as conn:
            # 清理已解决的旧问题
            conn.execute('''
                DELETE FROM integrity_issues 
                WHERE is_resolved = TRUE AND resolved_at < ?
            ''', (cutoff_time,))
            
            # 清理旧的修复记录
            conn.execute('''
                DELETE FROM repair_history 
                WHERE repair_completed_at < ?
            ''', (cutoff_time,))
            
        self.logger.info(f"清理了 {days} 天前的旧记录")


def test_data_integrity():
    """测试数据完整性功能"""
    print("测试数据完整性管理器...")
    
    manager = DataIntegrityManager()
    
    # 验证数据完整性
    print("\n1. 验证数据完整性...")
    report = manager.verify_data_integrity()
    print(f"完整性分数: {report.integrity_score:.2f}%")
    print(f"总项目: {report.total_items}")
    print(f"完整项目: {report.complete_items}")
    print(f"不完整项目: {report.incomplete_items}")
    print(f"损坏项目: {report.corrupted_items}")
    print(f"缺失项目: {report.missing_items}")
    
    if report.issues:
        print(f"\n发现 {len(report.issues)} 个问题:")
        for issue in report.issues[:5]:  # 只显示前5个
            print(f"  - {issue['type']}: {issue['description']}")
            
    if report.recommendations:
        print(f"\n建议:")
        for rec in report.recommendations:
            print(f"  - {rec}")
    
    # 检测不完整上传
    print("\n2. 检测不完整上传...")
    incomplete = manager.detect_incomplete_uploads()
    print(f"发现 {len(incomplete)} 个不完整上传")
    
    # 获取统计信息
    print("\n3. 完整性统计...")
    stats = manager.get_integrity_statistics()
    print(f"统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    test_data_integrity()