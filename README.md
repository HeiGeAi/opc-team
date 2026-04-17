# OPC Team — Cross-Platform Agent Ops Framework

![OPC Team agent ops hero](./assets/opc-team-hero.png)

[![Version](https://img.shields.io/badge/version-v4.4.0-111827.svg)](./README.md)
[![Python](https://img.shields.io/badge/python-3.7%2B-3776AB.svg?logo=python&logoColor=white)](./README.md)
[![Platforms](https://img.shields.io/badge/platform-Claude%20Code%20%7C%20OpenClaw%20%7C%20Cursor%20%7C%20Windsurf%20%7C%20API-0F766E.svg)](./DEPLOYMENT.md)
[![License](https://img.shields.io/badge/license-MIT-059669.svg)](./LICENSE)

> 把“固定角色表”的 AI Agent，升级成“能按任务强度自动扩缩容”的执行系统。

**OPC Team** 是一个跨平台的 Agent 协作框架，目标不是再造一个角色扮演 prompt，而是给 AI 执行过程加上明确的工程化约束：任务状态机、决策履历、风险量化、三级记忆，以及一组可审计的 CLI 工具。它适合跑在 **Claude Code / OpenClaw / Cursor / Windsurf / 通用 CLI / API 工作流** 上，让 Agent 的执行过程从“看起来会做”变成“真的可控、可回放、可治理”。当前默认编排策略已经升级为 `3 / 8 / 20` 三档弹性编组，也就是日常任务保留常驻小队，重要任务自动扩到核心队列，复杂任务再拉满全部角色协同。

[Quick Start](#-quick-start) · [Platform Matrix](#-supported-platforms) · [Deployment Guide](./DEPLOYMENT.md) · [Agent Catalog](./CATALOG.md) · [Skill Manual](./SKILL.md) · [API Schema](./adapters/api.json)

---

## 为什么这个项目值得看

- **不是纯 Prompt 模板**：核心能力是 `tools/*.py` 里的状态机、决策、风险、记忆和配置系统，不只是“设定一个 COO 角色”。
- **不是平台绑定插件**：同一套框架同时覆盖 Claude Code、OpenClaw、Cursor、Windsurf、通用 CLI 和 API 场景。
- **不是黑箱执行**：每次任务创建、状态流转、风险评估、决策更新、记忆同步，都可以被记录、回溯和审计。
- **不是会话即失忆**：L0/L1/L2 三级记忆可以把任务摘要、长期偏好和方法论沉淀下来。

## 它解决什么问题

| 只靠 Prompt 的 Agent 团队设定 | OPC Team 做的事 |
|---|---|
| 状态靠上下文“猜” | 用状态机强约束任务流转 |
| 方案拍脑袋，假设容易丢 | 用决策履历记录选项、假设、回填结果 |
| 风险描述停留在口头 | 用概率 × 影响做量化评分 |
| 会话结束就丢经验 | 用 L0/L1/L2 记忆沉淀跨任务经验 |
| 平台一换就要重写一版 | 用同一套 CLI 和 Skill 适配多平台 |

## 核心能力

- **Task Flow**：任务创建、定级、状态流转、进度上报、SLA 检查。
- **Decision Log**：记录方案、选择、理由、假设，并支持后续验证和回填。
- **Risk Score**：把风险从“感觉有点危险”变成可量化的等级和应对预案。
- **Memory Sync**：把即时记忆、短期摘要、长期经验同步到统一存储。
- **Config + Storage**：支持平台适配、路径配置、文件存储和 SQLite 存储。
- **Agent Catalog**：把内置角色定义放到 `agents/*.md` 或 `agents/<pack>/*.md`，用统一 schema + lint 管理角色层。
- **20-Role Bench**：default pack 内置 20 个可编排角色，覆盖策略、研究、产品、体验、增长、技术、运维、数据、财务、法务、客户成功等链路。
- **Role Packs**：支持把默认角色集复制成新 pack，并在运行时切换不同角色包。
- **Main/Sub Orchestration**：内置 `CEO主Agent -> sub-agent` 的主从编排结构，支持主 agent 派发子任务。
- **Agent Board**：用本地看板只读查看主 agent、sub-agent、当前编组档位、模型路由和最近状态变化。
- **Model Routing**：允许主 agent 和不同 sub-agent 指定不同 API provider / model；未配置时默认继承宿主平台模型。
- **Adaptive Orchestration**：支持 `daily / important / full` 三档编组，默认分别对应 `3 / 8 / 20角色` 的协同规模。
- **Workflow Runbooks**：补充 `OPC-Micro / Sprint / Control` 三种运行模式，以及 handoff/runbook 模板。

## 编排升级：弹性编组 + 可视化看板 + 多模型路由

- `tools/agent_ops.py` 维护主 agent / sub-agent 注册表、工作状态、派发任务和模型配置。
- `tools/agent_catalog.py` 负责校验角色目录、输出 manifest、发现/复制 role pack，并让角色层与编排层解耦。
- `tools/agent_convert.py` 负责把角色目录导出成 OpenClaw / Claude Code / Cursor / Windsurf / API 的集成文件。
- `tools/dashboard.py serve` 启动集成看板，浏览器直接查看当前编组档位、角色状态和模型切换入口。
- agent 模型配置支持三种来源：
  - `default`：继承全局默认路由
  - `platform_default`：强制使用宿主平台模型
  - `custom_api`：指定独立 provider / model / api_base / api_key_env
- 默认全局路由是 `platform_default`，也就是“默认用模型本身的模型”。
- 默认拓扑里 `ceo` 是主 agent，default pack 现在内置 20 个角色，从项目、研究、产品、体验、增长到技术、运维、QA、数据、采购、HR、法务都可直接编排。
- 编组默认分三档：`daily` 常驻 3 个 sub-agent，`important` 调用 8 个核心 sub-agent，`full` 启用满编 20 角色（`CEO + 19 个 sub-agent`）。
- 这意味着 OPC 的重点不再是“把 20 个角色全都常驻挂着”，而是让 CEO 主 agent 根据任务强度决定什么时候只动小队，什么时候拉起核心班底，什么时候再满编开战。

## 真实任务跑出来是什么样

下面不是静态 Prompt 示例，而是用 OPC Team 本地状态机跑出的 3 个 L3 策略任务形态：每个任务都会生成任务状态、风险记录、决策履历和记忆摘要。

| 真实任务 | OPC Team 给出的主决策 | 风险控制 |
|---|---|---|
| 上班族如何发展副业 | 先做垂直技能服务，再内容化，最后产品化 | 控制每周投入节奏；先做访谈和低价 MVP，避免一上来重投入 |
| 2026 年自媒体账号怎么变现 | 高客单咨询/陪跑 + 知识产品，广告和联盟只做补充 | 不把平台分成当唯一收入；先设计高信任高客单承接链路 |
| 我 + AI 适合什么知识付费产品 | 模板库 + 清单 + 7 天短周期陪跑 | 避免大课和重社群；围绕明确结果交付，而不是堆知识点 |

这类输出会沉淀到 `data/tasks/`、`data/decisions/`、`data/risks/`、`data/agents/`、`data/assignments/` 和 `data/MEMORY.md`，用于回放过程、复盘假设、追踪主从 agent 分工与后续执行。

## 角色目录：把角色层从编排代码里拆出来

- 默认角色定义位于 `agents/*.md`，额外角色包可以放在 `agents/<pack>/*.md`。
- `tools/agent_ops.py` 启动时会从当前 pack 加载主从拓扑，而不是再把角色写死在 Python 常量里。
- `tools/agent_catalog.py lint` 可以校验 schema、章节完整性和父子关系。
- `tools/agent_catalog.py scaffold-pack` 可以从默认角色复制出一个新 pack，再按行业或企业场景定制。
- `tools/agent_ops.py switch-pack` 可以直接切换当前运行 pack。
- 这使得你后续扩角色、做行业包、做平台适配时，不必直接修改编排代码。

## 工作流层：把角色编排变成可复用 runbook

- `strategy/QUICKSTART.md` 提供 `OPC-Micro / OPC-Sprint / OPC-Control` 三种运行模式。
- `strategy/coordination/handoff-templates.md` 提供主从交接、QA 通过/不通过、升级报告模板。
- `strategy/runbooks/` 里提供 `startup-mvp / enterprise-feature / incident-response` 三类场景 runbook。
- 这样 OPC 不只是“能派发角色”，而是能把不同场景的执行方式固定下来。

## 编组档位：把 20 角色按任务强度弹性调用

- `daily`：日常常驻 3 个 sub-agent，默认是 `coo / project / strategist`。
- `important`：重要任务拉起 8 个核心 sub-agent，默认是 `coo / project / strategist / research / product / tech / data / qa`。
- `full`：用户指定或高复杂任务直接启用满编 20 角色，也就是 `CEO + 19 个 sub-agent` 全量协同。
- `tools/task_flow.py assess --agent-profile ...` 可以显式指定档位。
- `tools/agent_ops.py recommend` 可以按任务等级、标题或关键词输出当前推荐编组。

---

## 🚀 Quick Start

### TL;DR

```bash
git clone https://github.com/HeiGeAi/opc-team.git
cd opc-team
./install.sh -p generic --skip-env -t
```

### 最短上手路径

```bash
# 1. 创建任务
python3 tools/task_flow.py create --title "评估知识付费可行性" --ceo-input "我想做知识付费"

# 2. 定级
python3 tools/task_flow.py assess --task-id T001 --level L3 --reason "需要多方案和风险评估"

# 如果是用户指定的复杂任务，可直接切到满编档位
python3 tools/task_flow.py assess --task-id T001 --level L4 --reason "复杂任务，需要全量协同" --agent-profile full

# 3. 创建决策履历
python3 tools/decision_log.py create \
  --task-id T001 \
  --title "定价策略" \
  --options "方案A,方案B" \
  --chosen "方案B" \
  --reason "高净值用户付费更明确" \
  --assumptions "假设1:转化率>5%"

# 4. 推进任务
python3 tools/task_flow.py transition --task-id T001 --to in_strategy --actor "COO魏明远"
python3 tools/task_flow.py progress --task-id T001 --message "策略官开始分析" --progress 30 --agent-id strategist
python3 tools/task_flow.py transition --task-id T001 --to in_execution --actor "COO魏明远"
python3 tools/task_flow.py transition --task-id T001 --to completed --actor "COO魏明远"

# 5. 配置某个 agent 使用独立 API 大模型（可选）
python3 tools/agent_ops.py set-model \
  --agent-id strategist \
  --source custom_api \
  --provider openai \
  --model gpt-4.1 \
  --api-key-env OPENAI_API_KEY

# 6. 由 CEO 主 agent 派发 sub-agent 任务
python3 tools/agent_ops.py dispatch \
  --from-agent ceo \
  --to-agent strategist \
  --title "输出三套策略方案" \
  --brief "给出方案、风险和收敛建议" \
  --task-id T001 \
  --task-title "评估知识付费可行性" \
  --auto-start

# 7. 启动本地看板
python3 tools/dashboard.py serve
```

### 在不同平台里怎么用

- **Claude Code / OpenClaw / Cursor / Windsurf**：安装后直接下达自然语言指令，让 Agent 按 `SKILL.md` 调用 CLI。
- **通用 CLI**：把 [SKILL.md](./SKILL.md) 当作 system prompt，允许执行 `python3 tools/*.py`。
- **API 工作流**：把 [adapters/api.json](./adapters/api.json) 接到 function calling 或工具层。

---

## 📁 项目结构

```
opc-team/
├── SKILL.md                    # 通用 AI 执行手册
├── README.md                   # 本文件
├── CATALOG.md                  # 角色目录说明
├── DEPLOYMENT.md               # 多平台部署指南
├── PLATFORM_ANALYSIS.md        # 平台兼容性分析
├── config.json                 # 配置文件
├── install.sh                  # 自动安装脚本
├── agents/                     # 标准化角色定义（默认 pack + 自定义 pack）
│   ├── ceo.md                  # default pack：主控编排角色
│   ├── coo.md                  # default pack：运营调度角色
│   ├── ...                     # default pack：其他 sub-agent
│   └── <pack>/                 # 可选：行业/企业角色包
│       ├── ceo.md
│       └── ...
├── strategy/                   # 工作流层（模式、交接模板、runbook）
│   ├── QUICKSTART.md           # OPC-Micro / Sprint / Control
│   ├── coordination/           # 标准交接模板
│   └── runbooks/               # 场景化 runbook
├── dashboard/                  # 本地可视化看板
│   └── index.html              # 单文件看板页面
├── tools/                      # CLI 工具层
│   ├── agent_catalog.py        # 角色目录 lint / manifest
│   ├── agent_convert.py        # 平台角色转换器
│   ├── task_flow.py            # 任务状态机
│   ├── decision_log.py         # 决策履历管理
│   ├── risk_score.py           # 风险量化评分
│   ├── memory_sync.py          # 三级记忆系统
│   ├── agent_ops.py            # 主从 agent、派发任务与模型路由
│   ├── dashboard.py            # 集成看板 API 与本地服务
│   ├── config.py               # 配置管理
│   ├── storage.py              # 存储抽象层
│   └── utils.py                # 通用工具
├── adapters/                   # 平台适配器（可选）
│   ├── claude_code.md          # Claude Code 特定说明
│   ├── openclaw.md             # OpenClaw 特定说明
│   ├── cursor.md               # Cursor 特定说明
│   └── api.json                # Function schema
└── data/                       # 数据存储
    ├── MEMORY.md               # 记忆文件
    ├── tasks/                  # 任务状态
    ├── decisions/              # 决策履历
    ├── risks/                  # 风险记录
    ├── agents/                 # agent 状态与模型配置
    ├── assignments/            # 主 agent 派发给 sub-agent 的任务
    ├── dashboard/              # 看板导出 JSON
    ├── memory/                 # 三级记忆
    └── logs/                   # 操作日志
```

---

## 🔧 支持的平台

| 平台 | 状态 | 安装方式 | 使用方式 |
|------|------|---------|---------|
| Claude Code | ✅ | `./install.sh -p claude_code` | 自然语言指令 |
| OpenClaw | ✅ | `./install.sh -p openclaw` | 直接下达指令 |
| Cursor | ✅ | `./install.sh -p cursor` | Composer 中使用 |
| Windsurf | ✅ | `./install.sh -p windsurf` | 直接下达指令 |
| 通用 CLI | ✅ | `./install.sh -p generic` | System prompt |
| API 调用 | ✅ | `./install.sh -p api` | Function calling |

详细部署说明请查看 [DEPLOYMENT.md](DEPLOYMENT.md)。

---

## 📚 CLI 工具使用

### task_flow.py - 任务状态机

```bash
# 创建任务
python3 tools/task_flow.py create --title "任务标题" --ceo-input "CEO输入"

# 定级
python3 tools/task_flow.py assess --task-id T001 --level L3 --reason "原因"

# 状态流转
python3 tools/task_flow.py transition --task-id T001 --to in_strategy --actor "COO魏明远"

# 上报进度（可选绑定 agent，看板会自动同步）
python3 tools/task_flow.py progress --task-id T001 --message "进展描述" --progress 50 --agent-id strategist

# 查询状态
python3 tools/task_flow.py status --task-id T001
```

### agent_catalog.py - 角色目录

```bash
# 查看可用角色 pack
python3 tools/agent_catalog.py list-packs

# 校验角色 schema 与章节
python3 tools/agent_catalog.py lint

# 校验某个自定义 pack
python3 tools/agent_catalog.py lint --pack enterprise

# 查看当前内置角色目录
python3 tools/agent_catalog.py list

# 导出 Markdown 目录清单
python3 tools/agent_catalog.py manifest --format markdown

# 从 default 复制一个新 pack
python3 tools/agent_catalog.py scaffold-pack --from-pack default --to-pack enterprise
```

当前 `default` pack 的 20 个角色按链路分成几组：

- 主控与调度：`ceo`、`coo`、`project`
- 策略与研究：`strategist`、`research`
- 产品与体验：`product`、`ux`
- 增长与商业化：`marketing`、`growth`、`sales`、`brand`
- 技术与交付：`tech`、`devops`、`qa`、`data`
- 经营与保障：`finance`、`procurement`、`customer_success`、`hr`、`legal`

### agent_convert.py - 平台转换器

```bash
# 查看支持的平台
python3 tools/agent_convert.py list-tools

# 查看支持导出的角色 pack
python3 tools/agent_convert.py list-packs

# 导出 OpenClaw 集成文件
python3 tools/agent_convert.py export --tool openclaw --out output/integrations

# 导出 API 集成文件
python3 tools/agent_convert.py export --tool api --out output/integrations

# 导出某个自定义 pack 的所有平台文件
python3 tools/agent_convert.py export --tool all --pack enterprise --out output/integrations

# 一次性导出所有平台集成文件
python3 tools/agent_convert.py export --tool all --out output/integrations
```

安装脚本在 `claude_code / openclaw / cursor / windsurf / generic / api` 模式下都会自动生成对应平台的集成文件。默认 pack 会输出到目标 bundle 的 `integrations/<tool>/`，或仓库根下的 `output/integrations/<tool>/`；自定义 pack 则对应输出到 `integrations/<pack>/<tool>/` 或 `output/integrations/<pack>/<tool>/`。

### decision_log.py - 决策履历

```bash
# 创建决策
python3 tools/decision_log.py create \
  --task-id T001 \
  --decision-id D001 \
  --title "定价策略" \
  --options "方案A,方案B,方案C" \
  --chosen "方案B" \
  --reason "理由" \
  --assumptions "假设1:描述1,假设2:描述2"

# 更新假设
python3 tools/decision_log.py update-assumption \
  --decision-id D001 \
  --assumption-id 1 \
  --status "证伪" \
  --actual "实际情况" \
  --trigger-review

# 回填结果
python3 tools/decision_log.py backfill \
  --decision-id D001 \
  --result "成功" \
  --metrics "转化率8%" \
  --lessons "经验教训"
```

### risk_score.py - 风险评分

```bash
# 评估风险
python3 tools/risk_score.py assess \
  --task-id T001 \
  --risk-name "获客成本过高" \
  --probability 3 \
  --impact 4 \
  --mitigation "先做小测试"

# 更新风险
python3 tools/risk_score.py update \
  --risk-id R001 \
  --status "已发生" \
  --actual-impact 3

# 查询风险
python3 tools/risk_score.py list --task-id T001 --min-level 3
```

### memory_sync.py - 三级记忆

```bash
# 写入 L0（即时记忆）
python3 tools/memory_sync.py write --level L0 --task-id T001 --content "内容"

# 压缩到 L1（短期记忆）
python3 tools/memory_sync.py compress --task-id T001 --summary "摘要"

# 归档到 L2（长期记忆）
python3 tools/memory_sync.py archive --category "CEO偏好" --content "内容"

# 同步到 MEMORY.md
python3 tools/memory_sync.py sync --task-id T001
```

### agent_ops.py - 主从 Agent / 派发 / 模型配置

```bash
# 初始化默认主从 agent 注册表
python3 tools/agent_ops.py init

# 查看可用角色 pack
python3 tools/agent_ops.py list-packs

# 切换到某个角色 pack
python3 tools/agent_ops.py switch-pack --pack enterprise

# 查看所有 agent
python3 tools/agent_ops.py list

# 由 CEO 主 agent 派发 sub-agent 任务
python3 tools/agent_ops.py dispatch \
  --from-agent ceo \
  --to-agent strategist \
  --title "输出三套策略方案" \
  --brief "给出方案、风险和收敛建议" \
  --task-id T001 \
  --task-title "评估知识付费可行性" \
  --auto-start

# 查看最近派发任务
python3 tools/agent_ops.py list-assignments --open-only

# 设置某个 agent 的运行状态
python3 tools/agent_ops.py set-status \
  --agent-id strategist \
  --status running \
  --task-id T001 \
  --progress 35 \
  --message "策略官开始分析" \
  --assignment-id A001 \
  --assigned-by ceo

# 给某个 agent 配独立模型
python3 tools/agent_ops.py set-model \
  --agent-id strategist \
  --source custom_api \
  --provider openai \
  --model gpt-4.1 \
  --api-key-env OPENAI_API_KEY

# 把某个 agent 切回宿主默认模型
python3 tools/agent_ops.py set-model --agent-id strategist --source platform_default

# 按任务级别查看推荐编组
python3 tools/agent_ops.py recommend --level L3

# 按任务标题 / 复杂度关键词自动判断是否满编
python3 tools/agent_ops.py recommend --title "集团级跨部门复杂任务" --reason "用户指定全员协同"
```

### dashboard.py - 本地可视化看板

```bash
# 输出摘要 JSON
python3 tools/dashboard.py summary --pretty

# 导出摘要文件
python3 tools/dashboard.py export

# 启动本地看板
python3 tools/dashboard.py serve --host 127.0.0.1 --port 8765
```

### strategy/ - 工作流运行模板

```bash
# 查看三种标准运行模式
sed -n '1,220p' strategy/QUICKSTART.md

# 打开标准交接模板
sed -n '1,220p' strategy/coordination/handoff-templates.md

# 查看一个场景 runbook
sed -n '1,220p' strategy/runbooks/scenario-enterprise-feature.md
```

---

## 🎯 任务分级

| 级别 | 特征 | 处理方式 | 预计时间 |
|------|------|----------|----------|
| L1 | 简单查询/执行 | `daily`：3 个常驻 sub-agent | <5分钟 |
| L2 | 有限判断 | `daily`：3 个常驻 sub-agent | 5-30分钟 |
| L3 | 多方案+风险 | `important`：8 个核心 sub-agent | 30分-2小时 |
| L4 | 战略级 | `full`：满编 20 角色协同 | 2小时以上 |

---

## 🔐 风险评分矩阵

| 等级 | 描述 | 处理方式 |
|------|------|----------|
| 1 | 可忽略 | 顺带处理 |
| 2 | 低危 | 监控即可 |
| 3 | 中危 | 必须有应对预案 |
| 4 | 高危 | 升级处理，建议暂缓 |
| 5 | 致命 | 触发停止机制 |

**计算公式**: 概率(1-5) × 影响(1-5) → 风险等级(1-5)

---

## ⚙️ 配置说明

### 配置文件 (config.json)

```json
{
  "version": "4.4.0",
  "platform": "generic",
  "paths": {
    "tasks_dir": "${data_dir}/tasks",
    "agents_dir": "${data_dir}/agents",
    "assignments_dir": "${data_dir}/assignments",
    "dashboard_dir": "${data_dir}/dashboard"
  },
  "storage": {
    "backend": "file",  // file / sqlite
    "file_lock": true,
    "auto_backup": false
  },
  "features": {
    "readonly_mode": false,
    "auto_sync_memory": true,
    "sla_check_enabled": true,
    "risk_alert_threshold": 3
  },
  "agent_defaults": {
    "model": {
      "source": "platform_default"
    }
  },
  "model_catalog": {
    "custom_models": []
  },
  "dashboard": {
    "host": "127.0.0.1",
    "port": 8765,
    "refresh_seconds": 8
  },
  "orchestration": {
    "main_agent_id": "ceo",
    "agent_pack": "default",
    "default_profile": "daily",
    "dispatch_profiles": {
      "daily": {
        "sub_agent_target": 3,
        "agent_ids": ["coo", "project", "strategist"]
      },
      "important": {
        "sub_agent_target": 8,
        "agent_ids": ["coo", "project", "strategist", "research", "product", "tech", "data", "qa"]
      },
      "full": {
        "sub_agent_target": 20,
        "agent_ids": "__all_sub_agents__"
      }
    }
  }
}
```

### 环境变量

```bash
export OPC_HOME="/path/to/opc-team"
export OPC_CONFIG="/custom/path/config.json"
```

---

## 🐛 故障排查

### 找不到 Python

```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt-get install python3
```

### 文件锁失败（Windows）

```bash
pip install filelock
```

### 权限被拒绝

```bash
chmod -R 755 data/
```

更多问题请查看 [DEPLOYMENT.md](DEPLOYMENT.md) 的故障排查章节。

---

## 📖 完整示例

### L3 任务完整流程

```bash
# 1. 创建任务
python3 tools/task_flow.py create \
  --title "评估知识付费可行性" \
  --ceo-input "我想做知识付费，不知道怎么定价"

# 2. 定级
python3 tools/task_flow.py assess --task-id T001 --level L3 --reason "需要多方案"

# 3. 进入策略阶段
python3 tools/task_flow.py transition --task-id T001 --to in_strategy --actor "COO魏明远"

# 4. 策略官评估风险
python3 tools/risk_score.py assess \
  --task-id T001 \
  --risk-name "获客成本过高" \
  --probability 3 \
  --impact 4 \
  --mitigation "先做10人内测"

# 5. 创建决策履历
python3 tools/decision_log.py create \
  --task-id T001 \
  --decision-id D001 \
  --title "定价策略" \
  --chosen "方案B" \
  --assumptions "假设1:获客成本<50元,假设2:转化率>5%"

# 6. 进入执行阶段
python3 tools/task_flow.py transition --task-id T001 --to in_execution --actor "COO魏明远"

# 7. 完成任务
python3 tools/task_flow.py transition --task-id T001 --to completed --actor "COO魏明远"

# 8. 同步记忆
python3 tools/memory_sync.py sync --task-id T001
```

---

## 🔄 版本历史

- **v4.4.0** (2026-04-17): 默认角色扩充到 20 个，补充 `strategy/` 工作流层、handoff 模板与场景 runbook，强化 pack 化编排说明
- **v4.3.0** (2026-04-13): 新增 `CEO主Agent -> sub-agent` 主从编排、派发任务记录、多 agent 独立模型路由、可写集成看板与 dashboard API
- **v4.2.3** (2026-04-10): 修复 completed 状态未自动收敛到 100% 进度、同任务并发写可能覆盖进度的问题，保持运行时语义与版本同步
- **v4.2.2** (2026-04-09): 修复 CLI 失败返回码、Windows 运行时锁、参数校验、平台参数初始化
- **v4.2.1** (2026-04-09): 修复 readonly_mode 写入穿透、平台安装后配置未适配、版本号治理
- **v4.2.0** (2026-04-09): 用户反馈优化版 - 修复并发ID撞号、-p参数覆盖、只读模式、auto_sync_memory、文档降噪
- **v4.1.0** (2026-04-08): 修复安装链路、路径配置、storage bug、SKILL.md args
- **v4.0.0** (2026-04-08): 跨平台通用版，支持多平台、配置系统、存储抽象层
- **v3.0.0** (2026-04-08): 文档版，整合所有历史版本（已废弃）
- **v2.5.0**: 记忆系统集成
- **v2.1.0**: 三级记忆 + 辩论机制
- **v2.0.0**: MBTI + 古文 + 思维框架
- **v1.2.0**: 廷议模式 + 上游传递
- **v1.1.0**: 基础版本

---

## 📄 License

MIT

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

---

## 📧 联系方式

如有问题，请联系：
- **作者**: Blake徐
- **微信**: 488137
- **GitHub**: [@HeiGeAi](https://github.com/HeiGeAi)

---

## 🙏 致谢

本项目受 [edict](https://github.com/cft0808/edict) 启发，采用了状态机 + CLI 工具的架构思想。
