"""跨考点复测配对保持率审计。

所有分析均以“资料获知日 as_of”为截止点，可对 locks 中的历史时点重放；
匹配区间只由互不矛盾的整批关联（可行匹配）取界，不逐人独立挑极端。
"""

from .windows import WAVES, wave_window, in_wave, cohort_mature, window_status
from .links import LinkLedger, POSSIBLE, CONFIRMED, EXCLUDED, WITHDRAWN
from .matching import build_tokens, enumerate_matchings, find_disputes
from .cohort_analysis import analyze_cohort, analyze_all
from .outreach import reconcile_invitations, retest_actions
from .planning import review_plan, consequential_edges
from .snapshots import snapshot_at, lock_snapshots

__all__ = [
    "WAVES",
    "wave_window",
    "in_wave",
    "cohort_mature",
    "window_status",
    "LinkLedger",
    "POSSIBLE",
    "CONFIRMED",
    "EXCLUDED",
    "WITHDRAWN",
    "build_tokens",
    "enumerate_matchings",
    "find_disputes",
    "analyze_cohort",
    "analyze_all",
    "reconcile_invitations",
    "retest_actions",
    "review_plan",
    "consequential_edges",
    "snapshot_at",
    "lock_snapshots",
]
