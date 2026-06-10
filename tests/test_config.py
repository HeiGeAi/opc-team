"""Tests for config: read paths must be side-effect free; readonly compat."""

from __future__ import annotations

import json

import pytest


def test_config_read_does_not_create_file(tmp_path, monkeypatch):
    """读路径（实例化 + get）不落盘，只有显式 init/set 才创建 config.json。"""
    import config as cfg_mod

    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OPC_CONFIG", str(config_path))

    cfg = cfg_mod.Config()
    assert cfg.get("storage.backend") == "file"
    assert cfg.get("version") is not None
    assert not config_path.exists(), "config get 不应该静默创建 config.json"


def test_config_set_creates_file(tmp_path, monkeypatch):
    import config as cfg_mod

    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OPC_CONFIG", str(config_path))

    cfg = cfg_mod.Config()
    cfg.set("storage.backend", "sqlite")
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["storage"]["backend"] == "sqlite"


def test_readonly_mode_top_level_also_blocks(opc_env, capsys):
    """顶层 readonly_mode 写法与 features.readonly_mode 等效。"""
    import runtime
    cfg = opc_env["config"]
    cfg.set("readonly_mode", True)

    with pytest.raises(SystemExit):
        runtime.require_writable("写入测试")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["success"] is False
    assert "readonly_mode" in payload["error"]


def test_readonly_mode_features_form_blocks(opc_env, capsys):
    import runtime
    cfg = opc_env["config"]
    cfg.set("features.readonly_mode", True)

    with pytest.raises(SystemExit):
        runtime.require_writable("写入测试")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["success"] is False
