"""Tests for memory_sync: MEMORY.md idempotency and storage-abstraction parity."""

from __future__ import annotations

import json


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out
    return json.loads(out[-1])


def _drain(capsys):
    capsys.readouterr()


def test_sync_is_idempotent_per_task(opc_env, capsys):
    """同一任务重复 sync 只保留一份条目（替换旧条目，不盲追加）。"""
    import memory_sync

    memory_sync.compress_to_l1("T001", "第一版摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["replaced"] is False

    memory_sync.compress_to_l1("T001", "第二版摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    payload = _last_json(capsys)
    assert payload["replaced"] is True

    content = (opc_env["data_dir"] / "MEMORY.md").read_text(encoding="utf-8")
    assert content.count("## 任务 T001 (") == 1
    assert "第二版摘要" in content
    assert "第一版摘要" not in content


def test_sync_keeps_other_task_entries(opc_env, capsys):
    import memory_sync

    memory_sync.compress_to_l1("T001", "任务一摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    _drain(capsys)
    memory_sync.compress_to_l1("T002", "任务二摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T002")
    _drain(capsys)

    # 重新同步 T001 不应影响 T002 条目。
    memory_sync.compress_to_l1("T001", "任务一新摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    _drain(capsys)

    content = (opc_env["data_dir"] / "MEMORY.md").read_text(encoding="utf-8")
    assert content.count("## 任务 T001 (") == 1
    assert content.count("## 任务 T002 (") == 1
    assert "任务一新摘要" in content
    assert "任务二摘要" in content


def test_sync_includes_decisions_via_storage_abstraction(opc_env, capsys):
    """文件后端：决策履历段要进 MEMORY.md。"""
    import decision_log
    import memory_sync

    decision_log.create_decision("T001", "D001", "定价策略", "A,B", "B", "x", "a1:y")
    _drain(capsys)
    memory_sync.compress_to_l1("T001", "摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    _drain(capsys)

    content = (opc_env["data_dir"] / "MEMORY.md").read_text(encoding="utf-8")
    assert "决策 #D001: 定价策略 → B" in content


def test_sync_includes_decisions_on_sqlite_backend(opc_env, capsys):
    """SQLite 后端：之前直读文件系统拿不到决策，现在走 storage 抽象后行为一致。"""
    import config as cfg_mod
    import storage as storage_mod

    cfg_mod.get_config().set("storage.backend", "sqlite")
    storage_mod.reset_storage_cache()

    import decision_log
    import memory_sync

    decision_log.create_decision("T001", "D001", "定价策略", "A,B", "B", "x", "a1:y")
    _drain(capsys)
    memory_sync.compress_to_l1("T001", "摘要")
    _drain(capsys)
    memory_sync.sync_to_memory_md("T001")
    _drain(capsys)

    content = (opc_env["data_dir"] / "MEMORY.md").read_text(encoding="utf-8")
    assert "决策 #D001: 定价策略 → B" in content
