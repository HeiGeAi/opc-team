# OPC Team — 样例运行

这个目录里的 JSON 都是真实跑出来的产物，不是文档示意。每个子目录对应一次完整任务生命周期（创建 → 定级 → 决策 → 风险评估 → 状态流转 → 完成），用来给你看 OPC Team 跑完一个 L3 策略任务后实际落了哪些可审计、可回放的数据。

## 复现方式

把命令贴进你的 opc-team 检出，跑完后对照 `examples/<topic>/` 下的产物即可。

```bash
# 用一个独立工作目录避免污染你现有的 data/
mkdir /tmp/my-run && cd /tmp/my-run
export OPC_CONFIG=/tmp/my-run/config.json
opc config init --platform generic
# 然后按各个样例的 README 命令逐条执行
```

或者用 `python3 tools/<name>.py ...` 写法，两者完全等价。

## 样例索引

### [T001-side-hustle/](./T001-side-hustle/) — 上班族如何发展副业

| 文件                          | 内容                                                              |
| ----------------------------- | ----------------------------------------------------------------- |
| [task.json](./T001-side-hustle/task.json) | 任务从 `created` → `assessed` → `in_strategy` → `in_execution` → `completed` 完整流转，含 4 次进度上报和 actor 履历 |
| [decision-D001.json](./T001-side-hustle/decision-D001.json) | 主决策：先做垂直技能服务，再内容化，最后产品化。含 3 条带状态的假设（招到时间/本职稳定/市场付费意愿）         |
| [risk-R001-high.json](./T001-side-hustle/risk-R001-high.json) | 高危风险（4 × 4 = 16，等级 4）：本职精力被侵占。含具体应对预案                |
| [risk-R002-low.json](./T001-side-hustle/risk-R002-low.json)   | 低危风险（3 × 3 = 9，等级 2）：前 6 个月零收入                              |
| [risk-R003-mid.json](./T001-side-hustle/risk-R003-mid.json)   | 中危风险（2 × 5 = 10，等级 3）：本职公司禁止副业                            |
| [MEMORY.md](./T001-side-hustle/MEMORY.md) | 任务完成时由 memory_sync 自动写入的 L2 长期记忆条目                  |

复现这一组产物的命令：

```bash
opc task create --title "上班族如何发展副业" \
  --ceo-input "我有本职工作，想用业余时间做副业。希望未来三年逐步增加收入，但不能影响主业"

opc task assess --task-id T001 --level L3 \
  --reason "策略类，需要多方案+风险评估"

opc task transition --task-id T001 --to in_strategy --actor "COO魏明远"

opc decision create --task-id T001 \
  --title "副业方向选择" \
  --options "方向A:做内容自媒体（个人IP）,方向B:做垂直技能服务（咨询/外包）,方向C:做信息差产品（电商/选品）" \
  --chosen "B → A → C 三阶段演进" \
  --reason "先做垂直技能服务变现最快、风险最低，建立专业信任..." \
  --assumptions "a1:每周能稳定投入15-20小时,a2:本职工作未来12个月不会大变动,a3:垂直技能在市场上有付费需求"

opc risk assess --task-id T001 --risk-name "本职工作精力被副业侵占" \
  --probability 4 --impact 4 \
  --mitigation "每周固定副业时间窗口..."

opc risk assess --task-id T001 --risk-name "前 6 个月零收入导致动力流失" \
  --probability 3 --impact 3 --mitigation "前 3 个月只做低价 MVP 验证付费意愿"

opc risk assess --task-id T001 --risk-name "本职公司禁止副业" \
  --probability 2 --impact 5 --mitigation "签约前看清楚劳动合同..."

opc task progress --task-id T001 --message "策略方案敲定：B→A→C 三阶段" --progress 40
opc task transition --task-id T001 --to in_execution --actor "COO魏明远"
opc task progress --task-id T001 --message "第一阶段服务包上线，收到 2 个付费客户" --progress 75
opc task transition --task-id T001 --to completed --actor "COO魏明远"
```

## 想看的几个细节

- **状态流转的 actor 履历**：打开 `task.json`，每个 `actors[]` 条目都记录了谁在什么时间做了什么动作，包括 COO 定级、状态推进、System 自动同步等。
- **L3 任务完成前的硬约束**：如果在 `decision_log create` 之前直接 transition 到 completed，状态机会拒绝（参考 `tests/test_task_flow.py::test_l3_completion_requires_decision_log`）。
- **风险等级的矩阵化**：4×4=16 自动落在「高危」（等级 4），同时 `alert` 字段被填上，提示需要应对预案。完整矩阵在 `tools/risk_score.py::calculate_risk_level`。
- **MEMORY.md 自动写入**：只有 `features.auto_sync_memory=true` 时才会触发；这个样例里 task 完成那一刻 memory_sync 把摘要 + 决策清单同步进 L2 长期记忆。
