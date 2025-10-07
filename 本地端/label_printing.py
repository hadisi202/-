import sys
import json
import os
import math
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QTableWidget, QTableWidgetItem, QLabel,
                             QLineEdit, QTextEdit, QComboBox, QMessageBox,
                             QDialog, QDialogButtonBox, QGroupBox, QCheckBox,
                             QSplitter, QHeaderView, QTabWidget, QSpinBox,
                             QButtonGroup, QRadioButton, QFrame, QListWidget,
                             QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QScrollArea, QSlider, QColorDialog, QFontDialog,
                             QGraphicsView, QGraphicsScene, QGraphicsTextItem,
                             QGraphicsRectItem, QGraphicsPixmapItem, QFileDialog,
                             QInputDialog, QToolBar, QAction, QApplication,
                             QGraphicsItem, QGraphicsProxyWidget, QStyleOptionGraphicsItem)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSizeF, QMimeData
from PyQt5.QtGui import (QFont, QColor, QPixmap, QPainter, QPen, QBrush, 
                         QDrag, QIcon, QFontMetrics, QPainterPath, QTransform,
                         QKeySequence)
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
import qrcode
from PIL import Image, ImageDraw, ImageFont
from database import db

class DraggableGraphicsItem(QGraphicsRectItem):
    """可拖拽的图形项基类"""
    
    def __init__(self, x, y, width, height, element_type="base"):
        # 统一坐标系：局部矩形始终为 (0,0,width,height)，位置用 setPos(x,y)
        super().__init__(0, 0, width, height)
        self.setPos(x, y)
        self.element_type = element_type
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # 调整大小的控制点
        self.resize_handles = []
        self.create_resize_handles()
        
        # 元素属性
        self.properties = {
            'font_family': 'Arial',
            'font_size': 12,
            'font_bold': False,
            'font_italic': False,
            'color': '#000000',
            'background_color': '#FFFFFF',
            'border': True,
            'border_width': 1,
            'border_color': '#000000',
            'alignment': 'left',
            'padding': 0,
            'text': '',
            'data_field': None
        }
    
    def create_resize_handles(self):
        """创建调整大小的控制点"""
        handle_size = 8
        positions = [
            (0, 0), (0.5, 0), (1, 0),
            (0, 0.5), (1, 0.5),
            (0, 1), (0.5, 1), (1, 1)
        ]
        
        for i, (x_ratio, y_ratio) in enumerate(positions):
            handle = ResizeHandle(self, i, handle_size)
            handle.setParentItem(self)
            self.resize_handles.append(handle)
            self.update_handle_position(handle, x_ratio, y_ratio)
    
    def update_handle_position(self, handle, x_ratio, y_ratio):
        """更新控制点位置"""
        rect = self.rect()
        # 局部坐标原点固定在 (0,0)，控制点相对宽高定位
        x = rect.width() * x_ratio - handle.rect().width() / 2
        y = rect.height() * y_ratio - handle.rect().height() / 2
        handle.setPos(x, y)
    
    def update_handles(self):
        """更新所有控制点位置"""
        positions = [
            (0, 0), (0.5, 0), (1, 0),
            (0, 0.5), (1, 0.5),
            (0, 1), (0.5, 1), (1, 1)
        ]
        
        for handle, (x_ratio, y_ratio) in zip(self.resize_handles, positions):
            self.update_handle_position(handle, x_ratio, y_ratio)
    
    def itemChange(self, change, value):
        """项目变化时的回调"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.update_handles()
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            # 显示或隐藏调整大小的控制点
            for handle in self.resize_handles:
                handle.setVisible(self.isSelected())
        
        return super().itemChange(change, value)
    
    def resize_to(self, new_rect):
        """调整大小"""
        # new_rect 为场景坐标系中的矩形，拆分为位置与尺寸
        self.setPos(new_rect.x(), new_rect.y())
        self.setRect(QRectF(0, 0, new_rect.width(), new_rect.height()))
        self.update_handles()
    
    def get_properties(self):
        """获取属性"""
        props = self.properties.copy()
        rect = self.rect()
        pos = self.pos()
        props.update({
            'type': self.element_type,  # 保存元素类型
            'x': pos.x(),
            'y': pos.y(),
            'width': rect.width(),
            'height': rect.height()
        })
        return props
    
    def set_properties(self, props):
        """设置属性"""
        self.properties.update(props)
        
        # 更新位置和大小（保持局部矩形原点为 0,0）
        if 'x' in props and 'y' in props:
            self.setPos(props['x'], props['y'])
        if 'width' in props and 'height' in props:
            self.setRect(QRectF(0, 0, props['width'], props['height']))
        
        self.update()
    
    def render_combination_text(self, config):
        """渲染组合字段文本"""
        template = config.get('template', '')
        if not template:
            return "无模板"

        # 优先从画布读取外部数据源
        canvas = getattr(self, 'canvas', None)
        data_source = {}
        if canvas is not None and hasattr(canvas, 'sample_data'):
            data_source = canvas.sample_data or {}

        # 解析字段并替换
        import re
        fields = config.get('fields') or list(set(re.findall(r'\{(\w+)\}', template)))
        result = template
        for field_key in fields:
            value = data_source.get(field_key, '')
            result = result.replace(f"{{{field_key}}}", str(value))

        return result

class ResizeHandle(QGraphicsRectItem):
    """调整大小的控制点"""
    
    def __init__(self, parent_item, handle_index, size):
        super().__init__(0, 0, size, size)
        self.parent_item = parent_item
        self.handle_index = handle_index
        self.setBrush(QBrush(QColor(0, 120, 215)))
        self.setPen(QPen(QColor(255, 255, 255), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setVisible(False)
        self.setCursor(Qt.SizeFDiagCursor)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self.start_pos = event.pos()
        self.start_rect = self.parent_item.rect()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if hasattr(self, 'start_pos'):
            delta = event.pos() - self.start_pos
            new_rect = self.calculate_new_rect(delta)
            self.parent_item.resize_to(new_rect)
    
    def calculate_new_rect(self, delta):
        """计算新的矩形"""
        rect = self.start_rect
        parent_pos = self.parent_item.pos()
        
        # 根据控制点位置调整矩形
        if self.handle_index == 0:  # 左上
            return QRectF(parent_pos.x() + delta.x(), parent_pos.y() + delta.y(),
                          rect.width() - delta.x(), rect.height() - delta.y())
        elif self.handle_index == 1:  # 上中
            return QRectF(parent_pos.x(), parent_pos.y() + delta.y(),
                          rect.width(), rect.height() - delta.y())
        elif self.handle_index == 2:  # 右上
            return QRectF(parent_pos.x(), parent_pos.y() + delta.y(),
                          rect.width() + delta.x(), rect.height() - delta.y())
        elif self.handle_index == 3:  # 左中
            return QRectF(parent_pos.x() + delta.x(), parent_pos.y(),
                          rect.width() - delta.x(), rect.height())
        elif self.handle_index == 4:  # 右中
            return QRectF(parent_pos.x(), parent_pos.y(),
                          rect.width() + delta.x(), rect.height())
        elif self.handle_index == 5:  # 左下
            return QRectF(parent_pos.x() + delta.x(), parent_pos.y(),
                          rect.width() - delta.x(), rect.height() + delta.y())
        elif self.handle_index == 6:  # 下中
            return QRectF(parent_pos.x(), parent_pos.y(),
                          rect.width(), rect.height() + delta.y())
        elif self.handle_index == 7:  # 右下
            return QRectF(parent_pos.x(), parent_pos.y(),
                          rect.width() + delta.x(), rect.height() + delta.y())
        
        return rect

class TextGraphicsItem(DraggableGraphicsItem):
    """文本图形项"""
    
    def __init__(self, x, y, width, height, text="文本"):
        super().__init__(x, y, width, height, "text")
        self.properties['text'] = text
        self.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.setPen(QPen(QColor(200, 200, 200), 1, Qt.DashLine))
    
    def paint(self, painter, option, widget):
        """绘制文本"""
        # 绘制背景和边框
        super().paint(painter, option, widget)
        
        # 设置字体
        font = QFont(self.properties['font_family'], self.properties['font_size'])
        font.setBold(self.properties['font_bold'])
        font.setItalic(self.properties['font_italic'])
        painter.setFont(font)
        
        # 设置颜色
        painter.setPen(QPen(QColor(self.properties['color'])))
        
        # 绘制文本（自动换行）
        rect = self.rect()
        text = self.properties['text']
        if self.properties['data_field']:
            if self.properties['data_field'] == 'custom_combination':
                # 组合字段显示
                config = self.properties.get('combination_config', {})
                if config:
                    text = self.render_combination_text(config)
                else:
                    text = "未配置组合字段"
            else:
                # 单字段显示
                text = f"{{{self.properties['data_field']}}}"

        # 对齐方式
        alignment = Qt.AlignLeft
        if self.properties['alignment'] == 'center':
            alignment = Qt.AlignHCenter
        elif self.properties['alignment'] == 'right':
            alignment = Qt.AlignRight

        # 自动换行：按照文本框宽度将文本拆分为多行
        try:
            from PyQt5.QtGui import QFontMetrics
            metrics = QFontMetrics(font)
            line_height = max(10, int(metrics.lineSpacing()))
            padding = int(self.properties.get('padding', 0))
            avail_w = max(1, int(rect.width()) - 2 * padding)
            avail_h = max(1, int(rect.height()) - 2 * padding)

            def text_width(s):
                try:
                    return metrics.horizontalAdvance(s)
                except Exception:
                    return metrics.width(s)

            import re
            lines_out = []
            for raw in str(text).split('\n'):
                if not raw:
                    continue
                buf = ''
                tokens = re.split(r'(\s+|\+)', raw)
                for tk in tokens:
                    if tk == '':
                        continue
                    candidate = buf + tk
                    if text_width(candidate) <= avail_w:
                        buf = candidate
                    else:
                        # token 本身过宽则逐字符拆分
                        if text_width(tk) > avail_w:
                            for ch in tk:
                                cand2 = buf + ch
                                if text_width(cand2) <= avail_w:
                                    buf = cand2
                                else:
                                    if buf.strip():
                                        lines_out.append(buf)
                                    buf = ch
                            continue
                        if buf.strip():
                            lines_out.append(buf)
                        buf = tk
                if buf.strip():
                    lines_out.append(buf)

            # 垂直方向从顶部开始绘制，超出高度的内容不绘制
            max_lines = max(1, avail_h // line_height)
            x = rect.left() + padding
            y = rect.top() + padding
            for i, line in enumerate(lines_out[:max_lines]):
                # 按对齐调整起始x：左/中/右
                if alignment == Qt.AlignHCenter:
                    lw = text_width(line)
                    sx = x + max(0, (avail_w - lw) // 2)
                elif alignment == Qt.AlignRight:
                    lw = text_width(line)
                    sx = x + max(0, (avail_w - lw))
                else:
                    sx = x
                painter.drawText(int(sx), int(y + i * line_height + metrics.ascent()), line)
        except Exception:
            # 失败则回退为原始绘制
            painter.drawText(rect, alignment | Qt.AlignVCenter, text)

class QRCodeGraphicsItem(DraggableGraphicsItem):
    """二维码图形项"""
    
    def __init__(self, x, y, size=80, data=""):
        super().__init__(x, y, size, size, "qrcode")
        self.properties['data'] = data
        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(0, 0, 0), 1))
    
    def paint(self, painter, option, widget):
        """绘制二维码"""
        # 绘制背景
        super().paint(painter, option, widget)
        
        # 生成二维码
        data = self.properties.get('data', '')
        data_field = self.properties.get('data_field')
        if data_field:
            if data_field == 'custom_combination':
                # 组合字段显示
                config = self.properties.get('combination_config', {})
                if config:
                    data = self.render_combination_text(config)
                else:
                    data = ""
            else:
                # 单字段显示：从画布的 sample_data 提取绑定值
                canvas = getattr(self, 'canvas', None)
                data_source = getattr(canvas, 'sample_data', {}) if canvas else {}
                data = str(data_source.get(data_field, ''))
        
        if data:
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=1)
                qr.add_data(data)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # 转换为QPixmap
                qr_img = qr_img.resize((int(self.rect().width()), int(self.rect().height())))
                qr_img.save("temp_qr.png")
                pixmap = QPixmap("temp_qr.png")
                
                # 绘制二维码
                painter.drawPixmap(self.rect().toRect(), pixmap)
                
                # 清理临时文件
                if os.path.exists("temp_qr.png"):
                    os.remove("temp_qr.png")
            except Exception as e:
                # 如果生成失败，绘制占位符
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(self.rect(), Qt.AlignCenter, "二维码")

class RectangleGraphicsItem(DraggableGraphicsItem):
    """矩形图形项"""
    
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height, "rectangle")
        self.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.setPen(QPen(QColor(0, 0, 0), 1))
    
    def paint(self, painter, option, widget):
        """绘制矩形"""
        # 设置画笔和画刷
        pen = QPen(QColor(self.properties['border_color']), self.properties['border_width'])
        brush = QBrush(QColor(self.properties['background_color']))
        
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRect(self.rect())

class LineGraphicsItem(DraggableGraphicsItem):
    """线条图形项"""
    
    def __init__(self, x, y, width, height=2):
        super().__init__(x, y, width, height, "line")
        self.setPen(QPen(QColor(0, 0, 0), 1))
    
    def paint(self, painter, option, widget):
        """绘制线条"""
        pen = QPen(QColor(self.properties['border_color']), self.properties['border_width'])
        painter.setPen(pen)
        
        rect = self.rect()
        painter.drawLine(rect.topLeft(), rect.topRight())

class LabelCanvas(QGraphicsView):
    """标签画布"""
    
    item_selected = pyqtSignal(object)  # 元素选择信号
    
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        # 外部业务可注入的数据源，用于模板字段渲染
        self.sample_data = {}
        
        # 设置画布属性
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        
        # 设置画布大小（标签纸大小）- 默认100×70mm快递标签纸（更贴近常见宽版）
        # 100mm ≈ 800px, 70mm ≈ 560px（按 ~8px/mm 近似，适配热敏）
        self.label_width = 800  # 100mm
        self.label_height = 560  # 70mm
        self.scene.setSceneRect(0, 0, self.label_width, self.label_height)
        
        # 绘制网格
        self.draw_grid()
        
        # 连接选择信号
        self.scene.selectionChanged.connect(self.on_selection_changed)
    
    def draw_grid(self):
        """绘制网格"""
        pen = QPen(QColor(200, 200, 200), 0.5, Qt.DotLine)
        
        # 垂直线
        for x in range(0, int(self.label_width) + 1, 10):
            self.scene.addLine(x, 0, x, self.label_height, pen)
        
        # 水平线
        for y in range(0, int(self.label_height) + 1, 10):
            self.scene.addLine(0, y, self.label_width, y, pen)
        
        # 边框
        border_pen = QPen(QColor(0, 0, 0), 2)
        self.scene.addRect(0, 0, self.label_width, self.label_height, border_pen)
    
    def add_text_element(self, x=50, y=50):
        """添加文本元素"""
        item = TextGraphicsItem(x, y, 100, 30, "文本")
        # 让元素可访问画布，以便渲染时读取 sample_data
        item.canvas = self
        self.scene.addItem(item)
        return item
    
    def add_qrcode_element(self, x=50, y=50):
        """添加二维码元素"""
        item = QRCodeGraphicsItem(x, y, 80, "示例数据")
        item.canvas = self
        self.scene.addItem(item)
        return item
    
    def add_rectangle_element(self, x=50, y=50):
        """添加矩形元素"""
        item = RectangleGraphicsItem(x, y, 100, 60)
        item.canvas = self
        self.scene.addItem(item)
        return item
    
    def add_line_element(self, x=50, y=50):
        """添加线条元素"""
        item = LineGraphicsItem(x, y, 150, 2)
        item.canvas = self
        self.scene.addItem(item)
        return item
    
    def on_selection_changed(self):
        """选择变化时的处理"""
        selected_items = self.scene.selectedItems()
        if selected_items:
            # 只处理第一个选中的项
            item = selected_items[0]
            if isinstance(item, DraggableGraphicsItem):
                self.item_selected.emit(item)
        else:
            self.item_selected.emit(None)
    
    def delete_selected(self):
        """删除选中的元素"""
        selected_items = self.scene.selectedItems()
        for item in selected_items:
            if isinstance(item, DraggableGraphicsItem):
                self.scene.removeItem(item)
    
    def clear_canvas(self):
        """清空画布"""
        # 只删除元素，保留网格
        items_to_remove = []
        for item in self.scene.items():
            if isinstance(item, DraggableGraphicsItem):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.scene.removeItem(item)
    
    def get_all_elements(self):
        """获取所有元素"""
        elements = []
        for item in self.scene.items():
            if isinstance(item, DraggableGraphicsItem):
                elements.append(item)
        return elements
    
    def update_canvas_size(self):
        """更新画布尺寸"""
        # 清除现有的网格和边框
        items_to_remove = []
        for item in self.scene.items():
            if not isinstance(item, DraggableGraphicsItem):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.scene.removeItem(item)
        
        # 更新场景矩形
        self.scene.setSceneRect(0, 0, self.label_width, self.label_height)
        
        # 重新绘制网格
        self.draw_grid()

class CombinationFieldDialog(QDialog):
    """组合字段配置对话框"""
    
    def __init__(self, config=None, parent=None, sample_data=None):
        super().__init__(parent)
        self.config = config or {}
        # 用于预览的外部示例数据
        self.sample_data = sample_data or {}
        self.setWindowTitle("配置组合字段")
        self.setModal(True)
        self.resize(600, 500)
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 说明文本
        info_label = QLabel("组合字段允许您将多个数据字段组合成一个显示内容。\n"
                           "使用 {字段名} 的格式在模板中引用字段。")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # 可用字段列表
        fields_group = QGroupBox("可用字段")
        fields_layout = QVBoxLayout(fields_group)
        
        self.fields_list = QListWidget()
        # 字段显示名映射（与 get_field_display_name 保持一致）
        label_map = {
            'order_number': '订单号',
            'component_name': '板件名',
            'material': '材质',
            'finished_size': '成品尺寸',
            'component_code': '板件编码',
            'room_number': '房间号',
            'cabinet_number': '柜号',
            'package_number': '包装号',
            'package_component_list': '包装板件列表',
            'package_list': '包裹列表',
            'total_packages': '总包装数',
            'pallet_number': '托盘号',
            'total_pallets': '总托盘数',
            'customer_name': '客户名称',
            'customer_address': '客户地址',
            'create_time': '创建时间',
            'component_count': '板件数量',
            'package_count': '托盘内总包裹数',
            'status': '状态',
            'package_index': '包裹序号',
            'package_index_display': '第N包',
            'pallet_index': '托盘序号'
        }

        # 显示完整字段列表（不再按 sample_data 过滤）
        preferred_order = [
            'order_number','customer_name','customer_address','create_time',
            'package_number','package_index','package_index_display','pallet_number','pallet_index',
            'component_count','package_count','packing_method','status','package_component_list','package_list',
            'component_name','material','finished_size','component_code','room_number','cabinet_number',
            'total_packages','total_pallets'
        ]
        for key in preferred_order:
            if key in label_map:
                item = QListWidgetItem(f"{label_map[key]} ({{{key}}})")
                item.setData(Qt.UserRole, key)
                self.fields_list.addItem(item)
        # 添加剩余未列出的字段
        for key in label_map.keys():
            if key not in preferred_order:
                item = QListWidgetItem(f"{label_map[key]} ({{{key}}})")
                item.setData(Qt.UserRole, key)
                self.fields_list.addItem(item)
        
        self.fields_list.itemDoubleClicked.connect(self.insert_field)
        fields_layout.addWidget(self.fields_list)
        
        # 添加字段按钮
        add_field_btn = QPushButton("插入选中字段")
        add_field_btn.clicked.connect(self.insert_field)
        fields_layout.addWidget(add_field_btn)
        
        layout.addWidget(fields_group)
        
        # 模板编辑
        template_group = QGroupBox("组合模板")
        template_layout = QVBoxLayout(template_group)
        
        template_info = QLabel("在下面的文本框中输入组合模板，使用 {字段名} 引用字段：")
        template_layout.addWidget(template_info)
        
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText("例如: {order_number} - {component_name}\n材质: {material}\n尺寸: {finished_size}")
        self.template_edit.textChanged.connect(self.update_preview)
        template_layout.addWidget(self.template_edit)
        
        layout.addWidget(template_group)
        
        # 预览
        preview_group = QGroupBox("预览效果")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("预览将在这里显示...")
        self.preview_label.setStyleSheet("background: #f5f5f5; padding: 10px; border: 1px solid #ddd;")
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def insert_field(self):
        """插入选中的字段"""
        current_item = self.fields_list.currentItem()
        if current_item:
            field_key = current_item.data(Qt.UserRole)
            cursor = self.template_edit.textCursor()
            cursor.insertText(f"{{{field_key}}}")
            self.template_edit.setTextCursor(cursor)
    
    def update_preview(self):
        """更新预览"""
        template = self.template_edit.toPlainText()
        preview = template
        # 使用传入的示例数据进行替换
        if self.sample_data:
            for field_key, sample_value in self.sample_data.items():
                preview = preview.replace(f"{{{field_key}}}", str(sample_value))
        self.preview_label.setText(preview if preview else "无内容")
    
    def load_config(self):
        """加载配置"""
        if self.config:
            template = self.config.get('template', '')
            self.template_edit.setPlainText(template)
            self.update_preview()
    
    def get_configuration(self):
        """获取配置"""
        template = self.template_edit.toPlainText()
        
        # 提取模板中使用的字段
        import re
        fields = re.findall(r'\{(\w+)\}', template)
        
        return {
            'template': template,
            'fields': list(set(fields))  # 去重
        }

class PropertyPanel(QWidget):
    """属性面板"""
    
    def __init__(self):
        super().__init__()
        self.current_item = None
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("属性面板")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # 属性容器
        self.properties_widget = QWidget()
        self.properties_layout = QVBoxLayout(self.properties_widget)
        scroll.setWidget(self.properties_widget)
        
        # 默认显示
        self.show_no_selection()
    
    def show_no_selection(self):
        """显示无选择状态"""
        self.clear_properties()
        label = QLabel("请选择一个元素")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray; padding: 20px;")
        self.properties_layout.addWidget(label)
    
    def clear_properties(self):
        """清空属性"""
        while self.properties_layout.count():
            child = self.properties_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def show_properties(self, item):
        """显示元素属性"""
        self.current_item = item
        self.clear_properties()
        
        if not item:
            self.show_no_selection()
            return
        
        # 基本属性组
        self.add_basic_properties()
        
        # 根据元素类型添加特定属性
        if item.element_type == "text":
            self.add_text_properties()
        elif item.element_type == "qrcode":
            self.add_qrcode_properties()
        elif item.element_type in ["rectangle", "line"]:
            self.add_shape_properties()
        
        # 数据绑定属性
        self.add_data_binding_properties()
        
        # 添加弹簧
        self.properties_layout.addStretch()
    
    def add_basic_properties(self):
        """添加基本属性"""
        group = QGroupBox("位置和大小")
        layout = QGridLayout(group)
        
        props = self.current_item.get_properties()
        
        # X坐标
        layout.addWidget(QLabel("X:"), 0, 0)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 1000)
        self.x_spin.setValue(int(props.get('x', 0)))
        self.x_spin.valueChanged.connect(self.update_position)
        layout.addWidget(self.x_spin, 0, 1)
        
        # Y坐标
        layout.addWidget(QLabel("Y:"), 1, 0)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 1000)
        self.y_spin.setValue(int(props.get('y', 0)))
        self.y_spin.valueChanged.connect(self.update_position)
        layout.addWidget(self.y_spin, 1, 1)
        
        # 宽度
        layout.addWidget(QLabel("宽度:"), 2, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 1000)
        self.width_spin.setValue(int(props.get('width', 100)))
        self.width_spin.valueChanged.connect(self.update_size)
        layout.addWidget(self.width_spin, 2, 1)
        
        # 高度
        layout.addWidget(QLabel("高度:"), 3, 0)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 1000)
        self.height_spin.setValue(int(props.get('height', 30)))
        self.height_spin.valueChanged.connect(self.update_size)
        layout.addWidget(self.height_spin, 3, 1)
        
        self.properties_layout.addWidget(group)
    
    def add_text_properties(self):
        """添加文本属性"""
        group = QGroupBox("文本属性")
        layout = QGridLayout(group)
        
        props = self.current_item.properties
        
        # 文本内容
        layout.addWidget(QLabel("文本:"), 0, 0)
        self.text_edit = QLineEdit()
        self.text_edit.setText(props.get('text', ''))
        self.text_edit.textChanged.connect(self.update_text)
        layout.addWidget(self.text_edit, 0, 1)
        
        # 字体
        layout.addWidget(QLabel("字体:"), 1, 0)
        self.font_combo = QComboBox()
        self.font_combo.addItems(['Arial', 'SimHei', 'SimSun', 'Microsoft YaHei'])
        self.font_combo.setCurrentText(props.get('font_family', 'Arial'))
        self.font_combo.currentTextChanged.connect(self.update_font)
        layout.addWidget(self.font_combo, 1, 1)
        
        # 字体大小
        layout.addWidget(QLabel("大小:"), 2, 0)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(props.get('font_size', 12))
        self.font_size_spin.valueChanged.connect(self.update_font_size)
        layout.addWidget(self.font_size_spin, 2, 1)
        
        # 对齐方式
        layout.addWidget(QLabel("对齐:"), 3, 0)
        self.align_combo = QComboBox()
        self.align_combo.addItems(['left', 'center', 'right'])
        self.align_combo.setCurrentText(props.get('alignment', 'left'))
        self.align_combo.currentTextChanged.connect(self.update_alignment)
        layout.addWidget(self.align_combo, 3, 1)
        
        # 颜色按钮
        layout.addWidget(QLabel("颜色:"), 4, 0)
        self.color_btn = QPushButton()
        self.color_btn.setStyleSheet(f"background-color: {props.get('color', '#000000')}")
        self.color_btn.clicked.connect(self.choose_color)
        layout.addWidget(self.color_btn, 4, 1)
        
        self.properties_layout.addWidget(group)
    
    def add_qrcode_properties(self):
        """添加二维码属性"""
        group = QGroupBox("二维码属性")
        layout = QGridLayout(group)
        
        props = self.current_item.properties
        
        # 数据内容
        layout.addWidget(QLabel("数据:"), 0, 0)
        self.qr_data_edit = QLineEdit()
        self.qr_data_edit.setText(props.get('data', ''))
        self.qr_data_edit.textChanged.connect(self.update_qr_data)
        layout.addWidget(self.qr_data_edit, 0, 1)
        
        self.properties_layout.addWidget(group)
    
    def add_shape_properties(self):
        """添加形状属性"""
        group = QGroupBox("外观属性")
        layout = QGridLayout(group)
        
        props = self.current_item.properties
        
        # 边框宽度
        layout.addWidget(QLabel("边框宽度:"), 0, 0)
        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 10)
        self.border_width_spin.setValue(props.get('border_width', 1))
        self.border_width_spin.valueChanged.connect(self.update_border_width)
        layout.addWidget(self.border_width_spin, 0, 1)
        
        # 边框颜色
        layout.addWidget(QLabel("边框颜色:"), 1, 0)
        self.border_color_btn = QPushButton()
        self.border_color_btn.setStyleSheet(f"background-color: {props.get('border_color', '#000000')}")
        self.border_color_btn.clicked.connect(self.choose_border_color)
        layout.addWidget(self.border_color_btn, 1, 1)
        
        # 背景颜色
        layout.addWidget(QLabel("背景颜色:"), 2, 0)
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setStyleSheet(f"background-color: {props.get('background_color', '#FFFFFF')}")
        self.bg_color_btn.clicked.connect(self.choose_bg_color)
        layout.addWidget(self.bg_color_btn, 2, 1)
        
        self.properties_layout.addWidget(group)
    
    def add_data_binding_properties(self):
        """添加数据绑定属性"""
        group = QGroupBox("数据绑定")
        layout = QGridLayout(group)
        
        props = self.current_item.properties
        
        # 数据字段
        layout.addWidget(QLabel("绑定字段:"), 0, 0)
        self.data_field_combo = QComboBox()
        
        # 字段显示名映射
        label_map = {
            'order_number': '订单号',
            'component_name': '板件名',
            'material': '材质',
            'finished_size': '成品尺寸',
            'component_code': '板件编码',
            'room_number': '房间号',
            'cabinet_number': '柜号',
            'package_number': '包装号',
            'package_component_list': '包装板件列表',
            'package_list': '包裹列表',
            'total_packages': '总包装数',
            'pallet_number': '托盘号',
            'total_pallets': '总托盘数',
            'customer_name': '客户名称',
            'customer_address': '客户地址',
            'create_time': '创建时间',
            'component_count': '板件数量',
            'package_count': '托盘内总包裹数',
            'status': '状态',
            'package_index': '包裹序号',
            'package_index_display': '第N包',
            'pallet_index': '托盘序号'
        }

        # 恢复为完整字段列表显示
        preferred_order = [
            'order_number','customer_name','customer_address','create_time',
            'package_number','package_index','package_index_display','pallet_number','pallet_index',
            'component_count','package_count','packing_method','status','package_component_list','package_list',
            'component_name','material','finished_size','component_code','room_number','cabinet_number',
            'total_packages','total_pallets'
        ]

        # 添加“无绑定”与“自定义组合”固定选项
        self.data_field_combo.addItem('无绑定', '')
        for key in preferred_order:
            if key in label_map:
                self.data_field_combo.addItem(label_map[key], key)
        # 添加剩余未列出的字段
        for key in label_map.keys():
            if key not in preferred_order:
                self.data_field_combo.addItem(label_map[key], key)
        self.data_field_combo.addItem('自定义组合', 'custom_combination')
        
        # 设置当前值
        current_field = props.get('data_field', '')
        for i in range(self.data_field_combo.count()):
            if self.data_field_combo.itemData(i) == current_field:
                self.data_field_combo.setCurrentIndex(i)
                break
        
        self.data_field_combo.currentTextChanged.connect(self.update_data_field)
        layout.addWidget(self.data_field_combo, 0, 1)
        
        # 组合字段配置
        layout.addWidget(QLabel("组合配置:"), 1, 0)
        self.combination_button = QPushButton("配置组合字段")
        self.combination_button.clicked.connect(self.configure_combination)
        layout.addWidget(self.combination_button, 1, 1)
        
        # 组合字段预览
        self.combination_preview = QLabel("组合预览: 无")
        self.combination_preview.setWordWrap(True)
        self.combination_preview.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.combination_preview, 2, 0, 1, 2)
        
        # 更新组合预览
        self.update_combination_preview()
        
        self.properties_layout.addWidget(group)
    
    # 属性更新方法
    def update_position(self):
        """更新位置"""
        if self.current_item:
            props = {'x': self.x_spin.value(), 'y': self.y_spin.value()}
            self.current_item.set_properties(props)
    
    def update_size(self):
        """更新大小"""
        if self.current_item:
            props = {'width': self.width_spin.value(), 'height': self.height_spin.value()}
            self.current_item.set_properties(props)
    
    def update_text(self):
        """更新文本"""
        if self.current_item:
            props = {'text': self.text_edit.text()}
            self.current_item.set_properties(props)
    
    def update_font(self):
        """更新字体"""
        if self.current_item:
            props = {'font_family': self.font_combo.currentText()}
            self.current_item.set_properties(props)
    
    def update_font_size(self):
        """更新字体大小"""
        if self.current_item:
            props = {'font_size': self.font_size_spin.value()}
            self.current_item.set_properties(props)
    
    def update_alignment(self):
        """更新对齐方式"""
        if self.current_item:
            props = {'alignment': self.align_combo.currentText()}
            self.current_item.set_properties(props)
    
    def update_qr_data(self):
        """更新二维码数据"""
        if self.current_item:
            props = {'data': self.qr_data_edit.text()}
            self.current_item.set_properties(props)
    
    def update_border_width(self):
        """更新边框宽度"""
        if self.current_item:
            props = {'border_width': self.border_width_spin.value()}
            self.current_item.set_properties(props)
    
    def update_data_field(self):
        """更新数据字段绑定"""
        if self.current_item:
            current_data = self.data_field_combo.currentData()
            props = {'data_field': current_data}
            self.current_item.set_properties(props)
            self.update_combination_preview()
    
    def configure_combination(self):
        """配置组合字段"""
        if not self.current_item:
            return
        # 传入当前画布的示例数据，供对话框预览使用
        canvas = getattr(self.current_item, 'canvas', None)
        sample_data = getattr(canvas, 'sample_data', {}) if canvas else {}
        dialog = CombinationFieldDialog(self.current_item.properties.get('combination_config', {}), sample_data=sample_data)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_configuration()
            props = {
                'data_field': 'custom_combination',
                'combination_config': config
            }
            self.current_item.set_properties(props)
            
            # 更新下拉框选择
            for i in range(self.data_field_combo.count()):
                if self.data_field_combo.itemData(i) == 'custom_combination':
                    self.data_field_combo.setCurrentIndex(i)
                    break
            
            self.update_combination_preview()
    
    def update_combination_preview(self):
        """更新组合字段预览"""
        if not hasattr(self, 'combination_preview') or not self.current_item:
            return
        
        props = self.current_item.properties
        data_field = props.get('data_field', '')
        
        if data_field == 'custom_combination':
            config = props.get('combination_config', {})
            if config:
                preview_text = self.generate_combination_preview(config)
                self.combination_preview.setText(f"组合预览: {preview_text}")
            else:
                self.combination_preview.setText("组合预览: 未配置")
        else:
            field_name = self.get_field_display_name(data_field)
            self.combination_preview.setText(f"单字段: {field_name}")
    
    def get_field_display_name(self, field_value):
        """获取字段显示名称"""
        field_map = {
            '': '无绑定',
            'order_number': '订单号',
            'component_name': '板件名',
            'material': '材质',
            'finished_size': '成品尺寸',
            'component_code': '板件编码',
            'room_number': '房间号',
            'cabinet_number': '柜号',
            'package_number': '包装号',
            'package_component_list': '包装板件列表',
            'package_list': '包裹列表',
            'total_packages': '总包装数',
            'pallet_number': '托盘号',
            'total_pallets': '总托盘数',
            'customer_name': '客户名称',
            'customer_address': '客户地址',
            'create_time': '创建时间',
            'component_count': '板件数量',
            'package_count': '托盘内总包裹数',
            'status': '状态',
            'custom_combination': '自定义组合',
            'package_index': '包裹序号',
            'package_index_display': '第N包',
            'pallet_index': '托盘序号'
        }
        return field_map.get(field_value, field_value)
    
    def generate_combination_preview(self, config):
        """生成组合字段预览文本"""
        template = config.get('template', '')
        fields = config.get('fields', [])
        
        preview = template
        for field in fields:
            field_name = self.get_field_display_name(field)
            preview = preview.replace(f"{{{field}}}", f"[{field_name}]")
        
        return preview if preview else "无模板"
    
    def choose_color(self):
        """选择颜色"""
        if self.current_item:
            color = QColorDialog.getColor()
            if color.isValid():
                color_str = color.name()
                self.color_btn.setStyleSheet(f"background-color: {color_str}")
                props = {'color': color_str}
                self.current_item.set_properties(props)
    
    def choose_border_color(self):
        """选择边框颜色"""
        if self.current_item:
            color = QColorDialog.getColor()
            if color.isValid():
                color_str = color.name()
                self.border_color_btn.setStyleSheet(f"background-color: {color_str}")
                props = {'border_color': color_str}
                self.current_item.set_properties(props)
    
    def choose_bg_color(self):
        """选择背景颜色"""
        if self.current_item:
            color = QColorDialog.getColor()
            if color.isValid():
                color_str = color.name()
                self.bg_color_btn.setStyleSheet(f"background-color: {color_str}")
                props = {'background_color': color_str}
                self.current_item.set_properties(props)

class LabelPrinting(QWidget):
    """标签打印主界面"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化属性
        self.current_template = None
        
        # 初始化撤销/重做栈
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_count = 50
        
        # 初始化剪贴板
        self.clipboard_data = None
        
        # 初始化界面
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # 先创建画布
        self.canvas = LabelCanvas()
        
        # 然后创建工具栏（需要访问canvas）
        self.create_toolbar()
        splitter.addWidget(self.toolbar_widget)
        self.canvas.item_selected.connect(self.on_item_selected)
        splitter.addWidget(self.canvas)
        
        # 右侧属性面板
        self.property_panel = PropertyPanel()
        splitter.addWidget(self.property_panel)
        
        # 设置分割器比例
        splitter.setSizes([200, 600, 300])
        
        # 设置键盘快捷键
        self.setup_shortcuts()
        
        # 加载已存在的客户模板
        self.load_existing_custom_templates()
        
        # 默认加载模板1
        self.load_default_template()
    
    def setup_shortcuts(self):
        """设置键盘快捷键"""
        # 复制快捷键 Ctrl+C
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_selected)
        
        # 粘贴快捷键 Ctrl+V
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self.paste_element)
        
        # 撤销快捷键 Ctrl+Z
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_action)
        
        # 重做快捷键 Ctrl+Y
        redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(self.redo_action)
        
        # 删除快捷键 Delete
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self.delete_selected)
        
        # 保存快捷键 Ctrl+S
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_template)
        
        # 打开快捷键 Ctrl+O
        open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self.load_template)
    
    def create_toolbar(self):
        """创建工具栏"""
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setMaximumWidth(200)
        layout = QVBoxLayout(self.toolbar_widget)
        
        # 标题
        title = QLabel("工具栏")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # 元素工具组
        elements_group = QGroupBox("元素")
        elements_layout = QVBoxLayout(elements_group)
        
        # 文本按钮
        text_btn = QPushButton("📝 文本")
        text_btn.clicked.connect(self.add_text)
        elements_layout.addWidget(text_btn)
        
        # 二维码按钮
        qr_btn = QPushButton("📱 二维码")
        qr_btn.clicked.connect(self.add_qrcode)
        elements_layout.addWidget(qr_btn)
        
        # 矩形按钮
        rect_btn = QPushButton("⬜ 矩形")
        rect_btn.clicked.connect(self.add_rectangle)
        elements_layout.addWidget(rect_btn)
        
        # 线条按钮
        line_btn = QPushButton("➖ 线条")
        line_btn.clicked.connect(self.add_line)
        elements_layout.addWidget(line_btn)
        
        layout.addWidget(elements_group)
        
        # 操作工具组
        actions_group = QGroupBox("操作")
        actions_layout = QVBoxLayout(actions_group)
        
        # 复制和粘贴
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self.copy_selected)
        actions_layout.addWidget(copy_btn)
        
        paste_btn = QPushButton("📄 粘贴")
        paste_btn.clicked.connect(self.paste_element)
        actions_layout.addWidget(paste_btn)
        
        # 撤销和重做
        undo_btn = QPushButton("↶ 撤销")
        undo_btn.clicked.connect(self.undo_action)
        actions_layout.addWidget(undo_btn)
        
        redo_btn = QPushButton("↷ 重做")
        redo_btn.clicked.connect(self.redo_action)
        actions_layout.addWidget(redo_btn)
        
        # 删除选中元素
        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.clicked.connect(self.delete_selected)
        actions_layout.addWidget(delete_btn)
        
        # 清空画布
        clear_btn = QPushButton("🧹 清空画布")
        clear_btn.clicked.connect(self.clear_canvas)
        actions_layout.addWidget(clear_btn)
        
        layout.addWidget(actions_group)
        
        # 标签尺寸设置组
        size_group = QGroupBox("标签尺寸")
        size_layout = QVBoxLayout(size_group)
        
        # 热敏标签纸预设尺寸
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设:"))
        preset_combo = QComboBox()
        preset_combo.addItems([
            "80×50mm (640×400px)",
            "100×60mm (800×480px)",
            "100×70mm (800×560px)",
            "100×80mm (800×640px)",
            "120×80mm (960×640px)",
            "自定义尺寸"
        ])
        preset_combo.currentTextChanged.connect(self.apply_preset_size)
        preset_layout.addWidget(preset_combo)
        size_layout.addLayout(preset_layout)
        
        # 宽度设置
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("宽度:"))
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(200, 2000)  # 适配热敏标签纸范围
        self.width_spinbox.setValue(self.canvas.label_width)
        self.width_spinbox.setSuffix(" px")
        self.width_spinbox.valueChanged.connect(self.update_canvas_width)
        width_layout.addWidget(self.width_spinbox)
        
        # 显示毫米值
        self.width_mm_label = QLabel("(80mm)")
        width_layout.addWidget(self.width_mm_label)
        size_layout.addLayout(width_layout)
        
        # 高度设置
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("高度:"))
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(200, 1600)  # 适配热敏标签纸范围
        self.height_spinbox.setValue(self.canvas.label_height)
        self.height_spinbox.setSuffix(" px")
        self.height_spinbox.valueChanged.connect(self.update_canvas_height)
        height_layout.addWidget(self.height_spinbox)
        
        # 显示毫米值
        self.height_mm_label = QLabel("(50mm)")
        height_layout.addWidget(self.height_mm_label)
        size_layout.addLayout(height_layout)
        
        # 预设尺寸按钮
        preset_layout = QHBoxLayout()
        preset_small_btn = QPushButton("小")
        preset_small_btn.setToolTip("300x200")
        preset_small_btn.clicked.connect(lambda: self.set_preset_size(300, 200))
        preset_layout.addWidget(preset_small_btn)
        
        preset_medium_btn = QPushButton("中")
        preset_medium_btn.setToolTip("400x300")
        preset_medium_btn.clicked.connect(lambda: self.set_preset_size(400, 300))
        preset_layout.addWidget(preset_medium_btn)
        
        preset_large_btn = QPushButton("大")
        preset_large_btn.setToolTip("600x400")
        preset_large_btn.clicked.connect(lambda: self.set_preset_size(600, 400))
        preset_layout.addWidget(preset_large_btn)
        size_layout.addLayout(preset_layout)
        
        layout.addWidget(size_group)
        
        # 模板工具组
        template_group = QGroupBox("模板")
        template_layout = QVBoxLayout(template_group)
        
        # 保存模板按钮
        save_btn = QPushButton("💾 保存模板")
        save_btn.clicked.connect(self.save_template)
        template_layout.addWidget(save_btn)
        
        # 加载模板按钮
        load_btn = QPushButton("📂 加载模板")
        # 修复：clicked 会传递一个布尔参数，导致方法将其当作 file_path
        # 使用 lambda 显式调用以打开文件对话框
        load_btn.clicked.connect(lambda: self.load_template())
        template_layout.addWidget(load_btn)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        template_layout.addWidget(line)
        
        # 客户自制模板标题
        custom_label = QLabel("客户自制模板")
        custom_label.setStyleSheet("font-weight: bold; color: #2E86AB; margin-top: 5px;")
        template_layout.addWidget(custom_label)
        
        # 创建3个客户模板按钮
        self.custom_templates = []
        for i in range(3):
            template_widget = QWidget()
            template_widget_layout = QHBoxLayout(template_widget)
            template_widget_layout.setContentsMargins(0, 0, 0, 0)
            
            # 模板按钮
            template_btn = QPushButton(f"模板{i+1}")
            template_btn.setMinimumHeight(30)
            template_btn.clicked.connect(lambda checked, idx=i: self.load_custom_template(idx))
            template_widget_layout.addWidget(template_btn, 3)
            
            # 保存按钮
            save_custom_btn = QPushButton("💾")
            save_custom_btn.setMaximumWidth(30)
            save_custom_btn.setToolTip(f"保存到模板{i+1}")
            save_custom_btn.clicked.connect(lambda checked, idx=i: self.save_custom_template(idx))
            template_widget_layout.addWidget(save_custom_btn, 1)
            
            template_layout.addWidget(template_widget)
            self.custom_templates.append({
                'button': template_btn,
                'save_button': save_custom_btn,
                'data': None,
                'name': f"模板{i+1}"
            })
        
        layout.addWidget(template_group)
        
        # 预览和打印组
        print_group = QGroupBox("预览打印")
        print_layout = QVBoxLayout(print_group)
        
        # 预览按钮
        preview_btn = QPushButton("👁️ 预览")
        preview_btn.clicked.connect(self.preview_label)
        print_layout.addWidget(preview_btn)
        
        # 打印按钮
        print_btn = QPushButton("🖨️ 打印")
        print_btn.clicked.connect(self.print_label)
        print_layout.addWidget(print_btn)
        
        layout.addWidget(print_group)
        
        # 添加弹簧
        layout.addStretch()
    
    def add_text(self):
        """添加文本元素"""
        self.save_state_for_undo("添加文本")
        self.canvas.add_text_element()
    
    def add_qrcode(self):
        """添加二维码元素"""
        self.save_state_for_undo("添加二维码")
        self.canvas.add_qrcode_element()
    
    def add_rectangle(self):
        """添加矩形元素"""
        self.save_state_for_undo("添加矩形")
        self.canvas.add_rectangle_element()
    
    def add_line(self):
        """添加线条元素"""
        self.save_state_for_undo("添加线条")
        self.canvas.add_line_element()
    
    def delete_selected(self):
        """删除选中元素"""
        selected_items = self.canvas.scene.selectedItems()
        if selected_items:
            self.save_state_for_undo("删除元素")
            self.canvas.delete_selected()
        else:
            QMessageBox.information(self, "删除", "请先选择要删除的元素")
    
    def clear_canvas(self):
        """清空画布"""
        reply = QMessageBox.question(self, "确认", "确定要清空画布吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.save_state_for_undo("清空画布")
            self.canvas.clear_canvas()
    
    def update_canvas_width(self, width):
        """更新画布宽度"""
        self.canvas.label_width = width
        self.canvas.update_canvas_size()
        # 更新毫米显示 (203 DPI: 1mm ≈ 8px)
        mm_width = round(width / 8)
        self.width_mm_label.setText(f"({mm_width}mm)")
    
    def update_canvas_height(self, height):
        """更新画布高度"""
        self.canvas.label_height = height
        self.canvas.update_canvas_size()
        # 更新毫米显示 (203 DPI: 1mm ≈ 8px)
        mm_height = round(height / 8)
        self.height_mm_label.setText(f"({mm_height}mm)")
    
    def apply_preset_size(self, preset_text):
        """应用预设尺寸"""
        if "80×50mm" in preset_text:
            self.set_preset_size(640, 400)
        elif "100×60mm" in preset_text:
            self.set_preset_size(800, 480)
        elif "100×70mm" in preset_text:
            self.set_preset_size(800, 560)
        elif "100×80mm" in preset_text:
            self.set_preset_size(800, 640)
        elif "120×80mm" in preset_text:
            self.set_preset_size(960, 640)
    
    def set_preset_size(self, width, height):
        """设置预设尺寸"""
        self.width_spinbox.setValue(width)
        self.height_spinbox.setValue(height)
        self.canvas.label_width = width
        self.canvas.label_height = height
        self.canvas.update_canvas_size()
    
    def save_state_for_undo(self, action_name):
        """保存状态用于撤销"""
        state = {
            'action': action_name,
            'canvas_width': self.canvas.label_width,
            'canvas_height': self.canvas.label_height,
            'elements': []
        }
        
        # 保存所有元素的状态
        for item in self.canvas.get_all_elements():
            state['elements'].append(item.get_properties())
        
        self.undo_stack.append(state)
        
        # 限制撤销栈大小
        if len(self.undo_stack) > self.max_undo_count:
            self.undo_stack.pop(0)
        
        # 清空重做栈
        self.redo_stack.clear()
    
    def copy_selected(self):
        """复制选中的元素"""
        selected_items = self.canvas.scene().selectedItems()
        if selected_items:
            # 只复制第一个选中的元素
            item = selected_items[0]
            if hasattr(item, 'get_properties'):
                self.clipboard_data = item.get_properties()
                QMessageBox.information(self, "复制", "元素已复制到剪贴板")
        else:
            QMessageBox.information(self, "复制", "请先选择要复制的元素")
    
    def paste_element(self):
        """粘贴元素"""
        if not self.clipboard_data:
            QMessageBox.information(self, "粘贴", "剪贴板为空")
            return
        
        self.save_state_for_undo("粘贴元素")
        
        # 复制数据并偏移位置
        paste_data = self.clipboard_data.copy()
        paste_data['x'] = paste_data.get('x', 50) + 20
        paste_data['y'] = paste_data.get('y', 50) + 20
        
        # 根据元素类型创建新元素
        element_type = paste_data.get('type', 'text')
        
        if element_type == 'text':
            item = self.canvas.add_text_element(paste_data['x'], paste_data['y'])
        elif element_type == 'qrcode':
            item = self.canvas.add_qrcode_element(paste_data['x'], paste_data['y'])
        elif element_type == 'rectangle':
            item = self.canvas.add_rectangle_element(paste_data['x'], paste_data['y'])
        elif element_type == 'line':
            item = self.canvas.add_line_element(paste_data['x'], paste_data['y'])
        else:
            return
        
        # 应用复制的属性
        item.set_properties(paste_data)
    
    def undo_action(self):
        """撤销操作"""
        if not self.undo_stack:
            QMessageBox.information(self, "撤销", "没有可撤销的操作")
            return
        
        # 保存当前状态到重做栈
        current_state = {
            'action': '重做',
            'canvas_width': self.canvas.label_width,
            'canvas_height': self.canvas.label_height,
            'elements': []
        }
        
        for item in self.canvas.get_all_elements():
            current_state['elements'].append(item.get_properties())
        
        self.redo_stack.append(current_state)
        
        # 恢复上一个状态
        last_state = self.undo_stack.pop()
        self.restore_state(last_state)
    
    def redo_action(self):
        """重做操作"""
        if not self.redo_stack:
            QMessageBox.information(self, "重做", "没有可重做的操作")
            return
        
        # 保存当前状态到撤销栈
        current_state = {
            'action': '撤销',
            'canvas_width': self.canvas.label_width,
            'canvas_height': self.canvas.label_height,
            'elements': []
        }
        
        for item in self.canvas.get_all_elements():
            current_state['elements'].append(item.get_properties())
        
        self.undo_stack.append(current_state)
        
        # 恢复重做状态
        redo_state = self.redo_stack.pop()
        self.restore_state(redo_state)
    
    def restore_state(self, state):
        """恢复状态"""
        # 清空画布
        self.canvas.clear_canvas()
        
        # 恢复画布尺寸
        self.canvas.label_width = state['canvas_width']
        self.canvas.label_height = state['canvas_height']
        self.canvas.update_canvas_size()
        self.width_spinbox.setValue(state['canvas_width'])
        self.height_spinbox.setValue(state['canvas_height'])
        
        # 恢复元素
        for element_data in state['elements']:
            element_type = element_data.get('type', 'text')
            
            if element_type == 'text':
                item = self.canvas.add_text_element(
                    element_data.get('x', 50), 
                    element_data.get('y', 50)
                )
            elif element_type == 'qrcode':
                item = self.canvas.add_qrcode_element(
                    element_data.get('x', 50), 
                    element_data.get('y', 50)
                )
            elif element_type == 'rectangle':
                item = self.canvas.add_rectangle_element(
                    element_data.get('x', 50), 
                    element_data.get('y', 50)
                )
            elif element_type == 'line':
                item = self.canvas.add_line_element(
                    element_data.get('x', 50), 
                    element_data.get('y', 50)
                )
            
            if item:
                item.set_properties(element_data)
    
    def on_item_selected(self, item):
        """元素选择时的处理"""
        self.property_panel.show_properties(item)
    
    def save_template(self):
        """保存模板"""
        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if ok and name:
            template_data = self.get_template_data()
            self.save_template_to_file(name, template_data)
            QMessageBox.information(self, "成功", "模板保存成功！")
    
    def load_template(self, file_path=None):
        """加载模板"""
        # 兼容 clicked(bool) 传参，确保打开文件选择对话框
        manual_select = False
        if isinstance(file_path, bool):
            file_path = None
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择模板文件", "", "JSON Files (*.json)")
            manual_select = bool(file_path)
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                self.load_template_data(template_data)
                # 取消启动时的阻塞弹窗，仅在用户手动选择时提示
                if manual_select:
                    # 改为非阻塞提示或静默成功，避免遮挡加载界面
                    # 如需提示，可替换为状态栏消息：self.status_bar.showMessage("模板加载成功！", 2000)
                    pass
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载模板失败：{str(e)}")
    
    def get_template_data(self):
        """获取模板数据"""
        elements = []
        for item in self.canvas.get_all_elements():
            elements.append(item.get_properties())
        
        return {
            'canvas_width': self.canvas.label_width,
            'canvas_height': self.canvas.label_height,
            'elements': elements
        }
    
    def load_template_data(self, template_data):
        """加载模板数据"""
        # 清空画布
        self.canvas.clear_canvas()
        
        # 恢复画布尺寸
        if 'canvas_width' in template_data and 'canvas_height' in template_data:
            self.canvas.label_width = template_data['canvas_width']
            self.canvas.label_height = template_data['canvas_height']
            self.canvas.update_canvas_size()
            # 更新尺寸控件的值
            self.width_spinbox.setValue(template_data['canvas_width'])
            self.height_spinbox.setValue(template_data['canvas_height'])
        
        # 加载元素 - 修复位置错乱问题
        for element_data in template_data.get('elements', []):
            element_type = element_data.get('type', 'text')
            
            # 获取元素的绝对坐标和尺寸
            x = element_data.get('x', 50)
            y = element_data.get('y', 50)
            width = element_data.get('width', 100)
            height = element_data.get('height', 30)
            
            if element_type == 'text':
                item = self.canvas.add_text_element(x, y)
                # 设置正确的尺寸
                item.resize_to(QRectF(x, y, width, height))
            elif element_type == 'qrcode':
                item = self.canvas.add_qrcode_element(x, y)
                # 设置正确的尺寸
                item.resize_to(QRectF(x, y, width, height))
            elif element_type == 'rectangle':
                item = self.canvas.add_rectangle_element(x, y)
                # 设置正确的尺寸
                item.resize_to(QRectF(x, y, width, height))
            elif element_type == 'line':
                item = self.canvas.add_line_element(x, y)
                # 设置正确的尺寸
                item.resize_to(QRectF(x, y, width, height))
            else:
                continue
            
            # 设置其他属性（但不包括位置和尺寸，因为已经设置过了）
            props_copy = element_data.copy()
            props_copy.pop('x', None)
            props_copy.pop('y', None)
            props_copy.pop('width', None)
            props_copy.pop('height', None)
            item.set_properties(props_copy)
    
    def save_template_to_file(self, name, template_data):
        """保存模板到文件"""
        templates_dir = "templates"
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
        
        file_path = os.path.join(templates_dir, f"{name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
    
    def preview_label(self):
        """预览标签"""
        # 创建预览对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("标签预览")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 创建预览画布
        preview_scene = QGraphicsScene()
        preview_view = QGraphicsView(preview_scene)
        layout.addWidget(preview_view)
        
        # 渲染当前画布到预览
        self.render_preview(preview_scene)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def render_preview(self, scene):
        """渲染预览"""
        # 清空预览场景
        scene.clear()
        
        # 设置场景矩形
        scene.setSceneRect(0, 0, self.canvas.label_width, self.canvas.label_height)
        
        # 绘制背景
        scene.addRect(0, 0, self.canvas.label_width, self.canvas.label_height, 
                     QPen(QColor(0, 0, 0)), QBrush(QColor(255, 255, 255)))
        
        # 渲染所有元素
        for item in self.canvas.get_all_elements():
            self.render_element_to_scene(scene, item)
    
    def render_element_to_scene(self, scene, item):
        """将元素渲染到场景"""
        props = item.get_properties()
        
        if item.element_type == "text":
            # 获取文本内容，优先使用data字段，然后是text字段
            text_content = props.get('data', props.get('text', ''))
            
            # 处理组合字段
            if props.get('data_field') == 'custom_combination':
                combination_config = props.get('combination_config', {})
                if combination_config:
                    text_content = item.render_combination_text(combination_config)
            
            # 使用 QGraphicsTextItem 并启用自动换行
            from PyQt5.QtWidgets import QGraphicsTextItem
            from PyQt5.QtGui import QTextOption
            text_item = QGraphicsTextItem(text_content)
            text_item.setPos(props.get('x', 0), props.get('y', 0))
            text_item.setTextWidth(max(1, int(props.get('width', 100))))
            
            # 设置字体
            font = QFont()
            font.setFamily(props.get('font_family', 'Arial'))
            font.setPointSize(props.get('font_size', 12))
            font.setBold(props.get('font_bold', False))
            font.setItalic(props.get('font_italic', False))
            text_item.setFont(font)
            
            # 设置颜色
            color = QColor(props.get('color', '#000000'))
            text_item.setDefaultTextColor(color)

            # 设置对齐与换行模式
            try:
                opt = QTextOption()
                align = props.get('alignment', 'left')
                if align == 'center':
                    opt.setAlignment(Qt.AlignHCenter)
                elif align == 'right':
                    opt.setAlignment(Qt.AlignRight)
                else:
                    opt.setAlignment(Qt.AlignLeft)
                from PyQt5.QtGui import QTextOption as _QTextOption
                opt.setWrapMode(_QTextOption.WrapAtWordBoundaryOrAnywhere)
                text_item.document().setDefaultTextOption(opt)
            except Exception:
                pass
            
            # 设置边框（如果有）
            if props.get('border', False):
                border_item = scene.addRect(
                    props.get('x', 0), props.get('y', 0),
                    props.get('width', text_item.boundingRect().width()), 
                    props.get('height', text_item.boundingRect().height()),
                    QPen(QColor(props.get('border_color', '#000000')), props.get('border_width', 1)),
                    QBrush(QColor(props.get('background_color', 'transparent')))
                )
            
        elif item.element_type == "qrcode":
            # 根据绑定字段/组合配置优先生成二维码数据
            data_field = props.get('data_field', '')
            if data_field == 'custom_combination':
                combination_config = props.get('combination_config', {})
                qr_text = item.render_combination_text(combination_config) if combination_config else ''
            elif data_field:
                canvas = getattr(item, 'canvas', None)
                sample_data = getattr(canvas, 'sample_data', {}) if canvas else {}
                qr_text = str(sample_data.get(data_field, ''))
            else:
                # 回退到元素的 data/text 属性
                qr_text = props.get('data', props.get('text', ''))
            
            if qr_text:
                try:
                    import qrcode
                    from PIL import Image
                    qr = qrcode.QRCode(version=1, box_size=10, border=2)
                    qr.add_data(qr_text)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    # 转换为QPixmap并添加到场景
                    pixmap = self.pil_to_qpixmap(img)
                    pixmap_item = scene.addPixmap(pixmap)
                    pixmap_item.setPos(props.get('x', 0), props.get('y', 0))
                    
                    # 缩放到指定尺寸
                    width = props.get('width', 50)
                    height = props.get('height', 50)
                    if pixmap.width() > 0 and pixmap.height() > 0:
                        scale_x = width / pixmap.width()
                        scale_y = height / pixmap.height()
                        pixmap_item.setScale(min(scale_x, scale_y))
                except Exception as e:
                    print(f"二维码渲染失败: {e}")
                    # 如果生成失败，显示占位符
                    rect_item = scene.addRect(props.get('x', 0), props.get('y', 0), 
                                            props.get('width', 50), props.get('height', 50),
                                            QPen(QColor(0, 0, 0)), QBrush(QColor(200, 200, 200)))
                    
        elif item.element_type == "rectangle":
            rect_item = scene.addRect(props.get('x', 0), props.get('y', 0), 
                                    props.get('width', 50), props.get('height', 50),
                                    QPen(QColor(props.get('border_color', '#000000'))), 
                                    QBrush(QColor(props.get('fill_color', 'transparent'))))
                                    
        elif item.element_type == "line":
            x = props.get('x', 0)
            y = props.get('y', 0)
            width = props.get('width', 50)
            height = props.get('height', 1)
            line_item = scene.addLine(x, y, x + width, y + height,
                                    QPen(QColor(props.get('color', '#000000'))))
    
    def pil_to_qpixmap(self, pil_image):
        """将PIL图像转换为QPixmap"""
        from PyQt5.QtGui import QPixmap, QImage
        import numpy as np
        
        # 转换PIL图像为numpy数组
        img_array = np.array(pil_image.convert('RGB'))
        h, w, ch = img_array.shape
        bytes_per_line = ch * w
        
        # 创建QImage
        qt_image = QImage(img_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 转换为QPixmap
        return QPixmap.fromImage(qt_image)
    
    def save_custom_template(self, index):
        """保存客户自制模板"""
        if index < 0 or index >= len(self.custom_templates):
            return
        
        # 获取当前模板数据
        template_data = self.get_template_data()
        
        # 保存到内存
        self.custom_templates[index]['data'] = template_data
        
        # 更新按钮样式，表示已保存
        button = self.custom_templates[index]['button']
        button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        # 保存到文件
        self.save_custom_template_to_file(index, template_data)
        
        QMessageBox.information(self, "成功", f"模板{index+1}保存成功！")
    
    def load_custom_template(self, index):
        """加载客户自制模板"""
        if index < 0 or index >= len(self.custom_templates):
            return
        
        # 先尝试从文件加载
        template_data = self.load_custom_template_from_file(index)
        
        if template_data:
            self.custom_templates[index]['data'] = template_data
            self.load_template_data(template_data)
            
            # 更新按钮样式
            button = self.custom_templates[index]['button']
            button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
            
            # 取消成功弹窗，避免在界面加载时阻塞点击
            # 如需提示，可替换为状态栏消息：self.status_bar.showMessage(f"模板{index+1}加载成功！", 2000)
        else:
            QMessageBox.warning(self, "提示", f"模板{index+1}为空，请先保存模板！")
    
    def save_custom_template_to_file(self, index, template_data):
        """保存客户模板到文件"""
        templates_dir = "custom_templates"
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
        
        file_path = os.path.join(templates_dir, f"custom_template_{index+1}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存客户模板失败: {e}")
    
    def load_custom_template_from_file(self, index):
        """从文件加载客户模板"""
        templates_dir = "custom_templates"
        file_path = os.path.join(templates_dir, f"custom_template_{index+1}.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载客户模板失败: {e}")
        
        return None
    
    def load_existing_custom_templates(self):
        """加载已存在的客户模板"""
        for i in range(3):
            template_data = self.load_custom_template_from_file(i)
            if template_data:
                self.custom_templates[i]['data'] = template_data
                # 更新按钮样式，表示已有模板
                button = self.custom_templates[i]['button']
                button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
    
    def print_label(self):
        """打印标签"""
        printer = QPrinter()
        
        # 从系统设置中读取打印机配置
        printer_name = db.get_setting('printer_name', '')
        if printer_name:
            printer.setPrinterName(printer_name)
        
        # 应用系统设置中的打印机配置
        self.apply_printer_settings_from_db(printer)
        
        # 检查是否需要显示打印预览
        show_preview = db.get_setting('print_preview', 'false') == 'true'
        
        if show_preview:
            # 显示打印预览对话框
            from PyQt5.QtPrintSupport import QPrintPreviewDialog
            preview_dialog = QPrintPreviewDialog(printer, self)
            preview_dialog.setWindowTitle("标签打印预览")
            preview_dialog.paintRequested.connect(lambda: self.render_to_printer(printer))
            preview_dialog.exec_()
        else:
            # 显示打印对话框
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle("热敏标签打印设置")
            
            if dialog.exec_() != QPrintDialog.Accepted:
                return
            
            # 开始打印
            self.render_to_printer(printer)
            
            # 保存打印日志
            if db.get_setting('save_print_log', 'true') == 'true':
                self.save_print_log()
            
            QMessageBox.information(self, "成功", "热敏标签打印完成！")
    
    def apply_printer_settings_from_db(self, printer):
        """从数据库设置中应用打印机配置"""
        # 设置分辨率（兼容如 "203 DPI" 文本）
        try:
            res_raw = db.get_setting('print_resolution', '203 DPI')
            if isinstance(res_raw, str):
                import re
                m = re.search(r"\d+", res_raw)
                resolution = int(m.group()) if m else 203
            else:
                resolution = int(res_raw)
        except Exception:
            resolution = 203
        printer.setResolution(resolution)
        
        # 设置颜色模式（热敏打印机只支持灰度）
        printer.setColorMode(QPrinter.GrayScale)
        
        # 设置页面大小
        printer.setPageSize(QPrinter.Custom)
        
        # 获取标签尺寸设置（兼容系统设置里的中文预设）
        label_preset = db.get_setting('label_preset', 'custom')
        if label_preset == 'custom':
            # 使用系统设置里的自定义尺寸键名
            try:
                width_mm = float(db.get_setting('custom_width', '80'))
                height_mm = float(db.get_setting('custom_height', '50'))
            except Exception:
                width_mm, height_mm = 80.0, 50.0
        else:
            # 尝试从字符串中解析如 "80x50mm (热敏标签)"
            import re
            m = re.search(r"(\d+)\s*x\s*(\d+)", str(label_preset))
            if m:
                width_mm = float(m.group(1))
                height_mm = float(m.group(2))
            else:
                # 兼容旧英文预设
                preset_sizes = {
                    '40x30': (40, 30),
                    '50x30': (50, 30),
                    '60x40': (60, 40),
                    '80x50': (80, 50),
                    '100x60': (100, 60)
                }
                width_mm, height_mm = preset_sizes.get(label_preset, (80, 50))

        # 读取打印方向设置（不在此处交换宽高；旋转由绘制阶段处理）
        orientation_text = db.get_setting('print_orientation', '自动')
        
        from PyQt5.QtCore import QSizeF
        printer.setPaperSize(QSizeF(width_mm, height_mm), QPrinter.Millimeter)
        # 设置方向（支持来自系统设置的固定方向/自动）
        try:
            if orientation_text == '纵向':
                printer.setOrientation(QPrinter.Portrait)
            elif orientation_text == '横向':
                printer.setOrientation(QPrinter.Landscape)
            else:
                # 自动：根据宽高判断
                if width_mm >= height_mm:
                    printer.setOrientation(QPrinter.Landscape)
                else:
                    printer.setOrientation(QPrinter.Portrait)
        except Exception:
            pass

        # 允许满版打印并设置页边距（额外边距由用户配置，不再被 0 覆盖）
        try:
            printer.setFullPage(True)
            extra_margin_mm = float(db.get_setting('print_extra_margin_mm', '0') or 0.0)
            printer.setPageMargins(extra_margin_mm, extra_margin_mm, extra_margin_mm, extra_margin_mm, QPrinter.Millimeter)
        except Exception:
            pass
        
        # 设置打印质量（兼容中文/英文枚举，不再强制覆盖自定义分辨率）
        quality = db.get_setting('print_quality', '正常')
        quality_map = {
            '高质量': max(300, resolution),
            '正常': resolution,
            '草稿': min(150, resolution),
            'high': max(300, resolution),
            'medium': 203,
            'low': 150
        }
        printer.setResolution(quality_map.get(quality, resolution))
    
    def save_print_log(self):
        """保存打印日志"""
        try:
            from datetime import datetime
            log_entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'printer': db.get_setting('printer_name', '默认打印机'),
                'label_size': f"{db.get_setting('custom_label_width', '50')}x{db.get_setting('custom_label_height', '30')}mm",
                'resolution': db.get_setting('print_resolution', '203'),
                'quality': db.get_setting('print_quality', 'high')
            }
            
            # 获取现有日志
            existing_logs = db.get_setting('print_logs', '[]')
            if existing_logs:
                import json
                logs = json.loads(existing_logs)
            else:
                logs = []
            
            # 添加新日志
            logs.append(log_entry)
            
            # 限制日志数量（保留最近100条）
            if len(logs) > 100:
                logs = logs[-100:]
            
            # 保存日志
            db.set_setting('print_logs', json.dumps(logs, ensure_ascii=False))
        except Exception as e:
            print(f"保存打印日志失败: {e}")
    
    def load_default_template(self):
        """加载默认模板1"""
        import os
        template_path = os.path.join(os.path.dirname(__file__), 'templates', '1.json')
        if os.path.exists(template_path):
            try:
                self.load_template(template_path)
            except Exception as e:
                print(f"加载默认模板失败：{str(e)}")
    
    def render_to_printer(self, printer):
        """渲染到打印机（支持自动分页）"""
        # 检查是否需要分页：根据模板中文本框字段内容长度决定
        sample = getattr(self.canvas, 'sample_data', {}) or {}
        list_fields = ['package_component_list', 'package_list']

        def find_text_props_for_field(field_name):
            """定位包含指定字段的文本元素属性"""
            try:
                for item in self.canvas.get_all_elements():
                    props = item.get_properties()
                    if props.get('type') == 'text':
                        cfg = props.get('combination_config', {}) or {}
                        fields = cfg.get('fields', [])
                        tmpl = cfg.get('template', '')
                        if (field_name in fields) or (f'{{{field_name}}}' in (tmpl or '')):
                            return props
            except Exception:
                pass
            return {}

        def wrap_lines_for_field(field_name, content):
            """将超宽文本按文本框宽度自动换行，并返回换行后的行列表"""
            try:
                props = find_text_props_for_field(field_name)
                width = int(props.get('width', 300))
                padding = int(props.get('padding', 0))
                avail_w = max(1, width - 2 * padding)
                font_family = props.get('font_family', 'Microsoft YaHei')
                font_size = int(props.get('font_size', 12))
                from PyQt5.QtGui import QFont, QFontMetrics
                font = QFont(font_family, font_size)
                metrics = QFontMetrics(font)

                def text_width(txt):
                    try:
                        return metrics.horizontalAdvance(txt)
                    except Exception:
                        return metrics.width(txt)

                # 按行处理；每行内部按空格或'+'优先断行，最后回退到逐字符断行
                import re
                out_lines = []
                for raw in str(content).split('\n'):
                    if not raw:
                        continue
                    buf = ''
                    tokens = re.split(r'(\s+|\+)', raw)  # 保留分隔符
                    for tk in tokens:
                        if tk == '':
                            continue
                        candidate = buf + tk
                        if text_width(candidate) <= avail_w:
                            buf = candidate
                        else:
                            # 若当前 token 太宽，尝试逐字符切分
                            if text_width(tk) > avail_w:
                                for ch in tk:
                                    cand2 = buf + ch
                                    if text_width(cand2) <= avail_w:
                                        buf = cand2
                                    else:
                                        if buf.strip():
                                            out_lines.append(buf)
                                        buf = ch
                                continue
                            # 将当前缓冲输出并开启新行
                            if buf.strip():
                                out_lines.append(buf)
                            buf = tk
                    if buf.strip():
                        out_lines.append(buf)
                return out_lines
            except Exception:
                # 失败时回退为原始按行分割
                return [l for l in str(content).split('\n') if l.strip()]

        def estimate_lines_per_page_for(field_name):
            """根据文本元素的实际高度与字体度量估算每页可容纳的行数。
            更精准地计算板件/托盘列表的分页，避免内容被截断。
            """
            try:
                lines_per = 15  # 合理的默认值
                for item in self.canvas.get_all_elements():
                    props = item.get_properties()
                    if props.get('type') == 'text':
                        cfg = props.get('combination_config', {}) or {}
                        fields = cfg.get('fields', [])
                        tmpl = cfg.get('template', '')
                        # 该文本框是否包含指定字段
                        if (field_name in fields) or (f'{{{field_name}}}' in (tmpl or '')):
                            font_family = props.get('font_family', 'Microsoft YaHei')
                            font_size = int(props.get('font_size', 12))
                            padding = int(props.get('padding', 0))
                            height = int(props.get('height', 200))
                            content_h = max(1, height - 2 * padding)
                            # 使用字体度量获取更准确的行高
                            try:
                                from PyQt5.QtGui import QFont, QFontMetrics
                                font = QFont(font_family, font_size)
                                metrics = QFontMetrics(font)
                                line_height = max(10, int(metrics.lineSpacing()))
                            except Exception:
                                # 回退：字号+4 近似行高
                                line_height = max(10, font_size + 4)
                            # 预留一点空间，避免最后一行被边距裁切
                            lines_per = max(1, (content_h // line_height) - 1)
                            break
                return max(1, lines_per)
            except Exception:
                # 回退默认值
                return 12

        pages_data = None
        for field in list_fields:
            content = str(sample.get(field, '') or '')
            # 先根据文本框宽度自动换行，再计算分页
            lines = wrap_lines_for_field(field, content)
            if lines:
                lines_per_page = estimate_lines_per_page_for(field)
                if len(lines) > lines_per_page:
                    base = dict(sample)
                    pages_data = []
                    for i in range(0, len(lines), lines_per_page):
                        chunk = '\n'.join(lines[i:i + lines_per_page])
                        page_data = dict(base)
                        page_data[field] = chunk
                        pages_data.append(page_data)
                    break

        if pages_data:
            # 使用多页渲染
            self.render_multiple_pages(printer, pages_data)
            return

        # 单页渲染
        painter = QPainter(printer)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        source_rect = self.canvas.scene.sceneRect()
        # 使用打印页区域而非viewport，避免驱动缩放影响
        page_rect = printer.pageRect()
        from PyQt5.QtCore import QRectF
        # 目标矩形考虑额外边距，避免内容被裁切
        try:
            extra_margin_mm = float(db.get_setting('print_extra_margin_mm', '0') or 0)
            dpi_x = printer.logicalDpiX()
            dpi_y = printer.logicalDpiY()
            mx = extra_margin_mm * dpi_x / 25.4
            my = extra_margin_mm * dpi_y / 25.4
            target_rectf = QRectF(mx, my, page_rect.width() - 2 * mx, page_rect.height() - 2 * my)
        except Exception:
            target_rectf = QRectF(page_rect)
        # 应用用户校准：旋转、偏移与缩放（顺序统一：先旋转再偏移缩放）
        try:
            orientation = db.get_setting('print_orientation', '自动') or '自动'
            offset_x_mm = float(db.get_setting('print_offset_x_mm', '0') or 0)
            offset_y_mm = float(db.get_setting('print_offset_y_mm', '0') or 0)
            scale_percent = int(db.get_setting('print_scale_percent', '100') or 100)
        except Exception:
            orientation = '自动'
            offset_x_mm = 0.0
            offset_y_mm = 0.0
            scale_percent = 100

        def mm_to_dev_x(mm):
            try:
                return (float(mm) / 25.4) * float(printer.logicalDpiX())
            except Exception:
                return float(mm)
        def mm_to_dev_y(mm):
            try:
                return (float(mm) / 25.4) * float(printer.logicalDpiY())
            except Exception:
                return float(mm)

        painter.save()
        # 旋转坐标系（与系统设置保持一致）
        try:
            if orientation in ('旋转90°', '90°'):
                painter.translate(page_rect.width(), 0)
                painter.rotate(90)
            elif orientation in ('旋转180°', '180°'):
                painter.translate(page_rect.width(), page_rect.height())
                painter.rotate(180)
            elif orientation in ('旋转270°', '270°'):
                painter.translate(0, page_rect.height())
                painter.rotate(270)
        except Exception:
            pass
        # 平移与缩放（在旋转之后，让偏移相对物理方向）
        try:
            painter.translate(mm_to_dev_x(offset_x_mm), mm_to_dev_y(offset_y_mm))
            scale = max(0.01, (scale_percent or 100) / 100.0)
            painter.scale(scale, scale)
        except Exception:
            pass
        self.canvas.scene.render(painter, target_rectf, source_rect)
        try:
            painter.restore()
        except Exception:
            pass
        painter.end()

    def render_multiple_pages(self, printer, pages_data):
        """渲染多页到打印机。pages_data 为每页的 sample_data 字典列表。"""
        # 开始打印
        painter = QPainter(printer)
        # 高质量渲染
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 统一源与目标矩形
        source_rect = self.canvas.scene.sceneRect()
        # 以打印页区域为目标矩形，考虑额外边距
        page_rect = printer.pageRect()
        from PyQt5.QtCore import QRectF
        # 目标矩形考虑额外边距，避免内容被裁切
        try:
            extra_margin_mm = float(db.get_setting('print_extra_margin_mm', '0') or 0)
            dpi_x = printer.logicalDpiX()
            dpi_y = printer.logicalDpiY()
            mx = extra_margin_mm * dpi_x / 25.4
            my = extra_margin_mm * dpi_y / 25.4
            target_rectf = QRectF(mx, my, page_rect.width() - 2 * mx, page_rect.height() - 2 * my)
        except Exception:
            target_rectf = QRectF(page_rect)

        # 逐页渲染
        for i, page_data in enumerate(pages_data):
            try:
                if hasattr(self.canvas, 'sample_data') and isinstance(page_data, dict):
                    # 更新当前页数据
                    base = getattr(self.canvas, 'sample_data', {})
                    if isinstance(base, dict):
                        # 创建合并后的数据，避免遗留数据被清空
                        merged = dict(base)
                        merged.update(page_data)
                        self.canvas.sample_data = merged
                # 应用用户校准：偏移、缩放与旋转
                try:
                    orientation = db.get_setting('print_orientation', '自动') or '自动'
                    offset_x_mm = float(db.get_setting('print_offset_x_mm', '0') or 0)
                    offset_y_mm = float(db.get_setting('print_offset_y_mm', '0') or 0)
                    scale_percent = int(db.get_setting('print_scale_percent', '100') or 100)
                except Exception:
                    orientation = '自动'
                    offset_x_mm = 0.0
                    offset_y_mm = 0.0
                    scale_percent = 100

                def mm_to_dev_x(mm):
                    try:
                        return (float(mm) / 25.4) * float(printer.logicalDpiX())
                    except Exception:
                        return float(mm)
                def mm_to_dev_y(mm):
                    try:
                        return (float(mm) / 25.4) * float(printer.logicalDpiY())
                    except Exception:
                        return float(mm)

                painter.save()
                # 旋转坐标系（与系统设置保持一致）
                try:
                    if orientation in ('旋转90°', '90°'):
                        painter.translate(page_rect.width(), 0)
                        painter.rotate(90)
                    elif orientation in ('旋转180°', '180°'):
                        painter.translate(page_rect.width(), page_rect.height())
                        painter.rotate(180)
                    elif orientation in ('旋转270°', '270°'):
                        painter.translate(0, page_rect.height())
                        painter.rotate(270)
                except Exception:
                    pass
                # 平移与缩放（在旋转之后，让偏移相对物理方向）
                try:
                    painter.translate(mm_to_dev_x(offset_x_mm), mm_to_dev_y(offset_y_mm))
                    scale = max(0.01, (scale_percent or 100) / 100.0)
                    painter.scale(scale, scale)
                except Exception:
                    pass

                # 渲染本页
                self.canvas.scene.render(painter, target_rectf, source_rect)
                try:
                    painter.restore()
                except Exception:
                    pass
                # 如果不是最后一页，翻页
                if i < len(pages_data) - 1:
                    printer.newPage()
            except Exception:
                # 即使单页渲染失败也尽量继续
                try:
                    if i < len(pages_data) - 1:
                        printer.newPage()
                except Exception:
                    pass
        painter.end()