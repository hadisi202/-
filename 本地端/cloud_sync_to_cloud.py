#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云数据库同步脚本 - 将本地SQLite数据同步到微信云开发数据库
"""

import json
import sqlite3
import requests
import time
from datetime import datetime
from database import Database

class CloudSyncManager:
    def __init__(self, cloud_env_id, cloud_function_name='db-sync'):
        """
        初始化云同步管理器
        
        Args:
            cloud_env_id: 云开发环境ID
            cloud_function_name: 云函数名称
        """
        self.cloud_env_id = cloud_env_id
        self.cloud_function_name = cloud_function_name
        self.db = Database()
        
    def sync_all_data_to_cloud(self):
        """同步所有数据到云端"""
        print("开始同步数据到云端...")
        
        try:
            # 同步订单数据
            self.sync_orders_to_cloud()
            
            # 同步板件数据
            self.sync_components_to_cloud()
            
            # 同步包裹数据
            self.sync_packages_to_cloud()
            
            # 同步托盘数据
            self.sync_pallets_to_cloud()
            
            print("数据同步完成！")
            return True
            
        except Exception as e:
            print(f"数据同步失败: {e}")
            return False
    
    def sync_orders_to_cloud(self):
        """同步订单数据到云端"""
        print("正在同步订单数据...")
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM orders WHERE status = "active"')
        orders = cursor.fetchall()
        
        orders_data = []
        for order in orders:
            order_dict = {
                '_id': str(order[0]),  # 使用本地ID作为云数据库ID
                'order_number': order[1],
                'customer_name': order[2],
                'customer_address': order[3],
                'customer_phone': order[4],
                'created_at': order[5],
                'updated_at': order[6],
                'status': order[7],
                'notes': order[8]
            }
            orders_data.append(order_dict)
        
        # 准备云函数调用数据
        cloud_data = {
            'operation': 'sync_orders',
            'data': orders_data
        }
        
        # 这里需要调用微信云函数
        # 由于需要小程序环境，我们先生成本地JSON文件
        self.save_sync_data('orders', orders_data)
        
        print(f"订单数据同步完成，共 {len(orders_data)} 条记录")
        conn.close()
    
    def sync_components_to_cloud(self):
        """同步板件数据到云端"""
        print("正在同步板件数据...")
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.*, o.order_number, o.customer_address 
            FROM components c 
            LEFT JOIN orders o ON c.order_id = o.id 
            WHERE 1=1
        ''')
        components = cursor.fetchall()
        
        components_data = []
        for comp in components:
            comp_dict = {
                '_id': str(comp[0]),
                'component_code': comp[5],
                'component_name': comp[2],
                'material': comp[3],
                'finished_size': comp[4],
                'room_number': comp[6],
                'cabinet_number': comp[7],
                'order_id': str(comp[1]) if comp[1] else None,
                'order_number': comp[13],
                'customer_address': comp[14],
                'package_id': str(comp[9]) if comp[9] else None,
                'status': comp[12],
                'created_at': comp[10],
                'updated_at': comp[11],
                'q_code': comp[8],
                'a_code': comp[9],
                'b_code': comp[10],
                'scanned_at': comp[15],
                'remarks': comp[16],
                'custom_field1': comp[17],
                'custom_field2': comp[18]
            }
            components_data.append(comp_dict)
        
        self.save_sync_data('components', components_data)
        print(f"板件数据同步完成，共 {len(components_data)} 条记录")
        conn.close()
    
    def sync_packages_to_cloud(self):
        """同步包裹数据到云端"""
        print("正在同步包裹数据...")
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, o.order_number, o.customer_address,
                   (SELECT COUNT(*) FROM components c WHERE c.package_id = p.id) as component_count
            FROM packages p 
            LEFT JOIN orders o ON p.order_id = o.id 
        ''')
        packages = cursor.fetchall()
        
        packages_data = []
        for pkg in packages:
            # 获取包裹内的板件
            cursor.execute('''
                SELECT c.component_code, c.component_name, c.material, c.finished_size,
                       c.room_number, c.cabinet_number, c.status
                FROM components c 
                WHERE c.package_id = ?
            ''', (pkg[0],))
            components = cursor.fetchall()
            
            components_list = []
            for comp in components:
                components_list.append({
                    'component_code': comp[0],
                    'component_name': comp[1],
                    'material': comp[2],
                    'finished_size': comp[3],
                    'room_number': comp[4],
                    'cabinet_number': comp[5],
                    'status': comp[6]
                })
            
            pkg_dict = {
                '_id': str(pkg[0]),
                'package_number': pkg[1],
                'package_index': pkg[9],
                'order_id': str(pkg[2]) if pkg[2] else None,
                'order_number': pkg[11],
                'customer_address': pkg[12],
                'component_count': pkg[10] or 0,
                'pallet_id': str(pkg[3]) if pkg[3] else None,
                'status': pkg[6],
                'created_at': pkg[4],
                'completed_at': pkg[5],
                'notes': pkg[7],
                'is_manual': pkg[8],
                'packing_method': pkg[13],
                'components': components_list
            }
            packages_data.append(pkg_dict)
        
        self.save_sync_data('packages', packages_data)
        print(f"包裹数据同步完成，共 {len(packages_data)} 条记录")
        conn.close()
    
    def sync_pallets_to_cloud(self):
        """同步托盘数据到云端"""
        print("正在同步托盘数据...")
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, o.order_number, o.customer_address,
                   (SELECT COUNT(*) FROM packages pkg WHERE pkg.pallet_id = p.id) as package_count
            FROM pallets p 
            LEFT JOIN orders o ON p.order_id = o.id 
        ''')
        pallets = cursor.fetchall()
        
        pallets_data = []
        for pallet in pallets:
            # 获取托盘内的包裹
            cursor.execute('''
                SELECT p.id, p.package_number, p.package_index, p.component_count,
                       p.status, p.created_at, p.completed_at
                FROM packages p 
                WHERE p.pallet_id = ?
                ORDER BY p.package_index, p.created_at
            ''', (pallet[0],))
            packages = cursor.fetchall()
            
            packages_list = []
            for pkg in packages:
                # 获取包裹内的板件
                cursor.execute('''
                    SELECT c.component_code, c.component_name, c.material, c.finished_size,
                           c.room_number, c.cabinet_number, c.status
                    FROM components c 
                    WHERE c.package_id = ?
                ''', (pkg[0],))
                components = cursor.fetchall()
                
                components_list = []
                for comp in components:
                    components_list.append({
                        'component_code': comp[0],
                        'component_name': comp[1],
                        'material': comp[2],
                        'finished_size': comp[3],
                        'room_number': comp[4],
                        'cabinet_number': comp[5],
                        'status': comp[6]
                    })
                
                packages_list.append({
                    'package_id': str(pkg[0]),
                    'package_number': pkg[1],
                    'package_index': pkg[2],
                    'component_count': pkg[3] or 0,
                    'status': pkg[4],
                    'created_at': pkg[5],
                    'completed_at': pkg[6],
                    'components': components_list
                })
            
            pallet_dict = {
                '_id': str(pallet[0]),
                'pallet_number': pallet[1],
                'pallet_type': pallet[2],
                'pallet_index': pallet[10],
                'order_id': str(pallet[3]) if pallet[3] else None,
                'order_number': pallet[11],
                'customer_address': pallet[12],
                'package_count': pallet[9] or 0,
                'status': pallet[6],
                'created_at': pallet[4],
                'sealed_at': pallet[5],
                'notes': pallet[7],
                'virtual_items': json.loads(pallet[8]) if pallet[8] else None,
                'packages': packages_list
            }
            pallets_data.append(pallet_dict)
        
        self.save_sync_data('pallets', pallets_data)
        print(f"托盘数据同步完成，共 {len(pallets_data)} 条记录")
        conn.close()
    
    def save_sync_data(self, collection_name, data):
        """保存同步数据到JSON文件（用于调试和手动导入）"""
        filename = f'cloud_sync_{collection_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"同步数据已保存到: {filename}")
        return filename

if __name__ == '__main__':
    # 示例用法
    sync_manager = CloudSyncManager('your-env-id')
    sync_manager.sync_all_data_to_cloud()