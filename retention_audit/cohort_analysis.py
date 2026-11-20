"""队列保持率分析：只在整批可行匹配上取界。

保持口径（README）：同一技能第二轮不少于第一轮，且首轮至少为 2，记为保持。
无辅助（independent=true）且落在观察窗内的作答才适用；没有数据可推断时
不得把分值填成零，配对缺失和无可用作答另列覆盖，不当作零。
"""

from collections import defaultdict

from .matching import build_tokens, enumerate_matchings, find_disputes
from .windows import cohort_mature, in_wave, window_status

RETAINED = "retained"          # R：已配对且判定保持
NOT_RETAINED = "not_retained"  # N：已配对且判定未保持
UNPAIRED = "unpaired"          # U：窗口已到期仍不能配对（不确定，留在分母）
NO_USABLE = "no_usable"        # X：无可用作答（如首轮窗口外/非无辅助）

# 教学组改进线：成熟有资格学员中至少 70% 保持
IMPROVEMENT_LINE = 0.70


def _applicable_rows(rows, ended, wave):
    """窗口内、无辅助的作答行；同技能重复行原样保留以便识别争议。"""
    return [r for r in rows
            if r["independent"] and in_wave(r["day"], ended, wave)]


def _student_tokens(matching, student):
    """该匹配中学员各轮认领的 token 键。"""
    owned = defaultdict(dict)
    for wave, assignment in matching["waves"].items():
        for key, (owner, _edge) in assignment.items():
            if owner == student:
                owned[wave][key] = _edge
    return owned


def _skill_rows(tokens, keys, skill):
    out = []
    for key in keys:
        token = tokens.get(key)
        if token:
            out.extend(token["skills"].get(skill, ()))
    return out


def _evaluate_matching(matching, cohort, tokens, disputes):
    """在一个整批匹配内给出每个 (学员, 技能) 的判定。"""
    ended = cohort["ended"]
    dispute_set = {(d["student"], d["skill"]) for d in disputes}
    per_student = {}

    for student in cohort["members"]:
        owned = _student_tokens(matching, student)
        per_student[student] = {}
        for skill in cohort["eligible"][student]:
            if (student, skill) in dispute_set:
                per_student[student][skill] = {
                    "status": "disputed",
                    "first": None,
                    "second": None,
                }
                continue

            first_rows = _applicable_rows(
                _skill_rows(tokens, owned.get(1, {}), skill), ended, 1)
            second_rows = _applicable_rows(
                _skill_rows(tokens, owned.get(2, {}), skill), ended, 2)

            if not first_rows:
                # 首轮无适用作答：第二轮无法判定迁移，不能填零
                per_student[student][skill] = {
                    "status": NO_USABLE,
                    "first": None,
                    "second": sorted({r["score"] for r in second_rows}) or None,
                }
                continue
            if not second_rows:
                # 首轮有适用作答但第二轮配不上对：成熟队列即“窗口到期仍不能
                # 配对”；未成熟队列是“窗口未到/未到期”，由窗口状态字段区分，
                # 两种情况都留在分母，不填零。
                per_student[student][skill] = {
                    "status": UNPAIRED,
                    "first": sorted({r["score"] for r in first_rows}),
                    "second": None,
                }
                continue

            first_score = first_rows[0]["score"]
            second_score = second_rows[0]["score"]
            kept = first_score >= 2 and second_score >= first_score
            per_student[student][skill] = {
                "status": RETAINED if kept else NOT_RETAINED,
                "first": first_score,
                "second": second_score,
            }
    return per_student


def _summarize(per_student):
    counts = defaultdict(int)
    for skills in per_student.values():
        for item in skills.values():
            counts[item["status"]] += 1
    return dict(counts)


def analyze_cohort(cohort_row, ledger, result_rows, as_of):
    """分析单个队列。cohort_row 由 analyze_all 预组装成员与资格映射。"""
    tokens = build_tokens(result_rows)
    ended = cohort_row["ended"]
    members = cohort_row["members"]
    matchings = enumerate_matchings(ledger, set(members))
    disputes = find_disputes(ledger, set(members), tokens, ended)
    mature = cohort_mature(ended, as_of)
    wstatus = window_status(ended, as_of)

    evaluations = [_evaluate_matching(m, cohort_row, tokens, disputes)
                   for m in matchings]
    summaries = [_summarize(e) for e in evaluations]

    def ext(status):
        values = [s.get(status, 0) for s in summaries]
        return {"min": min(values), "max": max(values)} if values else {"min": 0, "max": 0}

    denominator = sum(len(s) for s in cohort_row["eligible"].values())
    rate_min = rate_max = None
    line_crosses = []
    feasible = bool(matchings)
    if mature and denominator and feasible:
        rates = [s.get(RETAINED, 0) / denominator for s in summaries]
        rate_min, rate_max = min(rates), max(rates)
        line_crosses = sorted({round(r, 10) for r in rates if r >= IMPROVEMENT_LINE})

    # 每个 (学员, 技能) 在全部可行匹配中出现过的状态集合
    possible_status = defaultdict(set)
    for evaluation in evaluations:
        for student, skills in evaluation.items():
            for skill, item in skills.items():
                possible_status[(student, skill)].add(item["status"])

    students_out = []
    for student in members:
        skills_out = {}
        for skill in cohort_row["eligible"][student]:
            statuses = sorted(possible_status[(student, skill)])
            skills_out[skill] = {
                "statuses": statuses,
                "determined": len(statuses) == 1,
                "status": statuses[0] if len(statuses) == 1 else "indeterminate",
            }
        students_out.append({"student": student, "skills": skills_out})

    return {
        "cohort": cohort_row["cohort"],
        "mature": mature,
        "window_status": wstatus,
        "denominator": denominator,
        "disputes": disputes,
        "matching_count": len(matchings),
        "feasible": feasible,
        "coverage_ranges": {
            RETAINED: ext(RETAINED),
            NOT_RETAINED: ext(NOT_RETAINED),
            UNPAIRED: ext(UNPAIRED),
            NO_USABLE: ext(NO_USABLE),
            "disputed": ext("disputed"),
        },
        "retention_rate": {"min": rate_min, "max": rate_max},
        "improvement_line": IMPROVEMENT_LINE,
        "line_crossing_rates": line_crosses,
        "line_ever_crossed": bool(line_crosses),
        "students": students_out,
        "matchings": [
            {"edges": sorted(m["edges"]),
             "summary": summaries[i]}
            for i, m in enumerate(matchings)
        ],
    }


def analyze_all(tables, as_of):
    """组装队列成员并逐一分析；窗口未到的队列单独标注，不套用保持率。"""
    from .links import LinkLedger

    ledger = LinkLedger(tables["links"], as_of)
    cohorts = defaultdict(lambda: {"cohort": None, "ended": None,
                                   "members": [], "eligible": {}})
    for row in tables["cohorts"]:
        bucket = cohorts[row["cohort"]]
        bucket["cohort"] = row["cohort"]
        bucket["ended"] = row["ended"]
        bucket["members"].append(row["student"])
        bucket["eligible"][row["student"]] = list(row["eligible"])

    results = []
    for cohort_row in sorted(cohorts.values(),
                             key=lambda c: (c["ended"], c["cohort"])):
        results.append(analyze_cohort(cohort_row, ledger,
                                      tables["results"], as_of))
    return {
        "as_of": as_of,
        "open_edges": sorted(ledger.grouped().get("possible", set())),
        "cohorts": results}, ledger
