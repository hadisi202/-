import sys
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QTableWidget, QTableWidgetItem, QLabel,
                             QLineEdit, QTextEdit, QComboBox, QMessageBox,
                             QDialog, QDialogButtonBox, QGroupBox, QCheckBox,
                             QDateEdit, QTabWidget, QHeaderView, QSplitter,
                             QTreeWidget, QTreeWidgetItem, QApplication)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from database import db

# 统一交互提示助手
class Prompt:
    """集中化的交互提示助手，统一文案与样式。"""

    @staticmethod
    def show_info(message: str, title: str = "提示"):
        QMessageBox.information(None, title, message)

    @staticmethod
    def show_warning(message: str, title: str = "警告"):
        QMessageBox.warning(None, title, message)

    @staticmethod
    def show_error(message: str, title: str = "错误"):
        QMessageBox.critical(None, title, message)

    @staticmethod
    def ask_confirm(message: str, title: str = "确认") -> bool:
        reply = QMessageBox.question(None, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    @staticmethod
    def show_batch_result(title: str, total: int, success: int, failed: list):
        """显示批量操作结果与回滚信息。"""
        if failed:
            details = "\n".join([str(x) for x in failed[:10]])
            more = f"\n... 还有 {len(failed) - 10} 项失败" if len(failed) > 10 else ""
            QMessageBox.warning(None, title, f"共计 {total} 项\n成功: {success}\n失败: {len(failed)}\n\n失败项示例:\n{details}{more}")
        else:
            QMessageBox.information(None, title, f"共计 {total} 项\n全部成功")

class UndoManager:
    """撤销管理器"""
    
    def __init__(self):
        self.undo_stack = []
        self.max_undo_count = 50  # 最大撤销次数
    
    def add_operation(self, operation_type, operation_data, description=""):
        """添加操作到撤销栈"""
        operation = {
            'type': operation_type,
            'data': operation_data,
            'description': description,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.undo_stack.append(operation)
        
        # 限制撤销栈大小
        if len(self.undo_stack) > self.max_undo_count:
            self.undo_stack.pop(0)
    
    def can_undo(self):
        """是否可以撤销"""
        return len(self.undo_stack) > 0
    
    def get_last_operation(self):
        """获取最后一个操作"""
        if self.can_undo():
            return self.undo_stack[-1]
        return None
    
    def undo_last_operation(self):
        """撤销最后一个操作"""
        if not self.can_undo():
            return False, "没有可撤销的操作"
        
        operation = self.undo_stack.pop()
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            if operation['type'] == 'scan_component':
                # 撤销扫描板件
                component_id = operation['data']['component_id']
                cursor.execute('''
                    UPDATE components 
                    SET package_id = NULL, scanned_at = NULL, status = 'pending'
                    WHERE id = ?
                ''', (component_id,))
                
                # 记录操作日志
                db.log_operation('undo_scan', f"撤销扫描板件 ID: {component_id}")
                
            elif operation['type'] == 'finish_package':
                # 撤销完成包装
                package_id = operation['data']['package_id']
                cursor.execute('''
                    UPDATE packages 
                    SET status = 'active', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (package_id,))
                
                # 记录操作日志
                db.log_operation('undo_finish_package', f"撤销完成包装 ID: {package_id}")
                
            elif operation['type'] == 'add_to_pallet':
                # 撤销添加到托盘
                package_id = operation['data']['package_id']
                pallet_id = operation['data']['pallet_id']
                cursor.execute('''
                    DELETE FROM pallet_packages 
                    WHERE package_id = ? AND pallet_id = ?
                ''', (package_id, pallet_id))
                
                # 记录操作日志
                db.log_operation('undo_add_to_pallet', 
                               f"撤销包装 {package_id} 添加到托盘 {pallet_id}")
                
            elif operation['type'] == 'seal_pallet':
                # 撤销封托
                pallet_id = operation['data']['pallet_id']
                cursor.execute('''
                    UPDATE pallets 
                    SET status = 'active', sealed_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (pallet_id,))
                
                # 记录操作日志
                db.log_operation('undo_seal_pallet', f"撤销封托 ID: {pallet_id}")
                
            elif operation['type'] == 'create_package':
                # 撤销创建包装
                package_id = operation['data']['package_id']
                
                # 先将包装内的板件状态重置
                cursor.execute('''
                    UPDATE components 
                    SET package_id = NULL, scanned_at = NULL, status = 'pending'
                    WHERE package_id = ?
                ''', (package_id,))
                
                # 删除包装
                cursor.execute('DELETE FROM packages WHERE id = ?', (package_id,))
                
                # 记录操作日志
                db.log_operation('undo_create_package', f"撤销创建包装 ID: {package_id}")
                
            elif operation['type'] == 'create_pallet':
                # 撤销创建托盘
                pallet_id = operation['data']['pallet_id']
                
                # 删除托盘包装关联
                cursor.execute('DELETE FROM pallet_packages WHERE pallet_id = ?', (pallet_id,))
                
                # 删除虚拟物品
                cursor.execute('DELETE FROM virtual_items WHERE pallet_id = ?', (pallet_id,))
                
                # 删除托盘
                cursor.execute('DELETE FROM pallets WHERE id = ?', (pallet_id,))
                
                # 记录操作日志
                db.log_operation('undo_create_pallet', f"撤销创建托盘 ID: {pallet_id}")
            
            conn.commit()
            conn.close()
            
            return True, f"成功撤销操作: {operation['description']}"
            
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return False, f"撤销操作失败: {str(e)}"
    
    def clear_undo_stack(self):
        """清空撤销栈"""
        self.undo_stack.clear()

# 全局撤销管理器实例
undo_manager = UndoManager()

class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_duplicate_scan(component_code, existing_package_number):
        """处理重复扫描"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("重复扫描")
        msg.setText(f"板件 {component_code} 已经在包装 {existing_package_number} 中")
        msg.setInformativeText("此板件已被扫描，无法重复添加到包装中。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
        # 记录错误日志
        db.log_operation('error_duplicate_scan', 
                        f"重复扫描板件: {component_code}, 已在包装: {existing_package_number}")
    
    @staticmethod
    def handle_invalid_scan(scanned_code):
        """处理无效扫描"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("无效扫描")
        msg.setText(f"扫描的编码 {scanned_code} 不存在")
        msg.setInformativeText("请检查扫描的编码是否正确，或确认该板件是否已导入系统。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
        # 记录错误日志
        db.log_operation('error_invalid_scan', f"无效扫描编码: {scanned_code}")
    
    @staticmethod
    def handle_sealed_pallet_operation(pallet_number):
        """处理已封托盘的操作"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("托盘已封")
        msg.setText(f"托盘 {pallet_number} 已封，无法进行此操作")
        msg.setInformativeText("请先解封托盘，然后再进行操作。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
        # 记录错误日志
        db.log_operation('error_sealed_pallet', f"尝试操作已封托盘: {pallet_number}")
    
    @staticmethod
    def handle_package_modification_error(package_number, error_msg):
        """处理包装修改错误"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("包装修改失败")
        msg.setText(f"修改包装 {package_number} 失败")
        msg.setInformativeText(f"错误信息: {error_msg}")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        
        # 记录错误日志
        db.log_operation('error_package_modification', 
                        f"包装修改失败: {package_number}, 错误: {error_msg}")

class PackageModificationDialog(QDialog):
    """包装修改对话框"""
    
    package_modified = pyqtSignal()
    
    def __init__(self, package_id, parent=None):
        super().__init__(parent)
        self.package_id = package_id
        self.setWindowTitle("修改包装")
        self.setModal(True)
        self.resize(800, 600)
        
        self.init_ui()
        self.load_package_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 包装信息
        info_group = QGroupBox("包装信息")
        info_layout = QGridLayout(info_group)
        
        self.package_number_label = QLabel()
        self.order_number_label = QLabel()
        self.customer_name_label = QLabel()
        self.status_label = QLabel()
        self.created_at_label = QLabel()
        
        info_layout.addWidget(QLabel("包装号:"), 0, 0)
        info_layout.addWidget(self.package_number_label, 0, 1)
        info_layout.addWidget(QLabel("订单号:"), 0, 2)
        info_layout.addWidget(self.order_number_label, 0, 3)
        
        info_layout.addWidget(QLabel("客户名称:"), 1, 0)
        info_layout.addWidget(self.customer_name_label, 1, 1)
        info_layout.addWidget(QLabel("状态:"), 1, 2)
        info_layout.addWidget(self.status_label, 1, 3)
        
        info_layout.addWidget(QLabel("创建时间:"), 2, 0)
        info_layout.addWidget(self.created_at_label, 2, 1, 1, 3)
        
        layout.addWidget(info_group)
        
        # 板件列表
        components_group = QGroupBox("包装内板件")
        components_layout = QVBoxLayout(components_group)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.remove_btn = QPushButton("移除选中板件")
        self.remove_btn.clicked.connect(self.remove_selected_components)
        toolbar_layout.addWidget(self.remove_btn)
        
        self.add_btn = QPushButton("添加板件")
        self.add_btn.clicked.connect(self.add_component)
        toolbar_layout.addWidget(self.add_btn)
        
        toolbar_layout.addStretch()
        
        components_layout.addLayout(toolbar_layout)
        
        # 板件表格
        self.components_table = QTableWidget()
        self.components_table.setColumnCount(7)
        self.components_table.setHorizontalHeaderLabels([
            '板件编码', '板件名称', '材质', '尺寸', '房间号', '柜号', '扫描时间'
        ])
        self.components_table.horizontalHeader().setStretchLastSection(True)
        self.components_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        components_layout.addWidget(self.components_table)
        
        layout.addWidget(components_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存修改")
        self.save_btn.clicked.connect(self.save_modifications)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_package_data(self):
        """加载包装数据"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 加载包装基本信息
        cursor.execute('''
            SELECT p.package_number, p.status, p.created_at,
                   o.order_number, o.customer_name
            FROM packages p
            LEFT JOIN orders o ON p.order_id = o.id
            WHERE p.id = ?
        ''', (self.package_id,))
        
        package_data = cursor.fetchone()
        if package_data:
            self.package_number_label.setText(package_data[0])
            # 中文映射包装状态
            status = package_data[1]
            status_map = {
                'completed': '已完成',
                'open': '进行中',
                'sealed': '已封装',
                'pending': '未打包',
                'packed': '已打包',
            }
            self.status_label.setText(status_map.get(str(status), str(status) if status else '未设置'))
            self.created_at_label.setText(package_data[2])
            self.order_number_label.setText(package_data[3] or '')
            self.customer_name_label.setText(package_data[4] or '')
        
        # 加载包装内板件
        cursor.execute('''
            SELECT id, component_code, component_name, material, dimensions,
                   room_number, cabinet_number, scanned_at
            FROM components
            WHERE package_id = ?
            ORDER BY scanned_at
        ''', (self.package_id,))
        
        components_data = cursor.fetchall()
        
        self.components_table.setRowCount(len(components_data))
        for i, row in enumerate(components_data):
            for j, value in enumerate(row[1:], 0):  # 跳过ID列
                self.components_table.setItem(i, j, QTableWidgetItem(str(value) if value else ''))
            
            # 存储组件ID到表格项的用户数据中
            self.components_table.setItem(i, 0, QTableWidgetItem(str(row[1])))
            self.components_table.item(i, 0).setData(Qt.UserRole, row[0])  # 存储ID
        
        conn.close()
    
    def remove_selected_components(self):
        """移除选中的板件"""
        selected_rows = set()
        for item in self.components_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请选择要移除的板件")
            return
        
        reply = QMessageBox.question(self, "确认", 
                                   f"确定要移除选中的 {len(selected_rows)} 个板件吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                for row in sorted(selected_rows, reverse=True):
                    component_id = self.components_table.item(row, 0).data(Qt.UserRole)
                    
                    # 更新板件状态
                    cursor.execute('''
                        UPDATE components 
                        SET package_id = NULL, scanned_at = NULL, status = 'pending'
                        WHERE id = ?
                    ''', (component_id,))
                    
                    # 记录撤销操作
                    undo_manager.add_operation('scan_component', 
                                             {'component_id': component_id},
                                             f"从包装中移除板件 ID: {component_id}")
                    
                    # 移除表格行
                    self.components_table.removeRow(row)
                
                conn.commit()
                conn.close()
                
                # 记录操作日志
                db.log_operation('modify_package', 
                               f"从包装 {self.package_id} 移除 {len(selected_rows)} 个板件")
                
                QMessageBox.information(self, "成功", "板件移除成功")
                
            except Exception as e:
                if conn:
                    conn.rollback()
                    conn.close()
                ErrorHandler.handle_package_modification_error(
                    self.package_number_label.text(), str(e))
    
    def add_component(self):
        """添加板件"""
        # 这里可以实现添加板件的逻辑
        # 为简化，暂时显示提示信息
        QMessageBox.information(self, "提示", 
                              "添加板件功能可以通过扫描模块实现，请在扫描打包界面操作")
    
    def save_modifications(self):
        """保存修改"""
        try:
            # 更新包装的修改时间
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE packages 
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (self.package_id,))
            
            conn.commit()
            conn.close()
            
            # 记录操作日志
            db.log_operation('modify_package', f"保存包装 {self.package_id} 的修改")
            
            self.package_modified.emit()
            self.accept()
            
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            ErrorHandler.handle_package_modification_error(
                self.package_number_label.text(), str(e))

class ErrorHandling(QWidget):
    """异常处理和撤销功能模块"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.undo_btn = QPushButton("撤销上一步操作")
        self.undo_btn.clicked.connect(self.undo_last_operation)
        toolbar_layout.addWidget(self.undo_btn)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_data)
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.clear_logs_btn = QPushButton("清空日志")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        toolbar_layout.addWidget(self.clear_logs_btn)
        
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # 标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 撤销历史标签页
        self.init_undo_tab()
        
        # 操作日志标签页
        self.init_logs_tab()

        # 已移除：包装修改标签页（不再需要）
    
    def init_undo_tab(self):
        """撤销历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 撤销信息
        info_layout = QHBoxLayout()
        
        self.undo_count_label = QLabel("可撤销操作: 0")
        info_layout.addWidget(self.undo_count_label)
        
        self.last_operation_label = QLabel("最后操作: 无")
        info_layout.addWidget(self.last_operation_label)
        
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        
        # 撤销历史列表
        self.undo_tree = QTreeWidget()
        self.undo_tree.setHeaderLabels(['操作时间', '操作类型', '操作描述'])
        self.undo_tree.header().setStretchLastSection(True)
        
        layout.addWidget(self.undo_tree)
        
        self.tab_widget.addTab(tab, "撤销历史")
    
    def init_logs_tab(self):
        """操作日志标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 过滤器
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("操作类型:"))
        self.log_type_combo = QComboBox()
        self.log_type_combo.addItems(['全部', '扫描', '打包', '托盘', '错误', '撤销'])
        self.log_type_combo.currentTextChanged.connect(self.filter_logs)
        filter_layout.addWidget(self.log_type_combo)
        
        filter_layout.addWidget(QLabel("日期:"))
        self.log_date = QDateEdit()
        self.log_date.setDate(QDate.currentDate())
        self.log_date.setCalendarPopup(True)
        self.log_date.dateChanged.connect(self.filter_logs)
        filter_layout.addWidget(self.log_date)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # 日志表格
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(4)
        self.logs_table.setHorizontalHeaderLabels([
            '时间', '操作类型', '操作描述', '用户'
        ])
        self.logs_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.logs_table)
        
        self.tab_widget.addTab(tab, "操作日志")
    
    def init_package_modification_tab(self):
        """包装修改标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 搜索框
        search_layout = QHBoxLayout()
        
        search_layout.addWidget(QLabel("搜索包装:"))
        self.package_search_edit = QLineEdit()
        self.package_search_edit.setPlaceholderText("输入包装号或订单号...")
        self.package_search_edit.textChanged.connect(self.search_packages)
        search_layout.addWidget(self.package_search_edit)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.search_packages)
        search_layout.addWidget(self.search_btn)
        
        search_layout.addStretch()
        
        layout.addLayout(search_layout)
        
        # 包装列表
        self.packages_table = QTableWidget()
        self.packages_table.setColumnCount(7)
        self.packages_table.setHorizontalHeaderLabels([
            '包装号', '订单号', '客户名称', '板件数量', '状态', '创建时间', '操作'
        ])
        self.packages_table.horizontalHeader().setStretchLastSection(True)
        self.packages_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.packages_table.cellDoubleClicked.connect(self.modify_package)
        
        layout.addWidget(self.packages_table)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.modify_package_btn = QPushButton("修改选中包装")
        self.modify_package_btn.clicked.connect(self.modify_selected_package)
        button_layout.addWidget(self.modify_package_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.tab_widget.addTab(tab, "包装修改")
    
    def load_data(self):
        """加载数据"""
        self.load_undo_history()
        self.load_operation_logs()
        # 不再加载包装列表，已移除包装修改页
    
    def load_undo_history(self):
        """加载撤销历史"""
        self.undo_tree.clear()
        
        # 更新撤销信息
        self.undo_count_label.setText(f"可撤销操作: {len(undo_manager.undo_stack)}")
        
        last_op = undo_manager.get_last_operation()
        if last_op:
            self.last_operation_label.setText(f"最后操作: {last_op['description']}")
            self.undo_btn.setEnabled(True)
        else:
            self.last_operation_label.setText("最后操作: 无")
            self.undo_btn.setEnabled(False)
        
        # 填充撤销历史
        for operation in reversed(undo_manager.undo_stack):
            item = QTreeWidgetItem([
                operation['timestamp'],
                operation['type'],
                operation['description']
            ])
            self.undo_tree.addTopLevelItem(item)
    
    def load_operation_logs(self):
        """加载操作日志"""
        self.filter_logs()
    
    def filter_logs(self):
        """过滤日志"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 构建查询条件
        query = "SELECT created_at, operation_type, operation_data, user_name FROM operation_logs WHERE 1=1"
        params = []
        
        # 按类型过滤
        log_type = self.log_type_combo.currentText()
        if log_type != '全部':
            type_map = {
                '扫描': 'scan%',
                '打包': 'package%',
                '托盘': 'pallet%',
                '错误': 'error%',
                '撤销': 'undo%'
            }
            if log_type in type_map:
                query += " AND operation_type LIKE ?"
                params.append(type_map[log_type])
        
        # 按日期过滤
        selected_date = self.log_date.date().toString('yyyy-MM-dd')
        query += " AND DATE(created_at) = ?"
        params.append(selected_date)
        
        query += " ORDER BY created_at DESC LIMIT 1000"
        
        cursor.execute(query, params)
        logs_data = cursor.fetchall()
        
        self.logs_table.setRowCount(len(logs_data))
        for i, row in enumerate(logs_data):
            for j, value in enumerate(row):
                self.logs_table.setItem(i, j, QTableWidgetItem(str(value) if value else ''))
        
        conn.close()
    
    def load_packages(self):
        """加载包装列表"""
        self.search_packages()
    
    def search_packages(self):
        """搜索包装"""
        search_text = self.package_search_edit.text().strip()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT p.id, p.package_number, o.order_number, o.customer_name,
                   COUNT(c.id) as component_count, p.status, p.created_at
            FROM packages p
            LEFT JOIN orders o ON p.order_id = o.id
            LEFT JOIN components c ON c.package_id = p.id
            WHERE 1=1
        '''
        params = []
        
        if search_text:
            query += " AND (p.package_number LIKE ? OR o.order_number LIKE ?)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])
        
        query += " GROUP BY p.id ORDER BY p.created_at DESC LIMIT 100"
        
        cursor.execute(query, params)
        packages_data = cursor.fetchall()
        
        self.packages_table.setRowCount(len(packages_data))
        for i, row in enumerate(packages_data):
            for j, value in enumerate(row[1:], 0):  # 跳过ID列
                self.packages_table.setItem(i, j, QTableWidgetItem(str(value) if value else ''))
            
            # 存储包装ID
            self.packages_table.setItem(i, 0, QTableWidgetItem(str(row[1])))
            self.packages_table.item(i, 0).setData(Qt.UserRole, row[0])
            
            # 添加修改按钮
            modify_btn = QPushButton("修改")
            modify_btn.clicked.connect(lambda checked, package_id=row[0]: self.modify_package(package_id))
            self.packages_table.setCellWidget(i, 6, modify_btn)
        
        conn.close()
    
    def undo_last_operation(self):
        """撤销最后一个操作"""
        if not undo_manager.can_undo():
            QMessageBox.information(self, "提示", "没有可撤销的操作")
            return
        
        last_op = undo_manager.get_last_operation()
        reply = QMessageBox.question(self, "确认撤销", 
                                   f"确定要撤销操作: {last_op['description']} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = undo_manager.undo_last_operation()
            
            if success:
                QMessageBox.information(self, "成功", message)
                self.load_data()  # 刷新数据
            else:
                QMessageBox.critical(self, "错误", message)
    
    def clear_logs(self):
        """清空日志"""
        reply = QMessageBox.question(self, "确认", 
                                   "确定要清空所有操作日志吗？此操作不可撤销。",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM operation_logs")
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "成功", "操作日志已清空")
                self.load_operation_logs()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空日志失败: {str(e)}")
    
    def modify_selected_package(self):
        """修改选中的包装"""
        current_row = self.packages_table.currentRow()
        if current_row >= 0:
            package_id = self.packages_table.item(current_row, 0).data(Qt.UserRole)
            self.modify_package(package_id)
        else:
            QMessageBox.warning(self, "警告", "请选择要修改的包装")
    
    def modify_package(self, package_id=None):
        """修改包装"""
        if package_id is None:
            # 从双击事件获取包装ID
            current_row = self.packages_table.currentRow()
            if current_row >= 0:
                package_id = self.packages_table.item(current_row, 0).data(Qt.UserRole)
            else:
                return
        
        dialog = PackageModificationDialog(package_id, self)
        dialog.package_modified.connect(self.load_packages)
        dialog.exec_()