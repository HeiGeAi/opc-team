#!/usr/bin/env python3
"""
config.py - OPC Team 配置管理

功能：
- 加载配置文件
- 环境变量支持
- 多平台路径适配
- 配置验证
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Dict




class Config:
    """配置管理器"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._find_config_file()
        self.data = self._load_config()

    def _find_config_file(self) -> Path:
        """查找配置文件（优先级顺序）"""
        # 1. 环境变量指定
        if env_config := os.getenv("OPC_CONFIG"):
            return Path(env_config)

        # 2. 当前目录
        if (Path.cwd() / "config.json").exists():
            return Path.cwd() / "config.json"

        # 3. OPC_HOME 环境变量
        if opc_home := os.getenv("OPC_HOME"):
            return Path(opc_home) / "config.json"

        # 4. 用户主目录
        home_config = Path.home() / ".opc-team" / "config.json"
        if home_config.exists():
            return home_config

        # 5. 默认：当前目录（将创建）
        return Path.cwd() / "config.json"

    def _load_config(self) -> Dict:
        """加载配置文件"""
        if not self.config_file.exists():
            return self._create_default_config()

        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _create_default_config(self) -> Dict:
        """创建默认配置"""
        default = {
            "version": "4.2.2",
            "platform": "generic",  # generic / claude_code / openclaw / cursor / api
            "paths": {
                "data_dir": str(Path.cwd() / "data"),
                "tasks_dir": "${data_dir}/tasks",
                "decisions_dir": "${data_dir}/decisions",
                "risks_dir": "${data_dir}/risks",
                "memory_dir": "${data_dir}/memory",
                "logs_dir": "${data_dir}/logs"
            },
            "storage": {
                "backend": "file",  # file / sqlite
                "file_lock": True,
                "auto_backup": False
            },
            "features": {
                "readonly_mode": False,
                "auto_sync_memory": True,
                "sla_check_enabled": True,
                "risk_alert_threshold": 3
            },
            "ai_platform": {
                "name": "generic",
                "tool_prefix": "python3 tools/",
                "supports_bash": True,
                "supports_function_calling": False
            }
        }

        # 保存默认配置
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)

        return default

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号路径）"""
        keys = key.split(".")
        value = self.data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        # 处理路径变量替换
        if isinstance(value, str) and "${" in value:
            value = self._resolve_path_vars(value)

        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split(".")
        data = self.data

        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]

        data[keys[-1]] = value
        self._save_config()

    def _resolve_path_vars(self, path: str) -> str:
        """解析路径变量"""
        # 替换 ${data_dir} 等变量
        if "${data_dir}" in path:
            data_dir = self.get("paths.data_dir")
            path = path.replace("${data_dir}", data_dir)

        # 替换环境变量
        if "${" in path:
            import re
            for match in re.finditer(r'\$\{(\w+)\}', path):
                var_name = match.group(1)
                var_value = os.getenv(var_name, "")
                path = path.replace(match.group(0), var_value)

        return path

    def _save_config(self) -> None:
        """保存配置文件"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_path(self, key: str) -> Path:
        """获取路径配置（自动转换为 Path 对象）"""
        path_str = self.get(f"paths.{key}")
        if not path_str:
            raise ValueError(f"路径配置 paths.{key} 不存在")

        path = Path(path_str)

        # 如果是相对路径，相对于配置文件所在目录
        if not path.is_absolute():
            path = self.config_file.parent / path

        return path

    def ensure_dirs(self) -> None:
        """确保所有配置的目录存在"""
        for key in ["data_dir", "tasks_dir", "decisions_dir", "risks_dir", "memory_dir", "logs_dir"]:
            path = self.get_path(key)
            path.mkdir(parents=True, exist_ok=True)

    def detect_platform(self) -> str:
        """自动检测 AI 平台"""
        # 检测 Claude Code
        if (Path.home() / ".claude").exists():
            return "claude_code"

        # 检测 OpenClaw
        if (Path.home() / ".openclaw").exists():
            return "openclaw"

        # 检测 Cursor
        if (Path.cwd() / ".cursorrules").exists():
            return "cursor"

        # 检测 Windsurf
        if (Path.cwd() / ".windsurfrules").exists():
            return "windsurf"

        return "generic"

    def adapt_to_platform(self, platform: Optional[str] = None) -> None:
        """适配到特定平台"""
        if platform is None:
            platform = self.detect_platform()

        self.set("platform", platform)

        platform_configs = {
            "claude_code": {
                "ai_platform.name": "claude_code",
                "ai_platform.tool_prefix": "python3 tools/",
                "ai_platform.supports_bash": True,
                "ai_platform.supports_function_calling": False
            },
            "openclaw": {
                "ai_platform.name": "openclaw",
                "ai_platform.tool_prefix": "python3 tools/",
                "ai_platform.supports_bash": True,
                "ai_platform.supports_function_calling": False
            },
            "cursor": {
                "ai_platform.name": "cursor",
                "ai_platform.tool_prefix": "",
                "ai_platform.supports_bash": False,
                "ai_platform.supports_function_calling": False
            },
            "windsurf": {
                "ai_platform.name": "windsurf",
                "ai_platform.tool_prefix": "",
                "ai_platform.supports_bash": True,
                "ai_platform.supports_function_calling": False
            },
            "api": {
                "ai_platform.name": "api",
                "ai_platform.tool_prefix": "",
                "ai_platform.supports_bash": False,
                "ai_platform.supports_function_calling": True
            },
            "generic": {
                "ai_platform.name": "generic",
                "ai_platform.tool_prefix": "python3 tools/",
                "ai_platform.supports_bash": True,
                "ai_platform.supports_function_calling": False
            }
        }

        if platform in platform_configs:
            for key, value in platform_configs[platform].items():
                self.set(key, value)

    def validate(self) -> bool:
        """验证配置完整性"""
        required_keys = [
            "version",
            "paths.data_dir",
            "storage.backend",
            "ai_platform.name"
        ]

        for key in required_keys:
            if self.get(key) is None:
                print(f"❌ 配置缺失: {key}")
                return False

        return True

    def print_info(self) -> None:
        """打印配置信息"""
        print(f"📋 OPC Team 配置信息")
        print(f"配置文件: {self.config_file}")
        print(f"版本: {self.get('version')}")
        print(f"平台: {self.get('ai_platform.name')}")
        print(f"数据目录: {self.get_path('data_dir')}")
        print(f"存储后端: {self.get('storage.backend')}")
        print(f"只读模式: {self.get('features.readonly_mode')}")


# 全局配置实例
_config_instance = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# CLI 接口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OPC Team 配置管理")
    subparsers = parser.add_subparsers(dest="command")

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化配置文件")
    init_parser.add_argument("--platform", help="指定平台 (claude_code/openclaw/api/cursor/windsurf/generic)")

    # get 命令
    get_parser = subparsers.add_parser("get", help="获取配置值")
    get_parser.add_argument("key", help="配置键（支持点号路径）")

    # set 命令
    set_parser = subparsers.add_parser("set", help="设置配置值")
    set_parser.add_argument("key", help="配置键")
    set_parser.add_argument("value", help="配置值")

    # info/show 命令
    subparsers.add_parser("info", help="显示配置信息")
    subparsers.add_parser("show", help="显示配置信息")

    # detect 命令
    subparsers.add_parser("detect", help="检测 AI 平台")

    # adapt 命令
    adapt_parser = subparsers.add_parser("adapt", help="适配到特定平台")
    adapt_parser.add_argument("platform", nargs="?", help="平台名称（不指定则自动检测）")

    args = parser.parse_args()

    config = get_config()

    if args.command == "init":
        if args.platform:
            config.adapt_to_platform(args.platform)
        else:
            config.adapt_to_platform()
        config.ensure_dirs()
        print(f"✅ 配置文件已初始化: {config.config_file}")
        config.print_info()

    elif args.command == "get":
        value = config.get(args.key)
        print(json.dumps(value, ensure_ascii=False, indent=2))

    elif args.command == "set":
        # 自动类型解析
        value = args.value
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)
        elif value.startswith("[") or value.startswith("{"):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass  # 保持字符串
        config.set(args.key, value)
        print(f"✅ 已设置 {args.key} = {value}")

    elif args.command in {"info", "show"}:
        config.print_info()

    elif args.command == "detect":
        platform = config.detect_platform()
        print(f"检测到平台: {platform}")

    elif args.command == "adapt":
        platform = args.platform or config.detect_platform()
        config.adapt_to_platform(platform)
        print(f"✅ 已适配到平台: {platform}")
        config.print_info()

    else:
        parser.print_help()
