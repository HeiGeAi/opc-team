# Changelog

所有显著变更按版本记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [4.8.0] — 2026-07-09

### OPC 生存军规接入 + 接单预检器 + 红队诤友席位

蒸馏一位资深 OPC 从业者的长文经验，把「交易卫生学照抄、服务商姿态反着学」的方法论工程化进框架。minor 版本：新增确定性工具、新增角色、新增文档，向后兼容。

#### Added

- **`tools/deal_guard.py` 接单预检器**（`opc dealguard`）：零依赖只读扫描器，接单/报价前扫 7 类致命模式（画饼白嫖、无预付款、触碰交付红线、合规效果宣称、许愿机需求、项目制毛利黑洞、熟人不签约）+ 线程挤兑告警（`--active-fronts`），命中即给规则、修复动作和 severity 裁决（STOP/HOLD/CAUTION/CLEAR）
- **`agents/redteam.md` 红队诤友角色**（第 21 席）：在决策落地前独立反驳推荐结论，专杀「看似合理其实错」的判断，纳入 `important` 调度档，作为 L3/L4 决策的验证闸门（与状态机的 L4 决策门禁互补）
- **`references/OPC_PLAYBOOK.md` 共享军规**：13 条铁律分四组（交易卫生学 / 反服务商化 / 护城河标品 / 常被忽略的风险），全员做接单判断前共读
- 九个角色（sales/legal/finance/customer_success/strategist/product/tech/coo/ceo）的「关键规则」注入对口 OPC 铁律

#### Changed

- 角色数 20 → 21，编组档位 `daily/important/full` 的核心规模 `3 / 8` → `3 / 9`，`full` 满编 sub-agent 数 19 → 20
- `opc` CLI 新增 `dealguard` 子命令

## [4.7.0] — 2026-06-10

### 数据完整性、状态机与接口加固

深度检查找出一批数据完整性、状态机死角和接口契约问题，本版本集中修掉。定为 minor 版本：包含新增 CLI 能力（`--force`、决策命令的 `--task-id` 限定、assess 的 `--actor`、新 `cancelled` 状态）和若干行为变更，向后兼容但不只是补丁级修复。

#### Fixed

**数据完整性**
- `decision_log` 全部 ID 输入加白名单校验（`^[A-Za-z0-9_-]+$`）。此前 `--decision-id` 含 `/` 时数据会写到错误位置且报成功（实际等于写丢），现在直接报错退出
- 重复 `decision create` 同一 decision-id 不再静默覆盖：已存在即报错，显式覆盖走新增的 `--force` 参数
- `--decision-id` 跨任务查找不再取 glob 第一个命中：get / update-assumption / backfill 支持 `--task-id` 严格限定该任务；不带 `--task-id` 且多任务命中时报错并列出全部候选键
- `parse_assumptions` 不再静默丢弃无冒号条目：作为无标签假设收录，JSON 输出的 `assumptions_count` 如实计数；纯空白条目跳过
- SQLite 后端下 MEMORY.md 缺决策履历：`memory_sync` 此前绕过 storage 抽象直读文件系统，现改走 storage 抽象，文件 / SQLite 两种后端行为一致
- `memory sync` 不再盲追加：按 task_id 幂等，同任务重复同步会替换旧条目，README 完整示例重复执行不再产生重复条目

**状态机与门禁**
- `escalated` 状态此前没有出边、SLA 超期又会自动转入，任务一旦升级即永久卡死。现在新增 `escalated → in_execution`（恢复执行）和 `escalated → cancelled`（显式取消）两条出边，并新增终态 `cancelled`
- L4 任务完成此前不要求决策履历（代码只查 L3，与 SKILL.md 宣称的「L3+ 必须」不一致）：现在 L3 及以上完成前都必须有决策履历
- `check-sla` 此前所有非升级路径零输出零退出码，无法区分原因。现在每条路径都输出带状态字段的 JSON：SLA 关闭（action=skipped）、任务不存在（success=false + 退出码 1）、终态/已升级、未定级、未达升级阈值（含 sla_status 正常/超期）、已自动升级
- `completed` 流转 + `auto_sync_memory` 此前 stdout 输出两行 JSON，破坏统一契约。现在记忆同步结果内嵌在 transition 结果的 `memory_sync` 字段里，stdout 保持单 JSON 对象

**接口与配置**
- `config get` 等读路径不再在 cwd 静默创建 config.json，默认配置只在内存生效；只有显式 `init` / `set` 才落盘
- `readonly_mode` 兼容顶层与 `features.readonly_mode` 两种写法（此前只认 features 写法，SKILL.md 教的却是顶层写法），文档统一为 features 写法
- `opc --help` 的 memory 子命令清单从虚构的 `(init, snapshot, summarize)` 改为与实现一致的 `(init, write, compress, archive, read, sync)`
- 去掉 `task_flow` 里硬编码的「魏明远」：`assess` 新增可选 `--actor` 记录实际操作者，预设角色名只做默认兜底
- dashboard `_safe_call` 的过宽 except 现在会记录具体异常信息（函数名、SystemExit 退出码、完整 traceback）再返回错误响应
- `full` 编组档位 `sub_agent_target` 从 20 修正为 19（default pack 共 20 个角色 = CEO 主 agent + 19 个 sub-agent，full 档实际派发的是 19 个 sub-agent）

#### Added
- `decision create --force`、decision get/update-assumption/backfill 的 `--task-id`、`task assess --actor`
- 任务状态 `cancelled`（终态，无出边）
- `memory_sync.write_memory_entry()` / `build_memory_entry()`：返回结果字典、不直接输出 JSON，供 task_flow 内嵌结果
- 工具脚本执行位：带 shebang 的 `tools/*.py` 在 git 索引里加上 +x，使 install.sh 写入 PATH 的调用方式真正可用
- 测试 58 → **90**（+32）：覆盖 ID 校验、重复创建、跨任务消歧、无冒号假设、escalated 恢复/取消、L4 门禁、check-sla 各路径、单 JSON 契约、MEMORY.md 幂等与 SQLite 一致性、config 零副作用、readonly 双写法、actor 记录

#### Removed
- `tools/utils.py`：全文件无任何引用的死代码
- `tools/runtime.py` 里同源的实体存取辅助段（`save_entity` / `load_entity` / `list_entities` / `delete_entity` / `get_storage_path`，无引用）

#### Docs
- Python 版本口径统一 3.9+（代码含 walrus 运算符）：install.sh 版本检查、SKILL.md、PLATFORM_ANALYSIS.md
- README_EN 删除未发布的 `pip install opc-team`（PyPI 404），统一 `pip install -e .`，正文从 v4.5 同步到当前版本
- README 修复失效锚点、项目结构图补全（cli.py / runtime.py / tests / examples / pyproject.toml / ROADMAP / CHANGELOG / README_EN）、补 pip >= 21.3 门槛说明、dashboard 措辞改为「本地查看与调度面板」
- DEPLOYMENT.md 修复 your-repo 占位符链接、function calling 示例按 api.json 真实结构（Anthropic tools 格式包装对象）重写
- 所有 config.json 示例去掉 `//` 注释（复制即合法 JSON），说明移到代码块外
- ROADMAP 两个 v4.6 撞号条目并入正常版本序列

### Upgrade notes

从 v4.6 升级：

```bash
git pull
pytest tests/ -q    # 90/90 应该全过
```

行为变更注意：重复 `decision create` 现在会报错（之前静默覆盖），如有依赖覆盖行为的脚本请加 `--force`；`check-sla` 现在总有 stdout 输出，解析方按 `action` / `reason` 字段区分；completed 流转的记忆同步结果挪到了 `memory_sync` 字段内。

## [4.6.0] — 2026-05-26

### 性能与正确性修复

v4.5 引入的测试套件 + 11 类强度测试发现三个 P0 级别问题，本版本逐一修掉，并补充 13 个回归测试。

#### Fixed

**P0-1 · agent catalog 重复加载（性能 ~5×）**
- `tools/agent_catalog.py` 加 mtime-based 缓存，按 pack + strict 维度独立缓存
- 缓存签名包含目录 mtime + 每个文件 (name, mtime, size)，agent 文件改动后自动失效
- 暴露 `invalidate_catalog_cache(pack)` 给测试和未来手动清理使用
- 效果：`create_task` 21 → 112 ops/s，`assess_task` 5.7 → 30.2 ops/s

**P0-2 · `except Exception` 抓不到 `SystemExit`（用户看 success 实际状态没落盘）**
- `tools/task_flow.py` 全部 7 处 best-effort sync 钩子改成 `except (Exception, SystemExit)`
- 影响 `create_task` / `assess_task` / `transition_state` / `report_progress` 内调用 `sync_agent_from_task` / `describe_orchestration_plan` / `sync_to_memory_md` 的路径
- 加 4 个回归测试 monkey-patch `agent_ops.*` 让其稳定抛 SystemExit，验证主调用仍然完成并 emit success

**P0-3 · SQLite 后端两个深坑（功能 bug）**
- `StorageFactory.create("sqlite", base_dir=...)` 之前会忽略 `base_dir`，db 总是落到 `Path.cwd() / "data" / "opc.db"`。现在从 `base_dir.parent` 派生 `opc.db`，让多工作目录隔离真正生效
- 共享 db 下所有 storage_type 平铺写入，task 的 `T001` 与 agent storage 的 legacy 迁移逻辑会撞 key 把 task 错搬到 `default/T001`。新增 namespace 机制（`tasks::T001` / `agents::default/ceo` / `decisions::T001_D001`），透明前缀互不干扰
- 加 5 个 SQLite 测试覆盖 db_path 推导、单工作目录完整生命周期、read-after-write、跨 storage_type 共享 db、namespace 隔离

#### Added
- `tests/test_agent_catalog_cache.py` — 4 个测试：缓存命中、mtime 失效、显式 invalidate、cached vs cold 速度下限断言
- `tests/test_sync_hook_resilience.py` — 4 个测试：create / assess / transition / progress 在 sync 钩子抛 SystemExit 时全部正常返回
- `tests/test_sqlite_backend.py` — 5 个测试：StorageFactory 路径推导、完整 SQLite 生命周期、read-after-write 一致性、多 storage_type 共享 db、namespace 隔离
- `storage.reset_storage_cache()` 给测试和切换 backend 的场景用

#### Performance

| 操作 | v4.5 文件 | v4.6 文件 | v4.6 SQLite |
| --- | --- | --- | --- |
| `create_task` | 21.2 ops/s | **112.4** | 103.4 |
| `assess_task` | 5.7 ops/s | **30.2** | 28.3 |
| `get_status` | 9490 ops/s | 19293 | 16915 |
| `risk_assess` | 4369 ops/s | 4410 | 1981 |

注：v4.5 SQLite 的 `assess_task` 在测试中显示 296 ops/s，但那是数据 corruption 后的伪速度（task 被错搬到 agent namespace 后 load 永远找不到，错误路径反而短）。v4.6 修复后两个后端表现一致。

#### Test suite
- 测试数 45 → **58**（+13 新增）
- 全套 < 0.5s 完成
- CI 矩阵不变：Ubuntu + macOS × Python 3.9 / 3.11 / 3.12 + ruff

### Upgrade notes

从 v4.5 升级：

```bash
git pull
pytest tests/ -q    # 58/58 应该全过
```

如果你之前在 SQLite 后端跑过，`opc.db` 会落到 `Path.cwd() / data / opc.db` 而不是工作目录的 `data/opc.db`。升级后第一次跑会按新位置创建新 db；老的 db 里如果有数据可以手动 `sqlite3 old.db .dump | sqlite3 new.db` 迁移过来（key 需要按 namespace 加前缀）。文件后端无任何兼容性影响。

## [4.5.0] — 2026-05-26

### 工程化质量底座

把 README 上「可审计 / 可治理」的口号变成可验证的实物。

#### Added
- `tests/` 目录，45 个 pytest 用例，覆盖：
  - 任务状态机合法/非法跳转
  - L3 任务完成前必须有决策履历
  - 并发 ID 生成的原子性（多线程下唯一性）
  - 文件锁并发写不损坏 JSON
  - SLA 自动升级
  - 风险矩阵 5 个边界点
  - 决策假设证伪触发重审
- `.github/workflows/ci.yml`：在 Ubuntu + macOS × Python 3.9/3.11/3.12 矩阵上跑 pytest，外加 ruff lint job。
- `pyproject.toml` + `setup.py`，提供 `opc` console script。装包之后所有 `python3 tools/<name>.py ...` 都有更短的 `opc <name> ...` 写法。
- `tools/cli.py`：统一入口，dispatch 到 task / decision / risk / memory / agent / catalog / convert / dashboard / config 各个子命令。
- `tools/__init__.py`：tools/ 现在是真正的 Python 包。
- [README_EN.md](./README_EN.md)：英文版 README，给海外用户一个 60 秒入口。
- [examples/](./examples/) 目录，包含真实运行产生的 task / decision / risk / MEMORY.md 产物。第一个完整样例：「上班族如何发展副业」L3 策略任务的完整生命周期。
- [ROADMAP.md](./ROADMAP.md)：v4.5/v4.6/v4.7 的明确版本计划 + 已知限制清单。

#### Changed
- `tools/storage.py` docstring：移除「Redis 后端」的口头承诺。文件存储和 SQLite 是真实实现的两种后端，Redis 仅在 ROADMAP 中标注为未来项。
- `tools/config.py`：CLI 入口从 `if __name__ == "__main__":` 块抽出成 `main()` 函数，便于 `opc config` 子命令复用。
- `README.md`：Quick Start 同时给出 `opc` 新写法和 `python3 tools/*.py` 老写法两条等价路径；顶部加上 CI badge 和指向英文版 / examples / roadmap 的导航。
- `PLATFORM_ANALYSIS.md`：Roadmap 清单按实际完成进度更新（SQLite ✅、Function schema ✅、只读模式 ✅、Web UI ✅）。

#### Removed
- 无破坏性删除。所有变更保持向后兼容。

### 升级指引

从 v4.4 升级：

```bash
git pull
pip install -e .          # 装 opc 命令（可选）
pytest tests/             # 看看测试通过情况
```

旧的 `python3 tools/<name>.py ...` 写法完全不动。如果你只是用 install.sh 部署的 skill，本次升级对运行行为没有任何影响——只是多了测试网和质量门控。

## [4.4.0] — 2026-04-18

- 编排升级：默认 3 / 8 / 20 三档弹性编组（`daily / important / full`）。
- Dashboard model routing UX polish。
- CEO identity alignment across dashboard。

## [4.3.0] — 2026-04-17

- 引入 adaptive orchestration profiles。
- Default pack 扩到 20 个角色，覆盖策略 / 研究 / 产品 / 体验 / 增长 / 技术 / 运维 / QA / 数据 / 采购 / HR / 法务 / 客户成功等链路。
- Pack-aware agent catalog 与平台导出能力解耦。

## [4.2.0] — 2026-04-09

- 主从 agent 编排（CEO 主 agent + sub-agent）。
- 模型路由：default / platform_default / custom_api 三种来源。
- 本地集成看板：浏览器查看当前编组档位、角色状态、模型切换。
