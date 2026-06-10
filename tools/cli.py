"""opc — single entry point dispatching to OPC Team CLI tools.

Usage:
    opc <subcommand> [args...]

Subcommands are thin wrappers around the individual ``tools/*.py`` scripts:

    opc task create --title "..." --ceo-input "..."
    opc task transition --task-id T001 --to completed --actor COO
    opc risk assess --task-id T001 --risk-name "..." --probability 4 --impact 5
    opc decision create --task-id T001 --title "..." --options "..." --chosen "..." --reason "..." --assumptions "..."
    opc agent dispatch --agent-id research --task "..."
    opc dashboard serve
    opc config show

This wrapper keeps every existing ``python3 tools/<name>.py ...`` call working
(those scripts are unchanged); the wrapper just removes the boilerplate.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent

# The OPC tools use bare imports (``from config import ...``) so the tools
# directory must be importable as a flat search path.
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


SUBCOMMAND_MAP = {
    "task": "task_flow",
    "decision": "decision_log",
    "risk": "risk_score",
    "memory": "memory_sync",
    "agent": "agent_ops",
    "catalog": "agent_catalog",
    "convert": "agent_convert",
    "dashboard": "dashboard",
    "config": "config",
}


HELP_TEXT = """opc — Cross-platform Agent Ops CLI

Usage:
  opc <subcommand> [args...]

Subcommands:
  task        Task state machine (create, assess, transition, progress, status)
  decision    Decision log (create, update-assumption, backfill, get, list)
  risk        Risk scoring (assess, update, list, get)
  memory      Three-tier memory sync (init, write, compress, archive, read, sync)
  agent       Main/sub-agent orchestration & model routing
  catalog     Agent catalog management (lint, scaffold-pack, list)
  convert     Export agent catalog to platform integrations
  dashboard   Launch the local dashboard server
  config      Read/write OPC config (init, get, set, info, detect, adapt)

Help for any subcommand:
  opc <subcommand> --help

Documentation: https://github.com/HeiGeAi/opc-team
"""


def print_help() -> None:
    sys.stdout.write(HELP_TEXT)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        print_help()
        return

    subcommand = args[0]
    if subcommand not in SUBCOMMAND_MAP:
        sys.stderr.write(f"opc: unknown subcommand '{subcommand}'\n\n")
        print_help()
        raise SystemExit(2)

    module_name = SUBCOMMAND_MAP[subcommand]
    # Rewrite argv so the delegated module sees ``<module_name> <rest...>``,
    # exactly as if it had been invoked via ``python3 tools/<module_name>.py``.
    sys.argv = [module_name] + args[1:]

    module = importlib.import_module(module_name)
    if not hasattr(module, "main"):
        sys.stderr.write(f"opc: subcommand '{subcommand}' has no main() entry point\n")
        raise SystemExit(2)
    module.main()


if __name__ == "__main__":
    main()
