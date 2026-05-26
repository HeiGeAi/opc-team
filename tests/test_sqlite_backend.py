"""SQLite backend parity tests.

v4.5 shipped a broken SQLite path: ``StorageFactory.create("sqlite", ...)``
defaulted the db file to ``Path.cwd() / "data" / "opc.db"`` and ignored the
caller's ``base_dir``. As a result task_flow writes landed in one location
while reads went looking in another, depending on the process cwd. v4.6
derives db_path from base_dir.
"""

from __future__ import annotations

import json



def _switch_to_sqlite(opc_env):
    """Reconfigure the active env to use the SQLite backend."""
    import config as cfg_mod
    import storage as storage_mod

    cfg = cfg_mod.get_config()
    cfg.set("storage.backend", "sqlite")
    storage_mod.reset_storage_cache()
    return cfg


def _last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out
    return json.loads(out[-1])


def test_factory_derives_db_path_from_base_dir(tmp_path):
    """The db file must land under the configured workspace, not Path.cwd()."""
    import storage as storage_mod

    base_dir = tmp_path / "data" / "tasks"
    base_dir.mkdir(parents=True)

    sqlite_storage = storage_mod.StorageFactory.create("sqlite", base_dir=base_dir)
    assert sqlite_storage.db_path == tmp_path / "data" / "opc.db"


def test_factory_honours_explicit_db_path(tmp_path):
    import storage as storage_mod

    explicit = tmp_path / "custom" / "opc.db"
    storage_obj = storage_mod.StorageFactory.create(
        "sqlite", db_path=explicit, base_dir="/ignored"
    )
    assert storage_obj.db_path == explicit


def test_sqlite_full_lifecycle(opc_env, capsys):
    """End-to-end create → assess → transition → status on SQLite."""
    _switch_to_sqlite(opc_env)

    import task_flow
    task_flow.create_task("sqlite lifecycle", "exercise SQLite path")
    tid = _last_json(capsys)["task_id"]

    task_flow.assess_task(tid, "L1", "sqlite")
    _last_json(capsys)
    task_flow.transition_state(tid, "in_execution", actor="harness")
    _last_json(capsys)
    task_flow.report_progress(tid, "halfway", 50)
    _last_json(capsys)
    task_flow.transition_state(tid, "completed", actor="harness")
    _last_json(capsys)

    task_flow.get_status(tid)
    payload = _last_json(capsys)
    assert payload["success"] is True
    assert payload["task"]["state"] == "completed"
    assert payload["task"]["progress"] == 100

    # The SQLite db must live inside the workspace, not in some sibling dir.
    db_path = opc_env["data_dir"] / "opc.db"
    assert db_path.exists(), "opc.db should be at the workspace data root"


def test_sqlite_get_status_matches_create(opc_env, capsys):
    """The bug reproduced in stress test H1: get_status after create returned
    'task not found' under SQLite. This guards against a regression."""
    _switch_to_sqlite(opc_env)

    import task_flow
    task_flow.create_task("sqlite read-after-write", "verify visibility")
    create_payload = _last_json(capsys)
    tid = create_payload["task_id"]

    task_flow.get_status(tid)
    status_payload = _last_json(capsys)

    assert status_payload["success"] is True
    assert status_payload["task"]["task_id"] == tid


def test_sqlite_multiple_storage_types_share_db(opc_env, capsys):
    """tasks, decisions, risks should all live in the same opc.db so that
    cross-entity references resolve consistently."""
    _switch_to_sqlite(opc_env)

    import task_flow
    import decision_log
    import risk_score

    task_flow.create_task("multi-type sqlite", "")
    tid = _last_json(capsys)["task_id"]

    decision_log.create_decision(tid, None, "d1", "A,B", "A", "reason", "a1:hold")
    _last_json(capsys)
    risk_score.assess_risk(tid, "r1", 2, 2)
    _last_json(capsys)

    db_path = opc_env["data_dir"] / "opc.db"
    assert db_path.exists()

    # Verify all three rows actually live in one DB, each under its own namespace.
    # The shared opc.db is what makes SQLite worth shipping; the per-namespace
    # prefix is what stops e.g. a task T001 from being misread as an agent record.
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT key FROM opc_data")
        keys = sorted(row[0] for row in cur.fetchall())
    finally:
        conn.close()

    assert f"tasks::{tid}" in keys, f"no namespaced task row: {keys}"
    assert any(k.startswith(f"decisions::{tid}_D") for k in keys), f"no decision row for {tid}: {keys}"
    assert any(k.startswith(f"risks::{tid}_R") for k in keys), f"no risk row for {tid}: {keys}"
