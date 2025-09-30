import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                             QWidget, QMenuBar, QStatusBar, QAction, QMessageBox,
                             QHBoxLayout, QLabel, QPushButton, QSplashScreen)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QFont
from database import db
import traceback

# 导入各个模块
from order_management import OrderManagement
from scan_packaging import ScanPackaging
from pallet_management import PalletManagement
from label_printing import LabelPrinting
from system_settings import SystemSettings
from reports import Reports
from error_handling import ErrorHandling

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("哈迪斯 打包系统 v1.0")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置应用图标（窗口与任务栏）
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'ico10.ico')
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                self.setWindowIcon(app_icon)
            else:
                # 若图标缺失，保持默认图标但不阻塞启动
                self.setWindowIcon(QIcon())
        except Exception:
            # 防御式处理，避免图标设置异常影响启动
            self.setWindowIcon(QIcon())
        
        # 初始化UI
        self.init_ui()
        
        # 初始化状态栏
        self.init_status_bar()
        
        # 初始化菜单栏
        self.init_menu_bar()
        
        # 设置样式
        self.set_style()
        
        # 显示欢迎信息
        self.show_welcome_message()
    
    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 延迟创建各个模块标签页，避免阻塞启动界面
        QTimer.singleShot(0, self.create_tabs)
        
        # 设置默认选中第一个标签页
        self.tab_widget.setCurrentIndex(0)
    
    def create_tabs(self):
        """创建所有功能模块的标签页"""
        try:
            # 订单管理模块
            self.order_management = OrderManagement()
            self.tab_widget.addTab(self.order_management, "📋 订单管理")
            
            # 扫描打包模块
            self.scan_packaging = ScanPackaging()
            self.tab_widget.addTab(self.scan_packaging, "📦 扫描打包")
            # 连接待包删除事件以刷新订单页
            try:
                self.scan_packaging.components_deleted_from_pending.connect(self.on_components_deleted_from_pending)
            except Exception:
                pass
            
            # 托盘管理模块
            self.pallet_management = PalletManagement()
            self.tab_widget.addTab(self.pallet_management, "🚛 托盘管理")
            
            # 标签打印模块
            self.label_printing = LabelPrinting()
            self.tab_widget.addTab(self.label_printing, "🏷️ 标签打印")
            
            # 报表统计模块
            self.reports = Reports()
            self.tab_widget.addTab(self.reports, "📊 报表统计")
            
            # 系统设置模块
            self.system_settings = SystemSettings()
            self.tab_widget.addTab(self.system_settings, "⚙️ 系统设置")
            
            # 异常处理模块
            self.error_handling = ErrorHandling()
            self.tab_widget.addTab(self.error_handling, "🔧 异常处理")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化模块时发生错误：\n{str(e)}")
            print(f"Error creating tabs: {e}")
            traceback.print_exc()

    def on_components_deleted_from_pending(self, order_id: int):
        """待包列表删除后，刷新订单管理页的组件列表与统计"""
        try:
            if hasattr(self, 'order_management'):
                if hasattr(self.order_management, 'load_order_details') and order_id:
                    self.order_management.load_order_details(order_id)
                # 同步刷新订单列表以更新总数统计
                if hasattr(self.order_management, 'load_orders'):
                    self.order_management.load_orders()
        except Exception:
            pass
    
    def init_menu_bar(self):
        """初始化菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件(&F)')
        
        # 导入数据
        import_action = QAction('导入CSV数据', self)
        import_action.setShortcut('Ctrl+I')
        import_action.triggered.connect(self.import_data)
        file_menu.addAction(import_action)
        
        # 导出数据
        export_action = QAction('导出数据', self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具(&T)')
        
        # 数据库备份
        backup_action = QAction('数据库备份', self)
        backup_action.triggered.connect(self.backup_database)
        tools_menu.addAction(backup_action)
        
        # 数据库恢复
        restore_action = QAction('数据库恢复', self)
        restore_action.triggered.connect(self.restore_database)
        tools_menu.addAction(restore_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')
        
        # 关于
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_status_bar(self):
        """初始化状态栏"""
        self.status_bar = self.statusBar()
        
        # 左侧状态信息
        self.status_label = QLabel("系统就绪")
        self.status_bar.addWidget(self.status_label)
        
        # 右侧信息
        self.status_bar.addPermanentWidget(QLabel("哈迪斯 打包系统"))
        
        # 定时更新状态
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # 每5秒更新一次
    
    def update_status(self):
        """更新状态栏信息"""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 获取今日统计信息
            cursor.execute('''
                SELECT 
                    (SELECT COUNT(*) FROM packages WHERE DATE(created_at) = DATE('now')) as packages_today,
                    (SELECT COUNT(*) FROM packages WHERE status = 'open') as open_packages,
                    (SELECT COUNT(*) FROM pallets WHERE status = 'open') as open_pallets
            ''')
            
            result = cursor.fetchone()
            if result:
                packages_today, open_packages, open_pallets = result
                status_text = f"今日包装: {packages_today} | 未完成包装: {open_packages} | 未封托盘: {open_pallets}"
                self.status_label.setText(status_text)
            
            conn.close()
        except Exception as e:
            self.status_label.setText(f"状态更新失败: {str(e)}")
    
    def set_style(self):
        """设置应用样式"""
        style = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        
        QTabWidget::pane {
            border: 1px solid #c0c0c0;
            background-color: white;
        }
        
        QTabWidget::tab-bar {
            alignment: left;
        }
        
        QTabBar::tab {
            background-color: #e1e1e1;
            border: 1px solid #c0c0c0;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom-color: white;
        }
        
        QTabBar::tab:hover {
            background-color: #f0f0f0;
        }
        
        QStatusBar {
            background-color: #e1e1e1;
            border-top: 1px solid #c0c0c0;
        }
        
        QMenuBar {
            background-color: #f0f0f0;
            border-bottom: 1px solid #c0c0c0;
        }
        
        QMenuBar::item {
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #d0d0d0;
        }
        """
        self.setStyleSheet(style)
    
    def show_welcome_message(self):
        """显示欢迎信息"""
        self.status_label.setText("欢迎使用 哈迪斯 打包系统！")
        QTimer.singleShot(3000, lambda: self.status_label.setText("系统就绪"))
    
    def import_data(self):
        """导入数据"""
        try:
            # 切换到订单管理标签页并触发导入
            self.tab_widget.setCurrentIndex(0)
            self.order_management.import_csv_data()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入数据时发生错误：\n{str(e)}")
    
    def export_data(self):
        """导出数据"""
        try:
            # 切换到报表统计标签页并触发导出
            self.tab_widget.setCurrentIndex(4)
            self.reports.export_all_data()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出数据时发生错误：\n{str(e)}")
    
    def backup_database(self):
        """备份数据库"""
        try:
            import shutil
            from datetime import datetime
            
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db.db_path, backup_name)
            QMessageBox.information(self, "成功", f"数据库已备份为: {backup_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"备份数据库时发生错误：\n{str(e)}")
    
    def restore_database(self):
        """恢复数据库"""
        from PyQt5.QtWidgets import QFileDialog
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择备份文件", "", "数据库文件 (*.db)")
            
            if file_path:
                import shutil
                shutil.copy2(file_path, db.db_path)
                QMessageBox.information(self, "成功", "数据库已恢复，请重启应用程序")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复数据库时发生错误：\n{str(e)}")
    
    def show_about(self):
        """显示关于信息"""
        about_text = """
        <h3>板件家具打包系统 v1.0</h3>
        <p>专业的板件家具生产打包管理系统</p>
        <p><b>主要功能：</b></p>
        <ul>
        <li>订单管理和CSV数据导入</li>
        <li>扫码打包和包装管理</li>
        <li>托盘管理和装载跟踪</li>
        <li>标签设计和打印</li>
        <li>数据统计和报表导出</li>
        </ul>
        <p><b>技术支持：</b> 哈迪斯 李昌顺 开发</p>
        """
        QMessageBox.about(self, "关于", about_text)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        reply = QMessageBox.question(
            self, '确认退出', 
            '确定要退出板件家具打包系统吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 保存当前状态
            try:
                # 这里可以添加保存当前工作状态的代码
                pass
            except Exception as e:
                print(f"保存状态时发生错误: {e}")
            
            event.accept()
        else:
            event.ignore()

class SplashScreen(QSplashScreen):
    """启动画面"""
    def __init__(self):
        super().__init__()
        
        # 创建启动画面
        pixmap = QPixmap(400, 300)
        pixmap.fill(Qt.white)
        self.setPixmap(pixmap)
        
        # 设置文字
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.showMessage("正在启动板件家具打包系统...", Qt.AlignCenter | Qt.AlignBottom, Qt.black)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("板件家具打包系统")
    app.setApplicationVersion("1.0")
    # 设置任务栏应用图标
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'ico10.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    
    # 设置应用字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # 显示启动画面
    splash = SplashScreen()
    splash.show()
    
    # 处理启动事件
    app.processEvents()
    
    try:
        # 初始化数据库
        splash.showMessage("正在初始化数据库...", Qt.AlignCenter | Qt.AlignBottom, Qt.black)
        app.processEvents()
        
        # 创建主窗口
        splash.showMessage("正在加载主界面...", Qt.AlignCenter | Qt.AlignBottom, Qt.black)
        app.processEvents()
        
        main_window = MainWindow()
        
        # 隐藏启动画面并显示主窗口
        splash.finish(main_window)
        main_window.show()
        
    except Exception as e:
        splash.close()
        QMessageBox.critical(None, "启动错误", f"系统启动时发生错误：\n{str(e)}")
        sys.exit(1)
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()