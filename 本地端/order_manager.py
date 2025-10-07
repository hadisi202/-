#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
订单管理器
负责管理订单数据库系统，每个订单对应独立的.db文件
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from database import Database


class OrderManager:
    """订单管理器类"""
    
    def __init__(self, orders_dir: str = "orders"):
        """
        初始化订单管理器
        
        Args:
            orders_dir: 订单数据库文件存储目录
        """
        self.orders_dir = orders_dir
        self.orders_index_file = os.path.join(orders_dir, "orders_index.json")
        self.current_order = None
        self.current_db = None
        
        # 确保订单目录存在
        os.makedirs(orders_dir, exist_ok=True)
        
        # 初始化订单索引
        self._init_orders_index()
    
    def _init_orders_index(self):
        """初始化订单索引文件"""
        if not os.path.exists(self.orders_index_file):
            initial_data = {
                "orders": {},
                "last_updated": datetime.now().isoformat()
            }
            with open(self.orders_index_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    def create_order(self, order_id: str, order_name: str, description: str = "") -> bool:
        """
        创建新订单
        
        Args:
            order_id: 订单ID
            order_name: 订单名称
            description: 订单描述
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 检查订单是否已存在
            if self.order_exists(order_id):
                return False
            
            # 创建订单数据库文件
            db_file = os.path.join(self.orders_dir, f"{order_id}.db")
            
            # 使用Database创建数据库结构
            temp_db = Database(db_file)
            
            # 更新订单索引
            orders_data = self._load_orders_index()
            orders_data["orders"][order_id] = {
                "order_name": order_name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "db_file": db_file,
                "status": "active"
            }
            orders_data["last_updated"] = datetime.now().isoformat()
            
            self._save_orders_index(orders_data)
            return True
            
        except Exception as e:
            print(f"创建订单失败: {e}")
            return False
    
    def delete_order(self, order_id: str) -> bool:
        """
        删除订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.order_exists(order_id):
                return False
            
            # 关闭当前连接（如果是当前订单）
            if self.current_order == order_id:
                self.close_current_order()
            
            # 删除数据库文件
            db_file = os.path.join(self.orders_dir, f"{order_id}.db")
            if os.path.exists(db_file):
                os.remove(db_file)
            
            # 从索引中移除
            orders_data = self._load_orders_index()
            if order_id in orders_data["orders"]:
                del orders_data["orders"][order_id]
                orders_data["last_updated"] = datetime.now().isoformat()
                self._save_orders_index(orders_data)
            
            return True
            
        except Exception as e:
            print(f"删除订单失败: {e}")
            return False
    
    def open_order(self, order_id: str) -> bool:
        """
        打开订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: 打开是否成功
        """
        try:
            if not self.order_exists(order_id):
                return False
            
            # 关闭当前订单
            self.close_current_order()
            
            # 打开新订单
            db_file = os.path.join(self.orders_dir, f"{order_id}.db")
            self.current_db = Database(db_file)
            self.current_order = order_id
            
            # 更新最后访问时间
            orders_data = self._load_orders_index()
            if order_id in orders_data["orders"]:
                orders_data["orders"][order_id]["last_accessed"] = datetime.now().isoformat()
                self._save_orders_index(orders_data)
            
            return True
            
        except Exception as e:
            print(f"打开订单失败: {e}")
            return False
    
    def close_current_order(self):
        """关闭当前订单"""
        self.current_db = None
        self.current_order = None
    
    def get_current_db(self) -> Optional[Database]:
        """获取当前订单的数据库管理器"""
        return self.current_db
    
    def get_current_order_id(self) -> Optional[str]:
        """获取当前订单ID"""
        return self.current_order
    
    def get_order_db_path(self, order_id: str) -> Optional[str]:
        """获取订单对应的数据库文件路径"""
        if not self.order_exists(order_id):
            return None
        return os.path.join(self.orders_dir, f"{order_id}.db")
    
    def order_exists(self, order_id: str) -> bool:
        """检查订单是否存在"""
        orders_data = self._load_orders_index()
        return order_id in orders_data["orders"]
    
    def get_all_orders(self) -> List[Dict[str, Any]]:
        """获取所有订单列表"""
        orders_data = self._load_orders_index()
        orders_list = []
        
        for order_id, order_info in orders_data["orders"].items():
            order_info_copy = order_info.copy()
            order_info_copy["order_id"] = order_id
            orders_list.append(order_info_copy)
        
        # 按创建时间排序
        orders_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return orders_list
    
    def get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """获取订单信息"""
        orders_data = self._load_orders_index()
        if order_id in orders_data["orders"]:
            order_info = orders_data["orders"][order_id].copy()
            order_info["order_id"] = order_id
            return order_info
        return None
    
    def update_order_info(self, order_id: str, order_name: str = None, 
                         description: str = None, status: str = None) -> bool:
        """
        更新订单信息
        
        Args:
            order_id: 订单ID
            order_name: 新的订单名称
            description: 新的订单描述
            status: 新的订单状态
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if not self.order_exists(order_id):
                return False
            
            orders_data = self._load_orders_index()
            order_info = orders_data["orders"][order_id]
            
            if order_name is not None:
                order_info["order_name"] = order_name
            if description is not None:
                order_info["description"] = description
            if status is not None:
                order_info["status"] = status
            
            order_info["updated_at"] = datetime.now().isoformat()
            orders_data["last_updated"] = datetime.now().isoformat()
            
            self._save_orders_index(orders_data)
            return True
            
        except Exception as e:
            print(f"更新订单信息失败: {e}")
            return False
    
    def rename_order_id(self, old_order_id: str, new_order_id: str) -> bool:
        """
        重命名订单号（数据库文件名）
        
        Args:
            old_order_id: 原订单ID
            new_order_id: 新订单ID
            
        Returns:
            bool: 重命名是否成功
        """
        try:
            # 检查原订单是否存在
            if not self.order_exists(old_order_id):
                return False
            
            # 检查新订单ID是否已存在
            if self.order_exists(new_order_id):
                return False
            
            # 关闭当前连接（如果是当前订单）
            if self.current_order == old_order_id:
                self.close_current_order()
            
            # 重命名数据库文件
            old_db_file = os.path.join(self.orders_dir, f"{old_order_id}.db")
            new_db_file = os.path.join(self.orders_dir, f"{new_order_id}.db")
            
            if os.path.exists(old_db_file):
                os.rename(old_db_file, new_db_file)
            
            # 更新索引文件
            orders_data = self._load_orders_index()
            if old_order_id in orders_data["orders"]:
                # 复制订单信息到新ID
                order_info = orders_data["orders"][old_order_id].copy()
                order_info["updated_at"] = datetime.now().isoformat()
                order_info["db_file"] = new_db_file
                
                # 删除旧ID，添加新ID
                del orders_data["orders"][old_order_id]
                orders_data["orders"][new_order_id] = order_info
                orders_data["last_updated"] = datetime.now().isoformat()
                
                self._save_orders_index(orders_data)
            
            return True
            
        except Exception as e:
            print(f"重命名订单ID失败: {e}")
            return False

    def search_orders(self, keyword: str = "") -> List[Dict[str, Any]]:
        """
        搜索订单
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            List[Dict]: 匹配的订单列表
        """
        all_orders = self.get_all_orders()
        
        if not keyword:
            return all_orders
        
        keyword = keyword.lower()
        filtered_orders = []
        
        for order in all_orders:
            if (keyword in order.get("order_id", "").lower() or
                keyword in order.get("order_name", "").lower() or
                keyword in order.get("description", "").lower()):
                filtered_orders.append(order)
        
        return filtered_orders
    
    def get_order_statistics(self, order_id: str) -> Dict[str, Any]:
        """
        获取订单统计信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            Dict: 统计信息
        """
        if not self.order_exists(order_id):
            return {}
        
        # 临时打开订单数据库获取统计信息
        db_file = os.path.join(self.orders_dir, f"{order_id}.db")
        temp_db = Database(db_file)
        
        try:
            # 获取包裹统计
            packages = temp_db.search_packages("")
            package_count = len(packages)
            
            # 获取托盘统计
            trays = temp_db.get_all_trays()
            tray_count = len(trays)
            
            # 按状态统计包裹
            status_stats = {}
            for package in packages:
                status = package.get('status', 'unknown')
                status_stats[status] = status_stats.get(status, 0) + 1
            
            # 按类型统计包裹
            type_stats = {}
            for package in packages:
                pkg_type = package.get('package_type', 'unknown')
                type_stats[pkg_type] = type_stats.get(pkg_type, 0) + 1
            
            return {
                "package_count": package_count,
                "tray_count": tray_count,
                "status_stats": status_stats,
                "type_stats": type_stats
            }
            
        except Exception as e:
            print(f"获取订单统计信息失败: {e}")
            return {}
        finally:
            pass
    
    def _load_orders_index(self) -> Dict[str, Any]:
        """加载订单索引"""
        try:
            with open(self.orders_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载订单索引失败: {e}")
            return {"orders": {}, "last_updated": datetime.now().isoformat()}
    
    def _save_orders_index(self, data: Dict[str, Any]):
        """保存订单索引"""
        try:
            with open(self.orders_index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存订单索引失败: {e}")
    
    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close_current_order()