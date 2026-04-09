#!/usr/bin/env python3
"""
runtime.py - OPC Team 统一运行时

功能：
- 统一的 JSON 输出
- 统一的错误处理
- 只读模式检查
- 原子 ID 生成
- 统一日志
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from config import get_config

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


# ==================== 统一输出 ====================

def emit_json(success: bool, **kwargs) -> None:
    """统一 JSON 输出"""
    result = {"success": success}
    result.update(kwargs)
    print(json.dumps(result, ensure_ascii=False))


def emit_error(message: str, **kwargs) -> None:
    """统一错误输出"""
    result = {"success": False, "error": message}
    result.update(kwargs)
    print(json.dumps(result, ensure_ascii=False))


# ==================== 只读模式检查 ====================

def require_writable(operation: str = "操作") -> bool:
    """检查是否允许写操作，只读模式下拒绝"""
    config = get_config()
    if config.get("features.readonly_mode", False):
        emit_error(f"{operation}在只读模式下被拒绝（readonly_mode=true）")
        return False
    return True


# ==================== 原子 ID 生成 ====================

def get_counter_path(counter_type: str) -> Path:
    """获取计数器文件路径"""
    config = get_config()
    data_dir = config.get_path("data_dir")
    counter_dir = data_dir / ".counters"
    counter_dir.mkdir(parents=True, exist_ok=True)
    return counter_dir / f"{counter_type}_counter"


def reserve_id(prefix: str, counter_type: str) -> str:
    """
    原子方式预留 ID，避免并发冲突

    使用文件锁保证原子性：
    1. 锁定计数器文件
    2. 读取当前值
    3. +1 后写回
    4. 解锁
    """
    counter_file = get_counter_path(counter_type)

    # 初始化计数器文件
    if not counter_file.exists():
        with open(counter_file, "w") as f:
            f.write("0")

    # 原子递增
    with open(counter_file, "r+") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            current = int(f.read().strip() or "0")
            next_id = current + 1
            f.seek(0)
            f.write(str(next_id))
            f.truncate()
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return f"{prefix}{next_id:03d}"


def generate_task_id() -> str:
    """生成任务 ID"""
    return reserve_id("T", "tasks")


def generate_decision_id() -> str:
    """生成决策 ID"""
    return reserve_id("D", "decisions")


def generate_risk_id() -> str:
    """生成风险 ID"""
    return reserve_id("R", "risks")


# ==================== 统一日志 ====================

def get_log_dir() -> Path:
    """获取日志目录"""
    config = get_config()
    log_dir = config.get_path("logs_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_operation(operation: str, entity_id: str, entity_type: str, details: Dict) -> None:
    """
    统一日志记录

    Args:
        operation: 操作类型 (create, update, delete, transition, etc.)
        entity_id: 实体 ID (task_id, decision_id, risk_id)
        entity_type: 实体类型 (task, decision, risk)
        details: 详细信息
    """
    log_file = get_log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ==================== 存储接口 ====================

def get_storage_path(entity_type: str) -> Path:
    """获取实体存储目录"""
    config = get_config()
    type_to_key = {
        "task": "tasks_dir",
        "decision": "decisions_dir",
        "risk": "risks_dir",
        "memory": "memory_dir"
    }
    key = type_to_key.get(entity_type)
    if not key:
        raise ValueError(f"未知实体类型: {entity_type}")
    return config.get_path(key)


def save_entity(entity_type: str, entity_id: str, data: Dict) -> None:
    """
    统一保存实体

    Args:
        entity_type: 实体类型 (task, decision, risk)
        entity_id: 实体 ID
        data: 实体数据（必须包含 entity_id）
    """
    if not require_writable(f"保存{entity_type}"):
        return

    storage_dir = get_storage_path(entity_type)
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_path = storage_dir / f"{entity_id}.json"

    with open(file_path, "w", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_entity(entity_type: str, entity_id: str) -> Optional[Dict]:
    """
    统一加载实体

    Args:
        entity_type: 实体类型
        entity_id: 实体 ID

    Returns:
        实体数据或 None
    """
    storage_dir = get_storage_path(entity_type)
    file_path = storage_dir / f"{entity_id}.json"

    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def list_entities(entity_type: str) -> list:
    """
    列出所有实体

    Args:
        entity_type: 实体类型

    Returns:
        实体 ID 列表
    """
    storage_dir = get_storage_path(entity_type)
    if not storage_dir.exists():
        return []

    files = list(storage_dir.glob("*.json"))
    return sorted([f.stem for f in files])


def delete_entity(entity_type: str, entity_id: str) -> bool:
    """
    删除实体

    Args:
        entity_type: 实体类型
        entity_id: 实体 ID

    Returns:
        是否删除成功
    """
    if not require_writable(f"删除{entity_type}"):
        return False

    storage_dir = get_storage_path(entity_type)
    file_path = storage_dir / f"{entity_id}.json"

    if file_path.exists():
        file_path.unlink()
        return True
    return False
