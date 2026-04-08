#!/usr/bin/env python3
"""
memory_sync.py - OPC Team 三级记忆系统

功能：
- L0 即时记忆（当前会话）
- L1 短期记忆（任务摘要）
- L2 长期记忆（跨会话沉淀）
- 压缩提纯（L0 → L1）
- 归档沉淀（L1 → L2）
- 同步到 MEMORY.md
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import argparse

from config import get_config


# ==================== 工具函数 ====================

def get_memory_dir() -> Path:
    """获取记忆目录"""
    memory_dir = get_config().get_path("memory_dir")
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def get_memory_file() -> Path:
    """获取 MEMORY.md 文件路径"""
    return get_config().get_path("data_dir") / "MEMORY.md"


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


def log_operation(operation: str, details: Dict):
    """记录操作日志"""
    log_file = get_log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "details": details
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def load_l0_memory(task_id: str) -> List[str]:
    """加载 L0 即时记忆"""
    l0_file = get_memory_dir() / f"L0_{task_id}.json"
    if not l0_file.exists():
        return []

    with open(l0_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("entries", [])


def save_l0_memory(task_id: str, entries: List[str]):
    """保存 L0 即时记忆"""
    l0_file = get_memory_dir() / f"L0_{task_id}.json"
    with open(l0_file, "w", encoding="utf-8") as f:
        json.dump({
            "task_id": task_id,
            "entries": entries,
            "updated_at": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)


def load_l1_memory() -> Dict:
    """加载 L1 短期记忆"""
    l1_file = get_memory_dir() / "L1_short_term.json"
    if not l1_file.exists():
        return {}

    with open(l1_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_l1_memory(l1_data: Dict):
    """保存 L1 短期记忆"""
    l1_file = get_memory_dir() / "L1_short_term.json"
    with open(l1_file, "w", encoding="utf-8") as f:
        json.dump(l1_data, f, ensure_ascii=False, indent=2)


def load_l2_memory() -> Dict:
    """加载 L2 长期记忆"""
    l2_file = get_memory_dir() / "L2_long_term.json"
    if not l2_file.exists():
        return {
            "CEO偏好": [],
            "方法论": [],
            "避坑指南": [],
            "成功案例": []
        }

    with open(l2_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_l2_memory(l2_data: Dict):
    """保存 L2 长期记忆"""
    l2_file = get_memory_dir() / "L2_long_term.json"
    with open(l2_file, "w", encoding="utf-8") as f:
        json.dump(l2_data, f, ensure_ascii=False, indent=2)


def init_memory_system():
    """初始化记忆系统"""
    config = get_config()
    config.ensure_dirs()

    memory_file = get_memory_file()
    if not memory_file.exists():
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write("# OPC Team Memory\n")

    if not (get_memory_dir() / "L1_short_term.json").exists():
        save_l1_memory({})

    if not (get_memory_dir() / "L2_long_term.json").exists():
        save_l2_memory({
            "CEO偏好": [],
            "方法论": [],
            "避坑指南": [],
            "成功案例": []
        })

    log_operation("init_memory_system", {"memory_file": str(memory_file)})

    print(json.dumps({
        "success": True,
        "memory_dir": str(get_memory_dir()),
        "memory_file": str(memory_file),
        "message": "记忆系统初始化成功"
    }, ensure_ascii=False))


# ==================== 核心功能 ====================

def write_l0(task_id: str, content: str):
    """写入 L0 即时记忆"""
    entries = load_l0_memory(task_id)
    entries.append({
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    save_l0_memory(task_id, entries)

    log_operation("write_l0", {"task_id": task_id})

    print(json.dumps({
        "success": True,
        "level": "L0",
        "task_id": task_id,
        "entries_count": len(entries),
        "message": "L0 即时记忆写入成功"
    }, ensure_ascii=False))


def compress_to_l1(task_id: str, summary: str):
    """压缩提纯到 L1"""
    l1_data = load_l1_memory()

    l1_data[task_id] = {
        "summary": summary,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    save_l1_memory(l1_data)

    # 清理 L0
    l0_file = get_memory_dir() / f"L0_{task_id}.json"
    if l0_file.exists():
        l0_file.unlink()

    log_operation("compress_to_l1", {"task_id": task_id})

    print(json.dumps({
        "success": True,
        "level": "L1",
        "task_id": task_id,
        "message": "L0 已压缩提纯到 L1，L0 已清理"
    }, ensure_ascii=False))


def archive_to_l2(category: str, content: str):
    """归档到 L2 长期记忆"""
    valid_categories = ["CEO偏好", "方法论", "避坑指南", "成功案例"]
    if category not in valid_categories:
        print(json.dumps({
            "success": False,
            "error": f"无效分类，必须是: {', '.join(valid_categories)}"
        }, ensure_ascii=False))
        return

    l2_data = load_l2_memory()

    l2_data[category].append({
        "content": content,
        "archived_at": datetime.now().isoformat()
    })

    save_l2_memory(l2_data)
    log_operation("archive_to_l2", {"category": category})

    print(json.dumps({
        "success": True,
        "level": "L2",
        "category": category,
        "message": f"已归档到 L2 长期记忆 - {category}"
    }, ensure_ascii=False))


def read_memory(level: str, task_id: Optional[str] = None, category: Optional[str] = None):
    """读取记忆"""
    if level == "L0":
        if not task_id:
            print(json.dumps({"success": False, "error": "L0 需要指定 task_id"}, ensure_ascii=False))
            return

        entries = load_l0_memory(task_id)
        print(json.dumps({
            "success": True,
            "level": "L0",
            "task_id": task_id,
            "entries": entries
        }, ensure_ascii=False))

    elif level == "L1":
        l1_data = load_l1_memory()

        if task_id:
            result = l1_data.get(task_id)
            print(json.dumps({
                "success": True,
                "level": "L1",
                "task_id": task_id,
                "data": result
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "success": True,
                "level": "L1",
                "data": l1_data
            }, ensure_ascii=False))

    elif level == "L2":
        l2_data = load_l2_memory()

        if category:
            result = l2_data.get(category, [])
            print(json.dumps({
                "success": True,
                "level": "L2",
                "category": category,
                "data": result
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "success": True,
                "level": "L2",
                "data": l2_data
            }, ensure_ascii=False))


def sync_to_memory_md(task_id: str):
    """同步到 MEMORY.md"""
    memory_file = get_memory_file()

    # 读取任务相关数据
    l1_data = load_l1_memory()
    task_summary = l1_data.get(task_id, {}).get("summary", "无摘要")

    # 读取决策履历
    decision_dir = get_decision_dir()
    decisions = []
    if decision_dir.exists():
        for dec_file in decision_dir.glob(f"{task_id}_*.json"):
            with open(dec_file, "r", encoding="utf-8") as f:
                dec = json.load(f)
                decisions.append(f"- 决策 #{dec['decision_id']}: {dec['title']} → {dec['chosen']}")

    # 构建 MEMORY.md 内容
    content = []

    if memory_file.exists():
        with open(memory_file, "r", encoding="utf-8") as f:
            content = f.readlines()

    # 添加新任务记录
    new_entry = f"\n## 任务 {task_id} ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    new_entry += f"**摘要**: {task_summary}\n\n"

    if decisions:
        new_entry += "**决策履历**:\n"
        new_entry += "\n".join(decisions) + "\n"

    content.append(new_entry)

    # 写入文件
    with open(memory_file, "w", encoding="utf-8") as f:
        f.writelines(content)

    log_operation("sync_to_memory_md", {"task_id": task_id})

    print(json.dumps({
        "success": True,
        "task_id": task_id,
        "file": str(memory_file),
        "message": f"任务 {task_id} 已同步到 MEMORY.md"
    }, ensure_ascii=False))


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="OPC Team 三级记忆系统")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # init 命令
    subparsers.add_parser("init", help="初始化记忆系统")

    # write 命令
    write_parser = subparsers.add_parser("write", help="写入 L0 即时记忆")
    write_parser.add_argument("--level", required=True, choices=["L0"], help="记忆级别")
    write_parser.add_argument("--task-id", required=True, help="任务ID")
    write_parser.add_argument("--content", required=True, help="记忆内容")

    # compress 命令
    compress_parser = subparsers.add_parser("compress", help="压缩提纯到 L1")
    compress_parser.add_argument("--task-id", required=True, help="任务ID")
    compress_parser.add_argument("--summary", required=True, help="摘要")

    # archive 命令
    archive_parser = subparsers.add_parser("archive", help="归档到 L2")
    archive_parser.add_argument("--category", required=True, help="分类")
    archive_parser.add_argument("--content", required=True, help="内容")

    # read 命令
    read_parser = subparsers.add_parser("read", help="读取记忆")
    read_parser.add_argument("--level", required=True, choices=["L0", "L1", "L2"], help="记忆级别")
    read_parser.add_argument("--task-id", help="任务ID（L0/L1）")
    read_parser.add_argument("--category", help="分类（L2）")

    # sync 命令
    sync_parser = subparsers.add_parser("sync", help="同步到 MEMORY.md")
    sync_parser.add_argument("--task-id", required=True, help="任务ID")

    args = parser.parse_args()

    if args.command == "init":
        init_memory_system()
    elif args.command == "write":
        write_l0(args.task_id, args.content)
    elif args.command == "compress":
        compress_to_l1(args.task_id, args.summary)
    elif args.command == "archive":
        archive_to_l2(args.category, args.content)
    elif args.command == "read":
        read_memory(args.level, args.task_id, args.category)
    elif args.command == "sync":
        sync_to_memory_md(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
