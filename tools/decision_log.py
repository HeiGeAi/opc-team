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

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import argparse

from config import get_config
from runtime import (
    emit_json, emit_error, require_writable,
    generate_decision_id, log_operation,
    get_storage_path
)
from storage import get_storage


def parse_assumptions(assumptions_str: str) -> List[Dict]:
    """解析假设字符串"""
    # 格式: "假设1:描述1,假设2:描述2"
    assumptions = []
    for idx, item in enumerate(assumptions_str.split(","), 1):
        if ":" in item:
            _, desc = item.split(":", 1)
            assumptions.append({
                "id": idx,
                "description": desc.strip(),
                "status": "未验证",
                "actual": None,
                "verified_at": None
            })
    return assumptions


# ==================== 核心功能 ====================

def create_decision(
    task_id: str,
    decision_id: Optional[str],
    title: str,
    options: str,
    chosen: str,
    reason: str,
    assumptions: str
):
    """创建决策履历"""
    if not require_writable("创建决策"):
        return

    if not decision_id:
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
    storage.save(storage_key, decision)

    log_operation("create", decision_id, "decision", {"task_id": task_id, "title": title})

    emit_json(True, decision_id=decision_id, task_id=task_id, message=f"决策履历 #{decision_id} 创建成功", assumptions_count=len(decision["assumptions"]))


def update_assumption(
    decision_id: str,
    assumption_id: int,
    status: str,
    actual: Optional[str] = None,
    trigger_review: bool = False
):
    """更新假设验证状态"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    # 查找决策（遍历找到 decision_id）
    all_keys = storage.list("*_D*.json")
    decision_key = None
    decision = None
    for key in all_keys:
        if key.endswith(f"_{decision_id}.json"):
            decision_key = key
            decision = storage.load(key.replace(".json", ""))
            break

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
    storage.save(decision_key.replace(".json", ""), decision)

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
    lessons: Optional[str] = None
):
    """回填决策结果"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    # 查找决策
    all_keys = storage.list("*_D*.json")
    decision_key = None
    decision = None
    for key in all_keys:
        if key.endswith(f"_{decision_id}.json"):
            decision_key = key
            decision = storage.load(key.replace(".json", ""))
            break

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

    storage.save(decision_key.replace(".json", ""), decision)
    log_operation("backfill", decision_id, "decision", {"result": result})

    emit_json(True, decision_id=decision_id, message=f"决策 #{decision_id} 结果已回填")


def get_decision(decision_id: str):
    """查询决策"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    # 查找决策
    all_keys = storage.list("*_D*.json")
    decision = None
    for key in all_keys:
        if key.endswith(f"_{decision_id}.json"):
            decision = storage.load(key.replace(".json", ""))
            break

    if not decision:
        emit_error(f"决策 {decision_id} 不存在")
        return

    emit_json(True, decision=decision)


def list_decisions(task_id: Optional[str] = None):
    """列出决策"""
    config = get_config()
    backend = config.get("storage.backend", "file")
    storage = get_storage("decisions", {"backend": backend, "base_dir": config.get_path("decisions_dir")})

    all_keys = storage.list("*_D*.json")
    decisions = []

    for key in all_keys:
        # key 格式: task_id_decision_id.json
        key_without_ext = key.replace(".json", "")
        if "_D" in key_without_ext:
            decision = storage.load(key_without_ext)
            if decision:
                if task_id is None or decision.get("task_id") == task_id:
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

    # update-assumption 命令
    update_parser = subparsers.add_parser("update-assumption", help="更新假设验证状态")
    update_parser.add_argument("--decision-id", required=True, help="决策ID")
    update_parser.add_argument("--assumption-id", type=int, required=True, help="假设ID")
    update_parser.add_argument("--status", required=True, choices=["验证", "证伪", "部分验证"], help="验证状态")
    update_parser.add_argument("--actual", help="实际情况")
    update_parser.add_argument("--trigger-review", action="store_true", help="触发重审")

    # backfill 命令
    backfill_parser = subparsers.add_parser("backfill", help="回填决策结果")
    backfill_parser.add_argument("--decision-id", required=True, help="决策ID")
    backfill_parser.add_argument("--result", required=True, choices=["成功", "失败", "部分成功"], help="结果")
    backfill_parser.add_argument("--metrics", help="量化指标")
    backfill_parser.add_argument("--lessons", help="经验教训")

    # get 命令
    get_parser = subparsers.add_parser("get", help="查询决策")
    get_parser.add_argument("--decision-id", required=True, help="决策ID")

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
            args.assumptions
        )
    elif args.command == "update-assumption":
        update_assumption(
            args.decision_id,
            args.assumption_id,
            args.status,
            args.actual,
            args.trigger_review
        )
    elif args.command == "backfill":
        backfill_result(
            args.decision_id,
            args.result,
            args.metrics,
            args.lessons
        )
    elif args.command == "get":
        get_decision(args.decision_id)
    elif args.command == "list":
        list_decisions(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
