"""候选关联台账：按获知日重放每条 edge 的状态。

状态语义（README 约定）：
- ``possible`` 候选，仅表示可能；
- ``excluded`` 排除；
- ``confirmed`` 考务确认；
- ``withdrawn`` 撤回上一次确认，恢复为候选。

每一行更新其 edge 在当时的状态；同一 edge 以最后一条不晚于 as_of 的登记为准。
"""

from collections import defaultdict

POSSIBLE = "possible"
CONFIRMED = "confirmed"
EXCLUDED = "excluded"
WITHDRAWN = "withdrawn"

# 撤回确认后恢复成的状态
_AFTER_WITHDRAWAL = POSSIBLE


class LinkLedger:
    def __init__(self, link_rows, as_of):
        # edge -> 按日排列的登记序列
        self._history = defaultdict(list)
        for row in sorted(link_rows, key=lambda r: (r["day"], r["edge"])):
            if row["day"] <= as_of:
                self._history[row["edge"]].append(row)
        # 静态身份信息（同一 edge 的身份字段应一致）
        self._identity = {}
        for edge, rows in self._history.items():
            latest = rows[-1]
            self._identity[edge] = (
                latest["student"],
                latest["site"],
                latest["wave"],
                latest["token"],
            )

    @property
    def edges(self):
        return set(self._history)

    def identity(self, edge):
        """返回 (student, site, wave, token)。"""
        return self._identity[edge]

    def state(self, edge):
        """edge 在 as_of 时的有效状态；无登记返回 None。"""
        rows = self._history.get(edge)
        if not rows:
            return None
        latest_state = rows[-1]["state"]
        if latest_state == WITHDRAWN:
            return _AFTER_WITHDRAWAL
        return latest_state

    def state_at_issuance(self, edge, day):
        """edge 在某一签发日当天的状态（用于复核历史邀请是否合规）。"""
        rows = [r for r in self._history.get(edge, ()) if r["day"] <= day]
        if not rows:
            return None
        latest_state = rows[-1]["state"]
        if latest_state == WITHDRAWN:
            return _AFTER_WITHDRAWAL
        return latest_state

    def history(self, edge):
        """返回该 edge 的全部登记（按日），供审计追溯。"""
        return list(self._history.get(edge, ()))

    def grouped(self):
        """按有效状态分组，返回 edge 集合字典。"""
        groups = defaultdict(set)
        for edge in self._history:
            groups[self.state(edge)].add(edge)
        return dict(groups)
