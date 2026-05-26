"""Regression tests: task_flow's best-effort sync hooks must not abort the
primary call when ``sync_agent_from_task`` raises SystemExit.

Background: ``sync_agent_from_task`` and related helpers call ``emit_error``
which raises SystemExit (not Exception). A bare ``except Exception`` lets
SystemExit escape past the best-effort sync hook and short-circuits the
calling state machine method, leaving the caller with a partial write.
"""

from __future__ import annotations

import json



def _get_task_flow():
    import task_flow
    return task_flow


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out
    return json.loads(out[-1])


def _make_sync_blow_up(monkeypatch):
    """Force every agent_ops sync call to behave like emit_error → SystemExit."""
    import agent_ops

    def _raise_systemexit(*_args, **_kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(agent_ops, "sync_agent_from_task", _raise_systemexit)
    monkeypatch.setattr(agent_ops, "get_main_agent_id", _raise_systemexit)
    monkeypatch.setattr(agent_ops, "describe_orchestration_plan", _raise_systemexit)


def test_create_task_survives_sync_systemexit(opc_env, capsys, monkeypatch):
    task_flow = _get_task_flow()
    _make_sync_blow_up(monkeypatch)

    task_flow.create_task("survive create", "ensure SystemExit is caught")
    payload = _last_json(capsys)
    assert payload["success"] is True, "primary emit_json must still fire"
    assert payload["task_id"].startswith("T")


def test_assess_task_survives_sync_systemexit(opc_env, capsys, monkeypatch):
    task_flow = _get_task_flow()

    # First create cleanly so we have a task in the right state.
    task_flow.create_task("survive assess", "for SystemExit assessment")
    create_payload = _last_json(capsys)
    tid = create_payload["task_id"]

    # Then make the sync hooks blow up. The primary state change should still
    # land and emit success.
    _make_sync_blow_up(monkeypatch)
    task_flow.assess_task(tid, "L2", "verify resilience")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["level"] == "L2"

    # The on-disk state must reflect the assessment.
    path = opc_env["data_dir"] / "tasks" / f"{tid}.json"
    task = json.loads(path.read_text(encoding="utf-8"))
    assert task["state"] == "assessed"
    assert task["level"] == "L2_JUDGMENT"


def test_transition_survives_sync_systemexit(opc_env, capsys, monkeypatch):
    task_flow = _get_task_flow()
    task_flow.create_task("survive transition", "")
    tid = _last_json(capsys)["task_id"]
    task_flow.assess_task(tid, "L1", "simple")
    _last_json(capsys)

    _make_sync_blow_up(monkeypatch)
    task_flow.transition_state(tid, "in_execution", actor="harness")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["to_state"] == "in_execution"


def test_progress_survives_sync_systemexit(opc_env, capsys, monkeypatch):
    task_flow = _get_task_flow()
    task_flow.create_task("survive progress", "")
    tid = _last_json(capsys)["task_id"]

    _make_sync_blow_up(monkeypatch)
    task_flow.report_progress(tid, "halfway", 50, agent_id="strategist")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["progress"] == 50
