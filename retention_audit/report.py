"""把分析结果渲染成可读的中文审计报告（纯数据，无外部依赖）。"""

from .cohort_analysis import (
    NO_USABLE, NOT_RETAINED, RETAINED, UNPAIRED,
)

_STATUS_CN_MATURE = {
    RETAINED: "保持",
    NOT_RETAINED: "未保持",
    UNPAIRED: "窗口到期仍未配对",
    NO_USABLE: "无可用作答",
    "disputed": "同技能重复作答争议",
    "indeterminate": "归属待定",
}

_STATUS_CN_PENDING = {
    RETAINED: "保持",
    NOT_RETAINED: "未保持",
    UNPAIRED: "第二轮窗口未到/未到期，暂不能配对",
    NO_USABLE: "无可用作答",
    "disputed": "同技能重复作答争议",
    "indeterminate": "归属待定",
}

_DISPOSITION_CN = {
    "stands": "维持有效",
    "stop_dispatch": "停止发放（学员尚未确认）",
    "manual_review": "转人工核查（学员已确认，不得换人）",
    "invalid_at_issue": "签发依据不足",
}


def _pct(value):
    return "—" if value is None else f"{value * 100:.0f}%"


def render_report(snapshot):
    """返回字符串报告。snapshot 由 snapshots.snapshot_at 生成。"""
    lines = []
    as_of = snapshot["as_of"]
    lines.append(f"资料获知截止日：第 {as_of} 天")
    lines.append("=" * 60)

    for cohort in snapshot["analysis"]["cohorts"]:
        lines.append("")
        lines.append(f"【队列 {cohort['cohort']}】成熟度："
                     f"{'成熟' if cohort['mature'] else '未成熟（窗口未到/未到期）'}"
                     f"（窗口状态 {cohort['window_status']}）")
        cov = cohort["coverage_ranges"]
        lines.append(
            "覆盖（整批可行匹配取界，分母 "
            f"{cohort['denominator']} 个有资格学员-技能）："
        )
        for status in (RETAINED, NOT_RETAINED, UNPAIRED, NO_USABLE, "disputed"):
            rng = cov[status]
            label = (_STATUS_CN_MATURE if cohort["mature"]
                     else _STATUS_CN_PENDING)[status]
            if rng["min"] == rng["max"]:
                lines.append(f"  - {label}: {rng['min']}")
            else:
                lines.append(f"  - {label}: {rng['min']}–{rng['max']}")
        lines.append(f"整批可行匹配数：{cohort['matching_count']}（区间只在这些互不矛盾的整批关联上取界）")
        if cohort["mature"]:
            rate = cohort["retention_rate"]
            lines.append(
                f"配对保持率区间：{_pct(rate['min'])} – {_pct(rate['max'])}"
                f"（改进线 {_pct(cohort['improvement_line'])}，"
                f"{'存在跨过线的整批关联' if cohort['line_ever_crossed'] else '任何整批关联均不跨线'}）"
            )
        if cohort["disputes"]:
            for d in cohort["disputes"]:
                lines.append(
                    f"  ! 争议保留：{d['student']} 第{d['wave']}轮 {d['skill']} "
                    f"存在多份同等有效作答 {d['tokens']}，不按高分取用"
                )
        lines.append("  学员-技能状态（跨全部可行匹配）：")
        status_map = (_STATUS_CN_MATURE if cohort["mature"]
                      else _STATUS_CN_PENDING)
        for block in cohort["students"]:
            for skill, info in block["skills"].items():
                if info["determined"]:
                    label = status_map[info["status"]]
                else:
                    label = "可能为：" + "、".join(
                        status_map[s] for s in info["statuses"])
                lines.append(f"    · {block['student']} {skill}: {label}")

    lines.append("")
    lines.append("-" * 60)
    lines.append("历史复测邀请复核：")
    for inv in snapshot["invitations"]:
        lines.append(
            f"  - {inv['invitation']} → {inv['student']} {inv['skill']}"
            f"（依据 {inv['basis']}，联系方式 {inv['contact']}，"
            f"签发日 {inv['issued']}，学员状态 {inv['status']}）："
            f"{_DISPOSITION_CN[inv['disposition']]}"
        )

    actions = snapshot["actions"]
    lines.append("")
    lines.append("可发复测邀请（归属已确认且联系方式生效，每次只给一人的号码）：")
    for item in actions["issuable"]:
        lines.append(f"  - {item['student']} {item['skill']}：{item['contacts']}（依据 {item['basis_edges']}）")
    if not actions["issuable"]:
        lines.append("  （无）")
    lines.append("待联系（核实前不得登记为已安排，不附候选人号码）：")
    for item in actions["pending_contact"]:
        lines.append(f"  - {item['student']} {item['skill']}：候选 {item['candidate_edges']}")
    if not actions["pending_contact"]:
        lines.append("  （无）")
    if actions["insufficient"]:
        lines.append("资料不足（归属确认但无生效联系方式等）：")
        for item in actions["insufficient"]:
            lines.append(f"  - {item['student']} {item['skill']}：{item['reason']}")

    plan = snapshot["plan"]
    lines.append("")
    lines.append("有限核实时间排期（优先消解多处歧义/跨线歧义，而非最早登记优先）：")
    if plan["consequential_edges"]:
        lines.append(f"  影响改进线结论的关键 edge：{plan['consequential_edges']}")
    else:
        lines.append("  当前没有任何 edge 的裁定会改变改进线结论。")
    for item in plan["plan"]:
        flag = "（含跨线关键歧义）" if item["critical"] else ""
        lines.append(
            f"  - 第 {item['day']} 天调阅 {item['package']}{flag}，"
            f"耗时 {item['minutes']} 分钟，一并裁定 {item['resolves']}"
        )
    for item in plan["skipped"]:
        reason = {"no_open_ambiguity": "已无未决歧义",
                  "covered_by_earlier_package": "所含歧义已被优先证据包一并裁定",
                  "no_window_capacity": "时间窗容量不足"}[item["reason"]]
        lines.append(f"  - 跳过 {item['package']}：{reason}")

    return "\n".join(lines)
