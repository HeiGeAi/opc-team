"""Tests for runtime helpers: ID generation, readonly mode, logging."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest


def _get_runtime():
    import runtime
    return runtime


def test_emit_json_writes_success_payload(capsys):
    runtime = _get_runtime()
    runtime.emit_json(True, task_id="T001")
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload == {"success": True, "task_id": "T001"}


def test_emit_error_writes_payload_and_exits(capsys):
    runtime = _get_runtime()
    with pytest.raises(SystemExit):
        runtime.emit_error("boom", reason="x")
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload == {"success": False, "error": "boom", "reason": "x"}


def test_reserve_id_is_atomic_under_threads(opc_env):
    """Concurrent ID generation must produce distinct IDs."""
    runtime = _get_runtime()

    def gen() -> str:
        return runtime.reserve_id("T", "tasks_concurrent")

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _i: gen(), range(64)))

    assert len(set(ids)) == 64, "reserved IDs must be unique"


def test_generate_task_id_format(opc_env):
    runtime = _get_runtime()
    tid = runtime.generate_task_id()
    assert tid.startswith("T")
    assert tid[1:].isdigit()


def test_require_writable_blocks_in_readonly_mode(opc_env, monkeypatch, capsys):
    runtime = _get_runtime()
    # Toggle readonly in the loaded config and reset cache so the next
    # require_writable call picks it up.
    config_module = __import__("config")
    cfg = config_module.get_config()
    cfg.set("features.readonly_mode", True)

    with pytest.raises(SystemExit):
        runtime.require_writable("写入测试")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["success"] is False
    assert "readonly_mode" in payload["error"]


def test_log_operation_appends_jsonl(opc_env):
    runtime = _get_runtime()
    runtime.log_operation("create", "T001", "task", {"title": "x"})
    runtime.log_operation("update", "T001", "task", {"state": "completed"})

    log_dir = opc_env["data_dir"] / "logs"
    log_files = list(log_dir.glob("*.log"))
    assert len(log_files) == 1
    lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["operation"] == "create"
    assert parsed[1]["details"]["state"] == "completed"


def test_operation_lock_serialises_critical_section(opc_env):
    """operation_lock should serialise read-modify-write blocks across threads."""
    runtime = _get_runtime()
    lock_path = opc_env["data_dir"] / "tasks" / ".T001.lock"
    counter_file = opc_env["data_dir"] / "counter.txt"
    counter_file.write_text("0", encoding="utf-8")

    def bump() -> None:
        with runtime.operation_lock(lock_path):
            current = int(counter_file.read_text(encoding="utf-8") or "0")
            counter_file.write_text(str(current + 1), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _i: bump(), range(50)))

    assert counter_file.read_text(encoding="utf-8") == "50"
