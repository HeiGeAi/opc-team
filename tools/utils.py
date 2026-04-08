"""
utils.py - OPC Team 通用工具函数

提供跨工具共享的通用功能
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def ensure_dir(path: Path) -> Path:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_timestamp(dt: datetime = None) -> str:
    """格式化时间戳"""
    if dt is None:
        dt = datetime.now()
    return dt.isoformat()


def format_date(dt: datetime = None) -> str:
    """格式化日期"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")


def json_response(success: bool, data: Dict[str, Any] = None, error: str = None) -> str:
    """标准 JSON 响应格式"""
    response = {"success": success}

    if data:
        response.update(data)

    if error:
        response["error"] = error

    return json.dumps(response, ensure_ascii=False, indent=2)


def load_json_file(file_path: Path) -> Dict:
    """加载 JSON 文件"""
    if not file_path.exists():
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(file_path: Path, data: Dict):
    """保存 JSON 文件"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def progress_bar(progress: int, width: int = 10) -> str:
    """生成进度条"""
    filled = int(progress / 100 * width)
    empty = width - filled
    return "▓" * filled + "░" * empty


def format_progress(progress: int, status: str = "正常") -> str:
    """格式化进度显示"""
    bar = progress_bar(progress)
    status_emoji = {
        "正常": "✅",
        "延期": "🔄",
        "高危": "⚠️",
        "阻塞": "🚫"
    }
    emoji = status_emoji.get(status, "")
    return f"{bar} {progress}% | 状态：{emoji}{status}"
