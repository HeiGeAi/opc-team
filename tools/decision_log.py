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
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import fcntl
import argparse


# ==================== 工具函数 ====================

def get_decision_dir() -> Path:
    """获取决策目录"""
    decision_dir = Path.cwd() / "data" / "decisions"
    decision_dir.mkdir(parents=True, exist_ok=True)
    return decision_dir


def get_log_dir() -> Path:
    """获取日志目录"""
    log_dir = Path.cwd() / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_operation(operation: str, decision_id: str, details: Dict):
    """记录操作日志"""
    log_file = get_log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "decision_id": decision_id,
        "details": details
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def load_decision(decision_id: str) -> Optional[Dict]:
    """加载决策（带文件锁）"""
    decision_files = list(get_decision_dir().glob(f"*_{decision_id}.json"))
    if not decision_files:
        return None

    decision_file = decision_files[0]
    with open(decision_file, "r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def save_decision(decision: Dict):
    """保存决策（带文件锁）"""
    decision_file = get_decision_dir() / f"{decision['task_id']}_{decision['decision_id']}.json"

    with open(decision_file, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(decision, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def generate_decision_id() -> str:
    """生成决策ID"""
    existing_decisions = list(get_decision_dir().glob("*_D*.json"))
    if not existing_decisions:
        return "D001"

    max_id = max([int(f.stem.split("_")[1][1:]) for f in existing_decisions])
    return f"D{max_id + 1:03d}"


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

    save_decision(decision)
    log_operation("create", decision_id, {"task_id": task_id, "title": title})

    print(json.dumps({
        "success": True,
        "decision_id": decision_id,
        "task_id": task_id,
        "message": f"决策履历 #{decision_id} 创建成功",
        "assumptions_count": len(decision["assumptions"])
    }, ensure_ascii=False))


def update_assumption(
    decision_id: str,
    assumption_id: int,
    status: str,
    actual: Optional[str] = None,
    trigger_review: bool = False
):
    """更新假设验证状态"""
    decision = load_decision(decision_id)
    if not decision:
        print(json.dumps({"success": False, "error": f"决策 {decision_id} 不存在"}, ensure_ascii=False))
        return

    # 查找假设
    assumption = next((a for a in decision["assumptions"] if a["id"] == assumption_id), None)
    if not assumption:
        print(json.dumps({"success": False, "error": f"假设 {assumption_id} 不存在"}, ensure_ascii=False))
        return

    assumption["status"] = status
    assumption["actual"] = actual
    assumption["verified_at"] = datetime.now().isoformat()

    decision["updated_at"] = datetime.now().isoformat()

    save_decision(decision)
    log_operation("update_assumption", decision_id, {
        "assumption_id": assumption_id,
        "status": status,
        "trigger_review": trigger_review
    })

    result = {
        "success": True,
        "decision_id": decision_id,
        "assumption_id": assumption_id,
        "status": status,
        "message": f"假设 {assumption_id} 状态更新为 {status}"
    }

    if trigger_review:
        result["alert"] = "⚠️ 假设被证伪，必须在48小时内重新评估决策"
        result["action_required"] = "调用 task_flow.py 创建重审任务"

    print(json.dumps(result, ensure_ascii=False))


def backfill_result(
    decision_id: str,
    result: str,
    metrics: Optional[str] = None,
    lessons: Optional[str] = None
):
    """回填决策结果"""
    decision = load_decision(decision_id)
    if not decision:
        print(json.dumps({"success": False, "error": f"决策 {decision_id} 不存在"}, ensure_ascii=False))
        return

    decision["result"] = {
        "outcome": result,
        "metrics": metrics,
        "lessons": lessons,
        "backfilled_at": datetime.now().isoformat()
    }
    decision["backfilled_at"] = datetime.now().isoformat()
    decision["updated_at"] = datetime.now().isoformat()

    save_decision(decision)
    log_operation("backfill", decision_id, {"result": result})

    print(json.dumps({
        "success": True,
        "decision_id": decision_id,
        "message": f"决策 #{decision_id} 结果已回填"
    }, ensure_ascii=False))


def get_decision(decision_id: str):
    """查询决策"""
    decision = load_decision(decision_id)
    if not decision:
        print(json.dumps({"success": False, "error": f"决策 {decision_id} 不存在"}, ensure_ascii=False))
        return

    print(json.dumps({
        "success": True,
        "decision": decision
    }, ensure_ascii=False, indent=2))


def list_decisions(task_id: Optional[str] = None):
    """列出决策"""
    decision_dir = get_decision_dir()

    if task_id:
        decision_files = list(decision_dir.glob(f"{task_id}_*.json"))
    else:
        decision_files = list(decision_dir.glob("*_D*.json"))

    decisions = []
    for f in decision_files:
        with open(f, "r") as file:
            decisions.append(json.load(file))

    decisions.sort(key=lambda d: d["created_at"], reverse=True)

    print(json.dumps({
        "success": True,
        "count": len(decisions),
        "decisions": decisions
    }, ensure_ascii=False, indent=2))


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
