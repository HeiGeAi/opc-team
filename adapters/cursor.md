# Cursor 平台适配说明

## 安装

```bash
cd your-project
cp /path/to/opc-team/SKILL.md .cursorrules
# 或者
/path/to/opc-team/install.sh -p cursor
# 或者指定角色 pack
/path/to/opc-team/install.sh -p cursor -k enterprise
```

安装脚本会自动将 SKILL.md 追加到 `.cursorrules` 文件。
并且会在 `opc-team/integrations/cursor/` 下生成 `opc-team-catalog.mdc`，作为角色目录的 Cursor 规则版本。
如果使用自定义 pack，则输出路径会变成 `opc-team/integrations/<pack>/cursor/`。

---

## 使用方式

### 在 Composer 中使用

打开 Cursor Composer（Cmd/Ctrl + I），输入：

```
用 opc-team 评估知识付费可行性
```

或

```
启动 opc 团队分析这个项目
```

### 在 Chat 中使用

在 Chat 面板中也可以使用，但 Composer 的体验更好。

---

## 权限说明

Cursor 的命令执行需要用户确认：

1. **首次执行**：会弹出确认对话框
2. **后续执行**：可以选择"Always allow"
3. **建议配置**：在 Settings 中启用 "Auto-approve safe commands"

### 配置自动批准

1. 打开 Settings（Cmd/Ctrl + ,）
2. 搜索 "auto-approve"
3. 启用 "Auto-approve safe commands"
4. 添加白名单：`python3 tools/*.py`

---

## 工作目录

Cursor 的工作目录是当前打开的项目根目录。

建议在项目根目录下创建 `opc-team/` 目录：

```
your-project/
├── .cursorrules
├── opc-team/
│   ├── tools/
│   ├── data/
│   └── config.json
└── ...
```

---

## 与 .cursorrules 的集成

如果你已经有 `.cursorrules` 文件，安装脚本会自动追加内容。

你也可以手动编辑 `.cursorrules`，添加：

```markdown
# OPC Team

当用户要求评估商业可行性、制定策略、风险评估时，使用 opc-team。

[将 SKILL.md 的内容粘贴到这里]
```

---

## 多项目使用

### 方式1：每个项目独立安装

```bash
cd project-a
./install.sh -p cursor

cd project-b
./install.sh -p cursor
```

### 方式2：全局配置 + 项目引用

```bash
# 全局安装
export OPC_HOME="$HOME/.opc-team"
cd $OPC_HOME
./install.sh -p generic

# 在项目中引用
cd your-project
echo "source $OPC_HOME/SKILL.md" >> .cursorrules
```

---

## 常见问题

### Q: 为什么 Cursor 不执行命令？

A: 检查是否启用了 "Auto-approve safe commands"，或者手动批准执行。

### Q: 如何查看执行结果？

A: Cursor 会在 Composer 中显示命令输出。你也可以查看 `opc-team/data/logs/` 日志。

### Q: `opc-team-catalog.mdc` 有什么用？

A: 它是从 `agents/*.md` 自动生成的 Cursor 规则文件，适合放进 `.cursor/rules/` 或作为团队共享角色路由参考，而不是手工维护另一份角色说明。

### Q: 可以在 VS Code 中使用吗？

A: Cursor 是基于 VS Code 的，但 VS Code 本身不支持 `.cursorrules`。建议使用 Cursor 或其他支持的编辑器。

### Q: 命令执行太慢怎么办？

A: Cursor 的命令执行是同步的，复杂任务可能需要等待。建议将长时间任务拆分为多个步骤。

---

## 最佳实践

1. **项目级配置**：每个项目有独立的 `.cursorrules`
2. **自动批准**：启用安全命令自动批准，提高效率
3. **Composer 优先**：使用 Composer 而不是 Chat，体验更好
4. **定期清理**：定期清理 `data/` 目录，避免数据过多
5. **版本控制**：将 `.cursorrules` 加入 Git，团队共享配置

---

## 团队协作

如果团队使用 Cursor，可以将 `.cursorrules` 提交到 Git：

```bash
git add .cursorrules
git commit -m "Add opc-team skill"
git push
```

团队成员拉取代码后，Cursor 会自动加载规则。

**注意**：不要提交 `opc-team/data/` 目录，这是本地数据。

```bash
# .gitignore
opc-team/data/
```
