# Changelog

所有显著变更按版本记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

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
