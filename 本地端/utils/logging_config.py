"""
统一的日志配置模块

为整个应用提供统一的日志配置和工具函数
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


class AppLogger:
    """应用日志管理器"""
    
    _loggers = {}
    _initialized = False
    
    @classmethod
    def initialize(cls, log_dir='logs', log_level=logging.INFO):
        """初始化日志系统
        
        Args:
            log_dir: 日志目录
            log_level: 日志级别
        """
        if cls._initialized:
            return
        
        # 创建日志目录
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except OSError:
                log_dir = '.'  # 如果无法创建，使用当前目录
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # 移除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 创建文件处理器（每个文件最大10MB，保留5个备份）
        log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 创建错误日志文件处理器
        error_log_file = os.path.join(log_dir, f'error_{datetime.now().strftime("%Y%m%d")}.log')
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        cls._initialized = True
        
        # 记录初始化信息
        logger = cls.get_logger('AppLogger')
        logger.info(f"日志系统已初始化，日志目录: {log_dir}")
    
    @classmethod
    def get_logger(cls, name):
        """获取指定名称的日志记录器
        
        Args:
            name: 日志记录器名称（通常使用模块名）
            
        Returns:
            logging.Logger: 日志记录器实例
        """
        if not cls._initialized:
            cls.initialize()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]


# 便捷函数
def get_logger(name):
    """获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return AppLogger.get_logger(name)


# 在模块加载时初始化日志系统
AppLogger.initialize()
