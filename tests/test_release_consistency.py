import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _first_match(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"{path} is missing release version metadata"
    return match.group(1)


def test_release_version_is_consistent_across_public_surfaces():
    canonical = _first_match("pyproject.toml", r'^version = "([^"]+)"')

    versions = {
        "config.json": json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["version"],
        "adapters/api.json": json.loads(
            (ROOT / "adapters/api.json").read_text(encoding="utf-8")
        )["version"],
        "tools/config.py": _first_match("tools/config.py", r'"version": "([^"]+)"'),
        "install.sh": _first_match("install.sh", r"OPC Team v([^ ]+) 安装程序"),
        "README.md": _first_match("README.md", r"version-v([0-9.]+)-"),
        "README_EN.md": _first_match("README_EN.md", r"version-v([0-9.]+)-"),
        "SKILL.md": _first_match("SKILL.md", r"^# .* v([0-9.]+)"),
    }

    assert versions == {name: canonical for name in versions}
