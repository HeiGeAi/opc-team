#!/usr/bin/env python3
"""
agent_catalog.py - OPC Team 标准化角色目录

功能：
- 从 agents/*.md 或 agents/<pack>/*.md 加载标准化角色定义
- 校验 frontmatter schema 和正文章节
- 输出 JSON / Markdown manifest
- 提供 pack 发现与脚手架复制能力
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import get_config
from runtime import emit_error, emit_json


REQUIRED_KEYS = [
    "agent_id",
    "name",
    "role",
    "sort_order",
    "agent_type",
    "description",
    "capabilities",
    "aliases"
]

REQUIRED_SECTIONS = [
    "## 身份与记忆",
    "## 核心使命",
    "## 关键规则",
    "## 交付物",
    "## 工作流"
]

DEFAULT_AGENT_PACK = "default"


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _configured_pack() -> str:
    configured = str(get_config().get("orchestration.agent_pack", DEFAULT_AGENT_PACK) or DEFAULT_AGENT_PACK).strip()
    return configured or DEFAULT_AGENT_PACK


def resolve_pack(pack: Optional[str] = None) -> str:
    selected = str(pack or _configured_pack()).strip()
    return selected or DEFAULT_AGENT_PACK


def get_agents_root() -> Path:
    return get_repo_root() / "agents"


def get_agents_dir(pack: Optional[str] = None) -> Path:
    selected_pack = resolve_pack(pack)
    agents_root = get_agents_root()
    if selected_pack == DEFAULT_AGENT_PACK:
        return agents_root
    return agents_root / selected_pack


def list_agent_packs() -> List[str]:
    agents_root = get_agents_root()
    packs: List[str] = []

    if any(path.is_file() for path in agents_root.glob("*.md")):
        packs.append(DEFAULT_AGENT_PACK)

    if agents_root.exists():
        for path in sorted(item for item in agents_root.iterdir() if item.is_dir()):
            if any(child.is_file() for child in path.glob("*.md")):
                packs.append(path.name)

    return packs


def list_agent_files(pack: Optional[str] = None) -> List[Path]:
    agents_dir = get_agents_dir(pack)
    if not agents_dir.exists():
        return []
    return sorted(path for path in agents_dir.glob("*.md") if path.is_file())


def _split_frontmatter(text: str, path: Path) -> Tuple[Dict, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name}: 缺少 frontmatter 起始分隔符 ---")

    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError(f"{path.name}: 缺少 frontmatter 结束分隔符 ---")

    _, remainder = parts
    frontmatter_text = text[len("---\n"): len(text) - len(remainder) - len("\n---\n")]

    try:
        meta = json.loads(frontmatter_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: frontmatter 不是合法 JSON: {exc}") from exc

    if not isinstance(meta, dict):
        raise ValueError(f"{path.name}: frontmatter 必须是 JSON 对象")

    body = remainder.strip()
    if not body:
        raise ValueError(f"{path.name}: 缺少正文内容")

    return meta, body


def _first_meaningful_line(body: str) -> str:
    for line in body.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        return text
    return ""


def _validate_spec(meta: Dict, body: str, path: Path, seen_ids: set) -> List[str]:
    errors: List[str] = []

    for key in REQUIRED_KEYS:
        if key not in meta:
            errors.append(f"{path.name}: 缺少必填字段 {key}")

    agent_id = str(meta.get("agent_id") or "").strip()
    if not agent_id:
        errors.append(f"{path.name}: agent_id 不能为空")
    elif agent_id in seen_ids:
        errors.append(f"{path.name}: agent_id {agent_id} 重复")

    agent_type = str(meta.get("agent_type") or "").strip()
    if agent_type not in {"main", "sub"}:
        errors.append(f"{path.name}: agent_type 必须是 main 或 sub")

    sort_order = meta.get("sort_order")
    if not isinstance(sort_order, int):
        errors.append(f"{path.name}: sort_order 必须是整数")

    if agent_type == "sub" and not str(meta.get("parent_agent_id") or "").strip():
        errors.append(f"{path.name}: sub agent 必须声明 parent_agent_id")

    capabilities = meta.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(isinstance(item, str) and item.strip() for item in capabilities):
        errors.append(f"{path.name}: capabilities 必须是非空字符串数组")

    aliases = meta.get("aliases")
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item.strip() for item in aliases):
        errors.append(f"{path.name}: aliases 必须是字符串数组")

    for section in REQUIRED_SECTIONS:
        if section not in body:
            errors.append(f"{path.name}: 缺少章节 {section}")

    return errors


def _normalize_spec(meta: Dict, body: str, path: Path, pack: str) -> Dict:
    summary = _first_meaningful_line(body) or str(meta.get("description") or "").strip()
    return {
        "pack": pack,
        "agent_id": str(meta.get("agent_id") or "").strip(),
        "name": str(meta.get("name") or "").strip(),
        "role": str(meta.get("role") or "").strip(),
        "sort_order": int(meta.get("sort_order") or 0),
        "agent_type": str(meta.get("agent_type") or "").strip(),
        "parent_agent_id": (str(meta.get("parent_agent_id") or "").strip() or None),
        "description": str(meta.get("description") or "").strip(),
        "capabilities": [str(item).strip() for item in meta.get("capabilities", [])],
        "aliases": [str(item).strip() for item in meta.get("aliases", [])],
        "summary": summary,
        "body": body,
        "source_path": str(path)
    }


def load_agent_catalog(strict: bool = True, pack: Optional[str] = None) -> List[Dict]:
    selected_pack = resolve_pack(pack)
    files = list_agent_files(selected_pack)
    errors: List[str] = []
    seen_ids = set()
    agents: List[Dict] = []

    if not files:
        errors.append(f"agent pack `{selected_pack}` 下没有找到任何角色定义文件")

    for path in files:
        try:
            meta, body = _split_frontmatter(path.read_text(encoding="utf-8"), path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        spec_errors = _validate_spec(meta, body, path, seen_ids)
        if spec_errors:
            errors.extend(spec_errors)
            continue

        spec = _normalize_spec(meta, body, path, selected_pack)
        seen_ids.add(spec["agent_id"])
        agents.append(spec)

    main_ids = {agent["agent_id"] for agent in agents if agent["agent_type"] == "main"}
    if not main_ids:
        errors.append("agent catalog 至少需要一个 main agent")

    for agent in agents:
        parent_id = agent.get("parent_agent_id")
        if agent["agent_type"] == "sub" and parent_id not in main_ids and parent_id not in seen_ids:
            errors.append(f"{Path(agent['source_path']).name}: parent_agent_id {parent_id} 不存在")

    agents.sort(key=lambda item: (item["sort_order"], item["agent_id"]))

    if errors and strict:
        raise ValueError("\n".join(errors))
    return agents


def builtin_agent_map(strict: bool = True, pack: Optional[str] = None) -> Dict[str, Dict]:
    return {agent["agent_id"]: agent for agent in load_agent_catalog(strict=strict, pack=pack)}


def builtin_agent_aliases(strict: bool = True, pack: Optional[str] = None) -> Dict[str, List[str]]:
    return {
        agent["agent_id"]: list(agent.get("aliases", []))
        for agent in load_agent_catalog(strict=strict, pack=pack)
    }


def compact_catalog_entry(agent: Dict) -> Dict:
    return {
        "pack": agent.get("pack", DEFAULT_AGENT_PACK),
        "agent_id": agent["agent_id"],
        "name": agent["name"],
        "role": agent["role"],
        "sort_order": agent["sort_order"],
        "agent_type": agent["agent_type"],
        "parent_agent_id": agent.get("parent_agent_id"),
        "description": agent["description"],
        "capabilities": list(agent["capabilities"]),
        "aliases": list(agent["aliases"]),
        "summary": agent["summary"],
        "source_path": agent["source_path"]
    }


def render_markdown_manifest(agents: List[Dict], pack: Optional[str] = None) -> str:
    selected_pack = resolve_pack(pack or (agents[0]["pack"] if agents else None))
    lines = [
        f"# OPC Agent Catalog · {selected_pack}",
        "",
        "> 该目录由 `tools/agent_catalog.py` 校验，作为角色层与编排层之间的标准接口。",
        "",
        f"> 当前 pack：`{selected_pack}`",
        "",
        "| agent_id | 角色 | 类型 | 上级 | 能力 |",
        "|---|---|---|---|---|"
    ]

    for agent in agents:
        parent = agent.get("parent_agent_id") or "-"
        capabilities = ", ".join(agent["capabilities"])
        lines.append(f"| `{agent['agent_id']}` | {agent['name']} | {agent['agent_type']} | `{parent}` | {capabilities} |")

    for agent in agents:
        lines.extend([
            "",
            f"## {agent['name']}",
            "",
            f"- `agent_id`: `{agent['agent_id']}`",
            f"- `role`: {agent['role']}",
            f"- `description`: {agent['description']}",
            f"- `aliases`: {', '.join(agent['aliases']) or '-'}",
            "",
            agent["summary"]
        ])

    return "\n".join(lines) + "\n"


def scaffold_agent_pack(source_pack: str, target_pack: str, force: bool = False) -> List[str]:
    normalized_source = resolve_pack(source_pack)
    normalized_target = resolve_pack(target_pack)

    if normalized_target == DEFAULT_AGENT_PACK:
        raise ValueError("目标 pack 不能是 default，请使用自定义 pack 名称")
    if normalized_source == normalized_target:
        raise ValueError("源 pack 和目标 pack 不能相同")

    source_dir = get_agents_dir(normalized_source)
    target_dir = get_agents_dir(normalized_target)

    if not source_dir.exists():
        raise ValueError(f"源 pack `{normalized_source}` 不存在")

    existing_files = list(target_dir.glob("*.md")) if target_dir.exists() else []
    if existing_files and not force:
        raise ValueError(f"目标 pack `{normalized_target}` 已存在，使用 --force 允许覆盖")

    target_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for source_file in list_agent_files(normalized_source):
        target_file = target_dir / source_file.name
        shutil.copyfile(source_file, target_file)
        written.append(str(target_file))
    return written


def _add_pack_argument(parser: argparse.ArgumentParser, required: bool = False) -> None:
    parser.add_argument("--pack", required=required, help=f"角色 pack 名称，默认使用配置中的 pack（缺省为 {DEFAULT_AGENT_PACK}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="OPC Team 角色 catalog 管理")
    subparsers = parser.add_subparsers(dest="command")

    lint_parser = subparsers.add_parser("lint", help="校验角色目录")
    _add_pack_argument(lint_parser)

    list_parser = subparsers.add_parser("list", help="列出角色目录")
    _add_pack_argument(list_parser)

    subparsers.add_parser("list-packs", help="列出可用角色 pack")

    manifest_parser = subparsers.add_parser("manifest", help="导出 manifest")
    manifest_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="输出格式")
    _add_pack_argument(manifest_parser)

    get_parser = subparsers.add_parser("get", help="查看单个角色定义")
    get_parser.add_argument("--agent-id", required=True, help="agent ID")
    _add_pack_argument(get_parser)

    scaffold_parser = subparsers.add_parser("scaffold-pack", help="从现有 pack 复制一个新 pack")
    scaffold_parser.add_argument("--from-pack", default=DEFAULT_AGENT_PACK, help="源 pack")
    scaffold_parser.add_argument("--to-pack", required=True, help="目标 pack")
    scaffold_parser.add_argument("--force", action="store_true", help="覆盖已存在的目标 pack 文件")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list-packs":
        packs = list_agent_packs()
        emit_json(True, packs=packs, current_pack=_configured_pack(), count=len(packs))
        return

    if args.command == "scaffold-pack":
        try:
            written = scaffold_agent_pack(args.from_pack, args.to_pack, force=args.force)
        except ValueError as exc:
            emit_error(str(exc))
            return
        emit_json(True, source_pack=resolve_pack(args.from_pack), target_pack=resolve_pack(args.to_pack), written_files=written)
        return

    selected_pack = getattr(args, "pack", None)
    try:
        agents = load_agent_catalog(strict=True, pack=selected_pack)
    except ValueError as exc:
        emit_error("agent catalog 校验失败", details=str(exc))
        return

    if args.command == "lint":
        emit_json(
            True,
            pack=resolve_pack(selected_pack),
            count=len(agents),
            agents=[compact_catalog_entry(agent) for agent in agents],
            message="agent catalog 校验通过"
        )
    elif args.command == "list":
        emit_json(True, pack=resolve_pack(selected_pack), count=len(agents), agents=[compact_catalog_entry(agent) for agent in agents])
    elif args.command == "manifest":
        if args.format == "markdown":
            print(render_markdown_manifest(agents, pack=selected_pack), end="")
        else:
            print(json.dumps([compact_catalog_entry(agent) for agent in agents], ensure_ascii=False, indent=2))
    elif args.command == "get":
        target = next((agent for agent in agents if agent["agent_id"] == args.agent_id), None)
        if not target:
            emit_error(f"agent {args.agent_id} 不存在")
            return
        emit_json(True, agent=target)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
