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

DEFAULT_AGENTS = [
    {
        "agent_id": "ceo",
        "name": "CEO主Agent",
        "role": "CEO",
        "agent_type": "main",
        "description": "主控编排代理，负责拆解任务、选择 sub-agent、汇总结果。",
        "capabilities": ["dispatch", "model_routing", "status_control", "summary"]
    },
    {
        "agent_id": "coo",
        "name": "COO魏明远",
        "role": "COO",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "承接 CEO 主 agent 的运营调度与状态推进。",
        "capabilities": ["task_assess", "task_transition", "memory_sync"]
    },
    {
        "agent_id": "strategist",
        "name": "策略官苏然",
        "role": "策略官",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "负责方案设计、关键假设与风险收敛。",
        "capabilities": ["task_progress", "decision_create", "risk_assess"]
    },
    {
        "agent_id": "product",
        "name": "产品周雨桐",
        "role": "产品",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "拆解功能范围与用户故事。",
        "capabilities": ["task_progress"]
    },
    {
        "agent_id": "marketing",
        "name": "市场陈志远",
        "role": "市场",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "验证获客路径与测试方案。",
        "capabilities": ["task_progress", "risk_assess"]
    },
    {
        "agent_id": "tech",
        "name": "技术李峥",
        "role": "技术",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "负责技术实现、约束分析与交付判断。",
        "capabilities": ["task_progress", "risk_assess"]
    },
    {
        "agent_id": "finance",
        "name": "财务张晓燕",
        "role": "财务",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "测算成本、收益与盈亏平衡点。",
        "capabilities": ["task_progress", "risk_assess"]
    },
    {
        "agent_id": "brand",
        "name": "品牌林可欣",
        "role": "品牌",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "统一叙事、表达与品牌感知。",
        "capabilities": ["task_progress"]
    },
    {
        "agent_id": "legal",
        "name": "法务王建国",
        "role": "法务",
        "agent_type": "sub",
        "parent_agent_id": "ceo",
        "description": "识别合规风险并提出规避方案。",
        "capabilities": ["task_progress", "risk_assess"]
    }
]

AGENT_ALIASES = {
    "ceo": ["ceo", "CEO", "ceo主agent", "ceo主代理"],
    "coo": ["coo", "魏明远", "coo魏明远"],
    "strategist": ["策略官", "苏然", "策略官苏然"],
    "product": ["产品", "周雨桐", "产品周雨桐"],
    "marketing": ["市场", "陈志远", "市场陈志远"],
    "tech": ["技术", "李峥", "技术李峥"],
    "finance": ["财务", "张晓燕", "财务张晓燕"],
    "brand": ["品牌", "林可欣", "品牌林可欣"],
    "legal": ["法务", "王建国", "法务王建国"]
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


def _agent_lock(agent_id: str):
    return operation_lock(get_config().get_path("agents_dir") / f".{agent_id}.lock")


def _builtin_agent_map() -> Dict[str, Dict]:
    return {agent["agent_id"]: agent for agent in DEFAULT_AGENTS}


def get_main_agent_id() -> str:
    return get_config().get("orchestration.main_agent_id", "ceo")


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


def _new_agent_record(template: Dict) -> Dict:
    return {
        "agent_id": template["agent_id"],
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
    _agent_storage().save(agent["agent_id"], payload)


def _append_history(agent: Dict, event: Dict) -> None:
    history = list(agent.get("history", []))
    history.append(event)
    agent["history"] = history[-20:]


def _merge_agent(template: Dict, stored: Optional[Dict]) -> Dict:
    agent = _new_agent_record(template)
    if stored:
        agent.update(stored)
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
    storage = _agent_storage()
    stored = storage.load(agent_id)
    builtin = _builtin_agent_map().get(agent_id)

    if builtin:
        return _merge_agent(builtin, stored)
    if stored:
        template = {
            "agent_id": agent_id,
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
    stored_keys = set(storage.list("*"))
    builtin_ids = [agent["agent_id"] for agent in DEFAULT_AGENTS]
    ordered_ids = builtin_ids + sorted(stored_keys - set(builtin_ids))

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


def initialize_agents():
    if not require_writable("初始化 agent 注册表"):
        return

    storage = _agent_storage()
    created = []
    for builtin in DEFAULT_AGENTS:
        if not storage.exists(builtin["agent_id"]):
            storage.save(builtin["agent_id"], _new_agent_record(builtin))
            created.append(builtin["agent_id"])

    log_operation("init_registry", "agents", "agent", {"created": created})
    emit_json(True, created=created, total=len(DEFAULT_AGENTS), message="主从 agent 注册表初始化完成")


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
    for key in storage.list("*"):
        assignment = load_assignment(key)
        if not assignment:
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
    for agent in list_agents():
        candidates = [
            agent["agent_id"],
            agent.get("name", ""),
            agent.get("role", "")
        ] + AGENT_ALIASES.get(agent["agent_id"], [])
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
    get_config().set("agent_defaults.model", model_config)
    log_operation("set_default_model", "default", "agent", model_config)
    return model_config


def emit_agent(agent_id: str):
    agent = load_agent(agent_id)
    if not agent:
        emit_error(f"agent {agent_id} 不存在")
    emit_json(True, agent=agent)


def emit_agents():
    agents = list_agents()
    emit_json(True, count=len(agents), agents=agents, main_agent_id=get_main_agent_id())


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

    args = parser.parse_args()

    if args.command == "init":
        initialize_agents()
    elif args.command == "list":
        emit_agents()
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
