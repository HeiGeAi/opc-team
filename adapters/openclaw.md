# OpenClaw 平台适配说明

## 安装

```bash
cd opc-team
./install.sh -p openclaw
```

安装时需要指定 agent ID（例如：default）。

安装脚本会自动将 skill 复制到 `~/.openclaw/workspace-{agent}/skills/opc-team/`。

---

## 使用方式

OpenClaw 会自动加载 skills 目录下的所有 SKILL.md 文件。

直接下达指令即可：

```
评估知识付费可行性
```

或

```
用 opc-team 分析这个项目
```

---

## 权限说明

OpenClaw 的 Agent 拥有完全的命令执行权限，无需用户批准。

这意味着：
- ✅ 所有 CLI 工具可以直接执行
- ✅ 状态机流转自动进行
- ⚠️ 需要确保 Agent 的安全性

---

## 工作目录

OpenClaw 的工作目录是 `~/.openclaw/workspace-{agent}/`。

建议配置：

```bash
export OPC_HOME="$HOME/.openclaw/workspace-default/opc-team"
```

---

## 与 Edict 的集成

如果你同时使用 Edict（三省六部），可以将 opc-team 作为一个"部门"集成：

1. 在 `agents/` 目录下创建 `opc-team.md`
2. 将 SKILL.md 的内容复制进去
3. 在 SOUL.md 中引用 opc-team

示例：

```markdown
# agents/opc-team.md

## 角色定位
OPC Team 是一个专门负责商业决策的部门，由 COO 魏明远领导。

## 调用方式
当需要评估商业可行性、制定策略、风险评估时，调用 opc-team。

## 工具
- task_flow.py
- decision_log.py
- risk_score.py
- memory_sync.py
```

---

## 看板集成

如果你使用 Edict 的看板系统，可以将 opc-team 的任务同步到看板：

```bash
# 创建任务后
python3 scripts/kanban_update.py create \
  --task-id "OPC-T001" \
  --title "评估知识付费可行性" \
  --state "Doing"
```

---

## 常见问题

### Q: 如何指定 agent ID？

A: 安装时会提示输入，或者手动复制到对应目录。

### Q: 可以在多个 agent 中使用吗？

A: 可以。每个 agent 有独立的 workspace，互不干扰。

### Q: 如何与其他 skills 协作？

A: 在 SKILL.md 中可以引用其他 skills，OpenClaw 会自动协调。

---

## 最佳实践

1. **Agent 隔离**：为不同项目创建不同的 agent
2. **Skill 组合**：将 opc-team 与其他 skills 组合使用
3. **看板同步**：将任务同步到 Edict 看板，便于追踪
4. **日志监控**：定期查看 `data/logs/` 了解执行情况