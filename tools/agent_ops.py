#!/usr/bin/env python3
"""
agent_ops.py - OPC Team 主从 Agent 编排、状态与模型路由

功能：
- 管理主 agent / sub-agent 注册表
- 维护 agent 当前工作状态
- 记录主 agent 给 sub-agent 的派发任务
- 为不同 agent 配置不同 API 模型
- 在未配置时默认继承宿主平台模型
"""

import argparse
import copy
import json
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from agent_catalog import list_agent_packs, load_agent_catalog, resolve_pack
from config import get_config
from runtime import (
    emit_error,
    emit_json,
    generate_assignment_id,
    log_operation,
    operation_lock,
    require_writable
)
from storage import get_storage


AGENT_STATUSES = ["idle", "running", "waiting", "blocked", "completed", "offline"]
ASSIGNMENT_STATUSES = ["queued", "running", "blocked", "done", "canceled"]
PROFILE_ALL_SUB_AGENTS = "__all_sub_agents__"

STATUS_LABELS = {
    "idle": "空闲",
    "running": "执行中",
    "waiting": "等待中",
    "blocked": "阻塞",
    "completed": "已完成",
    "offline": "离线"
}

ASSIGNMENT_STATUS_LABELS = {
    "queued": "待处理",
    "running": "执行中",
    "blocked": "阻塞",
    "done": "已完成",
    "canceled": "已取消"
}

PROFILE_PRIORITY = {
    "daily": 1,
    "important": 2,
    "full": 3
}

LEVEL_PROFILE_MAP = {
    "L1_SIMPLE": "daily",
    "L2_JUDGMENT": "daily",
    "L3_STRATEGY": "important",
    "L4_DEBATE": "full"
}

LEVEL_ALIASES = {
    "L1": "L1_SIMPLE",
    "L1_SIMPLE": "L1_SIMPLE",
    "L2": "L2_JUDGMENT",
    "L2_JUDGMENT": "L2_JUDGMENT",
    "L3": "L3_STRATEGY",
    "L3_STRATEGY": "L3_STRATEGY",
    "L4": "L4_DEBATE",
    "L4_DEBATE": "L4_DEBATE"
}

DEFAULT_DISPATCH_PROFILES = {
    "daily": {
        "label": "日常常驻",
        "description": "日常任务默认由 3 个常驻 sub-agent 待命，保持响应速度和上下文稳定。",
        "sub_agent_target": 3,
        "agent_ids": ["coo", "project", "strategist"],
        "task_levels": ["L1_SIMPLE", "L2_JUDGMENT"]
    },
    "important": {
        "label": "重要任务",
        "description": "重要任务拉起 8 个核心 sub-agent，覆盖拆解、研究、方案、执行与校验。",
        "sub_agent_target": 8,
        "agent_ids": ["coo", "project", "strategist", "research", "product", "tech", "data", "qa"],
        "task_levels": ["L3_STRATEGY"]
    },
    "full": {
        "label": "满编协同",
        "description": "用户指定或高复杂任务启用全部角色梯队，按当前 pack 的满编能力协同。",
        "sub_agent_target": 20,
        "agent_ids": PROFILE_ALL_SUB_AGENTS,
        "task_levels": ["L4_DEBATE"]
    }
}

DEFAULT_PROFILE_KEYWORDS = {
    "full": [
        "满血",
        "全员",
        "全部代理",
        "所有代理",
        "20个代理",
        "复杂任务",
        "高复杂度",
        "跨部门",
        "集团级",
        "全量",
        "专项战役",
        "用户指定"
    ]
}

def _default_model_config() -> Dict:
    return {
        "source": "default",
        "provider": None,
        "model": None,
        "api_base": None,
        "api_key_env": None,
        "headers": {},
        "temperature": None,
        "max_tokens": None
    }


def _agent_storage():
    config = get_config()
    return get_storage("agents", {
        "backend": config.get("storage.backend", "file"),
        "base_dir": config.get_path("agents_dir"),
        "use_lock": config.get("storage.file_lock", True),
        "auto_backup": config.get("storage.auto_backup", False)
    })


def _assignment_storage():
    config = get_config()
    return get_storage("assignments", {
        "backend": config.get("storage.backend", "file"),
        "base_dir": config.get_path("assignments_dir"),
        "use_lock": config.get("storage.file_lock", True),
        "auto_backup": config.get("storage.auto_backup", False)
    })


def _task_storage():
    config = get_config()
    return get_storage("tasks", {
        "backend": config.get("storage.backend", "file"),
        "base_dir": config.get_path("tasks_dir"),
        "use_lock": config.get("storage.file_lock", True),
        "auto_backup": config.get("storage.auto_backup", False)
    })


def _agent_lock(agent_id: str):
    return operation_lock(get_config().get_path("agents_dir") / f".{get_agent_pack()}.{agent_id}.lock")


def get_agent_pack() -> str:
    return resolve_pack(get_config().get("orchestration.agent_pack", "default"))


def _load_default_agents(strict: bool = True, pack: Optional[str] = None) -> List[Dict]:
    selected_pack = resolve_pack(pack or get_agent_pack())
    try:
        return load_agent_catalog(strict=strict, pack=selected_pack)
    except ValueError as exc:
        emit_error(f"agent catalog 无效 (pack={selected_pack}): {exc}")


def _agent_aliases(strict: bool = True, pack: Optional[str] = None) -> Dict[str, List[str]]:
    selected_pack = resolve_pack(pack or get_agent_pack())
    return {
        agent["agent_id"]: list(agent.get("aliases", []))
        for agent in _load_default_agents(strict=strict, pack=selected_pack)
    }


def _agent_storage_key(agent_id: str, pack: Optional[str] = None) -> str:
    return f"{resolve_pack(pack or get_agent_pack())}/{agent_id}"


def _load_stored_agent_record(agent_id: str, pack: Optional[str] = None) -> Optional[Dict]:
    selected_pack = resolve_pack(pack or get_agent_pack())
    storage = _agent_storage()
    namespaced_key = _agent_storage_key(agent_id, selected_pack)
    stored = storage.load(namespaced_key)
    if stored:
        return stored

    if selected_pack == "default":
        legacy = storage.load(agent_id)
        if legacy:
            legacy["catalog_pack"] = "default"
            storage.save(namespaced_key, legacy)
            storage.delete(agent_id)
            return legacy
    return None


def _builtin_agent_map() -> Dict[str, Dict]:
    return {agent["agent_id"]: agent for agent in _load_default_agents(strict=True)}


def get_main_agent_id() -> str:
    configured = str(get_config().get("orchestration.main_agent_id", "") or "").strip()
    catalog = _load_default_agents(strict=True)
    if configured and any(agent["agent_id"] == configured and agent["agent_type"] == "main" for agent in catalog):
        return configured
    main_agent = next((agent["agent_id"] for agent in catalog if agent["agent_type"] == "main"), "ceo")
    if configured != main_agent:
        get_config().set("orchestration.main_agent_id", main_agent)
    return main_agent


def normalize_task_level(level: Optional[str]) -> Optional[str]:
    if level in (None, ""):
        return None
    text = str(level).strip().upper()
    return LEVEL_ALIASES.get(text, str(level).strip())


def load_task_record(task_id: str) -> Optional[Dict]:
    if not task_id:
        return None
    return _task_storage().load(task_id)


def _ordered_sub_agents(pack: Optional[str] = None) -> List[Dict]:
    return [
        agent for agent in _load_default_agents(strict=True, pack=pack)
        if agent.get("agent_type") == "sub"
    ]


def get_default_dispatch_profile_id() -> str:
    configured = str(get_config().get("orchestration.default_profile", "daily") or "daily").strip()
    return configured if configured in DEFAULT_DISPATCH_PROFILES else "daily"


def get_dispatch_profiles() -> Dict[str, Dict]:
    raw_profiles = get_config().get("orchestration.dispatch_profiles", {}) or {}
    profiles: Dict[str, Dict] = {}

    for profile_id, default in DEFAULT_DISPATCH_PROFILES.items():
        merged = copy.deepcopy(default)
        raw = raw_profiles.get(profile_id, {}) if isinstance(raw_profiles, dict) else {}
        if isinstance(raw, dict):
            for key in ("label", "description"):
                if raw.get(key) is not None:
                    merged[key] = str(raw.get(key)).strip() or merged[key]
            if "sub_agent_target" in raw:
                try:
                    merged["sub_agent_target"] = max(0, int(raw.get("sub_agent_target") or 0))
                except (TypeError, ValueError):
                    pass
            if "task_levels" in raw and isinstance(raw.get("task_levels"), list):
                merged["task_levels"] = [
                    normalize_task_level(level)
                    for level in raw.get("task_levels", [])
                    if normalize_task_level(level)
                ]
            if "agent_ids" in raw:
                agent_ids = raw.get("agent_ids")
                if isinstance(agent_ids, str):
                    merged["agent_ids"] = PROFILE_ALL_SUB_AGENTS if agent_ids == PROFILE_ALL_SUB_AGENTS else [agent_ids]
                elif isinstance(agent_ids, list):
                    merged["agent_ids"] = [str(agent_id).strip() for agent_id in agent_ids if str(agent_id).strip()]

        if isinstance(merged.get("agent_ids"), list):
            deduped: List[str] = []
            seen = set()
            for agent_id in merged["agent_ids"]:
                if agent_id not in seen:
                    deduped.append(agent_id)
                    seen.add(agent_id)
            merged["agent_ids"] = deduped

        merged["profile_id"] = profile_id
        profiles[profile_id] = merged

    return profiles


def _profile_keywords() -> Dict[str, List[str]]:
    merged = copy.deepcopy(DEFAULT_PROFILE_KEYWORDS)
    raw_keywords = get_config().get("orchestration.profile_keywords", {}) or {}
    if not isinstance(raw_keywords, dict):
        return merged

    for profile_id, keywords in raw_keywords.items():
        if not isinstance(keywords, list):
            continue
        merged[profile_id] = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
    return merged


def _keyword_profile(*texts: Optional[str]) -> Optional[Dict]:
    haystack = " ".join(str(text or "").strip().lower() for text in texts if str(text or "").strip())
    if not haystack:
        return None

    for profile_id, keywords in _profile_keywords().items():
        for keyword in keywords:
            normalized = keyword.lower()
            if normalized and normalized in haystack:
                return {
                    "profile_id": profile_id,
                    "keyword": keyword
                }
    return None


def _selected_profile_agents(profile: Dict) -> List[Dict]:
    sub_agents = _ordered_sub_agents()
    if not sub_agents:
        return []

    target = max(0, int(profile.get("sub_agent_target") or 0))
    all_by_id = {agent["agent_id"]: agent for agent in sub_agents}
    configured = profile.get("agent_ids", [])

    if configured == PROFILE_ALL_SUB_AGENTS:
        return sub_agents[:]

    selected: List[Dict] = []
    seen = set()
    if isinstance(configured, list):
        for agent_id in configured:
            agent = all_by_id.get(agent_id)
            if not agent or agent_id in seen:
                continue
            selected.append(agent)
            seen.add(agent_id)

    if target and len(selected) < target:
        for agent in sub_agents:
            if agent["agent_id"] in seen:
                continue
            selected.append(agent)
            seen.add(agent["agent_id"])
            if len(selected) >= target:
                break

    return selected[:target] if target else selected


def describe_orchestration_plan(
    task: Optional[Dict] = None,
    level: Optional[str] = None,
    requested_profile: Optional[str] = None,
    title: Optional[str] = None,
    ceo_input: Optional[str] = None,
    reason: Optional[str] = None
) -> Dict:
    profiles = get_dispatch_profiles()
    profile_id = str(requested_profile or (task or {}).get("orchestration_profile") or "").strip()
    source = "explicit"
    matched_keyword = None

    if profile_id not in profiles:
        keyword_match = _keyword_profile(
            (task or {}).get("title"),
            (task or {}).get("ceo_input"),
            (task or {}).get("assessment_reason"),
            title,
            ceo_input,
            reason
        )
        if keyword_match and keyword_match["profile_id"] in profiles:
            profile_id = keyword_match["profile_id"]
            matched_keyword = keyword_match["keyword"]
            source = "keyword"
        else:
            normalized_level = normalize_task_level(level or (task or {}).get("level"))
            profile_id = LEVEL_PROFILE_MAP.get(normalized_level, get_default_dispatch_profile_id())
            source = "task_level" if normalized_level else "default"
    else:
        normalized_level = normalize_task_level(level or (task or {}).get("level"))

    profile = copy.deepcopy(profiles.get(profile_id, profiles[get_default_dispatch_profile_id()]))
    selected_agents = _selected_profile_agents(profile)
    selected_agent_ids = [agent["agent_id"] for agent in selected_agents]
    available_sub_agents = _ordered_sub_agents()
    available_roles = len(available_sub_agents) + 1
    selected_role_count = len(selected_agents) + 1

    source_labels = {
        "explicit": "用户指定",
        "keyword": "复杂度命中",
        "task_level": "任务等级",
        "default": "默认档位"
    }

    if profile_id == "full" and selected_role_count == available_roles:
        headline = f"{profile.get('label')} · {selected_role_count} 角色"
    else:
        headline = f"{profile.get('label')} · {len(selected_agents)} 子代理"

    return {
        "profile_id": profile_id,
        "label": profile.get("label", profile_id),
        "description": profile.get("description", ""),
        "source": source,
        "source_label": source_labels.get(source, source),
        "matched_keyword": matched_keyword,
        "task_id": (task or {}).get("task_id"),
        "task_title": (task or {}).get("title") or title,
        "task_level": normalize_task_level(level or (task or {}).get("level")),
        "sub_agents": [
            {
                "agent_id": agent["agent_id"],
                "name": agent.get("name"),
                "role": agent.get("role")
            }
            for agent in selected_agents
        ],
        "selected_sub_agent_ids": selected_agent_ids,
        "selected_sub_agent_count": len(selected_agents),
        "target_sub_agent_count": int(profile.get("sub_agent_target") or len(selected_agents)),
        "selected_role_count": selected_role_count,
        "available_sub_agent_count": len(available_sub_agents),
        "available_role_count": available_roles,
        "headline": headline
    }


def build_orchestration_snapshot(tasks: Optional[List[Dict]] = None) -> Dict:
    profiles = {
        profile_id: describe_orchestration_plan(requested_profile=profile_id)
        for profile_id in ("daily", "important", "full")
    }
    default_profile_id = get_default_dispatch_profile_id()
    open_tasks = [
        task for task in (tasks or [])
        if task.get("state") not in {"completed"}
    ]

    current_profile = profiles[default_profile_id]
    focus_task = None
    if open_tasks:
        ranked_plans = []
        for task in open_tasks:
            plan = describe_orchestration_plan(task=task)
            ranked_plans.append({
                "task": task,
                "plan": plan
            })

        ranked_plans.sort(
            key=lambda item: (
                PROFILE_PRIORITY.get(item["plan"]["profile_id"], 0),
                item["task"].get("updated_at", item["task"].get("created_at", "")),
                item["task"].get("created_at", "")
            ),
            reverse=True
        )
        focus_task = ranked_plans[0]["task"]
        current_profile = ranked_plans[0]["plan"]

    current_profile = copy.deepcopy(current_profile)
    current_profile["focus_task_id"] = focus_task.get("task_id") if focus_task else None
    current_profile["focus_task_title"] = focus_task.get("title") if focus_task else None
    current_profile["focus_task_state"] = focus_task.get("state") if focus_task else None

    return {
        "default_profile_id": default_profile_id,
        "profiles": profiles,
        "current_profile": current_profile
    }


def _normalize_model_config(model_config: Optional[Dict]) -> Dict:
    normalized = _default_model_config()
    if model_config:
        normalized.update(model_config)
    headers = normalized.get("headers")
    normalized["headers"] = headers if isinstance(headers, dict) else {}
    return normalized


def get_default_model_config() -> Dict:
    config = get_config()
    default_model = config.get("agent_defaults.model", {}) or {}
    normalized = _normalize_model_config(default_model)
    if normalized["source"] == "default":
        normalized["source"] = "platform_default"
    return normalized


def model_display(model_config: Dict) -> str:
    if model_config.get("source") == "platform_default":
        return "宿主默认模型"

    provider = model_config.get("provider") or "custom"
    model = model_config.get("model") or "未指定模型"
    return f"{provider} · {model}"


def _model_registry_note(api_base: Optional[str], api_key_env: Optional[str]) -> str:
    note_bits: List[str] = []
    if api_base:
        parsed = urlparse(api_base)
        note_bits.append(parsed.netloc or api_base)
    if api_key_env:
        note_bits.append(api_key_env)
    return " / ".join(note_bits) if note_bits else "用户已接入模型"


def _model_registry_entry(model_config: Optional[Dict]) -> Optional[Dict]:
    normalized = _normalize_model_config(model_config)
    if normalized.get("source") != "custom_api":
        return None

    provider = str(normalized.get("provider") or "").strip()
    model = str(normalized.get("model") or "").strip()
    if not provider or not model:
        return None

    api_base = normalized.get("api_base") or None
    api_key_env = normalized.get("api_key_env") or None
    headers = normalized.get("headers") if isinstance(normalized.get("headers"), dict) else {}
    entry_id = "custom_api|" + "|".join([
        provider.lower(),
        model.lower(),
        api_base or "",
        api_key_env or ""
    ])
    return {
        "id": entry_id,
        "source": "custom_api",
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key_env": api_key_env,
        "headers": headers,
        "temperature": normalized.get("temperature"),
        "max_tokens": normalized.get("max_tokens"),
        "display": model_display(normalized),
        "note": _model_registry_note(api_base, api_key_env)
    }


def list_registered_custom_models() -> List[Dict]:
    config = get_config()
    raw_registry = config.get("model_catalog.custom_models", []) or []
    sources: List[Optional[Dict]] = list(raw_registry)

    default_model = get_default_model_config()
    if default_model.get("source") == "custom_api":
        sources.append(default_model)

    for agent in list_agents():
        model_config = agent.get("model_config") or {}
        if model_config.get("source") == "custom_api":
            sources.append(model_config)

    registry: List[Dict] = []
    seen = set()
    for item in sources:
        entry = _model_registry_entry(item)
        if not entry or entry["id"] in seen:
            continue
        seen.add(entry["id"])
        registry.append(entry)
    return registry


def _register_custom_model(model_config: Optional[Dict]) -> None:
    entry = _model_registry_entry(model_config)
    if not entry:
        return

    config = get_config()
    registry = config.get("model_catalog.custom_models", []) or []
    merged_sources = list(registry) + [entry]
    merged_registry: List[Dict] = []
    seen = set()
    for item in merged_sources:
        normalized = _model_registry_entry(item)
        if not normalized or normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        merged_registry.append(normalized)
    config.set("model_catalog.custom_models", merged_registry)


def register_custom_model(
    provider: str,
    model: str,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    headers: Optional[Dict] = None
) -> Dict:
    provider = str(provider or "").strip()
    model = str(model or "").strip()
    if not provider or not model:
        emit_error("接入模型时必须提供 provider 和 model")

    if not require_writable("接入自定义模型"):
        return {}

    model_config = _normalize_model_config({
        "source": "custom_api",
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key_env": api_key_env,
        "headers": headers or {},
        "temperature": temperature,
        "max_tokens": max_tokens
    })
    _register_custom_model(model_config)
    log_operation("register_custom_model", provider, "agent", {
        "provider": provider,
        "model": model
    })
    return _model_registry_entry(model_config) or model_config


def _new_agent_record(template: Dict) -> Dict:
    return {
        "agent_id": template["agent_id"],
        "catalog_pack": template.get("pack", get_agent_pack()),
        "name": template["name"],
        "role": template["role"],
        "agent_type": template.get("agent_type", "sub"),
        "parent_agent_id": template.get("parent_agent_id"),
        "description": template.get("description"),
        "capabilities": template.get("capabilities", []),
        "status": "idle",
        "status_label": STATUS_LABELS["idle"],
        "managed_agent_ids": [],
        "current_task_id": None,
        "current_task_title": None,
        "task_state": None,
        "task_level": None,
        "progress": 0,
        "current_assignment_id": None,
        "current_assignment_title": None,
        "assigned_by": None,
        "last_message": "等待分配任务",
        "updated_at": None,
        "history": [],
        "model_config": _default_model_config()
    }


def _resolve_model_config(agent: Dict) -> Dict:
    agent_model = _normalize_model_config(agent.get("model_config"))
    source = agent_model.get("source", "default")

    if source == "custom_api":
        effective = agent_model
        origin = "agent_override"
    elif source == "platform_default":
        effective = _normalize_model_config({"source": "platform_default"})
        origin = "agent_forced_platform"
    else:
        effective = get_default_model_config()
        origin = "config_default"

    effective["origin"] = origin
    effective["display"] = model_display(effective)
    return effective


def _persist_agent(agent: Dict) -> None:
    payload = copy.deepcopy(agent)
    payload.pop("effective_model", None)
    payload["catalog_pack"] = resolve_pack(payload.get("catalog_pack", get_agent_pack()))
    storage = _agent_storage()
    storage.save(_agent_storage_key(agent["agent_id"], payload["catalog_pack"]), payload)
    if payload["catalog_pack"] == "default" and storage.exists(agent["agent_id"]):
        storage.delete(agent["agent_id"])


def _append_history(agent: Dict, event: Dict) -> None:
    history = list(agent.get("history", []))
    history.append(event)
    agent["history"] = history[-20:]


def _merge_agent(template: Dict, stored: Optional[Dict]) -> Dict:
    agent = _new_agent_record(template)
    if stored:
        agent.update(stored)
    agent["catalog_pack"] = template.get("pack", get_agent_pack())
    agent["agent_type"] = agent.get("agent_type", template.get("agent_type", "sub"))
    agent["parent_agent_id"] = agent.get("parent_agent_id", template.get("parent_agent_id"))
    agent["capabilities"] = stored.get("capabilities", agent["capabilities"]) if stored else agent["capabilities"]
    agent["model_config"] = _normalize_model_config(agent.get("model_config"))
    agent["status_label"] = STATUS_LABELS.get(agent.get("status", "idle"), agent.get("status", "idle"))
    agent["effective_model"] = _resolve_model_config(agent)
    return agent


def materialize_agent(agent_id: str) -> Optional[Dict]:
    builtin = _builtin_agent_map().get(agent_id)
    if not builtin:
        return None
    return _merge_agent(builtin, None)


def load_agent(agent_id: str) -> Optional[Dict]:
    current_pack = get_agent_pack()
    stored = _load_stored_agent_record(agent_id, current_pack)
    builtin = _builtin_agent_map().get(agent_id)

    if builtin:
        return _merge_agent(builtin, stored)
    if stored:
        template = {
            "agent_id": agent_id,
            "pack": current_pack,
            "name": stored.get("name", agent_id),
            "role": stored.get("role", "custom"),
            "agent_type": stored.get("agent_type", "sub"),
            "parent_agent_id": stored.get("parent_agent_id"),
            "description": stored.get("description"),
            "capabilities": stored.get("capabilities", [])
        }
        return _merge_agent(template, stored)
    return None


def list_agents() -> List[Dict]:
    storage = _agent_storage()
    current_pack = get_agent_pack()
    builtin_ids = [agent["agent_id"] for agent in _load_default_agents(strict=True, pack=current_pack)]
    stored_ids = {key.split("/", 1)[1] for key in storage.list(f"{current_pack}/*")}

    if current_pack == "default":
        for key in storage.list("*"):
            if "/" in key:
                continue
            stored_ids.add(key)

    ordered_ids = builtin_ids + sorted(stored_ids - set(builtin_ids))

    agents = []
    for agent_id in ordered_ids:
        agent = load_agent(agent_id)
        if agent:
            agents.append(agent)

    children_map: Dict[str, List[str]] = {}
    for agent in agents:
        parent_id = agent.get("parent_agent_id")
        if parent_id:
            children_map.setdefault(parent_id, []).append(agent["agent_id"])

    for agent in agents:
        agent["managed_agent_ids"] = children_map.get(agent["agent_id"], [])

    return agents


def initialize_agents() -> Dict:
    if not require_writable("初始化 agent 注册表"):
        return {}

    current_pack = get_agent_pack()
    created = []
    catalog = _load_default_agents(strict=True, pack=current_pack)
    for builtin in catalog:
        if not _load_stored_agent_record(builtin["agent_id"], current_pack):
            _persist_agent(_new_agent_record(builtin))
            created.append(builtin["agent_id"])

    result = {
        "pack": current_pack,
        "created": created,
        "total": len(catalog),
        "main_agent_id": next((agent["agent_id"] for agent in catalog if agent["agent_type"] == "main"), None)
    }
    log_operation("init_registry", "agents", "agent", result)
    return result


def _enrich_assignment(assignment: Optional[Dict]) -> Optional[Dict]:
    if not assignment:
        return None
    enriched = copy.deepcopy(assignment)
    enriched["status_label"] = ASSIGNMENT_STATUS_LABELS.get(enriched.get("status", "queued"), enriched.get("status", "queued"))
    return enriched


def load_assignment(assignment_id: str) -> Optional[Dict]:
    return _enrich_assignment(_assignment_storage().load(assignment_id))


def list_assignments(
    from_agent_id: Optional[str] = None,
    to_agent_id: Optional[str] = None,
    include_closed: bool = True
) -> List[Dict]:
    assignments = []
    storage = _assignment_storage()
    current_pack = get_agent_pack()
    for key in storage.list("*"):
        assignment = load_assignment(key)
        if not assignment:
            continue
        assignment_pack = resolve_pack(assignment.get("catalog_pack", "default"))
        if assignment_pack != current_pack:
            continue
        if from_agent_id and assignment.get("from_agent_id") != from_agent_id:
            continue
        if to_agent_id and assignment.get("to_agent_id") != to_agent_id:
            continue
        if not include_closed and assignment.get("status") in {"done", "canceled"}:
            continue
        assignments.append(assignment)

    assignments.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
    return assignments


def _assignment_status_from_agent(agent_status: str) -> Optional[str]:
    mapping = {
        "waiting": "queued",
        "running": "running",
        "blocked": "blocked",
        "offline": "blocked",
        "completed": "done"
    }
    return mapping.get(agent_status)


def _sync_assignment_from_agent(agent: Dict, message: Optional[str] = None) -> None:
    assignment_id = agent.get("current_assignment_id")
    if not assignment_id:
        return

    storage = _assignment_storage()
    assignment = storage.load(assignment_id)
    if not assignment:
        return

    now = datetime.now().isoformat()
    mapped_status = _assignment_status_from_agent(agent.get("status", "idle"))
    if mapped_status:
        assignment["status"] = mapped_status
        assignment["status_label"] = ASSIGNMENT_STATUS_LABELS[mapped_status]
    assignment["assignee_status"] = agent.get("status")
    assignment["progress"] = agent.get("progress", assignment.get("progress", 0))
    assignment["last_message"] = message or agent.get("last_message")
    assignment["updated_at"] = now
    if agent.get("current_task_id"):
        assignment["task_id"] = agent.get("current_task_id")
        assignment["task_title"] = agent.get("current_task_title")
    if assignment.get("status") == "done":
        assignment["completed_at"] = now
    storage.save(assignment_id, assignment)


def update_agent_status(
    agent_id: str,
    status: str,
    task_id: Optional[str] = None,
    task_title: Optional[str] = None,
    task_state: Optional[str] = None,
    task_level: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    origin: str = "manual",
    assignment_id: Optional[str] = None,
    assigned_by: Optional[str] = None
) -> Dict:
    if status not in AGENT_STATUSES:
        emit_error(f"无效状态: {status}，必须是 {', '.join(AGENT_STATUSES)}")

    if not require_writable("更新 agent 状态"):
        return {}

    with _agent_lock(agent_id):
        agent = load_agent(agent_id)
        if not agent:
            emit_error(f"agent {agent_id} 不存在")

        now = datetime.now().isoformat()
        agent["status"] = status
        agent["status_label"] = STATUS_LABELS[status]

        if task_id is not None:
            agent["current_task_id"] = task_id
        if task_title is not None:
            agent["current_task_title"] = task_title
        if task_state is not None:
            agent["task_state"] = task_state
        if task_level is not None:
            agent["task_level"] = task_level
        if progress is not None:
            agent["progress"] = progress

        if assignment_id is not None:
            agent["current_assignment_id"] = assignment_id
            assignment = load_assignment(assignment_id)
            agent["current_assignment_title"] = assignment.get("title") if assignment else assignment_id
        elif status == "idle":
            agent["current_assignment_id"] = None
            agent["current_assignment_title"] = None
            agent["assigned_by"] = None

        if assigned_by is not None:
            agent["assigned_by"] = assigned_by

        if status == "idle" and task_id is None:
            agent["current_task_id"] = None
            agent["current_task_title"] = None
            agent["task_state"] = None
            agent["task_level"] = None
            agent["progress"] = 0

        if message:
            agent["last_message"] = message
        elif status == "idle":
            agent["last_message"] = "等待分配任务"

        agent["updated_at"] = now

        _append_history(agent, {
            "status": status,
            "task_id": agent.get("current_task_id"),
            "assignment_id": agent.get("current_assignment_id"),
            "message": message,
            "origin": origin,
            "timestamp": now
        })

        _persist_agent(agent)
    _sync_assignment_from_agent(agent, message)
    log_operation("status", agent_id, "agent", {
        "status": status,
        "task_id": agent.get("current_task_id"),
        "assignment_id": agent.get("current_assignment_id"),
        "origin": origin
    })
    return load_agent(agent_id) or agent


def dispatch_assignment(
    from_agent_id: str,
    to_agent_id: str,
    title: str,
    brief: str,
    task_id: Optional[str] = None,
    task_title: Optional[str] = None,
    auto_start: bool = False
) -> Dict:
    if from_agent_id == to_agent_id:
        emit_error("主 agent 不能给自己派发任务")

    if not require_writable("派发 sub-agent 任务"):
        return {}

    from_agent = load_agent(from_agent_id)
    to_agent = load_agent(to_agent_id)
    if not from_agent:
        emit_error(f"派发方 agent {from_agent_id} 不存在")
    if not to_agent:
        emit_error(f"接收方 agent {to_agent_id} 不存在")

    now = datetime.now().isoformat()
    assignment_id = generate_assignment_id()
    assignment = {
        "assignment_id": assignment_id,
        "catalog_pack": get_agent_pack(),
        "title": title,
        "brief": brief,
        "task_id": task_id,
        "task_title": task_title,
        "from_agent_id": from_agent_id,
        "from_agent_name": from_agent.get("name"),
        "to_agent_id": to_agent_id,
        "to_agent_name": to_agent.get("name"),
        "status": "running" if auto_start else "queued",
        "status_label": ASSIGNMENT_STATUS_LABELS["running" if auto_start else "queued"],
        "progress": 0,
        "last_message": brief,
        "assignee_status": "running" if auto_start else "waiting",
        "model_snapshot": {
            "dispatcher": from_agent.get("effective_model", {}).get("display"),
            "executor": to_agent.get("effective_model", {}).get("display")
        },
        "created_at": now,
        "updated_at": now,
        "completed_at": None
    }
    _assignment_storage().save(assignment_id, assignment)

    dispatch_message = f"来自 {from_agent.get('name')} 的派发：{title}"
    update_agent_status(
        agent_id=to_agent_id,
        status="running" if auto_start else "waiting",
        task_id=task_id,
        task_title=task_title or title,
        progress=0,
        message=dispatch_message,
        origin="dispatch",
        assignment_id=assignment_id,
        assigned_by=from_agent_id
    )

    dispatcher_status = from_agent.get("status")
    if dispatcher_status in {"idle", "waiting", "completed"}:
        dispatcher_status = "running"
    update_agent_status(
        agent_id=from_agent_id,
        status=dispatcher_status,
        message=f"已派发 {assignment_id} 给 {to_agent.get('name')}",
        origin="dispatch"
    )

    log_operation("dispatch", assignment_id, "assignment", {
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "task_id": task_id,
        "title": title
    })
    return load_assignment(assignment_id) or assignment


def _infer_status_from_task_state(task_state: Optional[str]) -> str:
    if task_state in {"completed"}:
        return "completed"
    if task_state in {"blocked", "escalated"}:
        return "blocked"
    if task_state in {"in_strategy", "in_execution", "in_debate", "assessed"}:
        return "running"
    if task_state == "created":
        return "waiting"
    return "idle"


def find_agent_id_by_actor(actor: Optional[str]) -> Optional[str]:
    if not actor:
        return None

    actor_text = actor.strip().lower()
    aliases = _agent_aliases(strict=True)
    for agent in list_agents():
        candidates = [
            agent["agent_id"],
            agent.get("name", ""),
            agent.get("role", "")
        ] + aliases.get(agent["agent_id"], [])
        for candidate in candidates:
            candidate_text = str(candidate).strip().lower()
            if candidate_text and (actor_text == candidate_text or candidate_text in actor_text):
                return agent["agent_id"]
    return None


def sync_agent_from_task(
    task: Dict,
    actor: Optional[str] = None,
    agent_id: Optional[str] = None,
    message: Optional[str] = None
) -> Optional[Dict]:
    resolved_agent_id = agent_id or find_agent_id_by_actor(actor)
    if not resolved_agent_id:
        return None

    status = _infer_status_from_task_state(task.get("state"))
    return update_agent_status(
        agent_id=resolved_agent_id,
        status=status,
        task_id=task.get("task_id"),
        task_title=task.get("title"),
        task_state=task.get("state"),
        task_level=task.get("level"),
        progress=task.get("progress"),
        message=message or task.get("title"),
        origin="task_flow"
    )


def set_agent_model(
    agent_id: str,
    source: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    headers: Optional[Dict] = None
) -> Dict:
    if source not in {"default", "platform_default", "custom_api"}:
        emit_error("source 必须是 default / platform_default / custom_api")
    if source == "custom_api" and (not provider or not model):
        emit_error("custom_api 模式必须提供 provider 和 model")

    if not require_writable("设置 agent 模型"):
        return {}

    agent = load_agent(agent_id)
    if not agent:
        emit_error(f"agent {agent_id} 不存在")

    agent["model_config"] = _normalize_model_config({
        "source": source,
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key_env": api_key_env,
        "headers": headers or {},
        "temperature": temperature,
        "max_tokens": max_tokens
    })
    if source == "custom_api":
        _register_custom_model(agent["model_config"])
    agent["updated_at"] = datetime.now().isoformat()
    _persist_agent(agent)
    log_operation("set_model", agent_id, "agent", {
        "source": source,
        "provider": provider,
        "model": model
    })
    return load_agent(agent_id) or agent


def set_default_model(
    source: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key_env: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    headers: Optional[Dict] = None
) -> Dict:
    if source not in {"platform_default", "custom_api"}:
        emit_error("默认模型 source 必须是 platform_default 或 custom_api")
    if source == "custom_api" and (not provider or not model):
        emit_error("custom_api 模式必须提供 provider 和 model")

    if not require_writable("设置默认模型"):
        return {}

    model_config = _normalize_model_config({
        "source": source,
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key_env": api_key_env,
        "headers": headers or {},
        "temperature": temperature,
        "max_tokens": max_tokens
    })
    if source == "custom_api":
        _register_custom_model(model_config)
    get_config().set("agent_defaults.model", model_config)
    log_operation("set_default_model", "default", "agent", model_config)
    return model_config


def switch_agent_pack(pack: str) -> Dict:
    available_packs = list_agent_packs()
    selected_pack = resolve_pack(pack)
    if selected_pack not in available_packs:
        emit_error(f"角色 pack `{selected_pack}` 不存在，可用 pack: {', '.join(available_packs) or '无'}")

    catalog = _load_default_agents(strict=True, pack=selected_pack)
    main_agent_id = next((agent["agent_id"] for agent in catalog if agent["agent_type"] == "main"), None)

    config = get_config()
    config.set("orchestration.agent_pack", selected_pack)
    if main_agent_id:
        config.set("orchestration.main_agent_id", main_agent_id)

    init_result = initialize_agents()
    result = {
        "pack": selected_pack,
        "available_packs": available_packs,
        "main_agent_id": main_agent_id,
        "created": init_result.get("created", []),
        "total": init_result.get("total", len(catalog))
    }
    log_operation("switch_pack", selected_pack, "agent", result)
    return result


def emit_agent(agent_id: str):
    agent = load_agent(agent_id)
    if not agent:
        emit_error(f"agent {agent_id} 不存在")
    emit_json(True, agent=agent)


def emit_agents():
    agents = list_agents()
    emit_json(True, count=len(agents), agents=agents, main_agent_id=get_main_agent_id(), pack=get_agent_pack())


def emit_packs():
    emit_json(True, packs=list_agent_packs(), current_pack=get_agent_pack())


def emit_assignment(assignment_id: str):
    assignment = load_assignment(assignment_id)
    if not assignment:
        emit_error(f"assignment {assignment_id} 不存在")
    emit_json(True, assignment=assignment)


def emit_assignments(from_agent_id: Optional[str], to_agent_id: Optional[str], include_closed: bool):
    assignments = list_assignments(from_agent_id=from_agent_id, to_agent_id=to_agent_id, include_closed=include_closed)
    emit_json(True, count=len(assignments), assignments=assignments)


def emit_resolved_model(agent_id: str):
    agent = load_agent(agent_id)
    if not agent:
        emit_error(f"agent {agent_id} 不存在")
    emit_json(True, agent_id=agent_id, model=agent["effective_model"])


def emit_orchestration_recommendation(
    task_id: Optional[str],
    level: Optional[str],
    profile: Optional[str],
    title: Optional[str],
    ceo_input: Optional[str],
    reason: Optional[str]
):
    task = load_task_record(task_id) if task_id else None
    if task_id and not task:
        emit_error(f"任务 {task_id} 不存在")

    plan = describe_orchestration_plan(
        task=task,
        level=level,
        requested_profile=profile,
        title=title,
        ceo_input=ceo_input,
        reason=reason
    )
    emit_json(True, recommendation=plan)


def _parse_headers(headers_text: Optional[str]) -> Dict:
    if not headers_text:
        return {}
    try:
        parsed = json.loads(headers_text)
    except json.JSONDecodeError as exc:
        emit_error(f"headers 不是合法 JSON: {exc}")
    if not isinstance(parsed, dict):
        emit_error("headers 必须是 JSON 对象")
    return parsed


def main():
    parser = argparse.ArgumentParser(description="OPC Team 主从 agent 管理")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="初始化默认主从 agent 注册表")
    subparsers.add_parser("list", help="列出所有 agent")
    subparsers.add_parser("list-packs", help="列出可用角色 pack")

    switch_pack_parser = subparsers.add_parser("switch-pack", help="切换当前角色 pack")
    switch_pack_parser.add_argument("--pack", required=True, help="目标角色 pack")

    get_parser = subparsers.add_parser("get", help="查看 agent 详情")
    get_parser.add_argument("--agent-id", required=True, help="agent ID")

    status_parser = subparsers.add_parser("set-status", help="更新 agent 状态")
    status_parser.add_argument("--agent-id", required=True, help="agent ID")
    status_parser.add_argument("--status", required=True, choices=AGENT_STATUSES, help="agent 状态")
    status_parser.add_argument("--task-id", help="当前任务 ID")
    status_parser.add_argument("--task-title", help="当前任务标题")
    status_parser.add_argument("--task-state", help="任务状态")
    status_parser.add_argument("--task-level", help="任务等级")
    status_parser.add_argument("--progress", type=int, help="任务进度")
    status_parser.add_argument("--message", help="状态说明")
    status_parser.add_argument("--assignment-id", help="当前派发任务 ID")
    status_parser.add_argument("--assigned-by", help="派发方 agent ID")

    dispatch_parser = subparsers.add_parser("dispatch", help="主 agent 给 sub-agent 派发任务")
    dispatch_parser.add_argument("--from-agent", required=True, help="派发方 agent ID")
    dispatch_parser.add_argument("--to-agent", required=True, help="接收方 agent ID")
    dispatch_parser.add_argument("--title", required=True, help="派发标题")
    dispatch_parser.add_argument("--brief", required=True, help="任务简报")
    dispatch_parser.add_argument("--task-id", help="关联任务 ID")
    dispatch_parser.add_argument("--task-title", help="关联任务标题")
    dispatch_parser.add_argument("--auto-start", action="store_true", help="派发后直接进入 running")

    list_assignments_parser = subparsers.add_parser("list-assignments", help="列出派发任务")
    list_assignments_parser.add_argument("--from-agent", help="按派发方过滤")
    list_assignments_parser.add_argument("--to-agent", help="按接收方过滤")
    list_assignments_parser.add_argument("--open-only", action="store_true", help="只看未关闭派发")

    get_assignment_parser = subparsers.add_parser("get-assignment", help="查看派发任务详情")
    get_assignment_parser.add_argument("--assignment-id", required=True, help="派发任务 ID")

    model_parser = subparsers.add_parser("set-model", help="配置某个 agent 的模型")
    model_parser.add_argument("--agent-id", required=True, help="agent ID")
    model_parser.add_argument("--source", required=True, choices=["default", "platform_default", "custom_api"], help="模型来源")
    model_parser.add_argument("--provider", help="provider，例如 openai / anthropic / deepseek")
    model_parser.add_argument("--model", help="模型名")
    model_parser.add_argument("--api-base", help="自定义 API Base")
    model_parser.add_argument("--api-key-env", help="API Key 对应环境变量名")
    model_parser.add_argument("--temperature", type=float, help="采样温度")
    model_parser.add_argument("--max-tokens", type=int, help="最大输出 token")
    model_parser.add_argument("--headers", help="附加请求头 JSON")

    default_model_parser = subparsers.add_parser("set-default-model", help="设置全局默认模型路由")
    default_model_parser.add_argument("--source", required=True, choices=["platform_default", "custom_api"], help="默认模型来源")
    default_model_parser.add_argument("--provider", help="provider")
    default_model_parser.add_argument("--model", help="模型名")
    default_model_parser.add_argument("--api-base", help="自定义 API Base")
    default_model_parser.add_argument("--api-key-env", help="API Key 对应环境变量名")
    default_model_parser.add_argument("--temperature", type=float, help="采样温度")
    default_model_parser.add_argument("--max-tokens", type=int, help="最大输出 token")
    default_model_parser.add_argument("--headers", help="附加请求头 JSON")

    resolve_parser = subparsers.add_parser("resolve-model", help="查看 agent 的最终模型配置")
    resolve_parser.add_argument("--agent-id", required=True, help="agent ID")

    recommend_parser = subparsers.add_parser("recommend", help="根据任务级别或显式档位推荐编组规模")
    recommend_parser.add_argument("--task-id", help="任务 ID")
    recommend_parser.add_argument("--level", choices=["L1", "L2", "L3", "L4"], help="任务级别")
    recommend_parser.add_argument("--profile", choices=["daily", "important", "full"], help="显式指定编组档位")
    recommend_parser.add_argument("--title", help="任务标题")
    recommend_parser.add_argument("--ceo-input", help="原始 CEO 输入")
    recommend_parser.add_argument("--reason", help="补充说明或定级原因")

    args = parser.parse_args()

    if args.command == "init":
        result = initialize_agents()
        emit_json(True, **result, message="主从 agent 注册表初始化完成")
    elif args.command == "list":
        emit_agents()
    elif args.command == "list-packs":
        emit_packs()
    elif args.command == "switch-pack":
        result = switch_agent_pack(args.pack)
        emit_json(True, **result, message=f"已切换到角色 pack: {result['pack']}")
    elif args.command == "get":
        emit_agent(args.agent_id)
    elif args.command == "set-status":
        agent = update_agent_status(
            agent_id=args.agent_id,
            status=args.status,
            task_id=args.task_id,
            task_title=args.task_title,
            task_state=args.task_state,
            task_level=args.task_level,
            progress=args.progress,
            message=args.message,
            assignment_id=args.assignment_id,
            assigned_by=args.assigned_by
        )
        emit_json(True, agent=agent, message=f"agent {args.agent_id} 状态已更新")
    elif args.command == "dispatch":
        assignment = dispatch_assignment(
            from_agent_id=args.from_agent,
            to_agent_id=args.to_agent,
            title=args.title,
            brief=args.brief,
            task_id=args.task_id,
            task_title=args.task_title,
            auto_start=args.auto_start
        )
        emit_json(True, assignment=assignment, message=f"派发任务 {assignment['assignment_id']} 已创建")
    elif args.command == "list-assignments":
        emit_assignments(args.from_agent, args.to_agent, include_closed=not args.open_only)
    elif args.command == "get-assignment":
        emit_assignment(args.assignment_id)
    elif args.command == "set-model":
        agent = set_agent_model(
            agent_id=args.agent_id,
            source=args.source,
            provider=args.provider,
            model=args.model,
            api_base=args.api_base,
            api_key_env=args.api_key_env,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            headers=_parse_headers(args.headers)
        )
        emit_json(True, agent=agent, message=f"agent {args.agent_id} 模型配置已更新")
    elif args.command == "set-default-model":
        model_config = set_default_model(
            source=args.source,
            provider=args.provider,
            model=args.model,
            api_base=args.api_base,
            api_key_env=args.api_key_env,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            headers=_parse_headers(args.headers)
        )
        emit_json(True, model=model_config, message="全局默认模型配置已更新")
    elif args.command == "resolve-model":
        emit_resolved_model(args.agent_id)
    elif args.command == "recommend":
        emit_orchestration_recommendation(
            task_id=args.task_id,
            level=args.level,
            profile=args.profile,
            title=args.title,
            ceo_input=args.ceo_input,
            reason=args.reason
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
