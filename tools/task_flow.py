#!/usr/bin/env python3
"""
task_flow.py - OPC Team 任务状态机

功能：
- 创建任务
- 任务定级（L1/L2/L3/L4）
- 状态流转（状态机约束）
- 进度上报
- SLA 检查与自动升级
"""

from datetime import datetime, timedelta
from enum import Enum
import argparse

from config import get_config
from runtime import (
    emit_json, emit_error, require_writable,
    generate_task_id, log_operation
)
from storage import get_storage


# ==================== 枚举定义 ====================

class TaskLevel(str, Enum):
    L1 = "L1_SIMPLE"
    L2 = "L2_JUDGMENT"
    L3 = "L3_STRATEGY"
    L4 = "L4_DEBATE"


class TaskState(str, Enum):
    CREATED = "created"
    ASSESSED = "assessed"
    IN_STRATEGY = "in_strategy"
    IN_EXECUTION = "in_execution"
    IN_DEBATE = "in_debate"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


# ==================== 状态转换规则 ====================

STATE_TRANSITIONS = {
    TaskState.CREATED: [TaskState.ASSESSED],
    TaskState.ASSESSED: [TaskState.IN_EXECUTION, TaskState.IN_STRATEGY, TaskState.IN_DEBATE],
    TaskState.IN_STRATEGY: [TaskState.IN_EXECUTION, TaskState.BLOCKED],
    TaskState.IN_EXECUTION: [TaskState.COMPLETED, TaskState.BLOCKED, TaskState.ESCALATED],
    TaskState.IN_DEBATE: [TaskState.IN_EXECUTION, TaskState.BLOCKED],
    TaskState.BLOCKED: [TaskState.IN_STRATEGY, TaskState.IN_EXECUTION, TaskState.ESCALATED],
}

# SLA 时间限制
SLA_LIMITS = {
    TaskLevel.L1: timedelta(minutes=5),
    TaskLevel.L2: timedelta(minutes=30),
    TaskLevel.L3: timedelta(hours=2),
    TaskLevel.L4: timedelta(hours=4),
}


# ==================== 核心功能 ====================

def create_task(title: str, ceo_input: str) -> str:
    """创建任务"""
    if not require_writable("创建任务"):
        return ""

    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task_id = generate_task_id()

    task = {
        "task_id": task_id,
        "title": title,
        "ceo_input": ceo_input,
        "level": None,
        "state": TaskState.CREATED.value,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "actors": [],
        "progress": 0,
        "progress_log": []
    }

    storage.save(task_id, task)
    log_operation("create", task_id, "task", {"title": title})

    emit_json(True, task_id=task_id, message=f"任务 {task_id} 创建成功")
    return task_id


def assess_task(task_id: str, level: str, reason: str):
    """任务定级"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task = storage.load(task_id)
    if not task:
        emit_error(f"任务 {task_id} 不存在")
        return

    if task["state"] != TaskState.CREATED.value:
        emit_error(f"任务状态必须是 created，当前是 {task['state']}")
        return

    if not require_writable("任务定级"):
        return

    # 标准化 level 格式
    level_map = {
        "L1": TaskLevel.L1.value,
        "L2": TaskLevel.L2.value,
        "L3": TaskLevel.L3.value,
        "L4": TaskLevel.L4.value,
    }
    task["level"] = level_map.get(level, level)
    task["state"] = TaskState.ASSESSED.value
    task["updated_at"] = datetime.now().isoformat()
    task["actors"].append({
        "role": "COO",
        "name": "魏明远",
        "action": "定级",
        "level": level,
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })

    storage.save(task_id, task)
    log_operation("assess", task_id, "task", {"level": level, "reason": reason})

    emit_json(True, task_id=task_id, level=level, message=f"任务 {task_id} 定级为 {level}")


def transition_state(task_id: str, to_state: str, actor: str):
    """状态流转"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task = storage.load(task_id)
    if not task:
        emit_error(f"任务 {task_id} 不存在")
        return

    from_state = task["state"]

    # 验证状态转换是否合法
    if to_state not in [s.value for s in STATE_TRANSITIONS.get(TaskState(from_state), [])]:
        emit_error(f"非法状态转换: {from_state} -> {to_state}")
        return

    # L3 任务完成前必须有决策履历
    if to_state == TaskState.COMPLETED.value and task.get("level") == TaskLevel.L3.value:
        decision_storage = get_storage("decisions", {
            "backend": config.get("storage.backend", "file"),
            "base_dir": config.get_path("decisions_dir")
        })
        task_decisions = decision_storage.list(f"{task_id}_D*")
        if not task_decisions:
            emit_error("L3 任务必须创建决策履历才能完成")
            return

    if not require_writable("状态流转"):
        return

    task["state"] = to_state
    task["updated_at"] = datetime.now().isoformat()
    task["actors"].append({
        "actor": actor,
        "action": f"状态流转: {from_state} -> {to_state}",
        "timestamp": datetime.now().isoformat()
    })

    storage.save(task_id, task)
    log_operation("transition", task_id, "task", {"from": from_state, "to": to_state, "actor": actor})

    # 如果开启了 auto_sync_memory 且任务完成，同步到 MEMORY.md
    if to_state == TaskState.COMPLETED.value and config.get("features.auto_sync_memory", False):
        try:
            from memory_sync import sync_to_memory_md
            sync_to_memory_md(task_id)
        except Exception:
            pass  # 忽略同步失败

    emit_json(True, task_id=task_id, from_state=from_state, to_state=to_state, message=f"任务 {task_id} 状态已更新")


def report_progress(task_id: str, message: str, progress: int):
    """上报进度"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task = storage.load(task_id)
    if not task:
        emit_error(f"任务 {task_id} 不存在")
        return

    if not require_writable("进度上报"):
        return

    task["progress"] = progress
    task["updated_at"] = datetime.now().isoformat()
    task["progress_log"].append({
        "message": message,
        "progress": progress,
        "timestamp": datetime.now().isoformat()
    })

    storage.save(task_id, task)
    log_operation("progress", task_id, "task", {"message": message, "progress": progress})

    # 生成进度条
    bar_length = 10
    filled = int(bar_length * progress / 100)
    bar = "▓" * filled + "░" * (bar_length - filled)

    emit_json(True, task_id=task_id, progress=progress, bar=f"{bar} {progress}%", message=message)


def get_status(task_id: str):
    """查询任务状态"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task = storage.load(task_id)
    if not task:
        emit_error(f"任务 {task_id} 不存在")
        return

    # SLA 检查
    created_at = datetime.fromisoformat(task["created_at"])
    elapsed = datetime.now() - created_at
    level = TaskLevel(task["level"]) if task["level"] else None
    sla_limit = SLA_LIMITS.get(level) if level else None
    sla_status = "正常"

    if config.get("features.sla_check_enabled", True) and sla_limit:
        if elapsed > sla_limit:
            if elapsed > sla_limit * 2:
                sla_status = "严重超期"
            else:
                sla_status = "超期"

    emit_json(True, task=task, elapsed_minutes=int(elapsed.total_seconds() / 60), sla_status=sla_status)


def check_sla(task_id: str):
    """检查 SLA 并自动升级"""
    config = get_config()

    if not config.get("features.sla_check_enabled", True):
        return

    backend = config.get("storage.backend", "file")
    storage = get_storage("tasks", {"backend": backend, "base_dir": config.get_path("tasks_dir")})

    task = storage.load(task_id)
    if not task:
        return

    if task["state"] in [TaskState.COMPLETED.value, TaskState.ESCALATED.value]:
        return

    created_at = datetime.fromisoformat(task["created_at"])
    elapsed = datetime.now() - created_at
    level = TaskLevel(task["level"]) if task["level"] else None

    if not level:
        return

    sla_limit = SLA_LIMITS[level]

    if elapsed > sla_limit * 2:
        # 超期 2 倍，自动升级
        if not require_writable("SLA 自动升级"):
            return

        task["state"] = TaskState.ESCALATED.value
        task["updated_at"] = datetime.now().isoformat()
        task["actors"].append({
            "actor": "System",
            "action": "自动升级",
            "reason": f"SLA 超期 {int(elapsed.total_seconds() / 60)} 分钟",
            "timestamp": datetime.now().isoformat()
        })
        storage.save(task_id, task)
        log_operation("escalate", task_id, "task", {"reason": "SLA超期"})

        emit_json(True, task_id=task_id, action="escalated", message=f"任务 {task_id} 因 SLA 超期已自动升级")


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="OPC Team 任务状态机")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # create
    create_parser = subparsers.add_parser("create", help="创建任务")
    create_parser.add_argument("--title", required=True, help="任务标题")
    create_parser.add_argument("--ceo-input", required=True, help="CEO 输入")

    # assess
    assess_parser = subparsers.add_parser("assess", help="任务定级")
    assess_parser.add_argument("--task-id", required=True, help="任务ID")
    assess_parser.add_argument("--level", required=True, choices=["L1", "L2", "L3", "L4"], help="任务级别")
    assess_parser.add_argument("--reason", required=True, help="定级原因")

    # transition
    transition_parser = subparsers.add_parser("transition", help="状态流转")
    transition_parser.add_argument("--task-id", required=True, help="任务ID")
    transition_parser.add_argument("--to", required=True, help="目标状态")
    transition_parser.add_argument("--actor", required=True, help="操作者")

    # progress
    progress_parser = subparsers.add_parser("progress", help="上报进度")
    progress_parser.add_argument("--task-id", required=True, help="任务ID")
    progress_parser.add_argument("--message", required=True, help="进度消息")
    progress_parser.add_argument("--progress", type=int, required=True, help="进度百分比")

    # status
    status_parser = subparsers.add_parser("status", help="查询状态")
    status_parser.add_argument("--task-id", required=True, help="任务ID")

    # check-sla
    sla_parser = subparsers.add_parser("check-sla", help="检查SLA")
    sla_parser.add_argument("--task-id", required=True, help="任务ID")

    args = parser.parse_args()

    if args.command == "create":
        create_task(args.title, args.ceo_input)
    elif args.command == "assess":
        assess_task(args.task_id, args.level, args.reason)
    elif args.command == "transition":
        transition_state(args.task_id, args.to, args.actor)
    elif args.command == "progress":
        report_progress(args.task_id, args.message, args.progress)
    elif args.command == "status":
        get_status(args.task_id)
    elif args.command == "check-sla":
        check_sla(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
