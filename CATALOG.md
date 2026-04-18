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

default pack 当前内置 20 个角色，覆盖主控编排、项目推进、策略研究、产品体验、增长商业化、技术交付、经营保障等完整链路。

| agent_id | 名称 | 类型 | 上级 | 核心能力 |
|---|---|---|---|---|
| `ceo` | 小黑子 | main | - | dispatch, model_routing, status_control, summary |
| `coo` | COO魏明远 | sub | `ceo` | task_assess, task_transition, memory_sync |
| `project` | 项目何安澜 | sub | `ceo` | task_progress, task_transition, memory_sync |
| `strategist` | 策略官苏然 | sub | `ceo` | task_progress, decision_create, risk_assess |
| `research` | 研究顾问顾闻舟 | sub | `ceo` | task_progress, decision_create |
| `product` | 产品周雨桐 | sub | `ceo` | task_progress |
| `ux` | 体验许知意 | sub | `ceo` | task_progress, risk_assess |
| `marketing` | 市场陈志远 | sub | `ceo` | task_progress, risk_assess |
| `growth` | 增长韩星野 | sub | `ceo` | task_progress, risk_assess |
| `sales` | 销售顾问顾霆 | sub | `ceo` | task_progress |
| `tech` | 技术李峥 | sub | `ceo` | task_progress, risk_assess |
| `devops` | 交付运维周策 | sub | `ceo` | task_progress, risk_assess |
| `qa` | 质控顾问唐宁 | sub | `ceo` | task_progress, risk_assess |
| `data` | 数据分析沈青岚 | sub | `ceo` | task_progress, decision_create |
| `finance` | 财务张晓燕 | sub | `ceo` | task_progress, risk_assess |
| `procurement` | 采购顾问宋嘉禾 | sub | `ceo` | task_progress, risk_assess |
| `brand` | 品牌林可欣 | sub | `ceo` | task_progress |
| `customer_success` | 客户成功程一诺 | sub | `ceo` | task_progress, memory_sync |
| `hr` | 组织人才陆蔚 | sub | `ceo` | task_progress, risk_assess |
| `legal` | 法务王建国 | sub | `ceo` | task_progress, risk_assess |

## default pack 分组

- 主控与调度：`ceo`、`coo`、`project`
- 策略与研究：`strategist`、`research`
- 产品与体验：`product`、`ux`
- 增长与商业化：`marketing`、`growth`、`sales`、`brand`
- 技术与交付：`tech`、`devops`、`qa`、`data`
- 经营与保障：`finance`、`procurement`、`customer_success`、`hr`、`legal`

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
