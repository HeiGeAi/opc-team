# OPC Team — Roadmap

> 路线图是公开承诺，不是 wishlist。下面每一项要么已经做完，要么有明确的下个版本目标，要么标注「未来」并说明触发条件。

## v4.6 — 强度测试 + 三个 P0 修复（当前版本）

> v4.5 工程化底座搭好后，11 类强度测试在 1500+ 操作的负载下找出三个真问题，本版本修掉。

- [x] **agent catalog 重复加载（P0-1）**：写路径每次都重读 20 个 agent .md，把 `assess_task` 拖到 5.7 ops/s。引入 mtime-based 缓存后 → 30+ ops/s（5×）。
- [x] **`except Exception` 抓不到 `SystemExit`（P0-2）**：sync 钩子内 emit_error 抛 SystemExit 漏出去，用户看到 success: true 但状态没真正落盘。改成 `except (Exception, SystemExit)`，补 4 个回归测试。
- [x] **SQLite 后端两个深坑（P0-3）**：`StorageFactory.create("sqlite", base_dir=...)` 忽略 `base_dir` 把 db 落到 cwd；多 storage_type 共享 db 下 key 撞车把 task 错搬到 agent namespace。修 db_path 派生 + 加 namespace 透明前缀。
- [x] 测试数 45 → 58，全套 < 0.5s。

## v4.5 — 工程化质量底座

> 把 README 上「可审计、可治理」的口号变成可验证的实物。

- [x] **测试套件**：`tests/` 共 45 个用例，覆盖状态机非法跳转、L3 完成前必须有决策、并发 ID 生成、文件锁并发写、风险矩阵边界、决策假设证伪等核心逻辑。
- [x] **CI**：`.github/workflows/ci.yml` 在 Ubuntu + macOS × Python 3.9/3.11/3.12 矩阵上跑 pytest，外加一个 ruff lint job。
- [x] **`opc` 命令行**：`pip install -e .` 之后，所有 `python3 tools/<name>.py ...` 都能改写为 `opc <name> ...`，旧写法保持兼容。
- [x] **英文 README**：[README_EN.md](./README_EN.md) 给海外用户一个 60 秒入口。
- [x] **examples/**：放真实跑出来的 task / decision / risk / MEMORY.md 产物，而不是文档示意。
- [x] **文档真实化**：移除 storage.py docstring 里「Redis 后端」的口头承诺；PLATFORM_ANALYSIS.md 的 Roadmap 重新对齐到实际进度。

## v4.6 — 让数据说话

> 已经把每个任务、决策、风险都存成 JSON 了，但聚合视图缺位。这个版本补上。

- [ ] `opc stats --last 7d`：按时间窗口聚合任务数、L 分布、风险等级分布、SLA 命中率、最常用 sub-agent。
- [ ] `opc audit --task-id T001`：回放某个任务的完整时间线（actors + decisions + risks + progress + memory）。
- [ ] Docker 镜像：`docker run heigeai/opc-team:latest` 跑通 dashboard + CLI，不再依赖本机 Python 环境。
- [ ] Windows 安装验证：现在 `install.sh` 默认 bash，Windows 原生需要走 `pip install opc-team[windows]` 路径，写一份对应的 PowerShell 流程。
- [ ] CLI 错误信息英文化（保留中文，加 `--lang en` 切换）。

## v4.7 — 角色生态

> 当前角色目录设计已经支持 `agents/<pack>/*.md`，但缺少分发机制。

- [ ] Agent pack 注册表：`opc agent install <pack-name>` 从 git URL 或本地路径拉一个行业角色包。
- [ ] 角色契约校验：在 `agent_catalog lint` 里加 `inputs / outputs / handoff` 三段强校验。
- [ ] Telemetry opt-in：用户自愿打开匿名遥测（任务数、平均 SLA、报错栈），用于优化默认行为。数据走 self-hosted 端点，源码在仓库里。

## 未来（触发后才动手）

> 这些条目都是「真有用户在问 / 真有人在 PR」之前不会做的功能。明确写出来避免被当成 v4.6 的延期项。

- Redis 存储后端：触发条件 = 多个团队同时跑 OPC 且共享同一份数据。当前文件 + SQLite 已经能覆盖单团队所有场景。
- 多用户权限系统：触发条件 = 仓库出现「多人 OPC 实例」案例。当前 OPC 是单人单工作目录设计。
- Web SaaS 版本：当前明确不做。OPC 的定位是本地工具，数据在你自己仓库里，没有云端版本计划。

## 已知限制（不是 bug，是边界）

- **`opc` console script 不自带 agents/ 目录**：pip 装的是工具引擎，完整运行需要 `git clone` 后跑 `./install.sh`。理由是角色包是用户资产，不应该被 pip 默认覆盖。
- **`auto_sync_memory` 的 MEMORY.md 是平铺 markdown**：L0/L1/L2 三级在概念里清晰，但落到文件目前是 append-only。下个版本要么补 compaction，要么明确这是「事件流」语义。
- **`emit_error` 在 try/except 里被吞掉**：`task_flow.create_task` 末尾的 `try: sync_agent_from_task ... except Exception: pass` 抓不到 `SystemExit`。这是 v4.6 要修的隐性 bug（不会影响主流程，但会把不必要的错误打到 stdout）。

---

如果你想让某个「未来」条目提前到 v4.6，开个 issue 说你的具体场景。
