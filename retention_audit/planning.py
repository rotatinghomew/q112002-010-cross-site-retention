"""有限核实时间的排期。

优先级不是“从最早一条开始排”，而是：
1. 先处理会使成熟队列总结跨过教学组改进线的歧义（关键 edge）；
2. 在同等关键性下，优先能一次消解多处歧义的证据包；
3. 证据包只能在 ready 之后、且不超过当日核实时间窗容量时安排，
   窗口容量按日独立，不能跨日借用。
"""

from .cohort_analysis import IMPROVEMENT_LINE, RETAINED
from .links import POSSIBLE


def consequential_edges(analysis):
    """返回会改变“是否跨过改进线”结论的候选 edge。

    判定：存在两个整批可行匹配，其采用的 edge 集合仅相差这一条，
    而一个跨过改进线、另一个不跨过——即该 edge 的取舍直接翻转结论。
    确认态 edge 是固定前提，不参与；未成熟队列不参与。
    """
    consequential = set()
    open_edges = set(analysis.get("open_edges", ()))
    for cohort in analysis["cohorts"]:
        if not cohort["mature"] or cohort["denominator"] == 0:
            continue
        # edge 集合 -> 该匹配是否跨线
        outcomes = {}
        for matching in cohort["matchings"]:
            edges = frozenset(matching["edges"])
            rate = matching["summary"].get(RETAINED, 0) / cohort["denominator"]
            outcomes[edges] = rate >= IMPROVEMENT_LINE
        edge_sets = list(outcomes)
        for i, left in enumerate(edge_sets):
            for right in edge_sets[i + 1:]:
                if outcomes[left] == outcomes[right]:
                    continue
                diff = left ^ right
                if len(diff) == 1:
                    consequential |= diff & open_edges
    return sorted(consequential)


def _ambiguous_edges(ledger):
    return set(ledger.grouped().get(POSSIBLE, set()))


def review_plan(tables, ledger, analysis, as_of):
    """生成证据包调阅计划与被跳过的包及原因。"""
    ambiguous = _ambiguous_edges(ledger)
    critical = set(consequential_edges(analysis))

    packages = []
    for pkg in tables["review_packages"]:
        resolvable = [e for e in pkg["edges"] if e in ambiguous]
        packages.append({
            "package": pkg["package"],
            "edges": list(pkg["edges"]),
            "minutes": pkg["minutes"],
            "ready": pkg["ready"],
            "resolvable_now": sorted(resolvable),
            "critical_edges": sorted(e for e in resolvable if e in critical),
        })

    # 关键 edge 优先；其次一次消解的歧义数量多者；再按 ready、耗时短者、包名
    def rank(p):
        return (
            0 if p["critical_edges"] else 1,
            -len(p["resolvable_now"]),
            -len(p["critical_edges"]),
            p["ready"],
            p["minutes"],
            p["package"],
        )

    ranked = sorted(packages, key=rank)
    windows = sorted((w for w in tables["review_windows"] if w["day"] >= as_of),
                     key=lambda w: w["day"])
    remaining = {w["day"]: w["minutes"] for w in windows}

    planned, skipped = [], []
    covered = set()  # 已选证据包将一并裁定的未决 edge
    for pkg in ranked:
        outstanding = [e for e in pkg["resolvable_now"] if e not in covered]
        if not pkg["resolvable_now"]:
            skipped.append({"package": pkg["package"],
                            "reason": "no_open_ambiguity"})
            continue
        if not outstanding:
            skipped.append({"package": pkg["package"],
                            "reason": "covered_by_earlier_package"})
            continue
        eligible_days = [d for d in remaining if d >= pkg["ready"]]
        fit_days = [d for d in eligible_days if remaining[d] >= pkg["minutes"]]
        if not fit_days:
            skipped.append({"package": pkg["package"],
                            "reason": "no_window_capacity"})
            continue
        day = fit_days[0]
        remaining[day] -= pkg["minutes"]
        covered.update(outstanding)
        planned.append({
            "package": pkg["package"],
            "day": day,
            "minutes": pkg["minutes"],
            "resolves": outstanding,
            "critical": any(e in critical for e in outstanding),
        })

    return {
        "consequential_edges": sorted(critical),
        "plan": sorted(planned, key=lambda p: (p["day"], p["package"])),
        "skipped": skipped,
        "window_load": [{"day": w["day"],
                         "capacity": w["minutes"],
                         "left": remaining[w["day"]]} for w in windows],
    }
