from typing import Optional

# 统一的状态常量（内部使用英文，界面显示为中文）
PACKAGE_STATUS = {"open", "completed", "sealed"}
PALLET_STATUS = {"open", "sealed", "closed"}
COMPONENT_STATUS = {"pending", "packaged"}


def normalize_package_status(status: Optional[str]) -> str:
    """将数据库/旧代码中的别名统一为标准枚举。
    - 将 'packed' 统一为 'sealed'
    - 其余保持原值（空值返回 'open' 作为退化默认）
    """
    if not status:
        return "open"
    s = str(status).strip().lower()
    if s == "packed":
        return "sealed"
    return s


def package_status_cn(status: Optional[str]) -> str:
    """包裹状态中文显示。"""
    s = normalize_package_status(status)
    mapping = {
        "open": "进行中",
        "completed": "已完成",
        "sealed": "已封包",
    }
    return mapping.get(s, s or "未设置")


def pallet_status_cn(status: Optional[str]) -> str:
    """托盘状态中文显示。"""
    s = (str(status).strip().lower() if status else "")
    mapping = {
        "open": "开放",
        "sealed": "已封托",
        "closed": "已关闭",
    }
    return mapping.get(s, s or "未设置")


def component_status_cn(status: Optional[str]) -> str:
    """板件状态中文显示。"""
    s = (str(status).strip().lower() if status else "")
    mapping = {
        "pending": "待包",
        "packaged": "已入包",
    }
    return mapping.get(s, s or "未设置")