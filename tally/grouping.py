"""Match N MainSheet target rows for a company against M broker pool rows.

This is the "CMS problem" from the spec: a company can have several MainSheet
rows (each one sale) that all map to the same broker company, whose rows must
be split into groups - one per MainSheet row - so that each group's amount
(and, for LTCG, unit count) sums to that MainSheet row's value.

Strategy:
  1. Single target (N == 1): the whole pool belongs to it. No partitioning
     needed - just report the sums and let the caller compare/delta them.
  2. Multiple targets: try to find an EXACT partition (every pool row used in
     exactly one group, each group summing exactly - to the paisa - to its
     target) via bounded backtracking. Real broker-vs-tax-portal data is
     frequently off by small rounding differences, so exact search often
     cannot succeed; when it fails (or blows past its search budget) we fall
     back to a deterministic greedy "best effort" partition and flag the
     result as approximate so the user can review it manually.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Sequence


@dataclass
class PoolItem:
    id: int
    primary: float          # sale amount
    secondary: float = 0.0  # units (only used for LTCG); 0 when unused
    date: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class Target:
    id: int
    primary: float
    secondary: float = 0.0


@dataclass
class GroupResult:
    target_id: int
    pool_ids: List[int]
    primary_sum: float
    secondary_sum: float
    status: str  # "single" | "exact" | "approx" | "empty"
    resolved_date: Optional[str]
    all_dates: List[str]


class _BudgetExceeded(Exception):
    pass


PAISE = 100  # scale factor to convert rupee amounts to integer paise
SEARCH_BUDGET = 200_000


def _to_int(amount: float) -> int:
    return round(amount * PAISE)


def _dates_for(pool_items: Sequence[PoolItem], ids: Sequence[int]) -> List[str]:
    id_set = set(ids)
    dates = [p.date for p in pool_items if p.id in id_set and p.date]
    # de-dupe while preserving order
    seen = []
    for d in dates:
        if d not in seen:
            seen.append(d)
    return seen


def _resolved_date(all_dates: List[str]) -> Optional[str]:
    if len(all_dates) == 1:
        return all_dates[0]
    if len(all_dates) == 0:
        return None
    return None  # ambiguous - caller shows all_dates instead


def _exact_partition(targets: List[Target], pool: List[PoolItem], use_secondary: bool):
    """Returns {target_id: [pool_id, ...]} for an exact partition, or None."""
    order = sorted(range(len(targets)), key=lambda i: -targets[i].primary)
    ordered_targets = [targets[i] for i in order]

    budget = [SEARCH_BUDGET]
    assignment: List[Optional[List[int]]] = [None] * len(ordered_targets)

    def rec(t_i: int, remaining: List[PoolItem]) -> bool:
        if t_i == len(ordered_targets):
            return len(remaining) == 0

        target_p = _to_int(ordered_targets[t_i].primary)
        target_s = _to_int(ordered_targets[t_i].secondary) if use_secondary else 0

        items = sorted(remaining, key=lambda p: -p.primary)
        n = len(items)
        suffix_p = [0] * (n + 1)
        suffix_s = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix_p[i] = suffix_p[i + 1] + _to_int(items[i].primary)
            suffix_s[i] = suffix_s[i + 1] + (_to_int(items[i].secondary) if use_secondary else 0)

        chosen: List[int] = []

        def dfs(pos: int, rem_p: int, rem_s: int) -> bool:
            budget[0] -= 1
            if budget[0] <= 0:
                raise _BudgetExceeded()
            if rem_p == 0 and rem_s == 0:
                chosen_set = set(chosen)
                rest = [it for it in items if it.id not in chosen_set]
                assignment[t_i] = list(chosen)
                if rec(t_i + 1, rest):
                    return True
                assignment[t_i] = None
                # keep searching for a different subset below (fallthrough)
            if pos >= n:
                return False
            if rem_p < 0 or rem_s < 0:
                return False
            if suffix_p[pos] < rem_p or suffix_s[pos] < rem_s:
                return False
            item = items[pos]
            chosen.append(item.id)
            if dfs(pos + 1, rem_p - _to_int(item.primary), rem_s - (_to_int(item.secondary) if use_secondary else 0)):
                return True
            chosen.pop()
            return dfs(pos + 1, rem_p, rem_s)

        return dfs(0, target_p, target_s)

    try:
        ok = rec(0, list(pool))
    except _BudgetExceeded:
        return None

    if not ok:
        return None

    result = {}
    for t, ids in zip(ordered_targets, assignment):
        result[t.id] = ids or []
    return result


def _greedy_partition(targets: List[Target], pool: List[PoolItem]):
    """Deterministic best-effort fallback: assign each item (largest first) to
    whichever bucket currently has the most remaining headroom against its
    target. Not guaranteed optimal, but stable and easy to reason about."""
    buckets = {t.id: {"target": t.primary, "sum": 0.0, "ids": []} for t in targets}
    for item in sorted(pool, key=lambda p: -p.primary):
        best_id = max(buckets, key=lambda k: buckets[k]["target"] - buckets[k]["sum"])
        buckets[best_id]["sum"] += item.primary
        buckets[best_id]["ids"].append(item.id)
    return {k: v["ids"] for k, v in buckets.items()}


def match_groups(
    targets: List[Target],
    pool: List[PoolItem],
    use_secondary: bool = False,
) -> List[GroupResult]:
    if not targets:
        return []

    if not pool:
        return [
            GroupResult(t.id, [], 0.0, 0.0, "empty", None, [])
            for t in targets
        ]

    if len(targets) == 1:
        t = targets[0]
        ids = [p.id for p in pool]
        primary_sum = sum(p.primary for p in pool)
        secondary_sum = sum(p.secondary for p in pool)
        dates = _dates_for(pool, ids)
        return [
            GroupResult(t.id, ids, primary_sum, secondary_sum, "single", _resolved_date(dates), dates)
        ]

    assignment = _exact_partition(targets, pool, use_secondary)
    status = "exact"
    if assignment is None:
        assignment = _greedy_partition(targets, pool)
        status = "approx"

    by_id = {p.id: p for p in pool}
    results = []
    for t in targets:
        ids = assignment.get(t.id, [])
        primary_sum = sum(by_id[i].primary for i in ids)
        secondary_sum = sum(by_id[i].secondary for i in ids)
        dates = _dates_for(pool, ids)
        results.append(
            GroupResult(
                t.id, ids, primary_sum, secondary_sum,
                status if ids else "empty",
                _resolved_date(dates), dates,
            )
        )
    return results
