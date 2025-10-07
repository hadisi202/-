#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QComboBox,
                             QDialog, QDialogButtonBox, QMessageBox, QHeaderView,
                             QLineEdit, QDateEdit, QTextEdit, QSplitter, QFrame,
                             QGroupBox, QGridLayout, QCheckBox, QRadioButton)
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
from database import db
from datetime import datetime
from order_manager import OrderManager
from order_management import OrderSelectionDialog
import traceback
from error_handling import Prompt
from status_utils import package_status_cn, pallet_status_cn, normalize_package_status
try:
    from voice import speak as voice_speak
except Exception:
    def voice_speak(_text: str):
        pass

class PalletManagement(QWidget):
    """托盘管理模块"""
    data_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.order_manager = OrderManager()
        self.current_pallet_id = None
        self.current_order_id = None
        self.current_order_info = None
        # 持久关联改造后不再需要临时集合

        self.init_ui()
        self.load_pallets()
    
    def init_ui(self):
        """初始化界面"""
        layout = QHBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：托盘管理
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        
        # 订单选择组
        order_group = QGroupBox("订单选择")
        order_layout = QVBoxLayout(order_group)
        
        # 当前订单信息
        self.current_order_label = QLabel("当前订单: 未选择")
        self.current_order_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #2c3e50;
                padding: 8px;
                background-color: #ecf0f1;
                border-radius: 4px;
                margin-bottom: 5px;
            }
        """)
        order_layout.addWidget(self.current_order_label)
        
        # 订单操作按钮
        order_btn_layout = QHBoxLayout()
        self.select_order_btn = QPushButton("选择订单")
        self.select_order_btn.clicked.connect(self.select_order)
        order_btn_layout.addWidget(self.select_order_btn)
        
        self.clear_order_btn = QPushButton("清除订单")
        self.clear_order_btn.clicked.connect(self.clear_order_selection)
        self.clear_order_btn.setEnabled(False)
        order_btn_layout.addWidget(self.clear_order_btn)
        
        order_layout.addLayout(order_btn_layout)
        left_layout.addWidget(order_group)
        
        # 包裹扫描组
        scan_group = QGroupBox("包裹扫描")
        scan_layout = QVBoxLayout(scan_group)
        
        # 扫描输入
        scan_input_layout = QHBoxLayout()
        scan_input_layout.addWidget(QLabel("扫描包裹号:"))
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("请扫描或输入包裹号")
        self.scan_input.returnPressed.connect(self.manual_scan)
        self.scan_input.textChanged.connect(self.on_scan_input_changed)
        scan_input_layout.addWidget(self.scan_input)
        
        self.manual_scan_btn = QPushButton("手动添加")
        self.manual_scan_btn.clicked.connect(self.manual_scan)
        self.manual_scan_btn.setEnabled(False)
        scan_input_layout.addWidget(self.manual_scan_btn)
        
        scan_layout.addLayout(scan_input_layout)
        
        # 扫描状态
        self.scan_status_label = QLabel("状态: 等待扫描")
        self.scan_status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        scan_layout.addWidget(self.scan_status_label)
        
        left_layout.addWidget(scan_group)
        
        # 托盘管理组
        tray_group = QGroupBox("托盘管理")
        tray_layout = QVBoxLayout(tray_group)
        
        # 托盘操作按钮
        button_layout = QGridLayout()
        
        self.new_tray_btn = QPushButton("新建托盘")
        self.new_tray_btn.clicked.connect(self.create_pallet)
        self.new_tray_btn.setMaximumHeight(35)  # 缩小按钮高度
        button_layout.addWidget(self.new_tray_btn, 0, 0)
        
        self.delete_tray_btn = QPushButton("删除托盘")
        self.delete_tray_btn.clicked.connect(self.delete_pallet)
        self.delete_tray_btn.setMaximumHeight(26)
        self.delete_tray_btn.setStyleSheet("QPushButton { font-size: 12px; }")
        button_layout.addWidget(self.delete_tray_btn, 0, 1)
        
        self.seal_tray_btn = QPushButton("封托")
        self.seal_tray_btn.clicked.connect(self.seal_pallet)
        self.seal_tray_btn.setMaximumHeight(26)
        self.seal_tray_btn.setStyleSheet("QPushButton { font-size: 12px; }")
        button_layout.addWidget(self.seal_tray_btn, 1, 0)
        
        self.unseal_tray_btn = QPushButton("解托")
        self.unseal_tray_btn.clicked.connect(self.unseal_pallet)
        self.unseal_tray_btn.setMaximumHeight(26)
        self.unseal_tray_btn.setStyleSheet("QPushButton { font-size: 12px; }")
        button_layout.addWidget(self.unseal_tray_btn, 1, 1)
        
        # 添加打印标签按钮
        self.print_label_btn = QPushButton("🖨️ 打印标签")
        self.print_label_btn.clicked.connect(self.print_pallet_label)
        self.print_label_btn.setEnabled(False)  # 默认禁用，需要选择托盘
        self.print_label_btn.setMaximumHeight(26)
        self.print_label_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 12px; }")
        # 编辑托盘按钮
        self.edit_tray_btn = QPushButton("编辑托盘")
        self.edit_tray_btn.setMaximumHeight(26)
        self.edit_tray_btn.setStyleSheet("QPushButton { font-size: 12px; }")
        self.edit_tray_btn.clicked.connect(self.edit_pallet)
        button_layout.addWidget(self.edit_tray_btn, 2, 0)
        button_layout.addWidget(self.print_label_btn, 2, 1)
        
        tray_layout.addLayout(button_layout)
        
        # 托盘列表
        # 新增：托盘搜索工具栏
        tray_toolbar = QHBoxLayout()
        tray_toolbar.addWidget(QLabel("搜索托盘:"))
        self.pallet_search_edit = QLineEdit()
        self.pallet_search_edit.setPlaceholderText("输入托盘号...")
        self.pallet_search_edit.textChanged.connect(self.on_pallets_search_changed)
        tray_toolbar.addWidget(self.pallet_search_edit)
        tray_layout.addLayout(tray_toolbar)
        self.pallets_table = QTableWidget()
        # 增加“序号”列，用于显示托盘序号
        self.pallets_table.setColumnCount(5)
        self.pallets_table.setHorizontalHeaderLabels(['托盘编号', '序号', '类型', '包裹数', '状态'])
        self.pallets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pallets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pallets_table.itemSelectionChanged.connect(self.on_pallet_selected)
        # 设置托盘列表的最小高度
        self.pallets_table.setMinimumHeight(200)
        tray_layout.addWidget(self.pallets_table)

        # 托盘分页工具栏
        tray_pagination = QHBoxLayout()
        self.pallets_prev_btn = QPushButton("上一页")
        self.pallets_next_btn = QPushButton("下一页")
        self.pallets_page_label = QLabel("第 1 / 1 页")
        self.pallets_prev_btn.clicked.connect(self.on_pallets_prev_page)
        self.pallets_next_btn.clicked.connect(self.on_pallets_next_page)
        tray_pagination.addWidget(self.pallets_prev_btn)
        tray_pagination.addWidget(self.pallets_next_btn)
        tray_pagination.addStretch()
        tray_pagination.addWidget(self.pallets_page_label)
        tray_layout.addLayout(tray_pagination)
        
        left_layout.addWidget(tray_group)
        splitter.addWidget(left_frame)
        
        # 右侧：包裹列表和操作面板
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        
        # 包裹列表组
        package_group = QGroupBox("包裹列表")
        package_layout = QVBoxLayout(package_group)
        
        # 包裹列表工具栏
        package_toolbar = QHBoxLayout()
        
        # 显示模式选择
        self.show_all_packages_cb = QCheckBox("显示所有包裹")
        self.show_all_packages_cb.stateChanged.connect(self.on_show_mode_changed)
        package_toolbar.addWidget(self.show_all_packages_cb)
        
        # 新增：显示待打托数量（未入托且已完成的包裹）
        self.pending_to_pallet_label = QLabel("待打托数量: 0")
        self.pending_to_pallet_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        package_toolbar.addWidget(self.pending_to_pallet_label)
        # 初始化一次计数
        try:
            self.update_pending_to_pallet_count()
        except Exception:
            pass
        
        package_toolbar.addStretch()
        
        # 搜索栏
        package_toolbar.addWidget(QLabel("搜索:"))
        self.package_search_edit = QLineEdit()
        self.package_search_edit.setPlaceholderText("输入包裹号搜索...")
        self.package_search_edit.textChanged.connect(self.filter_packages)
        package_toolbar.addWidget(self.package_search_edit)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_data)
        package_toolbar.addWidget(self.refresh_btn)

        # 包裹分页工具栏
        self.packages_prev_btn = QPushButton("上一页")
        self.packages_next_btn = QPushButton("下一页")
        self.packages_page_label = QLabel("第 1 / 1 页")
        self.packages_prev_btn.clicked.connect(self.on_packages_prev_page)
        self.packages_next_btn.clicked.connect(self.on_packages_next_page)
        package_toolbar.addWidget(self.packages_prev_btn)
        package_toolbar.addWidget(self.packages_next_btn)
        package_toolbar.addWidget(self.packages_page_label)
        
        package_layout.addLayout(package_toolbar)
        
        # 包裹表格
        self.packages_table = QTableWidget()
        self.packages_table.setColumnCount(8)
        self.packages_table.setHorizontalHeaderLabels([
            '包裹号', '序号', '类型', '托盘', '状态', '订单号', '创建时间', '操作'
        ])
        self.packages_table.horizontalHeader().setStretchLastSection(True)
        self.packages_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 选中行变化时更新右侧包裹信息
        self.packages_table.itemSelectionChanged.connect(self.update_package_info_from_selection)
        package_layout.addWidget(self.packages_table)
        
        right_layout.addWidget(package_group, 3)  # 给包裹列表分配3份空间
        
        # 托盘信息展示区（紧凑布局，保持信息不减）
        package_info_group = QGroupBox("托盘信息")
        compact_info_layout = QVBoxLayout(package_info_group)
        compact_info_layout.setContentsMargins(6, 4, 6, 4)
        compact_info_layout.setSpacing(4)

        def make_chip(title: str):
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color:#7f8c8d;")
            lbl_value = QLabel("-")
            lbl_value.setStyleSheet("font-weight:bold;color:#2c3e50;")
            box = QHBoxLayout()
            box.setContentsMargins(2, 2, 2, 2)
            box.setSpacing(4)
            box.addWidget(lbl_title)
            box.addWidget(lbl_value)
            frame = QFrame()
            frame.setLayout(box)
            frame.setStyleSheet("QFrame { background:#ecf0f1; border-radius:4px; padding:2px; }")
            return frame, lbl_value

        # 第一行：编号、序号、类型、状态
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        chip_number, self.pkg_info_number = make_chip("编号")
        chip_index, self.pkg_info_index = make_chip("序号")
        chip_type, self.pkg_info_type = make_chip("类型")
        chip_status, self.pkg_info_status = make_chip("状态")
        row1.addWidget(chip_number)
        row1.addWidget(chip_index)
        row1.addWidget(chip_type)
        row1.addWidget(chip_status)
        compact_info_layout.addLayout(row1)

        # 第二行：包裹数、已完成、订单号、创建时间
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        chip_count, self.pkg_info_count = make_chip("包裹数")
        chip_completed, self.pkg_info_completed = make_chip("已完成")
        chip_order, self.pkg_info_order = make_chip("订单号")
        chip_created, self.pkg_info_created = make_chip("创建时间")
        row2.addWidget(chip_count)
        row2.addWidget(chip_completed)
        row2.addWidget(chip_order)
        row2.addWidget(chip_created)
        row2.addStretch()
        compact_info_layout.addLayout(row2)

        # 兼容已有代码：提供不存在的属性以避免错误
        self.pkg_info_pallet = QLabel("")

        right_layout.addWidget(package_info_group, 1)
        
        # 托盘信息显示区域
        tray_info_group = QGroupBox("托盘信息")
        tray_info_layout = QVBoxLayout(tray_info_group)
        
        # 托盘基本信息（紧凑横向信息条）
        info_bar = QHBoxLayout()
        info_bar.setContentsMargins(6, 4, 6, 4)
        info_bar.setSpacing(10)
        def make_label(title):
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color:#7f8c8d;")
            lbl_value = QLabel("-")
            lbl_value.setStyleSheet("font-weight:bold;color:#2c3e50;")
            box = QHBoxLayout()
            box.setSpacing(4)
            box.addWidget(lbl_title)
            box.addWidget(lbl_value)
            wrapper = QHBoxLayout()
            frame = QFrame()
            frame.setLayout(box)
            frame.setStyleSheet("QFrame { background:#ecf0f1; border-radius:4px; padding:4px; }")
            wrapper.addWidget(frame)
            return lbl_value, wrapper

        self.info_number_label, number_box = make_label("编号:")
        self.info_type_label, type_box = make_label("类型:")
        self.info_status_label, status_box = make_label("状态:")
        self.info_count_label, count_box = make_label("包裹数:")
        # 合并到上方紧凑信息区，以下不再添加到布局，避免重复显示
        # info_bar.addLayout(number_box)
        # info_bar.addLayout(type_box)
        # info_bar.addLayout(status_box)
        # info_bar.addLayout(count_box)
        # tray_info_layout.addLayout(info_bar)
        
        # 包裹操作工具栏：移动/删除
        packages_toolbar = QHBoxLayout()
        self.move_package_btn = QPushButton("移动包裹")
        self.move_package_btn.setMaximumHeight(26)
        self.move_package_btn.setStyleSheet("QPushButton { font-size: 12px; }")
        self.move_package_btn.clicked.connect(self.move_packages)
        self.move_package_btn.setEnabled(False)
        packages_toolbar.addWidget(self.move_package_btn)

        self.delete_package_btn = QPushButton("移出托盘")
        self.delete_package_btn.setMaximumHeight(26)
        self.delete_package_btn.setStyleSheet("QPushButton { font-size: 12px; color: #c0392b; }")
        self.delete_package_btn.clicked.connect(self.delete_packages)
        self.delete_package_btn.setEnabled(False)
        packages_toolbar.addWidget(self.delete_package_btn)

        tray_info_layout.addLayout(packages_toolbar)
        
        # 托盘包裹列表
        self.pallet_packages_table = QTableWidget()
        # 增加“包裹序号”列
        self.pallet_packages_table.setColumnCount(6)
        self.pallet_packages_table.setHorizontalHeaderLabels(['包裹号', '包裹序号', '订单号', '板件数', '创建时间', '状态'])
        self.pallet_packages_table.horizontalHeader().setStretchLastSection(True)
        self.pallet_packages_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pallet_packages_table.setAlternatingRowColors(True)
        self.pallet_packages_table.setMinimumHeight(300)
        # 选择变化时根据托盘状态控制按钮可用性
        self.pallet_packages_table.itemSelectionChanged.connect(self.on_pallet_packages_selection_changed)
        tray_info_layout.addWidget(self.pallet_packages_table)
        # 顶部提示标签（紧凑样式）
        self.pallet_info_label = QLabel("")
        self.pallet_info_label.setStyleSheet("color:#7f8c8d;font-size:12px;")
        tray_info_layout.addWidget(self.pallet_info_label)

        right_layout.addWidget(tray_info_group, 4)  # 托盘包裹区域更大
        
        splitter.addWidget(right_frame)
        
        # 设置分割器比例
        splitter.setSizes([400, 600])

        # 右下角时间显示
        bottom_time_bar = QHBoxLayout()
        bottom_time_bar.addStretch()
        self.bottom_time_label = QLabel("")
        self.bottom_time_label.setStyleSheet("color:#7f8c8d;font-size:12px;")
        bottom_time_bar.addWidget(self.bottom_time_label)
        right_layout.addLayout(bottom_time_bar)
        # 启动时钟，每秒刷新
        self.ui_clock_timer = QTimer(self)
        self.ui_clock_timer.timeout.connect(lambda: self.bottom_time_label.setText(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.ui_clock_timer.start(1000)

        # 初始化分页状态
        self.pallets_page = 1
        self.pallets_total_pages = 1
        self.packages_page = 1
        self.packages_total_pages = 1

    @staticmethod
    def format_datetime(value):
        """将时间统一格式化为 YYYY-MM-DD HH:mm:ss"""
        try:
            s = str(value).strip()
            if not s:
                return ""
            # 兼容 ISO 格式
            s = s.replace('T', ' ').replace('Z', '')
            dt = datetime.fromisoformat(s)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(value)

    def update_package_info_from_selection(self):
        """根据包裹列表选中行，更新右侧包裹信息展示"""
        try:
            row = self.packages_table.currentRow()
            if row is None or row < 0:
                self.pkg_info_number.setText("")
                self.pkg_info_index.setText("")
                self.pkg_info_type.setText("标准")
                self.pkg_info_pallet.setText("")
                self.pkg_info_status.setText("")
                self.pkg_info_order.setText("")
                self.pkg_info_created.setText("")
                return

            def item_text(col):
                it = self.packages_table.item(row, col)
                return it.text() if it else ""

            self.pkg_info_number.setText(item_text(0))
            self.pkg_info_index.setText(item_text(1))
            self.pkg_info_type.setText(item_text(2))
            self.pkg_info_pallet.setText(item_text(3))
            self.pkg_info_status.setText(item_text(4))
            self.pkg_info_order.setText(item_text(5))
            self.pkg_info_created.setText(self.format_datetime(item_text(6)))
        except Exception:
            # 静默错误，避免影响操作
            pass
    
    def select_order(self):
        """选择订单"""
        dialog = OrderSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_order = dialog.get_selected_order()
            if selected_order:
                self.current_order_id = selected_order['id']
                self.current_order_info = selected_order
                self.update_order_display()
                self.load_order_packages()
                # 选择订单后，仅显示该订单的托盘
                self.load_pallets()
                self.clear_order_btn.setEnabled(True)
    
    def clear_order_selection(self):
        """清除订单选择"""
        self.current_order_id = None
        self.current_order_info = None
        self.update_order_display()
        self.load_packages()  # 重新加载所有包裹
        # 清除订单后，不显示任何托盘
        self.load_pallets()
        self.clear_order_btn.setEnabled(False)
    
    def update_order_display(self):
        """更新订单显示"""
        if self.current_order_info:
            order_text = f"当前订单: {self.current_order_info['order_number']} - {self.current_order_info['customer_name']}"
            self.current_order_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #27ae60;
                    padding: 8px;
                    background-color: #d5f4e6;
                    border-radius: 4px;
                    margin-bottom: 5px;
                }
            """)
        else:
            order_text = "当前订单: 未选择"
            self.current_order_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #2c3e50;
                    padding: 8px;
                    background-color: #ecf0f1;
                    border-radius: 4px;
                    margin-bottom: 5px;
                }
            """)
        self.current_order_label.setText(order_text)
    
    def on_scan_input_changed(self):
        """扫描输入变化时的处理"""
        text = self.scan_input.text().strip()
        self.manual_scan_btn.setEnabled(len(text) > 0)
    
    def process_scan_input(self):
        """处理扫描输入"""
        package_number = self.scan_input.text().strip()
        if package_number:
            self.add_package_to_pallet(package_number)
    
    def manual_scan(self):
        """手动扫描/添加包裹"""
        package_number = self.scan_input.text().strip()
        if package_number:
            self.add_package_to_pallet(package_number)
            self.scan_input.clear()
    
    def add_package_to_pallet(self, package_number):
        """将包裹添加到托盘（仅允许已封包/已完成的包裹）"""
        if not self.current_pallet_id:
            self.scan_status_label.setText("状态: 请先选择托盘")
            self.scan_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            Prompt.show_warning("请先选择一个托盘")
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 检查包裹是否存在
            cursor.execute('SELECT id, pallet_id, order_id, status FROM packages WHERE package_number = ?', (package_number,))
            package = cursor.fetchone()
            
            if not package:
                self.scan_status_label.setText(f"状态: 包裹 {package_number} 不存在")
                self.scan_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
                Prompt.show_warning(f"包裹 {package_number} 不存在")
                conn.close()
                return
            
            package_id, current_pallet_id, package_order_id, pkg_status = package

            # 未完成封包（open）不允许入托
            if normalize_package_status(pkg_status) == 'open':
                self.scan_status_label.setText(f"状态: 包裹 {package_number} 未封包，不能入托")
                self.scan_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
                Prompt.show_warning(f"包裹 {package_number} 未完成封包，不能入托")
                conn.close()
                return
            # 若为completed，先自动设为sealed
            if normalize_package_status(pkg_status) == 'completed':
                try:
                    cursor.execute('UPDATE packages SET status = ? WHERE id = ?', ('sealed', package_id))
                    conn.commit()
                    pkg_status = 'sealed'
                except Exception:
                    pass
            
            # 检查包裹是否已在其他托盘中
            if current_pallet_id and current_pallet_id != self.current_pallet_id:
                cursor.execute('SELECT pallet_number FROM pallets WHERE id = ?', (current_pallet_id,))
                other_pallet = cursor.fetchone()
                if other_pallet:
                    if not Prompt.ask_confirm(
                        f"包裹 {package_number} 已在托盘 {other_pallet[0]} 中，是否移动到当前托盘？",
                        title="确认"):
                        conn.close()
                        return
            
            # 如果选择了订单，检查包裹是否属于该订单
            if self.current_order_id and package_order_id != self.current_order_id:
                cursor.execute('SELECT order_number FROM orders WHERE id = ?', (package_order_id,))
                package_order = cursor.fetchone()
                order_text = package_order[0] if package_order else "未知订单"
                
                if not Prompt.ask_confirm(
                    f"包裹 {package_number} 属于订单 {order_text}，不是当前选择的订单。是否仍要添加？",
                    title="确认"):
                    conn.close()
                    return
            
            # 更新包裹的托盘ID
            cursor.execute('UPDATE packages SET pallet_id = ? WHERE id = ?', (self.current_pallet_id, package_id))
            conn.commit()
            conn.close()

            # 审计日志
            try:
                db.log_operation('add_to_pallet', f"包裹 {package_number} 入托盘 {self.current_pallet_id}")
            except Exception:
                pass
            
            self.scan_status_label.setText(f"状态: 包裹 {package_number} 添加成功")
            self.scan_status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
            try:
                voice_speak(f"托盘添加包裹成功。包裹号 {package_number}")
            except Exception:
                pass
            
            # 刷新显示
            self.load_pallets()
            # 更新包裹列表区域为显示该订单下剩余包裹
            try:
                self.current_order_id = package_order_id
                self.update_order_display()
                if hasattr(self, 'show_all_packages_cb'):
                    self.show_all_packages_cb.setChecked(False)
                # 重置分页并加载订单包裹
                self.packages_page = 1
                self.load_order_packages()
            except Exception:
                # 兜底：若失败则继续显示当前托盘的包裹
                self.load_packages_for_pallet(self.current_pallet_id)
            
            # 统一刷新并发出跨页信号
            try:
                self.refresh_data()
                self.data_changed.emit()
            except Exception:
                pass
            
        except Exception as e:
            self.scan_status_label.setText(f"状态: 添加失败 - {str(e)}")
            self.scan_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            QMessageBox.critical(self, "错误", f"添加包裹失败：{str(e)}")
            traceback.print_exc()

    def load_pallets(self):
        """加载托盘列表"""
        try:
            # 未选择订单时，不显示任何托盘
            if not getattr(self, 'current_order_id', None):
                self.pallets_table.setRowCount(0)
                return
            conn = db.get_connection()
            cursor = conn.cursor()
            # 每页大小
            try:
                page_size = int(db.get_setting('pallets_page_size', '100'))
            except Exception:
                page_size = 100
            offset = max(0, (getattr(self, 'pallets_page', 1) - 1) * page_size)
            
            # 显示：
            # 1) 该订单的托盘（p.order_id = current_order_id）
            # 2) 包含该订单包裹的托盘（EXISTS 包裹子查询）
            # 统计总数用于分页（支持搜索）
            search_text = (self.pallet_search_edit.text().strip() if hasattr(self, 'pallet_search_edit') else '')
            count_sql = '''
                SELECT COUNT(*)
                FROM pallets p
                WHERE (p.order_id = ?
                   OR EXISTS (
                        SELECT 1 FROM packages pp
                        WHERE pp.pallet_id = p.id AND pp.order_id = ?
                   ))
            '''
            count_params = [self.current_order_id, self.current_order_id]
            if search_text:
                count_sql += ' AND p.pallet_number LIKE ?'
                count_params.append(f'%{search_text}%')
            cursor.execute(count_sql, count_params)
            total = cursor.fetchone()[0] or 0
            self.pallets_total_pages = max(1, (total + page_size - 1) // page_size)

            query = '''
                SELECT p.id, p.pallet_number, p.pallet_type, p.status, p.created_at,
                       COUNT(pkg.id) as package_count, p.pallet_index
                FROM pallets p
                LEFT JOIN packages pkg ON p.id = pkg.pallet_id
                WHERE (p.order_id = ?
                   OR EXISTS (
                        SELECT 1 FROM packages pp
                        WHERE pp.pallet_id = p.id AND pp.order_id = ?
                   ))
            '''
            qparams = [self.current_order_id, self.current_order_id]
            if search_text:
                query += ' AND p.pallet_number LIKE ?'
                qparams.append(f'%{search_text}%')
            query += ' GROUP BY p.id, p.pallet_number, p.pallet_type, p.status, p.created_at, p.pallet_index ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
            qparams.extend([page_size, offset])
            cursor.execute(query, qparams)
            
            pallets = cursor.fetchall()
            conn.close()
            
            self.pallets_table.setRowCount(len(pallets))
            self.update_pallets_page_label()
            
            for row, pallet in enumerate(pallets):
                # 列对应：0托盘编号 | 1序号 | 2类型 | 3包裹数 | 4状态
                self.pallets_table.setItem(row, 0, QTableWidgetItem(str(pallet[1])))  # pallet_number

                # 序号（pallet_index）
                seq_text = ''
                try:
                    seq_text = str(pallet[6]) if len(pallet) > 6 and pallet[6] is not None else ''
                except Exception:
                    seq_text = ''
                self.pallets_table.setItem(row, 1, QTableWidgetItem(seq_text))  # 序号

                # 托盘类型中文
                pallet_type_text = ""
                if pallet[2] == "physical":
                    pallet_type_text = "实体托盘"
                elif pallet[2] == "virtual":
                    pallet_type_text = "虚拟托盘"
                else:
                    pallet_type_text = str(pallet[2])
                self.pallets_table.setItem(row, 2, QTableWidgetItem(pallet_type_text))  # 类型

                # 包裹数
                self.pallets_table.setItem(row, 3, QTableWidgetItem(str(pallet[5])))  # 包裹数

                # 状态中文（容量列已移除，状态改为第4列）
                status_text = ""
                status_text = pallet_status_cn(pallet[3])
                self.pallets_table.setItem(row, 4, QTableWidgetItem(status_text))  # 状态
                
                # 存储托盘ID用于后续操作
                self.pallets_table.item(row, 0).setData(Qt.UserRole, pallet[0])
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载托盘列表失败：{str(e)}")
            traceback.print_exc()
    
    def on_pallet_selected(self):
        """托盘选择事件"""
        current_row = self.pallets_table.currentRow()
        if current_row >= 0:
            pallet_id = self.pallets_table.item(current_row, 0).data(Qt.UserRole)
            self.current_pallet_id = pallet_id
            self.update_pallet_info_display()
            # 同步上方托盘信息面板
            self.update_selected_pallet_info_panel()
            # 启用打印/编辑按钮
            self.print_label_btn.setEnabled(True)
            # 启用编辑托盘按钮
            if hasattr(self, 'edit_tray_btn'):
                self.edit_tray_btn.setEnabled(True)
            # 根据托盘状态控制包裹操作
            status_item = self.pallets_table.item(current_row, 4)
            status_text = status_item.text() if status_item else ''
            is_sealed = status_text in ("已封托", "已关闭")
            if hasattr(self, 'move_package_btn'):
                self.move_package_btn.setEnabled(not is_sealed)
            if hasattr(self, 'delete_package_btn'):
                has_selection = len(self._get_selected_package_numbers()) > 0
                self.delete_package_btn.setEnabled(has_selection)
        else:
            self.current_pallet_id = None
            self.pallet_info_label.setText("请选择托盘查看详细信息")
            self.pallet_packages_table.setRowCount(0)
            # 禁用打印标签按钮
            self.print_label_btn.setEnabled(False)
            # 禁用编辑托盘按钮
            if hasattr(self, 'edit_tray_btn'):
                self.edit_tray_btn.setEnabled(False)
            # 禁用包裹操作按钮
            if hasattr(self, 'move_package_btn'):
                self.move_package_btn.setEnabled(False)
            if hasattr(self, 'delete_package_btn'):
                self.delete_package_btn.setEnabled(False)

    def _get_selected_package_numbers(self):
        """获取包裹列表中选中的包裹号集合"""
        rows = sorted({idx.row() for idx in self.pallet_packages_table.selectedIndexes()})
        numbers = []
        for r in rows:
            it = self.pallet_packages_table.item(r, 0)
            if it and it.text():
                numbers.append(it.text())
        return numbers

    def on_pallet_packages_selection_changed(self):
        """当托盘包裹表选择变化时，依据托盘状态更新按钮可用性"""
        try:
            has_selection = len(self._get_selected_package_numbers()) > 0
            is_sealed = False
            if self.current_pallet_id:
                conn = db.get_connection()
                cur = conn.cursor()
                cur.execute('SELECT status FROM pallets WHERE id = ?', (self.current_pallet_id,))
                r = cur.fetchone()
                conn.close()
                if r and r[0] in ('sealed', 'closed'):
                    is_sealed = True
            if hasattr(self, 'move_package_btn'):
                self.move_package_btn.setEnabled(has_selection and not is_sealed)
            if hasattr(self, 'delete_package_btn'):
                self.delete_package_btn.setEnabled(has_selection)
        except Exception:
            # 静默失败，避免影响用户操作
            pass

    def move_packages(self):
        """将选中的包裹移动到目标托盘（支持搜索与跨订单）"""
        try:
            if not self.current_pallet_id:
                QMessageBox.information(self, "提示", "请先选择托盘")
                return
            # 检查托盘状态
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute('SELECT status, order_id FROM pallets WHERE id = ?', (self.current_pallet_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                QMessageBox.critical(self, "错误", "未找到当前托盘")
                return
            status, order_id = row
            if status in ('sealed', 'closed'):
                conn.close()
                QMessageBox.information(self, "提示", "封托或关闭后不可操作包裹")
                return

            numbers = self._get_selected_package_numbers()
            if not numbers:
                conn.close()
                QMessageBox.information(self, "提示", "请在托盘内选择要移动的包裹")
                return

            # 选择目标托盘（支持搜索与是否仅同订单）
            dlg = QDialog(self)
            dlg.setWindowTitle("移动包裹到托盘")
            gl = QGridLayout(dlg)

            only_same_order = QCheckBox("仅同订单")
            only_same_order.setChecked(True)
            gl.addWidget(only_same_order, 0, 0)

            search_edit = QLineEdit()
            search_edit.setPlaceholderText("搜索托盘号或订单号...")
            gl.addWidget(search_edit, 0, 1)

            gl.addWidget(QLabel("目标托盘"), 1, 0)
            target_combo = QComboBox()
            gl.addWidget(target_combo, 1, 1)

            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            gl.addWidget(btns, 2, 0, 1, 2)

            def refresh_candidates():
                target_combo.clear()
                text = search_edit.text().strip()
                base_sql = """
                    SELECT p.id, p.pallet_number, o.order_number
                    FROM pallets p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.status = 'open' AND p.id <> ?
                """
                params = [self.current_pallet_id]
                if only_same_order.isChecked():
                    base_sql += " AND p.order_id = ?"
                    params.append(order_id)
                if text:
                    base_sql += " AND (p.pallet_number LIKE ? OR o.order_number LIKE ?)"
                    params.extend([f"%{text}%", f"%{text}%"]) 
                base_sql += " ORDER BY p.created_at DESC"
                cur.execute(base_sql, params)
                rows = cur.fetchall()
                for pid, pnum, onum in rows:
                    disp = f"{pnum} (订单: {onum or '-'} )"
                    target_combo.addItem(disp, pid)

            # 初次加载候选
            refresh_candidates()
            search_edit.textChanged.connect(lambda _t: refresh_candidates())
            only_same_order.stateChanged.connect(lambda _s: refresh_candidates())

            def on_ok():
                try:
                    target_id = target_combo.currentData()
                    # 查找选中包裹并迁移（仅允许已完成或已封包的包裹）
                    moved = 0
                    for num in numbers:
                        cur.execute('SELECT id, status FROM packages WHERE package_number = ? AND pallet_id = ?', (num, self.current_pallet_id))
                        pr = cur.fetchone()
                        if pr:
                            pkg_id, pkg_status = pr
                            if pkg_status not in ('completed', 'sealed'):
                                QMessageBox.information(self, "提示", f"包裹 {num} 未完成封包，无法移动")
                                continue
                            cur.execute('UPDATE packages SET pallet_id = ? WHERE id = ?', (target_id, pkg_id))
                            moved += 1
                    conn.commit()
                    # 刷新界面
                    self.update_pallet_info_display()
                    self.update_selected_pallet_info_panel()
                    QMessageBox.information(self, "成功", f"已移动 {moved} 个包裹")
                    # 统一刷新并发出跨页信号
                    self.refresh_data()
                    try:
                        self.data_changed.emit()
                    except Exception:
                        pass
                    dlg.accept()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"移动失败：{str(e)}")

            btns.accepted.connect(on_ok)
            btns.rejected.connect(dlg.reject)
            dlg.exec_()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移动包裹失败：{str(e)}")

    def delete_packages(self):
        """移除托盘：将选中的包裹从当前托盘中移出；若托盘为封托/关闭，先解托并记录日志后再移出"""
        try:
            if not self.current_pallet_id:
                QMessageBox.information(self, "提示", "请先选择托盘")
                return
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute('SELECT status, pallet_number FROM pallets WHERE id = ?', (self.current_pallet_id,))
            row = cur.fetchone()
            status, pallet_number = (row[0], row[1]) if row else (None, "")

            numbers = self._get_selected_package_numbers()
            if not numbers:
                conn.close()
                QMessageBox.information(self, "提示", "请在托盘包裹列表中选择要移出的包裹")
                return

            # 已封托/已关闭需先解托
            if status in ('sealed', 'closed'):
                reply = QMessageBox.question(
                    self,
                    "确认",
                    f"当前托盘已封托，需先解托后才能移除选中包裹。\n是否立即解托托盘 {pallet_number} 并移除?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.No:
                    conn.close()
                    return
                # 执行解托
                cur.execute('''
                    UPDATE pallets 
                    SET status = 'open', sealed_at = NULL
                    WHERE id = ?
                ''', (self.current_pallet_id,))
                # 记录操作日志
                try:
                    db.log_operation('unseal_pallet', {
                        'pallet_id': self.current_pallet_id,
                        'pallet_number': pallet_number,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                except Exception:
                    pass

            # 执行移出：将选中包裹的 pallet_id 置为 NULL
            removed = 0
            for num in numbers:
                cur.execute('''
                    UPDATE packages 
                    SET pallet_id = NULL,
                        status = CASE WHEN status = 'sealed' THEN 'completed' ELSE status END
                    WHERE package_number = ? AND pallet_id = ?
                ''', (num, self.current_pallet_id))
                if cur.rowcount:
                    removed += 1

            conn.commit()
            conn.close()

            # 刷新界面与列表
            self.update_pallet_info_display()
            self.update_selected_pallet_info_panel()
            self.refresh_data()
            try:
                self.data_changed.emit()
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"已将 {removed} 个包裹移出托盘")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移除托盘失败：{str(e)}")

    def edit_pallet(self):
        """编辑托盘信息（类型、序号、状态）"""
        try:
            if not self.current_pallet_id:
                QMessageBox.information(self, "提示", "请先选择托盘")
                return
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT pallet_number, pallet_index, pallet_type, status FROM pallets WHERE id = ?', (self.current_pallet_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                QMessageBox.critical(self, "错误", "未找到托盘信息")
                return
            pallet_number, pallet_index, pallet_type, status = row

            # 对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("编辑托盘")
            grid = QGridLayout(dialog)
            grid.addWidget(QLabel("托盘号"), 0, 0)
            pallet_number_label = QLabel(str(pallet_number))
            grid.addWidget(pallet_number_label, 0, 1)

            grid.addWidget(QLabel("序号"), 1, 0)
            index_edit = QLineEdit(str(pallet_index or ''))
            grid.addWidget(index_edit, 1, 1)

            grid.addWidget(QLabel("类型"), 2, 0)
            type_combo = QComboBox()
            type_combo.addItems(["实体托盘", "虚拟托盘"])
            type_combo.setCurrentIndex(0 if pallet_type == 'physical' else 1)
            grid.addWidget(type_combo, 2, 1)

            grid.addWidget(QLabel("状态"), 3, 0)
            status_combo = QComboBox()
            status_combo.addItems(["开放", "已封托", "已关闭"])
            if status == 'open':
                status_combo.setCurrentIndex(0)
            elif status == 'sealed':
                status_combo.setCurrentIndex(1)
            elif status == 'closed':
                status_combo.setCurrentIndex(2)
            grid.addWidget(status_combo, 3, 1)

            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            grid.addWidget(btns, 4, 0, 1, 2)

            def on_ok():
                try:
                    new_index = index_edit.text().strip()
                    new_type = 'physical' if type_combo.currentIndex() == 0 else 'virtual'
                    new_status = ['open', 'sealed', 'closed'][status_combo.currentIndex()]
                    conn2 = db.get_connection()
                    cur2 = conn2.cursor()
                    cur2.execute('UPDATE pallets SET pallet_index = ?, pallet_type = ?, status = ? WHERE id = ?',
                                 (new_index if new_index else None, new_type, new_status, self.current_pallet_id))
                    conn2.commit()
                    conn2.close()
                    # 刷新列表与信息区
                    self.load_pallets()
                    self.update_pallet_info_display()
                    self.update_selected_pallet_info_panel()
                    # 统一刷新并发出跨页信号
                    self.refresh_data()
                    try:
                        self.data_changed.emit()
                    except Exception:
                        pass
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

            btns.accepted.connect(on_ok)
            btns.rejected.connect(dialog.reject)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"编辑托盘失败：{str(e)}")
    
    def load_packages_for_pallet(self, pallet_id):
        """加载指定托盘的包裹"""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                page_size = int(db.get_setting('packages_page_size', '100'))
            except Exception:
                page_size = 100
            offset = max(0, (getattr(self, 'packages_page', 1) - 1) * page_size)
            # 总数统计（支持搜索）
            search_text = self.package_search_edit.text().strip() if hasattr(self, 'package_search_edit') else ''
            if search_text:
                count_sql = '''
                    SELECT COUNT(*)
                    FROM packages p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.pallet_id = ? AND (p.package_number LIKE ? OR o.order_number LIKE ?)
                '''
                cursor.execute(count_sql, (pallet_id, f'%{search_text}%', f'%{search_text}%'))
            else:
                cursor.execute('SELECT COUNT(*) FROM packages WHERE pallet_id = ?', (pallet_id,))
            total = cursor.fetchone()[0] or 0
            self.packages_total_pages = max(1, (total + page_size - 1) // page_size)
            
            query = '''
                SELECT p.id, p.package_number, p.package_index, p.created_at, 
                       (SELECT COUNT(*) FROM components WHERE package_id = p.id) as component_count,
                       o.order_number, p.status, p.pallet_id
                FROM packages p
                LEFT JOIN orders o ON p.order_id = o.id
                WHERE p.pallet_id = ?
            '''
            params = [pallet_id]
            if search_text:
                query += ' AND (p.package_number LIKE ? OR o.order_number LIKE ?)'
                params.extend([f'%{search_text}%', f'%{search_text}%'])
            query += ' ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
            params.extend([page_size, offset])
            cursor.execute(query, params)
            
            packages = cursor.fetchall()
            conn.close()
            
            self.display_packages(packages)
            self.update_packages_page_label()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载包裹列表失败：{str(e)}")
            traceback.print_exc()
    
    def load_order_packages(self):
        """加载当前订单的包裹"""
        if not self.current_order_id:
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                page_size = int(db.get_setting('packages_page_size', '100'))
            except Exception:
                page_size = 100
            offset = max(0, (getattr(self, 'packages_page', 1) - 1) * page_size)
            search_text = self.package_search_edit.text().strip() if hasattr(self, 'package_search_edit') else ''
            if search_text:
                count_sql = '''
                    SELECT COUNT(*) FROM packages p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.order_id = ? AND p.status = 'completed' AND (p.package_number LIKE ? OR o.order_number LIKE ?)
                '''
                cursor.execute(count_sql, (self.current_order_id, f'%{search_text}%', f'%{search_text}%'))
            else:
                cursor.execute("SELECT COUNT(*) FROM packages WHERE order_id = ? AND status = 'completed'", (self.current_order_id,))
            total = cursor.fetchone()[0] or 0
            self.packages_total_pages = max(1, (total + page_size - 1) // page_size)
            
            query = '''
                SELECT p.id, p.package_number, p.package_index, p.created_at, 
                       (SELECT COUNT(*) FROM components WHERE package_id = p.id) as component_count,
                       o.order_number, p.status, p.pallet_id
                FROM packages p
                LEFT JOIN orders o ON p.order_id = o.id
                WHERE p.order_id = ? AND p.status = 'completed'
            '''
            params = [self.current_order_id]
            if search_text:
                query += ' AND (p.package_number LIKE ? OR o.order_number LIKE ?)'
                params.extend([f'%{search_text}%', f'%{search_text}%'])
            query += ' ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
            params.extend([page_size, offset])
            cursor.execute(query, params)
            
            packages = cursor.fetchall()
            conn.close()
            
            self.display_packages(packages)
            self.update_packages_page_label()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载订单包裹失败：{str(e)}")
            traceback.print_exc()
    
    def load_packages(self):
        """加载所有已完成打包的包裹"""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            try:
                page_size = int(db.get_setting('packages_page_size', '100'))
            except Exception:
                page_size = 100
            offset = max(0, (getattr(self, 'packages_page', 1) - 1) * page_size)
            search_text = self.package_search_edit.text().strip() if hasattr(self, 'package_search_edit') else ''
            if search_text:
                count_sql = '''
                    SELECT COUNT(*) FROM packages p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.status = 'completed' AND (p.package_number LIKE ? OR o.order_number LIKE ?)
                '''
                cursor.execute(count_sql, (f'%{search_text}%', f'%{search_text}%'))
            else:
                cursor.execute("SELECT COUNT(*) FROM packages WHERE status = 'completed'")
            total = cursor.fetchone()[0] or 0
            self.packages_total_pages = max(1, (total + page_size - 1) // page_size)
            
            query = '''
                SELECT p.id, p.package_number, p.package_index, p.created_at, 
                       (SELECT COUNT(*) FROM components WHERE package_id = p.id) as component_count,
                       o.order_number, p.status, p.pallet_id
                FROM packages p
                LEFT JOIN orders o ON p.order_id = o.id
                WHERE p.status = 'completed'
            '''
            params = []
            if search_text:
                query += ' AND (p.package_number LIKE ? OR o.order_number LIKE ?)'
                params.extend([f'%{search_text}%', f'%{search_text}%'])
            query += ' ORDER BY p.created_at DESC LIMIT ? OFFSET ?'
            params.extend([page_size, offset])
            cursor.execute(query, params)
            
            packages = cursor.fetchall()
            conn.close()
            
            self.display_packages(packages)
            self.update_packages_page_label()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载包裹列表失败：{str(e)}")
            traceback.print_exc()
    
    def display_packages(self, packages):
        """显示包裹列表"""
        self.packages_table.setRowCount(len(packages))
        
        for row, package in enumerate(packages):
            package_id, package_number, package_index, created_at, component_count, order_number, status, pallet_id = package
            
            self.packages_table.setItem(row, 0, QTableWidgetItem(str(package_number)))  # package_number
            # 序号列：显示稳定包裹序号
            self.packages_table.setItem(row, 1, QTableWidgetItem(str(package_index) if package_index is not None else ""))  # package_index
            self.packages_table.setItem(row, 2, QTableWidgetItem("标准"))                # 类型
            
            # 托盘信息
            pallet_text = ""
            if pallet_id:
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT pallet_number FROM pallets WHERE id = ?', (pallet_id,))
                    pallet = cursor.fetchone()
                    conn.close()
                    if pallet:
                        pallet_text = pallet[0]
                except:
                    pass
            
            self.packages_table.setItem(row, 3, QTableWidgetItem(pallet_text))          # 托盘
            
            # 状态转换为中文
            status_text = ""
            status_text = package_status_cn(status)
            
            self.packages_table.setItem(row, 4, QTableWidgetItem(status_text))          # status
            self.packages_table.setItem(row, 5, QTableWidgetItem(str(order_number) if order_number else "")) # order_number
            self.packages_table.setItem(row, 6, QTableWidgetItem(str(created_at)))      # created_at
            
            # 操作按钮
            if pallet_id:
                self.packages_table.setItem(row, 7, QTableWidgetItem("已在托盘"))
            else:
                self.packages_table.setItem(row, 7, QTableWidgetItem("可添加"))
            
            # 存储包裹ID
            self.packages_table.item(row, 0).setData(Qt.UserRole, package_id)

    def on_show_mode_changed(self):
        """显示模式变化"""
        # 切换模式时重置分页
        self.packages_page = 1
        self.packages_total_pages = 1
        if self.show_all_packages_cb.isChecked():
            self.load_packages()  # 显示所有包裹
        else:
            if self.current_order_id:
                self.load_order_packages()  # 显示当前订单包裹
            elif self.current_pallet_id:
                self.load_packages_for_pallet(self.current_pallet_id)  # 显示当前托盘包裹
            else:
                self.packages_table.setRowCount(0)  # 清空显示
        # 同步更新待打托数量
        try:
            self.update_pending_to_pallet_count()
        except Exception:
            pass
    
    def filter_packages(self):
        """服务端搜索：重载包裹列表并重置分页"""
        # 切换搜索时重置到第一页
        self.packages_page = 1
        # 根据当前模式刷新
        if self.show_all_packages_cb.isChecked():
            self.load_packages()
        elif self.current_order_id:
            self.load_order_packages()
        elif self.current_pallet_id:
            self.load_packages_for_pallet(self.current_pallet_id)
        else:
            self.packages_table.setRowCount(0)

    def on_pallets_search_changed(self):
        """托盘服务端搜索：重置分页并重载托盘列表"""
        self.pallets_page = 1
        self.load_pallets()
    
    def refresh_data(self):
        """刷新数据"""
        # 保持当前分页，重新加载数据
        self.load_pallets()
        if self.show_all_packages_cb.isChecked():
            self.load_packages()
        elif self.current_order_id:
            self.load_order_packages()
        elif self.current_pallet_id:
            self.load_packages_for_pallet(self.current_pallet_id)
        # 同步更新待打托数量
        try:
            self.update_pending_to_pallet_count()
        except Exception:
            pass
    
    def update_pending_to_pallet_count(self):
        """统计待打托包裹数（已完成但未入托）并更新工具栏标签"""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM packages WHERE status = 'completed' AND pallet_id IS NULL")
            result = cursor.fetchone()
            count = (result[0] if result else 0) or 0
            conn.close()
            if hasattr(self, 'pending_to_pallet_label') and self.pending_to_pallet_label is not None:
                self.pending_to_pallet_label.setText(f"待打托数量: {count}")
        except Exception:
            try:
                if hasattr(self, 'pending_to_pallet_label') and self.pending_to_pallet_label is not None:
                    self.pending_to_pallet_label.setText("待打托数量: -")
            except Exception:
                pass

    def update_pallet_info_display(self):
        """更新托盘信息显示"""
        if not self.current_pallet_id:
            self.pallet_info_label.setText("请选择托盘查看详细信息")
            self.pallet_packages_table.setRowCount(0)
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 获取托盘基本信息
            cursor.execute('''
                SELECT pallet_number, pallet_type, status, created_at
                FROM pallets
                WHERE id = ?
            ''', (self.current_pallet_id,))
            
            pallet_info = cursor.fetchone()
            
            if pallet_info:
                pallet_number, pallet_type, status, created_at = pallet_info
                
                # 获取托盘中的包裹
                cursor.execute('''
                    SELECT p.package_number, p.package_index, o.order_number, 
                           (SELECT COUNT(*) FROM components WHERE package_id = p.id) as component_count,
                           p.created_at, p.status
                    FROM packages p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.pallet_id = ?
                    ORDER BY p.created_at DESC
                ''', (self.current_pallet_id,))
                
                packages = cursor.fetchall()
                package_count = len(packages)
                
                # 托盘类型转换为中文
                pallet_type_text = ""
                if pallet_type == "physical":
                    pallet_type_text = "实体托盘"
                elif pallet_type == "virtual":
                    pallet_type_text = "虚拟托盘"
                else:
                    pallet_type_text = str(pallet_type)
                
                # 托盘状态转换为中文
                status_text = ""
                if status == "open":
                    status_text = "开放"
                elif status == "sealed":
                    status_text = "已封托"
                elif status == "closed":
                    status_text = "已关闭"
                else:
                    status_text = str(status)
                
                # 更新紧凑信息区
                self.pkg_info_number.setText(str(pallet_number))
                self.pkg_info_index.setText('' )
                try:
                    # 如果托盘有稳定序号
                    self.pkg_info_index.setText(str(pallet_info[4]) if len(pallet_info) > 4 and pallet_info[4] is not None else '')
                except Exception:
                    pass
                self.pkg_info_type.setText(pallet_type_text)
                self.pkg_info_status.setText(status_text)
                self.pkg_info_count.setText(str(package_count))
                # 统计完成数
                completed_count = 0
                try:
                    completed_count = sum(1 for _pkg in packages if normalize_package_status(_pkg[5]) == 'completed')
                except Exception:
                    completed_count = 0
                self.pkg_info_completed.setText(str(completed_count))
                # 订单号
                try:
                    cursor.execute('''
                        SELECT o.order_number
                        FROM pallets p
                        LEFT JOIN orders o ON p.order_id = o.id
                        WHERE p.id = ?
                    ''', (self.current_pallet_id,))
                    r2 = cursor.fetchone()
                    self.pkg_info_order.setText((r2[0] if r2 and r2[0] else ''))
                except Exception:
                    self.pkg_info_order.setText('')
                self.pkg_info_created.setText(self.format_datetime(created_at or ''))
                
                # 更新托盘包裹列表
                self.pallet_packages_table.setRowCount(package_count)
                
                for row, package in enumerate(packages):
                    package_number, package_index, order_number, component_count, created_at, pkg_status = package
                    
                    # 包裹状态转换为中文
                    pkg_status_text = ""
                    if pkg_status == "completed":
                        pkg_status_text = "已完成"
                    elif pkg_status == "open":
                        pkg_status_text = "进行中"
                    elif pkg_status == "sealed":
                        pkg_status_text = "已封装"
                    else:
                        pkg_status_text = str(pkg_status)
                    
                    self.pallet_packages_table.setItem(row, 0, QTableWidgetItem(str(package_number)))
                    self.pallet_packages_table.setItem(row, 1, QTableWidgetItem(str(package_index) if package_index is not None else ""))
                    self.pallet_packages_table.setItem(row, 2, QTableWidgetItem(str(order_number) if order_number else ""))
                    self.pallet_packages_table.setItem(row, 3, QTableWidgetItem(str(component_count)))
                    self.pallet_packages_table.setItem(row, 4, QTableWidgetItem(self.format_datetime(created_at)))
                    self.pallet_packages_table.setItem(row, 5, QTableWidgetItem(pkg_status_text))
            
            conn.close()

        except Exception as e:
            self.pallet_info_label.setText(f"获取托盘信息失败: {str(e)}")
            self.pallet_packages_table.setRowCount(0)

    # ----- 分页相关方法 -----
    def update_pallets_page_label(self):
        self.pallets_page_label.setText(f"第 {getattr(self, 'pallets_page', 1)} / {getattr(self, 'pallets_total_pages', 1)} 页")
        self.pallets_prev_btn.setEnabled(self.pallets_page > 1)
        self.pallets_next_btn.setEnabled(self.pallets_page < self.pallets_total_pages)

    def update_packages_page_label(self):
        self.packages_page_label.setText(f"第 {getattr(self, 'packages_page', 1)} / {getattr(self, 'packages_total_pages', 1)} 页")
        self.packages_prev_btn.setEnabled(self.packages_page > 1)
        self.packages_next_btn.setEnabled(self.packages_page < self.packages_total_pages)

    def on_pallets_prev_page(self):
        if getattr(self, 'pallets_page', 1) > 1:
            self.pallets_page -= 1
            self.load_pallets()

    def on_pallets_next_page(self):
        if getattr(self, 'pallets_page', 1) < getattr(self, 'pallets_total_pages', 1):
            self.pallets_page += 1
            self.load_pallets()

    def on_packages_prev_page(self):
        if getattr(self, 'packages_page', 1) > 1:
            self.packages_page -= 1
            # 根据当前模式刷新
            if self.show_all_packages_cb.isChecked():
                self.load_packages()
            elif self.current_order_id:
                self.load_order_packages()
            elif self.current_pallet_id:
                self.load_packages_for_pallet(self.current_pallet_id)

    def on_packages_next_page(self):
        if getattr(self, 'packages_page', 1) < getattr(self, 'packages_total_pages', 1):
            self.packages_page += 1
            if self.show_all_packages_cb.isChecked():
                self.load_packages()
            elif self.current_order_id:
                self.load_order_packages()
            elif self.current_pallet_id:
                self.load_packages_for_pallet(self.current_pallet_id)

    def create_pallet(self):
        """创建新托盘（弹窗选择实体或虚拟）"""
        try:
            # 必须绑定订单后才能创建托盘
            if not self.current_order_id:
                QMessageBox.warning(self, "警告", "请先选择订单，托盘必须绑定订单后才能创建")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("新建托盘类型选择")
            layout = QVBoxLayout(dialog)
            info = QLabel("请选择托盘类型：")
            info.setStyleSheet("font-weight: bold;")
            layout.addWidget(info)

            radio_physical = QRadioButton("实体托盘")
            radio_virtual = QRadioButton("虚拟托盘")
            radio_physical.setChecked(True)
            layout.addWidget(radio_physical)
            layout.addWidget(radio_virtual)

            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(btns)
            btns.accepted.connect(dialog.accept)
            btns.rejected.connect(dialog.reject)

            if dialog.exec_() != QDialog.Accepted:
                return

            is_virtual = radio_virtual.isChecked()

            conn = db.get_connection()
            cursor = conn.cursor()

            pallet_number = db.generate_pallet_number(is_virtual=is_virtual)
            pallet_type = 'virtual' if is_virtual else 'physical'

            # 计算稳定托盘序号（每订单内填补缺口）
            next_index = None
            try:
                next_index = db.get_next_pallet_index(self.current_order_id)
            except Exception:
                next_index = None

            cursor.execute('''
                INSERT INTO pallets (pallet_number, pallet_type, status, created_at, order_id, pallet_index)
                VALUES (?, ?, 'open', datetime('now'), ?, ?)
            ''', (pallet_number, pallet_type, self.current_order_id, next_index))

            conn.commit()
            conn.close()

            # 记录操作日志
            try:
                db.log_operation('create_pallet', {
                    'pallet_number': pallet_number,
                    'order_id': self.current_order_id,
                    'pallet_type': pallet_type
                })
            except Exception:
                pass

            self.load_pallets()
            QMessageBox.information(self, "成功", f"{('虚拟托盘' if is_virtual else '实体托盘')} {pallet_number} 创建成功")
            try:
                voice_speak(f"{('虚拟托盘' if is_virtual else '实体托盘')}创建成功。编号 {pallet_number}")
            except Exception:
                pass
            # 统一刷新并发出跨页信号
            try:
                self.refresh_data()
                self.data_changed.emit()
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建托盘失败：{str(e)}")
            traceback.print_exc()
    
    def create_virtual_pallet(self):
        """创建虚拟托盘"""
        try:
            # 必须绑定订单后才能创建托盘
            if not self.current_order_id:
                QMessageBox.warning(self, "警告", "请先选择订单，托盘必须绑定订单后才能创建")
                return
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 生成虚拟托盘号
            pallet_number = db.generate_pallet_number(is_virtual=True)
            
            # 插入新虚拟托盘
            # 计算稳定托盘序号（每订单内填补缺口）
            next_index = None
            try:
                next_index = db.get_next_pallet_index(self.current_order_id)
            except Exception:
                next_index = None

            cursor.execute('''
                INSERT INTO pallets (pallet_number, pallet_type, status, created_at, order_id, pallet_index)
                VALUES (?, 'virtual', 'open', datetime('now'), ?, ?)
            ''', (pallet_number, self.current_order_id, next_index))
            
            conn.commit()
            conn.close()
            
            self.load_pallets()
            QMessageBox.information(self, "成功", f"虚拟托盘 {pallet_number} 创建成功")
            # 统一刷新并发出跨页信号
            try:
                self.refresh_data()
                self.data_changed.emit()
            except Exception:
                pass

            # 记录操作日志
            try:
                db.log_operation('create_pallet', {
                    'pallet_number': pallet_number,
                    'order_id': self.current_order_id,
                    'pallet_type': 'virtual'
                })
            except Exception:
                pass
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建虚拟托盘失败：{str(e)}")
            traceback.print_exc()
    
    def delete_pallet(self):
        """删除托盘"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择要删除的托盘")
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 获取托盘信息
            cursor.execute('SELECT pallet_number, pallet_type, order_id FROM pallets WHERE id = ?', (self.current_pallet_id,))
            pallet_info = cursor.fetchone()
            
            if not pallet_info:
                QMessageBox.warning(self, "警告", "托盘不存在")
                conn.close()
                return
            
            pallet_number, pallet_type, pallet_order_id = pallet_info
            
            # 检查托盘中是否有包裹
            cursor.execute('SELECT COUNT(*) FROM packages WHERE pallet_id = ?', (self.current_pallet_id,))
            package_count = cursor.fetchone()[0]
            
            if package_count > 0:
                reply = QMessageBox.question(self, "确认删除", 
                    f"托盘 {pallet_number} 中还有 {package_count} 个包裹，删除托盘将会将这些包裹移出托盘。\n\n确定要删除吗？",
                    QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    conn.close()
                    return
                
                # 将包裹从托盘中移出
                cursor.execute('''UPDATE packages 
                                   SET pallet_id = NULL,
                                       status = CASE WHEN status = 'sealed' THEN 'completed' ELSE status END 
                                   WHERE pallet_id = ?''', (self.current_pallet_id,))
            else:
                reply = QMessageBox.question(self, "确认删除", 
                    f"确定要删除托盘 {pallet_number} 吗？",
                    QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    conn.close()
                    return
            
            # 删除托盘
            cursor.execute('DELETE FROM pallets WHERE id = ?', (self.current_pallet_id,))
            
            conn.commit()
            conn.close()
            
            # 清除当前选择
            self.current_pallet_id = None
            self.pallet_info_label.setText("请选择托盘查看详细信息")
            self.pallet_packages_table.setRowCount(0)
            
            # 刷新托盘列表
            self.load_pallets()
            
            QMessageBox.information(self, "成功", f"托盘 {pallet_number} 删除成功")
            # 统一刷新并发出跨页信号
            try:
                self.refresh_data()
                self.data_changed.emit()
            except Exception:
                pass

            # 云端删除同步：托盘
            try:
                from real_time_cloud_sync import get_sync_service
                svc = getattr(self, 'cloud_sync_service', None) or get_sync_service()
                if pallet_number:
                    svc.trigger_sync('delete_pallets', {'items': [{'pallet_number': pallet_number}]})
            except Exception as e:
                print(f"触发云端删除托盘失败: {e}")

            # 记录操作日志
            try:
                db.log_operation('delete_pallet', {
                    'pallet_number': pallet_number,
                    'order_id': pallet_order_id,
                    'pallet_type': pallet_type,
                    'package_count': package_count
                })
            except Exception:
                pass
            # 云端删除同步：托盘
            try:
                from real_time_cloud_sync import get_sync_service
                svc = getattr(self, 'cloud_sync_service', None) or get_sync_service()
                if pallet_number:
                    svc.trigger_sync('delete_pallets', {'items': [{'pallet_number': pallet_number}]})
            except Exception as e:
                print(f"触发云端删除托盘失败: {e}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除托盘失败：{str(e)}")
            traceback.print_exc()
    
    def seal_pallet(self):
        """封托"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择托盘")
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE pallets 
                SET status = 'sealed', sealed_at = datetime('now')
                WHERE id = ?
            ''', (self.current_pallet_id,))
            
            conn.commit()
            conn.close()
            
            self.load_pallets()
            self.update_pallet_info_display()
            QMessageBox.information(self, "成功", "托盘封托成功")
            # 统一刷新并发出跨页信号
            self.refresh_data()
            try:
                self.data_changed.emit()
            except Exception:
                pass
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"封托失败：{str(e)}")
            traceback.print_exc()
    
    def unseal_pallet(self):
        """解托"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择托盘")
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE pallets 
                SET status = 'open', sealed_at = NULL
                WHERE id = ?
            ''', (self.current_pallet_id,))
            
            # 记录操作日志
            try:
                cursor.execute('SELECT pallet_number FROM pallets WHERE id = ?', (self.current_pallet_id,))
                r = cursor.fetchone()
                pallet_number = r[0] if r else ''
                db.log_operation('unseal_pallet', {
                    'pallet_id': self.current_pallet_id,
                    'pallet_number': pallet_number,
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception:
                pass

            conn.commit()
            conn.close()
            
            self.load_pallets()
            self.update_pallet_info_display()
            QMessageBox.information(self, "成功", "托盘解托成功")
            # 统一刷新并发出跨页信号
            self.refresh_data()
            try:
                self.data_changed.emit()
            except Exception:
                pass
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解托失败：{str(e)}")
            traceback.print_exc()
    
    def move_package_to_pallet(self):
        """移动包裹到托盘"""
        current_row = self.packages_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要移动的包裹")
            return
        
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择目标托盘")
            return
        
        package_id = self.packages_table.item(current_row, 0).data(Qt.UserRole)
        package_number = self.packages_table.item(current_row, 0).text()
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE packages SET pallet_id = ? WHERE id = ?', (self.current_pallet_id, package_id))
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "成功", f"包裹 {package_number} 已移动到当前托盘")
            self.refresh_data()
            try:
                self.data_changed.emit()
            except Exception:
                pass
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移动包裹失败：{str(e)}")
    
    def remove_package_from_pallet(self):
        """从托盘中移出包裹"""
        current_row = self.packages_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要移出的包裹")
            return
        
        package_id = self.packages_table.item(current_row, 0).data(Qt.UserRole)
        package_number = self.packages_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(self, "确认", f"确定要将包裹 {package_number} 从托盘中移出吗？")
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE packages 
                    SET pallet_id = NULL,
                        status = CASE WHEN status = 'sealed' THEN 'completed' ELSE status END
                    WHERE id = ?
                ''', (package_id,))
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "成功", f"包裹 {package_number} 已从托盘中移出")
                self.refresh_data()
                try:
                    self.data_changed.emit()
                except Exception:
                    pass
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"移出包裹失败：{str(e)}")
    
    def generate_pallet_report(self):
        """生成托盘清单"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择托盘")
            return
        
        QMessageBox.information(self, "提示", "托盘清单生成功能待实现")
    
    def print_pallet_report(self):
        """打印托盘清单"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择托盘")
            return
        
        QMessageBox.information(self, "提示", "托盘清单打印功能待实现")
    
    def export_to_excel(self):
        """导出到Excel"""
        QMessageBox.information(self, "提示", "Excel导出功能待实现")
    
    def select_template_for_pallet(self):
        """为托盘标签选择模板"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QListWidgetItem
        import os
        import json
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择托盘标签模板")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 标题
        title_label = QLabel("请选择托盘标签模板：")
        layout.addWidget(title_label)
        
        # 模板列表
        template_list = QListWidget()
        layout.addWidget(template_list)
        
        # 收集所有模板文件
        templates = []
        
        # 默认模板
        default_templates_dir = "templates"
        if os.path.exists(default_templates_dir):
            for file in os.listdir(default_templates_dir):
                if file.endswith('.json'):
                    template_path = os.path.join(default_templates_dir, file)
                    templates.append(("默认模板", file, template_path))
        
        # 自定义模板
        custom_templates_dir = "custom_templates"
        if os.path.exists(custom_templates_dir):
            for file in os.listdir(custom_templates_dir):
                if file.endswith('.json'):
                    template_path = os.path.join(custom_templates_dir, file)
                    templates.append(("自定义模板", file, template_path))
        
        # 添加模板到列表
        for template_type, filename, filepath in templates:
            try:
                # 尝试读取模板信息
                with open(filepath, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                    template_name = template_data.get('name', filename)
                    
                item = QListWidgetItem(f"[{template_type}] {template_name}")
                item.setData(32, filepath)  # 存储文件路径
                template_list.addItem(item)
            except:
                # 如果读取失败，使用文件名
                item = QListWidgetItem(f"[{template_type}] {filename}")
                item.setData(32, filepath)
                template_list.addItem(item)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # 连接信号
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        # 默认选择第一个模板
        if template_list.count() > 0:
            template_list.setCurrentRow(0)
        
        if dialog.exec_() == QDialog.Accepted:
            current_item = template_list.currentItem()
            if current_item:
                return current_item.data(32)  # 返回文件路径
        
        return None

    def print_pallet_label(self):
        """打印托盘标签"""
        if not self.current_pallet_id:
            QMessageBox.warning(self, "警告", "请先选择要打印标签的托盘！")
            return
        
        # 显示模板选择对话框
        template_path = self.select_template_for_pallet()
        if not template_path:
            return  # 用户取消了模板选择
        
        try:
            # 获取托盘信息
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pt.pallet_number, pt.pallet_type, pt.status, pt.created_at,
                       COUNT(p.id) as package_count, pt.order_id, pt.pallet_index
                FROM pallets pt
                LEFT JOIN packages p ON p.pallet_id = pt.id
                WHERE pt.id = ?
                GROUP BY pt.id
            ''', (self.current_pallet_id,))
            pallet_info = cursor.fetchone()
            
            if not pallet_info:
                QMessageBox.warning(self, "错误", "未找到托盘信息！")
                return
            
            # 获取托盘中的包装信息
            cursor.execute('''
                SELECT p.package_number, p.created_at, p.status,
                       o.order_number, o.customer_name, o.customer_address,
                       COUNT(c.id) as component_count
                FROM packages p
                LEFT JOIN orders o ON p.order_id = o.id
                LEFT JOIN components c ON c.package_id = p.id
                WHERE p.pallet_id = ?
                GROUP BY p.id
                ORDER BY p.created_at
            ''', (self.current_pallet_id,))
            packages = cursor.fetchall()

            # 订单与进度信息
            order_number = ''
            customer_name = ''
            customer_address = ''
            package_total_in_order = ''
            pallet_total_in_order = ''
            if pallet_info and pallet_info[5]:
                order_id = pallet_info[5]
                cursor.execute('SELECT order_number, customer_name, customer_address FROM orders WHERE id = ?', (order_id,))
                order_row = cursor.fetchone()
                if order_row:
                    order_number, customer_name, customer_address = order_row
                cursor.execute('SELECT COUNT(*) FROM packages WHERE order_id = ?', (order_id,))
                package_total_in_order = str(cursor.fetchone()[0])
                cursor.execute('SELECT COUNT(*) FROM pallets WHERE order_id = ?', (order_id,))
                pallet_total_in_order = str(cursor.fetchone()[0])

            # 打印时间与次数
            from datetime import datetime
            printed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print_count = 0
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM operation_logs WHERE operation_type = 'print_pallet_label' AND operation_data LIKE ?",
                    (f'%"pallet_number":"{pallet_info[0]}"%',)
                )
                print_count = cursor.fetchone()[0]
            except Exception:
                print_count = 0

            # 容量与填充率（依赖设置：pallet_capacity）
            try:
                from database import db as _db_inst
                cap_setting = _db_inst.get_setting('pallet_capacity', '')
                capacity_val = int(cap_setting) if str(cap_setting).strip().isdigit() else ''
            except Exception:
                capacity_val = ''
            fill_rate_percent = ''
            try:
                if capacity_val:
                    fill_rate_percent = f"{round((int(pallet_info[4]) / int(capacity_val)) * 100)}%"
            except Exception:
                fill_rate_percent = ''
            
            conn.close()
            
            # 准备标签数据
            label_data = {
                'pallet_number': pallet_info[0],
                'pallet_type': pallet_info[1],
                'status': pallet_info[2],
                'create_time': pallet_info[3],
                'package_count': pallet_info[4],
                'pallet_index': pallet_info[6],
                'order_number': order_number,
                'customer_name': customer_name,
                'customer_address': customer_address,
                'package_total_in_order': package_total_in_order,
                'pallet_total_in_order': pallet_total_in_order,
                'printed_at': printed_at,
                'print_count': print_count,
                'capacity': capacity_val,
                'fill_rate_percent': fill_rate_percent,
                'total_pallets': '1',  # 当前托盘数量
                'packages': packages
            }
            
            # 调用直接打印功能（热敏打印机优化）
            self.print_label_directly(label_data, template_path)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打印标签时发生错误：{str(e)}")
    
    def print_label_directly(self, label_data, template_path=None):
        """直接打印托盘标签，不打开设计界面"""
        try:
            from label_printing import LabelPrinting
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt5.QtGui import QPainter
            
            # 创建标签打印组件（不显示界面）
            label_printing = LabelPrinting()
            
            # 如果提供了模板路径，先加载模板，否则加载默认模板2
            if template_path:
                label_printing.load_template(template_path)
            else:
                # 默认加载模板2（托盘标签模板）
                import os
                default_template_path = os.path.join(os.path.dirname(__file__), 'custom_templates', 'custom_template_2.json')
                if os.path.exists(default_template_path):
                    try:
                        label_printing.load_template(default_template_path)
                    except Exception as e:
                        print(f"加载托盘默认模板失败：{str(e)}")
            
            # 设置标签数据到画布
            self.set_label_data_to_canvas(label_printing, label_data)
            
            # 直接打印 - 使用系统设置
            printer = QPrinter()
            
            # 从系统设置中读取打印机配置
            from database import db
            printer_name = db.get_setting('printer_name', '')
            if printer_name:
                printer.setPrinterName(printer_name)
            
            # 应用系统设置中的打印机配置
            label_printing.apply_printer_settings_from_db(printer)
            
            # 检查是否需要显示打印预览
            show_preview = db.get_setting('print_preview', 'false') == 'true'
            
            if show_preview:
                dialog = QPrintDialog(printer, self)
                dialog.setWindowTitle("热敏托盘标签打印")
                
                if dialog.exec_() != QPrintDialog.Accepted:
                    return
            
            # 开始打印（统一调用标签模块的渲染，避免重复旋转与缩放）
            label_printing.render_to_printer(printer)
            
            # 保存打印日志
            if db.get_setting('save_print_log', 'true') == 'true':
                label_printing.save_print_log()
                # 统一审计：记录打印托盘标签动作
                try:
                    db.log_operation('print_pallet_label', {
                        'pallet_number': label_data.get('pallet_number', ''),
                        'order_number': label_data.get('order_number', ''),
                        'printed_at': label_data.get('printed_at', '')
                    })
                except Exception:
                    pass
            
            QMessageBox.information(self, "成功", "热敏托盘标签打印完成！")
            
        except ImportError:
            QMessageBox.warning(self, "错误", "无法加载标签打印模块！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打印托盘标签时发生错误：{str(e)}")

    def open_label_printing_with_data(self, label_data, template_path=None):
        """打开标签打印页面并传入数据"""
        try:
            # 导入标签打印模块
            from label_printing import LabelPrinting
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
            
            # 创建标签打印对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("打印托盘标签")
            dialog.resize(1200, 800)
            
            layout = QVBoxLayout(dialog)
            
            # 创建标签打印组件
            label_printing = LabelPrinting()
            layout.addWidget(label_printing)
            
            # 如果提供了模板路径，先加载模板
            if template_path:
                label_printing.load_template(template_path)
            
            # 设置标签数据到画布
            self.set_label_data_to_canvas(label_printing, label_data)
            
            # 添加关闭按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            button_layout.addWidget(close_btn)
            layout.addLayout(button_layout)
            
            dialog.exec_()
            
        except ImportError:
            QMessageBox.warning(self, "错误", "无法加载标签打印模块！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开标签打印页面时发生错误：{str(e)}")
    
    def set_label_data_to_canvas(self, label_printing, label_data):
        """将托盘数据设置到标签画布"""
        try:
            # 计算托盘序号（从托盘号中提取数字）
            def extract_index(num_str):
                try:
                    import re
                    m = re.search(r"(\d+)", str(num_str or ''))
                    return int(m.group(1)) if m else None
                except Exception:
                    return None

            pallet_number = label_data.get('pallet_number', '')
            pallet_index = label_data.get('pallet_index')
            if pallet_index is None:
                pallet_index = extract_index(pallet_number)

            # 更新标签打印模块的示例数据
            sample_data = {
                'pallet_number': pallet_number,
                'pallet_type': label_data.get('pallet_type', ''),
                'capacity': str(label_data.get('capacity', '')),
                'fill_rate_percent': label_data.get('fill_rate_percent', ''),
                'status': label_data.get('status', ''),
                'create_time': label_data.get('create_time', ''),
                'package_count': str(label_data.get('package_count', 0)),
                'total_pallets': label_data.get('total_pallets', '1'),
                'component_name': '托盘标签',  # 默认组件名称
                'order_number': label_data.get('order_number', ''),
                'customer_name': label_data.get('customer_name', ''),
                'customer_address': label_data.get('customer_address', ''),
                'package_total_in_order': str(label_data.get('package_total_in_order', '')),
                'pallet_total_in_order': str(label_data.get('pallet_total_in_order', '')),
                'printed_at': label_data.get('printed_at', ''),
                'print_count': str(label_data.get('print_count', 0)),
                # 新增：托盘序号字段
                'pallet_index': str(pallet_index) if pallet_index is not None else '',
                'pallet_index_display': f"第{pallet_index}托盘" if pallet_index is not None else '',
                # 便于模板二维码使用的组合字段
                'qr_payload': f"{label_data.get('order_number', '')}+{pallet_number}" if label_data.get('order_number') else pallet_number
            }
            
            # 如果托盘只包含一个订单的包装，使用该订单信息
            packages = label_data.get('packages', [])
            if packages:
                # 获取第一个包装的订单信息
                first_package = packages[0]
                if len(first_package) >= 7:
                    sample_data.update({
                        'order_number': first_package[3],   # order_number
                        'customer_name': first_package[4],  # customer_name
                        'customer_address': first_package[5]  # customer_address
                    })
                
                # 生成包裹列表：包裹编号+共几片板件
                package_list_items = []
                for package in packages:
                    if len(package) >= 7:
                        package_number = package[0]  # package_number
                        component_count = package[6]  # component_count
                        package_list_items.append(f"{package_number}+共{component_count}片板件")
                
                package_list = '\n'.join(package_list_items)
                sample_data['package_list'] = package_list
            
            # 更新画布的示例数据
            if hasattr(label_printing.canvas, 'sample_data'):
                label_printing.canvas.sample_data.update(sample_data)
            
        except Exception as e:
            print(f"设置标签数据时发生错误: {e}")
    
    def undo_last_operation(self):
        """撤销上一次操作"""
        QMessageBox.information(self, "提示", "撤销操作功能待实现")
    def update_selected_pallet_info_panel(self):
        """根据当前选择的托盘，更新中间信息面板"""
        try:
            row = self.pallets_table.currentRow()
            if row is None or row < 0:
                self.pkg_info_number.setText("")
                self.pkg_info_index.setText("")
                self.pkg_info_type.setText("")
                self.pkg_info_status.setText("")
                self.pkg_info_order.setText("")
                self.pkg_info_created.setText("")
                self.pkg_info_count.setText("")
                self.pkg_info_completed.setText("")
                return

            # 直接从表格读展示值
            def t(col):
                it = self.pallets_table.item(row, col)
                return it.text() if it else ""

            self.pkg_info_number.setText(t(0))  # 托盘号
            self.pkg_info_index.setText(t(1))   # 序号
            self.pkg_info_type.setText(t(2))    # 类型
            self.pkg_info_status.setText(t(4))  # 状态
            self.pkg_info_count.setText(t(3))   # 包裹数

            # 查询订单号、创建时间与已完成数量
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT o.order_number, p.created_at
                    FROM pallets p
                    LEFT JOIN orders o ON p.order_id = o.id
                    WHERE p.id = ?
                ''', (self.current_pallet_id,))
                r = cursor.fetchone()
                order_num = ''
                created_at = ''
                if r:
                    order_num, created_at = r
                # 统计已完成包裹数量
                cursor.execute("SELECT COUNT(*) FROM packages WHERE pallet_id = ? AND status = 'completed'", (self.current_pallet_id,))
                cr = cursor.fetchone()
                completed_cnt = (cr[0] if cr and cr[0] is not None else 0)
                conn.close()
                self.pkg_info_order.setText(order_num or '')
                self.pkg_info_created.setText(self.format_datetime(created_at or ''))
                self.pkg_info_completed.setText(str(completed_cnt))
            except Exception:
                pass
        except Exception:
            pass