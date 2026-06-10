#!/usr/bin/env python3
"""
decision_log.py - OPC Team 决策履历管理

功能：
- 创建决策履历（#D{seq}）
- 记录假设清单
- 更新假设验证状态
- 回填决策结果
- 触发假设证伪重审
"""

import re
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import argparse

from config import get_config
from runtime import (
    emit_json, emit_error, require_writable,
    generate_decision_id, log_operation
)
from storage import get_storage


# ID 白名单：只允许字母、数字、下划线、连字符。
# 路径分隔符（/）会让存储键落到错误位置导致数据丢失；
# glob 元字符（* ? [ ]）会让按 ID 查找时跨界匹配。
VALID_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_id(value: Optional[str], field: str) -> str:
    """校验 ID 输入，含非法字符直接报错退出。"""
    value = (value or "").strip()
    if not VALID_ID_PATTERN.match(value):
        emit_error(f"{field} 含非法字符，只允许字母、数字、下划线、连字符: {value!r}")
    return value


def parse_assumptions(assumptions_str: str) -> List[Dict]:
    """解析假设字符串。

    格式: "标签1:描述1,标签2:描述2"。
    带冒号的条目取冒号后的内容作为描述；
    不带冒号的条目作为无标签假设原样收录，不会被静默丢弃。
    """
    assumptions = []
    for item in assumptions_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            _, desc = item.split(":", 1)
            desc = desc.strip() or item
        else:
            desc = item
        assumptions.append({
            "id": len(assumptions) + 1,
            "description": desc,
            "status": "未验证",
            "actual": None,
            "verified_at": None
        })
    return assumptions


def load_decision_by_id(
    storage,
    decision_id: str,
    task_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[Dict]]:
    """按决策 ID 查找存储键和内容。

    指定 task_id 时严格限定该任务下的决策；
    未指定时如果多个任务下存在同名决策 ID，报错并列出候选。
    """
    if task_id:
        key = f"{task_id}_{decision_id}"
        decision = storage.load(key)
        if decision:
            return key, decision
        return None, None

    matches = []
    for key in sorted(storage.list(f"*_{decision_id}")):
        decision = storage.load(key)
        if decision:
            matches.append((key, decision))

    if len(matches) > 1:
        candidates = ", ".join(key for key, _ in matches)
        emit_error(f"决策 {decision_id} 在多个任务下存在，请加 --task-id 指定。候选: {candidates}")
    if matches:
        return matches[0]
    return None, None


# ==================== 核心功能 ====================

def create_decision(
    task_id: str,
    decision_id: Optional[str],
    title: str,
    options: str,
    chosen: str,
    reason: str,
    assumptions: str,
    force: bool = False
):
    """创建决策履历"""
    if not require_writable("创建决策"):
        return

    task_id = validate_id(task_id, "task-id")
    if decision_id:
        decision_id = validate_id(decision_id, "decision-id")
    else:
        decision_id = generate_decision_id()

    decision = {
        "decision_id": decision_id,
        "task_id": task_id,
        "title": title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "options": options,
        "chosen": chosen,
        "reason": reason,
        "assumptions": parse_assumptions(assumptions),
        "result": None,
        "backfilled_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # 使用 task_id_decision_id 作为存储键
    storage_key = f"{task_id}_{decision_id}"
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    if storage.exists(storage_key) and not force:
        emit_error(f"决策 {decision_id} 在任务 {task_id} 下已存在，如需覆盖请加 --force")
        return

    storage.save(storage_key, decision)

    log_operation("create", decision_id, "decision", {"task_id": task_id, "title": title})

    emit_json(True, decision_id=decision_id, task_id=task_id, message=f"决策履历 #{decision_id} 创建成功", assumptions_count=len(decision["assumptions"]))


def update_assumption(
    decision_id: str,
    assumption_id: int,
    status: str,
    actual: Optional[str] = None,
    trigger_review: bool = False,
    task_id: Optional[str] = None
):
    """更新假设验证状态"""
    decision_id = validate_id(decision_id, "decision-id")
    if task_id:
        task_id = validate_id(task_id, "task-id")

    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    decision_key, decision = load_decision_by_id(storage, decision_id, task_id=task_id)

    if not decision:
        emit_error(f"决策 {decision_id} 不存在")
        return

    # 查找假设
    assumption = next((a for a in decision["assumptions"] if a["id"] == assumption_id), None)
    if not assumption:
        emit_error(f"假设 {assumption_id} 不存在")
        return

    if not require_writable("更新假设"):
        return

    assumption["status"] = status
    assumption["actual"] = actual
    assumption["verified_at"] = datetime.now().isoformat()

    decision["updated_at"] = datetime.now().isoformat()
    storage.save(decision_key, decision)

    log_operation("update_assumption", decision_id, "decision", {
        "assumption_id": assumption_id,
        "status": status,
        "trigger_review": trigger_review
    })

    result_data = {
        "decision_id": decision_id,
        "assumption_id": assumption_id,
        "status": status,
        "message": f"假设 {assumption_id} 状态更新为 {status}"
    }

    if trigger_review:
        result_data["alert"] = "⚠️ 假设被证伪，必须在48小时内重新评估决策"
        result_data["action_required"] = "调用 task_flow.py 创建重审任务"

    emit_json(True, **result_data)


def backfill_result(
    decision_id: str,
    result: str,
    metrics: Optional[str] = None,
    lessons: Optional[str] = None,
    task_id: Optional[str] = None
):
    """回填决策结果"""
    decision_id = validate_id(decision_id, "decision-id")
    if task_id:
        task_id = validate_id(task_id, "task-id")

    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    decision_key, decision = load_decision_by_id(storage, decision_id, task_id=task_id)

    if not decision:
        emit_error(f"决策 {decision_id} 不存在")
        return

    if not require_writable("回填结果"):
        return

    decision["result"] = {
        "outcome": result,
        "metrics": metrics,
        "lessons": lessons,
        "backfilled_at": datetime.now().isoformat()
    }
    decision["backfilled_at"] = datetime.now().isoformat()
    decision["updated_at"] = datetime.now().isoformat()

    storage.save(decision_key, decision)
    log_operation("backfill", decision_id, "decision", {"result": result})

    emit_json(True, decision_id=decision_id, message=f"决策 #{decision_id} 结果已回填")


def get_decision(decision_id: str, task_id: Optional[str] = None):
    """查询决策"""
    decision_id = validate_id(decision_id, "decision-id")
    if task_id:
        task_id = validate_id(task_id, "task-id")

    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    _, decision = load_decision_by_id(storage, decision_id, task_id=task_id)

    if not decision:
        emit_error(f"决策 {decision_id} 不存在")
        return

    emit_json(True, decision=decision)


def list_decisions(task_id: Optional[str] = None):
    """列出决策"""
    if task_id:
        task_id = validate_id(task_id, "task-id")

    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    all_keys = storage.list(f"{task_id}_D*" if task_id else "*_D*")
    decisions = []

    for key in all_keys:
        decision = storage.load(key)
        if decision:
            decisions.append(decision)

    decisions.sort(key=lambda d: d["created_at"], reverse=True)

    emit_json(True, count=len(decisions), decisions=decisions)


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="OPC Team 决策履历管理")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建决策履历")
    create_parser.add_argument("--task-id", required=True, help="任务ID")
    create_parser.add_argument("--decision-id", help="决策ID（可选，自动生成）")
    create_parser.add_argument("--title", required=True, help="决策标题")
    create_parser.add_argument("--options", required=True, help="供选方案")
    create_parser.add_argument("--chosen", required=True, help="最终选择")
    create_parser.add_argument("--reason", required=True, help="决策依据")
    create_parser.add_argument("--assumptions", required=True, help="假设清单（逗号分隔）")
    create_parser.add_argument("--force", action="store_true", help="决策已存在时显式覆盖")

    # update-assumption 命令
    update_parser = subparsers.add_parser("update-assumption", help="更新假设验证状态")
    update_parser.add_argument("--decision-id", required=True, help="决策ID")
    update_parser.add_argument("--task-id", help="任务ID（可选，多任务存在同名决策时必须指定）")
    update_parser.add_argument("--assumption-id", type=int, required=True, help="假设ID")
    update_parser.add_argument("--status", required=True, choices=["验证", "证伪", "部分验证"], help="验证状态")
    update_parser.add_argument("--actual", help="实际情况")
    update_parser.add_argument("--trigger-review", action="store_true", help="触发重审")

    # backfill 命令
    backfill_parser = subparsers.add_parser("backfill", help="回填决策结果")
    backfill_parser.add_argument("--decision-id", required=True, help="决策ID")
    backfill_parser.add_argument("--task-id", help="任务ID（可选，多任务存在同名决策时必须指定）")
    backfill_parser.add_argument("--result", required=True, choices=["成功", "失败", "部分成功"], help="结果")
    backfill_parser.add_argument("--metrics", help="量化指标")
    backfill_parser.add_argument("--lessons", help="经验教训")

    # get 命令
    get_parser = subparsers.add_parser("get", help="查询决策")
    get_parser.add_argument("--decision-id", required=True, help="决策ID")
    get_parser.add_argument("--task-id", help="任务ID（可选，多任务存在同名决策时必须指定）")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出决策")
    list_parser.add_argument("--task-id", help="任务ID（可选）")

    args = parser.parse_args()

    if args.command == "create":
        create_decision(
            args.task_id,
            args.decision_id,
            args.title,
            args.options,
            args.chosen,
            args.reason,
            args.assumptions,
            force=args.force
        )
    elif args.command == "update-assumption":
        update_assumption(
            args.decision_id,
            args.assumption_id,
            args.status,
            args.actual,
            args.trigger_review,
            task_id=args.task_id
        )
    elif args.command == "backfill":
        backfill_result(
            args.decision_id,
            args.result,
            args.metrics,
            args.lessons,
            task_id=args.task_id
        )
    elif args.command == "get":
        get_decision(args.decision_id, task_id=args.task_id)
    elif args.command == "list":
        list_decisions(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
