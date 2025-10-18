"""
统一的错误处理模块

提供统一的异常处理、错误记录和用户提示功能
"""

import traceback
from functools import wraps
from typing import Optional, Callable, Any
from PyQt5.QtWidgets import QMessageBox, QWidget

from .logging_config import get_logger

logger = get_logger('ErrorHandler')


class AppError(Exception):
    """应用程序基础异常类"""
    
    def __init__(self, message: str, details: Optional[str] = None, user_message: Optional[str] = None):
        """
        Args:
            message: 错误消息（用于日志）
            details: 详细错误信息
            user_message: 显示给用户的消息（如果为None，使用message）
        """
        self.message = message
        self.details = details
        self.user_message = user_message or message
        super().__init__(self.message)


class DatabaseError(AppError):
    """数据库相关错误"""
    pass


class ValidationError(AppError):
    """数据验证错误"""
    pass


class BusinessLogicError(AppError):
    """业务逻辑错误"""
    pass


class ErrorHandler:
    """统一的错误处理器"""
    
    @staticmethod
    def log_error(error: Exception, context: str = '') -> None:
        """记录错误到日志
        
        Args:
            error: 异常对象
            context: 错误上下文描述
        """
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'context': context
        }
        
        logger.error(f"错误发生: {context}", exc_info=True, extra=error_info)
    
    @staticmethod
    def show_error(parent: Optional[QWidget], error: Exception, context: str = '') -> None:
        """显示错误对话框给用户
        
        Args:
            parent: 父窗口
            error: 异常对象
            context: 错误上下文
        """
        # 记录到日志
        ErrorHandler.log_error(error, context)
        
        # 确定要显示给用户的消息
        if isinstance(error, AppError):
            title = "错误"
            message = error.user_message
            details = error.details
        else:
            title = "系统错误"
            message = f"{context}: {str(error)}" if context else str(error)
            details = traceback.format_exc()
        
        # 显示错误对话框
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # 如果有详细信息，添加到详细文本中
        if details:
            msg_box.setDetailedText(details)
        
        msg_box.exec_()
    
    @staticmethod
    def show_warning(parent: Optional[QWidget], message: str, title: str = "警告") -> None:
        """显示警告对话框
        
        Args:
            parent: 父窗口
            message: 警告消息
            title: 对话框标题
        """
        logger.warning(f"警告: {message}")
        QMessageBox.warning(parent, title, message)
    
    @staticmethod
    def show_info(parent: Optional[QWidget], message: str, title: str = "信息") -> None:
        """显示信息对话框
        
        Args:
            parent: 父窗口
            message: 信息内容
            title: 对话框标题
        """
        logger.info(f"信息: {message}")
        QMessageBox.information(parent, title, message)
    
    @staticmethod
    def confirm(parent: Optional[QWidget], message: str, title: str = "确认") -> bool:
        """显示确认对话框
        
        Args:
            parent: 父窗口
            message: 确认消息
            title: 对话框标题
            
        Returns:
            bool: 用户是否确认
        """
        reply = QMessageBox.question(
            parent, title, message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes


def handle_errors(parent_getter: Optional[Callable[[], QWidget]] = None, context: str = ''):
    """错误处理装饰器
    
    用于自动捕获和处理函数中的异常
    
    Args:
        parent_getter: 获取父窗口的函数（通常是 lambda: self）
        context: 错误上下文描述
    
    Example:
        @handle_errors(lambda: self, "加载订单")
        def load_orders(self):
            # ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                parent = parent_getter() if parent_getter else None
                ErrorHandler.show_error(parent, e, context or func.__name__)
                return None
        return wrapper
    return decorator


def handle_errors_silently(context: str = ''):
    """静默错误处理装饰器
    
    捕获异常但只记录日志，不显示对话框
    
    Args:
        context: 错误上下文描述
    
    Example:
        @handle_errors_silently("更新状态栏")
        def update_status(self):
            # ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.log_error(e, context or func.__name__)
                return None
        return wrapper
    return decorator
