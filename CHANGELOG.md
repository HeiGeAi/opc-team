# Changelog

所有显著变更按版本记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

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
