import sys
import json
import re
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QTableWidget, QTableWidgetItem, QLabel,
                             QLineEdit, QTextEdit, QComboBox, QMessageBox,
                             QDialog, QDialogButtonBox, QGroupBox, QCheckBox,
                             QSplitter, QHeaderView, QTabWidget, QSpinBox,
                             QButtonGroup, QRadioButton, QFrame, QMenu, QAction,
                             QFileDialog, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QImage
import numpy as np
from qr_handler import QRCodeHandler
from database import db
from error_handling import ErrorHandler, undo_manager, Prompt
from order_management import OrderSelectionDialog
try:
    from voice import speak as voice_speak
except Exception:
    def voice_speak(_text: str):
        pass

class QRPreviewDialog(QDialog):
    """二维码预览对话框，支持复制包裹号与保存图片"""
    def __init__(self, pil_image, package_number: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("包裹二维码预览")
        self.resize(360, 420)
        self._pil_image = pil_image
        self._package_number = package_number

        layout = QVBoxLayout(self)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)

        # 按钮区
        btn_box = QHBoxLayout()
        self.copy_btn = QPushButton("复制包裹号")
        self.save_btn = QPushButton("保存图片")
        self.close_btn = QPushButton("关闭")
        btn_box.addStretch()
        btn_box.addWidget(self.copy_btn)
        btn_box.addWidget(self.save_btn)
        btn_box.addWidget(self.close_btn)
        layout.addLayout(btn_box)

        self.copy_btn.clicked.connect(self.copy_package_number)
        self.save_btn.clicked.connect(self.save_image)
        self.close_btn.clicked.connect(self.accept)

        self._update_preview()

    def _update_preview(self):
        pixmap = self._pil_to_qpixmap(self._pil_image)
        self.image_label.setPixmap(pixmap)

    def _pil_to_qpixmap(self, pil_image):
        arr = np.array(pil_image.convert('RGB'))
        h, w, ch = arr.shape
        bytes_per_line = ch * w
        qt_image = QImage(arr.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(qt_image)

    def copy_package_number(self):
        QApplication.clipboard().setText(self._package_number)
        QMessageBox.information(self, "已复制", f"包裹号 {self._package_number} 已复制到剪贴板")

    def save_image(self):
        default_name = f"package_{self._package_number}.png"
        fname, _ = QFileDialog.getSaveFileName(self, "保存二维码", default_name, "PNG 图片 (*.png)")
        if fname:
            try:
                self._pil_image.save(fname, format='PNG')
                QMessageBox.information(self, "成功", f"已保存到\n{fname}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

class ScanConfigDialog(QDialog):
    """扫码配置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫码配置")
        self.setModal(True)
        self.resize(600, 600)
        
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 扫码处理方式
        process_group = QGroupBox("扫码处理方式")
        process_layout = QVBoxLayout(process_group)
        
        self.process_group = QButtonGroup()
        
        self.no_process_radio = QRadioButton("不处理（保持原样）")
        self.process_group.addButton(self.no_process_radio, 0)
        process_layout.addWidget(self.no_process_radio)
        
        self.remove_prefix_radio = QRadioButton("去掉前缀字符")
        self.process_group.addButton(self.remove_prefix_radio, 1)
        process_layout.addWidget(self.remove_prefix_radio)
        
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("前缀长度:"))
        self.prefix_length_spin = QSpinBox()
        self.prefix_length_spin.setRange(1, 10)
        self.prefix_length_spin.setValue(1)
        prefix_layout.addWidget(self.prefix_length_spin)
        prefix_layout.addStretch()
        process_layout.addLayout(prefix_layout)
        
        self.remove_suffix_radio = QRadioButton("去掉后缀字符")
        self.process_group.addButton(self.remove_suffix_radio, 2)
        process_layout.addWidget(self.remove_suffix_radio)
        
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("后缀长度:"))
        self.suffix_length_spin = QSpinBox()
        self.suffix_length_spin.setRange(1, 10)
        self.suffix_length_spin.setValue(1)
        suffix_layout.addWidget(self.suffix_length_spin)
        suffix_layout.addStretch()
        process_layout.addLayout(suffix_layout)
        
        self.extract_middle_radio = QRadioButton("提取中间字符")
        self.process_group.addButton(self.extract_middle_radio, 3)
        process_layout.addWidget(self.extract_middle_radio)
        
        middle_layout = QGridLayout()
        middle_layout.addWidget(QLabel("起始位置:"), 0, 0)
        self.start_pos_spin = QSpinBox()
        self.start_pos_spin.setRange(1, 50)
        self.start_pos_spin.setValue(1)
        middle_layout.addWidget(self.start_pos_spin, 0, 1)
        
        middle_layout.addWidget(QLabel("长度:"), 0, 2)
        self.extract_length_spin = QSpinBox()
        self.extract_length_spin.setRange(1, 50)
        self.extract_length_spin.setValue(5)
        middle_layout.addWidget(self.extract_length_spin, 0, 3)
        
        process_layout.addLayout(middle_layout)
        
        # 新增：字符插入配置
        self.insert_chars_radio = QRadioButton("插入字符")
        self.process_group.addButton(self.insert_chars_radio, 4)
        process_layout.addWidget(self.insert_chars_radio)
        
        insert_layout = QGridLayout()
        insert_layout.addWidget(QLabel("插入位置:"), 0, 0)
        self.insert_position_spin = QSpinBox()
        self.insert_position_spin.setRange(0, 50)  # 0表示开头
        self.insert_position_spin.setValue(0)
        insert_layout.addWidget(self.insert_position_spin, 0, 1)
        
        insert_layout.addWidget(QLabel("插入内容:"), 0, 2)
        self.insert_content_edit = QLineEdit()
        self.insert_content_edit.setPlaceholderText("要插入的字符")
        self.insert_content_edit.setMaxLength(10)
        insert_layout.addWidget(self.insert_content_edit, 0, 3)
        
        process_layout.addLayout(insert_layout)
        
        # 新增：组合配置
        self.combination_radio = QRadioButton("组合配置")
        self.process_group.addButton(self.combination_radio, 5)
        process_layout.addWidget(self.combination_radio)
        
        # 组合配置选项
        combo_layout = QVBoxLayout()
        
        # 组合选项复选框
        combo_options_layout = QGridLayout()
        
        self.combo_remove_prefix_check = QCheckBox("去掉前缀")
        combo_options_layout.addWidget(self.combo_remove_prefix_check, 0, 0)
        self.combo_prefix_spin = QSpinBox()
        self.combo_prefix_spin.setRange(1, 10)
        self.combo_prefix_spin.setValue(1)
        self.combo_prefix_spin.setEnabled(False)
        combo_options_layout.addWidget(self.combo_prefix_spin, 0, 1)
        
        self.combo_remove_suffix_check = QCheckBox("去掉后缀")
        combo_options_layout.addWidget(self.combo_remove_suffix_check, 0, 2)
        self.combo_suffix_spin = QSpinBox()
        self.combo_suffix_spin.setRange(1, 10)
        self.combo_suffix_spin.setValue(1)
        self.combo_suffix_spin.setEnabled(False)
        combo_options_layout.addWidget(self.combo_suffix_spin, 0, 3)
        
        self.combo_insert_check = QCheckBox("插入字符")
        combo_options_layout.addWidget(self.combo_insert_check, 1, 0)
        self.combo_insert_pos_spin = QSpinBox()
        self.combo_insert_pos_spin.setRange(0, 50)
        self.combo_insert_pos_spin.setValue(0)
        self.combo_insert_pos_spin.setEnabled(False)
        combo_options_layout.addWidget(self.combo_insert_pos_spin, 1, 1)
        self.combo_insert_content_edit = QLineEdit()
        self.combo_insert_content_edit.setPlaceholderText("插入内容")
        self.combo_insert_content_edit.setMaxLength(10)
        self.combo_insert_content_edit.setEnabled(False)
        combo_options_layout.addWidget(self.combo_insert_content_edit, 1, 2, 1, 2)
        
        self.combo_extract_check = QCheckBox("提取中间字符")
        combo_options_layout.addWidget(self.combo_extract_check, 2, 0)
        self.combo_start_spin = QSpinBox()
        self.combo_start_spin.setRange(1, 50)
        self.combo_start_spin.setValue(1)
        self.combo_start_spin.setEnabled(False)
        combo_options_layout.addWidget(self.combo_start_spin, 2, 1)
        self.combo_length_spin = QSpinBox()
        self.combo_length_spin.setRange(1, 50)
        self.combo_length_spin.setValue(5)
        self.combo_length_spin.setEnabled(False)
        combo_options_layout.addWidget(self.combo_length_spin, 2, 2)
        
        combo_layout.addLayout(combo_options_layout)
        
        # 执行顺序说明
        order_label = QLabel("执行顺序：去前缀 → 去后缀 → 插入字符 → 提取中间字符")
        order_label.setStyleSheet("color: #666; font-size: 10px;")
        combo_layout.addWidget(order_label)
        
        process_layout.addLayout(combo_layout)
        
        layout.addWidget(process_group)
        
        # 测试区域
        test_group = QGroupBox("测试")
        test_layout = QGridLayout(test_group)
        
        test_layout.addWidget(QLabel("输入测试:"), 0, 0)
        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText("输入测试扫码内容")
        self.test_input.textChanged.connect(self.update_test_result)
        test_layout.addWidget(self.test_input, 0, 1)
        
        test_layout.addWidget(QLabel("处理结果:"), 1, 0)
        self.test_result = QLineEdit()
        self.test_result.setReadOnly(True)
        test_layout.addWidget(self.test_result, 1, 1)
        
        layout.addWidget(test_group)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 连接信号
        for button in self.process_group.buttons():
            button.toggled.connect(self.update_test_result)
        
        self.prefix_length_spin.valueChanged.connect(self.update_test_result)
        self.suffix_length_spin.valueChanged.connect(self.update_test_result)
        self.start_pos_spin.valueChanged.connect(self.update_test_result)
        self.extract_length_spin.valueChanged.connect(self.update_test_result)
        
        # 新增控件的信号连接
        self.insert_position_spin.valueChanged.connect(self.update_test_result)
        self.insert_content_edit.textChanged.connect(self.update_test_result)
        
        # 组合配置复选框信号连接
        self.combo_remove_prefix_check.toggled.connect(self.on_combo_prefix_toggled)
        self.combo_remove_suffix_check.toggled.connect(self.on_combo_suffix_toggled)
        self.combo_insert_check.toggled.connect(self.on_combo_insert_toggled)
        self.combo_extract_check.toggled.connect(self.on_combo_extract_toggled)
        
        # 组合配置控件信号连接
        self.combo_prefix_spin.valueChanged.connect(self.update_test_result)
        self.combo_suffix_spin.valueChanged.connect(self.update_test_result)
        self.combo_insert_pos_spin.valueChanged.connect(self.update_test_result)
        self.combo_insert_content_edit.textChanged.connect(self.update_test_result)
        self.combo_start_spin.valueChanged.connect(self.update_test_result)
        self.combo_length_spin.valueChanged.connect(self.update_test_result)
    
    def on_combo_prefix_toggled(self, checked):
        """组合配置-前缀复选框状态变化"""
        self.combo_prefix_spin.setEnabled(checked)
        self.update_test_result()
    
    def on_combo_suffix_toggled(self, checked):
        """组合配置-后缀复选框状态变化"""
        self.combo_suffix_spin.setEnabled(checked)
        self.update_test_result()
    
    def on_combo_insert_toggled(self, checked):
        """组合配置-插入复选框状态变化"""
        self.combo_insert_pos_spin.setEnabled(checked)
        self.combo_insert_content_edit.setEnabled(checked)
        self.update_test_result()
    
    def on_combo_extract_toggled(self, checked):
        """组合配置-提取复选框状态变化"""
        self.combo_start_spin.setEnabled(checked)
        self.combo_length_spin.setEnabled(checked)
        self.update_test_result()
    
    def load_config(self):
        """加载配置"""
        try:
            config_str = db.get_setting('scan_config', None)
            if config_str and isinstance(config_str, str):
                import json
                config = json.loads(config_str)
            elif isinstance(config_str, dict):
                config = config_str
            else:
                config = {
                    'process_type': 0,
                    'prefix_length': 1,
                    'suffix_length': 1,
                    'start_pos': 1,
                    'extract_length': 5,
                    'insert_position': 0,
                    'insert_content': '',
                    'combo_remove_prefix': False,
                    'combo_prefix_length': 1,
                    'combo_remove_suffix': False,
                    'combo_suffix_length': 1,
                    'combo_insert_chars': False,
                    'combo_insert_position': 0,
                    'combo_insert_content': '',
                    'combo_extract_middle': False,
                    'combo_start_pos': 1,
                    'combo_extract_length': 5
                }
        except (json.JSONDecodeError, TypeError):
            # 如果配置解析失败，使用默认配置
            config = {
                'process_type': 0,
                'prefix_length': 1,
                'suffix_length': 1,
                'start_pos': 1,
                'extract_length': 5,
                'insert_position': 0,
                'insert_content': '',
                'combo_remove_prefix': False,
                'combo_prefix_length': 1,
                'combo_remove_suffix': False,
                'combo_suffix_length': 1,
                'combo_insert_chars': False,
                'combo_insert_position': 0,
                'combo_insert_content': '',
                'combo_extract_middle': False,
                'combo_start_pos': 1,
                'combo_extract_length': 5
            }
        
        # 加载基本配置
        self.process_group.button(config.get('process_type', 0)).setChecked(True)
        self.prefix_length_spin.setValue(config.get('prefix_length', 1))
        self.suffix_length_spin.setValue(config.get('suffix_length', 1))
        self.start_pos_spin.setValue(config.get('start_pos', 1))
        self.extract_length_spin.setValue(config.get('extract_length', 5))
        
        # 加载字符插入配置
        self.insert_position_spin.setValue(config.get('insert_position', 0))
        self.insert_content_edit.setText(config.get('insert_content', ''))
        
        # 加载组合配置
        self.combo_remove_prefix_check.setChecked(config.get('combo_remove_prefix', False))
        self.combo_prefix_spin.setValue(config.get('combo_prefix_length', 1))
        self.combo_prefix_spin.setEnabled(config.get('combo_remove_prefix', False))
        
        self.combo_remove_suffix_check.setChecked(config.get('combo_remove_suffix', False))
        self.combo_suffix_spin.setValue(config.get('combo_suffix_length', 1))
        self.combo_suffix_spin.setEnabled(config.get('combo_remove_suffix', False))
        
        self.combo_insert_check.setChecked(config.get('combo_insert_chars', False))
        self.combo_insert_pos_spin.setValue(config.get('combo_insert_position', 0))
        self.combo_insert_content_edit.setText(config.get('combo_insert_content', ''))
        combo_insert_enabled = config.get('combo_insert_chars', False)
        self.combo_insert_pos_spin.setEnabled(combo_insert_enabled)
        self.combo_insert_content_edit.setEnabled(combo_insert_enabled)
        
        self.combo_extract_check.setChecked(config.get('combo_extract_middle', False))
        self.combo_start_spin.setValue(config.get('combo_start_pos', 1))
        self.combo_length_spin.setValue(config.get('combo_extract_length', 5))
        combo_extract_enabled = config.get('combo_extract_middle', False)
        self.combo_start_spin.setEnabled(combo_extract_enabled)
        self.combo_length_spin.setEnabled(combo_extract_enabled)
    
    def save_config(self):
        """保存配置"""
        config = {
            'process_type': self.process_group.checkedId(),
            'prefix_length': self.prefix_length_spin.value(),
            'suffix_length': self.suffix_length_spin.value(),
            'start_pos': self.start_pos_spin.value(),
            'extract_length': self.extract_length_spin.value(),
            'insert_position': self.insert_position_spin.value(),
            'insert_content': self.insert_content_edit.text(),
            'combo_remove_prefix': self.combo_remove_prefix_check.isChecked(),
            'combo_prefix_length': self.combo_prefix_spin.value(),
            'combo_remove_suffix': self.combo_remove_suffix_check.isChecked(),
            'combo_suffix_length': self.combo_suffix_spin.value(),
            'combo_insert_chars': self.combo_insert_check.isChecked(),
            'combo_insert_position': self.combo_insert_pos_spin.value(),
            'combo_insert_content': self.combo_insert_content_edit.text(),
            'combo_extract_middle': self.combo_extract_check.isChecked(),
            'combo_start_pos': self.combo_start_spin.value(),
            'combo_extract_length': self.combo_length_spin.value()
        }
        
        db.set_setting('scan_config', config)
        self.accept()
    
    def update_test_result(self):
        """更新测试结果"""
        input_text = self.test_input.text()
        if not input_text:
            self.test_result.setText("")
            return
        
        result = self.process_scan_code(input_text)
        self.test_result.setText(result)
    
    def process_scan_code(self, code):
        """处理扫码"""
        process_type = self.process_group.checkedId()
        
        if process_type == 0:  # 不处理
            return code
        elif process_type == 1:  # 去掉前缀
            length = self.prefix_length_spin.value()
            return code[length:] if len(code) > length else ""
        elif process_type == 2:  # 去掉后缀
            length = self.suffix_length_spin.value()
            return code[:-length] if len(code) > length else ""
        elif process_type == 3:  # 提取中间
            start = self.start_pos_spin.value() - 1  # 转为0基索引
            length = self.extract_length_spin.value()
            return code[start:start+length] if len(code) > start else ""
        elif process_type == 4:  # 插入字符
            position = self.insert_position_spin.value()
            content = self.insert_content_edit.text()
            if position == 0:  # 插入到开头
                return content + code
            elif position >= len(code):  # 插入到末尾
                return code + content
            else:  # 插入到中间
                return code[:position] + content + code[position:]
        elif process_type == 5:  # 组合配置
            result = code
            
            # 执行顺序：去前缀 → 去后缀 → 插入字符 → 提取中间字符
            
            # 1. 去掉前缀
            if self.combo_remove_prefix_check.isChecked():
                length = self.combo_prefix_spin.value()
                result = result[length:] if len(result) > length else ""
            
            # 2. 去掉后缀
            if self.combo_remove_suffix_check.isChecked():
                length = self.combo_suffix_spin.value()
                result = result[:-length] if len(result) > length else ""
            
            # 3. 插入字符
            if self.combo_insert_check.isChecked():
                position = self.combo_insert_pos_spin.value()
                content = self.combo_insert_content_edit.text()
                if position == 0:  # 插入到开头
                    result = content + result
                elif position >= len(result):  # 插入到末尾
                    result = result + content
                else:  # 插入到中间
                    result = result[:position] + content + result[position:]
            
            # 4. 提取中间字符
            if self.combo_extract_check.isChecked():
                start = self.combo_start_spin.value() - 1  # 转为0基索引
                length = self.combo_length_spin.value()
                result = result[start:start+length] if len(result) > start else ""
            
            return result
        
        return code

class PackageDialog(QDialog):
    """包装对话框"""
    def __init__(self, package_data=None, parent=None, order_id=None):
        super().__init__(parent)
        self.package_data = package_data
        self.order_id = order_id
        self.setWindowTitle("包装详情" if package_data else "新建包装")
        self.setModal(True)
        self.resize(600, 500)
        
        self.init_ui()
        if package_data:
            self.load_package_data()
            # 逻辑限制：已入托包裹不可编辑
            try:
                conn = db.get_connection()
                c = conn.cursor()
                c.execute('SELECT pallet_id FROM packages WHERE id = ?', (self.package_data['id'],))
                r = c.fetchone()
                conn.close()
                if r and r[0]:
                    # 禁用可编辑控件
                    self.order_combo.setEnabled(False)
                    self.pack_type_combo.setEnabled(False)
                    self.remarks_edit.setReadOnly(True)
                    # 板件区禁用手动添加输入
                    self.manual_component_name.setEnabled(False)
                    self.manual_material.setEnabled(False)
                    self.manual_size.setEnabled(False)
                    self.manual_code.setEnabled(False)
                    self.manual_room.setEnabled(False)
                    self.manual_cabinet.setEnabled(False)
                    # 完成/重新打开按钮禁用
                    self.complete_btn.setEnabled(False)
                    self.reopen_btn.setEnabled(False)
                    self.setWindowTitle("包装详情（已入托，只读）")
            except Exception:
                pass
        elif order_id:
            # 如果是新建包装且指定了订单ID，设置默认订单
            self.set_default_order(order_id)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 包装信息
        info_group = QGroupBox("包装信息")
        info_layout = QGridLayout(info_group)
        
        info_layout.addWidget(QLabel("包装号:"), 0, 0)
        self.package_number_label = QLabel()
        info_layout.addWidget(self.package_number_label, 0, 1)
        
        info_layout.addWidget(QLabel("订单号:"), 1, 0)
        self.order_combo = QComboBox()
        self.load_orders()
        info_layout.addWidget(self.order_combo, 1, 1)
        
        info_layout.addWidget(QLabel("打包方式:"), 2, 0)
        self.pack_type_combo = QComboBox()
        self.pack_type_combo.addItems(['按房间分组', '按柜号分组', '混合打包'])
        info_layout.addWidget(self.pack_type_combo, 2, 1)
        
        info_layout.addWidget(QLabel("备注:"), 3, 0)
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(60)
        info_layout.addWidget(self.remarks_edit, 3, 1)
        
        # 添加状态信息
        info_layout.addWidget(QLabel("包装状态:"), 4, 0)
        self.status_label = QLabel("未完成")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        info_layout.addWidget(self.status_label, 4, 1)
        
        info_layout.addWidget(QLabel("板件数量:"), 5, 0)
        self.component_count_label = QLabel("0")
        info_layout.addWidget(self.component_count_label, 5, 1)
        
        layout.addWidget(info_group)
        
        # 板件列表
        components_group = QGroupBox("板件列表")
        components_layout = QVBoxLayout(components_group)
        
        # 手动输入板件工具栏
        manual_input_layout = QHBoxLayout()
        manual_input_layout.addWidget(QLabel("手动添加板件:"))
        
        self.manual_component_name = QLineEdit()
        self.manual_component_name.setPlaceholderText("板件名")
        self.manual_component_name.setMaximumWidth(120)
        manual_input_layout.addWidget(self.manual_component_name)
        
        self.manual_material = QLineEdit()
        self.manual_material.setPlaceholderText("材质")
        self.manual_material.setMaximumWidth(80)
        manual_input_layout.addWidget(self.manual_material)
        
        self.manual_size = QLineEdit()
        self.manual_size.setPlaceholderText("成品尺寸")
        self.manual_size.setMaximumWidth(120)
        manual_input_layout.addWidget(self.manual_size)
        
        self.manual_code = QLineEdit()
        self.manual_code.setPlaceholderText("板件编码")
        self.manual_code.setMaximumWidth(150)
        manual_input_layout.addWidget(self.manual_code)
        
        self.manual_room = QLineEdit()
        self.manual_room.setPlaceholderText("房间号")
        self.manual_room.setMaximumWidth(80)
        manual_input_layout.addWidget(self.manual_room)
        
        self.manual_cabinet = QLineEdit()
        self.manual_cabinet.setPlaceholderText("柜号")
        self.manual_cabinet.setMaximumWidth(80)
        manual_input_layout.addWidget(self.manual_cabinet)
        
        self.add_manual_component_btn = QPushButton("添加")
        self.add_manual_component_btn.clicked.connect(self.add_manual_component)
        self.add_manual_component_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        manual_input_layout.addWidget(self.add_manual_component_btn)
        
        manual_input_layout.addStretch()
        components_layout.addLayout(manual_input_layout)
        
        self.components_table = QTableWidget()
        self.components_table.setColumnCount(8)
        self.components_table.setHorizontalHeaderLabels([
            '板件名', '材质', '成品尺寸', '板件编码', '房间号', '柜号', '扫描时间', '操作'
        ])
        
        # 设置列宽
        self.components_table.setColumnWidth(0, 120)  # 板件名
        self.components_table.setColumnWidth(1, 80)   # 材质
        self.components_table.setColumnWidth(2, 120)  # 成品尺寸
        self.components_table.setColumnWidth(3, 150)  # 板件编码
        self.components_table.setColumnWidth(4, 80)   # 房间号
        self.components_table.setColumnWidth(5, 80)   # 柜号
        self.components_table.setColumnWidth(6, 140)  # 扫描时间
        self.components_table.setColumnWidth(7, 80)   # 操作
        
        self.components_table.horizontalHeader().setStretchLastSection(False)
        components_layout.addWidget(self.components_table)
        
        layout.addWidget(components_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        if not self.package_data:  # 新建包装
            self.create_btn = QPushButton("创建包装")
            self.create_btn.clicked.connect(self.create_package)
            button_layout.addWidget(self.create_btn)
        else:  # 编辑现有包装
            self.complete_btn = QPushButton("完成打包")
            self.complete_btn.clicked.connect(self.complete_package)
            self.complete_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            button_layout.addWidget(self.complete_btn)
            
            self.reopen_btn = QPushButton("重新打开")
            self.reopen_btn.clicked.connect(self.reopen_package)
            button_layout.addWidget(self.reopen_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def load_orders(self):
        """加载订单列表"""
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, order_number FROM orders WHERE status = "active"')
        orders = cursor.fetchall()
        conn.close()
        
        self.order_combo.clear()
        for order in orders:
            self.order_combo.addItem(order[1], order[0])
    
    def set_default_order(self, order_id):
        """设置默认订单"""
        for i in range(self.order_combo.count()):
            if self.order_combo.itemData(i) == order_id:
                self.order_combo.setCurrentIndex(i)
                break
    
    def load_package_data(self):
        """加载包装数据"""
        if not self.package_data:
            return
        
        self.package_number_label.setText(self.package_data['package_number'])
        
        # 设置订单
        for i in range(self.order_combo.count()):
            if self.order_combo.itemData(i) == self.package_data['order_id']:
                self.order_combo.setCurrentIndex(i)
                break
        
        self.pack_type_combo.setCurrentText(self.package_data.get('pack_type', ''))
        self.remarks_edit.setPlainText(self.package_data.get('remarks', ''))
        
        # 更新状态显示
        self.update_status_display()
        
        # 加载板件列表
        self.load_package_components()
    
    def load_package_components(self):
        """加载包装中的板件"""
        if not self.package_data:
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.component_name, c.material, c.finished_size, c.component_code,
                   c.room_number, c.cabinet_number, c.scanned_at
            FROM components c
            WHERE c.package_id = ?
            ORDER BY c.scanned_at
        ''', (self.package_data['id'],))
        components = cursor.fetchall()
        conn.close()
        
        print(f"加载包裹 {self.package_data['id']} 的板件数据:")
        for comp in components:
            print(f"  板件: {comp}")
        
        self.components_table.setRowCount(len(components))
        for i, component in enumerate(components):
            print(f"  处理第{i}行数据: {component}")
            for j, value in enumerate(component):
                item_text = str(value) if value else ''
                item = QTableWidgetItem(item_text)
                self.components_table.setItem(i, j, item)
                print(f"    设置第{i}行第{j}列: '{item_text}'")
                if j == 2:  # 成品尺寸列
                    print(f"    *** 成品尺寸列设置: '{item_text}' ***")
                    # 验证设置是否成功
                    check_item = self.components_table.item(i, j)
                    if check_item:
                        print(f"    验证成功，表格中的值: '{check_item.text()}'")
                    else:
                        print(f"    验证失败，表格中没有找到项目")
            
            # 添加删除按钮
            remove_btn = QPushButton("移除")
            remove_btn.clicked.connect(lambda checked, row=i: self.remove_component(row))
            self.components_table.setCellWidget(i, 7, remove_btn)
    
    def add_manual_component(self):
        """手动添加板件"""
        # 获取输入的数据
        component_name = self.manual_component_name.text().strip()
        material = self.manual_material.text().strip()
        size = self.manual_size.text().strip()
        code = self.manual_code.text().strip()
        room = self.manual_room.text().strip()
        cabinet = self.manual_cabinet.text().strip()
        
        # 验证必填字段
        if not component_name:
            QMessageBox.warning(self, "警告", "请输入板件名")
            return
        
        if not code:
            QMessageBox.warning(self, "警告", "请输入板件编码")
            return
        
        # 添加到表格
        row_count = self.components_table.rowCount()
        self.components_table.insertRow(row_count)
        
        # 设置数据
        self.components_table.setItem(row_count, 0, QTableWidgetItem(component_name))
        self.components_table.setItem(row_count, 1, QTableWidgetItem(material))
        self.components_table.setItem(row_count, 2, QTableWidgetItem(size))
        self.components_table.setItem(row_count, 3, QTableWidgetItem(code))
        self.components_table.setItem(row_count, 4, QTableWidgetItem(room))
        self.components_table.setItem(row_count, 5, QTableWidgetItem(cabinet))
        self.components_table.setItem(row_count, 6, QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # 添加删除按钮
        remove_btn = QPushButton("移除")
        remove_btn.clicked.connect(lambda checked, row=row_count: self.remove_component(row))
        self.components_table.setCellWidget(row_count, 7, remove_btn)
        
        # 清空输入框
        self.manual_component_name.clear()
        self.manual_material.clear()
        self.manual_size.clear()
        self.manual_code.clear()
        self.manual_room.clear()
        self.manual_cabinet.clear()
        
        # 更新板件数量显示
        self.update_component_count()
        
        QMessageBox.information(self, "成功", "板件添加成功")
    
    def remove_component(self, row):
        """移除板件"""
        reply = QMessageBox.question(self, "确认", "确定要移除这个板件吗？", 
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.components_table.removeRow(row)
            self.update_component_count()
    
    def update_component_count(self):
        """更新板件数量显示"""
        count = self.components_table.rowCount()
        self.component_count_label.setText(str(count))
    
    def create_package(self):
        """创建包装"""
        order_id = self.order_combo.currentData()
        if not order_id:
            QMessageBox.warning(self, "警告", "请选择订单")
            return
        
        # 检查是否有手动添加的板件
        has_manual_components = self.components_table.rowCount() > 0
        
        pack_type = self.pack_type_combo.currentText()
        # 映射打包方式到存储值
        pack_method_map = {
            '按房间分组': 'by_room',
            '按柜号分组': 'by_cabinet',
            '混合打包': 'mixed'
        }
        packing_method = pack_method_map.get(pack_type, 'mixed')
        remarks = self.remarks_edit.toPlainText()
        
        try:
            package_number = db.generate_package_number()
            
            # 将pack_type和remarks合并到notes字段中
            notes = f"打包方式: {pack_type}"
            if remarks.strip():
                notes += f"\n备注: {remarks}"
            if has_manual_components:
                notes += "\n包含手动添加的板件"
            
            conn = db.get_connection()
            try:
                cursor = conn.cursor()
                
                # 如选择按房间/柜号分组，且有手动板件，校验一致性
                if has_manual_components:
                    if packing_method == 'by_room':
                        rooms = set()
                        for row in range(self.components_table.rowCount()):
                            room = self.components_table.item(row, 4).text() if self.components_table.item(row, 4) else ""
                            if room:
                                rooms.add(room.strip())
                        if len(rooms) > 1:
                            QMessageBox.warning(self, "警告", f"按房间分组时，板件房间号需一致。当前房间号: {', '.join(sorted(rooms))}")
                            try:
                                voice_speak("房间号不一致，请检查")
                            except Exception:
                                pass
                            return
                    elif packing_method == 'by_cabinet':
                        cabinets = set()
                        for row in range(self.components_table.rowCount()):
                            cabinet = self.components_table.item(row, 5).text() if self.components_table.item(row, 5) else ""
                            if cabinet:
                                cabinets.add(cabinet.strip())
                        if len(cabinets) > 1:
                            QMessageBox.warning(self, "警告", f"按柜号分组时，板件柜号需一致。当前柜号: {', '.join(sorted(cabinets))}")
                            try:
                                voice_speak("柜号不一致，请检查")
                            except Exception:
                                pass
                            return

                # 计算稳定包裹序号（每订单内填补缺口）
                try:
                    next_index = db.get_next_package_index(order_id)
                except Exception:
                    next_index = None

                # 创建包装，保存稳定序号package_index；若有手动板件则标记为手动创建
                cursor.execute('''
                    INSERT INTO packages (package_number, order_id, package_index, packing_method, notes, status, created_at, is_manual)
                    VALUES (?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP, ?)
                ''', (package_number, order_id, next_index, packing_method, notes, 1 if has_manual_components else 0))
                
                package_id = cursor.lastrowid
                
                # 保存手动添加的板件
                if has_manual_components:
                    for row in range(self.components_table.rowCount()):
                        component_name = self.components_table.item(row, 0).text() if self.components_table.item(row, 0) else ""
                        material = self.components_table.item(row, 1).text() if self.components_table.item(row, 1) else ""
                        size = self.components_table.item(row, 2).text() if self.components_table.item(row, 2) else ""
                        code = self.components_table.item(row, 3).text() if self.components_table.item(row, 3) else ""
                        room = self.components_table.item(row, 4).text() if self.components_table.item(row, 4) else ""
                        cabinet = self.components_table.item(row, 5).text() if self.components_table.item(row, 5) else ""
                        
                        # 插入手动添加的板件
                        cursor.execute('''
                            INSERT INTO components 
                            (order_id, component_name, material, finished_size, component_code, 
                             room_number, cabinet_number, package_id, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'packed')
                        ''', (order_id, component_name, material, size, code, room, cabinet, package_id))
                
                # 更新包装的板件数量
                cursor.execute('''
                    UPDATE packages SET component_count = (
                        SELECT COUNT(*) FROM components WHERE package_id = ?
                    ) WHERE id = ?
                ''', (package_id, package_id))
                
                conn.commit()
                
                # 记录操作日志
                db.log_operation('create_package', {
                    'package_number': package_number,
                    'order_id': order_id,
                    'pack_type': pack_type,
                    'packing_method': packing_method,
                    'is_manual': has_manual_components,
                    'manual_component_count': self.components_table.rowCount() if has_manual_components else 0
                })
                
                QMessageBox.information(self, "成功", f"包装 {package_number} 创建成功")
                self.accept()
                
            finally:
                conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建包装失败：\n{str(e)}")
    
    def remove_component(self, row):
        """移除板件"""
        if not self.package_data:
            return
        
        reply = QMessageBox.question(self, "确认", "确定要移除这个板件吗？")
        if reply == QMessageBox.Yes:
            # 这里需要实现移除逻辑
            self.components_table.removeRow(row)
    
    def update_status_display(self):
        """更新状态显示"""
        if not self.package_data:
            return
        
        # 获取包装状态
        status = self.package_data.get('status', 'open')
        if status == 'completed':
            self.status_label.setText("已完成")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.complete_btn.setEnabled(False)
            self.reopen_btn.setEnabled(True)
        else:
            self.status_label.setText("未完成")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            if hasattr(self, 'complete_btn'):
                self.complete_btn.setEnabled(True)
            if hasattr(self, 'reopen_btn'):
                self.reopen_btn.setEnabled(False)
        
        # 获取板件数量
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM components WHERE package_id = ?', (self.package_data['id'],))
        count = cursor.fetchone()[0]
        conn.close()
        
        self.component_count_label.setText(str(count))
    
    def complete_package(self):
        """完成打包"""
        if not self.package_data:
            return
        
        reply = QMessageBox.question(self, "确认", "确定要完成这个包装吗？完成后将无法继续添加板件。")
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE packages 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (self.package_data['id'],))
                conn.commit()
                conn.close()
                
                self.package_data['status'] = 'completed'
                self.update_status_display()
                
                QMessageBox.information(self, "成功", "包装已完成！")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"完成包装失败：\n{str(e)}")
    
    def reopen_package(self):
        """重新打开包装"""
        if not self.package_data:
            return
        
        reply = QMessageBox.question(self, "确认", "确定要重新打开这个包装吗？")
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE packages 
                    SET status = 'open', completed_at = NULL 
                    WHERE id = ?
                ''', (self.package_data['id'],))
                conn.commit()
                conn.close()
                
                self.package_data['status'] = 'open'
                self.update_status_display()
                
                QMessageBox.information(self, "成功", "包装已重新打开！")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重新打开包装失败：\n{str(e)}")

class ScanPackaging(QWidget):
    """扫描打包模块"""
    
    # 信号
    component_scanned = pyqtSignal(dict)
    package_completed = pyqtSignal(str)
    components_deleted_from_pending = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.current_package_id = None
        self.current_order_id = None  # 初始化时没有选择订单
        self.current_package_status = None  # 当前包装状态
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.process_scan_input)
        self.scan_buffer = ""
        
        # 板件编码搜索防抖定时器
        self.component_search_timer = QTimer()
        self.component_search_timer.setSingleShot(True)
        self.component_search_timer.timeout.connect(self.perform_component_search)
        self.pending_component_search = ""
        
        self.init_ui()
        self.load_active_packages()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 订单选择
        self.order_select_btn = QPushButton("选择订单")
        self.order_select_btn.setMinimumWidth(150)
        self.order_select_btn.clicked.connect(self.select_order_dialog)
        toolbar_layout.addWidget(self.order_select_btn)
        
        # 当前选中的订单信息
        # self.current_order_label = QLabel("未选择订单")
        # self.current_order_label.setStyleSheet("color: gray; font-style: italic;")
        # toolbar_layout.addWidget(self.current_order_label)
        
        self.new_package_btn = QPushButton("新建包装")
        self.new_package_btn.clicked.connect(self.new_package)
        self.new_package_btn.setEnabled(False)  # 默认禁用，需要先选择订单
        toolbar_layout.addWidget(self.new_package_btn)
        
        self.delete_package_btn = QPushButton("删除包裹")
        self.delete_package_btn.clicked.connect(self.delete_package)
        self.delete_package_btn.setEnabled(False)
        toolbar_layout.addWidget(self.delete_package_btn)
        
        self.scan_config_btn = QPushButton("扫码配置")
        self.scan_config_btn.clicked.connect(self.scan_config)
        toolbar_layout.addWidget(self.scan_config_btn)
        
        self.pending_components_btn = QPushButton("待包板件")
        self.pending_components_btn.clicked.connect(self.show_pending_components)
        toolbar_layout.addWidget(self.pending_components_btn)
        
        self.print_label_btn = QPushButton("🖨️ 打印标签")
        self.print_label_btn.clicked.connect(self.print_package_label)
        self.print_label_btn.setEnabled(False)  # 默认禁用，需要选择包装
        self.print_label_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        toolbar_layout.addWidget(self.print_label_btn)
        
        toolbar_layout.addStretch()
        
        # 查找功能
        toolbar_layout.addWidget(QLabel("查找包裹号:"))
        self.package_search = QLineEdit()
        self.package_search.setPlaceholderText("输入包裹号...")
        self.package_search.setMaximumWidth(120)
        self.package_search.textChanged.connect(self.search_package_by_number)
        toolbar_layout.addWidget(self.package_search)
        
        toolbar_layout.addWidget(QLabel("查找板件:"))
        self.component_search = QLineEdit()
        self.component_search.setPlaceholderText("输入板件编码...")
        self.component_search.setMaximumWidth(120)
        self.component_search.textChanged.connect(self.on_component_search_text_changed)
        toolbar_layout.addWidget(self.component_search)
        
        self.search_btn = QPushButton("查找")
        self.search_btn.clicked.connect(self.perform_search)
        toolbar_layout.addWidget(self.search_btn)
        
        self.clear_search_btn = QPushButton("显示全部")
        self.clear_search_btn.clicked.connect(self.clear_search)
        toolbar_layout.addWidget(self.clear_search_btn)
        
        layout.addLayout(toolbar_layout)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：包装列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        left_layout.addWidget(QLabel("活动包装"))
        
        self.packages_table = QTableWidget()
        self.packages_table.setColumnCount(6)
        self.packages_table.setHorizontalHeaderLabels([
            '包装号', '订单号', '包裹序号', '板件数量', '创建时间', '状态'
        ])
        self.packages_table.horizontalHeader().setStretchLastSection(True)
        self.packages_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.packages_table.setSelectionMode(QTableWidget.SingleSelection)
        self.packages_table.setAlternatingRowColors(True)
        self.packages_table.setStyleSheet("QTableWidget::item:selected{background-color: rgba(255,224,130,0.7); color:black;}")
        self.packages_table.itemSelectionChanged.connect(self.on_package_selected)
        # 确保垂直滚动条始终可见
        self.packages_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # 右键菜单：预览/保存二维码、复制包裹号
        self.packages_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.packages_table.customContextMenuRequested.connect(self.on_packages_context_menu)
        left_layout.addWidget(self.packages_table)
        
        splitter.addWidget(left_widget)
        
        # 右侧：扫描区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 当前包装信息
        current_group = QGroupBox("当前包装")
        current_layout = QGridLayout(current_group)
        
        current_layout.addWidget(QLabel("包装号:"), 0, 0)
        self.current_package_label = QLabel("未选择")
        current_layout.addWidget(self.current_package_label, 0, 1)
        
        current_layout.addWidget(QLabel("订单号:"), 1, 0)
        self.current_order_label = QLabel("-")
        current_layout.addWidget(self.current_order_label, 1, 1)
        
        current_layout.addWidget(QLabel("板件数量:"), 2, 0)
        self.current_count_label = QLabel("0")
        current_layout.addWidget(self.current_count_label, 2, 1)

        current_layout.addWidget(QLabel("打包方式:"), 3, 0)
        self.current_packing_method_label = QLabel("-")
        current_layout.addWidget(self.current_packing_method_label, 3, 1)
        
        # 顶部信息区：左为当前包装，右为订单统计
        current_info_layout = QHBoxLayout()
        current_info_layout.addWidget(current_group, 1)  # 左侧占比1

        order_stats_group = QGroupBox("订单统计")
        stats_layout = QGridLayout(order_stats_group)
        stats_layout.addWidget(QLabel("总板件数:"), 0, 0)
        self.stats_total_components_label = QLabel("-")
        stats_layout.addWidget(self.stats_total_components_label, 0, 1)

        stats_layout.addWidget(QLabel("已包装板件数:"), 0, 2)
        self.stats_packaged_components_label = QLabel("-")
        stats_layout.addWidget(self.stats_packaged_components_label, 0, 3)

        stats_layout.addWidget(QLabel("未包装板件数:"), 1, 0)
        self.stats_unpacked_label = QLabel("-")
        stats_layout.addWidget(self.stats_unpacked_label, 1, 1)

        stats_layout.addWidget(QLabel("总包裹数:"), 1, 2)
        self.stats_total_packages_label = QLabel("-")
        stats_layout.addWidget(self.stats_total_packages_label, 1, 3)

        stats_layout.addWidget(QLabel("手动添加包裹数:"), 2, 0)
        self.stats_manual_packages_label = QLabel("-")
        stats_layout.addWidget(self.stats_manual_packages_label, 2, 1)

        stats_layout.addWidget(QLabel("手动添加总板件数量:"), 2, 2)
        self.stats_manual_components_label = QLabel("-")
        stats_layout.addWidget(self.stats_manual_components_label, 2, 3)

        stats_layout.addWidget(QLabel("包装进度:"), 3, 0)
        self.stats_progress_label = QLabel("-")
        stats_layout.addWidget(self.stats_progress_label, 3, 1, 1, 3)

        current_info_layout.addWidget(order_stats_group, 2)  # 右侧占比2
        right_layout.addLayout(current_info_layout)
        
        # 扫描输入
        scan_group = QGroupBox("扫描输入")
        scan_layout = QVBoxLayout(scan_group)
        
        scan_input_layout = QHBoxLayout()
        scan_input_layout.addWidget(QLabel("扫码:"))
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("请扫描板件Q码或通用完成码")
        self.scan_input.returnPressed.connect(self.manual_scan)
        scan_input_layout.addWidget(self.scan_input)
        
        self.manual_scan_btn = QPushButton("手动扫描")
        self.manual_scan_btn.clicked.connect(self.manual_scan)
        scan_input_layout.addWidget(self.manual_scan_btn)
        
        scan_layout.addLayout(scan_input_layout)
        
        # 完成包装按钮
        self.finish_package_btn = QPushButton("完成包装")
        self.finish_package_btn.clicked.connect(self.finish_package)
        self.finish_package_btn.setEnabled(False)
        scan_layout.addWidget(self.finish_package_btn)
        
        # 解包按钮
        self.unpack_btn = QPushButton("解包")
        self.unpack_btn.clicked.connect(self.unpack_package)
        self.unpack_btn.setEnabled(False)
        scan_layout.addWidget(self.unpack_btn)
        
        # 扫描历史
        self.scan_history = QTextEdit()
        self.scan_history.setMaximumHeight(100)
        self.scan_history.setReadOnly(True)
        scan_layout.addWidget(QLabel("扫描历史:"))
        scan_layout.addWidget(self.scan_history)
        
        right_layout.addWidget(scan_group)
        
        # 当前包装板件列表
        components_group = QGroupBox("当前包装板件")
        components_layout = QVBoxLayout(components_group)
        
        self.current_components_table = QTableWidget()
        self.current_components_table.setColumnCount(8)
        self.current_components_table.setHorizontalHeaderLabels([
            '板件名', '材质', '板件编码', '房间号', '柜号', '板件尺寸', '扫描时间', '操作'
        ])
        self.current_components_table.horizontalHeader().setStretchLastSection(True)
        components_layout.addWidget(self.current_components_table)
        
        right_layout.addWidget(components_group)
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setSizes([400, 600])
        
        # 初始状态设置：没有选择包装时禁用扫描功能
        self.scan_input.setEnabled(False)
        self.manual_scan_btn.setEnabled(False)
        
        # 设置焦点
        self.scan_input.setFocus()
    

    
    def select_order_dialog(self):
        """打开订单选择对话框"""
        dialog = OrderSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_order = dialog.get_selected_order()
            if selected_order:
                self.current_order_id = selected_order['id']
                # 更新按钮文本和标签
                self.order_select_btn.setText(f"订单: {selected_order['order_number']}")
                self.current_order_label.setText(f"{selected_order['customer_name'] or '未知客户'}")
                self.current_order_label.setStyleSheet("color: black; font-style: normal;")
                self.new_package_btn.setEnabled(True)
                # 重新加载包装列表
                self.load_active_packages()
                # 刷新订单统计
                self.update_order_stats()
    
    def on_order_selected(self):
        """订单选择事件（保留用于兼容性）"""
        # 这个方法现在主要用于其他地方的兼容性
        pass
    
    def delete_package(self):
        """删除选中的包裹"""
        current_row = self.packages_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要删除的包裹")
            return
        
        package_number = self.packages_table.item(current_row, 0).text()
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除包裹 {package_number} 吗？\n仅允许删除未封包且未入托的包裹。",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                # 获取包裹ID
                cursor.execute('SELECT id, status, pallet_id FROM packages WHERE package_number = ?', (package_number,))
                package_result = cursor.fetchone()
                if not package_result:
                    QMessageBox.warning(self, "错误", "找不到指定的包裹")
                    return
                
                package_id, status, pallet_id = package_result
                # 仅允许删除open状态且未入托的包裹
                if pallet_id is not None:
                    QMessageBox.warning(self, "警告", "包裹已在托盘中，不能删除")
                    conn.close()
                    return
                if status != 'open':
                    QMessageBox.warning(self, "警告", "仅允许删除未封包的包裹")
                    conn.close()
                    return
                
                # 将包裹内的板件状态还原为未打包
                cursor.execute('''
                    UPDATE components 
                    SET package_id = NULL, status = 'pending' 
                    WHERE package_id = ?
                ''', (package_id,))
                
                # 删除包裹
                cursor.execute('DELETE FROM packages WHERE id = ?', (package_id,))
                
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "成功", f"包裹 {package_number} 已删除，板件已还原为未打包状态")
                self.load_active_packages()
                # 云端删除同步：包裹（受系统设置控制）
                try:
                    if package_number:
                        from real_time_cloud_sync import get_sync_service
                        svc = getattr(self, 'cloud_sync_service', None) or get_sync_service()
                        svc.trigger_sync('delete_packages', {'items': [{'package_number': package_number}]}, force=True)
                except Exception as e:
                    print(f"触发云端删除包裹失败: {e}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除包裹失败：\n{str(e)}")
    
    def perform_search(self):
        """执行查找操作，验证输入并执行相应的搜索"""
        package_text = self.package_search.text().strip()
        component_text = self.component_search.text().strip()
        
        # 验证只能有一个输入框有内容
        if not package_text and not component_text:
            QMessageBox.warning(self, "提示", "请在查找包裹号或查找板件中输入内容")
            return
        
        if package_text and component_text:
            QMessageBox.warning(self, "提示", "请只在一个查找框中输入内容，不能同时查找包裹号和板件")
            return
        
        # 执行相应的搜索
        if package_text:
            self.search_package_by_number(package_text)
        elif component_text:
            self.search_component_by_code(component_text)
    
    def search_package_by_number(self, search_text):
        """根据包裹号搜索包裹"""
        search_text = search_text.strip()
        
        # 如果搜索框为空，显示所有包裹
        if not search_text:
            for row in range(self.packages_table.rowCount()):
                self.packages_table.setRowHidden(row, False)
            self.packages_table.clearSelection()
            return
        
        search_text = search_text.lower()
        found = False
        
        for row in range(self.packages_table.rowCount()):
            package_item = self.packages_table.item(row, 0)
            if package_item:
                package_number = package_item.text().lower()
                match = search_text in package_number
                self.packages_table.setRowHidden(row, not match)
                
                # 高亮显示匹配的行
                if match:
                    self.packages_table.selectRow(row)
                    found = True
    
    def search_component_by_code(self, search_text):
        """根据板件编码搜索包裹"""
        search_text = search_text.strip()
        
        # 如果搜索框为空，显示所有包裹
        if not search_text:
            for row in range(self.packages_table.rowCount()):
                self.packages_table.setRowHidden(row, False)
            self.packages_table.clearSelection()
            return
        
        # 对于实时搜索，只在输入长度大于等于2时才进行数据库查询
        if len(search_text) < 2:
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.package_number 
                FROM components c
                JOIN packages p ON c.package_id = p.id
                WHERE c.component_code LIKE ?
            ''', (f'%{search_text}%',))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                package_number = result[0]
                # 先隐藏所有行
                for row in range(self.packages_table.rowCount()):
                    self.packages_table.setRowHidden(row, True)
                
                # 只显示包含该板件的包裹
                found = False
                for row in range(self.packages_table.rowCount()):
                    package_item = self.packages_table.item(row, 0)
                    if package_item and package_item.text() == package_number:
                        self.packages_table.setRowHidden(row, False)
                        self.packages_table.selectRow(row)
                        found = True
                        break
                
                if not found:
                    # 如果没找到，显示所有行
                    for row in range(self.packages_table.rowCount()):
                        self.packages_table.setRowHidden(row, False)
            else:
                # 没找到时显示所有行
                for row in range(self.packages_table.rowCount()):
                    self.packages_table.setRowHidden(row, False)
                
        except Exception as e:
            # 静默处理错误，不显示弹窗
            # 出错时显示所有行
            for row in range(self.packages_table.rowCount()):
                self.packages_table.setRowHidden(row, False)

    def on_component_search_text_changed(self, text):
        """板件编码搜索框文本变化处理（防抖）"""
        self.pending_component_search = text
        self.component_search_timer.stop()
        self.component_search_timer.start(300)  # 300ms 防抖延迟
    
    def perform_component_search(self):
        """执行板件编码搜索"""
        self.search_component_by_code(self.pending_component_search)

    def search_package(self):
        """搜索包裹号"""
        search_text = self.package_search.text().lower()
        
        for row in range(self.packages_table.rowCount()):
            package_item = self.packages_table.item(row, 0)
            if package_item:
                package_number = package_item.text().lower()
                match = search_text == "" or search_text in package_number
                self.packages_table.setRowHidden(row, not match)
                
                # 高亮显示匹配的行
                if match and search_text != "":
                    self.packages_table.selectRow(row)
    
    def search_component(self):
        """搜索板件编码，找出所在包裹"""
        search_text = self.component_search.text().strip()
        
        if not search_text:
            # 清空搜索时显示所有包裹
            for row in range(self.packages_table.rowCount()):
                self.packages_table.setRowHidden(row, False)
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.package_number 
                FROM components c
                JOIN packages p ON c.package_id = p.id
                WHERE c.component_code LIKE ?
            ''', (f'%{search_text}%',))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                package_number = result[0]
                # 高亮显示包含该板件的包裹
                for row in range(self.packages_table.rowCount()):
                    package_item = self.packages_table.item(row, 0)
                    if package_item and package_item.text() == package_number:
                        self.packages_table.selectRow(row)
                        self.packages_table.setRowHidden(row, False)
                        QMessageBox.information(self, "找到板件", f"板件 {search_text} 在包裹 {package_number} 中")
                        break
            else:
                QMessageBox.information(self, "未找到", f"未找到包含板件编码 {search_text} 的包裹")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"搜索失败：\n{str(e)}")
    
    def clear_search(self):
        """清除搜索，显示所有包裹"""
        # 清空搜索框
        self.package_search.clear()
        self.component_search.clear()
        
        # 显示所有行
        for row in range(self.packages_table.rowCount()):
            self.packages_table.setRowHidden(row, False)
        
        # 清除选择
        self.packages_table.clearSelection()
    
    def load_active_packages(self):
        """加载活动包装列表"""
        # 如果没有选择订单，清空表格
        if not hasattr(self, 'current_order_id') or not self.current_order_id:
            self.packages_table.setRowCount(0)
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.package_number, o.order_number, p.package_index,
                   COUNT(c.id) as component_count,
                   p.created_at, p.status, p.is_manual
            FROM packages p
            LEFT JOIN orders o ON p.order_id = o.id
            LEFT JOIN components c ON p.id = c.package_id
            WHERE p.status IN ('open', 'completed', 'sealed') AND p.order_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        ''', (self.current_order_id,))
        packages = cursor.fetchall()
        conn.close()
        
        self.packages_table.setRowCount(len(packages))
        for i, package in enumerate(packages):
            self.packages_table.setItem(i, 0, QTableWidgetItem(package[1]))  # package_number
            self.packages_table.setItem(i, 1, QTableWidgetItem(package[2] or ''))  # order_number
            # 显示包裹序号
            self.packages_table.setItem(i, 2, QTableWidgetItem(str(package[3] or '')))  # package_index
            self.packages_table.setItem(i, 3, QTableWidgetItem(str(package[4])))  # component_count
            # 创建时间统一为 YYYY-MM-DD HH:mm:ss
            created_text = package[5]
            try:
                s = str(created_text)
                s = s.replace('T', ' ').replace('Z', '')
                dt = datetime.fromisoformat(s)
                created_text = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                created_text = str(created_text)
            self.packages_table.setItem(i, 4, QTableWidgetItem(created_text))  # created_at
            # 状态改为中文显示
            status_map = {
                'open': '进行中',
                'completed': '已完成',
                'sealed': '已封装'
            }
            status_text = status_map.get(package[6], str(package[6]))
            self.packages_table.setItem(i, 5, QTableWidgetItem(status_text))  # status
            
            # 存储包装ID
            self.packages_table.item(i, 0).setData(Qt.UserRole, package[0])

        # 刷新右侧订单统计
        self.update_order_stats()

    def on_packages_context_menu(self, pos):
        # 根据点击位置确定行
        item = self.packages_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        pkg_item = self.packages_table.item(row, 0)
        if not pkg_item:
            return
        package_number = pkg_item.text()

        menu = QMenu(self)
        act_preview = QAction("预览包裹二维码", self)
        act_save = QAction("保存包裹二维码", self)
        act_copy = QAction("复制包裹号", self)
        menu.addAction(act_preview)
        menu.addAction(act_save)
        menu.addSeparator()
        menu.addAction(act_copy)

        action = menu.exec_(self.packages_table.viewport().mapToGlobal(pos))
        if not action:
            return

        try:
            if action == act_copy:
                QApplication.clipboard().setText(package_number)
                return

            # 生成二维码图片
            handler = QRCodeHandler()
            pil_img = handler.create_qr_code_with_text(package_number)

            if action == act_preview:
                dlg = QRPreviewDialog(pil_img, package_number, self)
                dlg.exec_()
            elif action == act_save:
                default_name = f"package_{package_number}.png"
                fname, _ = QFileDialog.getSaveFileName(self, "保存包裹二维码", default_name, "PNG 图片 (*.png)")
                if fname:
                    pil_img.save(fname, format='PNG')
        except Exception as e:
            QMessageBox.critical(self, "错误", f"操作失败：\n{str(e)}")
            # 设置背景色
            is_manual = package[7] if len(package) > 7 else 0  # is_manual字段
            status = package[6]  # status字段
            
            if is_manual and status == 'completed':
                # 手动创建且已完成的包装设置浅红色背景
                light_red = QColor(255, 182, 193)  # 浅红色
                for j in range(6):  # 为所有列设置背景色
                    if self.packages_table.item(i, j):
                        self.packages_table.item(i, j).setBackground(light_red)
            elif status == 'completed':
                # 普通已完成的包装设置浅绿色背景
                light_green = QColor(144, 238, 144)  # 浅绿色
                for j in range(6):  # 为所有列设置背景色
                    if self.packages_table.item(i, j):
                        self.packages_table.item(i, j).setBackground(light_green)

        # 更新右侧订单统计
        self.update_order_stats()

    def update_order_stats(self):
        """更新右侧订单统计信息"""
        try:
            if not getattr(self, 'current_order_id', None):
                for lbl in [
                    self.stats_total_components_label,
                    self.stats_packaged_components_label,
                    self.stats_unpacked_label,
                    self.stats_total_packages_label,
                    self.stats_manual_packages_label,
                    self.stats_manual_components_label,
                    self.stats_progress_label
                ]:
                    lbl.setText('-')
                return

            conn = db.get_connection()
            cur = conn.cursor()

            # 总板件数、已包装板件数
            cur.execute('SELECT COUNT(*) FROM components WHERE order_id = ?', (self.current_order_id,))
            total_components = cur.fetchone()[0] or 0
            cur.execute('SELECT COUNT(*) FROM components WHERE order_id = ? AND package_id IS NOT NULL', (self.current_order_id,))
            packaged_components = cur.fetchone()[0] or 0
            unpacked_components = max(0, total_components - packaged_components)

            # 包裹统计
            cur.execute('SELECT COUNT(*) FROM packages WHERE order_id = ?', (self.current_order_id,))
            total_packages = cur.fetchone()[0] or 0
            cur.execute('SELECT COUNT(*) FROM packages WHERE order_id = ? AND is_manual = 1', (self.current_order_id,))
            manual_packages = cur.fetchone()[0] or 0
            cur.execute('SELECT COALESCE(SUM(component_count), 0) FROM packages WHERE order_id = ? AND is_manual = 1', (self.current_order_id,))
            manual_components_total = cur.fetchone()[0] or 0

            conn.close()

            # 进度
            progress_pct = (packaged_components / total_components * 100) if total_components else 0
            progress_text = f"{packaged_components}/{total_components}（{progress_pct:.1f}%）"

            # 写入标签
            self.stats_total_components_label.setText(str(total_components))
            self.stats_packaged_components_label.setText(str(packaged_components))
            self.stats_unpacked_label.setText(str(unpacked_components))
            self.stats_total_packages_label.setText(str(total_packages))
            self.stats_manual_packages_label.setText(str(manual_packages))
            self.stats_manual_components_label.setText(str(manual_components_total))
            self.stats_progress_label.setText(progress_text)
        except Exception:
            # 出错时保持静默，不影响主界面
            pass
    
    def on_package_selected(self):
        """包装选择事件"""
        current_row = self.packages_table.currentRow()
        if current_row >= 0:
            package_id = self.packages_table.item(current_row, 0).data(Qt.UserRole)
            self.select_package(package_id)
    
    def select_package(self, package_id):
        """选择包装"""
        self.current_package_id = package_id
        
        # 加载包装信息
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.package_number, o.order_number, p.status, p.packing_method
            FROM packages p
            LEFT JOIN orders o ON p.order_id = o.id
            WHERE p.id = ?
        ''', (package_id,))
        package = cursor.fetchone()
        
        if package:
            self.current_package_label.setText(package[0])
            self.current_order_label.setText(package[1] or '')
            # 显示打包方式（中文：房间/柜号/混包），兼容旧数据
            pm_map = {
                'by_room': '房间',
                'by_cabinet': '柜号',
                'mixed': '混包',
                'manual': '混包'
            }
            pm_value = package[3] if len(package) > 3 else None
            self.current_packing_method_label.setText(pm_map.get(pm_value, pm_value if pm_value else '-'))
            
            package_status = package[2]
            is_open = package_status == 'open'
            
            # 启用/禁用完成按钮（只有状态为'open'的包装才能完成）
            self.finish_package_btn.setEnabled(is_open)
            
            # 启用/禁用解包按钮（只有状态为'completed'的包装才能解包）
            self.unpack_btn.setEnabled(package_status == 'completed')
            
            # 启用删除按钮（选择了包裹就可以删除）
            self.delete_package_btn.setEnabled(True)
            
            # 启用打印标签按钮（选择了包装就可以打印标签）
            self.print_label_btn.setEnabled(True)
            
            # 根据包装状态控制扫描功能
            self.scan_input.setEnabled(is_open)
            self.manual_scan_btn.setEnabled(is_open)
            
            # 存储当前包装状态，用于控制移除按钮
            self.current_package_status = package_status
        
        # 加载包装板件
        self.load_current_package_components()
        
        conn.close()
    
    def load_current_package_components(self):
        """加载当前包装的板件"""
        if not self.current_package_id:
            self.current_components_table.setRowCount(0)
            self.current_count_label.setText("0")
            # 重置打包方式显示
            if hasattr(self, 'current_packing_method_label'):
                self.current_packing_method_label.setText("-")
            return
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.component_name, c.material, c.component_code,
                   c.room_number, c.cabinet_number, c.finished_size, c.updated_at
            FROM components c
            WHERE c.package_id = ?
            ORDER BY c.updated_at DESC
        ''', (self.current_package_id,))
        components = cursor.fetchall()
        conn.close()
        
        self.current_components_table.setRowCount(len(components))
        for i, component in enumerate(components):
            for j, value in enumerate(component[1:]):  # 跳过ID
                self.current_components_table.setItem(i, j, QTableWidgetItem(str(value) if value else ''))
            
            # 添加移除按钮
            remove_btn = QPushButton("移除")
            remove_btn.clicked.connect(lambda checked, comp_id=component[0]: self.remove_component_from_package(comp_id))
            # 根据包装状态控制移除按钮是否启用
            if hasattr(self, 'current_package_status'):
                remove_btn.setEnabled(self.current_package_status == 'open')
            self.current_components_table.setCellWidget(i, 7, remove_btn)
        
        self.current_count_label.setText(str(len(components)))
    
    def new_package(self):
        """新建包装"""
        if not self.current_order_id:
            QMessageBox.warning(self, "警告", "请先选择订单")
            return
            
        dialog = PackageDialog(parent=self, order_id=self.current_order_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_active_packages()
            self.update_order_stats()
    
    def scan_config(self):
        """扫码配置"""
        dialog = ScanConfigDialog(self)
        dialog.exec_()
    
    def manual_scan(self):
        """手动扫描"""
        code = self.scan_input.text().strip()
        if code:
            self.process_scan_code(code)
            self.scan_input.clear()
    
    def process_scan_code(self, raw_code):
        """处理扫描码"""
        if not self.current_package_id:
            QMessageBox.warning(self, "警告", "请先选择一个包装")
            return
        
        # 检查是否是通用完成码
        universal_code = db.get_setting('universal_finish_code', 'FINISH')
        if raw_code == universal_code:
            self.finish_package()
            self.new_package()
            return
        
        # 处理扫描码
        processed_code = self.apply_scan_config(raw_code)
        
        # 添加到扫描历史
        timestamp = datetime.now().strftime("%H:%M:%S")
        history_text = f"[{timestamp}] {raw_code} -> {processed_code}\n"
        self.scan_history.append(history_text)
        
        # 查找板件
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, component_name, material, component_code, room_number, cabinet_number
            FROM components 
            WHERE component_code = ? AND status = 'pending'
        ''', (processed_code,))
        component = cursor.fetchone()
        
        if not component:
            # 使用异常处理器处理无效扫描
            ErrorHandler.handle_invalid_scan(processed_code)
            return
        
        component_id = component[0]
        component_room = component[4]
        component_cabinet = component[5]
        
        # 检查是否已经在包装中
        cursor.execute('''
            SELECT p.package_number FROM components c
            JOIN packages p ON c.package_id = p.id
            WHERE c.id = ? AND c.package_id IS NOT NULL
        ''', (component_id,))
        existing = cursor.fetchone()
        
        if existing:
            # 使用异常处理器处理重复扫描
            ErrorHandler.handle_duplicate_scan(processed_code, existing[0])
            return
        
        # 校验当前包装的打包规则（房间/柜号一致性）
        try:
            cursor.execute('SELECT packing_method FROM packages WHERE id = ?', (self.current_package_id,))
            pm_row = cursor.fetchone()
            current_pm = pm_row[0] if pm_row else 'mixed'
            if current_pm == 'by_room':
                cursor.execute('SELECT DISTINCT room_number FROM components WHERE package_id = ?', (self.current_package_id,))
                rooms = [r[0] for r in cursor.fetchall() if r and r[0]]
                if rooms:
                    base_room = rooms[0]
                    if component_room and component_room != base_room:
                        QMessageBox.warning(self, "警告", f"当前包装为按房间分组，房间号不一致：{base_room} vs {component_room}")
                        try:
                            voice_speak("房间号不一致，请检查")
                        except Exception:
                            pass
                        return
            elif current_pm == 'by_cabinet':
                # 同时校验房间号与柜号一致性
                # 先校验房间号一致
                cursor.execute('SELECT DISTINCT room_number FROM components WHERE package_id = ?', (self.current_package_id,))
                rooms = [r[0] for r in cursor.fetchall() if r and r[0]]
                if rooms:
                    base_room = rooms[0]
                    if component_room and component_room != base_room:
                        QMessageBox.warning(self, "警告", f"当前包装为按柜号分组，房间号不一致：{base_room} vs {component_room}")
                        try:
                            voice_speak("房间号不一致，请检查")
                        except Exception:
                            pass
                        return
                # 再校验柜号一致
                cursor.execute('SELECT DISTINCT cabinet_number FROM components WHERE package_id = ?', (self.current_package_id,))
                cabinets = [c[0] for c in cursor.fetchall() if c and c[0]]
                if cabinets:
                    base_cabinet = cabinets[0]
                    if component_cabinet and component_cabinet != base_cabinet:
                        QMessageBox.warning(self, "警告", f"当前包装为按柜号分组，柜号不一致：{base_cabinet} vs {component_cabinet}")
                        try:
                            voice_speak("柜号不一致，请检查")
                        except Exception:
                            pass
                        return
        except Exception:
            # 规则校验出错时，不阻塞；仅继续执行
            pass
        
        # 添加到当前包装
        try:
            # 更新板件状态
            cursor.execute('''
                UPDATE components 
                SET package_id = ?, scanned_at = CURRENT_TIMESTAMP, status = 'packed' 
                WHERE id = ?
            ''', (self.current_package_id, component_id))
            
            conn.commit()
            
            # 记录撤销操作
            undo_manager.add_operation('scan_component', 
                                     {'component_id': component_id},
                                     f"扫描板件: {processed_code}")
            
            # 记录操作日志
            db.log_operation('scan_component', 
                           f"扫描板件 {processed_code} 到包装 {self.current_package_id}")
            
            # 刷新界面
            self.load_current_package_components()
            self.load_active_packages()
            self.update_order_stats()
            
            # 语音提醒：板件加入包装成功
            try:
                voice_speak(f"板件加入包装成功。编码 {processed_code}")
            except Exception:
                pass

            # 发送信号
            self.component_scanned.emit({
                'component_id': component_id,
                'component_code': processed_code,
                'component_name': component[1]
                })
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加板件失败：\n{str(e)}")
        
        conn.close()
    
    def apply_scan_config(self, code):
        """应用扫描配置"""
        try:
            config_str = db.get_setting('scan_config', None)
            if config_str and isinstance(config_str, str):
                import json
                config = json.loads(config_str)
            elif isinstance(config_str, dict):
                config = config_str
            else:
                config = {'process_type': 0}
            
            process_type = config.get('process_type', 0)
        except (json.JSONDecodeError, TypeError):
            # 如果配置解析失败，使用默认配置
            config = {'process_type': 0}
            process_type = 0
        
        if process_type == 0:  # 不处理
            return code
        elif process_type == 1:  # 去掉前缀
            length = config.get('prefix_length', 1)
            return code[length:] if len(code) > length else ""
        elif process_type == 2:  # 去掉后缀
            length = config.get('suffix_length', 1)
            return code[:-length] if len(code) > length else ""
        elif process_type == 3:  # 提取中间
            start = config.get('start_pos', 1) - 1  # 转为0基索引
            length = config.get('extract_length', 5)
            return code[start:start+length] if len(code) > start else ""
        elif process_type == 4:  # 插入字符
            position = config.get('insert_position', 0)
            content = config.get('insert_content', '')
            if position == 0:  # 插入到开头
                return content + code
            elif position >= len(code):  # 插入到末尾
                return code + content
            else:  # 插入到中间
                return code[:position] + content + code[position:]
        elif process_type == 5:  # 组合配置
            result = code
            
            # 执行顺序：去前缀 → 去后缀 → 插入字符 → 提取中间字符
            
            # 1. 去掉前缀
            if config.get('combo_remove_prefix', False):
                length = config.get('combo_prefix_length', 1)
                result = result[length:] if len(result) > length else ""
            
            # 2. 去掉后缀
            if config.get('combo_remove_suffix', False):
                length = config.get('combo_suffix_length', 1)
                result = result[:-length] if len(result) > length else ""
            
            # 3. 插入字符
            if config.get('combo_insert_chars', False):
                position = config.get('combo_insert_position', 0)
                content = config.get('combo_insert_content', '')
                if position == 0:  # 插入到开头
                    result = content + result
                elif position >= len(result):  # 插入到末尾
                    result = result + content
                else:  # 插入到中间
                    result = result[:position] + content + result[position:]
            
            # 4. 提取中间字符
            if config.get('combo_extract_middle', False):
                start = config.get('combo_start_pos', 1) - 1  # 转为0基索引
                length = config.get('combo_extract_length', 5)
                result = result[start:start+length] if len(result) > start else ""
            
            return result
        
        return code
    
    def remove_component_from_package(self, component_id):
        """从包装中移除板件"""
        # 禁止从已封包或已入托包裹移除板件
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT package_id FROM components WHERE id = ?', (component_id,))
            comp = cursor.fetchone()
            pkg_id = comp[0] if comp else None
            status = None
            pallet_id = None
            if pkg_id:
                cursor.execute('SELECT status, pallet_id FROM packages WHERE id = ?', (pkg_id,))
                pkg = cursor.fetchone()
                if pkg:
                    status, pallet_id = pkg[0], pkg[1]
            conn.close()
            if pallet_id is not None or (status and status != 'open'):
                QMessageBox.warning(self, "警告", "包裹已封包或已入托，不能移除板件")
                return
        except Exception:
            pass

        reply = QMessageBox.question(self, "确认", "确定要移除这个板件吗？")
        if reply == QMessageBox.Yes:
            try:
                conn = db.get_connection()
                cursor = conn.cursor()
                
                # 从包装中移除（更新板件状态和包装关联）
                cursor.execute('''
                    UPDATE components SET status = 'pending', package_id = NULL 
                    WHERE id = ?
                ''', (component_id,))
                
                conn.commit()
                conn.close()
                
                # 记录操作日志
                db.log_operation('remove_component', {
                    'package_id': self.current_package_id,
                    'component_id': component_id
                })
                
                # 刷新界面
                self.load_current_package_components()
                self.load_active_packages()
                self.update_order_stats()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"移除板件失败：\n{str(e)}")
    
    def finish_package(self):
        """完成包装"""
        if not self.current_package_id:
            QMessageBox.warning(self, "警告", "请先选择一个包装")
            return
        
        # 检查包装是否有板件
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM components WHERE package_id = ?
        ''', (self.current_package_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            Prompt.show_warning("包装中没有板件，无法完成")
            return
        
        if Prompt.ask_confirm(f"确定要完成当前包装吗？\n包装中共有 {count} 个板件"):
            try:
                # 更新包装状态
                cursor.execute('''
                    UPDATE packages 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (self.current_package_id,))
                
                conn.commit()
                
                # 获取包装号
                cursor.execute('SELECT package_number FROM packages WHERE id = ?', (self.current_package_id,))
                package_number = cursor.fetchone()[0]
                
                conn.close()
                
                # 记录撤销操作
                undo_manager.add_operation('finish_package', 
                                         {'package_id': self.current_package_id},
                                         f"完成包装: {package_number}")
                
                # 记录操作日志
                db.log_operation('finish_package', 
                               f"完成包装 {package_number}，包含 {count} 个板件")
                
                # 发送信号
                self.package_completed.emit(package_number)
                
                # 清空当前选择
                self.current_package_id = None
                self.current_package_status = None
                self.current_package_label.setText("未选择")
                self.current_order_label.setText("-")
                self.current_count_label.setText("0")
                self.finish_package_btn.setEnabled(False)
                self.unpack_btn.setEnabled(False)
                self.delete_package_btn.setEnabled(False)
                self.current_components_table.setRowCount(0)
                
                # 禁用扫描功能（没有选择包装时）
                self.scan_input.setEnabled(False)
                self.manual_scan_btn.setEnabled(False)
                
                # 刷新列表
                self.load_active_packages()
                self.update_order_stats()
                
                Prompt.show_info(f"包装 {package_number} 已完成")
                
            except Exception as e:
                Prompt.show_error(f"完成包装失败：\n{str(e)}")
    
    def unpack_package(self):
        """解包：将已完成的包装重新设置为开放状态"""
        if not self.current_package_id:
            Prompt.show_warning("请先选择一个包装")
            return
        
        # 获取包装信息
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT package_number, status, pallet_id FROM packages WHERE id = ?
        ''', (self.current_package_id,))
        package_info = cursor.fetchone()
        
        if not package_info:
            Prompt.show_warning("包装不存在")
            return
        
        package_number, status, pallet_id = package_info
        
        if pallet_id is not None:
            Prompt.show_warning("已入托的包裹不能解包")
            return
        if status == 'sealed':
            Prompt.show_warning("已封包的包裹不能解包")
            return
        if status != 'completed':
            Prompt.show_warning("只能解包已完成的包装")
            return
        
        if Prompt.ask_confirm(f"确定要解包 {package_number} 吗？\n解包后可以继续添加或移除板件。"):
            try:
                # 更新包装状态为开放
                cursor.execute('''
                    UPDATE packages 
                    SET status = 'open', completed_at = NULL
                    WHERE id = ?
                ''', (self.current_package_id,))
                
                conn.commit()
                conn.close()
                
                # 记录撤销操作
                undo_manager.add_operation('unpack_package', 
                                         {'package_id': self.current_package_id},
                                         f"解包: {package_number}")
                
                # 记录操作日志
                db.log_operation('unpack_package', 
                               f"解包 {package_number}")
                
                # 更新当前包装状态
                self.current_package_status = 'open'
                
                # 重新启用扫描功能
                self.scan_input.setEnabled(True)
                self.manual_scan_btn.setEnabled(True)
                
                # 更新按钮状态
                self.finish_package_btn.setEnabled(True)
                self.unpack_btn.setEnabled(False)
                
                # 刷新板件列表（重新加载移除按钮状态）
                self.load_current_package_components()
                
                # 刷新包装列表
                self.load_active_packages()
                self.update_order_stats()
                
                Prompt.show_info(f"包装 {package_number} 已解包，可以继续编辑")
                
            except Exception as e:
                Prompt.show_error(f"解包失败：\n{str(e)}")
    
    def keyPressEvent(self, event):
        """键盘事件处理（用于扫码枪输入）"""
        # 如果焦点在扫描输入框，让其正常处理
        if self.scan_input.hasFocus():
            super().keyPressEvent(event)
            return
        
        # 处理扫码枪输入
        if event.text().isprintable():
            self.scan_buffer += event.text()
            self.scan_timer.start(100)  # 100ms后处理
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.process_scan_input()
        
        super().keyPressEvent(event)
    
    def process_scan_input(self):
        """处理扫描输入"""
        self.scan_timer.stop()
        if self.scan_buffer:
            self.process_scan_code(self.scan_buffer)
            self.scan_buffer = ""
    
    def show_pending_components(self):
        """显示待包板件列表"""
        # 获取当前选择的订单ID
        current_order_id = getattr(self, 'current_order_id', None)
        dialog = PendingComponentsDialog(self, order_id=current_order_id)
        try:
            dialog.components_deleted.connect(lambda order_id: self.components_deleted_from_pending.emit(order_id))
        except Exception:
            pass
        dialog.exec_()
    
    def select_template_for_package(self):
        """为包装标签选择模板"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QListWidgetItem
        import os
        import json
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择包装标签模板")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 标题
        title_label = QLabel("请选择包装标签模板：")
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

    def print_package_label(self):
        """打印包装标签"""
        if not self.current_package_id:
            QMessageBox.warning(self, "警告", "请先选择要打印标签的包装！")
            return
        
        # 显示模板选择对话框
        template_path = self.select_template_for_package()
        if not template_path:
            return  # 用户取消了模板选择
        
        try:
            # 获取包装信息
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.package_number, p.created_at, p.status, p.packing_method,
                       o.order_number, o.customer_name, o.customer_address,
                       COUNT(c.id) as component_count,
                       pl.pallet_number,
                       p.package_index,
                       pl.pallet_index
                FROM packages p
                LEFT JOIN orders o ON p.order_id = o.id
                LEFT JOIN components c ON c.package_id = p.id
                LEFT JOIN pallets pl ON p.pallet_id = pl.id
                WHERE p.id = ?
                GROUP BY p.id
            ''', (self.current_package_id,))
            package_info = cursor.fetchone()
            
            if not package_info:
                QMessageBox.warning(self, "错误", "未找到包装信息！")
                return
            
            # 获取包装中的板件信息
            cursor.execute('''
                SELECT component_name, material, finished_size, component_code, room_number, cabinet_number
                FROM components
                WHERE package_id = ?
                ORDER BY created_at
            ''', (self.current_package_id,))
            components = cursor.fetchall()
            conn.close()
            
            # 聚合房间号与柜号
            rooms = []
            cabinets = []
            for comp in components:
                if len(comp) > 4 and comp[4]:
                    rooms.append(str(comp[4]))
                if len(comp) > 5 and comp[5]:
                    cabinets.append(str(comp[5]))
            unique_rooms = sorted(set([r for r in rooms if r.strip()]))
            unique_cabinets = sorted(set([c for c in cabinets if c.strip()]))
            room_display = unique_rooms[0] if len(unique_rooms) == 1 else '、'.join(unique_rooms)
            cabinet_display = unique_cabinets[0] if len(unique_cabinets) == 1 else '、'.join(unique_cabinets)

            # 打包方式显示
            method_display_map = {
                'by_room': '按房间分组',
                'by_cabinet': '按柜号分组',
                'mixed': '混合打包',
                'manual': '手动打包',
                'scan': '扫码打包'
            }
            method_display = method_display_map.get(package_info[3] or '', '')

            # 统计该订单下包裹与托盘总数（进度视图：第N/共M）
            package_total_in_order = 0
            pallet_total_in_order = 0
            try:
                conn2 = db.get_connection()
                cur2 = conn2.cursor()
                # 订单ID需要从当前包裹查询
                cur2.execute('SELECT order_id FROM packages WHERE id = ?', (self.current_package_id,))
                row = cur2.fetchone()
                current_order_id = row[0] if row else None
                if current_order_id:
                    cur2.execute('SELECT COUNT(*) FROM packages WHERE order_id = ?', (current_order_id,))
                    package_total_in_order = cur2.fetchone()[0]
                    cur2.execute('SELECT COUNT(*) FROM pallets WHERE order_id = ?', (current_order_id,))
                    pallet_total_in_order = cur2.fetchone()[0]
                conn2.close()
            except Exception:
                pass

            # 准备标签数据
            label_data = {
                'package_number': package_info[0],
                'packing_method': method_display,
                'create_time': package_info[1],
                'status': package_info[2],
                'order_number': package_info[4] or '',
                'customer_name': package_info[5] or '',
                'customer_address': package_info[6] or '',
                'component_count': package_info[7],
                'pallet_number': package_info[8] or '未分配',
                'components': components,
                'room_number': room_display,
                'cabinet_number': cabinet_display,
                # 序号：使用数据库存储的稳定序号
                'package_index': package_info[9],
                'pallet_index': package_info[10],
                # 进度视图
                'package_total_in_order': package_total_in_order,
                'pallet_total_in_order': pallet_total_in_order,
                # 打印审计
                'printed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                # 包裹扩展字段：是否手动、打包方式原值
                'is_manual': None,
                'packing_method_raw': package_info[3] or ''
            }

            # 查询是否手动创建
            try:
                conn3 = db.get_connection()
                cur3 = conn3.cursor()
                cur3.execute('SELECT is_manual FROM packages WHERE id = ?', (self.current_package_id,))
                r = cur3.fetchone()
                if r is not None:
                    label_data['is_manual'] = r[0]
                conn3.close()
            except Exception:
                pass
            
            # 直接打印标签
            self.print_label_directly(label_data, template_path)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打印标签时发生错误：{str(e)}")
    
    def print_label_directly(self, label_data, template_path=None):
        """直接打印标签，不打开设计界面"""
        try:
            from label_printing import LabelPrinting
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt5.QtGui import QPainter
            
            # 创建标签打印组件（不显示界面）
            label_printing = LabelPrinting()
            
            # 如果提供了模板路径，先加载模板
            if template_path:
                label_printing.load_template(template_path)
            
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
                dialog.setWindowTitle("热敏包装标签打印")
                
                if dialog.exec_() != QPrintDialog.Accepted:
                    return
            
            # 开始打印（统一调用标签模块渲染，避免重复旋转与缩放）
            label_printing.render_to_printer(printer)
            
            # 保存打印日志
            if db.get_setting('save_print_log', 'true') == 'true':
                label_printing.save_print_log()
            
            QMessageBox.information(self, "成功", "热敏包装标签打印完成！")
            
        except ImportError:
            QMessageBox.warning(self, "错误", "无法加载标签打印模块！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"直接打印标签时发生错误：{str(e)}")
    
    def open_label_printing_with_data(self, label_data):
        """打开标签打印页面并传入数据"""
        try:
            # 导入标签打印模块
            from label_printing import LabelPrinting
            
            # 创建标签打印对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("打印包装标签")
            dialog.resize(1200, 800)
            
            layout = QVBoxLayout(dialog)
            
            # 创建标签打印组件
            label_printing = LabelPrinting()
            layout.addWidget(label_printing)
            
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
        """将包装数据设置到标签画布"""
        try:
            # 生成包装列表字符串：板件编号+名称+尺寸
            components = label_data.get('components', [])
            component_list_items = []
            for comp in components:
                # comp结构: (component_name, material, finished_size, component_code)
                component_code = comp[3] if len(comp) > 3 else ''
                component_name = comp[0] if len(comp) > 0 else ''
                finished_size = comp[2] if len(comp) > 2 else ''
                
                # 格式化为：编号+名称+尺寸
                item_text = f"{component_code}+{component_name}+{finished_size}"
                component_list_items.append(item_text)
            
            package_component_list = '\n'.join(component_list_items)
            
            # 计算包裹序号与显示文本（第N包）
            def extract_index(num_str):
                try:
                    import re
                    m = re.search(r"(\d+)", str(num_str or ''))
                    return int(m.group(1)) if m else None
                except Exception:
                    return None

            package_number = label_data.get('package_number', '')
            pallet_number = label_data.get('pallet_number', '')
            # 优先使用存储的稳定序号
            package_index = label_data.get('package_index')
            if package_index is None:
                package_index = extract_index(package_number)
            pallet_index = label_data.get('pallet_index')
            if pallet_index is None:
                pallet_index = extract_index(pallet_number)
            package_index_display = f"第{package_index}包" if package_index is not None else ''

            # 更新标签打印模块的示例数据
            sample_data = {
                'order_number': label_data.get('order_number', ''),
                'component_name': ', '.join([comp[0] for comp in label_data.get('components', [])[:3]]),  # 显示前3个板件名称
                'customer_name': label_data.get('customer_name', ''),
                'customer_address': label_data.get('customer_address', ''),
                'create_time': label_data.get('create_time', ''),
                'package_number': package_number,
                'pallet_number': pallet_number,
                'packing_method': label_data.get('packing_method', ''),
                'packing_method_raw': label_data.get('packing_method_raw', ''),
                'component_count': str(label_data.get('component_count', 0)),
                'status': label_data.get('status', ''),
                'package_component_list': package_component_list,
                # 房间号/柜号聚合显示
                'room_number': label_data.get('room_number', ''),
                'cabinet_number': label_data.get('cabinet_number', ''),
                # 新增：包裹/托盘序号相关字段
                'package_index': str(package_index) if package_index is not None else '',
                'package_index_display': package_index_display,
                'pallet_index': str(pallet_index) if pallet_index is not None else '',
                # 进度视图
                'package_total_in_order': str(label_data.get('package_total_in_order', '')),
                'pallet_total_in_order': str(label_data.get('pallet_total_in_order', '')),
                # 审计
                'printed_at': label_data.get('printed_at', ''),
                # 扩展
                'is_manual': str(label_data.get('is_manual', ''))
            }
            
            # 更新画布的示例数据
            if hasattr(label_printing.canvas, 'sample_data'):
                label_printing.canvas.sample_data.update(sample_data)
            
        except Exception as e:
            print(f"设置标签数据时发生错误: {e}")


class PendingComponentsDialog(QDialog):
    """待包板件对话框"""
    components_deleted = pyqtSignal(int)
    
    def __init__(self, parent=None, order_id=None):
        super().__init__(parent)
        self.order_id = order_id
        self.setWindowTitle("待包板件列表")
        self.setGeometry(200, 200, 1000, 600)
        self.init_ui()
        self.load_pending_components()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        
        self.total_label = QLabel("总计: 0 个板件")
        stats_layout.addWidget(self.total_label)
        
        self.filtered_label = QLabel("")
        stats_layout.addWidget(self.filtered_label)
        
        stats_layout.addStretch()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_pending_components)
        stats_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(stats_layout)
        
        # 筛选输入框
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        
        self.filter_inputs = []
        filter_labels = ['板件名', '材质', '成品尺寸', '板件编码', '房间号', '柜号', '订单号', '扫描时间']
        
        for i, label in enumerate(filter_labels):
            filter_input = QLineEdit()
            filter_input.setPlaceholderText(f"筛选{label}")
            filter_input.setMaximumWidth(100)
            filter_input.textChanged.connect(self.apply_filters)
            self.filter_inputs.append(filter_input)
            filter_layout.addWidget(filter_input)
        
        clear_filter_btn = QPushButton("清除筛选")
        clear_filter_btn.clicked.connect(self.clear_filters)
        filter_layout.addWidget(clear_filter_btn)
        
        layout.addLayout(filter_layout)
        
        # 待包板件表格
        self.components_table = QTableWidget()
        self.components_table.setColumnCount(8)
        self.components_table.setHorizontalHeaderLabels([
            '板件名', '材质', '成品尺寸', '板件编码', '房间号', '柜号', '订单号', '扫描时间'
        ])
        
        # 设置列宽
        self.components_table.setColumnWidth(0, 120)  # 板件名
        self.components_table.setColumnWidth(1, 80)   # 材质
        self.components_table.setColumnWidth(2, 120)  # 成品尺寸
        self.components_table.setColumnWidth(3, 150)  # 板件编码
        self.components_table.setColumnWidth(4, 80)   # 房间号
        self.components_table.setColumnWidth(5, 80)   # 柜号
        self.components_table.setColumnWidth(6, 120)  # 订单号
        self.components_table.setColumnWidth(7, 140)  # 扫描时间
        
        # 启用多选模式
        self.components_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.components_table.setSelectionMode(QTableWidget.MultiSelection)
        
        self.components_table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.components_table)
        
        # 存储原始数据用于筛选
        self.original_data = []
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("取消全选")
        self.select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(self.select_none_btn)
        
        button_layout.addStretch()
        
        self.one_click_pack_btn = QPushButton("一键打包选中项")
        self.one_click_pack_btn.clicked.connect(self.one_click_pack)
        self.one_click_pack_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        button_layout.addWidget(self.one_click_pack_btn)

        # 新增：删除选中板件（仅删除未入包/未入托的pending状态板件）
        self.delete_btn = QPushButton("删除选中板件")
        self.delete_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; font-weight: bold; }")
        self.delete_btn.clicked.connect(self.delete_selected_components)
        button_layout.addWidget(self.delete_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def load_pending_components(self):
        """加载待包板件"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if self.order_id:
            # 只显示指定订单的待包板件，同时获取component_id用于打包
            cursor.execute('''
                SELECT c.id, c.component_name, c.material, c.finished_size, c.component_code,
                       c.room_number, c.cabinet_number, o.order_number, c.created_at
                FROM components c
                LEFT JOIN orders o ON c.order_id = o.id
                WHERE c.package_id IS NULL AND c.order_id = ?
                ORDER BY c.created_at DESC
            ''', (self.order_id,))
        else:
            # 显示所有待包板件，同时获取component_id用于打包
            cursor.execute('''
                SELECT c.id, c.component_name, c.material, c.finished_size, c.component_code,
                       c.room_number, c.cabinet_number, o.order_number, c.created_at
                FROM components c
                LEFT JOIN orders o ON c.order_id = o.id
                WHERE c.package_id IS NULL
                ORDER BY c.created_at DESC
            ''')
        components = cursor.fetchall()
        conn.close()
        
        # 存储原始数据（包含ID）
        self.original_data = components
        
        # 显示数据（不包含ID列）
        display_data = [component[1:] for component in components]  # 跳过第一列ID
        
        # 更新统计标签
        self.total_label.setText(f"总计: {len(display_data)} 个板件")
        self.filtered_label.setText("")
        
        self.populate_table(display_data)
    
    def populate_table(self, data):
        """填充表格数据"""
        self.components_table.setRowCount(len(data))
        for i, component in enumerate(data):
            for j, value in enumerate(component):
                item_text = str(value) if value else ''
                item = QTableWidgetItem(item_text)
                self.components_table.setItem(i, j, item)
    
    def apply_filters(self):
        """应用筛选"""
        if not self.original_data:
            return
        
        # 获取筛选条件
        filters = [input_field.text().lower().strip() for input_field in self.filter_inputs]
        
        # 筛选数据
        filtered_data = []
        for component in self.original_data:
            # 检查每列是否匹配筛选条件（跳过ID列）
            display_component = component[1:]  # 跳过ID列
            match = True
            for i, filter_text in enumerate(filters):
                if filter_text and filter_text not in str(display_component[i]).lower():
                    match = False
                    break
            
            if match:
                filtered_data.append(display_component)
        
        # 更新表格
        self.populate_table(filtered_data)
        
        # 更新统计信息
        if any(filters):
            self.filtered_label.setText(f"筛选结果: {len(filtered_data)} 个板件")
        else:
            self.filtered_label.setText("")
    
    def clear_filters(self):
        """清除所有筛选"""
        for input_field in self.filter_inputs:
            input_field.clear()
        
        # 重新显示所有数据
        if self.original_data:
            display_data = [component[1:] for component in self.original_data]
            self.populate_table(display_data)
        
        self.filtered_label.setText("")
    
    def select_all(self):
        """全选"""
        self.components_table.selectAll()
    
    def select_none(self):
        """取消全选"""
        self.components_table.clearSelection()
    
    def get_selected_component_ids(self):
        """获取选中的板件ID"""
        selected_rows = set()
        for item in self.components_table.selectedItems():
            selected_rows.add(item.row())
        
        # 获取当前显示的数据对应的原始数据索引
        current_display_data = []
        for row in range(self.components_table.rowCount()):
            row_data = []
            for col in range(self.components_table.columnCount()):
                item = self.components_table.item(row, col)
                row_data.append(item.text() if item else '')
            current_display_data.append(row_data)
        
        # 找到选中行对应的原始数据ID
        selected_ids = []
        for row in selected_rows:
            if row < len(current_display_data):
                # 在原始数据中查找匹配的行
                display_row = current_display_data[row]
                for original_component in self.original_data:
                    original_display = original_component[1:]  # 跳过ID列
                    if list(original_display) == display_row:
                        selected_ids.append(original_component[0])  # 添加ID
                        break
        
        return selected_ids
    
    def one_click_pack(self):
        """一键打包选中的板件"""
        selected_ids = self.get_selected_component_ids()
        
        if not selected_ids:
            QMessageBox.warning(self, "警告", "请先选择要打包的板件")
            return
        
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 生成新的包裹号
            package_number = db.generate_package_number()
            
            # 获取第一个板件的订单ID（假设同一批打包的板件属于同一订单）
            cursor.execute('SELECT order_id FROM components WHERE id = ?', (selected_ids[0],))
            order_result = cursor.fetchone()
            order_id = order_result[0] if order_result else None
            
            # 计算包裹序号（按订单内补位规则）
            try:
                next_index = db.get_next_package_index(order_id)
            except Exception:
                next_index = None
            
            # 创建新包裹（打包方式统一为“mixed”），使用数据库时间戳
            cursor.execute('''
                INSERT INTO packages (package_number, order_id, package_index, packing_method, status, created_at, is_manual)
                VALUES (?, ?, ?, ?, 'open', CURRENT_TIMESTAMP, ?)
            ''', (package_number, order_id, next_index, 'mixed', 1))
            
            package_id = cursor.lastrowid
            
            # 将选中的板件添加到包裹中
            for component_id in selected_ids:
                cursor.execute('''
                    UPDATE components 
                    SET package_id = ?, scanned_at = ?
                    WHERE id = ? AND package_id IS NULL
                ''', (package_id, datetime.now(), component_id))
            
            # 更新包裹的板件数量统计字段
            cursor.execute('''
                UPDATE packages SET component_count = (
                    SELECT COUNT(*) FROM components WHERE package_id = ?
                ) WHERE id = ?
            ''', (package_id, package_id))
            
            conn.commit()
            
            # 记录操作日志
            db.log_operation('one_click_pack', 
                           f"一键打包创建包裹 {package_number}，包含 {len(selected_ids)} 个板件")
            
            # 添加撤销操作
            undo_manager.add_operation('one_click_pack', 
                                     {'package_id': package_id, 'component_ids': selected_ids},
                                     f"一键打包: {package_number}")
            
            conn.close()
            
            QMessageBox.information(self, "成功", 
                                  f"成功创建包裹 {package_number}\n已打包 {len(selected_ids)} 个板件")
            
            # 刷新数据
            self.load_pending_components()
            
            # 通知父窗口刷新
            if hasattr(self.parent(), 'load_active_packages'):
                self.parent().load_active_packages()
                try:
                    if hasattr(self.parent(), 'update_order_stats'):
                        self.parent().update_order_stats()
                except Exception:
                    pass
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"一键打包失败：\n{str(e)}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

    def delete_selected_components(self):
        """删除选中的待包板件（仅允许pending且未入包/未入托）"""
        selected_ids = self.get_selected_component_ids()
        if not selected_ids:
            Prompt.show_warning("请先选择要删除的板件")
            return
        if not Prompt.ask_confirm(f"确定要删除选中的 {len(selected_ids)} 个板件吗？", title="确认删除"):
            return
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            # 只删除未入包的板件（package_id IS NULL）
            placeholders = ','.join(['?'] * len(selected_ids))
            cursor.execute(f'''DELETE FROM components WHERE id IN ({placeholders}) AND package_id IS NULL''', selected_ids)
            deleted_count = cursor.rowcount if hasattr(cursor, 'rowcount') else None
            conn.commit()
            conn.close()

            Prompt.show_info(f"已删除 {deleted_count or len(selected_ids)} 个板件")
            # 刷新当前列表
            self.load_pending_components()
            # 发出删除信号用于联动订单管理页刷新
            try:
                if self.order_id:
                    self.components_deleted.emit(self.order_id)
            except Exception:
                pass
        except Exception as e:
            Prompt.show_error(f"删除板件失败：\n{str(e)}")
