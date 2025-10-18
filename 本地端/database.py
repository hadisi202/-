import sqlite3
import os
import logging
from datetime import datetime
import json
from contextlib import contextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Database')


class DatabaseError(Exception):
    """数据库相关错误的基类"""
    pass


class DatabaseInitError(DatabaseError):
    """数据库初始化错误"""
    pass


class Database:
    """改进的数据库管理类
    
    主要改进：
    1. 简化数据库修复逻辑
    2. 优化连接管理，移除重复的配置查询
    3. 添加连接上下文管理器
    4. 统一的错误处理和日志记录
    """
    
    def __init__(self, db_path="packing_system.db"):
        self.db_path = db_path
        self._connection_config = {
            'enable_wal': True,
            'cache_size_mb': 100,
            'timeout': 10.0,  # 增加超时时间到10秒
        }
        
        try:
            # 检查并修复无效的数据库文件
            self._check_and_repair_database()
            # 初始化数据库结构
            self.init_database()
            # 加载连接配置
            self._load_connection_config()
            logger.info(f"数据库初始化成功: {self.db_path}")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            raise DatabaseInitError(f"无法初始化数据库: {e}") from e
    
    def _check_and_repair_database(self):
        """检查并修复无效的数据库文件
        
        简化的修复策略：
        1. 如果文件不存在，无需处理（会自动创建）
        2. 如果文件存在但不是SQLite格式，备份后删除
        3. 如果备份失败，记录警告但继续
        """
        if not os.path.exists(self.db_path):
            return
        
        try:
            # 检查是否为有效的SQLite文件
            with open(self.db_path, 'rb') as f:
                header = f.read(16)
            
            if not header.startswith(b'SQLite format 3'):
                logger.warning(f"检测到无效的数据库文件: {self.db_path}")
                # 备份无效文件
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"{self.db_path}.invalid_{timestamp}.bak"
                try:
                    os.replace(self.db_path, backup_path)
                    logger.info(f"已将无效文件移动到: {backup_path}")
                except OSError as e:
                    logger.warning(f"无法备份无效文件: {e}")
                    # 即使备份失败，也尝试删除无效文件
                    try:
                        os.remove(self.db_path)
                        logger.info("已删除无效的数据库文件")
                    except OSError:
                        pass
        except Exception as e:
            logger.warning(f"检查数据库文件时出错: {e}")
    
    def get_connection(self):
        """获取数据库连接（兼容旧代码）
        
        注意：调用者需要手动关闭连接
        建议使用 connection_context() 上下文管理器代替
        """
        conn = sqlite3.connect(
            self.db_path, 
            timeout=self._connection_config['timeout']
        )
        self._configure_connection(conn)
        return conn
    
    @contextmanager
    def connection_context(self):
        """获取数据库连接的上下文管理器
        
        用法：
            with db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
                conn.commit()
        
        优势：
        - 自动管理连接的打开和关闭
        - 异常时自动回滚
        - 确保连接总是被释放
        """
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        except sqlite3.Error as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _configure_connection(self, conn):
        """配置数据库连接
        
        一次性配置所有PRAGMA，避免重复查询
        """
        cursor = conn.cursor()
        try:
            # 基础配置
            cursor.execute('PRAGMA foreign_keys = ON')
            cursor.execute('PRAGMA busy_timeout = 10000')  # 10秒
            cursor.execute('PRAGMA temp_store = MEMORY')
            
            # WAL模式配置（从缓存的配置读取）
            if self._connection_config['enable_wal']:
                cursor.execute('PRAGMA journal_mode = WAL')
                cursor.execute('PRAGMA synchronous = NORMAL')
            else:
                cursor.execute('PRAGMA journal_mode = DELETE')
                cursor.execute('PRAGMA synchronous = FULL')
            
            # 缓存大小（负值表示KB）
            cache_kb = -self._connection_config['cache_size_mb'] * 1024
            cursor.execute(f'PRAGMA cache_size = {cache_kb}')
            
        except sqlite3.Error as e:
            logger.warning(f"配置连接PRAGMA时出错: {e}")
    
    def _load_connection_config(self):
        """从system_settings表加载连接配置
        
        只在初始化时调用一次，避免每次连接都查询
        """
        try:
            with self.connection_context() as conn:
                cursor = conn.cursor()
                
                # 读取WAL配置
                cursor.execute(
                    "SELECT setting_value FROM system_settings WHERE setting_key='enable_wal'"
                )
                row = cursor.fetchone()
                if row:
                    self._connection_config['enable_wal'] = (
                        row[0].lower() == 'true' if isinstance(row[0], str) else True
                    )
                
                # 读取缓存大小配置
                cursor.execute(
                    "SELECT setting_value FROM system_settings WHERE setting_key='cache_size'"
                )
                row = cursor.fetchone()
                if row and row[0]:
                    try:
                        self._connection_config['cache_size_mb'] = int(row[0])
                    except ValueError:
                        pass
                        
        except sqlite3.Error as e:
            logger.warning(f"加载连接配置失败，使用默认值: {e}")
    
    def init_database(self):
        """初始化数据库，创建所有表"""
        try:
            with self.connection_context() as conn:
                cursor = conn.cursor()
                
                # 创建订单表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_number TEXT UNIQUE NOT NULL,
                        customer_name TEXT,
                        customer_address TEXT,
                        customer_phone TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'active',
                        notes TEXT
                    )
                ''')
                
                # 创建板件表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS components (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER,
                        component_name TEXT NOT NULL,
                        material TEXT,
                        finished_size TEXT,
                        component_code TEXT UNIQUE NOT NULL,
                        room_number TEXT,
                        cabinet_number TEXT,
                        q_code TEXT,
                        a_code TEXT,
                        b_code TEXT,
                        package_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                        FOREIGN KEY (package_id) REFERENCES packages (id) ON DELETE SET NULL
                    )
                ''')
                
                # 创建包装表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS packages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        package_number TEXT UNIQUE NOT NULL,
                        order_id INTEGER,
                        component_count INTEGER DEFAULT 0,
                        pallet_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        status TEXT DEFAULT 'open',
                        notes TEXT,
                        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                        FOREIGN KEY (pallet_id) REFERENCES pallets (id) ON DELETE SET NULL
                    )
                ''')
                
                # 创建托盘表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pallet_number TEXT UNIQUE NOT NULL,
                        pallet_type TEXT DEFAULT 'physical',
                        order_id INTEGER,
                        package_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sealed_at TIMESTAMP,
                        status TEXT DEFAULT 'open',
                        notes TEXT,
                        virtual_items TEXT
                    )
                ''')
                
                # 创建标签模板表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS label_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT UNIQUE NOT NULL,
                        template_config TEXT NOT NULL,
                        label_width INTEGER DEFAULT 100,
                        label_height INTEGER DEFAULT 60,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_default INTEGER DEFAULT 0
                    )
                ''')
                
                # 创建系统设置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_key TEXT UNIQUE NOT NULL,
                        setting_value TEXT,
                        setting_type TEXT DEFAULT 'string',
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建CSV导入配置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS import_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_name TEXT UNIQUE NOT NULL,
                        field_mapping TEXT NOT NULL,
                        encoding TEXT DEFAULT 'utf-8',
                        delimiter TEXT DEFAULT ',',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_default INTEGER DEFAULT 0
                    )
                ''')
                
                # 创建扫码配置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scan_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_name TEXT UNIQUE NOT NULL,
                        prefix_remove INTEGER DEFAULT 0,
                        suffix_remove INTEGER DEFAULT 0,
                        extract_start INTEGER DEFAULT 0,
                        extract_length INTEGER DEFAULT 0,
                        extract_mode TEXT DEFAULT 'none',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_default INTEGER DEFAULT 0
                    )
                ''')
                
                # 创建操作日志表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS operation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation_type TEXT NOT NULL,
                        operation_data TEXT,
                        user_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        can_undo INTEGER DEFAULT 1,
                        undo_data TEXT
                    )
                ''')
                
                # 创建包装历史表（用于撤销功能）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS package_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        package_id INTEGER,
                        component_id INTEGER,
                        operation TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (package_id) REFERENCES packages (id) ON DELETE CASCADE,
                        FOREIGN KEY (component_id) REFERENCES components (id) ON DELETE CASCADE
                    )
                ''')
                
                # 创建托盘包装关联表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pallet_packages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pallet_id INTEGER NOT NULL,
                        package_id INTEGER NOT NULL,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (pallet_id) REFERENCES pallets (id) ON DELETE CASCADE,
                        FOREIGN KEY (package_id) REFERENCES packages (id) ON DELETE CASCADE,
                        UNIQUE(pallet_id, package_id)
                    )
                ''')
                
                # 创建虚拟物品表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS virtual_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pallet_id INTEGER NOT NULL,
                        item_name TEXT NOT NULL,
                        quantity INTEGER DEFAULT 1,
                        unit TEXT,
                        specification TEXT,
                        remarks TEXT,
                        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (pallet_id) REFERENCES pallets (id) ON DELETE CASCADE
                    )
                ''')
                
                conn.commit()
                
                # 执行数据库迁移
                self.migrate_database(conn)
                
            # 初始化默认设置
            self.init_default_settings()
            
        except sqlite3.Error as e:
            logger.error(f"初始化数据库失败: {e}", exc_info=True)
            raise
    
    def migrate_database(self, conn):
        """执行数据库迁移"""
        cursor = conn.cursor()
        
        try:
            # 检查并添加customer_phone字段
            cursor.execute("PRAGMA table_info(orders)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'customer_phone' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN customer_phone TEXT')
                logger.info("已添加customer_phone字段到orders表")
            
            # 检查并添加字段到components表
            cursor.execute("PRAGMA table_info(components)")
            components_columns = [column[1] for column in cursor.fetchall()]
            
            fields_to_add = [
                ('scanned_at', 'TIMESTAMP'),
                ('remarks', 'TEXT'),
                ('custom_field1', 'TEXT'),
                ('custom_field2', 'TEXT')
            ]
            
            for field_name, field_type in fields_to_add:
                if field_name not in components_columns:
                    cursor.execute(f'ALTER TABLE components ADD COLUMN {field_name} {field_type}')
                    logger.info(f"已添加{field_name}字段到components表")
            
            # 检查并添加字段到packages表
            cursor.execute("PRAGMA table_info(packages)")
            packages_columns = [column[1] for column in cursor.fetchall()]
            
            if 'is_manual' not in packages_columns:
                cursor.execute('ALTER TABLE packages ADD COLUMN is_manual INTEGER DEFAULT 0')
                logger.info("已添加is_manual字段到packages表")
            
            if 'packing_method' not in packages_columns:
                cursor.execute('ALTER TABLE packages ADD COLUMN packing_method TEXT DEFAULT "scan"')
                logger.info("已添加packing_method字段到packages表")

            # 为packages添加package_index（每订单内稳定序号）
            if 'package_index' not in packages_columns:
                cursor.execute('ALTER TABLE packages ADD COLUMN package_index INTEGER')
                logger.info("已添加package_index字段到packages表")
                # 回填数据
                self._backfill_package_indices(cursor)

            # 检查并为pallets表添加order_id字段
            cursor.execute("PRAGMA table_info(pallets)")
            pallets_columns = [column[1] for column in cursor.fetchall()]
            
            if 'order_id' not in pallets_columns:
                cursor.execute('ALTER TABLE pallets ADD COLUMN order_id INTEGER')
                logger.info("已为pallets表添加order_id字段")
                # 回填数据
                self._backfill_pallet_order_ids(cursor)

            # 为pallets添加pallet_index（每订单内稳定序号）
            if 'pallet_index' not in pallets_columns:
                cursor.execute('ALTER TABLE pallets ADD COLUMN pallet_index INTEGER')
                logger.info("已添加pallet_index字段到pallets表")
                # 回填数据
                self._backfill_pallet_indices(cursor)

            # 创建索引以提升查询性能
            self._create_indices(cursor)

            # 检查并为import_configs添加custom_field_names列
            cursor.execute("PRAGMA table_info(import_configs)")
            import_configs_columns = [column[1] for column in cursor.fetchall()]
            if 'custom_field_names' not in import_configs_columns:
                cursor.execute('ALTER TABLE import_configs ADD COLUMN custom_field_names TEXT')
                logger.info("已添加custom_field_names字段到import_configs表")

            conn.commit()
            
        except sqlite3.Error as e:
            logger.error(f"数据库迁移失败: {e}", exc_info=True)
            raise
    
    def _backfill_package_indices(self, cursor):
        """回填包裹的稳定序号"""
        try:
            cursor.execute('SELECT id FROM orders')
            order_rows = cursor.fetchall()
            for (oid,) in order_rows:
                cursor.execute('''
                    SELECT id FROM packages 
                    WHERE order_id = ? 
                    ORDER BY created_at ASC, id ASC
                ''', (oid,))
                pkgs = [row[0] for row in cursor.fetchall()]
                for index_val, pid in enumerate(pkgs, start=1):
                    cursor.execute(
                        'UPDATE packages SET package_index = ? WHERE id = ? AND package_index IS NULL',
                        (index_val, pid)
                    )
        except sqlite3.Error as e:
            logger.warning(f"回填包裹序号失败: {e}")
    
    def _backfill_pallet_order_ids(self, cursor):
        """回填托盘的订单ID"""
        try:
            cursor.execute('''
                UPDATE pallets AS pal
                SET order_id = (
                    SELECT p.order_id
                    FROM packages p
                    WHERE p.pallet_id = pal.id
                    GROUP BY p.order_id
                    HAVING COUNT(*) = (
                        SELECT COUNT(*) FROM packages p2 WHERE p2.pallet_id = pal.id
                    )
                )
                WHERE EXISTS (SELECT 1 FROM packages p WHERE p.pallet_id = pal.id)
                  AND (
                    SELECT COUNT(DISTINCT p3.order_id)
                    FROM packages p3
                    WHERE p3.pallet_id = pal.id
                  ) = 1
            ''')
        except sqlite3.Error as e:
            logger.warning(f"回填托盘订单ID失败: {e}")
    
    def _backfill_pallet_indices(self, cursor):
        """回填托盘的稳定序号"""
        try:
            cursor.execute('SELECT DISTINCT order_id FROM pallets WHERE order_id IS NOT NULL')
            order_rows = cursor.fetchall()
            for (oid,) in order_rows:
                cursor.execute('''
                    SELECT id FROM pallets 
                    WHERE order_id = ? 
                    ORDER BY created_at ASC, id ASC
                ''', (oid,))
                pls = [row[0] for row in cursor.fetchall()]
                for index_val, pid in enumerate(pls, start=1):
                    cursor.execute(
                        'UPDATE pallets SET pallet_index = ? WHERE id = ? AND pallet_index IS NULL',
                        (index_val, pid)
                    )
        except sqlite3.Error as e:
            logger.warning(f"回填托盘序号失败: {e}")
    
    def _create_indices(self, cursor):
        """创建数据库索引"""
        indices = [
            'CREATE INDEX IF NOT EXISTS idx_packages_order_status_created ON packages(order_id, status, created_at)',
            'CREATE INDEX IF NOT EXISTS idx_packages_pallet_id ON packages(pallet_id)',
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_packages_package_number ON packages(package_number)',
            'CREATE INDEX IF NOT EXISTS idx_packages_order_pkgindex ON packages(order_id, package_index)',
            'CREATE INDEX IF NOT EXISTS idx_components_package_id ON components(package_id)',
            'CREATE INDEX IF NOT EXISTS idx_components_order_id ON components(order_id)',
            'CREATE INDEX IF NOT EXISTS idx_components_status ON components(status)',
            'CREATE INDEX IF NOT EXISTS idx_pallets_order_status_created ON pallets(order_id, status, created_at)',
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_pallets_pallet_number ON pallets(pallet_number)',
            'CREATE INDEX IF NOT EXISTS idx_pallets_order_plindex ON pallets(order_id, pallet_index)',
        ]
        
        for index_sql in indices:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"创建索引失败: {e}")
    
    def init_default_settings(self):
        """初始化默认系统设置"""
        default_settings = [
            ('package_number_format', 'YYYYMMDD{:04d}', 'string', '包装号格式'),
            ('pallet_number_format', 'T{date}{:04d}', 'string', '托盘号格式'),
            ('virtual_pallet_format', 'VT{date}{:04d}', 'string', '虚拟托盘号格式'),
            ('auto_complete_code', 'COMPLETE', 'string', '自动完成包装的扫码'),
            ('default_scan_config', '1', 'integer', '默认扫码配置ID'),
            ('default_import_config', '1', 'integer', '默认导入配置ID'),
            ('default_label_template', '1', 'integer', '默认标签模板ID'),
            ('enable_wal', 'true', 'boolean', '启用SQLite WAL模式'),
            ('cache_size', '100', 'integer', 'SQLite缓存大小（MB）'),
            ('pallets_page_size', '100', 'integer', '托盘列表每页行数'),
            ('packages_page_size', '100', 'integer', '包裹列表每页行数'),
        ]
        
        with self.connection_context() as conn:
            cursor = conn.cursor()
            
            for key, value, type_, desc in default_settings:
                cursor.execute('''
                    INSERT OR IGNORE INTO system_settings 
                    (setting_key, setting_value, setting_type, description)
                    VALUES (?, ?, ?, ?)
                ''', (key, value, type_, desc))
            
            # 创建默认扫码配置
            cursor.execute('''
                INSERT OR IGNORE INTO scan_configs 
                (config_name, prefix_remove, suffix_remove, extract_mode, is_default)
                VALUES ('默认配置-不处理', 0, 0, 'none', 1)
            ''')
            
            # 创建默认导入配置
            default_mapping = {
                'order_number': '订单号',
                'component_name': '板件名',
                'material': '材质',
                'finished_size': '成品尺寸',
                'component_code': '板件编码',
                'room_number': '房间号',
                'cabinet_number': '柜号'
            }
            
            cursor.execute('''
                INSERT OR IGNORE INTO import_configs 
                (config_name, field_mapping, is_default)
                VALUES ('默认导入配置', ?, 1)
            ''', (json.dumps(default_mapping, ensure_ascii=False),))
            
            # 创建默认标签模板
            default_template = {
                'fields': [
                    {'type': 'text', 'content': '包装号: {package_number}', 'x': 10, 'y': 10, 'font_size': 12},
                    {'type': 'text', 'content': '订单号: {order_number}', 'x': 10, 'y': 25, 'font_size': 10},
                    {'type': 'text', 'content': '客户: {customer_name}', 'x': 10, 'y': 40, 'font_size': 10},
                    {'type': 'text', 'content': '板件数: {component_count}', 'x': 10, 'y': 55, 'font_size': 10},
                    {'type': 'qrcode', 'content': '{package_number}', 'x': 200, 'y': 10, 'size': 50}
                ]
            }
            
            cursor.execute('''
                INSERT OR IGNORE INTO label_templates 
                (template_name, template_config, is_default)
                VALUES ('默认标签模板', ?, 1)
            ''', (json.dumps(default_template, ensure_ascii=False),))
            
            conn.commit()
    
    def get_setting(self, key, default=None):
        """获取系统设置"""
        try:
            with self.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT setting_value FROM system_settings WHERE setting_key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except sqlite3.Error as e:
            logger.error(f"获取设置失败 {key}: {e}")
            return default
    
    def set_setting(self, key, value):
        """设置系统设置"""
        try:
            with self.connection_context() as conn:
                cursor = conn.cursor()
                
                # 如果值是字典或列表，转换为JSON字符串
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, ensure_ascii=False)
                else:
                    value_str = str(value)
                    
                cursor.execute('''
                    INSERT OR REPLACE INTO system_settings (setting_key, setting_value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, value_str))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"设置配置失败 {key}: {e}")
            raise
    
    def generate_package_number(self):
        """生成包装号"""
        today = datetime.now().strftime('%Y%m%d')
        
        with self.connection_context() as conn:
            cursor = conn.cursor()
            
            # 查找今天最大的包装号序号
            cursor.execute('''
                SELECT package_number FROM packages 
                WHERE package_number LIKE ?
                ORDER BY package_number DESC
                LIMIT 1
            ''', (f"{today}%",))
            
            result = cursor.fetchone()
            if result:
                # 提取序号部分并加1
                last_number = result[0]
                sequence = int(last_number[-4:]) + 1
            else:
                # 今天第一个包装
                sequence = 1
            
            # 生成新的包装号，如果重复则继续递增
            while True:
                package_number = f"{today}{sequence:04d}"
                
                # 检查是否已存在
                cursor.execute('SELECT 1 FROM packages WHERE package_number = ?', (package_number,))
                if not cursor.fetchone():
                    return package_number
                
                sequence += 1
    
    def generate_pallet_number(self, is_virtual=False):
        """生成托盘号（保证唯一，避免当天删除或并发导致重复）"""
        today = datetime.now().strftime('%Y%m%d')
        prefix = 'VT' if is_virtual else 'T'

        with self.connection_context() as conn:
            cursor = conn.cursor()
            # 基础序列：当日同类型托盘计数 + 1
            cursor.execute('''
                SELECT COUNT(*) FROM pallets 
                WHERE DATE(created_at) = DATE('now') AND pallet_type = ?
            ''', ('virtual' if is_virtual else 'physical',))
            sequence = (cursor.fetchone()[0] or 0) + 1

            # 循环校验唯一性，若已存在则序列递增
            while True:
                pallet_number = f"{prefix}{today}{sequence:04d}"
                cursor.execute('SELECT 1 FROM pallets WHERE pallet_number = ?', (pallet_number,))
                if not cursor.fetchone():
                    return pallet_number
                sequence += 1

    def get_next_package_index(self, order_id):
        """获取该订单下包裹的下一个稳定序号（填补缺口）"""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT package_index FROM packages 
                WHERE order_id = ? AND package_index IS NOT NULL
                ORDER BY package_index ASC
            ''', (order_id,))
            indices = [row[0] for row in cursor.fetchall() if row and row[0] is not None]
            used = set(indices)
            i = 1
            while i in used:
                i += 1
            return i

    def get_next_pallet_index(self, order_id):
        """获取该订单下托盘的下一个稳定序号（填补缺口）"""
        with self.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pallet_index FROM pallets 
                WHERE order_id = ? AND pallet_index IS NOT NULL
                ORDER BY pallet_index ASC
            ''', (order_id,))
            indices = [row[0] for row in cursor.fetchall() if row and row[0] is not None]
            used = set(indices)
            i = 1
            while i in used:
                i += 1
            return i
    
    def log_operation(self, operation_type, operation_data, user_name='system', undo_data=None):
        """记录操作日志"""
        try:
            with self.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO operation_logs 
                    (operation_type, operation_data, user_name, undo_data)
                    VALUES (?, ?, ?, ?)
                ''', (operation_type, json.dumps(operation_data, ensure_ascii=False), user_name, 
                      json.dumps(undo_data, ensure_ascii=False) if undo_data else None))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"记录操作日志失败: {e}")


# 全局数据库实例
# 注意：为了保持向后兼容，提供 get_connection_legacy() 方法
db = Database()
