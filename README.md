# OPC Team — Cross-Platform Agent Ops Framework

![OPC Team agent ops hero](./assets/opc-team-hero.png)

[![Version](https://img.shields.io/badge/version-v4.2.3-111827.svg)](./README.md)
[![Python](https://img.shields.io/badge/python-3.7%2B-3776AB.svg?logo=python&logoColor=white)](./README.md)
[![Platforms](https://img.shields.io/badge/platform-Claude%20Code%20%7C%20OpenClaw%20%7C%20Cursor%20%7C%20Windsurf%20%7C%20API-0F766E.svg)](./DEPLOYMENT.md)
[![License](https://img.shields.io/badge/license-MIT-059669.svg)](./LICENSE)

> 把“靠 prompt 演戏”的 AI Agent，升级成“可调度、可追踪、可复盘”的执行系统。

**OPC Team** 是一个跨平台的 Agent 协作框架，目标不是再造一个角色扮演 prompt，而是给 AI 执行过程加上明确的工程化约束：任务状态机、决策履历、风险量化、三级记忆，以及一组可审计的 CLI 工具。它适合跑在 **Claude Code / OpenClaw / Cursor / Windsurf / 通用 CLI / API 工作流** 上，让 Agent 的执行过程从“看起来会做”变成“真的可控、可回放、可治理”。

[Quick Start](#-quick-start) · [Platform Matrix](#-supported-platforms) · [Deployment Guide](./DEPLOYMENT.md) · [Skill Manual](./SKILL.md) · [API Schema](./adapters/api.json)

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

## 真实任务跑出来是什么样

下面不是静态 Prompt 示例，而是用 OPC Team 本地状态机跑出的 3 个 L3 策略任务形态：每个任务都会生成任务状态、风险记录、决策履历和记忆摘要。

| 真实任务 | OPC Team 给出的主决策 | 风险控制 |
|---|---|---|
| 上班族如何发展副业 | 先做垂直技能服务，再内容化，最后产品化 | 控制每周投入节奏；先做访谈和低价 MVP，避免一上来重投入 |
| 2026 年自媒体账号怎么变现 | 高客单咨询/陪跑 + 知识产品，广告和联盟只做补充 | 不把平台分成当唯一收入；先设计高信任高客单承接链路 |
| 我 + AI 适合什么知识付费产品 | 模板库 + 清单 + 7 天短周期陪跑 | 避免大课和重社群；围绕明确结果交付，而不是堆知识点 |

这类输出会沉淀到 `data/tasks/`、`data/decisions/`、`data/risks/` 和 `data/MEMORY.md`，用于回放过程、复盘假设和追踪后续执行。

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
python3 tools/task_flow.py transition --task-id T001 --to in_execution --actor "COO魏明远"
python3 tools/task_flow.py transition --task-id T001 --to completed --actor "COO魏明远"
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
├── DEPLOYMENT.md               # 多平台部署指南
├── PLATFORM_ANALYSIS.md        # 平台兼容性分析
├── config.json                 # 配置文件
├── install.sh                  # 自动安装脚本
├── tools/                      # CLI 工具层
│   ├── task_flow.py            # 任务状态机
│   ├── decision_log.py         # 决策履历管理
│   ├── risk_score.py           # 风险量化评分
│   ├── memory_sync.py          # 三级记忆系统
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

# 上报进度
python3 tools/task_flow.py progress --task-id T001 --message "进展描述" --progress 50

# 查询状态
python3 tools/task_flow.py status --task-id T001
```

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

---

## 🎯 任务分级

| 级别 | 特征 | 处理方式 | 预计时间 |
|------|------|----------|----------|
| L1 | 简单查询/执行 | COO 直接调单一部门 | <5分钟 |
| L2 | 有限判断 | COO + 1-2部门评估 | 5-30分钟 |
| L3 | 多方案+风险 | 策略官 + 执行组 | 30分-2小时 |
| L4 | 战略级 | 廷议模式 | 2小时以上 |

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
  "version": "4.2.3",
  "platform": "generic",
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
- **作者**: Blake
- **微信**: 488137
- **GitHub**: [@HeiGeAi](https://github.com/HeiGeAi)

---

## 🙏 致谢

本项目受 [edict](https://github.com/cft0808/edict) 启发，采用了状态机 + CLI 工具的架构思想。
