"""
改进的API服务器

主要改进：
1. 添加API Key认证
2. 限制CORS来源
3. 添加请求日志
4. 统一错误处理
5. 使用配置文件
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import sqlite3

from config import (
    DATABASE_PATH, API_HOST, API_PORT, API_DEBUG,
    API_KEY_REQUIRED, API_KEYS, CORS_ENABLED, CORS_ORIGINS
)
from utils.logging_config import get_logger

logger = get_logger('APIServer')

app = Flask(__name__)

# 配置CORS
if CORS_ENABLED:
    CORS(app, resources={
        r"/api/*": {
            "origins": CORS_ORIGINS,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-API-Key"]
        }
    })
    logger.info(f"CORS已启用，允许的来源: {CORS_ORIGINS}")

# 在首次导入时尝试修复/初始化数据库文件
try:
    from database import Database as _DB
    _db_instance = _DB(DATABASE_PATH)
    logger.info(f"数据库初始化成功: {DATABASE_PATH}")
except Exception as e:
    logger.error(f"数据库初始化失败: {e}", exc_info=True)
    _db_instance = None


def require_api_key(f):
    """API Key认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not API_KEY_REQUIRED:
            return f(*args, **kwargs)
        
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            logger.warning(f"未提供API Key - IP: {request.remote_addr}")
            return jsonify({"error": "API Key required", "message": "请在请求头中提供 X-API-Key"}), 401
        
        if api_key not in API_KEYS:
            logger.warning(f"无效的API Key - IP: {request.remote_addr}, Key: {api_key[:8]}...")
            return jsonify({"error": "Invalid API Key", "message": "无效的API密钥"}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_db_connection():
    """获取数据库连接"""
    try:
        if _db_instance:
            return _db_instance.get_connection()
        else:
            return sqlite3.connect(DATABASE_PATH, timeout=10.0)
    except Exception as e:
        logger.error(f"获取数据库连接失败: {e}")
        raise


def query_one(sql, params=()):
    """执行单行查询"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"查询失败: {sql}, 错误: {e}")
        raise


def query_all(sql, params=()):
    """执行多行查询"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"查询失败: {sql}, 错误: {e}")
        raise


@app.before_request
def log_request():
    """记录请求日志"""
    logger.info(f"{request.method} {request.path} - IP: {request.remote_addr}")


@app.after_request
def log_response(response):
    """记录响应日志"""
    logger.info(f"{request.method} {request.path} - Status: {response.status_code}")
    return response


@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({"error": "Not Found", "message": "请求的资源不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    logger.error(f"服务器内部错误: {error}", exc_info=True)
    return jsonify({"error": "Internal Server Error", "message": "服务器内部错误"}), 500


@app.get('/')
def index():
    """API根路径"""
    return jsonify({
        "status": "ok",
        "service": "packing-system-api",
        "version": "2.0",
        "auth_required": API_KEY_REQUIRED
    })


@app.get('/api/health')
def health_check():
    """健康检查接口"""
    try:
        # 测试数据库连接
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({"status": "unhealthy", "database": "error", "message": str(e)}), 503


@app.get('/api/search')
@require_api_key
def search():
    """搜索接口
    
    查询参数:
        code: 要搜索的编码（板件编码/包裹号/托盘号）
    
    返回:
        JSON对象，包含搜索结果
    """
    code = (request.args.get('code') or '').strip()
    if not code:
        return jsonify({"error": "Missing parameter", "message": "参数 code 是必需的"}), 400

    try:
        # Search component by component_code
        comp = query_one(
            '''SELECT c.*, o.order_number, o.customer_address 
               FROM components c 
               LEFT JOIN orders o ON c.order_id = o.id 
               WHERE c.component_code = ?''', (code,)
        )
        if comp:
            logger.info(f"找到板件: {code}")
            return jsonify({"ok": True, "type": "component", "data": comp})

        # Search package by package_number
        pkg = query_one(
            '''SELECT pk.*, o.order_number, o.customer_address, pal.pallet_number 
               FROM packages pk 
               LEFT JOIN orders o ON pk.order_id = o.id 
               LEFT JOIN pallets pal ON pk.pallet_id = pal.id 
               WHERE pk.package_number = ?''', (code,)
        )
        if pkg:
            logger.info(f"找到包裹: {code}")
            return jsonify({"ok": True, "type": "package", "data": pkg})

        # Search pallet by pallet_number
        pal = query_one(
            '''SELECT p.*, o.order_number, o.customer_address 
               FROM pallets p 
               LEFT JOIN orders o ON p.order_id = o.id 
               WHERE p.pallet_number = ?''', (code,)
        )
        if pal:
            logger.info(f"找到托盘: {code}")
            return jsonify({"ok": True, "type": "pallet", "data": pal})

        logger.info(f"未找到: {code}")
        return jsonify({"ok": False, "error": "not found", "message": "未找到匹配的记录"})
        
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        return jsonify({"error": "Database error", "message": str(e)}), 500


def run_server():
    """启动服务器"""
    logger.info(f"启动API服务器 - 主机: {API_HOST}, 端口: {API_PORT}, 调试模式: {API_DEBUG}")
    logger.info(f"API认证: {'启用' if API_KEY_REQUIRED else '禁用'}")
    
    if API_KEY_REQUIRED and API_KEYS:
        logger.info("已配置的API Keys:")
        for i, key in enumerate(API_KEYS, 1):
            logger.info(f"  Key {i}: {key[:8]}...{key[-4:]}")
    
    app.run(host=API_HOST, port=API_PORT, debug=API_DEBUG)


if __name__ == '__main__':
    run_server()
