# OPC Team — Cross-Platform Agent Ops Framework

[![CI](https://github.com/HeiGeAi/opc-team/actions/workflows/ci.yml/badge.svg)](https://github.com/HeiGeAi/opc-team/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-v4.8.0-111827.svg)](./README.md)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg?logo=python&logoColor=white)](./pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-059669.svg)](./LICENSE)

> Turn prompt-based agents into auditable ops. State machine, decision log, risk scoring, and three-tier memory for Claude Code, OpenClaw, Cursor, Windsurf, and any CLI/API workflow.

中文版：[README.md](./README.md) · Deployment guide: [DEPLOYMENT.md](./DEPLOYMENT.md) · Agent catalog: [CATALOG.md](./CATALOG.md)

---

## What this is

OPC Team is **not** another role-playing prompt template. It is a small Python framework that wraps an agent team with engineering discipline:

- **Task state machine** with explicit `created → assessed → in_strategy / in_execution / in_debate → completed / blocked / escalated / cancelled` transitions (escalated tasks can resume execution or be cancelled)
- **Decision log** with options, chosen path, reason, and assumption tracking with falsification triggers
- **Quantitative risk scoring** (`probability × impact → level 1-5`) with mitigation requirements above a threshold
- **Three-tier memory** (`L0 working → L1 short-term → L2 long-term`) that survives across sessions
- **Cross-platform file locking** (`fcntl` on Unix, `filelock` fallback on Windows)
- **Pack-aware agent catalog**: drop role definitions into `agents/*.md` or `agents/<pack>/*.md`, validate with `opc catalog lint`, switch with `opc agent switch-pack`
- **Adaptive orchestration**: `daily / important / full` profiles dispatch `3 / 9 / 20` sub-agents (the `full` profile is all 21 roles: CEO + 20 sub-agents) based on task intensity
- **Deal Guard** (`opc dealguard scan`): a zero-dependency pre-flight scanner that flags fatal deal patterns (revenue-share bait, no-prepayment, red-line scope, compliance traps, scope-creep wishlists, project-drift, thread contention) before you take on work, returning the rule and the fix for every hit
- **Red Team Gate**: a dedicated `redteam` adversary role that independently refutes recommended decisions on L3/L4 tasks before they are committed, killing plausible-but-wrong conclusions

Every state change, decision update, and risk assessment is logged as JSON under `data/` so the entire run can be replayed.

## What this is NOT

- Not an LLM router (use LiteLLM, OpenRouter, or your provider SDK directly)
- Not a multi-agent execution engine (no concurrent task workers — orchestration is logical)
- Not a vector RAG layer (memory is task summaries, not embeddings)
- Not a hosted product (everything runs locally; data stays in your repo)

## Install

```bash
git clone https://github.com/HeiGeAi/opc-team.git
cd opc-team
./install.sh                # auto-detects Claude Code / OpenClaw / Cursor / Windsurf
# OR
pip install -e .            # installs the `opc` console script
```

Requires Python 3.9+ and pip >= 21.3 (PEP 660 editable install; run `pip install -U pip` on older versions). Windows users should `pip install -e ".[windows]"` to pull in the `filelock` fallback.

The package is not published on PyPI; install from a source checkout. The `agents/` role catalog lives in the checkout, so full operation (task lifecycle with sub-agent dispatch) runs from the cloned directory.

## 60-second walkthrough

```bash
# Create and assess a task
opc task create --title "Plan H2 hiring" --ceo-input "5 engineers by Q4"
opc task assess --task-id T001 --level L3 --reason "Strategy-level scope"

# Record a decision with explicit assumptions
opc decision create \
  --task-id T001 \
  --title "Hire senior before junior" \
  --options "senior-first,junior-first,balanced" \
  --chosen "senior-first" \
  --reason "Senior hires can ramp juniors later" \
  --assumptions "a1:senior pipeline > 10 candidates,a2:budget locked"

# Log a risk
opc risk assess \
  --task-id T001 \
  --risk-name "Senior pipeline dries up" \
  --probability 3 --impact 5 \
  --mitigation "Maintain two parallel sourcing channels"

# Move the task forward
opc task transition --task-id T001 --to in_execution --actor "COO"

# When an assumption is falsified, trigger a review
# (--task-id scopes the lookup when the same decision id exists under multiple tasks)
opc decision update-assumption \
  --decision-id D001 --task-id T001 --assumption-id 1 --status 证伪 \
  --actual "Only 4 senior candidates" --trigger-review

# Check status with SLA
opc task status --task-id T001
```

## Architecture (one diagram)

```
                       ┌────────────────────┐
                       │   opc <command>    │  ← single CLI entry
                       └─────────┬──────────┘
                                 │
   ┌────────────┬────────────────┼──────────────┬──────────────┐
   ▼            ▼                ▼              ▼              ▼
 task_flow  decision_log     risk_score    memory_sync     agent_ops
   (state    (decisions      (risk          (L0/L1/L2     (main/sub
   machine)   + assumptions)  matrix)        memory)       routing)
   │            │                │              │              │
   └────────────┴────────────────┴──────────────┴──────────────┘
                                 │
                       ┌─────────▼──────────┐
                       │  storage layer     │  ← file or sqlite
                       │  (file lock + atomic IDs)
                       └─────────┬──────────┘
                                 │
                          data/{tasks,decisions,risks,memory,agents,logs}
```

## Supported platforms

| Platform     | Skill location                                         | Tool invocation        |
| ------------ | ------------------------------------------------------ | ---------------------- |
| Claude Code  | `~/.claude/skills/opc-team/SKILL.md`                   | Bash tool              |
| OpenClaw     | `~/.openclaw/workspace-<agent>/skills/opc-team/`       | CLI command            |
| Cursor       | `.cursorrules`                                         | Manual/Task            |
| Windsurf     | `.windsurfrules`                                       | Bash                   |
| API/Generic  | `adapters/api.json` (function-calling schema)          | Function calling       |

## Project layout

```
opc-team/
├── tools/                 # Python engine (state machine, decisions, risks, memory, agents)
├── tools/cli.py           # `opc` console script entry point
├── agents/                # Role catalog (default pack: 21 roles)
├── strategy/              # Runbooks (OPC-Micro, OPC-Sprint, OPC-Control)
├── adapters/              # Platform integration (Claude Code, OpenClaw, Cursor, API)
├── dashboard/             # Web UI (one HTML + tools/dashboard.py serve)
├── examples/              # Sample run artifacts (T001/D001/R001 JSON)
├── tests/                 # pytest suite (90 cases)
└── .github/workflows/     # CI: pytest on macOS + Ubuntu × 3 Python versions, plus ruff
```

## Development

```bash
pip install -e ".[dev]"     # pytest, ruff, filelock
pytest tests/ -v            # 90 unit tests
ruff check tools/ tests/    # lint
```

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for what's planned. Highlights:

- v4.6: stress testing + three P0 fixes (agent catalog cache, SystemExit-safe sync hooks, SQLite db_path + namespaces)
- v4.7 (current): data-integrity hardening — decision id validation, duplicate-create guard with `--force`, cross-task decision disambiguation, escalated-state recovery edges, L4 decision gate, structured `check-sla` output, idempotent MEMORY.md sync
- v4.8: aggregate stats (`opc stats --last 7d`), task audit replay, Docker image, Windows install verification
- v4.9: agent pack registry, role contract validation, telemetry opt-in

## License

MIT — see [LICENSE](./LICENSE).
