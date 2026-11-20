import unittest

from record_reader import read_records
from retention_audit import (
    LinkLedger,
    analyze_all,
    cohort_mature,
    in_wave,
    review_plan,
    snapshot_at,
    window_status,
)
from retention_audit.cohort_analysis import (
    IMPROVEMENT_LINE,
    NO_USABLE,
    NOT_RETAINED,
    RETAINED,
    UNPAIRED,
)
from retention_audit.links import CONFIRMED, EXCLUDED, POSSIBLE
from retention_audit.matching import build_tokens, enumerate_matchings
from retention_audit.outreach import active_routes, reconcile_invitations
from retention_audit.planning import consequential_edges


AS_OF = 26


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tables = read_records()

    def _ledger(self, as_of=AS_OF):
        return LinkLedger(self.tables["links"], as_of)

    def _cohort(self, name, as_of=AS_OF):
        analysis, _ = analyze_all(self.tables, as_of)
        return next(c for c in analysis["cohorts"] if c["cohort"] == name)

    # ---- 窗口与成熟度 -------------------------------------------------

    def test_wave_windows_are_inclusive(self):
        # ended=0 时窗口即偏移本身：第一轮 7-10，第二轮 14-18，首尾均计
        self.assertTrue(in_wave(7, 0, 1))
        self.assertTrue(in_wave(10, 0, 1))
        self.assertFalse(in_wave(11, 0, 1))
        self.assertTrue(in_wave(14, 0, 2))
        self.assertTrue(in_wave(18, 0, 2))
        self.assertFalse(in_wave(13, 0, 2))
        self.assertFalse(in_wave(19, 0, 2))
        # 真实队列（ended=1）的绝对日边界
        self.assertTrue(in_wave(8, 1, 1))
        self.assertTrue(in_wave(15, 1, 2))
        self.assertTrue(in_wave(19, 1, 2))

    def test_cohort_maturity_requires_wave2_closed(self):
        self.assertTrue(cohort_mature(1, 19))
        self.assertFalse(cohort_mature(1, 18))
        self.assertEqual(window_status(14, AS_OF), "wave2_open")
        self.assertEqual(window_status(1, AS_OF), "closed")

    # ---- 关联台账 -----------------------------------------------------

    def test_withdrawal_restores_possible_state(self):
        ledger = self._ledger()
        self.assertEqual(ledger.state("l9"), POSSIBLE)      # confirmed 后 withdrawn
        self.assertEqual(ledger.state("l5"), CONFIRMED)
        # day24 撤回尚未发生，l9 仍是确认
        self.assertEqual(ledger.state_at_issuance("l9", 24), CONFIRMED)

    def test_excluded_edges_never_matchable(self):
        rows = [
            {"edge": "e1", "student": "s1", "site": "东", "wave": 1,
             "token": "a", "state": EXCLUDED, "day": 5},
        ]
        ledger = LinkLedger(rows, AS_OF)
        matchings = enumerate_matchings(ledger, {"s1"})
        # 只剩排除态时唯一可行匹配就是不分配该 token
        self.assertEqual(len(matchings), 1)
        self.assertEqual(matchings[0]["edges"], frozenset())

    # ---- 整批匹配约束 -------------------------------------------------

    def test_token_cannot_be_claimed_by_two_students(self):
        ledger = self._ledger()
        matchings = enumerate_matchings(ledger, {"s1", "s2", "s3", "s4"})
        for matching in matchings:
            for wave, assignment in matching["waves"].items():
                seen_tokens, seen_students = set(), set()
                for key, (student, _edge) in assignment.items():
                    # 同轮内 token 与学员都必须一一对应
                    self.assertNotIn(key, seen_tokens)
                    self.assertNotIn(student, seen_students)
                    seen_tokens.add(key)
                    seen_students.add(student)

    def test_confirmed_edges_are_mandatory(self):
        ledger = self._ledger()
        matchings = enumerate_matchings(ledger, {"s1", "s2", "s3", "s4"})
        self.assertTrue(matchings)
        for matching in matchings:
            self.assertIn("l1", matching["edges"])
            self.assertIn("l2", matching["edges"])
            self.assertIn("l3", matching["edges"])
            self.assertIn("l4", matching["edges"])
            self.assertIn("l5", matching["edges"])  # day22 确认
            # l9 的确认已于 day26 撤回：恢复候选，可行匹配中可选可不选
        chosen = [m for m in matchings if "l9" in m["edges"]]
        self.assertTrue(chosen)
        self.assertLess(len(chosen), len(matchings))

    def test_confirmed_edge_is_mandatory_before_withdrawal(self):
        # day24 时点 l9 仍是确认态，所有整批匹配都必须采用
        ledger = self._ledger(24)
        matchings = enumerate_matchings(ledger, {"s1", "s2", "s3", "s4"})
        self.assertTrue(all("l9" in m["edges"] for m in matchings))

    def test_matching_never_uses_scores(self):
        # 调换分值不改变可行匹配集合（配对只看关联，不看分数相似度）
        ledger = self._ledger()
        baseline = enumerate_matchings(ledger, {"s1", "s2", "s3", "s4"})
        shuffled = [dict(r, score=4 - r["score"]) for r in self.tables["results"]]
        tokens_a = build_tokens(self.tables["results"])
        tokens_b = build_tokens(shuffled)
        self.assertEqual(set(tokens_a), set(tokens_b))
        self.assertEqual(len(baseline), 6)  # 组件1有2种 × 组件2有3种

    # ---- 保持率区间（整批取界） ---------------------------------------

    def test_mature_cohort_ranges_and_line(self):
        jia = self._cohort("甲")
        self.assertTrue(jia["mature"])
        self.assertEqual(jia["denominator"], 6)
        cov = jia["coverage_ranges"]
        self.assertEqual((cov[RETAINED]["min"], cov[RETAINED]["max"]), (1, 3))
        self.assertEqual((cov[NOT_RETAINED]["min"], cov[NOT_RETAINED]["max"]), (1, 2))
        self.assertEqual((cov[UNPAIRED]["min"], cov[UNPAIRED]["max"]), (1, 4))
        self.assertEqual(cov[NO_USABLE], {"min": 0, "max": 0})
        # 区间端点由真实整批匹配达到，且覆盖数守恒
        for matching in jia["matchings"]:
            total = sum(matching["summary"].values())
            self.assertEqual(total, 6)
        rates = jia["retention_rate"]
        self.assertAlmostEqual(rates["min"], 1 / 6)
        self.assertAlmostEqual(rates["max"], 3 / 6)
        self.assertFalse(jia["line_ever_crossed"])
        self.assertEqual(jia["improvement_line"], IMPROVEMENT_LINE)

    def test_ranges_are_jointly_feasible_not_per_person_extremes(self):
        # 端点必须出现在某个完整匹配的总结里，而非逐人拼凑
        jia = self._cohort("甲")
        retained_values = {m["summary"].get(RETAINED, 0) for m in jia["matchings"]}
        self.assertIn(1, retained_values)
        self.assertIn(3, retained_values)
        self.assertNotIn(0, retained_values)

    def test_independent_flag_and_out_of_window_answers_excluded(self):
        # s4 首轮 token d 在第11日，超出第一轮窗（7-10）：
        # - 第二轮配不上 -> 未配对；配上 c 时首轮无适用作答可对照，
        #   只能就第二轮作答记未保持，绝不把缺失的首轮分填成零
        jia = self._cohort("甲")
        s4 = next(s for s in jia["students"] if s["student"] == "s4")
        self.assertEqual(set(s4["skills"]["解释"]["statuses"]),
                         {NOT_RETAINED, UNPAIRED})
        # 站点南 token f 在窗口外、token e 非无辅助：
        # s5 没有任何适用首轮作答，落在无可用作答
        yi = self._cohort("乙")
        s5 = next(s for s in yi["students"] if s["student"] == "s5")
        self.assertIn(NO_USABLE, s5["skills"]["解释"]["statuses"])

    def test_immature_cohort_has_no_retention_rate(self):
        yi = self._cohort("乙")
        self.assertFalse(yi["mature"])
        self.assertIsNone(yi["retention_rate"]["min"])
        self.assertIsNone(yi["retention_rate"]["max"])

    def test_no_zero_filled_when_data_missing(self):
        # 未配对/无作答均作为覆盖类别保留；s4 不存在“确定为未保持”的结论，
        # 未保持只出现在部分整批匹配中，且其分值均来自真实作答而非填零
        jia = self._cohort("甲")
        s4 = next(s for s in jia["students"] if s["student"] == "s4")
        self.assertFalse(s4["skills"]["解释"]["determined"])
        for matching in jia["matchings"]:
            self.assertEqual(
                sum(matching["summary"].values()), jia["denominator"])

    # ---- 邀请复核与联系方式 -------------------------------------------

    def test_invitation_withdrawal_disposition_by_confirmation(self):
        ledger = self._ledger()
        rows = reconcile_invitations(self.tables, ledger, AS_OF)
        r1 = next(r for r in rows if r["invitation"] == "r1")
        r2 = next(r for r in rows if r["invitation"] == "r2")
        self.assertEqual(r1["disposition"], "manual_review")  # 学员已确认
        self.assertEqual(r2["disposition"], "stands")         # 依据仍确认
        # 签发当时两者都合规
        self.assertTrue(r1["route_active_at_issue"])
        self.assertEqual(r1["state_at_issue"], CONFIRMED)

    def test_route_expiry_is_half_open(self):
        # c001: from 23 until 26，结束日不含
        self.assertTrue(active_routes(self.tables["routes"], 23).get("s3"))
        self.assertTrue(active_routes(self.tables["routes"], 25).get("s3"))
        self.assertIsNone(active_routes(self.tables["routes"], 26).get("s3"))
        self.assertTrue(active_routes(self.tables["routes"], 40).get("s1"))

    def test_pending_never_marked_scheduled_and_no_contact_leak(self):
        snap = snapshot_at(self.tables, AS_OF)
        # 待联系/资料不足记录一律不得携带任何号码（s2 本人虽有 b001 也不外泄）
        for item in snap["actions"]["pending_contact"]:
            self.assertEqual(item["contacts"], [])
        for item in snap["actions"]["insufficient"]:
            self.assertEqual(item["contacts"], [])
        # 可发邀请只携带本人号码
        for item in snap["actions"]["issuable"]:
            self.assertEqual(item["contacts"], ["a001"])
            self.assertEqual(item["student"], "s1")

    # ---- 核实排期 -----------------------------------------------------

    def test_review_plan_prefers_joint_resolution_and_dedups(self):
        ledger = self._ledger()
        analysis, _ = analyze_all(self.tables, AS_OF)
        plan = review_plan(self.tables, ledger, analysis, AS_OF)
        # 只剩第26天窗口（15分钟）：x1（12分钟，消3处歧义）优先
        self.assertEqual([p["package"] for p in plan["plan"]], ["x1"])
        skipped = {s["package"]: s["reason"] for s in plan["skipped"]}
        self.assertEqual(skipped["x3"], "no_open_ambiguity")
        self.assertEqual(skipped["x2"], "no_window_capacity")

    def test_day20_plan_skips_package_covered_by_earlier_one(self):
        analysis, _ = analyze_all(self.tables, 20)
        plan = review_plan(self.tables, LinkLedger(self.tables["links"], 20),
                           analysis, 20)
        names = [p["package"] for p in plan["plan"]]
        self.assertEqual(names, ["x1", "x2"])  # x3 的 l5 已被 x1 覆盖
        skipped = {s["package"]: s["reason"] for s in plan["skipped"]}
        self.assertEqual(skipped["x3"], "covered_by_earlier_package")

    def test_consequential_edges_empty_when_line_never_crossed(self):
        analysis, _ = analyze_all(self.tables, AS_OF)
        self.assertEqual(consequential_edges(analysis), [])

    # ---- 历史重放 -----------------------------------------------------

    def test_lock_snapshots_replay_prior_meetings(self):
        snap20 = snapshot_at(self.tables, 20)
        self.assertEqual(snap20["invitations"], [])  # 邀请尚未签发
        jia20 = next(c for c in snap20["analysis"]["cohorts"]
                     if c["cohort"] == "甲")
        self.assertEqual(jia20["coverage_ranges"][RETAINED],
                         {"min": 0, "max": 3})
        snap24 = snapshot_at(self.tables, 24)
        self.assertEqual({i["invitation"] for i in snap24["invitations"]},
                         {"r1", "r2"})


class SyntheticRulesTest(unittest.TestCase):
    """用内联合成资料覆盖真实数据未出现的规则（不触碰 records/）。"""

    def _base_tables(self):
        return {
            "cohorts": [], "results": [], "links": [], "routes": [],
            "review_packages": [], "review_windows": [],
            "invitations": [], "locks": [],
        }

    def test_two_confirmed_answers_same_skill_keep_dispute(self):
        # 场景：k1 第一轮有两个不同 token，两条确认关联分别落定，
        # 且两个 token 都携带同技能、窗内、无辅助的有效作答。
        # 此时不得用分高者替代，先保留争议。
        tables = self._base_tables()
        tables["cohorts"].append(
            {"student": "k1", "cohort": "丁", "ended": 0,
             "eligible": ["解释"]})
        for token, score in (("a", 2), ("b", 4)):
            tables["results"].append(
                {"site": "东", "wave": 1, "token": token, "skill": "解释",
                 "day": 8, "score": score, "independent": True})
        tables["links"] = [
            {"edge": "d1", "student": "k1", "site": "东", "wave": 1,
             "token": "a", "state": CONFIRMED, "day": 9},
            {"edge": "d2", "student": "k1", "site": "东", "wave": 1,
             "token": "b", "state": CONFIRMED, "day": 9},
        ]
        analysis, _ = analyze_all(tables, 20)
        cohort = analysis["cohorts"][0]
        self.assertEqual(len(cohort["disputes"]), 1)
        self.assertEqual(cohort["disputes"][0]["tokens"],
                         [("东", 1, "a"), ("东", 1, "b")])
        student = cohort["students"][0]
        self.assertEqual(student["skills"]["解释"]["status"], "disputed")
        # 争议不进入保持/未保持计数，也不按高分者静默取用
        self.assertEqual(cohort["coverage_ranges"]["disputed"],
                         {"min": 1, "max": 1})
        self.assertEqual(cohort["coverage_ranges"][RETAINED],
                         {"min": 0, "max": 0})

    def test_consequential_edge_detection_on_synthetic_line_crossing(self):
        from retention_audit.planning import consequential_edges

        tables = self._base_tables()
        tables["cohorts"].append(
            {"student": "k1", "cohort": "丁", "ended": 0,
             "eligible": ["解释"]})
        # 首轮 k1 已确认 2 分；第二轮 token a 为候选，分数 2（保持）
        tables["results"] = [
            {"site": "东", "wave": 1, "token": "x", "skill": "解释",
             "day": 8, "score": 2, "independent": True},
            {"site": "西", "wave": 2, "token": "a", "skill": "解释",
             "day": 16, "score": 2, "independent": True},
        ]
        tables["links"] = [
            {"edge": "d1", "student": "k1", "site": "东", "wave": 1,
             "token": "x", "state": CONFIRMED, "day": 9},
            {"edge": "d2", "student": "k1", "site": "西", "wave": 2,
             "token": "a", "state": POSSIBLE, "day": 17},
        ]
        analysis, _ = analyze_all(tables, 20)
        # 配对则 1/1=100% 跨 70% 线，不配对则 0%，d2 即关键 edge
        self.assertEqual(consequential_edges(analysis), ["d2"])
        cohort = analysis["cohorts"][0]
        self.assertTrue(cohort["line_ever_crossed"])
        self.assertEqual(cohort["retention_rate"], {"min": 0.0, "max": 1.0})

    def test_conflicting_confirmed_links_make_no_feasible_matching(self):
        ledger = LinkLedger([
            {"edge": "c1", "student": "k1", "site": "西", "wave": 2,
             "token": "a", "state": CONFIRMED, "day": 10},
            {"edge": "c2", "student": "k2", "site": "西", "wave": 2,
             "token": "a", "state": CONFIRMED, "day": 10},
        ], 20)
        self.assertEqual(enumerate_matchings(ledger, {"k1", "k2"}), [])


if __name__ == "__main__":
    unittest.main()
