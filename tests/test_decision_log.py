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


def test_parse_assumptions_skips_malformed_entries():
    decision_log = _get_decision_log()
    items = decision_log.parse_assumptions("a1:有效,malformed,a2:也有效")
    # Items without ':' are silently dropped.
    assert [a["description"] for a in items] == ["有效", "也有效"]


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
