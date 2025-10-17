#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库初始化脚本
用于创建和初始化测试环境所需的数据库
"""

import sqlite3
import os
from pathlib import Path

def init_sync_monitor_db():
    """初始化同步监控数据库"""
    db_path = "e:/Trae/021/本地端/sync_monitor.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建传输指标表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfer_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                transfer_id TEXT,
                operation_type TEXT,
                data_size INTEGER,
                transfer_speed REAL,
                success_rate REAL,
                error_count INTEGER,
                chunk_size INTEGER,
                network_latency REAL
            )
        ''')
        
        # 创建网络状况表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                bandwidth_mbps REAL,
                latency_ms REAL,
                packet_loss_rate REAL,
                connection_stability REAL,
                optimal_chunk_size INTEGER
            )
        ''')
        
        # 创建传输进度表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfer_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transfer_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                progress_percent REAL,
                bytes_transferred INTEGER,
                total_bytes INTEGER,
                current_speed REAL,
                estimated_time_remaining REAL
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfer_metrics_timestamp ON transfer_metrics(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_network_conditions_timestamp ON network_conditions(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfer_progress_id ON transfer_progress(transfer_id)')
        
        conn.commit()
        conn.close()
        print(f"✓ 同步监控数据库初始化成功: {db_path}")
        return True
        
    except Exception as e:
        print(f"✗ 同步监控数据库初始化失败: {e}")
        return False

def init_adaptive_sync_db():
    """初始化自适应同步数据库"""
    db_path = "e:/Trae/021/本地端/transfer_state.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建传输状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfer_states (
                transfer_id TEXT PRIMARY KEY,
                operation_type TEXT NOT NULL,
                data_type TEXT NOT NULL,
                total_size INTEGER NOT NULL,
                transferred_size INTEGER DEFAULT 0,
                chunk_size INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                checksum TEXT,
                error_message TEXT
            )
        ''')
        
        # 创建分片状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunk_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transfer_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_size INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                checksum TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                completed_at REAL,
                FOREIGN KEY (transfer_id) REFERENCES transfer_states (transfer_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_transfer_states_status ON transfer_states(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunk_states_transfer_id ON chunk_states(transfer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunk_states_status ON chunk_states(status)')
        
        conn.commit()
        conn.close()
        print(f"✓ 自适应同步数据库初始化成功: {db_path}")
        return True
        
    except Exception as e:
        print(f"✗ 自适应同步数据库初始化失败: {e}")
        return False

def init_data_integrity_db():
    """初始化数据完整性数据库"""
    db_path = "e:/Trae/021/本地端/data_integrity.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建校验和表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_checksums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                checksum TEXT NOT NULL,
                algorithm TEXT DEFAULT 'sha256',
                file_size INTEGER,
                created_at REAL NOT NULL,
                verified_at REAL
            )
        ''')
        
        # 创建完整性报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS integrity_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                total_files INTEGER,
                verified_files INTEGER,
                corrupted_files INTEGER,
                missing_files INTEGER,
                integrity_score REAL,
                scan_duration REAL,
                created_at REAL NOT NULL
            )
        ''')
        
        # 创建修复记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repair_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                repair_action TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                created_at REAL NOT NULL,
                details TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_checksums_file_path ON data_checksums(file_path)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_scan_id ON integrity_reports(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repairs_file_path ON repair_records(file_path)')
        
        conn.commit()
        conn.close()
        print(f"✓ 数据完整性数据库初始化成功: {db_path}")
        return True
        
    except Exception as e:
        print(f"✗ 数据完整性数据库初始化失败: {e}")
        return False

def init_performance_optimizer_db():
    """初始化性能优化数据库"""
    db_path = "e:/Trae/021/本地端/performance_optimizer.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建性能指标表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                cpu_usage_percent REAL,
                memory_usage_mb REAL,
                disk_io_mbps REAL,
                network_io_mbps REAL,
                active_transfers INTEGER,
                transfer_speed_mbps REAL
            )
        ''')
        
        # 创建传输任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfer_tasks (
                task_id TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                data_size INTEGER,
                transfer_speed REAL
            )
        ''')
        
        # 创建优化建议表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS optimization_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_type TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                implemented BOOLEAN DEFAULT FALSE,
                created_at REAL NOT NULL
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON transfer_tasks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_suggestions_type ON optimization_suggestions(suggestion_type)')
        
        conn.commit()
        conn.close()
        print(f"✓ 性能优化数据库初始化成功: {db_path}")
        return True
        
    except Exception as e:
        print(f"✗ 性能优化数据库初始化失败: {e}")
        return False

def main():
    """主函数"""
    print("开始初始化测试数据库...")
    
    results = []
    results.append(init_sync_monitor_db())
    results.append(init_adaptive_sync_db())
    results.append(init_data_integrity_db())
    results.append(init_performance_optimizer_db())
    
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n数据库初始化完成: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("✓ 所有数据库初始化成功！")
        return True
    else:
        print("⚠️ 部分数据库初始化失败，请检查错误信息。")
        return False

if __name__ == "__main__":
    main()