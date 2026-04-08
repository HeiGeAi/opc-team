# OPC Team 跨平台兼容性分析

## 当前版本的平台依赖问题

### 1. 文件路径硬编码
```python
# 当前实现
data_dir = Path.cwd() / "data" / "tasks"
```
**问题**: 
- 假设工作目录是 opc-team 根目录
- 不同 AI 工具的工作目录不同（Claude Code 可能在项目根，OpenClaw 可能在 workspace）

**解决方案**: 
- 引入环境变量 `OPC_HOME`
- 自动检测配置文件位置
- 支持相对路径和绝对路径

---

### 2. Skill 加载机制差异

| 平台 | Skill 加载方式 | 路径 |
|------|---------------|------|
| Claude Code | `~/.claude/skills/{skill_name}/SKILL.md` | 固定路径 |
| OpenClaw | `~/.openclaw/workspace-{agent}/skills/{skill_name}/SKILL.md` | Agent 隔离 |
| Cursor | 通过 `.cursorrules` 或 system prompt | 项目级 |
| Windsurf | 通过 `.windsurfrules` | 项目级 |
| 通用 CLI | 手动指定 prompt 文件 | 任意路径 |

**解决方案**:
- 提供多种加载方式的说明文档
- SKILL.md 使用纯 Markdown，不依赖特定平台语法
- 提供安装脚本自动适配

---

### 3. 工具调用方式差异

| 平台 | 工具调用 | 示例 |
|------|---------|------|
| Claude Code | Bash tool | `python3 tools/task_flow.py create ...` |
| OpenClaw | CLI 命令 | `python3 scripts/kanban_update.py ...` |
| Cursor | 终端命令 | 需要用户手动执行或通过 task |
| API 调用 | Function calling | 需要注册 function schema |

**解决方案**:
- CLI 工具保持独立，不依赖特定平台
- 提供 function schema 定义（可选，供 API 调用）
- 文档中说明不同平台的调用方式

---

### 4. 权限和沙箱限制

| 平台 | 文件操作 | 命令执行 | 网络访问 |
|------|---------|---------|---------|
| Claude Code | 需要用户授权 | 支持 Bash tool | 支持 |
| OpenClaw | 完全控制 | 支持 | 支持 |
| Cursor | 受限 | 需要用户确认 | 支持 |
| API 调用 | 取决于实现 | 取决于实现 | 取决于实现 |

**解决方案**:
- 所有文件操作通过 CLI 工具，不直接在 prompt 中读写
- 提供"只读模式"配置（仅查询，不修改）
- 文档中说明权限要求

---

### 5. 状态持久化

**当前实现**: 
- 数据存储在 `data/` 目录
- 依赖文件系统

**跨平台问题**:
- 某些平台可能没有持久化文件系统（如纯 API 调用）
- 多用户环境需要隔离

**解决方案**:
- 支持多种存储后端（文件系统 / SQLite / Redis）
- 通过配置文件选择
- 提供迁移工具

---

### 6. Python 环境依赖

**当前实现**:
- 依赖 Python 3.7+
- 使用标准库（json, pathlib, fcntl）

**跨平台问题**:
- Windows 不支持 fcntl（文件锁）
- 某些环境可能没有 Python

**解决方案**:
- 文件锁改用跨平台库（filelock）
- 提供 Docker 镜像（可选）
- 提供纯 Shell 脚本版本（简化版）

---

## 需要抽象的核心接口

### 1. 存储接口
```python
class Storage:
    def save(self, key: str, data: dict) -> None
    def load(self, key: str) -> dict
    def list(self, pattern: str) -> List[str]
    def delete(self, key: str) -> None
```

实现：
- FileStorage（当前）
- SQLiteStorage（可选）
- RedisStorage（可选）

### 2. 配置接口
```python
class Config:
    def get(self, key: str, default=None) -> Any
    def set(self, key: str, value: Any) -> None
    def load_from_file(self, path: str) -> None
```

### 3. 日志接口
```python
class Logger:
    def log(self, level: str, message: str, **kwargs) -> None
```

实现：
- FileLogger（当前）
- ConsoleLogger（可选）
- RemoteLogger（可选）

---

## 通用化改造清单

### 高优先级（必须）
1. ✅ 引入配置文件 `config.json`
2. ✅ 环境变量支持 `OPC_HOME`
3. ✅ 跨平台文件锁（filelock 库）
4. ✅ 安装脚本 `install.sh`
5. ✅ 多平台部署文档

### 中优先级（建议）
6. ⬜ SQLite 存储后端（可选）
7. ⬜ Function schema 定义（供 API 调用）
8. ⬜ Docker 镜像
9. ⬜ 只读模式配置

### 低优先级（未来）
10. ⬜ Web UI（可视化看板）
11. ⬜ Redis 存储后端
12. ⬜ 多用户权限系统

---

## 目标架构

```
opc-team/
├── config.json              # 配置文件（自动生成）
├── install.sh               # 通用安装脚本
├── SKILL.md                 # 通用 prompt（无平台依赖）
├── README.md                # 多平台部署说明
├── tools/                   # CLI 工具（跨平台）
│   ├── task_flow.py
│   ├── decision_log.py
│   ├── risk_score.py
│   ├── memory_sync.py
│   ├── config.py            # 配置管理
│   └── storage.py           # 存储抽象层
├── adapters/                # 平台适配器（可选）
│   ├── claude_code.md       # Claude Code 特定说明
│   ├── openclaw.md          # OpenClaw 特定说明
│   ├── cursor.md            # Cursor 特定说明
│   └── api.json             # Function schema
└── data/                    # 数据目录（可配置）
```

---

## 下一步行动

1. 实现配置系统（config.py）
2. 重构存储层（storage.py）
3. 编写安装脚本（install.sh）
4. 更新 SKILL.md（移除平台特定语法）
5. 编写多平台部署文档