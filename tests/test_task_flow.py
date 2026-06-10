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


def _escalate(task_flow, opc_env, capsys):
    """Create + assess + execute + auto-escalate, return task id."""
    tid = task_flow.create_task("升级恢复测试", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L1", "简单类")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    path = opc_env["data_dir"] / "tasks" / f"{tid}.json"
    task = json.loads(path.read_text("utf-8"))
    task["created_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
    path.write_text(json.dumps(task), encoding="utf-8")

    task_flow.check_sla(tid)
    _drain(capsys)
    return tid


def test_escalated_can_resume_execution(opc_env, capsys):
    """escalated 不再是死状态：可以恢复 in_execution 并最终完成。"""
    task_flow = _get_task_flow()
    tid = _escalate(task_flow, opc_env, capsys)

    task_flow.transition_state(tid, "in_execution", actor="COO")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["to_state"] == "in_execution"
    _drain(capsys)

    task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "completed"


def test_escalated_can_be_cancelled(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = _escalate(task_flow, opc_env, capsys)

    task_flow.transition_state(tid, "cancelled", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "cancelled"

    # cancelled 是终态，没有出边。
    with pytest.raises(SystemExit):
        task_flow.transition_state(tid, "in_execution", actor="COO")
    payload = _last_json(capsys)
    assert "非法状态转换" in payload["error"]


def test_l4_completion_requires_decision_log(opc_env, capsys):
    """L4 与 L3 一样，完成前必须有决策履历。"""
    task_flow = _get_task_flow()
    tid = task_flow.create_task("战略辩论任务", "L4")
    _drain(capsys)
    task_flow.assess_task(tid, "L4", "战略级")
    _drain(capsys)
    task_flow.transition_state(tid, "in_debate", actor="COO")
    _drain(capsys)

    with pytest.raises(SystemExit):
        task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert "决策" in payload["error"]

    import decision_log
    decision_log.create_decision(tid, None, "主决策", "A,B", "A", "x", "a1:y")
    _drain(capsys)
    task_flow.transition_state(tid, "completed", actor="COO")
    payload = _last_json(capsys)
    assert payload["to_state"] == "completed"


def test_completed_transition_emits_single_json_with_sync_result(opc_env, capsys):
    """auto_sync_memory 开启时，完成态流转 stdout 仍是单个 JSON 对象，
    记忆同步结果内嵌在 memory_sync 字段。"""
    import config as cfg_mod
    cfg_mod.get_config().set("features.auto_sync_memory", True)

    task_flow = _get_task_flow()
    tid = task_flow.create_task("单JSON契约", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L1", "简单类")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)

    task_flow.transition_state(tid, "completed", actor="COO")
    out_lines = [line for line in capsys.readouterr().out.strip().splitlines() if line.strip()]
    assert len(out_lines) == 1, f"completed 流转应只输出一行 JSON，实际: {out_lines}"
    payload = json.loads(out_lines[0])
    assert payload["to_state"] == "completed"
    assert payload["memory_sync"]["success"] is True
    assert (opc_env["data_dir"] / "MEMORY.md").exists()


def test_check_sla_reports_when_disabled(opc_env, capsys):
    import config as cfg_mod
    cfg_mod.get_config().set("features.sla_check_enabled", False)

    task_flow = _get_task_flow()
    task_flow.check_sla("T999")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["action"] == "skipped"
    assert payload["reason"] == "sla_check_disabled"


def test_check_sla_errors_on_missing_task(opc_env, capsys):
    task_flow = _get_task_flow()
    with pytest.raises(SystemExit):
        task_flow.check_sla("T999")
    payload = _last_json(capsys)
    assert payload["success"] is False
    assert "不存在" in payload["error"]


def test_check_sla_reports_terminal_state(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("已完成任务", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L1", "简单类")
    _drain(capsys)
    task_flow.transition_state(tid, "in_execution", actor="COO")
    _drain(capsys)
    task_flow.transition_state(tid, "completed", actor="COO")
    _drain(capsys)

    task_flow.check_sla(tid)
    payload = _last_json(capsys)
    assert payload["action"] == "none"
    assert payload["reason"] == "terminal_or_escalated"
    assert payload["state"] == "completed"


def test_check_sla_reports_unassessed_task(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("未定级任务", "")
    _drain(capsys)

    task_flow.check_sla(tid)
    payload = _last_json(capsys)
    assert payload["action"] == "none"
    assert payload["reason"] == "not_assessed"


def test_check_sla_reports_within_threshold(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("未超期任务", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L4", "战略级（4 小时 SLA，不会超）")
    _drain(capsys)

    task_flow.check_sla(tid)
    payload = _last_json(capsys)
    assert payload["action"] == "none"
    assert payload["reason"] == "within_escalation_threshold"
    assert payload["sla_status"] == "正常"


def test_assess_records_actual_actor(opc_env, capsys):
    """--actor 实际值要进 actors 履历，预设角色名只做默认兜底。"""
    task_flow = _get_task_flow()
    tid = task_flow.create_task("记录操作者", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L2", "判断类", actor="CFO张晓燕")
    _drain(capsys)

    raw = json.loads((opc_env["data_dir"] / "tasks" / f"{tid}.json").read_text("utf-8"))
    assess_entries = [a for a in raw["actors"] if a.get("action") == "定级"]
    assert assess_entries and assess_entries[0]["actor"] == "CFO张晓燕"


def test_assess_actor_defaults_to_preset(opc_env, capsys):
    task_flow = _get_task_flow()
    tid = task_flow.create_task("默认操作者", "")
    _drain(capsys)
    task_flow.assess_task(tid, "L2", "判断类")
    _drain(capsys)

    raw = json.loads((opc_env["data_dir"] / "tasks" / f"{tid}.json").read_text("utf-8"))
    assess_entries = [a for a in raw["actors"] if a.get("action") == "定级"]
    assert assess_entries and assess_entries[0]["actor"] == "COO魏明远"
