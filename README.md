# OPC Team - 跨平台通用版 v4.2.0

**版本**: v4.2.0 Universal Edition  
**类型**: 跨平台 Agent 协作框架

---

## 🌟 核心特性

- ✅ **跨平台通用**：支持 Claude Code / OpenClaw / Cursor / Windsurf / 通用 CLI / API 调用
- ✅ **强制 CLI 调用**：所有操作可追溯、可审计、可恢复
- ✅ **状态机约束**：防止非法流转，保证流程正确性
- ✅ **决策履历闭环**：假设追踪与证伪，48小时内重审
- ✅ **三级记忆系统**：L0/L1/L2，跨会话沉淀
- ✅ **量化风险评分**：1-5 级，中危以上必须有应对预案
- ✅ **自动安装脚本**：一键部署，自动检测平台

---

## 🚀 快速开始

### 1. 安装

```bash
cd opc-team
./install.sh
```

安装脚本会自动检测你的 AI 平台并完成配置。

### 2. 验证

```bash
python3 tools/task_flow.py create --title "测试任务" --ceo-input "测试安装"
```

### 3. 使用

根据你的平台：

**Claude Code**：
直接下达自然语言指令即可：
```
评估知识付费可行性
```

**OpenClaw / Cursor / Windsurf**：
```
评估知识付费可行性
```

**通用 CLI**：
将 `SKILL.md` 作为 system prompt 传给 AI。

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
  "version": "4.0.0",
  "platform": "generic",
  "storage": {
    "backend": "file",  // file / sqlite / redis
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