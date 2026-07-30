import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installer_selftest_removes_its_temporary_task(tmp_path):
    checkout = tmp_path / "opc-team"
    shutil.copytree(
        ROOT,
        checkout,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", "build", "data", "output"),
    )
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")

    result = subprocess.run(
        ["bash", "install.sh", "-p", "generic", "--skip-env", "--skip-deps", "-t"],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert list((checkout / "data" / "tasks").glob("*.json")) == []
    agent_records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (checkout / "data" / "agents").glob("**/*.json")
    ]
    assert all(record.get("current_task_id") is None for record in agent_records)
