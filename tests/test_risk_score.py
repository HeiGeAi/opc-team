"""Tests for risk_score: matrix math and CRUD."""

from __future__ import annotations

import json

import pytest


def _get_risk_score():
    import risk_score
    return risk_score


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out
    return json.loads(out[-1])


@pytest.mark.parametrize(
    "probability,impact,expected_level",
    [
        (1, 1, 1),    # score 1 → 可忽略
        (2, 2, 1),    # score 4 → 可忽略 (boundary)
        (3, 3, 2),    # score 9 → 低危 (boundary)
        (4, 3, 3),    # score 12 → 中危 (boundary)
        (5, 3, 4),    # score 15 → 高危
        (5, 5, 5),    # score 25 → 致命
    ],
)
def test_risk_level_matrix(probability, impact, expected_level):
    risk_score = _get_risk_score()
    assert risk_score.calculate_risk_level(probability, impact) == expected_level


def test_assess_risk_persists_and_returns_level(opc_env, capsys):
    risk_score = _get_risk_score()
    # 4 × 5 = 20 → 高危 (level 4) at the upper boundary of the 高危 band.
    risk_score.assess_risk("T001", "供应商断供", probability=4, impact=5, mitigation="备用供应商")
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["level"] == 4
    assert "高危" in payload["level_desc"]


def test_assess_risk_rejects_out_of_range(opc_env, capsys):
    risk_score = _get_risk_score()
    with pytest.raises(SystemExit):
        risk_score.assess_risk("T001", "bad", probability=10, impact=1)


def test_assess_risk_alerts_when_above_threshold(opc_env, capsys):
    risk_score = _get_risk_score()
    risk_score.assess_risk("T001", "数据丢失", probability=5, impact=5)
    payload = _last_json(capsys)
    # threshold defaults to 3 in conftest, level 5 (致命) must trigger alert + warning.
    assert "alert" in payload
    assert payload.get("warning"), "no mitigation supplied → warning expected"


def test_list_risks_sorts_descending(opc_env, capsys):
    risk_score = _get_risk_score()
    risk_score.assess_risk("T001", "低风险", probability=1, impact=1)
    _last_json(capsys)
    risk_score.assess_risk("T001", "高风险", probability=5, impact=5, mitigation="x")
    _last_json(capsys)

    risk_score.list_risks("T001")
    payload = _last_json(capsys)
    assert payload["total"] == 2
    assert payload["risks"][0]["level"] >= payload["risks"][1]["level"]


def test_update_risk_flags_higher_than_predicted_impact(opc_env, capsys):
    risk_score = _get_risk_score()
    risk_score.assess_risk("T001", "供应商延迟", probability=3, impact=3, mitigation="备用")
    rid = _last_json(capsys)["risk_id"]

    risk_score.update_risk(rid, status="已发生", actual_impact=5)
    payload = _last_json(capsys)
    assert payload["status"] == "已发生"
    assert "alert" in payload  # 实际 > 预期


def test_get_risk_returns_full_record(opc_env, capsys):
    risk_score = _get_risk_score()
    risk_score.assess_risk("T001", "迁移风险", probability=3, impact=4, mitigation="灰度")
    rid = _last_json(capsys)["risk_id"]

    risk_score.get_risk(rid)
    payload = _last_json(capsys)
    assert payload["risk"]["risk_id"] == rid
    assert payload["risk"]["mitigation"] == "灰度"
