"""Tests for storage.FileStorage and SQLiteStorage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest


def _get_storage_module():
    import storage
    return storage


def test_file_storage_save_and_load(opc_env):
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")

    fs.save("T001", {"task_id": "T001", "title": "hello"})
    assert fs.exists("T001")

    loaded = fs.load("T001")
    assert loaded == {"task_id": "T001", "title": "hello"}


def test_file_storage_list_pattern(opc_env):
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")
    for i in range(1, 4):
        fs.save(f"T00{i}", {"task_id": f"T00{i}"})

    keys = sorted(fs.list("T*"))
    assert keys == ["T001", "T002", "T003"]


def test_file_storage_list_pattern_tolerates_json_suffix(opc_env):
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")
    fs.save("T001", {"task_id": "T001"})

    # The CLI sometimes passes "*.json"; storage should normalise it.
    assert "T001" in fs.list("*.json")


def test_file_storage_delete(opc_env):
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")
    fs.save("T001", {"task_id": "T001"})

    assert fs.delete("T001") is True
    assert fs.exists("T001") is False
    # Deleting a missing key is a no-op returning False.
    assert fs.delete("T001") is False


def test_file_storage_load_missing_returns_none(opc_env):
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")
    assert fs.load("missing") is None


def test_file_storage_concurrent_writes_do_not_corrupt(opc_env):
    """Two writers updating the same key should leave a valid JSON file.

    Without the lock in storage.save() the second writer could truncate while
    the first is mid-flush, leaving partial JSON behind.
    """
    storage = _get_storage_module()
    fs = storage.FileStorage(opc_env["data_dir"] / "tasks")
    fs.save("T001", {"task_id": "T001", "n": 0})

    def writer(n: int) -> None:
        fs.save("T001", {"task_id": "T001", "n": n, "payload": "x" * 1024})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(writer, range(64)))

    loaded = fs.load("T001")
    assert loaded is not None
    assert loaded["task_id"] == "T001"
    assert "n" in loaded


def test_file_storage_get_storage_singleton(opc_env):
    storage = _get_storage_module()
    a = storage.get_storage("tasks", {
        "backend": "file",
        "base_dir": opc_env["data_dir"] / "tasks",
    })
    b = storage.get_storage("tasks")
    assert a is b, "get_storage should cache per storage_type"


def test_sqlite_storage_round_trip(tmp_path):
    storage = _get_storage_module()
    sqlite = storage.SQLiteStorage(tmp_path / "opc.db")

    sqlite.save("T001", {"task_id": "T001", "title": "hello"})
    assert sqlite.exists("T001")
    assert sqlite.load("T001") == {"task_id": "T001", "title": "hello"}

    keys = sqlite.list("T*")
    assert keys == ["T001"]

    assert sqlite.delete("T001") is True
    assert sqlite.exists("T001") is False


def test_storage_factory_rejects_unknown_backend():
    storage = _get_storage_module()
    with pytest.raises(ValueError, match="不支持的存储后端"):
        storage.StorageFactory.create("redis")
