"""Shared pytest fixtures for OPC Team tests.

The tools/ modules use bare imports (``from config import get_config``) and
module-level singletons (``_config_instance``, ``_storage_instances``). To get
deterministic isolation per test we:

1. Add ``tools/`` to ``sys.path`` once (session scope).
2. Per test, point ``OPC_CONFIG`` at a temp ``config.json`` whose ``data_dir``
   lives under a fresh ``tmp_path``.
3. Reset the cached singletons so each test starts from a clean slate.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _make_config(data_dir: Path) -> dict:
    return {
        "version": "test",
        "platform": "generic",
        "paths": {
            "data_dir": str(data_dir),
            "tasks_dir": "${data_dir}/tasks",
            "decisions_dir": "${data_dir}/decisions",
            "risks_dir": "${data_dir}/risks",
            "memory_dir": "${data_dir}/memory",
            "logs_dir": "${data_dir}/logs",
            "agents_dir": "${data_dir}/agents",
            "dashboard_dir": "${data_dir}/dashboard",
            "assignments_dir": "${data_dir}/assignments",
        },
        "storage": {
            "backend": "file",
            "file_lock": True,
            "auto_backup": False,
        },
        "features": {
            "readonly_mode": False,
            "auto_sync_memory": False,
            "sla_check_enabled": True,
            "risk_alert_threshold": 3,
        },
        "ai_platform": {
            "name": "generic",
            "tool_prefix": "python3 tools/",
            "supports_bash": True,
            "supports_function_calling": False,
        },
        "agent_defaults": {
            "model": {
                "source": "platform_default",
                "provider": None,
                "model": None,
                "api_base": None,
                "api_key_env": None,
                "headers": {},
                "temperature": None,
                "max_tokens": None,
            }
        },
        "orchestration": {
            "main_agent_id": "ceo",
            "agent_pack": "default",
            "default_profile": "daily",
            "dispatch_profiles": {
                "daily": {
                    "label": "日常常驻",
                    "sub_agent_target": 3,
                    "agent_ids": ["coo", "project", "strategist"],
                },
                "important": {
                    "label": "重要任务",
                    "sub_agent_target": 8,
                    "agent_ids": ["coo", "project", "strategist", "research", "product", "tech", "data", "qa"],
                },
                "full": {
                    "label": "满编协同",
                    "sub_agent_target": 20,
                    "agent_ids": "__all_sub_agents__",
                },
            },
            "profile_keywords": {"full": []},
        },
        "dashboard": {"host": "127.0.0.1", "port": 8765, "refresh_seconds": 8},
        "model_catalog": {"custom_models": []},
    }


def _reset_singletons() -> None:
    """Drop cached module-level singletons so the next get_config / get_storage
    call rereads from the env-pointed config file."""
    for mod_name in ("config", "storage"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "_config_instance"):
                mod._config_instance = None
            if hasattr(mod, "_storage_instances"):
                mod._storage_instances.clear()


@pytest.fixture
def opc_env(tmp_path, monkeypatch):
    """Provide an isolated OPC working directory rooted at tmp_path.

    Yields a dict with paths and the loaded ``config`` module so tests can
    inspect the resolved configuration.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(_make_config(data_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPC_CONFIG", str(config_path))
    _reset_singletons()

    config_module = importlib.import_module("config")
    importlib.reload(config_module)
    # After reload the storage module also needs its cached singletons cleared.
    if "storage" in sys.modules:
        importlib.reload(sys.modules["storage"])

    yield {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "config_path": config_path,
        "config": config_module.get_config(),
    }

    _reset_singletons()


@pytest.fixture
def capjson(capsys):
    """Capture emit_json / emit_error output and parse as JSON."""

    def _read():
        captured = capsys.readouterr().out.strip().splitlines()
        if not captured:
            return None
        # last non-empty line is the result
        return json.loads(captured[-1])

    return _read
