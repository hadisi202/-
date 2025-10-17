from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QGroupBox, QFormLayout,
                             QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QMessageBox,
                             QScrollArea, QFrame, QCheckBox, QTabWidget,
                             QGridLayout, QSplitter, QListWidget, QListWidgetItem,
                             QStackedWidget, QSizePolicy, QTimeEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QTime
from PyQt5.QtGui import QFont, QIcon
import database as db
import json
import os
from real_time_cloud_sync import get_sync_service

class SystemSettings(QWidget):
    """系统设置模块 - 重新设计的统一设置界面"""
    
    settings_changed = pyqtSignal()  # 设置变更信号
    # 管理员删除联动信号（最高权限）
    admin_components_deleted = pyqtSignal()
    admin_packages_deleted = pyqtSignal()
    admin_pallets_deleted = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.db = db.Database()
        # 管理员认证状态
        self.is_admin_authenticated = False
        self.admin_user_name = None
        # 云同步服务与定时器
        # 在创建同步服务之前设置 HTTP 直连与 CLI 兜底所需环境变量
        try:
            os.environ.setdefault('PACKOPS_BASE_URL', 'https://cloud1-7grjr7usb5d86f59-1363732811.ap-shanghai.app.tcloudbase.com/packOps')
            os.environ.setdefault('PACKOPS_ENV_ID', 'cloud1-7grjr7usb5d86f59')
            os.environ.setdefault('PACKOPS_VERIFY', 'true')
        except Exception:
            pass
        try:
            # 统一使用单例，避免 UI 内与其它模块各自实例造成状态不一致
            from real_time_cloud_sync import get_sync_service
            self.cloud_sync_service = get_sync_service(self.db.db_path)
        except Exception:
            self.cloud_sync_service = None
        self.cloud_sync_timer = QTimer(self)
        self.cloud_sync_timer.setSingleShot(False)
        self.cloud_sync_timer.timeout.connect(self._on_cloud_sync_timer)
        # 每日全量同步定时器（单次触发，到点后自动重新调度下一次）
        self.daily_full_sync_timer = QTimer(self)
        self.daily_full_sync_timer.setSingleShot(True)
        self.daily_full_sync_timer.timeout.connect(self._on_daily_full_sync_timer)
        # 自动备份定时器
        self.backup_timer = QTimer(self)
        self.backup_timer.setSingleShot(False)
        self.backup_timer.timeout.connect(self._on_backup_timer)
        self.init_ui()
        self.load_all_settings()
        # 根据当前设置应用自动备份定时器
        try:
            self._apply_backup_settings()
        except Exception:
            pass

    # === 上传进度条（简洁显示百分比） ===
    def _progress_file_path(self) -> str:
        try:
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_progress.json')
        except Exception:
            return 'sync_progress.json'

    def _show_upload_progress(self, title_text: str = '正在上传到云端…'):
        try:
            # 仅创建一次对话框，避免重复实例
            dlg = QDialog(self)
            dlg.setWindowTitle(title_text)
            dlg.setModal(True)
            dlg.setFixedWidth(420)
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(20, 20, 20, 20)

            label = QLabel('上传进度：0%')
            label.setAlignment(Qt.AlignCenter)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            # 简洁样式：仅显示条与百分比
            bar.setTextVisible(True)
            bar.setFormat('%p%')
            layout.addWidget(label)
            layout.addWidget(bar)

            # 轮询进度文件更新进度
            timer = QTimer(dlg)
            timer.setSingleShot(False)
            # 若出现连续的完成状态且内容未变化，认为整体任务已完成
            state = {'last_sig': '', 'quiet_ticks': 0}
            def _poll():
                try:
                    path = self._progress_file_path()
                    if not os.path.exists(path):
                        return
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    percent = int(data.get('percent') or 0)
                    status = str(data.get('status') or '')
                    sig = f"{status}:{percent}:{data.get('operation')}:{data.get('data_type')}:{data.get('updated_at')}"
                    bar.setValue(max(0, min(100, percent)))
                    label.setText(f'上传进度：{percent}%')
                    if status in ('completed', 'failed') or percent >= 100:
                        # 若进度文件在短时间内未变化，判定整体完成
                        if sig == state['last_sig']:
                            state['quiet_ticks'] += 1
                        else:
                            state['quiet_ticks'] = 0
                        state['last_sig'] = sig
                        if state['quiet_ticks'] >= 4:  # ~1.2s 无变化
                            timer.stop()
                            dlg.accept()
                            return
                    else:
                        state['last_sig'] = sig
                        state['quiet_ticks'] = 0
                except Exception:
                    # 忽略解析/读取异常
                    pass
            timer.timeout.connect(_poll)
            timer.start(300)

            # 展示对话框并由轮询自动关闭
            dlg.exec_()
        except Exception:
            # UI 异常不影响上传流程
            pass
    
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧导航栏
        nav_widget = self.create_navigation()
        nav_widget.setMaximumWidth(200)
        nav_widget.setMinimumWidth(180)
        splitter.addWidget(nav_widget)
        
        # 右侧设置内容区域
        content_widget = self.create_content_area()
        splitter.addWidget(content_widget)
        
        # 设置分割器比例
        splitter.setSizes([200, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        # 底部按钮区域改为顶部工具区：在内容区域顶部创建按钮栏
        # 注意：调用位置调整为在创建内容区域后，由内容区域自身负责摆放按钮
        #（此处不再在 main_layout 末尾添加底部按钮）
        
        # 设置默认选中第一项（在所有UI组件创建完成后）
        self.nav_list.setCurrentRow(0)
    
    def create_navigation(self):
        """创建左侧导航栏"""
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_label = QLabel("系统设置")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                border-bottom: 2px solid #3498db;
                margin-bottom: 10px;
            }
        """)
        nav_layout.addWidget(title_label)
        
        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: #f8f9fa;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
                color: #495057;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QListWidget::item:selected {
                background-color: #2196f3;
                color: white;
                font-weight: bold;
            }
        """)
        
        # 添加导航项
        nav_items = [
            ("📦 包装设置", "packaging"),
            ("🔧 扫码配置", "scan_config"),
            ("📄 导入配置", "import_config"),
            ("🖨️ 打印机设置", "printer_settings"),
            ("🎨 界面设置", "ui_settings"),
            ("💾 数据库设置", "database"),
            ("📊 日志设置", "log_settings"),
            ("⚡ 系统行为", "system_behavior"),
            ("🔄 备份设置", "backup_settings")
        ]
        
        for text, key in nav_items:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        
        self.nav_list.currentItemChanged.connect(self.on_nav_changed)
        nav_layout.addWidget(self.nav_list)
        
        nav_layout.addStretch()
        return nav_widget
    
    def create_content_area(self):
        """创建右侧内容区域"""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 10, 10, 10)
        
        # 内容标题
        self.content_title = QLabel("包装设置")
        self.content_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px 0;
                border-bottom: 1px solid #bdc3c7;
                margin-bottom: 20px;
            }
        """)
        content_layout.addWidget(self.content_title)

        # 顶部按钮区域（原底部按钮上移至此）
        top_button_layout = QHBoxLayout()
        top_button_layout.setContentsMargins(0, 0, 0, 0)
        # 左侧按钮：导入/导出设置
        self.import_settings_btn = QPushButton("导入设置")
        self.export_settings_btn = QPushButton("导出设置")
        top_button_layout.addWidget(self.import_settings_btn)
        top_button_layout.addWidget(self.export_settings_btn)
        top_button_layout.addStretch()
        # 右侧按钮：重置/应用/保存
        self.reset_btn = QPushButton("重置为默认")
        self.apply_btn = QPushButton("应用")
        self.save_btn = QPushButton("保存设置")
        # 样式与原保持一致
        for btn in [self.reset_btn, self.apply_btn]:
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                }
                """
            )
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            """
        )
        top_button_layout.addWidget(self.reset_btn)
        top_button_layout.addWidget(self.apply_btn)
        top_button_layout.addWidget(self.save_btn)
        # 信号连接与原逻辑一致
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        self.apply_btn.clicked.connect(self.apply_settings)
        self.save_btn.clicked.connect(self.save_settings)
        # 接入导入/导出按钮
        self.import_settings_btn.clicked.connect(self.on_import_settings)
        self.export_settings_btn.clicked.connect(self.on_export_settings)
        content_layout.addLayout(top_button_layout)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        
        # 堆叠窗口部件
        self.stacked_widget = QStackedWidget()
        
        # 创建各个设置页面
        self.create_packaging_settings()
        self.create_scan_config_settings()
        self.create_import_config_settings()
        # 移除标签模板设置页
        self.create_printer_settings()
        self.create_ui_settings()
        self.create_database_settings()
        self.create_log_settings()
        self.create_system_behavior_settings()
        self.create_backup_settings()
        
        scroll_area.setWidget(self.stacked_widget)
        content_layout.addWidget(scroll_area)
        
        return content_widget
    
    def create_packaging_settings(self):
        """创建包装设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 包装号格式设置
        format_group = QGroupBox("包装号格式设置")
        format_group.setStyleSheet(self.get_group_style())
        format_layout = QFormLayout(format_group)
        
        self.package_number_format = QLineEdit()
        self.package_number_format.setPlaceholderText("例如: YYYYMMDD{:04d}")
        format_layout.addRow("包装号格式:", self.package_number_format)
        
        self.pallet_number_format = QLineEdit()
        self.pallet_number_format.setPlaceholderText("例如: T{date}{:04d}")
        format_layout.addRow("托盘号格式:", self.pallet_number_format)
        
        self.virtual_pallet_format = QLineEdit()
        self.virtual_pallet_format.setPlaceholderText("例如: VT{date}{:04d}")
        format_layout.addRow("虚拟托盘号格式:", self.virtual_pallet_format)
        
        layout.addWidget(format_group)
        
        # 自动化设置
        auto_group = QGroupBox("自动化设置")
        auto_group.setStyleSheet(self.get_group_style())
        auto_layout = QFormLayout(auto_group)
        
        self.auto_complete_code = QLineEdit()
        self.auto_complete_code.setPlaceholderText("例如: COMPLETE")
        auto_layout.addRow("自动完成包装扫码:", self.auto_complete_code)
        
        layout.addWidget(auto_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_scan_config_settings(self):
        """创建扫码配置设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 默认扫码配置
        default_group = QGroupBox("默认扫码配置")
        default_group.setStyleSheet(self.get_group_style())
        default_layout = QFormLayout(default_group)
        
        self.default_scan_config = QComboBox()
        self.load_scan_configs()
        default_layout.addRow("默认扫码配置:", self.default_scan_config)
        
        # 添加配置管理按钮
        config_buttons = QHBoxLayout()
        self.new_scan_config_btn = QPushButton("新建配置")
        self.edit_scan_config_btn = QPushButton("编辑配置")
        self.delete_scan_config_btn = QPushButton("删除配置")
        
        for btn in [self.new_scan_config_btn, self.edit_scan_config_btn, self.delete_scan_config_btn]:
            btn.setStyleSheet(self.get_button_style())
            config_buttons.addWidget(btn)
        
        config_buttons.addStretch()
        default_layout.addRow("配置管理:", config_buttons)
        
        layout.addWidget(default_group)
        
        # 扫码处理说明
        help_group = QGroupBox("扫码处理说明")
        help_group.setStyleSheet(self.get_group_style())
        help_layout = QVBoxLayout(help_group)
        
        help_text = QLabel("""
        • 前缀移除: 移除扫码结果的前N个字符
        • 后缀移除: 移除扫码结果的后N个字符  
        • 中间提取: 从指定位置提取指定长度的字符
        • 字符插入: 在指定位置插入自定义字符
        • 组合配置: 可以组合多种处理方式
        """)
        help_text.setStyleSheet("color: #666; line-height: 1.5;")
        help_layout.addWidget(help_text)
        
        layout.addWidget(help_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_import_config_settings(self):
        """创建导入配置设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 默认导入配置
        default_group = QGroupBox("默认导入配置")
        default_group.setStyleSheet(self.get_group_style())
        default_layout = QFormLayout(default_group)
        
        self.default_import_config = QComboBox()
        self.load_import_configs()
        default_layout.addRow("默认导入配置:", self.default_import_config)
        
        # 添加配置管理按钮
        import_buttons = QHBoxLayout()
        self.new_import_config_btn = QPushButton("新建配置")
        self.edit_import_config_btn = QPushButton("编辑配置")
        self.delete_import_config_btn = QPushButton("删除配置")
        
        for btn in [self.new_import_config_btn, self.edit_import_config_btn, self.delete_import_config_btn]:
            btn.setStyleSheet(self.get_button_style())
            import_buttons.addWidget(btn)
        
        import_buttons.addStretch()
        default_layout.addRow("配置管理:", import_buttons)
        
        layout.addWidget(default_group)
        
        # 导入说明
        help_group = QGroupBox("CSV导入说明")
        help_group.setStyleSheet(self.get_group_style())
        help_layout = QVBoxLayout(help_group)
        
        help_text = QLabel("""
        • 支持自动检测CSV文件编码格式
        • 支持自定义字段映射配置
        • 可保存多套导入配置方案
        • 支持预览导入数据
        """)
        help_text.setStyleSheet("color: #666; line-height: 1.5;")
        help_layout.addWidget(help_text)
        
        layout.addWidget(help_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_label_template_settings(self):
        """创建标签模板设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 默认标签模板
        template_group = QGroupBox("默认标签模板")
        template_group.setStyleSheet(self.get_group_style())
        template_layout = QFormLayout(template_group)
        
        self.default_label_template = QComboBox()
        self.load_label_templates()
        template_layout.addRow("默认标签模板:", self.default_label_template)
        
        # 模板管理按钮
        template_buttons = QHBoxLayout()
        self.open_label_editor_btn = QPushButton("打开标签编辑器")
        self.manage_templates_btn = QPushButton("管理模板")
        
        for btn in [self.open_label_editor_btn, self.manage_templates_btn]:
            btn.setStyleSheet(self.get_button_style())
            template_buttons.addWidget(btn)
        
        template_buttons.addStretch()
        template_layout.addRow("模板管理:", template_buttons)
        
        layout.addWidget(template_group)
        
        # 标签设置
        label_group = QGroupBox("标签打印设置")
        label_group.setStyleSheet(self.get_group_style())
        label_layout = QFormLayout(label_group)
        
        self.label_width = QSpinBox()
        self.label_width.setRange(10, 500)
        self.label_width.setSuffix(" mm")
        label_layout.addRow("标签宽度:", self.label_width)
        
        self.label_height = QSpinBox()
        self.label_height.setRange(10, 500)
        self.label_height.setSuffix(" mm")
        label_layout.addRow("标签高度:", self.label_height)
        
        layout.addWidget(label_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_printer_settings(self):
        """创建打印机设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 热敏打印机设置
        thermal_group = QGroupBox("热敏打印机设置")
        thermal_group.setStyleSheet(self.get_group_style())
        thermal_layout = QFormLayout(thermal_group)
        
        # 打印机选择
        self.printer_name = QComboBox()
        self.printer_name.setEditable(True)
        self.refresh_printers_btn = QPushButton("刷新打印机列表")
        self.refresh_printers_btn.setStyleSheet(self.get_button_style())
        
        printer_layout = QHBoxLayout()
        printer_layout.addWidget(self.printer_name)
        printer_layout.addWidget(self.refresh_printers_btn)
        thermal_layout.addRow("打印机:", printer_layout)
        
        # 打印分辨率
        self.print_resolution = QComboBox()
        self.print_resolution.addItems(["203 DPI", "300 DPI", "600 DPI"])
        self.print_resolution.setCurrentText("203 DPI")
        thermal_layout.addRow("打印分辨率:", self.print_resolution)
        
        # 打印质量
        self.print_quality = QComboBox()
        self.print_quality.addItems(["草稿", "正常", "高质量"])
        self.print_quality.setCurrentText("正常")
        thermal_layout.addRow("打印质量:", self.print_quality)
        
        # 打印速度
        self.print_speed = QComboBox()
        self.print_speed.addItems(["慢速", "正常", "快速"])
        self.print_speed.setCurrentText("正常")
        thermal_layout.addRow("打印速度:", self.print_speed)

        # 打印方向/旋转
        self.print_orientation = QComboBox()
        self.print_orientation.addItems(["自动", "纵向", "横向", "旋转90°", "旋转180°", "旋转270°"]) 
        self.print_orientation.setCurrentText("自动")
        thermal_layout.addRow("打印方向:", self.print_orientation)
        
        layout.addWidget(thermal_group)
        
        # 标签预设尺寸
        preset_group = QGroupBox("标签预设尺寸")
        preset_group.setStyleSheet(self.get_group_style())
        preset_layout = QFormLayout(preset_group)
        
        self.label_preset = QComboBox()
        self.label_preset.addItems([
            "80x50mm (热敏标签)",
            "100x60mm (快递标签)",
            "100x70mm (快递标签-宽版)",
            "100x80mm (物流标签)",
            "120x80mm (大型标签)",
            "自定义尺寸"
        ])
        # 默认给到更常用的100x70mm，如果数据库有值会在load_all_settings中覆盖
        self.label_preset.setCurrentText("100x70mm (快递标签-宽版)")
        preset_layout.addRow("预设尺寸:", self.label_preset)
        
        # 自定义尺寸设置
        custom_size_layout = QHBoxLayout()
        self.custom_width = QSpinBox()
        self.custom_width.setRange(10, 500)
        self.custom_width.setSuffix(" mm")
        self.custom_width.setValue(80)
        
        self.custom_height = QSpinBox()
        self.custom_height.setRange(10, 500)
        self.custom_height.setSuffix(" mm")
        self.custom_height.setValue(50)
        
        custom_size_layout.addWidget(QLabel("宽度:"))
        custom_size_layout.addWidget(self.custom_width)
        custom_size_layout.addWidget(QLabel("高度:"))
        custom_size_layout.addWidget(self.custom_height)
        custom_size_layout.addStretch()
        
        preset_layout.addRow("自定义尺寸:", custom_size_layout)
        
        layout.addWidget(preset_group)
        
        # 打印选项
        options_group = QGroupBox("打印选项")
        options_group.setStyleSheet(self.get_group_style())
        options_layout = QFormLayout(options_group)
        
        self.auto_cut = QCheckBox("自动切纸")
        self.auto_cut.setChecked(True)
        options_layout.addRow("切纸设置:", self.auto_cut)
        
        self.print_preview = QCheckBox("打印前预览")
        self.print_preview.setChecked(False)
        options_layout.addRow("预览设置:", self.print_preview)
        
        self.save_print_log = QCheckBox("保存打印日志")
        self.save_print_log.setChecked(True)
        options_layout.addRow("日志设置:", self.save_print_log)
        
        layout.addWidget(options_group)

        # 高级打印设置
        advanced_group = QGroupBox("高级打印设置")
        advanced_group.setStyleSheet(self.get_group_style())
        advanced_layout = QFormLayout(advanced_group)

        self.print_density = QComboBox()
        self.print_density.addItems(["低", "正常", "高", "超高"]) 
        advanced_layout.addRow("打印浓度:", self.print_density)

        self.print_inverse = QCheckBox("反色打印")
        advanced_layout.addRow("颜色模式:", self.print_inverse)

        self.print_centered = QCheckBox("居中打印")
        self.print_centered.setChecked(True)
        advanced_layout.addRow("版面位置:", self.print_centered)

        layout.addWidget(advanced_group)

        # 校准与偏移
        calibration_group = QGroupBox("校准与偏移")
        calibration_group.setStyleSheet(self.get_group_style())
        calibration_layout = QFormLayout(calibration_group)

        self.offset_x_mm = QDoubleSpinBox()
        self.offset_x_mm.setRange(-50.0, 50.0)
        self.offset_x_mm.setDecimals(1)
        self.offset_x_mm.setSuffix(" mm")
        self.offset_x_mm.setValue(0.0)
        calibration_layout.addRow("X偏移:", self.offset_x_mm)

        self.offset_y_mm = QDoubleSpinBox()
        self.offset_y_mm.setRange(-50.0, 50.0)
        self.offset_y_mm.setDecimals(1)
        self.offset_y_mm.setSuffix(" mm")
        self.offset_y_mm.setValue(0.0)
        calibration_layout.addRow("Y偏移:", self.offset_y_mm)

        self.scale_percent = QSpinBox()
        self.scale_percent.setRange(50, 200)
        self.scale_percent.setSuffix(" %")
        self.scale_percent.setValue(100)
        calibration_layout.addRow("缩放比例:", self.scale_percent)

        self.extra_margin_mm = QDoubleSpinBox()
        self.extra_margin_mm.setRange(0.0, 20.0)
        self.extra_margin_mm.setDecimals(1)
        self.extra_margin_mm.setSuffix(" mm")
        self.extra_margin_mm.setValue(0.0)
        calibration_layout.addRow("额外边距:", self.extra_margin_mm)

        hint = QLabel("提示：如出现偏移或裁切不齐，可调节X/Y偏移与额外边距；缩放比例用于整体缩放以适配不同纸张与打印机驱动。")
        hint.setStyleSheet("color: #666;")
        calibration_layout.addRow("说明:", hint)

        layout.addWidget(calibration_group)
        
        # 测试打印
        test_group = QGroupBox("测试打印")
        test_group.setStyleSheet(self.get_group_style())
        test_layout = QVBoxLayout(test_group)
        
        test_buttons = QHBoxLayout()
        self.test_print_btn = QPushButton("测试打印")
        self.print_config_btn = QPushButton("打印配置页")
        
        for btn in [self.test_print_btn, self.print_config_btn]:
            btn.setStyleSheet(self.get_button_style())
            test_buttons.addWidget(btn)
        
        test_buttons.addStretch()
        test_layout.addLayout(test_buttons)
        
        layout.addWidget(test_group)
        
        # 连接事件
        self.refresh_printers_btn.clicked.connect(self.refresh_printer_list)
        self.label_preset.currentTextChanged.connect(self.on_preset_changed)
        self.test_print_btn.clicked.connect(self.test_print)
        self.print_config_btn.clicked.connect(self.print_config_page)
        
        # 初始化打印机列表
        self.refresh_printer_list()
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_ui_settings(self):
        """创建界面设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_group.setStyleSheet(self.get_group_style())
        theme_layout = QFormLayout(theme_group)
        
        self.theme = QComboBox()
        self.theme.addItems(["默认", "深色", "浅色"])
        theme_layout.addRow("主题:", self.theme)

        self.ui_primary_color = QComboBox()
        self.ui_primary_color.addItems(["蓝色", "绿色", "紫色", "橙色", "红色"]) 
        theme_layout.addRow("主色:", self.ui_primary_color)
        
        self.language = QComboBox()
        self.language.addItems(["中文", "English"])
        theme_layout.addRow("语言:", self.language)
        
        layout.addWidget(theme_group)
        
        # 字体设置
        font_group = QGroupBox("字体设置")
        font_group.setStyleSheet(self.get_group_style())
        font_layout = QFormLayout(font_group)
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.font_size.setSuffix(" px")
        font_layout.addRow("字体大小:", self.font_size)
        
        layout.addWidget(font_group)
        
        # 界面行为设置
        behavior_group = QGroupBox("界面行为")
        behavior_group.setStyleSheet(self.get_group_style())
        behavior_layout = QFormLayout(behavior_group)
        
        self.auto_save_window_state = QCheckBox("自动保存窗口状态")
        behavior_layout.addRow("窗口状态:", self.auto_save_window_state)
        
        self.show_tooltips = QCheckBox("显示工具提示")
        behavior_layout.addRow("工具提示:", self.show_tooltips)

        self.ui_compact_mode = QCheckBox("紧凑模式（减少间距，更多信息可视）")
        behavior_layout.addRow("布局密度:", self.ui_compact_mode)
        
        layout.addWidget(behavior_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_database_settings(self):
        """创建数据库设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 数据库信息
        info_group = QGroupBox("数据库信息")
        info_group.setStyleSheet(self.get_group_style())
        info_layout = QFormLayout(info_group)
        
        self.db_path_label = QLabel()
        info_layout.addRow("数据库路径:", self.db_path_label)
        
        self.db_size_label = QLabel()
        info_layout.addRow("数据库大小:", self.db_size_label)
        
        layout.addWidget(info_group)
        
        # 数据库维护
        maintenance_group = QGroupBox("数据库维护")
        maintenance_group.setStyleSheet(self.get_group_style())
        maintenance_layout = QFormLayout(maintenance_group)

        self.auto_vacuum = QCheckBox("启用自动清理")
        maintenance_layout.addRow("自动清理:", self.auto_vacuum)

        # 性能/模式选项
        self.enable_wal = QCheckBox("启用WAL模式（提升并发性能）")
        maintenance_layout.addRow("日志模式:", self.enable_wal)
        
        # 维护操作按钮
        maintenance_buttons = QHBoxLayout()
        self.vacuum_btn = QPushButton("立即清理")
        self.backup_db_btn = QPushButton("备份数据库")
        self.repair_db_btn = QPushButton("修复数据库")
        
        for btn in [self.vacuum_btn, self.backup_db_btn, self.repair_db_btn]:
            btn.setStyleSheet(self.get_button_style())
            maintenance_buttons.addWidget(btn)
        
        # 事件绑定
        self.vacuum_btn.clicked.connect(self.on_vacuum_now)
        self.backup_db_btn.clicked.connect(self.on_backup_now)
        self.repair_db_btn.clicked.connect(self.on_repair_db_clicked)
        
        maintenance_buttons.addStretch()
        maintenance_layout.addRow("维护操作:", maintenance_buttons)
        
        layout.addWidget(maintenance_group)
        
        # 最高权限删除（管理员）
        admin_group = QGroupBox("最高权限删除（管理员）")
        admin_group.setStyleSheet(self.get_group_style())
        admin_layout = QVBoxLayout(admin_group)
        
        # 登录区域
        login_form = QFormLayout()
        self.admin_username_edit = QLineEdit()
        self.admin_username_edit.setPlaceholderText("管理员账号（默认 admin）")
        self.admin_password_edit = QLineEdit()
        self.admin_password_edit.setPlaceholderText("密码")
        self.admin_password_edit.setEchoMode(QLineEdit.Password)
        login_btns = QHBoxLayout()
        self.admin_login_btn = QPushButton("登录")
        self.admin_logout_btn = QPushButton("注销")
        self.admin_set_password_btn = QPushButton("首次设置/重置密码")
        for btn in [self.admin_login_btn, self.admin_logout_btn, self.admin_set_password_btn]:
            btn.setStyleSheet(self.get_button_style())
            login_btns.addWidget(btn)
        login_btns.addStretch()
        login_form.addRow("账号:", self.admin_username_edit)
        login_form.addRow("密码:", self.admin_password_edit)
        login_form.addRow("操作:", login_btns)
        admin_layout.addLayout(login_form)
        
        # 查询与删除区域（仅登录后启用）
        query_group = QGroupBox("数据查询与批量删除")
        query_group.setStyleSheet(self.get_group_style())
        query_layout = QFormLayout(query_group)
        
        self.delete_type_combo = QComboBox()
        self.delete_type_combo.addItems(["板件", "包裹", "托盘"])
        query_layout.addRow("数据类型:", self.delete_type_combo)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键字（ID/编码/编号/名称），留空加载最近数据")
        query_layout.addRow("查询条件:", self.search_input)
        
        btns = QHBoxLayout()
        self.search_btn = QPushButton("查询")
        self.select_all_btn = QPushButton("全选")
        self.clear_selection_btn = QPushButton("全不选")
        self.delete_selected_btn = QPushButton("批量删除（二次确认）")
        for b in [self.search_btn, self.select_all_btn, self.clear_selection_btn, self.delete_selected_btn]:
            b.setStyleSheet(self.get_button_style())
            btns.addWidget(b)
        btns.addStretch()
        query_layout.addRow("操作:", btns)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels(["选中", "ID", "订单ID", "主标识", "辅助标识", "状态", "创建时间", "表名"])
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        admin_layout.addWidget(query_group)
        admin_layout.addWidget(self.results_table)
        
        # 初始禁用查询/删除控件，登录后启用
        for w in [self.delete_type_combo, self.search_input, self.search_btn, self.select_all_btn, self.clear_selection_btn, self.delete_selected_btn, self.results_table]:
            w.setEnabled(False)
        
        # 事件连接
        self.admin_login_btn.clicked.connect(self.on_admin_login_clicked)
        self.admin_logout_btn.clicked.connect(self.on_admin_logout_clicked)
        self.admin_set_password_btn.clicked.connect(self.on_set_admin_password_clicked)
        self.search_btn.clicked.connect(self.admin_search_items)
        self.select_all_btn.clicked.connect(lambda: self._admin_select_all(True))
        self.clear_selection_btn.clicked.connect(lambda: self._admin_select_all(False))
        self.delete_selected_btn.clicked.connect(self.admin_delete_selected_clicked)
        
        layout.addWidget(admin_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
        
    # =========== 管理员最高权限删除：方法实现 ==========
    def _set_admin_controls_enabled(self, enabled: bool):
        for w in [self.delete_type_combo, self.search_input, self.search_btn, self.select_all_btn, self.clear_selection_btn, self.delete_selected_btn, self.results_table]:
            try:
                w.setEnabled(bool(enabled))
            except Exception:
                pass

    def on_admin_login_clicked(self):
        try:
            username = (self.admin_username_edit.text() or '').strip() or 'admin'
            password = self.admin_password_edit.text() or ''
            stored_hash = self.db.get_setting('admin_password_hash', None)
            stored_salt = self.db.get_setting('admin_password_salt', None)
            import hashlib
            if stored_hash and stored_salt:
                calc = hashlib.sha256((stored_salt + password).encode('utf-8')).hexdigest()
                if calc != stored_hash:
                    QMessageBox.warning(self, "登录失败", "密码不正确。")
                    return
            else:
                # 未设置密码时使用默认口令：admin
                if password != 'admin':
                    QMessageBox.warning(self, "登录失败", "尚未设置管理员密码。请使用默认口令：admin，或先设置新密码后再登录。")
                    return
            self.is_admin_authenticated = True
            self.admin_user_name = username
            self._set_admin_controls_enabled(True)
            QMessageBox.information(self, "成功", "管理员已登录。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"登录处理失败：{e}")

    def on_admin_logout_clicked(self):
        try:
            self.is_admin_authenticated = False
            self.admin_user_name = None
            self._set_admin_controls_enabled(False)
            try:
                self.results_table.setRowCount(0)
            except Exception:
                pass
            QMessageBox.information(self, "成功", "已注销管理员登录。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"注销处理失败：{e}")

    def on_set_admin_password_clicked(self):
        try:
            new_pwd = self.admin_password_edit.text() or ''
            if not new_pwd:
                QMessageBox.warning(self, "提示", "请输入新密码后再点击此按钮。")
                return
            import hashlib, os
            salt = os.urandom(16).hex()
            hashed = hashlib.sha256((salt + new_pwd).encode('utf-8')).hexdigest()
            self.db.set_setting('admin_password_salt', salt)
            self.db.set_setting('admin_password_hash', hashed)
            QMessageBox.information(self, "成功", "管理员密码已设置，请使用新密码登录。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置密码失败：{e}")

    def _fill_admin_results(self, rows, table_name: str):
        try:
            self.results_table.setRowCount(0)
            for r_idx, row in enumerate(rows):
                self.results_table.insertRow(r_idx)
                chk_item = QTableWidgetItem()
                chk_item.setCheckState(Qt.Unchecked)
                self.results_table.setItem(r_idx, 0, chk_item)
                self.results_table.setItem(r_idx, 1, QTableWidgetItem(str(row[0])))  # ID
                self.results_table.setItem(r_idx, 2, QTableWidgetItem(str(row[1] if row[1] is not None else '')))  # 订单ID
                self.results_table.setItem(r_idx, 3, QTableWidgetItem(str(row[2] if row[2] is not None else '')))  # 主标识
                self.results_table.setItem(r_idx, 4, QTableWidgetItem(str(row[3] if row[3] is not None else '')))  # 辅助标识
                self.results_table.setItem(r_idx, 5, QTableWidgetItem(str(row[4] if row[4] is not None else '')))  # 状态
                self.results_table.setItem(r_idx, 6, QTableWidgetItem(str(row[5] if row[5] is not None else '')))  # 创建时间
                self.results_table.setItem(r_idx, 7, QTableWidgetItem(table_name))  # 表名
        except Exception as e:
            QMessageBox.critical(self, "错误", f"渲染结果失败：{e}")

    def admin_search_items(self):
        try:
            if not self.is_admin_authenticated:
                QMessageBox.warning(self, "提示", "请先登录管理员。")
                return
            type_text = self.delete_type_combo.currentText()
            keyword = (self.search_input.text() or '').strip()
            conn = self.db.get_connection()
            cursor = conn.cursor()
            try:
                if type_text == '板件':
                    sql = "SELECT id, order_id, component_code, component_name, status, created_at FROM components"
                    params = []
                    if keyword:
                        sql += " WHERE component_code LIKE ? OR component_name LIKE ? OR CAST(id AS TEXT)=? OR CAST(order_id AS TEXT)=?"
                        kw = f"%{keyword}%"
                        params = [kw, kw, keyword, keyword]
                    sql += " ORDER BY created_at DESC, id DESC LIMIT 200"
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    self._fill_admin_results(rows, 'components')
                elif type_text == '包裹':
                    sql = "SELECT id, order_id, package_number, component_count, status, created_at FROM packages"
                    params = []
                    if keyword:
                        sql += " WHERE package_number LIKE ? OR CAST(id AS TEXT)=? OR CAST(order_id AS TEXT)=?"
                        kw = f"%{keyword}%"
                        params = [kw, keyword, keyword]
                    sql += " ORDER BY created_at DESC, id DESC LIMIT 200"
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    self._fill_admin_results(rows, 'packages')
                else:
                    sql = "SELECT id, order_id, pallet_number, pallet_type, status, created_at FROM pallets"
                    params = []
                    if keyword:
                        sql += " WHERE pallet_number LIKE ? OR CAST(id AS TEXT)=? OR CAST(order_id AS TEXT)=?"
                        kw = f"%{keyword}%"
                        params = [kw, keyword, keyword]
                    sql += " ORDER BY created_at DESC, id DESC LIMIT 200"
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    self._fill_admin_results(rows, 'pallets')
            finally:
                conn.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查询失败：{e}")

    def _admin_select_all(self, select: bool):
        try:
            rows = self.results_table.rowCount()
            for i in range(rows):
                item = self.results_table.item(i, 0)
                if item is None:
                    item = QTableWidgetItem()
                    self.results_table.setItem(i, 0, item)
                item.setCheckState(Qt.Checked if select else Qt.Unchecked)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择失败：{e}")

    def admin_delete_selected_clicked(self):
        try:
            if not self.is_admin_authenticated:
                QMessageBox.warning(self, "提示", "请先登录管理员。")
                return
            # 二次确认
            try:
                needs_confirm = self.db.get_setting('confirm_delete', 'true') == 'true'
            except Exception:
                needs_confirm = True
            if needs_confirm:
                ret = QMessageBox.question(self, "确认删除", "将批量物理删除所选记录，确定继续？", QMessageBox.Yes | QMessageBox.No)
                if ret != QMessageBox.Yes:
                    return
            rows = self.results_table.rowCount()
            deleted_counts = {'components': 0, 'packages': 0, 'pallets': 0}
            # 云端删除：收集主标识
            comp_codes = []
            pkg_numbers = []
            pal_numbers = []
            conn = self.db.get_connection()
            cursor = conn.cursor()
            try:
                for i in range(rows):
                    item = self.results_table.item(i, 0)
                    if not item or item.checkState() != Qt.Checked:
                        continue
                    tbl = self.results_table.item(i, 7).text()
                    id_val = self.results_table.item(i, 1).text()
                    if not id_val or not tbl:
                        continue
                    try:
                        if tbl == 'components':
                            # 收集 component_code
                            comp_code = ''
                            try:
                                pri_item = self.results_table.item(i, 3)
                                comp_code = pri_item.text() if pri_item else ''
                                if not comp_code:
                                    cursor.execute("SELECT component_code FROM components WHERE id=?", (id_val,))
                                    r = cursor.fetchone()
                                    comp_code = (r[0] if r else '') or ''
                                if comp_code:
                                    comp_codes.append(comp_code)
                            except Exception:
                                pass
                            cursor.execute("DELETE FROM components WHERE id=?", (id_val,))
                            if 'components' in deleted_counts:
                                deleted_counts['components'] += cursor.rowcount if hasattr(cursor, 'rowcount') else 1
                        elif tbl == 'packages':
                            # 收集 package_number
                            pkg_no = ''
                            try:
                                pri_item = self.results_table.item(i, 3)
                                pkg_no = pri_item.text() if pri_item else ''
                                if not pkg_no:
                                    cursor.execute("SELECT package_number FROM packages WHERE id=?", (id_val,))
                                    r = cursor.fetchone()
                                    pkg_no = (r[0] if r else '') or ''
                                if pkg_no:
                                    pkg_numbers.append(pkg_no)
                            except Exception:
                                pass
                            # 解除组件关联并恢复状态
                            cursor.execute("UPDATE components SET package_id = NULL, status = 'pending' WHERE package_id = ?", (id_val,))
                            # 删除与托盘的关联
                            cursor.execute("DELETE FROM pallet_packages WHERE package_id = ?", (id_val,))
                            # 物理删除包裹
                            cursor.execute("DELETE FROM packages WHERE id = ?", (id_val,))
                            if 'packages' in deleted_counts:
                                deleted_counts['packages'] += cursor.rowcount if hasattr(cursor, 'rowcount') else 1
                        elif tbl == 'pallets':
                            # 收集 pallet_number
                            pal_no = ''
                            try:
                                pri_item = self.results_table.item(i, 3)
                                pal_no = pri_item.text() if pri_item else ''
                                if not pal_no:
                                    cursor.execute("SELECT pallet_number FROM pallets WHERE id=?", (id_val,))
                                    r = cursor.fetchone()
                                    pal_no = (r[0] if r else '') or ''
                                if pal_no:
                                    pal_numbers.append(pal_no)
                            except Exception:
                                pass
                            # 删除与包裹的关联
                            cursor.execute("DELETE FROM pallet_packages WHERE pallet_id = ?", (id_val,))
                            # 删除虚拟项（如有）
                            try:
                                cursor.execute("DELETE FROM virtual_items WHERE pallet_id = ?", (id_val,))
                            except Exception:
                                pass
                            # 物理删除托盘
                            cursor.execute("DELETE FROM pallets WHERE id = ?", (id_val,))
                            if 'pallets' in deleted_counts:
                                deleted_counts['pallets'] += cursor.rowcount if hasattr(cursor, 'rowcount') else 1
                        else:
                            cursor.execute(f"DELETE FROM {tbl} WHERE id=?", (id_val,))
                    except Exception as e:
                        print(f"删除 {tbl} id={id_val} 失败: {e}")
                conn.commit()
            finally:
                conn.close()
            # 记录操作日志
            try:
                self.db.log_operation('admin_delete_physical', json.dumps({'deleted': deleted_counts, 'user': self.admin_user_name}, ensure_ascii=False))
            except Exception:
                pass
            # 云端删除同步（异步入队）
            try:
                svc = self.cloud_sync_service if hasattr(self, 'cloud_sync_service') and self.cloud_sync_service else get_sync_service()
                if comp_codes:
                    svc.trigger_sync('delete_components', {'items': [{'component_code': c} for c in comp_codes]}, force=True)
                if pkg_numbers:
                    svc.trigger_sync('delete_packages', {'items': [{'package_number': p} for p in pkg_numbers]}, force=True)
                if pal_numbers:
                    svc.trigger_sync('delete_pallets', {'items': [{'pallet_number': p} for p in pal_numbers]}, force=True)
            except Exception as e:
                print(f"触发云端删除任务失败: {e}")
            # 发出联动信号
            try:
                if deleted_counts['components'] > 0:
                    self.admin_components_deleted.emit()
                if deleted_counts['packages'] > 0:
                    self.admin_packages_deleted.emit()
                if deleted_counts['pallets'] > 0:
                    self.admin_pallets_deleted.emit()
            except Exception:
                pass
            # 刷新查询结果
            try:
                self.admin_search_items()
            except Exception:
                pass
            QMessageBox.information(self, "成功", f"已批量删除。\n板件: {deleted_counts['components']}，包裹: {deleted_counts['packages']}，托盘: {deleted_counts['pallets']}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除处理失败：{e}")
        
    
    def create_log_settings(self):
        """创建日志设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 日志级别设置
        level_group = QGroupBox("日志级别设置")
        level_group.setStyleSheet(self.get_group_style())
        level_layout = QFormLayout(level_group)
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        level_layout.addRow("日志级别:", self.log_level)
        
        self.log_retention_days = QSpinBox()
        self.log_retention_days.setRange(1, 365)
        self.log_retention_days.setSuffix(" 天")
        level_layout.addRow("日志保留天数:", self.log_retention_days)
        
        layout.addWidget(level_group)
        
        # 日志文件设置
        file_group = QGroupBox("日志文件设置")
        file_group.setStyleSheet(self.get_group_style())
        file_layout = QFormLayout(file_group)
        
        self.max_log_size = QSpinBox()
        self.max_log_size.setRange(1, 1000)
        self.max_log_size.setSuffix(" MB")
        file_layout.addRow("单个日志文件最大大小:", self.max_log_size)
        
        self.max_log_files = QSpinBox()
        self.max_log_files.setRange(1, 100)
        self.max_log_files.setSuffix(" 个")
        file_layout.addRow("最大日志文件数:", self.max_log_files)
        
        layout.addWidget(file_group)
        
        # 日志操作
        operation_group = QGroupBox("日志操作")
        operation_group.setStyleSheet(self.get_group_style())
        operation_layout = QFormLayout(operation_group)
        
        log_buttons = QHBoxLayout()
        self.view_logs_btn = QPushButton("查看日志")
        self.clear_logs_btn = QPushButton("清空日志")
        self.export_logs_btn = QPushButton("导出日志")
        
        for btn in [self.view_logs_btn, self.clear_logs_btn, self.export_logs_btn]:
            btn.setStyleSheet(self.get_button_style())
            log_buttons.addWidget(btn)
        
        log_buttons.addStretch()
        operation_layout.addRow("日志管理:", log_buttons)
        
        layout.addWidget(operation_group)

        # 日志上传
        upload_group = QGroupBox("日志上传")
        upload_group.setStyleSheet(self.get_group_style())
        upload_layout = QFormLayout(upload_group)

        self.upload_logs_enabled = QCheckBox("启用自动上传日志")
        upload_layout.addRow("自动上传:", self.upload_logs_enabled)

        self.log_upload_endpoint = QLineEdit()
        self.log_upload_endpoint.setPlaceholderText("https://example.com/api/upload-logs")
        upload_layout.addRow("上传地址:", self.log_upload_endpoint)

        layout.addWidget(upload_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_system_behavior_settings(self):
        """创建系统行为设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 启动设置
        startup_group = QGroupBox("启动设置")
        startup_group.setStyleSheet(self.get_group_style())
        startup_layout = QFormLayout(startup_group)
        
        self.auto_start_with_system = QCheckBox("开机自动启动")
        startup_layout.addRow("自动启动:", self.auto_start_with_system)
        
        self.remember_last_tab = QCheckBox("记住上次打开的标签页")
        startup_layout.addRow("标签页记忆:", self.remember_last_tab)

        self.start_minimized = QCheckBox("启动最小化到托盘/任务栏")
        startup_layout.addRow("启动状态:", self.start_minimized)
        
        layout.addWidget(startup_group)
        
        # 操作确认设置
        confirm_group = QGroupBox("操作确认设置")
        confirm_group.setStyleSheet(self.get_group_style())
        confirm_layout = QFormLayout(confirm_group)
        
        self.confirm_delete = QCheckBox("删除操作需要确认")
        confirm_layout.addRow("删除确认:", self.confirm_delete)
        
        self.confirm_clear = QCheckBox("清空操作需要确认")
        confirm_layout.addRow("清空确认:", self.confirm_clear)
        
        layout.addWidget(confirm_group)
        
        # 性能设置
        performance_group = QGroupBox("性能设置")
        performance_group.setStyleSheet(self.get_group_style())
        performance_layout = QFormLayout(performance_group)

        self.max_recent_files = QSpinBox()
        self.max_recent_files.setRange(5, 50)
        self.max_recent_files.setSuffix(" 个")
        performance_layout.addRow("最大最近文件数:", self.max_recent_files)

        self.cache_size = QSpinBox()
        self.cache_size.setRange(10, 1000)
        self.cache_size.setSuffix(" MB")
        performance_layout.addRow("缓存大小:", self.cache_size)

        # 分页大小设置
        self.pallets_page_size = QSpinBox()
        self.pallets_page_size.setRange(10, 1000)
        self.pallets_page_size.setSuffix(" 行")
        performance_layout.addRow("托盘列表每页:", self.pallets_page_size)

        self.packages_page_size = QSpinBox()
        self.packages_page_size.setRange(10, 1000)
        self.packages_page_size.setSuffix(" 行")
        performance_layout.addRow("包裹列表每页:", self.packages_page_size)
        
        layout.addWidget(performance_group)

        # 安全与空闲
        security_group = QGroupBox("安全与空闲")
        security_group.setStyleSheet(self.get_group_style())
        security_layout = QFormLayout(security_group)

        self.auto_lock_enabled = QCheckBox("空闲时自动锁定")
        security_layout.addRow("自动锁定:", self.auto_lock_enabled)

        self.auto_lock_minutes = QSpinBox()
        self.auto_lock_minutes.setRange(1, 120)
        self.auto_lock_minutes.setSuffix(" 分钟")
        security_layout.addRow("空闲时间:", self.auto_lock_minutes)

        layout.addWidget(security_group)

        # 云同步设置（仅保留手动上传按钮，移除自动上传与时间设置）
        cloud_group = QGroupBox("云同步设置")
        cloud_group.setStyleSheet(self.get_group_style())
        cloud_layout = QFormLayout(cloud_group)

        btn_layout = QHBoxLayout()
        self.sync_now_btn = QPushButton("立即同步最近更新")
        self.full_sync_btn = QPushButton("执行全量同步")
        self.clear_then_full_btn = QPushButton("清空云端并全量同步")
        self.sync_now_btn.setStyleSheet(self.get_button_style())
        self.full_sync_btn.setStyleSheet(self.get_button_style())
        self.clear_then_full_btn.setStyleSheet(self.get_button_style())
        self.sync_now_btn.clicked.connect(self.on_sync_now)
        self.full_sync_btn.clicked.connect(self.on_full_sync_now)
        self.clear_then_full_btn.clicked.connect(self.on_clear_cloud_and_full_sync_clicked)
        btn_layout.addWidget(self.sync_now_btn)
        btn_layout.addWidget(self.full_sync_btn)
        btn_layout.addWidget(self.clear_then_full_btn)
        cloud_layout.addRow("操作:", btn_layout)

        layout.addWidget(cloud_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    def create_backup_settings(self):
        """创建备份设置页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        
        # 自动备份设置
        auto_group = QGroupBox("自动备份设置")
        auto_group.setStyleSheet(self.get_group_style())
        auto_layout = QFormLayout(auto_group)
        
        self.auto_backup_enabled = QCheckBox("启用自动备份")
        auto_layout.addRow("自动备份:", self.auto_backup_enabled)
        
        self.backup_interval = QSpinBox()
        self.backup_interval.setRange(1, 30)
        self.backup_interval.setSuffix(" 天")
        auto_layout.addRow("备份间隔:", self.backup_interval)
        
        self.max_backup_files = QSpinBox()
        self.max_backup_files.setRange(1, 100)
        self.max_backup_files.setSuffix(" 个")
        auto_layout.addRow("最大备份文件数:", self.max_backup_files)

        self.backup_compress_enabled = QCheckBox("压缩备份（节省空间）")
        auto_layout.addRow("压缩备份:", self.backup_compress_enabled)
        
        layout.addWidget(auto_group)
        
        # 备份路径设置
        path_group = QGroupBox("备份路径设置")
        path_group.setStyleSheet(self.get_group_style())
        path_layout = QFormLayout(path_group)
        
        backup_path_layout = QHBoxLayout()
        self.backup_path_edit = QLineEdit()
        self.browse_backup_path_btn = QPushButton("浏览")
        self.browse_backup_path_btn.setStyleSheet(self.get_button_style())
        backup_path_layout.addWidget(self.backup_path_edit)
        backup_path_layout.addWidget(self.browse_backup_path_btn)
        
        # 事件绑定：选择备份路径
        self.browse_backup_path_btn.clicked.connect(self.on_browse_backup_path)
        
        path_layout.addRow("备份路径:", backup_path_layout)
        
        layout.addWidget(path_group)
        
        # 手动备份操作
        manual_group = QGroupBox("手动备份操作")
        manual_group.setStyleSheet(self.get_group_style())
        manual_layout = QFormLayout(manual_group)
        
        backup_buttons = QHBoxLayout()
        self.backup_now_btn = QPushButton("立即备份")
        self.restore_backup_btn = QPushButton("恢复备份")
        self.manage_backups_btn = QPushButton("管理备份")
        
        for btn in [self.backup_now_btn, self.restore_backup_btn, self.manage_backups_btn]:
            btn.setStyleSheet(self.get_button_style())
            backup_buttons.addWidget(btn)
        
        # 事件绑定
        self.backup_now_btn.clicked.connect(self.on_backup_now)
        self.restore_backup_btn.clicked.connect(self.on_restore_backup)
        self.manage_backups_btn.clicked.connect(self.on_manage_backups)
        
        backup_buttons.addStretch()
        manual_layout.addRow("备份操作:", backup_buttons)
        
        layout.addWidget(manual_group)
        
        layout.addStretch()
        self.stacked_widget.addWidget(widget)
    
    # 底部按钮已上移为顶部工具区，此方法不再使用，保留以兼容旧调用但不执行
    def create_bottom_buttons(self, main_layout):
        pass
    
    def get_group_style(self):
        """获取组框样式"""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 12px;
                padding: 12px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                color: #2c3e50;
                background-color: #ffffff;
            }
        """
    
    def get_button_style(self):
        """获取按钮样式"""
        return """
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0069d9;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
        """
    
    def on_nav_changed(self, current, previous):
        """导航项变更事件"""
        if current:
            key = current.data(Qt.UserRole)
            nav_titles = {
                "packaging": "📦 包装设置",
                "scan_config": "🔧 扫码配置",
                "import_config": "📄 导入配置", 
                "printer_settings": "🖨️ 打印机设置",
                "ui_settings": "🎨 界面设置",
                "database": "💾 数据库设置",
                "log_settings": "📊 日志设置",
                "system_behavior": "⚡ 系统行为",
                "backup_settings": "🔄 备份设置"
            }
            
            self.content_title.setText(nav_titles.get(key, "设置"))
            
            # 切换到对应的设置页面
            nav_indices = {
                "packaging": 0,
                "scan_config": 1,
                "import_config": 2,
                "printer_settings": 3,
                "ui_settings": 4,
                "database": 5,
                "log_settings": 6,
                "system_behavior": 7,
                "backup_settings": 8
            }
            
            index = nav_indices.get(key, 0)
            self.stacked_widget.setCurrentIndex(index)

    def load_scan_configs(self):
        """加载扫码配置"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, config_name FROM scan_configs ORDER BY config_name')
            configs = cursor.fetchall()
            conn.close()
            
            self.default_scan_config.clear()
            for config_id, config_name in configs:
                self.default_scan_config.addItem(config_name, config_id)
        except Exception as e:
            print(f"加载扫码配置失败: {e}")

    def load_import_configs(self):
        """加载导入配置"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, config_name FROM import_configs ORDER BY config_name')
            configs = cursor.fetchall()
            conn.close()
            
            self.default_import_config.clear()
            for config_id, config_name in configs:
                self.default_import_config.addItem(config_name, config_id)
        except Exception as e:
            print(f"加载导入配置失败: {e}")

    # 标签模板设置页已移除

    def load_all_settings(self):
        """加载所有系统设置"""
        # 包装设置
        self.package_number_format.setText(self.db.get_setting('package_number_format', 'YYYYMMDD{:04d}'))
        self.pallet_number_format.setText(self.db.get_setting('pallet_number_format', 'T{date}{:04d}'))
        self.virtual_pallet_format.setText(self.db.get_setting('virtual_pallet_format', 'VT{date}{:04d}'))
        self.auto_complete_code.setText(self.db.get_setting('auto_complete_code', 'COMPLETE'))
        
        # 默认配置
        default_scan = self.db.get_setting('default_scan_config', '1')
        for i in range(self.default_scan_config.count()):
            if str(self.default_scan_config.itemData(i)) == default_scan:
                self.default_scan_config.setCurrentIndex(i)
                break
        
        default_import = self.db.get_setting('default_import_config', '1')
        for i in range(self.default_import_config.count()):
            if str(self.default_import_config.itemData(i)) == default_import:
                self.default_import_config.setCurrentIndex(i)
                break
        
        # 标签模板设置页面已移除，默认模板不再从此界面加载
        
        # 系统行为设置
        self.auto_backup_enabled.setChecked(self.db.get_setting('auto_backup_enabled', 'false') == 'true')
        self.backup_interval.setValue(int(self.db.get_setting('backup_interval', '7')))
        self.max_backup_files.setValue(int(self.db.get_setting('max_backup_files', '10')))
        
        # 界面设置
        theme = self.db.get_setting('theme', '默认')
        theme_index = self.theme.findText(theme)
        if theme_index >= 0:
            self.theme.setCurrentIndex(theme_index)
        
        language = self.db.get_setting('language', '中文')
        language_index = self.language.findText(language)
        if language_index >= 0:
            self.language.setCurrentIndex(language_index)
        
        self.font_size.setValue(int(self.db.get_setting('font_size', '12')))
        
        # 数据库设置
        self.db_path_label.setText(self.db.db_path)
        # 更新数据库大小/路径信息
        self.update_db_info()
        self.auto_vacuum.setChecked(self.db.get_setting('auto_vacuum', 'true') == 'true')
        self.enable_wal.setChecked(self.db.get_setting('enable_wal', 'true') == 'true')
        
        # 日志设置
        log_level = self.db.get_setting('log_level', 'INFO')
        log_level_index = self.log_level.findText(log_level)
        if log_level_index >= 0:
            self.log_level.setCurrentIndex(log_level_index)
        
        self.log_retention_days.setValue(int(self.db.get_setting('log_retention_days', '30')))
        
        # 新增设置项的默认值（界面/日志/行为等）
        self.auto_save_window_state.setChecked(self.db.get_setting('auto_save_window_state', 'true') == 'true')
        self.show_tooltips.setChecked(self.db.get_setting('show_tooltips', 'true') == 'true')
        self.max_log_size.setValue(int(self.db.get_setting('max_log_size', '10')))
        self.max_log_files.setValue(int(self.db.get_setting('max_log_files', '5')))
        self.auto_start_with_system.setChecked(self.db.get_setting('auto_start_with_system', 'false') == 'true')
        # 启动最小化与空闲自动锁定
        self.start_minimized.setChecked(self.db.get_setting('start_minimized', 'false') == 'true')
        self.auto_lock_enabled.setChecked(self.db.get_setting('auto_lock_enabled', 'false') == 'true')
        try:
            self.auto_lock_minutes.setValue(int(self.db.get_setting('auto_lock_minutes', '15')))
        except Exception:
            self.auto_lock_minutes.setValue(15)
        # 界面扩展
        self.ui_compact_mode.setChecked(self.db.get_setting('ui_compact_mode', 'false') == 'true')
        primary = self.db.get_setting('ui_primary_color', '蓝色')
        idx_primary = self.ui_primary_color.findText(primary)
        if idx_primary >= 0:
            self.ui_primary_color.setCurrentIndex(idx_primary)
        # 日志上传扩展
        self.upload_logs_enabled.setChecked(self.db.get_setting('upload_logs_enabled', 'false') == 'true')
        self.log_upload_endpoint.setText(self.db.get_setting('log_upload_endpoint', ''))
        self.remember_last_tab.setChecked(self.db.get_setting('remember_last_tab', 'true') == 'true')
        self.confirm_delete.setChecked(self.db.get_setting('confirm_delete', 'true') == 'true')
        self.confirm_clear.setChecked(self.db.get_setting('confirm_clear', 'true') == 'true')
        self.max_recent_files.setValue(int(self.db.get_setting('max_recent_files', '10')))
        self.cache_size.setValue(int(self.db.get_setting('cache_size', '100')))
        self.pallets_page_size.setValue(int(self.db.get_setting('pallets_page_size', '100')))
        self.packages_page_size.setValue(int(self.db.get_setting('packages_page_size', '100')))
        self.backup_path_edit.setText(self.db.get_setting('backup_path', './backups'))
        self.backup_compress_enabled.setChecked(self.db.get_setting('backup_compress_enabled', 'true') == 'true')
        
        # 云同步设置已禁用，不再加载任何自动同步相关项
        
        # 打印机设置
        self.printer_name.setCurrentText(self.db.get_setting('printer_name', ''))
        
        print_resolution = self.db.get_setting('print_resolution', '203 DPI')
        resolution_index = self.print_resolution.findText(print_resolution)
        if resolution_index >= 0:
            self.print_resolution.setCurrentIndex(resolution_index)
        
        print_quality = self.db.get_setting('print_quality', '正常')
        quality_index = self.print_quality.findText(print_quality)
        if quality_index >= 0:
            self.print_quality.setCurrentIndex(quality_index)
        
        print_speed = self.db.get_setting('print_speed', '正常')
        speed_index = self.print_speed.findText(print_speed)
        if speed_index >= 0:
            self.print_speed.setCurrentIndex(speed_index)

        # 加载打印方向
        orientation_text = self.db.get_setting('print_orientation', '自动')
        orientation_index = self.print_orientation.findText(orientation_text)
        if orientation_index >= 0:
            self.print_orientation.setCurrentIndex(orientation_index)
        
        label_preset = self.db.get_setting('label_preset', '80x50mm (热敏标签)')
        preset_index = self.label_preset.findText(label_preset)
        if preset_index >= 0:
            self.label_preset.setCurrentIndex(preset_index)
        
        self.custom_width.setValue(int(self.db.get_setting('custom_width', '80')))
        self.custom_height.setValue(int(self.db.get_setting('custom_height', '50')))
        self.auto_cut.setChecked(self.db.get_setting('auto_cut', 'true') == 'true')
        self.print_preview.setChecked(self.db.get_setting('print_preview', 'false') == 'true')
        self.save_print_log.setChecked(self.db.get_setting('save_print_log', 'true') == 'true')
        # 打印扩展项
        density = self.db.get_setting('print_density', '正常')
        idx_density = self.print_density.findText(density)
        if idx_density >= 0:
            self.print_density.setCurrentIndex(idx_density)
        self.print_inverse.setChecked(self.db.get_setting('print_inverse', 'false') == 'true')
        self.print_centered.setChecked(self.db.get_setting('print_centered', 'true') == 'true')

        # 加载校准与偏移
        try:
            self.offset_x_mm.setValue(float(self.db.get_setting('print_offset_x_mm', '0')))
            self.offset_y_mm.setValue(float(self.db.get_setting('print_offset_y_mm', '0')))
        except Exception:
            self.offset_x_mm.setValue(0.0)
            self.offset_y_mm.setValue(0.0)
        try:
            self.scale_percent.setValue(int(self.db.get_setting('print_scale_percent', '100')))
        except Exception:
            self.scale_percent.setValue(100)
        try:
            self.extra_margin_mm.setValue(float(self.db.get_setting('print_extra_margin_mm', '0')))
        except Exception:
            self.extra_margin_mm.setValue(0.0)

    # === 云同步方法 ===
    def _apply_cloud_sync_settings(self):
        """根据界面的设置启动/停止云同步服务与定时器"""
        try:
            enabled = getattr(self, 'auto_sync_enabled', None)
            interval = getattr(self, 'sync_interval_minutes', None)
            if not self.cloud_sync_service:
                print('云同步服务不可用，跳过启动')
                self.cloud_sync_timer.stop()
                return
            is_enabled = bool(enabled and enabled.isChecked())
            minutes = int(interval.value()) if interval else 5
            if is_enabled:
                # 启动服务并根据间隔启动定时器
                try:
                    self.cloud_sync_service.start_sync_service()
                except Exception as e:
                    print(f'启动云同步服务失败: {e}')
                try:
                    self.cloud_sync_timer.start(max(1, minutes) * 60 * 1000)
                except Exception as e:
                    print(f'启动云同步定时器失败: {e}')
            else:
                # 关闭定时器与服务
                try:
                    self.cloud_sync_timer.stop()
                except Exception:
                    pass
                try:
                    # 停止服务，避免后台无意义运行
                    self.cloud_sync_service.stop_sync_service()
                except Exception:
                    pass
        except Exception as e:
            print(f'应用云同步设置失败: {e}')
    
    def _on_cloud_sync_timer(self):
        """定时器回调：触发最近更新的增量同步"""
        try:
            if not self.cloud_sync_service:
                return
            # 若服务未运行，尝试启动
            if not getattr(self.cloud_sync_service, 'running', False):
                try:
                    self.cloud_sync_service.start_sync_service()
                except Exception:
                    pass
            # 以任务形式入队，工作线程会合并批量推送
            self.cloud_sync_service.trigger_sync('component', {})
            self.cloud_sync_service.trigger_sync('package', {})
            self.cloud_sync_service.trigger_sync('pallet', {})
        except Exception as e:
            print(f'自动同步触发失败: {e}')
    
    def on_sync_now(self):
        """立即同步最近更新（按钮）"""
        try:
            if not self.cloud_sync_service:
                QMessageBox.warning(self, "提示", "云同步服务不可用，未能执行同步。")
                return
            # 确保服务正在运行
            if not getattr(self.cloud_sync_service, 'running', False):
                try:
                    self.cloud_sync_service.start_sync_service()
                except Exception as e:
                    print(f'启动云同步服务失败: {e}')
            if not getattr(self.cloud_sync_service, 'running', False):
                QMessageBox.warning(self, "提示", "云同步服务未能启动，请检查 API Key / 环境配置。")
                return
            # 入队最近更新的三类数据（仅手动触发，force=True）
            self.cloud_sync_service.trigger_sync('component', {}, force=True)
            self.cloud_sync_service.trigger_sync('package', {}, force=True)
            self.cloud_sync_service.trigger_sync('pallet', {}, force=True)
            # 弹出简洁进度条对话框（仅显示百分比）
            self._show_upload_progress('正在上传最近更新…')
            QMessageBox.information(self, "成功", "已触发最近更新的云同步任务。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"立即同步失败：{e}")
    
    def on_full_sync_now(self):
        """立即执行全量同步（按钮）"""
        try:
            if not self.cloud_sync_service:
                QMessageBox.warning(self, "提示", "云同步服务不可用，未能执行全量同步。")
                return
            # 确保服务正在运行
            if not getattr(self.cloud_sync_service, 'running', False):
                try:
                    self.cloud_sync_service.start_sync_service()
                except Exception as e:
                    print(f'启动云同步服务失败: {e}')
            if not getattr(self.cloud_sync_service, 'running', False):
                QMessageBox.warning(self, "提示", "云同步服务未能启动，请检查 API Key / 环境配置。")
                return
            # 改为入队 full_sync 任务，避免阻塞（仅手动触发，force=True）
            self.cloud_sync_service.trigger_sync('full_sync', {}, force=True)
            # 弹出简洁进度条对话框（仅显示百分比）
            self._show_upload_progress('全量同步上传进行中…')
            QMessageBox.information(self, "成功", "已触发全量同步任务并入队。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"全量同步失败：{e}")

    def on_clear_cloud_and_full_sync_clicked(self):
        """清空云端并入队一次全量同步（按钮）"""
        try:
            ret = QMessageBox.question(self, "确认操作", "将清空云端 components/packages/pallets 三个集合，并立即入队全量同步任务。确定继续？", QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
            # 获取同步服务实例（优先复用已存在实例，否则获取单例）
            try:
                svc = self.cloud_sync_service if hasattr(self, 'cloud_sync_service') and self.cloud_sync_service else get_sync_service()
            except Exception:
                svc = None
            if not svc:
                QMessageBox.warning(self, "提示", "云同步服务不可用，未能执行该操作。")
                return
            # 确保工作线程已启动
            try:
                if not getattr(svc, 'running', False):
                    svc.start_sync_service()
            except Exception as e:
                print(f'启动云同步服务失败: {e}')
            # 先入队清空集合，再入队全量同步
            try:
                svc.trigger_sync('clear', {'collections': ['components', 'packages', 'pallets']}, force=True)
                svc.trigger_sync('full_sync', {}, force=True)
                QMessageBox.information(self, "成功", "已触发云端清空并入队全量同步任务。")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"触发任务失败：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败：{e}")

    # === 自动备份方法 ===
    def _apply_backup_settings(self):
        """根据设置启动/停止自动备份定时器"""
        try:
            enabled = getattr(self, 'auto_backup_enabled', None)
            interval_days_spin = getattr(self, 'backup_interval', None)
            is_enabled = bool(enabled and enabled.isChecked())
            days = int(interval_days_spin.value()) if interval_days_spin else 7
            if is_enabled:
                try:
                    # 按天间隔运行
                    self.backup_timer.start(max(1, days) * 24 * 60 * 60 * 1000)
                except Exception as e:
                    print(f'启动自动备份定时器失败: {e}')
            else:
                try:
                    self.backup_timer.stop()
                except Exception:
                    pass
        except Exception as e:
            print(f'应用自动备份设置失败: {e}')

    def _on_backup_timer(self):
        """自动备份定时器回调：执行备份并清理旧备份"""
        try:
            # 调用现有的备份逻辑
            self.on_backup_now()
            # 备份完成后清理旧文件
            self._prune_old_backups()
        except Exception as e:
            print(f'自动备份失败: {e}')

    def _prune_old_backups(self):
        """根据最大保留数量删除旧的备份文件"""
        try:
            import os
            max_files_spin = getattr(self, 'max_backup_files', None)
            max_files = int(max_files_spin.value()) if max_files_spin else int(self.db.get_setting('max_backup_files', '10'))
            backup_dir = self.backup_path_edit.text().strip() or os.path.join(os.path.dirname(self.db.db_path), 'backups')
            if not os.path.isdir(backup_dir):
                return
            # 收集 .db 和 .zip 备份文件
            files = []
            for name in os.listdir(backup_dir):
                if name.lower().endswith('.db') or name.lower().endswith('.zip'):
                    full = os.path.join(backup_dir, name)
                    try:
                        mtime = os.path.getmtime(full)
                        files.append((mtime, full))
                    except Exception:
                        pass
            # 按时间新->旧排序
            files.sort(reverse=True)
            # 删除超过保留数量的文件
            if len(files) > max_files:
                for _, path in files[max_files:]:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        except Exception as e:
            print(f'清理旧备份失败: {e}')

    # === 设置导入/导出 ===
    def _safe_json_loads(self, text):
        try:
            if text is None:
                return None
            return json.loads(text)
        except Exception:
            return text

    def _maybe_json_str(self, value):
        try:
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        except Exception:
            return str(value)

    def on_export_settings(self):
        """导出当前系统的所有配置参数到 JSON 文件（含附属配置）"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            from datetime import datetime
            # 选择保存文件
            default_dir = os.path.dirname(getattr(self.db, 'db_path', '')) or os.getcwd()
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = os.path.join(default_dir, f"system_settings_{ts}.json")
            save_path, _ = QFileDialog.getSaveFileName(self, "导出系统设置", default_name, "JSON 文件 (*.json)")
            if not save_path:
                return

            conn = self.db.get_connection()
            cur = conn.cursor()

            # 导出 system_settings 全表
            cur.execute('SELECT setting_key, setting_value, setting_type, description FROM system_settings ORDER BY setting_key')
            s_rows = cur.fetchall()
            system_settings = [
                {
                    'key': r[0],
                    'value': self._safe_json_loads(r[1]),
                    'type': r[2],
                    'description': r[3]
                } for r in s_rows
            ]

            # 导出扫码配置
            try:
                cur.execute('''
                    SELECT config_name, prefix_remove, suffix_remove, extract_start, extract_length, extract_mode, is_default
                    FROM scan_configs ORDER BY config_name
                ''')
                scan_configs = []
                for row in cur.fetchall():
                    scan_configs.append({
                        'config_name': row[0],
                        'prefix_remove': row[1],
                        'suffix_remove': row[2],
                        'extract_start': row[3],
                        'extract_length': row[4],
                        'extract_mode': row[5],
                        'is_default': row[6]
                    })
            except Exception:
                scan_configs = []

            # 导出导入配置
            try:
                cur.execute('''
                    SELECT config_name, field_mapping, encoding, delimiter, custom_field_names, is_default
                    FROM import_configs ORDER BY config_name
                ''')
                import_configs = []
                for row in cur.fetchall():
                    import_configs.append({
                        'config_name': row[0],
                        'field_mapping': self._safe_json_loads(row[1]),
                        'encoding': row[2],
                        'delimiter': row[3],
                        'custom_field_names': self._safe_json_loads(row[4]) if row[4] else None,
                        'is_default': row[5]
                    })
            except Exception:
                import_configs = []

            # 导出标签模板（如存在）
            try:
                cur.execute('''
                    SELECT template_name, template_config, label_width, label_height, is_default
                    FROM label_templates ORDER BY template_name
                ''')
                label_templates = []
                for row in cur.fetchall():
                    label_templates.append({
                        'template_name': row[0],
                        'template_config': self._safe_json_loads(row[1]),
                        'label_width': row[2],
                        'label_height': row[3],
                        'is_default': row[4]
                    })
            except Exception:
                label_templates = []

            conn.close()

            data = {
                'meta': {
                    'format': 'PackingSystem.Settings',
                    'version': 1,
                    'exported_at': datetime.now().isoformat(timespec='seconds')
                },
                'system_settings': system_settings,
                'scan_configs': scan_configs,
                'import_configs': import_configs,
                'label_templates': label_templates
            }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, "成功", f"已导出系统设置到:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败：{e}")

    def on_import_settings(self):
        """从 JSON 文件导入系统设置（覆盖当前配置，含附属配置）"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(self, "导入系统设置", "", "JSON 文件 (*.json)")
            if not file_path:
                return

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 兼容不同结构提取 system_settings
            system_settings = []
            if isinstance(data, dict):
                if isinstance(data.get('system_settings'), list):
                    system_settings = data.get('system_settings')
                elif isinstance(data.get('settings'), list):
                    # 兼容旧键名
                    system_settings = data.get('settings')
                elif isinstance(data.get('settings'), dict):
                    system_settings = [
                        {'key': k, 'value': v, 'type': None, 'description': None}
                        for k, v in data.get('settings', {}).items()
                    ]
            elif isinstance(data, list):
                system_settings = data

            conn = self.db.get_connection()
            cur = conn.cursor()

            # 覆盖写入 system_settings
            for item in system_settings:
                key = item.get('key') or item.get('setting_key')
                val = item.get('value') if 'value' in item else item.get('setting_value')
                if key is None:
                    continue
                self.db.set_setting(key, val)

            # 导入扫码配置（按名称幂等 Upsert）
            try:
                for sc in (data.get('scan_configs') or []):
                    name = sc.get('config_name')
                    if not name:
                        continue
                    cur.execute('SELECT 1 FROM scan_configs WHERE config_name = ?', (name,))
                    exists = cur.fetchone() is not None
                    if exists:
                        cur.execute('''
                            UPDATE scan_configs
                            SET prefix_remove=?, suffix_remove=?, extract_start=?, extract_length=?, extract_mode=?, is_default=?, updated_at=CURRENT_TIMESTAMP
                            WHERE config_name=?
                        ''', (
                            int(sc.get('prefix_remove') or 0),
                            int(sc.get('suffix_remove') or 0),
                            int(sc.get('extract_start') or 0),
                            int(sc.get('extract_length') or 0),
                            sc.get('extract_mode') or 'none',
                            int(sc.get('is_default') or 0),
                            name
                        ))
                    else:
                        cur.execute('''
                            INSERT INTO scan_configs (config_name, prefix_remove, suffix_remove, extract_start, extract_length, extract_mode, is_default)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            name,
                            int(sc.get('prefix_remove') or 0),
                            int(sc.get('suffix_remove') or 0),
                            int(sc.get('extract_start') or 0),
                            int(sc.get('extract_length') or 0),
                            sc.get('extract_mode') or 'none',
                            int(sc.get('is_default') or 0)
                        ))
            except Exception:
                pass

            # 导入导入配置（按名称 Upsert）
            try:
                for ic in (data.get('import_configs') or []):
                    name = ic.get('config_name')
                    if not name:
                        continue
                    field_mapping = ic.get('field_mapping')
                    custom_field_names = ic.get('custom_field_names')
                    field_mapping_str = self._maybe_json_str(field_mapping)
                    custom_names_str = self._maybe_json_str(custom_field_names) if custom_field_names is not None else None
                    cur.execute('SELECT 1 FROM import_configs WHERE config_name = ?', (name,))
                    exists = cur.fetchone() is not None
                    if exists:
                        cur.execute('''
                            UPDATE import_configs
                            SET field_mapping=?, encoding=?, delimiter=?, custom_field_names=?, is_default=?, updated_at=CURRENT_TIMESTAMP
                            WHERE config_name=?
                        ''', (
                            field_mapping_str,
                            ic.get('encoding') or 'utf-8',
                            ic.get('delimiter') or ',',
                            custom_names_str,
                            int(ic.get('is_default') or 0),
                            name
                        ))
                    else:
                        cur.execute('''
                            INSERT INTO import_configs (config_name, field_mapping, encoding, delimiter, custom_field_names, is_default)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            name,
                            field_mapping_str,
                            ic.get('encoding') or 'utf-8',
                            ic.get('delimiter') or ',',
                            custom_names_str,
                            int(ic.get('is_default') or 0)
                        ))
            except Exception:
                pass

            # 导入标签模板（按模板名 Upsert）
            try:
                for lt in (data.get('label_templates') or []):
                    name = lt.get('template_name')
                    if not name:
                        continue
                    cfg_str = self._maybe_json_str(lt.get('template_config'))
                    cur.execute('SELECT 1 FROM label_templates WHERE template_name = ?', (name,))
                    exists = cur.fetchone() is not None
                    if exists:
                        cur.execute('''
                            UPDATE label_templates
                            SET template_config=?, label_width=?, label_height=?, is_default=?, updated_at=CURRENT_TIMESTAMP
                            WHERE template_name=?
                        ''', (
                            cfg_str,
                            int(lt.get('label_width') or 100),
                            int(lt.get('label_height') or 60),
                            int(lt.get('is_default') or 0),
                            name
                        ))
                    else:
                        cur.execute('''
                            INSERT INTO label_templates (template_name, template_config, label_width, label_height, is_default)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            name,
                            cfg_str,
                            int(lt.get('label_width') or 100),
                            int(lt.get('label_height') or 60),
                            int(lt.get('is_default') or 0)
                        ))
            except Exception:
                pass

            conn.commit()
            conn.close()

            # 刷新界面并应用相关定时器设置
            try:
                self.load_all_settings()
                self.update_db_info()
                self._apply_backup_settings()
                # 若启用云同步设置逻辑，确保定时器一致
                self._apply_cloud_sync_settings()
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"已导入设置并覆盖当前配置:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _apply_daily_full_sync_settings(self):
        """根据设置调度每日全量同步的下一次触发时间"""
        try:
            if not self.cloud_sync_service:
                # 无服务时停止定时器
                try:
                    self.daily_full_sync_timer.stop()
                except Exception:
                    pass
                return
            enabled = getattr(self, 'daily_full_sync_enabled', None)
            time_edit = getattr(self, 'daily_full_sync_time', None)
            is_enabled = bool(enabled and enabled.isChecked())
            if not is_enabled or not time_edit:
                try:
                    self.daily_full_sync_timer.stop()
                except Exception:
                    pass
                return
            # 计算从当前时间到下一次触发的毫秒数
            t = time_edit.time()
            from datetime import datetime, timedelta
            now = datetime.now()
            target = datetime.combine(now.date(), datetime.min.time()).replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)
            delay_ms = max(1000, int((target - now).total_seconds() * 1000))
            try:
                self.daily_full_sync_timer.start(delay_ms)
            except Exception as e:
                print(f'启动每日全量同步定时器失败: {e}')
        except Exception as e:
            print(f'应用每日全量同步设置失败: {e}')

    def _on_daily_full_sync_timer(self):
        """每日定时器回调：仅入队全量同步任务并调度下一次"""
        try:
            # 获取同步服务，确保服务运行
            try:
                svc = self.cloud_sync_service if hasattr(self, 'cloud_sync_service') and self.cloud_sync_service else get_sync_service()
            except Exception:
                svc = None
            if not svc:
                return
            try:
                if not getattr(svc, 'running', False):
                    svc.start_sync_service()
            except Exception as e:
                print(f'启动云同步服务失败: {e}')
            # 入队 full_sync 任务，避免阻塞 UI
            try:
                svc.trigger_sync('full_sync', {}, force=True)
            except Exception as e:
                print(f'每日全量同步入队失败: {e}')
        finally:
            # 无论成功失败，重新调度下一次
            try:
                self._apply_daily_full_sync_settings()
            except Exception:
                pass
    
    def apply_settings(self):
        """应用设置（不保存到数据库）"""
        # 这里可以实现实时预览设置效果
        QMessageBox.information(self, "提示", "设置已应用，但尚未保存到数据库。")

    def save_settings(self):
        """保存系统设置"""
        try:
            # 包装设置
            self.db.set_setting('package_number_format', self.package_number_format.text())
            self.db.set_setting('pallet_number_format', self.pallet_number_format.text())
            self.db.set_setting('virtual_pallet_format', self.virtual_pallet_format.text())
            self.db.set_setting('auto_complete_code', self.auto_complete_code.text())
            
            # 默认配置
            if self.default_scan_config.currentData():
                self.db.set_setting('default_scan_config', str(self.default_scan_config.currentData()))
            if self.default_import_config.currentData():
                self.db.set_setting('default_import_config', str(self.default_import_config.currentData()))
            # 标签模板设置页面已移除
            
            # 系统行为设置
            self.db.set_setting('auto_backup_enabled', 'true' if self.auto_backup_enabled.isChecked() else 'false')
            self.db.set_setting('backup_interval', str(self.backup_interval.value()))
            self.db.set_setting('max_backup_files', str(self.max_backup_files.value()))
            
            # 云同步设置（自动上传与每日全量设置已移除，不再保存）

            
            # 界面设置
            self.db.set_setting('theme', self.theme.currentText())
            self.db.set_setting('language', self.language.currentText())
            self.db.set_setting('font_size', str(self.font_size.value()))
            
            # 数据库设置
            self.db.set_setting('auto_vacuum', 'true' if self.auto_vacuum.isChecked() else 'false')
            self.db.set_setting('enable_wal', 'true' if self.enable_wal.isChecked() else 'false')
            
            # 日志设置
            self.db.set_setting('log_level', self.log_level.currentText())
            self.db.set_setting('log_retention_days', str(self.log_retention_days.value()))
            
            # 保存新增设置项
            self.db.set_setting('auto_save_window_state', 'true' if self.auto_save_window_state.isChecked() else 'false')
            self.db.set_setting('show_tooltips', 'true' if self.show_tooltips.isChecked() else 'false')
            self.db.set_setting('max_log_size', str(self.max_log_size.value()))
            self.db.set_setting('max_log_files', str(self.max_log_files.value()))
            self.db.set_setting('auto_start_with_system', 'true' if self.auto_start_with_system.isChecked() else 'false')
            self.db.set_setting('start_minimized', 'true' if self.start_minimized.isChecked() else 'false')
            self.db.set_setting('auto_lock_enabled', 'true' if self.auto_lock_enabled.isChecked() else 'false')
            self.db.set_setting('auto_lock_minutes', str(self.auto_lock_minutes.value()))
            self.db.set_setting('remember_last_tab', 'true' if self.remember_last_tab.isChecked() else 'false')
            self.db.set_setting('confirm_delete', 'true' if self.confirm_delete.isChecked() else 'false')
            self.db.set_setting('confirm_clear', 'true' if self.confirm_clear.isChecked() else 'false')
            self.db.set_setting('max_recent_files', str(self.max_recent_files.value()))
            self.db.set_setting('cache_size', str(self.cache_size.value()))
            self.db.set_setting('pallets_page_size', str(self.pallets_page_size.value()))
            self.db.set_setting('packages_page_size', str(self.packages_page_size.value()))
            self.db.set_setting('backup_path', self.backup_path_edit.text())
            self.db.set_setting('backup_compress_enabled', 'true' if self.backup_compress_enabled.isChecked() else 'false')
            
            # 保存打印机设置
            self.db.set_setting('printer_name', self.printer_name.currentText())
            self.db.set_setting('print_resolution', self.print_resolution.currentText())
            self.db.set_setting('print_quality', self.print_quality.currentText())
            self.db.set_setting('print_speed', self.print_speed.currentText())
            self.db.set_setting('label_preset', self.label_preset.currentText())
            self.db.set_setting('custom_width', str(self.custom_width.value()))
            self.db.set_setting('custom_height', str(self.custom_height.value()))
            self.db.set_setting('auto_cut', 'true' if self.auto_cut.isChecked() else 'false')
            self.db.set_setting('print_preview', 'true' if self.print_preview.isChecked() else 'false')
            self.db.set_setting('save_print_log', 'true' if self.save_print_log.isChecked() else 'false')
            self.db.set_setting('print_orientation', self.print_orientation.currentText())
            # 打印扩展项
            self.db.set_setting('print_density', self.print_density.currentText())
            self.db.set_setting('print_inverse', 'true' if self.print_inverse.isChecked() else 'false')
            self.db.set_setting('print_centered', 'true' if self.print_centered.isChecked() else 'false')
            # 保存校准与偏移
            self.db.set_setting('print_offset_x_mm', str(self.offset_x_mm.value()))
            self.db.set_setting('print_offset_y_mm', str(self.offset_y_mm.value()))
            self.db.set_setting('print_scale_percent', str(self.scale_percent.value()))
            self.db.set_setting('print_extra_margin_mm', str(self.extra_margin_mm.value()))
            
            # 发出设置变更信号
            # 自动云上传与每日全量调度已禁用，不再应用对应设置
            # 应用自动备份设置（启动/停止定时器）
            try:
                self._apply_backup_settings()
            except Exception:
                pass
            self.settings_changed.emit()
            
            QMessageBox.information(self, "成功", "设置已保存成功！\n某些设置可能需要重启应用程序后生效。")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败：\n{str(e)}")

    def reset_to_defaults(self):
        """重置为默认设置"""
        reply = QMessageBox.question(self, "确认重置", 
                                   "确定要重置所有设置为默认值吗？\n此操作不可撤销。",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # 删除所有设置
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM system_settings')
                conn.commit()
                conn.close()
                
                # 重新初始化默认设置
                self.db.init_default_settings()
                
                # 重新加载界面
                self.load_all_settings()
                
                QMessageBox.information(self, "成功", "设置已重置为默认值！")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重置设置失败：\n{str(e)}")
    
    def refresh_printer_list(self):
        """刷新打印机列表"""
        try:
            from PyQt5.QtPrintSupport import QPrinterInfo
            
            # 清空当前列表
            self.printer_name.clear()
            
            # 获取所有可用打印机
            printers = QPrinterInfo.availablePrinters()
            
            if printers:
                for printer in printers:
                    self.printer_name.addItem(printer.printerName())
                
                # 设置默认打印机
                default_printer = QPrinterInfo.defaultPrinter()
                if default_printer and not default_printer.isNull():
                    default_name = default_printer.printerName()
                    index = self.printer_name.findText(default_name)
                    if index >= 0:
                        self.printer_name.setCurrentIndex(index)
            else:
                self.printer_name.addItem("未找到可用打印机")
                
        except Exception as e:
            QMessageBox.warning(self, "警告", f"刷新打印机列表失败：\n{str(e)}")
            self.printer_name.addItem("刷新失败")
    
    def on_preset_changed(self, preset_text):
        """当预设尺寸改变时更新自定义尺寸"""
        preset_sizes = {
            "80x50mm (热敏标签)": (80, 50),
            "100x60mm (快递标签)": (100, 60),
            "100x70mm (快递标签-宽版)": (100, 70),
            "100x80mm (物流标签)": (100, 80),
            "120x80mm (大型标签)": (120, 80)
        }
        
        if preset_text in preset_sizes:
            width, height = preset_sizes[preset_text]
            self.custom_width.setValue(width)
            self.custom_height.setValue(height)
    
    def test_print(self):
        """测试打印功能"""
        try:
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt5.QtGui import QPainter, QFont
            from PyQt5.QtCore import QRectF
            
            # 创建打印机对象
            printer = QPrinter(QPrinter.HighResolution)
            
            # 设置打印机
            if self.printer_name.currentText() and self.printer_name.currentText() != "未找到可用打印机":
                printer.setPrinterName(self.printer_name.currentText())
            
            # 应用打印设置
            self.apply_printer_settings(printer)
            
            # 创建打印对话框
            print_dialog = QPrintDialog(printer, self)
            print_dialog.setWindowTitle("测试打印")
            
            if print_dialog.exec_() == QPrintDialog.Accepted:
                # 开始打印
                painter = QPainter(printer)

                try:
                    # 设置字体
                    font = QFont("Arial", 12)
                    painter.setFont(font)
                    
                    # 获取页面矩形
                    page_rect = printer.pageRect()
                    # 根据旋转选项调整坐标系，避免方向被反
                    orientation_text = self.print_orientation.currentText()
                    if orientation_text == "旋转90°":
                        painter.translate(page_rect.width(), 0)
                        painter.rotate(90)
                    elif orientation_text == "旋转270°":
                        painter.translate(0, page_rect.height())
                        painter.rotate(270)
                    elif orientation_text == "旋转180°":
                        painter.translate(page_rect.width(), page_rect.height())
                        painter.rotate(180)
                    # 应用用户校准：偏移与缩放
                    try:
                        dpi_x = printer.logicalDpiX()
                        dpi_y = printer.logicalDpiY()
                        dx = float(self.offset_x_mm.value()) * dpi_x / 25.4
                        dy = float(self.offset_y_mm.value()) * dpi_y / 25.4
                        scale = float(self.scale_percent.value()) / 100.0
                        painter.translate(dx, dy)
                        if abs(scale - 1.0) > 1e-6:
                            painter.scale(scale, scale)
                    except Exception:
                        pass
                
                    # 绘制测试内容
                    y_pos = 100
                    painter.drawText(100, y_pos, "热敏打印机测试页")
                    y_pos += 50

                    painter.drawText(100, y_pos, f"打印机: {self.printer_name.currentText()}")
                    y_pos += 30

                    painter.drawText(100, y_pos, f"分辨率: {self.print_resolution.currentText()}")
                    y_pos += 30

                    painter.drawText(100, y_pos, f"质量: {self.print_quality.currentText()}")
                    y_pos += 30

                    painter.drawText(100, y_pos, f"速度: {self.print_speed.currentText()}")
                    y_pos += 30

                    painter.drawText(100, y_pos, f"方向: {self.print_orientation.currentText()}")
                    y_pos += 30
                    painter.drawText(100, y_pos, f"X偏移: {self.offset_x_mm.value()}mm  Y偏移: {self.offset_y_mm.value()}mm")
                    y_pos += 30
                    painter.drawText(100, y_pos, f"缩放: {self.scale_percent.value()}%  额外边距: {self.extra_margin_mm.value()}mm")
                    y_pos += 30

                    painter.drawText(100, y_pos, f"标签尺寸: {self.custom_width.value()}x{self.custom_height.value()}mm")
                    y_pos += 50

                    # 绘制边框
                    painter.drawRect(50, 50, page_rect.width() - 100, y_pos)
                    
                finally:
                    painter.end()
                
                QMessageBox.information(self, "成功", "测试打印完成！")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试打印失败：\n{str(e)}")
    
    def print_config_page(self):
        """打印配置页"""
        try:
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt5.QtGui import QPainter, QFont
            
            # 创建打印机对象
            printer = QPrinter(QPrinter.HighResolution)
            
            # 设置打印机
            if self.printer_name.currentText() and self.printer_name.currentText() != "未找到可用打印机":
                printer.setPrinterName(self.printer_name.currentText())
            
            # 应用打印设置
            self.apply_printer_settings(printer)
            
            # 直接打印配置页（不显示对话框）
            painter = QPainter(printer)
            
            try:
                # 设置字体
                font = QFont("Arial", 10)
                painter.setFont(font)
                
                # 获取页面矩形
                page_rect = printer.pageRect()

                # 根据旋转选项调整坐标系，避免方向被反
                orientation_text = self.print_orientation.currentText()
                if orientation_text == "旋转90°":
                    painter.translate(page_rect.width(), 0)
                    painter.rotate(90)
                elif orientation_text == "旋转270°":
                    painter.translate(0, page_rect.height())
                    painter.rotate(270)
                elif orientation_text == "旋转180°":
                    painter.translate(page_rect.width(), page_rect.height())
                    painter.rotate(180)
                # 应用用户校准：偏移与缩放
                try:
                    dpi_x = printer.logicalDpiX()
                    dpi_y = printer.logicalDpiY()
                    dx = float(self.offset_x_mm.value()) * dpi_x / 25.4
                    dy = float(self.offset_y_mm.value()) * dpi_y / 25.4
                    scale = float(self.scale_percent.value()) / 100.0
                    painter.translate(dx, dy)
                    if abs(scale - 1.0) > 1e-6:
                        painter.scale(scale, scale)
                except Exception:
                    pass
                
                # 绘制配置信息
                y_pos = 100
                painter.drawText(100, y_pos, "=== 热敏打印机配置页 ===")
                y_pos += 60
                
                config_items = [
                    f"打印机名称: {self.printer_name.currentText()}",
                    f"打印分辨率: {self.print_resolution.currentText()}",
                    f"打印质量: {self.print_quality.currentText()}",
                    f"打印方向: {self.print_orientation.currentText()}",
                    f"打印速度: {self.print_speed.currentText()}",
                    f"标签预设: {self.label_preset.currentText()}",
                    f"自定义尺寸: {self.custom_width.value()}x{self.custom_height.value()}mm",
                    f"自动切纸: {'是' if self.auto_cut.isChecked() else '否'}",
                    f"打印预览: {'是' if self.print_preview.isChecked() else '否'}",
                    f"保存日志: {'是' if self.save_print_log.isChecked() else '否'}",
                    f"X偏移: {self.offset_x_mm.value()}mm",
                    f"Y偏移: {self.offset_y_mm.value()}mm",
                    f"缩放: {self.scale_percent.value()}%",
                    f"额外边距: {self.extra_margin_mm.value()}mm"
                ]
                
                for item in config_items:
                    painter.drawText(100, y_pos, item)
                    y_pos += 40
                
                # 绘制测试图案
                y_pos += 50
                painter.drawText(100, y_pos, "测试图案:")
                y_pos += 40
                
                # 绘制矩形
                painter.drawRect(100, y_pos, 200, 100)
                painter.drawText(120, y_pos + 50, "测试矩形")
                
            finally:
                painter.end()
            
            QMessageBox.information(self, "成功", "配置页打印完成！")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打印配置页失败：\n{str(e)}")
    
    def apply_printer_settings(self, printer):
        """应用打印机设置到QPrinter对象"""
        try:
            # 确保 QPrinter 可用
            from PyQt5.QtPrintSupport import QPrinter
            # 设置分辨率
            resolution_map = {
                "203 DPI": 203,
                "300 DPI": 300,
                "600 DPI": 600
            }
            resolution = resolution_map.get(self.print_resolution.currentText(), 203)
            printer.setResolution(resolution)
            
            # 设置颜色模式（热敏打印机通常使用灰度）
            printer.setColorMode(QPrinter.GrayScale)
            
            # 设置页面尺寸（使用毫米，避免单位转换误差）
            width_mm = float(self.custom_width.value())
            height_mm = float(self.custom_height.value())
            orientation_text = self.print_orientation.currentText()
            # 对于 90/270 度旋转，交换宽高以匹配驱动的纸张方向
            if orientation_text in ["旋转90°", "旋转270°"]:
                width_mm, height_mm = height_mm, width_mm
            from PyQt5.QtCore import QSizeF
            printer.setPaperSize(QSizeF(width_mm, height_mm), QPrinter.Millimeter)
            
            # 根据尺寸设置方向
            if orientation_text == "纵向":
                printer.setOrientation(QPrinter.Portrait)
            elif orientation_text == "横向":
                printer.setOrientation(QPrinter.Landscape)
            else:
                # 自动：根据宽高判断
                if width_mm >= height_mm:
                    printer.setOrientation(QPrinter.Landscape)
                else:
                    printer.setOrientation(QPrinter.Portrait)
            
            # 允许满版打印（忽略驱动默认的不可打印边距）
            printer.setFullPage(True)
            
            # 设置页边距：允许用户配置额外边距
            try:
                margin_mm = float(getattr(self, 'extra_margin_mm', None).value()) if hasattr(self, 'extra_margin_mm') else 0.0
            except Exception:
                margin_mm = 0.0
            printer.setPageMargins(margin_mm, margin_mm, margin_mm, margin_mm, QPrinter.Millimeter)
            
        except Exception as e:
            print(f"应用打印机设置时出错: {e}")
    
    def update_db_info(self):
        """更新数据库路径与大小显示"""
        try:
            db_path = getattr(self.db, 'db_path', '')
            self.db_path_label.setText(db_path)
            import os
            if db_path and os.path.exists(db_path):
                size = os.path.getsize(db_path)
                def fmt_bytes(n):
                    for unit in ['B','KB','MB','GB','TB']:
                        if n < 1024.0:
                            return f"{n:,.2f} {unit}"
                        n /= 1024.0
                    return f"{n:,.2f} PB"
                self.db_size_label.setText(fmt_bytes(size))
            else:
                self.db_size_label.setText("未知")
        except Exception as e:
            self.db_size_label.setText(f"计算大小失败: {e}")
    
    def on_vacuum_now(self):
        """立即执行 VACUUM 清理数据库碎片"""
        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute('VACUUM')
            conn.commit()
            conn.close()
            self.update_db_info()
            QMessageBox.information(self, "成功", "数据库清理完成 (VACUUM)")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"执行清理时发生错误:\n{e}")
    
    def on_backup_now(self):
        """立即备份数据库到指定路径"""
        try:
            import os, shutil
            from datetime import datetime
            backup_dir = self.backup_path_edit.text().strip() or os.path.join(os.path.dirname(self.db.db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            compress = self.backup_compress_enabled.isChecked()
            base_name = f"backup_{ts}"
            if compress:
                backup_file = os.path.join(backup_dir, f"{base_name}.zip")
                import zipfile
                with zipfile.ZipFile(backup_file, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.write(self.db.db_path, arcname=os.path.basename(self.db.db_path))
            else:
                backup_file = os.path.join(backup_dir, f"{base_name}.db")
                shutil.copy2(self.db.db_path, backup_file)
            QMessageBox.information(self, "成功", f"已备份到: {backup_file}")
            # 备份后清理旧备份文件，遵循最大保留数量
            try:
                self._prune_old_backups()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "错误", f"备份失败:\n{e}")
    
    def on_repair_db_clicked(self):
        """尝试修复数据库：重建索引并进行完整性检查"""
        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute('REINDEX')
            cur.execute('PRAGMA integrity_check')
            result = cur.fetchone()
            conn.commit()
            conn.close()
            msg = result[0] if result else '未知'
            if msg.upper() == 'OK':
                QMessageBox.information(self, "成功", "数据库完整性检查 OK，索引已重建")
            else:
                QMessageBox.warning(self, "警告", f"完整性检查结果: {msg}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修复数据库失败:\n{e}")
    
    def on_restore_backup(self):
        """从备份文件恢复数据库"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            import os, shutil, zipfile
            file_path, _ = QFileDialog.getOpenFileName(self, "选择备份文件", self.backup_path_edit.text(), "备份文件 (*.db *.zip)")
            if not file_path:
                return
            restore_path = file_path
            if file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zf:
                    db_members = [m for m in zf.namelist() if m.lower().endswith('.db')]
                    if not db_members:
                        QMessageBox.critical(self, "错误", "压缩包内未找到 .db 文件")
                        return
                    temp_dir = os.path.join(os.path.dirname(self.db.db_path), 'tmp_restore')
                    os.makedirs(temp_dir, exist_ok=True)
                    restore_path = os.path.join(temp_dir, os.path.basename(db_members[0]))
                    zf.extract(db_members[0], temp_dir)
                    if os.path.exists(os.path.join(temp_dir, db_members[0])):
                        shutil.move(os.path.join(temp_dir, db_members[0]), restore_path)
            shutil.copy2(restore_path, self.db.db_path)
            QMessageBox.information(self, "成功", "数据库已恢复，请重启应用程序")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复失败:\n{e}")
    
    def on_manage_backups(self):
        """打开备份目录以便用户管理文件"""
        try:
            import os
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            backup_dir = self.backup_path_edit.text().strip() or os.path.join(os.path.dirname(self.db.db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(backup_dir))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开目录失败:\n{e}")
    
    def on_browse_backup_path(self):
        """选择备份保存目录"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            dir_path = QFileDialog.getExistingDirectory(self, "选择备份目录", self.backup_path_edit.text() or "")
            if dir_path:
                self.backup_path_edit.setText(dir_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择目录失败:\n{e}")