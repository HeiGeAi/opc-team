# OpenClaw 平台适配说明

## 安装

```bash
cd opc-team
./install.sh -p openclaw
# 或指定角色 pack
./install.sh -p openclaw -k enterprise
```

安装时需要指定 agent ID（例如：default）。

安装脚本会自动将 skill 复制到 `~/.openclaw/workspace-{agent}/skills/opc-team/`。
同时会在 `integrations/openclaw/` 下生成平台参考文件。
如果使用自定义 pack，则输出路径会变成 `integrations/<pack>/openclaw/`。

生成文件包括：

- `SOUL.md`
- `IDENTITY.md`
- `AGENTS.md`
- `ROUTING.md`

---

## 使用方式

OpenClaw 会自动加载 skills 目录下的所有 SKILL.md 文件。

如果你想查看角色映射或把 OPC 进一步嵌入自己的 OpenClaw 组织结构，可以直接参考 `integrations/openclaw/` 下的导出文件。

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

## 常见问题

### Q: 如何指定 agent ID？

A: 使用 `./install.sh -p openclaw -a <agent-id>` 安装。

### Q: 可以在多个 agent 中使用吗？

A: 可以。每个 agent 有独立的 workspace，互不干扰。

### Q: 如何与其他 skills 协作？

A: 在 SKILL.md 中可以引用其他 skills，OpenClaw 会自动协调。

### Q: `SOUL.md / IDENTITY.md / AGENTS.md` 是做什么的？

A: 这是 OPC 角色目录自动导出的 OpenClaw 适配文件，方便你把角色层嵌入已有 OpenClaw 组织结构，而不必手写第二份角色文档。

---

## 最佳实践

1. **Agent 隔离**：为不同项目创建不同的 agent
2. **Skill 组合**：将 opc-team 与其他 skills 组合使用
3. **日志监控**：定期查看 `data/logs/` 了解执行情况
