"""
数据库事务管理工具

提供便捷的事务管理装饰器和上下文管理器
"""

from functools import wraps
from contextlib import contextmanager
import sqlite3

from .logging_config import get_logger
from .error_handler import DatabaseError

logger = get_logger('Transaction')


@contextmanager
def transaction(db_connection=None, db_getter=None):
    """事务上下文管理器
    
    用法1（提供现有连接）:
        conn = db.get_connection()
        with transaction(db_connection=conn):
            cursor = conn.cursor()
            cursor.execute(...)
            cursor.execute(...)
        # 自动commit，异常时自动rollback
    
    用法2（使用db_getter获取连接）:
        with transaction(db_getter=lambda: db.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(...)
        # 自动关闭连接
    
    Args:
        db_connection: 现有的数据库连接
        db_getter: 获取数据库连接的函数
        
    Yields:
        数据库连接对象
    """
    conn = db_connection or (db_getter() if db_getter else None)
    if conn is None:
        raise ValueError("必须提供 db_connection 或 db_getter 参数")
    
    should_close = (db_connection is None)  # 只有我们创建的连接才需要关闭
    
    try:
        # 开始事务
        conn.execute('BEGIN')
        yield conn
        # 提交事务
        conn.commit()
        logger.debug("事务已提交")
    except Exception as e:
        # 回滚事务
        try:
            conn.rollback()
            logger.warning(f"事务已回滚: {e}")
        except Exception as rollback_error:
            logger.error(f"回滚失败: {rollback_error}")
        raise DatabaseError(f"事务执行失败: {e}") from e
    finally:
        if should_close:
            try:
                conn.close()
            except Exception as close_error:
                logger.warning(f"关闭连接失败: {close_error}")


def with_transaction(db_getter):
    """事务装饰器
    
    用于自动管理函数的事务
    
    Args:
        db_getter: 获取数据库连接的函数
    
    Example:
        @with_transaction(lambda: db.get_connection())
        def update_multiple_records(data):
            conn = db.get_connection()
            cursor = conn.cursor()
            for item in data:
                cursor.execute(...)
            conn.close()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with transaction(db_getter=db_getter) as conn:
                # 将连接注入到函数的局部变量中
                # 注意：这需要函数内部使用这个连接
                return func(*args, **kwargs)
        return wrapper
    return decorator


class TransactionManager:
    """事务管理器类
    
    用于更复杂的事务管理场景
    """
    
    def __init__(self, db_instance):
        """
        Args:
            db_instance: 数据库实例（必须有get_connection方法）
        """
        self.db = db_instance
        self._connection = None
        self._in_transaction = False
    
    def begin(self):
        """开始事务"""
        if self._in_transaction:
            raise RuntimeError("事务已经开始")
        
        self._connection = self.db.get_connection()
        self._connection.execute('BEGIN')
        self._in_transaction = True
        logger.debug("事务已开始")
    
    def commit(self):
        """提交事务"""
        if not self._in_transaction:
            raise RuntimeError("没有活动的事务")
        
        try:
            self._connection.commit()
            logger.debug("事务已提交")
        finally:
            self._cleanup()
    
    def rollback(self):
        """回滚事务"""
        if not self._in_transaction:
            raise RuntimeError("没有活动的事务")
        
        try:
            self._connection.rollback()
            logger.debug("事务已回滚")
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """清理资源"""
        if self._connection:
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"关闭连接失败: {e}")
            self._connection = None
        self._in_transaction = False
    
    @property
    def connection(self):
        """获取当前事务的连接"""
        if not self._in_transaction:
            raise RuntimeError("没有活动的事务")
        return self._connection
    
    def __enter__(self):
        """上下文管理器入口"""
        self.begin()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if exc_type is not None:
            # 发生异常，回滚
            self.rollback()
            return False  # 不抑制异常
        else:
            # 正常退出，提交
            self.commit()
            return True
