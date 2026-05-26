"""Tests for the task_flow state machine, assessment and SLA logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


def _get_task_flow():
    import task_flow
    return task_flow


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "expected JSON output on stdout"
    return json.loads(out[-1])


def _drain(capsys):
    capsys.readouterr()


def test_create_task_persists_and_returns_id(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("做一份周报", "本周交付摘要")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["task_id"] == tid
    assert (opc_env["data_dir"] / "tasks" / f"{tid}.json").exists()


def test_full_lifecycle_l1_task(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("整理客户清单", "周一下午前给到")
    _drain(capsys)

    task_flow.assess_task(tid, "L1", "简单整理类")
    payload = _last_json(capsys)
    assert payload["level"] == "L1"
    _drain(capsys)

    task_flow.transition_state(tid, "in_execution", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "in_execution"
    _drain(capsys)

    task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "completed"


def test_illegal_state_transition_rejected(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("非法跳转", "")
    _drain(capsys)

    # CREATED -> COMPLETED is not allowed; only CREATED -> ASSESSED.
    with pytest.raises(SystemExit):
        task_flow.transition_state(tid, "completed", actor="COO")

    payload = _last_json(capsys)
    assert payload["success"] is False
    assert "非法状态转换" in payload["error"]


def test_assess_requires_created_state(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("二次定级", "")
    _drain(capsys)

    task_flow.assess_task(tid, "L2", "判断类")
    _drain(capsys)

    with pytest.raises(SystemExit):
        task_flow.assess_task(tid, "L3", "想再定一次")
    payload = _last_json(capsys)
    assert "created" in payload["error"]


def test_l3_completion_requires_decision_log(opc_env, capsys):
    """L3 strategy tasks must record at least one decision before completing."""
    task_flow = _get_task_flow()
    tid = task_flow.create_task("做战略决策", "L3 策略任务")
    _drain(capsys)
    task_flow.assess_task(tid, "L3", "战略级")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    with pytest.raises(SystemExit):
        task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert "决策" in payload["error"]


def test_l3_completion_works_with_decision_record(opc_env, capsys):
    task_flow = _get_task_flow()
    import decision_log

    tid = task_flow.create_task("做战略决策", "L3 策略任务")
    _drain(capsys)
    task_flow.assess_task(tid, "L3", "战略级")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    decision_log.create_decision(
        tid,
        None,
        title="主决策",
        options="A,B",
        chosen="A",
        reason="A 风险更可控",
        assumptions="a1:招到人,a2:预算稳定",
    )
    _drain(capsys)

    task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "completed"


def test_progress_report_records_log(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("拆解任务", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L2", "判断类")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    task_flow.report_progress(tid, "完成第一步", progress=30)
    payload = _last_json(capsys)
    assert payload["progress"] == 30
    assert payload["bar"].endswith("30%")

    raw = json.loads((opc_env["data_dir"] / "tasks" / f"{tid}.json").read_text("utf-8"))
    assert raw["progress"] == 30
    assert len(raw["progress_log"]) == 1


def test_progress_rejects_out_of_range(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("范围检查", "")
    _drain(capsys)

    with pytest.raises(SystemExit):
        task_flow.report_progress(tid, "bad", progress=150)


def test_sla_status_marks_overdue(opc_env, capsys):
    """get_status should surface overdue / 严重超期 SLA states."""
    task_flow = _get_task_flow()
    tid = task_flow.create_task("SLA 测试", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L1", "简单类")
    _drain(capsys)

    # Backdate created_at so the SLA window (5 minutes for L1) is exceeded.
    path = opc_env["data_dir"] / "tasks" / f"{tid}.json"
    task = json.loads(path.read_text("utf-8"))
    task["created_at"] = (datetime.now() - timedelta(minutes=20)).isoformat()
    path.write_text(json.dumps(task), encoding="utf-8")

    task_flow.get_status(tid)
    payload = _last_json(capsys)
    assert payload["sla_status"] in ("超期", "严重超期")


def test_check_sla_auto_escalates(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("自动升级测试", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L1", "简单类")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    # Backdate beyond 2x the SLA window (10 minutes for L1).
    path = opc_env["data_dir"] / "tasks" / f"{tid}.json"
    task = json.loads(path.read_text("utf-8"))
    task["created_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
    path.write_text(json.dumps(task), encoding="utf-8")

    task_flow.check_sla(tid)
    payload = _last_json(capsys)
    assert payload["action"] == "escalated"

    refreshed = json.loads(path.read_text("utf-8"))
    assert refreshed["state"] == "escalated"
