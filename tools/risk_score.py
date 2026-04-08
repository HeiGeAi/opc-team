#!/usr/bin/env python3
"""
risk_score.py - OPC Team 风险量化评分

功能：
- 评估风险（概率 × 影响 = 等级）
- 更新风险状态
- 查询风险列表
- 风险等级自动计算
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import argparse

from config import get_config

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


# ==================== 风险评分矩阵 ====================

def calculate_risk_level(probability: int, impact: int) -> int:
    """
    计算风险等级
    概率 (1-5) × 影响 (1-5) → 风险等级 (1-5)
    """
    score = probability * impact

    if score <= 4:
        return 1  # 可忽略
    elif score <= 9:
        return 2  # 低危
    elif score <= 12:
        return 3  # 中危
    elif score <= 20:
        return 4  # 高危
    else:
        return 5  # 致命


RISK_LEVEL_DESC = {
    1: "可忽略 - 顺带处理",
    2: "低危 - 监控即可",
    3: "中危 - 必须有应对预案",
    4: "高危 - 升级处理，建议暂缓",
    5: "致命 - 触发停止机制"
}


# ==================== 工具函数 ====================

def get_risk_dir() -> Path:
    """获取风险目录"""
    risk_dir = get_config().get_path("risks_dir")
    risk_dir.mkdir(parents=True, exist_ok=True)
    return risk_dir


def get_log_dir() -> Path:
    """获取日志目录"""
    log_dir = get_config().get_path("logs_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_operation(operation: str, risk_id: str, details: Dict):
    """记录操作日志"""
    log_file = get_log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "risk_id": risk_id,
        "details": details
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def load_risk(risk_id: str) -> Optional[Dict]:
    """加载风险（带文件锁）"""
    risk_files = list(get_risk_dir().glob(f"*_{risk_id}.json"))
    if not risk_files:
        return None

    risk_file = risk_files[0]
    with open(risk_file, "r", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            return json.load(f)


def save_risk(risk: Dict):
    """保存风险（带文件锁）"""
    risk_file = get_risk_dir() / f"{risk['task_id']}_{risk['risk_id']}.json"

    with open(risk_file, "w", encoding="utf-8") as f:
        if HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(risk, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            json.dump(risk, f, ensure_ascii=False, indent=2)


def generate_risk_id() -> str:
    """生成风险ID"""
    existing_risks = list(get_risk_dir().glob("*_R*.json"))
    if not existing_risks:
        return "R001"

    max_id = max([int(f.stem.split("_")[1][1:]) for f in existing_risks])
    return f"R{max_id + 1:03d}"


# ==================== 核心功能 ====================

def assess_risk(
    task_id: str,
    risk_name: str,
    probability: int,
    impact: int,
    mitigation: Optional[str] = None
):
    """评估风险"""
    if not (1 <= probability <= 5 and 1 <= impact <= 5):
        print(json.dumps({
            "success": False,
            "error": "概率和影响必须在 1-5 之间"
        }, ensure_ascii=False))
        return

    risk_id = generate_risk_id()
    risk_level = calculate_risk_level(probability, impact)

    risk = {
        "risk_id": risk_id,
        "task_id": task_id,
        "name": risk_name,
        "probability": probability,
        "impact": impact,
        "level": risk_level,
        "level_desc": RISK_LEVEL_DESC[risk_level],
        "mitigation": mitigation,
        "status": "未发生",
        "actual_impact": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    save_risk(risk)
    log_operation("assess", risk_id, {
        "task_id": task_id,
        "name": risk_name,
        "level": risk_level
    })

    result = {
        "success": True,
        "risk_id": risk_id,
        "task_id": task_id,
        "level": risk_level,
        "level_desc": RISK_LEVEL_DESC[risk_level],
        "message": f"风险 {risk_id} 评估完成，等级 {risk_level}"
    }

    # 高危及以上风险触发警告
    if risk_level >= 4:
        result["alert"] = f"⚠️ {RISK_LEVEL_DESC[risk_level]}"
        if not mitigation:
            result["warning"] = "高危风险必须提供应对预案"

    print(json.dumps(result, ensure_ascii=False))


def update_risk(
    risk_id: str,
    status: str,
    actual_impact: Optional[int] = None
):
    """更新风险状态"""
    risk = load_risk(risk_id)
    if not risk:
        print(json.dumps({"success": False, "error": f"风险 {risk_id} 不存在"}, ensure_ascii=False))
        return

    risk["status"] = status
    if actual_impact is not None:
        risk["actual_impact"] = actual_impact
    risk["updated_at"] = datetime.now().isoformat()

    save_risk(risk)
    log_operation("update", risk_id, {"status": status, "actual_impact": actual_impact})

    result = {
        "success": True,
        "risk_id": risk_id,
        "status": status,
        "message": f"风险 {risk_id} 状态更新为 {status}"
    }

    # 如果风险已发生，对比预期影响和实际影响
    if status == "已发生" and actual_impact is not None:
        predicted_impact = risk["impact"]
        if actual_impact > predicted_impact:
            result["alert"] = f"⚠️ 实际影响 ({actual_impact}) 超过预期 ({predicted_impact})"
        elif actual_impact < predicted_impact:
            result["note"] = f"✅ 实际影响 ({actual_impact}) 低于预期 ({predicted_impact})，应对有效"

    print(json.dumps(result, ensure_ascii=False))


def list_risks(task_id: str, min_level: Optional[int] = None):
    """列出任务的所有风险"""
    risk_files = list(get_risk_dir().glob(f"{task_id}_*.json"))

    if not risk_files:
        print(json.dumps({
            "success": True,
            "task_id": task_id,
            "risks": [],
            "message": f"任务 {task_id} 暂无风险记录"
        }, ensure_ascii=False))
        return

    risks = []
    for risk_file in risk_files:
        with open(risk_file, "r", encoding="utf-8") as f:
            risk = json.load(f)
            if min_level is None or risk["level"] >= min_level:
                risks.append({
                    "risk_id": risk["risk_id"],
                    "name": risk["name"],
                    "level": risk["level"],
                    "level_desc": risk["level_desc"],
                    "status": risk["status"],
                    "mitigation": risk["mitigation"]
                })

    # 按风险等级降序排序
    risks.sort(key=lambda x: x["level"], reverse=True)

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "risks": risks,
        "total": len(risks),
        "high_risk_count": len([r for r in risks if r["level"] >= 4])
    }, ensure_ascii=False, indent=2))


def get_risk(risk_id: str):
    """获取风险详情"""
    risk = load_risk(risk_id)
    if not risk:
        print(json.dumps({"success": False, "error": f"风险 {risk_id} 不存在"}, ensure_ascii=False))
        return

    print(json.dumps({
        "success": True,
        "risk": risk
    }, ensure_ascii=False, indent=2))


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="OPC Team 风险量化评分工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # assess 命令
    assess_parser = subparsers.add_parser("assess", help="评估风险")
    assess_parser.add_argument("--task-id", required=True, help="任务ID")
    assess_parser.add_argument("--risk-name", required=True, help="风险名称")
    assess_parser.add_argument("--probability", type=int, required=True, help="概率 (1-5)")
    assess_parser.add_argument("--impact", type=int, required=True, help="影响 (1-5)")
    assess_parser.add_argument("--mitigation", help="应对预案")

    # update 命令
    update_parser = subparsers.add_parser("update", help="更新风险状态")
    update_parser.add_argument("--risk-id", required=True, help="风险ID")
    update_parser.add_argument("--status", required=True, help="状态")
    update_parser.add_argument("--actual-impact", type=int, help="实际影响 (1-5)")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出风险")
    list_parser.add_argument("--task-id", required=True, help="任务ID")
    list_parser.add_argument("--min-level", type=int, help="最小风险等级")

    # get 命令
    get_parser = subparsers.add_parser("get", help="获取风险详情")
    get_parser.add_argument("--risk-id", required=True, help="风险ID")

    args = parser.parse_args()

    if args.command == "assess":
        assess_risk(
            args.task_id,
            args.risk_name,
            args.probability,
            args.impact,
            args.mitigation
        )
    elif args.command == "update":
        update_risk(args.risk_id, args.status, args.actual_impact)
    elif args.command == "list":
        list_risks(args.task_id, args.min_level)
    elif args.command == "get":
        get_risk(args.risk_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
