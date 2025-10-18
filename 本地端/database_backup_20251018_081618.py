import sqlite3
import os
from datetime import datetime
import json

class Database:
    def __init__(self, db_path="packing_system.db"):
        self.db_path = db_path
        # 若目标文件存在但并非 SQLite3 数据库，先做安全备份并重建
        self._repair_invalid_file()
        try:
            self.init_database()
        except sqlite3.OperationalError as e:
            # 某些环境中会因为误放了非 SQLite 文件而报 unsupported file format
            if 'unsupported file format' in str(e).lower():
                self._repair_invalid_file()
                try:
                    # 优先尝试强制重建同名文件
                    self._force_recreate_db()
                    self.init_database()
                except Exception:
                    # 若重建失败（例如Windows文件锁导致无法重命名），切换到新的数据库文件路径
                    base, ext = os.path.splitext(self.db_path)
                    fallback = f"{base}_fixed{ext or '.db'}"
                    self.db_path = fallback
                    print(f"[database] Fallback to new db path: {self.db_path}")
                    # 确保目录存在并创建空库
                    try:
                        conn = sqlite3.connect(self.db_path)
                        conn.close()
                    except Exception:
                        pass
                    self.init_database()
            else:
                raise

    def _is_sqlite3_file(self) -> bool:
        try:
            if not os.path.exists(self.db_path):
                return True  # 不存在时将创建为 SQLite，新建视为有效
            with open(self.db_path, 'rb') as f:
                header = f.read(16)
            return header.startswith(b'SQLite format 3')
        except Exception:
            # 读取失败或其它异常一律视为无效，以触发修复流程
            return False

    def _repair_invalid_file(self):
        try:
            if os.path.exists(self.db_path) and not self._is_sqlite3_file():
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bad_path = f"{self.db_path}.invalid_{ts}.bak"
                os.replace(self.db_path, bad_path)
                print(f"[database] Detected non-SQLite file at {self.db_path}; moved to {bad_path} and will initialize a new database.")
        except Exception as e:
            # 备份失败不影响继续初始化（可能为只读目录），但会提示
            print(f"[database] Failed to backup invalid db file: {e}")

    def _force_recreate_db(self):
        """在检测到不受支持的文件格式时，强制重建数据库文件"""
        try:
            if os.path.exists(self.db_path):
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                bad_path = f"{self.db_path}.invalid_{ts}.bak"
                os.replace(self.db_path, bad_path)
                print(f"[database] Force recreated database: moved invalid file to {bad_path}")
            # 创建一个全新的空数据库文件
            conn = sqlite3.connect(self.db_path)
            conn.close()
        except Exception as e:
            print(f"[database] Failed to force recreate db: {e}")

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            cursor = conn.cursor()
            # 始终启用外键以保证引用完整性
            cursor.execute('PRAGMA foreign_keys = ON')
            # 设置忙等待超时，降低并发写入时的锁冲突错误
            cursor.execute('PRAGMA busy_timeout = 5000')

            # 读取可配置的 WAL 开关（默认启用）
            try:
                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key='enable_wal'")
                row = cursor.fetchone()
                enable_wal = (row[0].lower() == 'true') if row and isinstance(row[0], str) else True
            except Exception:
                enable_wal = True

            if enable_wal:
                cursor.execute('PRAGMA journal_mode = WAL')
                # NORMAL 同步在 WAL 下通常有更好吞吐
                cursor.execute('PRAGMA synchronous = NORMAL')
            else:
                cursor.execute('PRAGMA journal_mode = DELETE')
                cursor.execute('PRAGMA synchronous = FULL')

            # 其它轻量优化：缓存与临时表
            cursor.execute('PRAGMA temp_store = MEMORY')
            # 可选缓存大小（KB），从设置读取，默认 100MB
            try:
                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key='cache_size'")
                row = cursor.fetchone()
                cache_mb = int(row[0]) if row and row[0] is not None else 100
            except Exception:
                cache_mb = 100
            # negative value means KB
            cursor.execute(f'PRAGMA cache_size = {-cache_mb * 1024}')
        except Exception:
            # 若 PRAGMA 失败，不影响连接使用
            pass
        return conn
    
    def init_database(self):
        """初始化数据库，创建所有表"""
        conn = None
        try:
            conn = self.get_connection()
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
                    FOREIGN KEY (order_id) REFERENCES orders (id),
                    FOREIGN KEY (package_id) REFERENCES packages (id)
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
                    FOREIGN KEY (order_id) REFERENCES orders (id),
                    FOREIGN KEY (pallet_id) REFERENCES pallets (id)
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
                    FOREIGN KEY (package_id) REFERENCES packages (id),
                    FOREIGN KEY (component_id) REFERENCES components (id)
                )
            ''')
            
            # 创建托盘包装关联表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pallet_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pallet_id INTEGER NOT NULL,
                    package_id INTEGER NOT NULL,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pallet_id) REFERENCES pallets (id),
                    FOREIGN KEY (package_id) REFERENCES packages (id),
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
                    FOREIGN KEY (pallet_id) REFERENCES pallets (id)
                )
            ''')
            
            conn.commit()
            
            # 执行数据库迁移
            self.migrate_database(conn)
            
            conn.close()
            
            # 初始化默认设置
            self.init_default_settings()
        except sqlite3.OperationalError:
            # 发生异常时确保连接被关闭，避免Windows锁阻止后续修复
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            raise
    
    def migrate_database(self, conn):
        """执行数据库迁移"""
        cursor = conn.cursor()
        
        # 检查并添加customer_phone字段
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'customer_phone' not in columns:
            cursor.execute('ALTER TABLE orders ADD COLUMN customer_phone TEXT')
            print("已添加customer_phone字段到orders表")
        
        # 检查并添加scanned_at字段到components表
        cursor.execute("PRAGMA table_info(components)")
        components_columns = [column[1] for column in cursor.fetchall()]
        
        if 'scanned_at' not in components_columns:
            cursor.execute('ALTER TABLE components ADD COLUMN scanned_at TIMESTAMP')
            print("已添加scanned_at字段到components表")
        
        # 检查并添加备注字段到components表
        if 'remarks' not in components_columns:
            cursor.execute('ALTER TABLE components ADD COLUMN remarks TEXT')
            print("已添加remarks字段到components表")
        
        # 检查并添加自定义字段1到components表
        if 'custom_field1' not in components_columns:
            cursor.execute('ALTER TABLE components ADD COLUMN custom_field1 TEXT')
            print("已添加custom_field1字段到components表")
        
        # 检查并添加自定义字段2到components表
        if 'custom_field2' not in components_columns:
            cursor.execute('ALTER TABLE components ADD COLUMN custom_field2 TEXT')
            print("已添加custom_field2字段到components表")
        
        # 检查并添加is_manual字段到packages表
        cursor.execute("PRAGMA table_info(packages)")
        packages_columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_manual' not in packages_columns:
            cursor.execute('ALTER TABLE packages ADD COLUMN is_manual INTEGER DEFAULT 0')
            print("已添加is_manual字段到packages表")
        
        # 检查并添加packing_method字段到packages表
        if 'packing_method' not in packages_columns:
            cursor.execute('ALTER TABLE packages ADD COLUMN packing_method TEXT DEFAULT "scan"')
            print("已添加packing_method字段到packages表")

        # 新增：为packages添加package_index（每订单内稳定序号）
        if 'package_index' not in packages_columns:
            cursor.execute('ALTER TABLE packages ADD COLUMN package_index INTEGER')
            print("已添加package_index字段到packages表")
            # 回填：按每订单创建时间为现有包裹分配稳定序号
            try:
                cursor.execute('SELECT id FROM orders')
                order_rows = cursor.fetchall()
                for (oid,) in order_rows:
                    # 获取该订单的所有包裹，按创建时间排序
                    cursor.execute('''
                        SELECT id FROM packages 
                        WHERE order_id = ? 
                        ORDER BY created_at ASC, id ASC
                    ''', (oid,))
                    pkgs = [row[0] for row in cursor.fetchall()]
                    index_val = 1
                    for pid in pkgs:
                        cursor.execute('UPDATE packages SET package_index = ? WHERE id = ? AND package_index IS NULL', (index_val, pid))
                        index_val += 1
            except Exception:
                # 回填失败不阻塞迁移
                pass

        # 检查并为pallets表添加order_id字段
        cursor.execute("PRAGMA table_info(pallets)")
        pallets_columns = [column[1] for column in cursor.fetchall()]
        if 'order_id' not in pallets_columns:
            cursor.execute('ALTER TABLE pallets ADD COLUMN order_id INTEGER')
            print("已为pallets表添加order_id字段")
            # 回填：若托盘中的包裹全部属于同一订单，则设置该订单为托盘的order_id
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
            except Exception:
                pass

        # 新增：为pallets添加pallet_index（每订单内稳定序号）
        cursor.execute("PRAGMA table_info(pallets)")
        pallets_columns = [column[1] for column in cursor.fetchall()]
        if 'pallet_index' not in pallets_columns:
            cursor.execute('ALTER TABLE pallets ADD COLUMN pallet_index INTEGER')
            print("已添加pallet_index字段到pallets表")
            # 回填：按每订单创建时间为现有托盘分配稳定序号（仅对有order_id的托盘）
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
                    index_val = 1
                    for pid in pls:
                        cursor.execute('UPDATE pallets SET pallet_index = ? WHERE id = ? AND pallet_index IS NULL', (index_val, pid))
                        index_val += 1
            except Exception:
                pass

        # 创建常用索引以提升查询性能
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_packages_order_status_created ON packages(order_id, status, created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_packages_pallet_id ON packages(pallet_id)')
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_packages_package_number ON packages(package_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_packages_order_pkgindex ON packages(order_id, package_index)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_components_package_id ON components(package_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_components_order_id ON components(order_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pallets_order_status_created ON pallets(order_id, status, created_at)')
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_pallets_pallet_number ON pallets(pallet_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pallets_order_plindex ON pallets(order_id, pallet_index)')
        except Exception:
            pass

        # 检查并为import_configs添加custom_field_names列（用于存储自定义字段显示名）
        try:
            cursor.execute("PRAGMA table_info(import_configs)")
            import_configs_columns = [column[1] for column in cursor.fetchall()]
            if 'custom_field_names' not in import_configs_columns:
                cursor.execute('ALTER TABLE import_configs ADD COLUMN custom_field_names TEXT')
                print("已添加custom_field_names字段到import_configs表")
        except Exception:
            # 迁移失败不阻塞启动
            pass

        conn.commit()
        conn.close()
    
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
            # 新增：数据库与分页相关默认项
            ('enable_wal', 'true', 'boolean', '启用SQLite WAL模式'),
            ('cache_size', '100', 'integer', 'SQLite缓存大小（MB）'),
            ('pallets_page_size', '100', 'integer', '托盘列表每页行数'),
            ('packages_page_size', '100', 'integer', '包裹列表每页行数'),
        ]
        
        conn = self.get_connection()
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
        conn.close()
    
    def get_setting(self, key, default=None):
        """获取系统设置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM system_settings WHERE setting_key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default
    
    def set_setting(self, key, value):
        """设置系统设置"""
        conn = self.get_connection()
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
        conn.close()
    
    def generate_package_number(self):
        """生成包装号"""
        today = datetime.now().strftime('%Y%m%d')
        conn = self.get_connection()
        try:
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
                
        finally:
            conn.close()
    
    def generate_pallet_number(self, is_virtual=False):
        """生成托盘号（保证唯一，避免当天删除或并发导致重复）"""
        today = datetime.now().strftime('%Y%m%d')
        prefix = 'VT' if is_virtual else 'T'

        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def get_next_package_index(self, order_id):
        """获取该订单下包裹的下一个稳定序号（填补缺口）"""
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def get_next_pallet_index(self, order_id):
        """获取该订单下托盘的下一个稳定序号（填补缺口）"""
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()
    
    def log_operation(self, operation_type, operation_data, user_name='system', undo_data=None):
        """记录操作日志"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO operation_logs 
            (operation_type, operation_data, user_name, undo_data)
            VALUES (?, ?, ?, ?)
        ''', (operation_type, json.dumps(operation_data, ensure_ascii=False), user_name, 
              json.dumps(undo_data, ensure_ascii=False) if undo_data else None))
        conn.commit()
        conn.close()

# 全局数据库实例
# 注意：辅助方法必须位于类内部，并且缩进正确
# 将 db 实例保留在文件末尾，并确保没有额外缩进造成语法错误

db = Database()