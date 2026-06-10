"""Tests for decision_log: assumption tracking and result backfill."""

from __future__ import annotations

import json

import pytest


def _get_decision_log():
    import decision_log
    return decision_log


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out
    return json.loads(out[-1])


def test_parse_assumptions_extracts_id_description_pairs():
    decision_log = _get_decision_log()
    items = decision_log.parse_assumptions("a1:能招到人,a2:预算稳定,a3:平台不改规则")
    assert len(items) == 3
    assert items[0]["description"] == "能招到人"
    assert items[0]["status"] == "未验证"
    assert items[2]["id"] == 3


def test_parse_assumptions_keeps_unlabeled_entries():
    decision_log = _get_decision_log()
    items = decision_log.parse_assumptions("a1:有效,无冒号假设,a2:也有效")
    # Entries without ':' are kept as unlabeled assumptions, not silently dropped.
    assert [a["description"] for a in items] == ["有效", "无冒号假设", "也有效"]
    assert [a["id"] for a in items] == [1, 2, 3]


def test_parse_assumptions_skips_empty_entries():
    decision_log = _get_decision_log()
    items = decision_log.parse_assumptions("a1:有效,, ,a2:也有效")
    assert [a["description"] for a in items] == ["有效", "也有效"]


def test_create_decision_counts_unlabeled_assumptions(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision(
        "T001", None, "计数检查", "A,B", "A", "x",
        assumptions="a1:有标签,无标签条目"
    )
    payload = _last_json(capsys)
    assert payload["assumptions_count"] == 2


def test_create_decision_rejects_id_with_path_separator(opc_env, capsys):
    """decision-id 含 / 之前会把数据写到错误位置且报成功，现在直接报错。"""
    decision_log = _get_decision_log()
    with pytest.raises(SystemExit):
        decision_log.create_decision(
            "T001", "D001/evil", "坏ID", "A,B", "A", "x", "a1:y"
        )
    payload = _last_json(capsys)
    assert payload["success"] is False
    assert "非法字符" in payload["error"]
    # 不允许残留任何写入。
    decisions_dir = opc_env["data_dir"] / "decisions"
    assert not decisions_dir.exists() or not list(decisions_dir.rglob("*.json"))


@pytest.mark.parametrize("bad_id", ["D*", "D?1", "D[1]", "../D001", "D001/../x"])
def test_create_decision_rejects_glob_metacharacters(opc_env, capsys, bad_id):
    decision_log = _get_decision_log()
    with pytest.raises(SystemExit):
        decision_log.create_decision("T001", bad_id, "坏ID", "A,B", "A", "x", "a1:y")
    payload = _last_json(capsys)
    assert "非法字符" in payload["error"]


def test_create_duplicate_decision_id_rejected(opc_env, capsys):
    """同 task 重复 create 同一 decision-id 不再静默覆盖。"""
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", "D001", "第一次", "A,B", "A", "x", "a1:y")
    _last_json(capsys)

    with pytest.raises(SystemExit):
        decision_log.create_decision("T001", "D001", "第二次", "A,B", "B", "y", "a1:z")
    payload = _last_json(capsys)
    assert payload["success"] is False
    assert "已存在" in payload["error"]

    # 原内容未被覆盖。
    decision_log.get_decision("D001", task_id="T001")
    payload = _last_json(capsys)
    assert payload["decision"]["title"] == "第一次"


def test_create_duplicate_decision_id_with_force_overwrites(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", "D001", "第一次", "A,B", "A", "x", "a1:y")
    _last_json(capsys)

    decision_log.create_decision("T001", "D001", "第二次", "A,B", "B", "y", "a1:z", force=True)
    payload = _last_json(capsys)
    assert payload["success"] is True

    decision_log.get_decision("D001", task_id="T001")
    payload = _last_json(capsys)
    assert payload["decision"]["title"] == "第二次"


def test_same_decision_id_across_tasks_requires_task_id(opc_env, capsys):
    """同名 decision-id 出现在多个任务下时，不带 --task-id 必须报错并列出候选。"""
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", "D001", "任务一的决策", "A,B", "A", "x", "a1:y")
    _last_json(capsys)
    decision_log.create_decision("T002", "D001", "任务二的决策", "A,B", "B", "y", "a1:z")
    _last_json(capsys)

    with pytest.raises(SystemExit):
        decision_log.get_decision("D001")
    payload = _last_json(capsys)
    assert payload["success"] is False
    assert "T001_D001" in payload["error"]
    assert "T002_D001" in payload["error"]


def test_get_decision_scoped_by_task_id(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", "D001", "任务一的决策", "A,B", "A", "x", "a1:y")
    _last_json(capsys)
    decision_log.create_decision("T002", "D001", "任务二的决策", "A,B", "B", "y", "a1:z")
    _last_json(capsys)

    decision_log.get_decision("D001", task_id="T002")
    payload = _last_json(capsys)
    assert payload["decision"]["title"] == "任务二的决策"


def test_update_assumption_scoped_by_task_id(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", "D001", "任务一的决策", "A,B", "A", "x", "a1:y")
    _last_json(capsys)
    decision_log.create_decision("T002", "D001", "任务二的决策", "A,B", "B", "y", "a1:z")
    _last_json(capsys)

    decision_log.update_assumption("D001", assumption_id=1, status="验证", task_id="T002")
    payload = _last_json(capsys)
    assert payload["success"] is True

    decision_log.get_decision("D001", task_id="T002")
    assert _last_json(capsys)["decision"]["assumptions"][0]["status"] == "验证"
    decision_log.get_decision("D001", task_id="T001")
    assert _last_json(capsys)["decision"]["assumptions"][0]["status"] == "未验证"


def test_create_decision_persists(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision(
        task_id="T001",
        decision_id=None,
        title="选定主路径",
        options="A,B,C",
        chosen="A",
        reason="ROI 最高",
        assumptions="a1:招到人,a2:预算到位",
    )
    payload = _last_json(capsys)
    assert payload["assumptions_count"] == 2
    did = payload["decision_id"]

    path = opc_env["data_dir"] / "decisions" / f"T001_{did}.json"
    assert path.exists()


def test_update_assumption_marks_falsified(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision(
        "T001", None, "选 A", "A,B", "A", "更快", "a1:招到人"
    )
    did = _last_json(capsys)["decision_id"]

    decision_log.update_assumption(did, assumption_id=1, status="证伪", actual="没招到", trigger_review=True)
    payload = _last_json(capsys)
    assert payload["status"] == "证伪"
    assert "alert" in payload
    assert "重新评估" in payload["alert"]


def test_backfill_result_writes_outcome(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision(
        "T001", None, "灰度上线", "全量,灰度", "灰度", "降风险", "a1:错误率<1%"
    )
    did = _last_json(capsys)["decision_id"]

    decision_log.backfill_result(did, result="成功", metrics="P50延迟降低20%", lessons="灰度有效")
    _last_json(capsys)  # drain

    decision_log.get_decision(did)
    payload = _last_json(capsys)
    decision = payload["decision"]
    assert decision["result"]["outcome"] == "成功"
    assert decision["result"]["metrics"] == "P50延迟降低20%"


def test_list_decisions_orders_newest_first(opc_env, capsys):
    decision_log = _get_decision_log()
    decision_log.create_decision("T001", None, "第一个", "A,B", "A", "x", "a1:y")
    _last_json(capsys)
    decision_log.create_decision("T001", None, "第二个", "A,B", "B", "y", "a1:z")
    _last_json(capsys)

    decision_log.list_decisions("T001")
    payload = _last_json(capsys)
    assert payload["count"] == 2
    # newest first
    assert payload["decisions"][0]["title"] == "第二个"


def test_get_missing_decision_raises(opc_env, capsys):
    decision_log = _get_decision_log()
    with pytest.raises(SystemExit):
        decision_log.get_decision("D999")
    payload = _last_json(capsys)
    assert "不存在" in payload["error"]
