"""
改进功能测试脚本

测试新添加的功能是否正常工作
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_logging():
    """测试日志功能"""
    print("测试1: 日志系统...")
    try:
        from utils.logging_config import AppLogger, get_logger
        
        logger = get_logger('Test')
        logger.info("这是一条测试日志")
        logger.warning("这是一条警告")
        logger.error("这是一条错误日志")
        
        print("✓ 日志系统正常")
        return True
    except Exception as e:
        print(f"✗ 日志系统失败: {e}")
        return False


def test_database():
    """测试数据库功能"""
    print("\n测试2: 数据库连接...")
    try:
        from database import db
        
        # 测试连接
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        conn.close()
        
        assert result[0] == 1, "查询结果不正确"
        
        # 测试上下文管理器
        with db.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result[0] == 1, "上下文管理器查询结果不正确"
        
        print("✓ 数据库连接正常")
        print("✓ 上下文管理器正常")
        return True
    except Exception as e:
        print(f"✗ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handler():
    """测试错误处理"""
    print("\n测试3: 错误处理...")
    try:
        from utils.error_handler import ErrorHandler, AppError, DatabaseError
        
        # 测试自定义异常
        try:
            raise DatabaseError("测试数据库错误", user_message="这是用户看到的消息")
        except DatabaseError as e:
            assert str(e) == "测试数据库错误"
            assert e.user_message == "这是用户看到的消息"
        
        print("✓ 错误处理正常")
        return True
    except Exception as e:
        print(f"✗ 错误处理测试失败: {e}")
        return False


def test_transaction():
    """测试事务管理"""
    print("\n测试4: 事务管理...")
    try:
        from utils.transaction import transaction, TransactionManager
        from database import db
        
        # 测试事务上下文管理器
        with transaction(db_getter=lambda: db.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result[0] == 1
        
        # 测试TransactionManager
        tm = TransactionManager(db)
        try:
            tm.begin()
            cursor = tm.connection.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result[0] == 1
            tm.commit()
        except:
            tm.rollback()
            raise
        
        print("✓ 事务上下文管理器正常")
        print("✓ TransactionManager正常")
        return True
    except Exception as e:
        print(f"✗ 事务管理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置模块"""
    print("\n测试5: 配置模块...")
    try:
        from config import DATABASE_PATH, API_HOST, API_PORT
        
        assert DATABASE_PATH is not None, "数据库路径未配置"
        assert API_HOST is not None, "API主机未配置"
        assert API_PORT > 0, "API端口无效"
        
        print(f"  数据库路径: {DATABASE_PATH}")
        print(f"  API地址: {API_HOST}:{API_PORT}")
        print("✓ 配置模块正常")
        return True
    except Exception as e:
        print(f"✗ 配置模块测试失败: {e}")
        return False


def test_database_indices():
    """测试数据库索引"""
    print("\n测试6: 数据库索引...")
    try:
        from database import db
        
        with db.connection_context() as conn:
            cursor = conn.cursor()
            
            # 检查索引是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = [row[0] for row in cursor.fetchall()]
            
            expected_indices = [
                'idx_packages_order_status_created',
                'idx_components_package_id',
                'idx_pallets_pallet_number'
            ]
            
            for index in expected_indices:
                if index in indices:
                    print(f"  ✓ 索引 {index} 存在")
                else:
                    print(f"  ✗ 索引 {index} 不存在")
            
        print("✓ 数据库索引检查完成")
        return True
    except Exception as e:
        print(f"✗ 数据库索引测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("="*60)
    print("开始测试改进功能...")
    print("="*60)
    
    tests = [
        test_logging,
        test_database,
        test_error_handler,
        test_transaction,
        test_config,
        test_database_indices
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "="*60)
    print("测试总结:")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！")
        return 0
    else:
        print(f"\n✗ 有 {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
