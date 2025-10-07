# 本地数据库操作包装器
# 所有数据库操作都会自动触发云同步

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from real_time_cloud_sync import get_sync_service

class CloudEnabledDatabase:
    def __init__(self, db_path: str = 'packing_system.db'):
        self.db_path = db_path
        self.sync_service = get_sync_service(db_path)
        self._init_database()
        
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 板件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_code TEXT UNIQUE NOT NULL,
                component_name TEXT NOT NULL,
                material TEXT,
                finished_size TEXT,
                room_number TEXT,
                cabinet_number TEXT,
                order_id INTEGER,
                order_number TEXT,
                customer_address TEXT,
                package_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                q_code TEXT,
                a_code TEXT,
                b_code TEXT,
                scanned_at TEXT,
                remarks TEXT,
                custom_field1 TEXT,
                custom_field2 TEXT
            )
        ''')
        
        # 包裹表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_number TEXT UNIQUE NOT NULL,
                package_index INTEGER,
                order_id INTEGER,
                order_number TEXT,
                customer_address TEXT,
                component_count INTEGER DEFAULT 0,
                pallet_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                notes TEXT,
                is_manual BOOLEAN DEFAULT 0,
                packing_method TEXT
            )
        ''')
        
        # 托盘表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pallet_number TEXT UNIQUE NOT NULL,
                pallet_type TEXT,
                pallet_index INTEGER,
                order_id INTEGER,
                order_number TEXT,
                customer_address TEXT,
                package_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sealed_at TEXT,
                notes TEXT,
                virtual_items TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def start_cloud_sync(self):
        """启动云同步服务"""
        self.sync_service.start_sync_service()
        
    def stop_cloud_sync(self):
        """停止云同步服务"""
        self.sync_service.stop_sync_service()
        
    def insert_component(self, component_data: Dict) -> int:
        """插入板件数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        component_data['updated_at'] = datetime.now().isoformat()
        
        columns = ', '.join(component_data.keys())
        placeholders = ', '.join(['?' for _ in component_data])
        values = list(component_data.values())
        
        sql = f"INSERT INTO components ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        
        component_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 触发云同步
        component_data['id'] = component_id
        self.sync_service.trigger_sync('component', component_data)
        
        return component_id
        
    def update_component(self, component_code: str, update_data: Dict) -> bool:
        """更新板件数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        update_data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [component_code]
        
        sql = f"UPDATE components SET {set_clause} WHERE component_code = ?"
        cursor.execute(sql, values)
        
        updated = cursor.rowcount > 0
        conn.commit()
        
        # 获取更新后的数据
        if updated:
            cursor.execute("SELECT * FROM components WHERE component_code = ?", (component_code,))
            updated_data = dict(cursor.fetchone())
            conn.close()
            
            # 触发云同步
            self.sync_service.trigger_sync('component', updated_data)
        else:
            conn.close()
            
        return updated
        
    def insert_package(self, package_data: Dict) -> int:
        """插入包裹数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        package_data['updated_at'] = datetime.now().isoformat()
        
        columns = ', '.join(package_data.keys())
        placeholders = ', '.join(['?' for _ in package_data])
        values = list(package_data.values())
        
        sql = f"INSERT INTO packages ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        
        package_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 触发云同步
        package_data['id'] = package_id
        self.sync_service.trigger_sync('package', package_data)
        
        return package_id
        
    def update_package(self, package_number: str, update_data: Dict) -> bool:
        """更新包裹数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        update_data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [package_number]
        
        sql = f"UPDATE packages SET {set_clause} WHERE package_number = ?"
        cursor.execute(sql, values)
        
        updated = cursor.rowcount > 0
        conn.commit()
        
        # 获取更新后的数据
        if updated:
            cursor.execute("SELECT * FROM packages WHERE package_number = ?", (package_number,))
            updated_data = dict(cursor.fetchone())
            conn.close()
            
            # 触发云同步
            self.sync_service.trigger_sync('package', updated_data)
        else:
            conn.close()
            
        return updated
        
    def insert_pallet(self, pallet_data: Dict) -> int:
        """插入托盘数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        pallet_data['updated_at'] = datetime.now().isoformat()
        
        columns = ', '.join(pallet_data.keys())
        placeholders = ', '.join(['?' for _ in pallet_data])
        values = list(pallet_data.values())
        
        sql = f"INSERT INTO pallets ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        
        pallet_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 触发云同步
        pallet_data['id'] = pallet_id
        self.sync_service.trigger_sync('pallet', pallet_data)
        
        return pallet_id
        
    def update_pallet(self, pallet_number: str, update_data: Dict) -> bool:
        """更新托盘数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 添加更新时间
        update_data['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [pallet_number]
        
        sql = f"UPDATE pallets SET {set_clause} WHERE pallet_number = ?"
        cursor.execute(sql, values)
        
        updated = cursor.rowcount > 0
        conn.commit()
        
        # 获取更新后的数据
        if updated:
            cursor.execute("SELECT * FROM pallets WHERE pallet_number = ?", (pallet_number,))
            updated_data = dict(cursor.fetchone())
            conn.close()
            
            # 触发云同步
            self.sync_service.trigger_sync('pallet', updated_data)
        else:
            conn.close()
            
        return updated
        
    def get_component_by_code(self, component_code: str) -> Optional[Dict]:
        """根据编码获取板件"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM components WHERE component_code = ?", (component_code,))
        row = cursor.fetchone()
        
        conn.close()
        
        return dict(row) if row else None
        
    def get_package_by_number(self, package_number: str) -> Optional[Dict]:
        """根据编号获取包裹"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM packages WHERE package_number = ?", (package_number,))
        row = cursor.fetchone()
        
        conn.close()
        
        return dict(row) if row else None
        
    def get_pallet_by_number(self, pallet_number: str):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute('PRAGMA busy_timeout = 5000')
            except Exception:
                pass
            cur.execute("SELECT id, pallet_number, order_id, package_count, status, notes FROM pallets WHERE pallet_number=?", (pallet_number,))
            row = cur.fetchone()
            return row
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_pallet_packages(self, pallet_number: str):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            try:
                cur.execute('PRAGMA busy_timeout = 5000')
            except Exception:
                pass
            cur.execute(
                """
                SELECT pk.id, pk.package_number, pk.component_count, pk.status, pk.notes
                FROM packages AS pk
                JOIN pallets AS p ON pk.pallet_id = p.id
                WHERE p.pallet_number = ?
                ORDER BY pk.id ASC
                """,
                (pallet_number,)
            )
            return cur.fetchall()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    def get_package_components(self, package_id: int) -> List[Dict]:
        """获取包裹内的板件"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM components WHERE package_id = ?", (package_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
        
    def get_pallet_packages(self, pallet_id: int) -> List[Dict]:
        """获取托盘内的包裹"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM packages WHERE pallet_id = ?", (pallet_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]

if __name__ == '__main__':
    # 测试云数据库包装器
    db = CloudEnabledDatabase()
    
    # 启动云同步
    db.start_cloud_sync()
    
    try:
        # 测试插入板件
        component_data = {
            'component_code': 'TEST001',
            'component_name': '测试板件',
            'material': '实木',
            'finished_size': '600x400x18',
            'room_number': '客厅',
            'cabinet_number': 'A01',
            'order_number': 'ORD2025001',
            'customer_address': '测试地址'
        }
        
        component_id = db.insert_component(component_data)
        print(f"插入板件成功: ID={component_id}")
        
        # 测试查询
        component = db.get_component_by_code('TEST001')
        print(f"查询板件: {component}")
        
    except Exception as e:
        print(f"测试失败: {e}")
    finally:
        # 停止云同步
        db.stop_cloud_sync()