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

import json
import sys
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List
import argparse

from config import get_config

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


# ==================== 工具函数 ====================

def get_data_dir() -> Path:
    """获取数据目录"""
    data_dir = get_config().get_path("tasks_dir")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_log_dir() -> Path:
    """获取日志目录"""
    log_dir = get_config().get_path("logs_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_decision_dir() -> Path:
    """获取决策目录"""
    decision_dir = get_config().get_path("decisions_dir")
    decision_dir.mkdir(parents=True, exist_ok=True)
    return decision_dir


def log_operation(operation: str, task_id: str, details: Dict):
    """记录操作日志"""
    log_file = get_log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "task_id": task_id,
        "details": details
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def load_task(task_id: str) -> Optional[Dict]:
    """加载任务（带文件锁）"""
    task_file = get_data_dir() / f"{task_id}.json"
    if not task_file.exists():
        return None

    with open(task_file, "r", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            return json.load(f)


def save_task(task: Dict):
    """保存任务（带文件锁）"""
    task_file = get_data_dir() / f"{task['task_id']}.json"

    with open(task_file, "w", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(task, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            json.dump(task, f, ensure_ascii=False, indent=2)


def generate_task_id() -> str:
    """生成任务ID"""
    existing_tasks = list(get_data_dir().glob("T*.json"))
    if not existing_tasks:
        return "T001"

    max_id = max([int(t.stem[1:]) for t in existing_tasks])
    return f"T{max_id + 1:03d}"


# ==================== 核心功能 ====================

def create_task(title: str, ceo_input: str) -> str:
    """创建任务"""
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

    save_task(task)
    log_operation("create", task_id, {"title": title})

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "message": f"任务 {task_id} 创建成功"
    }, ensure_ascii=False))

    return task_id


def assess_task(task_id: str, level: str, reason: str):
    """任务定级"""
    task = load_task(task_id)
    if not task:
        print(json.dumps({"success": False, "error": f"任务 {task_id} 不存在"}, ensure_ascii=False))
        return

    if task["state"] != TaskState.CREATED.value:
        print(json.dumps({"success": False, "error": f"任务状态必须是 created，当前是 {task['state']}"}, ensure_ascii=False))
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

    save_task(task)
    log_operation("assess", task_id, {"level": level, "reason": reason})

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "level": level,
        "message": f"任务 {task_id} 定级为 {level}"
    }, ensure_ascii=False))


def transition_state(task_id: str, to_state: str, actor: str):
    """状态流转"""
    task = load_task(task_id)
    if not task:
        print(json.dumps({"success": False, "error": f"任务 {task_id} 不存在"}, ensure_ascii=False))
        return

    from_state = task["state"]

    # 验证状态转换是否合法
    if to_state not in [s.value for s in STATE_TRANSITIONS.get(TaskState(from_state), [])]:
        print(json.dumps({
            "success": False,
            "error": f"非法状态转换: {from_state} -> {to_state}"
        }, ensure_ascii=False))
        return

    # L3 任务完成前必须有决策履历
    if to_state == TaskState.COMPLETED.value and task.get("level") == TaskLevel.L3.value:
        decisions = list(get_decision_dir().glob(f"{task_id}_*.json"))
        if not decisions:
            print(json.dumps({
                "success": False,
                "error": "L3 任务必须创建决策履历才能完成"
            }, ensure_ascii=False))
            return

    task["state"] = to_state
    task["updated_at"] = datetime.now().isoformat()
    task["actors"].append({
        "actor": actor,
        "action": f"状态流转: {from_state} -> {to_state}",
        "timestamp": datetime.now().isoformat()
    })

    save_task(task)
    log_operation("transition", task_id, {"from": from_state, "to": to_state, "actor": actor})

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "from_state": from_state,
        "to_state": to_state,
        "message": f"任务 {task_id} 状态已更新"
    }, ensure_ascii=False))


def report_progress(task_id: str, message: str, progress: int):
    """上报进度"""
    task = load_task(task_id)
    if not task:
        print(json.dumps({"success": False, "error": f"任务 {task_id} 不存在"}, ensure_ascii=False))
        return

    task["progress"] = progress
    task["updated_at"] = datetime.now().isoformat()
    task["progress_log"].append({
        "message": message,
        "progress": progress,
        "timestamp": datetime.now().isoformat()
    })

    save_task(task)
    log_operation("progress", task_id, {"message": message, "progress": progress})

    # 生成进度条
    bar_length = 10
    filled = int(bar_length * progress / 100)
    bar = "▓" * filled + "░" * (bar_length - filled)

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "progress": progress,
        "bar": f"{bar} {progress}%",
        "message": message
    }, ensure_ascii=False))


def get_status(task_id: str):
    """查询任务状态"""
    task = load_task(task_id)
    if not task:
        print(json.dumps({"success": False, "error": f"任务 {task_id} 不存在"}, ensure_ascii=False))
        return

    # 检查 SLA
    created_at = datetime.fromisoformat(task["created_at"])
    elapsed = datetime.now() - created_at
    level = TaskLevel(task["level"]) if task["level"] else None
    sla_limit = SLA_LIMITS.get(level) if level else None
    sla_status = "正常"

    if sla_limit and elapsed > sla_limit:
        if elapsed > sla_limit * 2:
            sla_status = "严重超期"
        else:
            sla_status = "超期"

    print(json.dumps({
        "success": True,
        "task": task,
        "elapsed_minutes": int(elapsed.total_seconds() / 60),
        "sla_status": sla_status
    }, ensure_ascii=False, indent=2))


def check_sla(task_id: str):
    """检查 SLA 并自动升级"""
    task = load_task(task_id)
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
        task["state"] = TaskState.ESCALATED.value
        task["updated_at"] = datetime.now().isoformat()
        task["actors"].append({
            "actor": "System",
            "action": "自动升级",
            "reason": f"SLA 超期 {int(elapsed.total_seconds() / 60)} 分钟",
            "timestamp": datetime.now().isoformat()
        })
        save_task(task)
        log_operation("escalate", task_id, {"reason": "SLA超期"})

        print(json.dumps({
            "success": True,
            "task_id": task_id,
            "action": "escalated",
            "message": f"任务 {task_id} 因 SLA 超期已自动升级"
        }, ensure_ascii=False))


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
