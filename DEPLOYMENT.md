# OPC Team - 多平台部署指南

## 支持的平台

- ✅ Claude Code
- ✅ OpenClaw
- ✅ Cursor
- ✅ Windsurf
- ✅ 通用 CLI（任何支持命令执行的 AI）
- ✅ API 调用（通过 function calling）

---

## 快速安装

### 自动安装（推荐）

```bash
cd opc-team
./install.sh
```

安装脚本会自动：
1. 检测你的 AI 平台
2. 检查 Python 环境
3. 安装依赖
4. 初始化配置
5. 创建数据目录
6. 设置环境变量

### 手动安装

```bash
# 1. 创建数据目录
mkdir -p data/{tasks,decisions,risks,memory,logs}

# 2. 初始化配置
python3 tools/config.py init

# 3. 初始化记忆系统
python3 tools/memory_sync.py init

# 4. 测试安装
python3 tools/task_flow.py create --title "测试" --ceo-input "测试安装"
```

---

## 平台特定配置

### 1. Claude Code

**安装位置**：`~/.claude/skills/opc-team/`

**安装步骤**：
```bash
./install.sh -p claude_code
```

**使用方式**：
- 在 Claude Code 中直接下达自然语言指令
- Claude 会自动加载 SKILL.md 并执行

**验证**：
```bash
# 在 Claude Code 中
评估知识付费可行性
```

---

### 2. OpenClaw

**安装位置**：`~/.openclaw/workspace-{agent}/skills/opc-team/`

**安装步骤**：
```bash
./install.sh -p openclaw -a <agent-id>
# 例如: ./install.sh -p openclaw -a default
```

**使用方式**：
- OpenClaw 会自动加载 skills 目录下的 SKILL.md
- 直接下达指令即可

**验证**：
```bash
# 在 OpenClaw 中
评估知识付费可行性
```

---

### 3. Cursor

**安装位置**：项目根目录的 `.cursorrules`

**安装步骤**：
```bash
cd your-project
cp /path/to/opc-team/SKILL.md .cursorrules
# 或者
./install.sh -p cursor
```

**使用方式**：
- Cursor 会自动加载 `.cursorrules`
- 在 Composer 中说"用 opc-team 评估"

**验证**：
```bash
# 在 Cursor Composer 中
用 opc-team 评估知识付费可行性
```

**注意事项**：
- Cursor 的命令执行需要用户确认
- 建议在 Settings 中启用 "Auto-approve safe commands"

---

### 4. Windsurf

**安装位置**：项目根目录的 `.windsurfrules`

**安装步骤**：
```bash
cd your-project
cp /path/to/opc-team/SKILL.md .windsurfrules
# 或者
./install.sh -p windsurf
```

**使用方式**：
- Windsurf 会自动加载 `.windsurfrules`
- 直接下达指令即可

**验证**：
```bash
# 在 Windsurf 中
评估知识付费可行性
```

---

### 5. 通用 CLI（任何 AI）

**适用场景**：
- 使用 API 调用 Claude/GPT/其他模型
- 自建 AI 工具
- 不支持 skill 加载的平台

**安装步骤**：
```bash
./install.sh -p generic
```

**使用方式**：
1. 将 `SKILL.md` 的内容作为 system prompt 传给 AI
2. 确保 AI 有权限执行 `python3 tools/*.py` 命令
3. 下达指令

**示例（Python API 调用）**：
```python
import anthropic

# 读取 SKILL.md
with open("SKILL.md", "r") as f:
    skill_content = f.read()

client = anthropic.Anthropic(api_key="your-api-key")

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    system=skill_content,  # 将 SKILL.md 作为 system prompt
    messages=[
        {"role": "user", "content": "评估知识付费可行性"}
    ]
)

print(message.content)
```

---

### 6. API 调用（Function Calling）

**适用场景**：
- 使用 OpenAI / Anthropic / 其他支持 function calling 的 API
- 需要更严格的工具调用控制

**安装步骤**：
```bash
./install.sh -p api
```

**Function Schema**：
参考 `adapters/api.json`，包含所有 CLI 工具的 function 定义。

**示例（OpenAI Function Calling）**：
```python
import openai
import json

# 读取 function schema
with open("adapters/api.json", "r") as f:
    functions = json.load(f)

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "你是 OPC Team 的 COO 魏明远..."},
        {"role": "user", "content": "评估知识付费可行性"}
    ],
    functions=functions,
    function_call="auto"
)

# 处理 function call
if response.choices[0].message.get("function_call"):
    function_name = response.choices[0].message["function_call"]["name"]
    arguments = json.loads(response.choices[0].message["function_call"]["arguments"])
    
    # 执行对应的 CLI 工具
    # ...
```

---

## 配置文件说明

### config.json

```json
{
  "version": "4.2.1",
  "platform": "generic",
  "paths": {
    "data_dir": "data",
    "tasks_dir": "${data_dir}/tasks",
    ...
  },
  "storage": {
    "backend": "file",  // file / sqlite
    "file_lock": true,
    "auto_backup": false
  },
  "features": {
    "readonly_mode": false,  // 只读模式（仅查询，不修改）
    "auto_sync_memory": true,
    "sla_check_enabled": true,
    "risk_alert_threshold": 3
  },
  "ai_platform": {
    "name": "generic",
    "tool_prefix": "python3 tools/",
    "supports_bash": true,
    "supports_function_calling": false
  }
}
```

### 自定义配置

```bash
# 修改配置
python3 tools/config.py set storage.backend sqlite
python3 tools/config.py set features.readonly_mode true

# 查看配置
python3 tools/config.py get storage.backend

# 适配到特定平台
python3 tools/config.py adapt claude_code
```

---

## 环境变量

### OPC_HOME

指定 OPC Team 的安装目录。

```bash
export OPC_HOME="/path/to/opc-team"
export PATH="$OPC_HOME/tools:$PATH"
```

### OPC_CONFIG

指定配置文件路径（默认：`$OPC_HOME/config.json`）。

```bash
export OPC_CONFIG="/custom/path/config.json"
```

---

## 权限要求

### 文件系统权限

- 读取：`SKILL.md`, `config.json`
- 写入：`data/` 目录下的所有文件
- 执行：`tools/*.py` 脚本

### 命令执行权限

不同平台的命令执行权限不同：

| 平台 | 权限模型 | 说明 |
|------|---------|------|
| Claude Code | 用户授权 | 首次执行需要用户批准 |
| OpenClaw | 完全控制 | Agent 可直接执行 |
| Cursor | 用户确认 | 每次执行需要确认 |
| Windsurf | 用户确认 | 每次执行需要确认 |
| API 调用 | 取决于实现 | 需要自行实现工具调用 |

---

## 故障排查

### 问题1：找不到 Python

**症状**：
```
python3: command not found
```

**解决方案**：
```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt-get install python3

# Windows
# 从 python.org 下载安装
```

### 问题2：文件锁失败（Windows）

**症状**：
```
ModuleNotFoundError: No module named 'fcntl'
```

**解决方案**：
```bash
pip install filelock
```

### 问题3：权限被拒绝

**症状**：
```
Permission denied: data/tasks/T001.json
```

**解决方案**：
```bash
chmod -R 755 data/
```

### 问题4：配置文件未找到

**症状**：
```
FileNotFoundError: config.json
```

**解决方案**：
```bash
python3 tools/config.py init
```

### 问题5：AI 不执行命令

**症状**：
AI 说"我会调用工具"，但实际没有执行。

**解决方案**：
- 检查 AI 平台是否支持命令执行
- 检查权限设置
- 尝试手动执行命令验证
- 查看 `data/logs/{date}.log` 日志

---

## 高级配置

### 使用 SQLite 存储

```bash
# 修改配置
python3 tools/config.py set storage.backend sqlite

# 重新初始化
python3 tools/config.py init
```

### 启用只读模式

```bash
python3 tools/config.py set features.readonly_mode true
```

只读模式下，所有写操作会被拒绝，仅支持查询。

### 启用自动备份

```bash
python3 tools/config.py set storage.auto_backup true
```

每次修改文件时会自动创建备份（`.bak` 文件）。

---

## 迁移指南

### 从 v3.0.0 迁移到 v4.0.0

v3.0.0 是纯文档版本，没有数据需要迁移。直接安装 v4.0.0 即可。

### 数据备份

当前版本还没有内置 `import/export` 子命令，直接备份 `data/` 目录即可：

```bash
mkdir -p backup
cp -R data backup/data
```

---

## 团队部署

### 多用户环境

每个用户独立安装：

```bash
# 用户 A
cd ~/opc-team-a
./install.sh

# 用户 B
cd ~/opc-team-b
./install.sh
```

### 共享数据目录

```bash
# 设置共享目录
export OPC_HOME="/shared/opc-team"

# 所有用户使用相同配置
python3 tools/config.py set paths.data_dir "/shared/opc-team/data"
```

**注意**：共享模式需要文件锁支持，避免并发冲突。

---

## 性能优化

### 减少日志写入

```bash
python3 tools/config.py set features.log_level error
```

### 禁用 SLA 检查

```bash
python3 tools/config.py set features.sla_check_enabled false
```

### 使用 SQLite 存储

SQLite 在大量任务时性能更好：

```bash
python3 tools/config.py set storage.backend sqlite
```

---

## 安全建议

1. **不要在公共仓库中提交 `data/` 目录**
   ```bash
   echo "data/" >> .gitignore
   ```

2. **定期备份数据**
   ```bash
   tar -czf opc-backup-$(date +%Y%m%d).tar.gz data/
   ```

3. **限制文件权限**
   ```bash
   chmod 700 data/
   ```

4. **使用环境变量存储敏感配置**
   ```bash
   export OPC_API_KEY="your-secret-key"
   ```

---

## 获取帮助

- 查看日志：`cat data/logs/$(date +%Y-%m-%d).log`
- 查看配置：`python3 tools/config.py info`
- 运行测试：`./install.sh -t`
- 提交 Issue：https://github.com/your-repo/opc-team/issues
