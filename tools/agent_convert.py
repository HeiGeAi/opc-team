#!/usr/bin/env python3
"""
agent_convert.py - OPC Team 角色目录平台转换器

功能：
- 从标准化 agent catalog 导出平台集成文件
- 支持 OpenClaw / Claude Code / Cursor / Windsurf / Generic / API
- 让角色内容与宿主格式适配解耦
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List

from agent_catalog import (
    compact_catalog_entry,
    list_agent_packs,
    load_agent_catalog,
    render_markdown_manifest,
    resolve_pack
)
from runtime import emit_error, emit_json


SUPPORTED_TOOLS = ["generic", "claude_code", "openclaw", "cursor", "windsurf", "api"]


def _section_map(body: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current = None

    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _main_agent(agents: List[Dict]) -> Dict:
    return next(agent for agent in agents if agent["agent_type"] == "main")


def _default_executor(agents: List[Dict]) -> Dict:
    return next((agent for agent in agents if agent["agent_id"] == "coo"), next(agent for agent in agents if agent["agent_type"] == "sub"))


def _routing_table(agents: List[Dict]) -> str:
    lines = [
        "| agent_id | 角色 | 适用场景 | aliases | 能力 |",
        "|---|---|---|---|---|"
    ]
    for agent in agents:
        lines.append(
            f"| `{agent['agent_id']}` | {agent['name']} | {agent['description']} | "
            f"{', '.join(agent['aliases']) or '-'} | {', '.join(agent['capabilities'])} |"
        )
    return "\n".join(lines)


def _agent_detail_block(agent: Dict) -> str:
    sections = _section_map(agent["body"])
    mission = sections.get("核心使命", "暂无")
    rules = sections.get("关键规则", "暂无")
    deliverables = sections.get("交付物", "暂无")
    workflow = sections.get("工作流", "暂无")
    return "\n".join([
        f"## {agent['name']}",
        "",
        f"- `agent_id`: `{agent['agent_id']}`",
        f"- `role`: {agent['role']}",
        f"- `description`: {agent['description']}",
        f"- `aliases`: {', '.join(agent['aliases']) or '-'}",
        f"- `capabilities`: {', '.join(agent['capabilities'])}",
        "",
        "### 核心使命",
        mission,
        "",
        "### 关键规则",
        rules,
        "",
        "### 交付物",
        deliverables,
        "",
        "### 工作流",
        workflow
    ])


def _catalog_pack(agents: List[Dict]) -> str:
    return agents[0].get("pack", "default") if agents else "default"


def _base_platform_intro(tool: str, agents: List[Dict]) -> str:
    main_agent = _main_agent(agents)
    default_executor = _default_executor(agents)
    pack = _catalog_pack(agents)
    return "\n".join([
        f"# OPC Team Platform Pack · {tool}",
        "",
        f"- 角色 pack：`{pack}`",
        f"- 主控编排：`{main_agent['agent_id']}` / {main_agent['name']}",
        f"- 默认执行身份：`{default_executor['agent_id']}` / {default_executor['name']}",
        "- 角色内容来自 `agents/*.md` 标准目录，不要在宿主规则里再维护第二份角色文本。",
        "- 状态、风险、决策和记忆仍然统一通过 `tools/*.py` CLI 落盘。"
    ])


def render_openclaw_bundle(agents: List[Dict]) -> Dict[str, str]:
    main_agent = _main_agent(agents)
    default_executor = _default_executor(agents)
    executor_sections = _section_map(default_executor["body"])

    soul = "\n".join([
        "# OPC Team Soul",
        "",
        "你当前接入的是 OPC Team 的组织化执行层。",
        "",
        f"- 主控编排身份：`{main_agent['agent_id']}` / {main_agent['name']}",
        f"- 默认执行身份：`{default_executor['agent_id']}` / {default_executor['name']}",
        "- 复杂任务默认先由 CEO 主控拆解，再由 COO 和对应 sub-agent 接力。",
        "- 所有关键状态必须通过 CLI 工具更新，不能直接写临时状态文件。",
        "",
        "## 核心操作规则",
        "",
        "- 先判断当前任务属于哪类角色，再选择 agent。",
        "- 需要推进任务状态时调用 `task_flow.py` 或 `agent_ops.py`。",
        "- 需要落决策、风险、记忆时分别调用 `decision_log.py`、`risk_score.py`、`memory_sync.py`。",
        "",
        "## 默认执行身份摘要",
        "",
        executor_sections.get("身份与记忆", default_executor["description"])
    ])

    identity = "\n".join([
        "# Default Identity",
        "",
        f"当前默认执行身份：{default_executor['name']}",
        "",
        "## 身份与记忆",
        executor_sections.get("身份与记忆", default_executor["description"]),
        "",
        "## 核心使命",
        executor_sections.get("核心使命", ""),
        "",
        "## 关键规则",
        executor_sections.get("关键规则", ""),
        "",
        "## 工作流",
        executor_sections.get("工作流", "")
    ])

    agents_md = "\n\n".join([
        "# OPC Team Agents",
        "",
        "以下为 OpenClaw 环境中的角色路由表与角色卡。",
        "",
        _routing_table(agents),
        "",
        *[_agent_detail_block(agent) for agent in agents]
    ])

    routing = "\n".join([
        "# OPC Team Routing",
        "",
        "## 主从关系",
        "",
        "- CEO 负责编排、派发、收敛",
        "- COO 负责任务定级、状态推进和跨角色衔接",
        "- 其他 sub-agent 在各自专业域内输出结果",
        "",
        _routing_table(agents)
    ])

    return {
        "SOUL.md": soul + "\n",
        "IDENTITY.md": identity + "\n",
        "AGENTS.md": agents_md + "\n",
        "ROUTING.md": routing + "\n"
    }


def render_claude_code_bundle(agents: List[Dict]) -> Dict[str, str]:
    guide = "\n\n".join([
        _base_platform_intro("claude_code", agents),
        "## 路由参考",
        "",
        _routing_table(agents),
        "",
        *[_agent_detail_block(agent) for agent in agents]
    ])

    router = "\n".join([
        "# OPC Team Role Router",
        "",
        "- 任务拆解、派发、主结论：`ceo`",
        "- 定级、流转、同步：`coo`",
        "- 策略与收敛：`strategist`",
        "- 需求拆解：`product`",
        "- 渠道测试：`marketing`",
        "- 技术约束：`tech`",
        "- 成本收益：`finance`",
        "- 叙事表达：`brand`",
        "- 合规边界：`legal`"
    ])

    return {
        "AGENTS.md": guide + "\n",
        "ROUTER.md": router + "\n"
    }


def render_generic_bundle(agents: List[Dict]) -> Dict[str, str]:
    return {
        "AGENTS.md": (render_markdown_manifest(agents, pack=_catalog_pack(agents)) + "\n"),
        "ROUTING.md": ("\n".join([
            _base_platform_intro("generic", agents),
            "",
            "## 角色路由",
            "",
            _routing_table(agents)
        ]) + "\n")
    }


def render_cursor_bundle(agents: List[Dict]) -> Dict[str, str]:
    body = "\n".join([
        "---",
        "description: OPC Team role catalog and routing map",
        "globs:",
        "  - \"**/*\"",
        "alwaysApply: false",
        "---",
        "",
        "# OPC Team Cursor Rule",
        "",
        "这个规则文件是从 OPC Agent Catalog 自动生成的角色参考。",
        "",
        "## 路由原则",
        "",
        "- 主控编排使用 `ceo`",
        "- 状态推进默认由 `coo` 承担",
        "- 领域任务按下表选择对应 sub-agent",
        "",
        _routing_table(agents)
    ])
    return {"opc-team-catalog.mdc": body + "\n"}


def render_windsurf_bundle(agents: List[Dict]) -> Dict[str, str]:
    body = "\n".join([
        "# OPC Team Windsurf Rules",
        "",
        "这份规则由标准化角色目录自动生成，作为 Windsurf 中的角色映射参考。",
        "",
        "## 角色路由",
        "",
        _routing_table(agents),
        "",
        "## 默认执行顺序",
        "",
        "1. `ceo` 拆解任务",
        "2. `coo` 推进状态与同步",
        "3. 领域 sub-agent 输出专业结果",
        "4. `ceo` 汇总结论"
    ])
    return {".windsurfrules": body + "\n"}


def render_api_bundle(agents: List[Dict]) -> Dict[str, str]:
    pack = _catalog_pack(agents)
    main_agent = _main_agent(agents)
    default_executor = _default_executor(agents)
    catalog_payload = {
        "pack": pack,
        "main_agent_id": main_agent["agent_id"],
        "default_executor_id": default_executor["agent_id"],
        "agents": [compact_catalog_entry(agent) for agent in agents]
    }
    routing_payload = {
        "pack": pack,
        "main_agent": {
            "agent_id": main_agent["agent_id"],
            "name": main_agent["name"]
        },
        "default_executor": {
            "agent_id": default_executor["agent_id"],
            "name": default_executor["name"]
        },
        "routing": [
            {
                "agent_id": agent["agent_id"],
                "name": agent["name"],
                "role": agent["role"],
                "agent_type": agent["agent_type"],
                "parent_agent_id": agent.get("parent_agent_id"),
                "description": agent["description"],
                "capabilities": list(agent["capabilities"]),
                "aliases": list(agent["aliases"])
            }
            for agent in agents
        ]
    }
    system_prompt = "\n".join([
        "# OPC Team API Router",
        "",
        f"- 当前角色 pack：`{pack}`",
        f"- 主控编排：`{main_agent['agent_id']}` / {main_agent['name']}",
        f"- 默认执行：`{default_executor['agent_id']}` / {default_executor['name']}",
        "- API 宿主应把任务先交给 main agent 判断是否需要拆解。",
        "- 若任务需要专业分工，则按 `routing-map.json` 选择对应 sub-agent。",
        "- 角色文本以 `agent-catalog.json` 为准，运行时状态仍由 OPC CLI 工具负责。"
    ])
    return {
        "agent-catalog.json": json.dumps(catalog_payload, ensure_ascii=False, indent=2) + "\n",
        "routing-map.json": json.dumps(routing_payload, ensure_ascii=False, indent=2) + "\n",
        "SYSTEM_PROMPT.md": system_prompt + "\n"
    }


def export_bundle(tool: str, out_root: Path, pack: str) -> Dict[str, List[str]]:
    agents = load_agent_catalog(strict=True, pack=pack)
    selected_pack = resolve_pack(pack)

    renderers = {
        "generic": render_generic_bundle,
        "claude_code": render_claude_code_bundle,
        "openclaw": render_openclaw_bundle,
        "cursor": render_cursor_bundle,
        "windsurf": render_windsurf_bundle,
        "api": render_api_bundle
    }

    if tool not in renderers:
        raise ValueError(f"不支持的平台: {tool}")

    bundle_dir = out_root / tool if selected_pack == "default" else out_root / selected_pack / tool
    bundle_dir.mkdir(parents=True, exist_ok=True)

    files = renderers[tool](agents)
    written: List[str] = []
    for filename, content in files.items():
        target = bundle_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target))

    return {
        "tool": tool,
        "pack": selected_pack,
        "written_files": written
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="OPC Team 平台角色转换器")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-tools", help="列出支持的平台")
    subparsers.add_parser("list-packs", help="列出支持导出的角色 pack")

    export_parser = subparsers.add_parser("export", help="导出平台集成文件")
    export_parser.add_argument("--tool", required=True, choices=SUPPORTED_TOOLS + ["all"], help="目标平台")
    export_parser.add_argument("--out", default="output/integrations", help="输出目录")
    export_parser.add_argument("--pack", default="default", help="角色 pack 名称")

    args = parser.parse_args()

    if args.command == "list-tools":
        emit_json(True, tools=SUPPORTED_TOOLS)
        return

    if args.command == "list-packs":
        packs = list_agent_packs()
        emit_json(True, packs=packs, count=len(packs))
        return

    if args.command != "export":
        parser.print_help()
        return

    out_root = Path(args.out).resolve()
    selected_pack = resolve_pack(args.pack)

    try:
        if args.tool == "all":
            results = [export_bundle(tool, out_root, selected_pack) for tool in SUPPORTED_TOOLS]
            emit_json(True, results=results, output_root=str(out_root), pack=selected_pack)
        else:
            result = export_bundle(args.tool, out_root, selected_pack)
            emit_json(True, result=result, output_root=str(out_root), pack=selected_pack)
    except ValueError as exc:
        emit_error(str(exc))


if __name__ == "__main__":
    main()
