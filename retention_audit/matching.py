"""整批关联匹配引擎。

一个“可行匹配”必须同时满足：
1. 同一考点同一轮的同一次作答（token）不能被两个名册人认领；
2. 一个名册人同一轮最多认领一个 token；
3. ``confirmed`` 关联必须采用，``excluded`` 关联禁止采用；
4. ``possible`` 关联可以采用或不采用，但不得为凑齐人而按分数相似度配对
   —— 引擎只看关联台账，完全不读取分值。

区间只能在这些整批可行匹配之间取界，禁止逐人独立挑最好/最坏。
"""

from collections import defaultdict

from .links import CONFIRMED, EXCLUDED, POSSIBLE
from .windows import in_wave


def token_key(row):
    return (row["site"], row["wave"], row["token"])


def build_tokens(result_rows):
    """把按技能展开的作答行折叠成 token 记录。

    返回 {token_key: {"wave": int, "skills": {skill: row}}}；
    同一 token 同一技能若重复登记，保留全部行并打 duplicate 标记。
    """
    tokens = {}
    for row in result_rows:
        key = token_key(row)
        record = tokens.setdefault(key, {"wave": row["wave"], "skills": {}})
        bucket = record["skills"].setdefault(row["skill"], [])
        bucket.append(row)
    return tokens


def _wave_edges(ledger, cohort_students):
    """按轮次整理本队列学员的可用 edge。"""
    by_wave = defaultdict(lambda: {"confirmed": [], "possible": [], "token_edges": defaultdict(list)})
    for edge in ledger.edges:
        student, _site, wave, _token = ledger.identity(edge)
        if student not in cohort_students:
            continue
        state = ledger.state(edge)
        if state == EXCLUDED:
            continue
        entry = {"edge": edge, "student": student, "key": ledger.identity(edge)[1:]}
        bucket = by_wave[wave]
        bucket["token_edges"][entry["key"]].append(entry)
        if state == CONFIRMED:
            bucket["confirmed"].append(entry)
        elif state == POSSIBLE:
            bucket["possible"].append(entry)
    return by_wave


def _enumerate_wave(wave_bucket):
    """枚举单轮的全部可行分配，返回 [{token_key: (student, edge)}, ...]。"""
    token_edges = wave_bucket["token_edges"]
    assignment = {}
    student_used = set()

    # 先强制落实 confirmed 关联
    for entry in wave_bucket["confirmed"]:
        key, student, edge = entry["key"], entry["student"], entry["edge"]
        if key in assignment and assignment[key][0] != student:
            # 同一 token 被两条确认关联指向不同学员：硬矛盾，无可行匹配
            return []
        # 同学员同轮多条确认关联指向不同 token 不在此判无解：
        # 那是“两份同等有效作答”的争议，由 find_disputes 保留。
        assignment[key] = (student, edge)
        student_used.add(student)

    # 待分支的 token：含有候选 edge、且尚未被确认占用
    open_tokens = sorted(k for k in token_edges if k not in assignment)
    solutions = []

    def backtrack(index, current, used_students):
        if index == len(open_tokens):
            solutions.append(dict(current))
            return
        key = open_tokens[index]
        # 分支一：该 token 不分配给任何名册人（结果保留在图内，不强行配对）
        backtrack(index + 1, current, used_students)
        # 分支二：分配给某个候选学员（排除态已过滤）
        for entry in token_edges[key]:
            student, edge = entry["student"], entry["edge"]
            # 已因确认关联占用一个 token 的学员，不再经候选 edge 追加第二个；
            # 其多份确认作答走争议流程，而不是在这里扩张分配
            if student in used_students:
                continue
            current[key] = (student, edge)
            used_students.add(student)
            backtrack(index + 1, current, used_students)
            used_students.discard(student)
            del current[key]

    backtrack(0, assignment, student_used)
    return solutions


def enumerate_matchings(ledger, cohort_students):
    """枚举队列的全部整批可行匹配。

    返回列表，每项为 {"waves": {wave: {token_key: (student, edge)}},
    "edges": 采用的 edge 集合}，按 wave/token/edge 去重排序保证确定性。
    """
    by_wave = _wave_edges(ledger, cohort_students)
    wave_solutions = {}
    for wave, bucket in by_wave.items():
        wave_solutions[wave] = _enumerate_wave(bucket)
        if not wave_solutions[wave]:
            return []

    waves = sorted(wave_solutions)
    matchings = []

    def combine(index, waves_map, used_edges):
        if index == len(waves):
            matchings.append({"waves": {w: dict(m) for w, m in waves_map.items()},
                              "edges": frozenset(used_edges)})
            return
        wave = waves[index]
        for solution in wave_solutions[wave]:
            waves_map[wave] = solution
            edges = {edge for _student, edge in solution.values()}
            combine(index + 1, waves_map, used_edges | edges)
            del waves_map[wave]

    combine(0, {}, set())
    matchings.sort(key=lambda m: sorted((w, k, s, e) for w, m in m["waves"].items()
                                        for k, (s, e) in m.items()))
    return matchings


def find_disputes(ledger, cohort_students, tokens, ended):
    """同一学员同轮同技能存在两份同等有效作答时保留争议。

    判定：两个不同 token 都有指向该学员的 *已确认* 关联，且携带的该技能
    作答都落在对应窗口内且为无辅助（independent=true）。仅停留在候选
    （possible）阶段的多 token 可达属于归属歧义，由整批匹配的区间承载，
    不在此按“重复作答”处理，更不能用分高者代替。
    """
    # student -> wave -> set(token_key)（仅经确认关联可达）
    reach = defaultdict(lambda: defaultdict(set))
    for edge in ledger.edges:
        student, _site, wave, _token = ledger.identity(edge)
        if student not in cohort_students or ledger.state(edge) != CONFIRMED:
            continue
        reach[student][wave].add(ledger.identity(edge)[1:])

    disputes = []
    for student, per_wave in reach.items():
        for wave, keys in per_wave.items():
            by_skill = defaultdict(list)
            for key in keys:
                token = tokens.get(key)
                if token is None:
                    continue
                for skill, rows in token["skills"].items():
                    for row in rows:
                        if row["independent"] and in_wave(row["day"], ended, wave):
                            by_skill[skill].append(key)
            for skill, skill_keys in by_skill.items():
                unique = sorted(set(skill_keys))
                if len(unique) > 1:
                    disputes.append({
                        "student": student,
                        "wave": wave,
                        "skill": skill,
                        "tokens": unique,
                    })
    disputes.sort(key=lambda d: (d["student"], d["wave"], d["skill"]))
    return disputes
