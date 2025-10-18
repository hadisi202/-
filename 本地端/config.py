"""
应用配置文件

集中管理所有配置项，避免硬编码
"""

import os
from typing import List

# 数据库配置
DATABASE_PATH = os.getenv('DB_PATH', 'packing_system.db')
DATABASE_TIMEOUT = float(os.getenv('DB_TIMEOUT', '10.0'))

# API服务器配置
API_HOST = os.getenv('API_HOST', '127.0.0.1')  # 默认只监听本地，提高安全性
API_PORT = int(os.getenv('API_PORT', '5000'))
API_DEBUG = os.getenv('API_DEBUG', 'false').lower() == 'true'

# API认证配置
API_KEY_REQUIRED = os.getenv('API_KEY_REQUIRED', 'true').lower() == 'true'
API_KEYS = os.getenv('API_KEYS', '').split(',') if os.getenv('API_KEYS') else []
# 如果没有配置API_KEYS，生成一个默认的
if not API_KEYS:
    import secrets
    DEFAULT_API_KEY = secrets.token_urlsafe(32)
    API_KEYS = [DEFAULT_API_KEY]
    print(f"[警告] 未配置API_KEYS，已生成默认密钥: {DEFAULT_API_KEY}")
    print("[警告] 请在生产环境中设置环境变量 API_KEYS")

# CORS配置
CORS_ENABLED = os.getenv('CORS_ENABLED', 'true').lower() == 'true'
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:*').split(',')

# 日志配置
LOG_DIR = os.getenv('LOG_DIR', 'logs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# 系统配置
BACKUP_DIR = os.getenv('BACKUP_DIR', 'backups')
ORDERS_DIR = os.getenv('ORDERS_DIR', 'orders')
TEMPLATES_DIR = os.getenv('TEMPLATES_DIR', 'templates')
