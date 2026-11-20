"""复测通知与邀请复核。

硬规则：
- 通知只能从考务确认归属（confirmed）且在生效区间内的联系索引发出；
- 不能把两位候选人的联系方式一起交给老师；
- 未获核实的只能标“待联系”，簿上不得写“已安排”；
- 已发预约在确认被撤回后，按学员是否已确认区分停止发放/转人工，
  绝不悄悄更换预约接收人。
"""

from .links import CONFIRMED, POSSIBLE
from .cohort_analysis import NOT_RETAINED

# 邀请回执中学员侧已确认的状态
INVITATION_CONFIRMED = "confirmed"


def active_routes(route_rows, day):
    """某日仍生效的联系索引（from_day <= day < until_day，null 视为开放）。"""
    active = {}
    for row in route_rows:
        if row["from_day"] <= day and (row["until_day"] is None or day < row["until_day"]):
            active.setdefault(row["student"], []).append(row)
    return active


def _route_for(student, route_rows, day):
    return active_routes(route_rows, day).get(student, [])


def reconcile_invitations(tables, ledger, as_of):
    """逐条复核截至 as_of 已签发的历史邀请在当时及当前是否站得住。"""
    out = []
    for inv in sorted(tables["invitations"], key=lambda r: r["invitation"]):
        if inv["issued"] > as_of:
            continue  # 历史时点重放：尚未签发的邀请不进入台账
        edge = inv["basis"]
        state_now = ledger.state(edge)
        state_then = ledger.state_at_issuance(edge, inv["issued"])
        routes_then = [r for r in _route_for(inv["student"], tables["routes"], inv["issued"])
                       if r["contact"] == inv["contact"]]
        valid_at_issue = (state_then == CONFIRMED and bool(routes_then))
        basis_intact = state_now == CONFIRMED

        if valid_at_issue and basis_intact:
            disposition = "stands"              # 依据仍为确认，预约维持
        elif valid_at_issue and not basis_intact:
            if inv["status"] == INVITATION_CONFIRMED:
                disposition = "manual_review"   # 学员已确认：转人工核查，不得换发
            else:
                disposition = "stop_dispatch"   # 尚未确认：停止发放
        else:
            disposition = "invalid_at_issue"    # 签发当时依据就不足（审计异常）

        out.append({
            "invitation": inv["invitation"],
            "student": inv["student"],
            "skill": inv["skill"],
            "basis": edge,
            "contact": inv["contact"],
            "issued": inv["issued"],
            "status": inv["status"],
            "state_at_issue": state_then,
            "state_now": state_now,
            "route_active_at_issue": bool(routes_then),
            "disposition": disposition,
        })
    return out


def retest_actions(analysis, tables, ledger, as_of):
    """生成复测外联动作：可发邀请 / 待联系 / 资料不足，均不携带他人联系方式。"""
    routes = active_routes(tables["routes"], as_of)
    confirmed_edges = ledger.grouped().get(CONFIRMED, set())
    possible_edges = ledger.grouped().get(POSSIBLE, set())

    # 学员 -> 指向他的未决候选 edge
    possible_by_student = {}
    for edge in possible_edges:
        student, _site, _wave, _token = ledger.identity(edge)
        possible_by_student.setdefault(student, []).append(edge)

    issuable, pending, insufficient = [], [], []
    for cohort in analysis["cohorts"]:
        if not cohort["mature"]:
            continue  # 窗口未到/未到期的队列不安排复测
        for student_block in cohort["students"]:
            student = student_block["student"]
            for skill, info in student_block["skills"].items():
                # 未确认归属的记录一律不携带任何联系方式，避免把候选人号码外交
                record = {
                    "cohort": cohort["cohort"],
                    "student": student,
                    "skill": skill,
                    "status": info["status"],
                    "contacts": [],
                }
                if info["status"] == NOT_RETAINED:
                    # 未保持且归属已唯一确认，才允许发邀请
                    owned_confirmed = [e for e in confirmed_edges
                                       if ledger.identity(e)[0] == student]
                    if owned_confirmed and routes.get(student):
                        record["contacts"] = [r["contact"]
                                              for r in routes[student]]
                        record["basis_edges"] = sorted(owned_confirmed)
                        issuable.append(record)
                    elif owned_confirmed:
                        record["reason"] = "no_active_route"
                        insufficient.append(record)
                    else:
                        record["candidate_edges"] = sorted(
                            possible_by_student.get(student, []))
                        pending.append(record)
                elif info["status"] == "indeterminate":
                    # 归属未唯一：只能待联系，绝不能写已安排
                    record["candidate_edges"] = sorted(
                        possible_by_student.get(student, []))
                    pending.append(record)
                # retained / no_usable / disputed 不产生复测邀请

    return {
        "issuable": sorted(issuable, key=lambda r: (r["student"], r["skill"])),
        "pending_contact": sorted(pending, key=lambda r: (r["student"], r["skill"])),
        "insufficient": sorted(insufficient, key=lambda r: (r["student"], r["skill"])),
    }
