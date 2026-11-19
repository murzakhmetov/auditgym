"""Helpers shared by scripted policies: table paging through list_records."""

from __future__ import annotations

ORDER = ("invoices", "payments", "fx", "ledger")


class Pager:
    """Reads every page of every table, in a fixed order, through the tool interface."""

    def __init__(self, order=ORDER):
        self.order = tuple(order)
        self.data = {t: [] for t in self.order}
        self.idx = 0
        self.cursor = None
        self.pending = None

    @property
    def finished(self) -> bool:
        return self.idx >= len(self.order)

    def feed(self, obs: dict) -> None:
        if self.pending is None:
            return
        table, self.pending = self.pending, None
        result = obs.get("result")
        if obs.get("error") or not result:
            self.idx += 1
            self.cursor = None
            return
        self.data[table].extend(result.get("rows") or [])
        if result.get("next_cursor") is None:
            self.idx += 1
            self.cursor = None
        else:
            self.cursor = result["next_cursor"]

    def next_action(self) -> dict | None:
        if self.finished:
            return None
        table = self.order[self.idx]
        self.pending = table
        return {"action": "list_records", "table": table, "cursor": self.cursor, "limit": 50}

    def pages_left(self, totals: dict) -> int:
        left = 0
        for i, t in enumerate(self.order):
            if i < self.idx:
                continue
            have = len(self.data[t])
            total = totals.get(t, 0)
            left += max(0, -(-(total - have) // 50))
        return left


def submission(episode_id: str, findings: list) -> dict:
    return {"action": "submit", "findings": {"episode_id": episode_id, "findings": findings[:30]}}
