# Claude Code 平台适配说明

## 安装

```bash
cd opc-team
./install.sh -p claude_code
```

安装脚本会自动将 skill 复制到 `~/.claude/skills/opc-team/`。

---

## 使用方式

### 触发 Skill

在 Claude Code 中输入以下任一方式：

```
/opc 评估知识付费可行性
```

或

```
用 opc-team 评估一下要不要做知识付费
```

或

```
启动 opc 团队，分析这个项目的可行性
```

---

## 权限说明

Claude Code 使用权限审批机制：

1. **首次执行**：会提示用户批准工具调用
2. **后续执行**：可以在设置中配置自动批准
3. **建议配置**：允许自动执行 `python3 tools/*.py` 命令

---

## 工作目录

Claude Code 的工作目录通常是：
- 项目模式：项目根目录
- 全局模式：用户主目录

建议在项目根目录下使用 opc-team。

---

## 数据存储

数据存储在 `data/` 目录下，相对于当前工作目录。

如果需要跨项目共享数据，可以设置环境变量：

```bash
export OPC_HOME="$HOME/.opc-team"
```

---

## 常见问题

### Q: 为什么 Claude 说"我会调用工具"但没有执行？

A: 检查权限设置，确保允许执行 Python 命令。

### Q: 如何查看执行日志？

A: 日志存储在 `data/logs/{date}.log`，可以用 Read 工具查看。

### Q: 可以在多个项目中使用吗？

A: 可以。每个项目有独立的 `data/` 目录，互不干扰。

---

## 最佳实践

1. **项目级部署**：在每个项目根目录下安装 opc-team
2. **全局配置**：将 OPC_HOME 设置为全局目录，共享配置和记忆
3. **定期备份**：定期备份 `data/` 目录
4. **查看状态**：使用 `task_flow.py status` 查看任务进度