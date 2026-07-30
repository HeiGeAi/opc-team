import json
from pathlib import Path

from tools.agent_ops import DEFAULT_DISPATCH_PROFILES
from tools.config import Config


ROOT = Path(__file__).resolve().parents[1]


def test_fallback_profiles_match_the_shipped_default_config(tmp_path):
    configured = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    configured = configured["orchestration"]["dispatch_profiles"]
    generated = Config(str(tmp_path / "missing-config.json")).data
    generated = generated["orchestration"]["dispatch_profiles"]

    for profile_id, fallback in DEFAULT_DISPATCH_PROFILES.items():
        assert fallback["sub_agent_target"] == configured[profile_id]["sub_agent_target"]
        assert fallback["agent_ids"] == configured[profile_id]["agent_ids"]
        assert generated[profile_id]["sub_agent_target"] == configured[profile_id]["sub_agent_target"]
        assert generated[profile_id]["agent_ids"] == configured[profile_id]["agent_ids"]

    important = DEFAULT_DISPATCH_PROFILES["important"]
    assert str(important["sub_agent_target"]) in important["description"]
