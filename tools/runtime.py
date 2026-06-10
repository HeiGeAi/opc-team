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
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict

from config import get_config

# In-process serialisation. fcntl.flock() guards cross-process access but its
# behaviour for separate file descriptors held by threads in the same process
# is platform-dependent (observed flaky on macOS / Python 3.9). The thread lock
# below covers the within-process case so reserve_id() is safe under both
# threading and multi-process load.
_counter_thread_locks: Dict[str, threading.Lock] = {}
_counter_thread_locks_guard = threading.Lock()


def _get_counter_thread_lock(counter_type: str) -> threading.Lock:
    with _counter_thread_locks_guard:
        lock = _counter_thread_locks.get(counter_type)
        if lock is None:
            lock = threading.Lock()
            _counter_thread_locks[counter_type] = lock
        return lock

HAS_FILELOCK = False
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        import filelock
        HAS_FILELOCK = True
    except ImportError:
        HAS_FILELOCK = False


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
    raise SystemExit(1)


def lock_file(file_obj, shared: bool = False):
    """跨平台文件锁。"""
    if HAS_FCNTL:
        lock_type = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(file_obj.fileno(), lock_type)
    elif HAS_FILELOCK:
        import filelock
        lock_path = str(file_obj.name) + ".lock"
        lock = filelock.FileLock(lock_path)
        lock.acquire()
        setattr(file_obj, "_opc_lock", lock)


def unlock_file(file_obj):
    """跨平台解锁。"""
    if HAS_FCNTL:
        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
    elif HAS_FILELOCK:
        lock = getattr(file_obj, "_opc_lock", None)
        if lock is not None:
            lock.release()
            delattr(file_obj, "_opc_lock")


@contextmanager
def operation_lock(lock_path: Path):
    """对一段读-改-写操作加锁，避免单独 load/save 锁导致更新丢失。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as f:
        lock_file(f)
        try:
            yield
        finally:
            unlock_file(f)


# ==================== 只读模式检查 ====================

def require_writable(operation: str = "操作") -> bool:
    """检查是否允许写操作，只读模式下拒绝。

    兼容两种配置写法：推荐的 features.readonly_mode 和顶层 readonly_mode。
    """
    config = get_config()
    if config.get("features.readonly_mode", False) or config.get("readonly_mode", False):
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
    原子方式预留 ID，避免并发冲突。

    双层锁：
    - 进程内：threading.Lock 保证同一进程多线程串行。
    - 进程间：fcntl.flock / filelock 保证多进程串行。
    单独靠文件锁不够，因为 flock 的同进程多 FD 语义在 macOS / Python 3.9
    下表现不一致，会造成 ID 撞号（见 CI #1 失败）。

    所有读-改-写包括初始化必须在锁内完成，否则未初始化的线程会用 "0"
    覆盖已被其他线程推进的计数器。
    """
    counter_file = get_counter_path(counter_type)

    with _get_counter_thread_lock(counter_type):
        # 以 a+ 模式打开：文件不存在则创建，存在则保留内容，FD 起始在末尾。
        # seek(0) 之后按 r+ 的方式读-改-写。
        with open(counter_file, "a+", encoding="utf-8") as f:
            lock_file(f)
            try:
                f.seek(0)
                raw = f.read().strip()
                current = int(raw) if raw else 0
                next_id = current + 1
                f.seek(0)
                f.truncate()
                f.write(str(next_id))
                f.flush()
            finally:
                unlock_file(f)

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


def generate_assignment_id() -> str:
    """生成派发任务 ID"""
    return reserve_id("A", "assignments")


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
