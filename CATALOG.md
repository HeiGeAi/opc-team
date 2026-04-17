# OPC Agent Catalog

OPC Team 现在把内置角色定义从 `tools/agent_ops.py` 中拆出，统一放在 `agents/*.md`，并支持通过 `agents/<pack>/*.md` 扩展行业/企业角色包。

## 为什么这样做

- 角色层和编排层分离，后续扩角色时不用直接改 orchestration 代码
- 每个角色都有统一 schema，便于 lint、适配和平台分发
- 可以继续往上叠加行业包、企业包或平台专用转换器

## 目录结构

- `agents/*.md`：default pack 的角色定义源文件
- `agents/<pack>/*.md`：自定义角色 pack
- `tools/agent_catalog.py`：schema 校验、清单导出、pack 发现与 pack 脚手架
- `tools/agent_convert.py`：导出平台适配文件（含 API）
- `tools/agent_ops.py`：从当前 pack 加载主从拓扑并支持切换

## 当前内置角色

| agent_id | 名称 | 类型 | 上级 | 核心能力 |
|---|---|---|---|---|
| `ceo` | CEO主Agent | main | - | dispatch, model_routing, status_control, summary |
| `coo` | COO魏明远 | sub | `ceo` | task_assess, task_transition, memory_sync |
| `strategist` | 策略官苏然 | sub | `ceo` | task_progress, decision_create, risk_assess |
| `product` | 产品周雨桐 | sub | `ceo` | task_progress |
| `marketing` | 市场陈志远 | sub | `ceo` | task_progress, risk_assess |
| `tech` | 技术李峥 | sub | `ceo` | task_progress, risk_assess |
| `finance` | 财务张晓燕 | sub | `ceo` | task_progress, risk_assess |
| `brand` | 品牌林可欣 | sub | `ceo` | task_progress |
| `legal` | 法务王建国 | sub | `ceo` | task_progress, risk_assess |

## Pack 机制

- `default`：仓库根下的 `agents/*.md`
- 自定义 pack：`agents/<pack>/*.md`
- `tools/agent_catalog.py list-packs`：列出可用 pack
- `tools/agent_catalog.py scaffold-pack --from-pack default --to-pack enterprise`：复制一个新 pack
- `tools/agent_ops.py switch-pack --pack enterprise`：切换运行中的 pack
- `tools/agent_convert.py export --tool all --pack enterprise --out output/integrations`：为指定 pack 导出所有平台适配文件

## 角色文件规范

每个角色文件由两部分组成：

1. JSON frontmatter
2. 固定章节正文

必填字段：

- `agent_id`
- `name`
- `role`
- `sort_order`
- `agent_type`
- `description`
- `capabilities`
- `aliases`

固定章节：

- `## 身份与记忆`
- `## 核心使命`
- `## 关键规则`
- `## 交付物`
- `## 工作流`

## 常用命令

```bash
# 查看可用角色 pack
python3 tools/agent_catalog.py list-packs

# 校验角色目录
python3 tools/agent_catalog.py lint

# 复制一个新 pack
python3 tools/agent_catalog.py scaffold-pack --from-pack default --to-pack enterprise

# 列出所有角色
python3 tools/agent_catalog.py list

# 导出 Markdown 清单
python3 tools/agent_catalog.py manifest --format markdown

# 导出 OpenClaw 平台文件
python3 tools/agent_convert.py export --tool openclaw --out output/integrations

# 导出 API 平台文件
python3 tools/agent_convert.py export --tool api --out output/integrations
```
