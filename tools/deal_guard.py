#!/usr/bin/env python3
"""
deal_guard.py - OPC Team 接单预检器（Deal Guard）

把资深 OPC 从业者踩过的坑沉淀成确定性探测器。
接单/报价前，把客户原话或需求描述丢进来，自动扫出致命模式，给出规则和修复动作。

设计原则：
- 纯只读、零依赖（不碰 config / 存储 / 网络），任何环境都能跑，是接单前的第一道闸
- 命中即给「为什么危险 + 怎么修 + 归哪个角色管」，不止报警还给下一步
- 分数复用团队 1-5 风险语义：5=致命触发停止，4=高危建议暂缓，3=中危必须有预案

用法：
  python3 tools/deal_guard.py scan --text "客户说做好了帮我卖给几十个同行 按比例分账 前期开发费先不给"
  python3 tools/deal_guard.py scan --text "..." --active-fronts 2   # 叠加线程挤兑检查
  python3 tools/deal_guard.py rules                                  # 查看全部规则
"""

import argparse
import json


# ==================== 规则库（资深 OPC 从业者经验蒸馏） ====================
# 每条规则：命中任一 signal 即触发。severity 复用 1-5 团队风险语义。
RULES = [
    {
        "id": "huabing",
        "name": "画饼白嫖",
        "severity": 5,
        "owner": "sales / legal",
        "signals": ["分账", "分成", "按比例", "帮你卖", "帮你推", "帮你介绍客户",
                     "一起创业", "当合伙", "卖一套分", "卖一套给", "走量以后",
                     "做出来我帮", "我认识很多老板", "认识的老板", "资源置换",
                     "前期不给", "前期先不", "开发费先不", "后面分你", "后期分"],
        "rule": "上来就谈分账、资源置换、做好了帮你卖的，大概率想白嫖劳动力（无预付款+分账话术是经典白嫖信号）。",
        "fix": "拒绝纯分账。转成标准报价 + 先收预付款。对方不肯付首款就当假客户，直接放弃。"
    },
    {
        "id": "no_prepay",
        "name": "无预付款/先做后付",
        "severity": 4,
        "owner": "finance / sales",
        "signals": ["先做后付", "做好了再付", "做完再付", "验收后付", "验收再付",
                     "见效果再付", "见效果付", "先看效果", "不见效不付", "效果好再",
                     "先做样品", "免费样品", "先垫", "先干着", "账期", "月结", "押款"],
        "rule": "先收款再开工是铁律。不愿意付首款的客户不是真客户。",
        "fix": "小单标品全款到账开工；大单分期（预付30-40% / 交付款 / 尾款≤20%），加验收超期视为通过条款。"
    },
    {
        "id": "redline",
        "name": "触碰交付红线",
        "severity": 5,
        "owner": "tech / coo",
        "signals": ["内网", "本地部署到", "部署到我们电脑", "装在本地", "生产线",
                     "工艺", "智能工厂", "改造产线", "帮我们自己开发", "给源码自己改",
                     "我们自己改", "自己开发的功能", "驻场开发", "常驻我们公司"],
        "rule": "触碰交付红线（内网设备级部署 / 生产工艺改造 / 把开发权交给客户）会导致售后不可控、维护成本失控。红线清单按团队自身业务边界定义。",
        "fix": "私有部署只到服务器级；工艺/内网需求当场明确不接，可转介绍；加功能走工时制承接。"
    },
    {
        "id": "compliance",
        "name": "合规/效果宣称雷区",
        "severity": 4,
        "owner": "legal",
        "signals": ["根治", "疗效", "治好", "包好", "保证效果", "一定涨", "保证涨",
                     "涨粉保证", "包涨", "增收保证", "医美", "养生", "推拿", "除甲醛",
                     "保健", "祛痘保证", "药", "医疗"],
        "rule": "面客交付物说一句根治/疗效/营收承诺就是广告法问题，锅在交付方（健康、医疗、金融类客户高发）。",
        "fix": "面客交付三件套：敏感词过滤 + 免责声明 + 客户对最终输出负责；上线前跑一遍违禁词测试集。"
    },
    {
        "id": "wishmachine",
        "name": "许愿机式发散需求",
        "severity": 3,
        "owner": "product / sales",
        "signals": ["全都要", "都要", "什么都要", "都想要", "越多越好", "尽量多",
                     "先做着看", "想到再说", "你看着办", "智能一点", "高端大气",
                     "牛一点", "厉害一点", "反正就是", "类似那种"],
        "rule": "需求方把 AI 当许愿机，需求讲不清、边界无限扩。照单全收就退化成项目制。",
        "fix": "跑需求结构化话术收口，范围写进交付确认单；超出标品菜单即升档报价，让需求工程变涨价开关。"
    },
    {
        "id": "project_drift",
        "name": "项目制毛利黑洞",
        "severity": 3,
        "owner": "strategist / finance",
        "signals": ["定制", "按需开发", "无限次修改", "随时改", "随叫随到",
                     "长期维护免费", "一直跟着", "陪跑", "常驻", "专门为我们",
                     "我们情况特殊", "我们比较特殊", "全程跟进"],
        "rule": "交付闭环的隐性成本（需求/设计/运维/售后）会吃光毛利。非标不可复制=永远项目制。",
        "fix": "标品 SKU 锁死交付边界；定制走工时/正式合同；维护做订阅收费。每单模板沉淀入库，同类第二单交付时间大幅压缩。"
    },
    {
        "id": "acquaintance",
        "name": "熟人不签约",
        "severity": 3,
        "owner": "legal",
        "signals": ["朋友介绍", "熟人", "亲戚", "老乡", "兄弟", "关系好", "不用签",
                     "走个形式", "口头说", "信得过", "都是自己人", "不好意思提钱"],
        "rule": "越是熟人越要把规则讲清楚。没签书面约定，出纠纷时没有任何追讨依据。",
        "fix": "熟人单照走电子确认单/合同，先收款照旧。把规则前置说清是保护关系，不是不信任。"
    },
]

SEVERITY_LABEL = {
    5: "致命 · 触发停止，别接",
    4: "高危 · 建议暂缓，先补条款",
    3: "中危 · 必须有预案再接",
    2: "低危 · 监控即可",
    1: "可忽略 · 顺带处理",
}


def scan_text(text: str, active_fronts: int = 0):
    """扫描一段客户原话/需求描述，返回命中的风险模式。"""
    findings = []

    for rule in RULES:
        hits = [s for s in rule["signals"] if s in text]
        if hits:
            findings.append({
                "id": rule["id"],
                "name": rule["name"],
                "severity": rule["severity"],
                "severity_label": SEVERITY_LABEL[rule["severity"]],
                "owner": rule["owner"],
                "matched_signals": hits,
                "rule": rule["rule"],
                "fix": rule["fix"],
            })

    # 线程挤兑：不看客户文本，看主控手上同时开的战线数
    if active_fronts >= 2:
        findings.append({
            "id": "thread_contention",
            "name": "线程挤兑",
            "severity": 4,
            "severity_label": SEVERITY_LABEL[4],
            "owner": "ceo / coo",
            "matched_signals": [f"当前已开 {active_fronts} 条主战线"],
            "rule": "主控是单点，同时主攻超过 2 条战线必然互相挤兑注意力。大单的机会成本远高于小单，小单做得越顺越容易吃掉主线精力。",
            "fix": "本人同时主攻战役≤2 条。多出来的线降级给执行组按 SOP 跑或自动化承接，主线优先级绝对压过增量线。",
        })

    findings.sort(key=lambda f: f["severity"], reverse=True)

    max_sev = findings[0]["severity"] if findings else 0
    if max_sev >= 5:
        verdict = "STOP · 命中致命模式，不要接这个单，先按 fix 处理"
    elif max_sev == 4:
        verdict = "HOLD · 命中高危模式，补齐条款前不要开工"
    elif max_sev == 3:
        verdict = "CAUTION · 有中危模式，落实预案再接"
    else:
        verdict = "CLEAR · 未命中已知致命模式，仍按标准流程出确认单和收款"

    # 给出可执行下一步：把高危项落成团队风险记录
    next_actions = []
    for f in findings:
        if f["severity"] >= 3:
            next_actions.append(
                f"[{f['name']}] 建议登记为风险：risk_score.py assess --task-id <T> "
                f"--risk-name \"{f['name']}\" --probability 4 --impact {f['severity']} "
                f"--mitigation \"{f['fix'][:40]}...\""
            )
    next_actions.append("接单落地：出交付确认单 + 锁收款时点")

    return {
        "verdict": verdict,
        "max_severity": max_sev,
        "findings": findings,
        "finding_count": len(findings),
        "next_actions": next_actions,
    }


def list_rules():
    return {
        "rules": [
            {
                "id": r["id"],
                "name": r["name"],
                "severity": r["severity"],
                "severity_label": SEVERITY_LABEL[r["severity"]],
                "owner": r["owner"],
                "rule": r["rule"],
                "fix": r["fix"],
                "signal_count": len(r["signals"]),
            }
            for r in sorted(RULES, key=lambda x: x["severity"], reverse=True)
        ],
        "total": len(RULES),
        "note": "线程挤兑规则不靠文本命中，用 scan --active-fronts N 触发（N>=2 告警）。",
    }


def _emit(payload: dict):
    payload = {"success": True, **payload}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="OPC Team 接单预检器（Deal Guard）")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="扫描客户原话/需求描述")
    scan_p.add_argument("--text", required=True, help="客户原话或需求描述")
    scan_p.add_argument("--active-fronts", type=int, default=0,
                        help="主控当前同时主攻的主战线数量，>=2 触发线程挤兑告警")

    sub.add_parser("rules", help="列出全部预检规则")

    args = parser.parse_args()

    if args.command == "scan":
        _emit(scan_text(args.text, args.active_fronts))
    elif args.command == "rules":
        _emit(list_rules())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
