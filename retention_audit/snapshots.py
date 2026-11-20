"""历史截止点重放：支持例会区间与已发复测安排的追溯。"""

from .cohort_analysis import analyze_all
from .outreach import reconcile_invitations, retest_actions
from .planning import review_plan


def snapshot_at(tables, as_of):
    """在任意资料获知日重放完整分析。"""
    analysis, ledger = analyze_all(tables, as_of)
    return {
        "as_of": as_of,
        "analysis": analysis,
        "invitations": reconcile_invitations(tables, ledger, as_of),
        "actions": retest_actions(analysis, tables, ledger, as_of),
        "plan": review_plan(tables, ledger, analysis, as_of),
    }


def lock_snapshots(tables):
    """对 locks 中每个例会截止点生成可追溯快照。"""
    return [
        {"issue": lock["issue"],
         "cohort": lock["cohort"],
         "snapshot": snapshot_at(tables, lock["day"])}
        for lock in sorted(tables["locks"], key=lambda r: r["issue"])
    ]
