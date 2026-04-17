#!/usr/bin/env python3
"""
dashboard.py - OPC Team 主从 Agent 集成看板

功能：
- 聚合 tasks / decisions / risks / agents / assignments 数据
- 导出看板摘要 JSON
- 提供本地 HTTP 服务
- 支持从看板直接派发任务、调整状态和模型路由
"""

import argparse
import json
import mimetypes
from collections import Counter, defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from agent_catalog import list_agent_packs
from agent_ops import (
    dispatch_assignment,
    get_default_model_config,
    get_agent_pack,
    get_main_agent_id,
    list_agents,
    list_assignments,
    list_registered_custom_models,
    register_custom_model,
    set_agent_model,
    set_default_model,
    update_agent_status
)
from config import get_config
from storage import get_storage
from task_flow import SLA_LIMITS, TaskLevel


REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ROOT = REPO_ROOT / "dashboard"


def _entity_storage(storage_type: str, path_key: str):
    config = get_config()
    return get_storage(storage_type, {
        "backend": config.get("storage.backend", "file"),
        "base_dir": config.get_path(path_key),
        "use_lock": config.get("storage.file_lock", True),
        "auto_backup": config.get("storage.auto_backup", False)
    })


def _load_entities(storage_type: str, path_key: str) -> List[Dict]:
    storage = _entity_storage(storage_type, path_key)
    items = []
    for key in storage.list("*"):
        item = storage.load(key)
        if item:
            items.append(item)
    return items


def _safe_iso(dt_text: Optional[str]) -> datetime:
    if not dt_text:
        return datetime.min
    try:
        return datetime.fromisoformat(dt_text)
    except ValueError:
        return datetime.min


def _task_sla_status(task: Dict) -> str:
    level_value = task.get("level")
    if not level_value:
        return "未定级"

    try:
        level = TaskLevel(level_value)
    except ValueError:
        return "未知"

    sla_limit = SLA_LIMITS.get(level)
    if not sla_limit:
        return "未知"

    created_at = _safe_iso(task.get("created_at"))
    if created_at == datetime.min:
        return "未知"

    elapsed = datetime.now() - created_at
    if elapsed > sla_limit * 2:
        return "严重超期"
    if elapsed > sla_limit:
        return "超期"
    return "正常"


def _recent_events(limit: int = 14) -> List[Dict]:
    log_dir = get_config().get_path("logs_dir")
    if not log_dir.exists():
        return []

    events = []
    for log_file in sorted(log_dir.glob("*.log"), reverse=True)[:3]:
        try:
            with open(log_file, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    events.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return events[:limit]


def build_summary() -> Dict:
    config = get_config()
    tasks = _load_entities("tasks", "tasks_dir")
    decisions = _load_entities("decisions", "decisions_dir")
    risks = _load_entities("risks", "risks_dir")
    agents = list_agents()
    assignments = list_assignments()

    tasks.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
    task_map = {task["task_id"]: task for task in tasks if task.get("task_id")}
    assignment_map = {assignment["assignment_id"]: assignment for assignment in assignments}

    decisions_by_task = Counter()
    for decision in decisions:
        task_id = decision.get("task_id")
        if task_id:
            decisions_by_task[task_id] += 1

    risks_by_task = Counter()
    high_risks_by_task = Counter()
    for risk in risks:
        task_id = risk.get("task_id")
        if not task_id:
            continue
        risks_by_task[task_id] += 1
        if int(risk.get("level", 0) or 0) >= 4:
            high_risks_by_task[task_id] += 1

    assignments_by_task = defaultdict(list)
    assignments_by_agent = defaultdict(list)
    dispatch_count_by_agent = Counter()
    for assignment in assignments:
        task_id = assignment.get("task_id")
        if task_id:
            assignments_by_task[task_id].append({
                "assignment_id": assignment["assignment_id"],
                "title": assignment.get("title"),
                "to_agent_name": assignment.get("to_agent_name"),
                "status": assignment.get("status"),
                "status_label": assignment.get("status_label")
            })
        assignments_by_agent[assignment.get("to_agent_id")].append(assignment)
        dispatch_count_by_agent[assignment.get("from_agent_id")] += 1

    agents_by_task = defaultdict(list)
    enriched_agents = []
    main_agent_id = get_main_agent_id()

    for agent in agents:
        current_task_id = agent.get("current_task_id")
        task = task_map.get(current_task_id) if current_task_id else None
        current_assignment = assignment_map.get(agent.get("current_assignment_id"))

        if task:
            agent["current_task_title"] = task.get("title")
            agent["task_state"] = task.get("state")
            agent["task_level"] = task.get("level")
            agent["progress"] = task.get("progress", agent.get("progress"))
            agents_by_task[current_task_id].append({
                "agent_id": agent["agent_id"],
                "name": agent.get("name"),
                "status": agent.get("status"),
                "status_label": agent.get("status_label")
            })

        agent["risk_count"] = risks_by_task.get(current_task_id, 0)
        agent["high_risk_count"] = high_risks_by_task.get(current_task_id, 0)
        agent["dispatch_count"] = dispatch_count_by_agent.get(agent["agent_id"], 0)
        agent["open_assignments"] = sum(
            1 for item in assignments_by_agent.get(agent["agent_id"], [])
            if item.get("status") in {"queued", "running", "blocked"}
        )
        agent["current_assignment"] = current_assignment
        agent["is_main_agent"] = agent["agent_id"] == main_agent_id
        enriched_agents.append(agent)

    task_cards = []
    for task in tasks:
        task_id = task["task_id"]
        task_cards.append({
            "task_id": task_id,
            "title": task.get("title"),
            "state": task.get("state"),
            "level": task.get("level"),
            "progress": task.get("progress", 0),
            "sla_status": _task_sla_status(task),
            "updated_at": task.get("updated_at"),
            "created_at": task.get("created_at"),
            "decision_count": decisions_by_task.get(task_id, 0),
            "risk_count": risks_by_task.get(task_id, 0),
            "high_risk_count": high_risks_by_task.get(task_id, 0),
            "agents": agents_by_task.get(task_id, []),
            "assignments": assignments_by_task.get(task_id, []),
            "latest_progress": (task.get("progress_log") or [{}])[-1] if task.get("progress_log") else None
        })

    task_states = Counter(task.get("state", "unknown") for task in tasks)
    agent_states = Counter(agent.get("status", "unknown") for agent in enriched_agents)
    assignment_states = Counter(assignment.get("status", "unknown") for assignment in assignments)
    main_agent = next((agent for agent in enriched_agents if agent["agent_id"] == main_agent_id), None)
    custom_models = list_registered_custom_models()

    return {
        "generated_at": datetime.now().isoformat(),
        "refresh_seconds": config.get("dashboard.refresh_seconds", 8),
        "defaults": {
            "main_agent_id": main_agent_id,
            "default_model": get_default_model_config()
        },
        "catalog": {
            "current_pack": get_agent_pack(),
            "available_packs": list_agent_packs()
        },
        "model_catalog": {
            "custom_models": custom_models,
            "switching_enabled": bool(custom_models)
        },
        "metrics": {
            "agents_total": len(enriched_agents),
            "sub_agents_total": sum(1 for agent in enriched_agents if agent.get("agent_type") == "sub"),
            "agents_active": sum(1 for agent in enriched_agents if agent.get("status") in {"running", "waiting", "blocked"}),
            "tasks_total": len(tasks),
            "tasks_in_progress": sum(1 for task in tasks if task.get("state") in {"in_strategy", "in_execution", "in_debate", "assessed"}),
            "tasks_blocked": task_states.get("blocked", 0) + task_states.get("escalated", 0),
            "high_risk_tasks": sum(1 for task_id in task_map if high_risks_by_task.get(task_id, 0) > 0),
            "assignments_open": sum(1 for assignment in assignments if assignment.get("status") in {"queued", "running", "blocked"})
        },
        "state_breakdown": {
            "tasks": dict(task_states),
            "agents": dict(agent_states),
            "assignments": dict(assignment_states)
        },
        "main_agent": main_agent,
        "agents": enriched_agents,
        "tasks": task_cards,
        "assignments": assignments[:16],
        "events": _recent_events()
    }


def export_summary(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(build_summary(), handle, ensure_ascii=False, indent=2)
    return output_path


def _coerce_optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _coerce_optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs), None
    except SystemExit:
        return None, "操作失败，请检查输入参数。"
    except Exception as exc:  # pragma: no cover - 防御性兜底
        return None, str(exc)


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: Dict, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"success": False, "error": "not found"}, status=404)
            return

        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> Dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"success": False, "error": "invalid json"}, status=400)
            raise ValueError("invalid json")
        if not isinstance(payload, dict):
            self._send_json({"success": False, "error": "json body must be an object"}, status=400)
            raise ValueError("invalid body")
        return payload

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/summary":
            self._send_json(build_summary())
            return

        if path == "/api/health":
            self._send_json({"success": True, "status": "ok", "generated_at": datetime.now().isoformat()})
            return

        if path in {"/", ""}:
            self._send_file(DASHBOARD_ROOT / "index.html")
            return

        candidate = (DASHBOARD_ROOT / path.lstrip("/")).resolve()
        if DASHBOARD_ROOT.resolve() not in candidate.parents and candidate != DASHBOARD_ROOT.resolve():
            self._send_json({"success": False, "error": "forbidden"}, status=403)
            return

        self._send_file(candidate)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [part for part in path.split("/") if part]

        try:
            payload = self._read_json()
        except ValueError:
            return

        if path == "/api/dispatch":
            result, error = _safe_call(
                dispatch_assignment,
                from_agent_id=payload.get("from_agent"),
                to_agent_id=payload.get("to_agent"),
                title=payload.get("title"),
                brief=payload.get("brief"),
                task_id=payload.get("task_id") or None,
                task_title=payload.get("task_title") or None,
                auto_start=bool(payload.get("auto_start"))
            )
            if error:
                self._send_json({"success": False, "error": error}, status=400)
            else:
                self._send_json({"success": True, "assignment": result, "summary": build_summary()})
            return

        if path == "/api/default-model":
            result, error = _safe_call(
                set_default_model,
                source=payload.get("source"),
                provider=payload.get("provider") or None,
                model=payload.get("model") or None,
                api_base=payload.get("api_base") or None,
                api_key_env=payload.get("api_key_env") or None,
                temperature=_coerce_optional_float(payload.get("temperature")),
                max_tokens=_coerce_optional_int(payload.get("max_tokens")),
                headers=payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
            )
            if error:
                self._send_json({"success": False, "error": error}, status=400)
            else:
                self._send_json({"success": True, "model": result, "summary": build_summary()})
            return

        if path == "/api/model-catalog":
            result, error = _safe_call(
                register_custom_model,
                provider=payload.get("provider") or None,
                model=payload.get("model") or None,
                api_base=payload.get("api_base") or None,
                api_key_env=payload.get("api_key_env") or None,
                temperature=_coerce_optional_float(payload.get("temperature")),
                max_tokens=_coerce_optional_int(payload.get("max_tokens")),
                headers=payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
            )
            if error:
                self._send_json({"success": False, "error": error}, status=400)
            else:
                self._send_json({"success": True, "model": result, "summary": build_summary()})
            return

        if len(parts) == 4 and parts[:2] == ["api", "agents"] and parts[3] == "status":
            agent_id = parts[2]
            result, error = _safe_call(
                update_agent_status,
                agent_id=agent_id,
                status=payload.get("status"),
                task_id=payload.get("task_id") or None,
                task_title=payload.get("task_title") or None,
                task_state=payload.get("task_state") or None,
                task_level=payload.get("task_level") or None,
                progress=_coerce_optional_int(payload.get("progress")),
                message=payload.get("message") or None,
                assignment_id=payload.get("assignment_id") or None,
                assigned_by=payload.get("assigned_by") or None
            )
            if error:
                self._send_json({"success": False, "error": error}, status=400)
            else:
                self._send_json({"success": True, "agent": result, "summary": build_summary()})
            return

        if len(parts) == 4 and parts[:2] == ["api", "agents"] and parts[3] == "model":
            agent_id = parts[2]
            result, error = _safe_call(
                set_agent_model,
                agent_id=agent_id,
                source=payload.get("source"),
                provider=payload.get("provider") or None,
                model=payload.get("model") or None,
                api_base=payload.get("api_base") or None,
                api_key_env=payload.get("api_key_env") or None,
                temperature=_coerce_optional_float(payload.get("temperature")),
                max_tokens=_coerce_optional_int(payload.get("max_tokens")),
                headers=payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
            )
            if error:
                self._send_json({"success": False, "error": error}, status=400)
            else:
                self._send_json({"success": True, "agent": result, "summary": build_summary()})
            return

        self._send_json({"success": False, "error": "not found"}, status=404)

    def log_message(self, format: str, *args):
        return


def serve_dashboard(host: str, port: int):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"OPC Dashboard listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOPC Dashboard stopped")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="OPC Team 主从 agent 集成看板")
    subparsers = parser.add_subparsers(dest="command")

    summary_parser = subparsers.add_parser("summary", help="输出看板摘要 JSON")
    summary_parser.add_argument("--pretty", action="store_true", help="格式化输出")

    export_parser = subparsers.add_parser("export", help="导出看板摘要 JSON 文件")
    export_parser.add_argument("--output", help="输出路径")

    serve_parser = subparsers.add_parser("serve", help="启动本地看板服务")
    serve_parser.add_argument("--host", help="监听地址")
    serve_parser.add_argument("--port", type=int, help="监听端口")

    args = parser.parse_args()
    config = get_config()

    if args.command == "summary":
        payload = build_summary()
        if args.pretty:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False))
    elif args.command == "export":
        output = Path(args.output) if args.output else config.get_path("dashboard_dir") / "summary.json"
        final_path = export_summary(output)
        print(json.dumps({
            "success": True,
            "output": str(final_path),
            "generated_at": datetime.now().isoformat()
        }, ensure_ascii=False))
    elif args.command == "serve":
        serve_dashboard(
            host=args.host or config.get("dashboard.host", "127.0.0.1"),
            port=args.port or int(config.get("dashboard.port", 8765))
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
