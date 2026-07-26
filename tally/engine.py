"""Orchestrates the full tally: load the three sheets, fuzzy-match companies,
run the grouping engine per company, and produce one result row per
MainSheet transaction with full traceability of how each value was derived.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional

from . import grouping, ltcg, mainsheet, name_match, stcg


@dataclass
class ContributingRow:
    excel_row: int
    date: Optional[str]
    amount: float
    extra: dict = field(default_factory=dict)


@dataclass
class ResultRow:
    excel_row: int
    company_raw: str
    matched_company: Optional[str]
    match_score: float

    mainsheet_sale_amount: float
    broker_sale_amount: float
    amount_match: bool
    amount_delta: float

    mainsheet_units: Optional[float]
    broker_units: Optional[float]
    units_match: Optional[bool]
    units_delta: Optional[float]

    mainsheet_purchase_date: Optional[str]
    resolved_purchase_date: Optional[str]
    all_dates: List[str]

    mainsheet_purchase_cost: Optional[float]
    resolved_purchase_cost: Optional[float]

    group_status: str  # single | exact | approx | empty | no_company_match
    group_size: int
    contributing_rows: List[ContributingRow]


def _match_all(main_rows, candidates: dict):
    """Fuzzy-match each distinct MainSheet company name once, cached by raw string."""
    cache = {}
    for r in main_rows:
        if r.company_raw not in cache:
            cache[r.company_raw] = name_match.best_match(r.company_raw, candidates)
    return cache


def process_ltcg(main_rows: List[mainsheet.MainRow], ltcg_rows: List[ltcg.LtcgRow]) -> List[ResultRow]:
    targets_main = [r for r in main_rows if mainsheet.is_long_term(r.term)]
    candidates = ltcg.company_candidates(ltcg_rows)
    match_cache = _match_all(targets_main, candidates)

    pool_by_key = defaultdict(list)
    for r in ltcg_rows:
        pool_by_key[r.company_key].append(r)

    groups_by_key = defaultdict(list)
    unmatched = []
    for idx, r in enumerate(targets_main):
        m = match_cache[r.company_raw]
        if m.matched_key is None:
            unmatched.append((idx, r, m))
        else:
            groups_by_key[m.matched_key].append((idx, r, m))

    results: List[Optional[ResultRow]] = [None] * len(targets_main)

    for key, items in groups_by_key.items():
        pool_rows = pool_by_key[key]
        targets = [grouping.Target(id=idx, primary=r.sale_amount, secondary=r.units) for idx, r, m in items]
        pool = [
            grouping.PoolItem(id=i, primary=pr.sale_amount, secondary=pr.qty, date=pr.purchase_date)
            for i, pr in enumerate(pool_rows)
        ]
        group_results = {gr.target_id: gr for gr in grouping.match_groups(targets, pool, use_secondary=True)}

        for idx, r, m in items:
            gr = group_results[idx]
            contributing = [
                ContributingRow(
                    excel_row=pool_rows[i].excel_row,
                    date=pool_rows[i].purchase_date,
                    amount=pool_rows[i].purchase_amount,
                    extra={"qty": pool_rows[i].qty, "sale_amount": pool_rows[i].sale_amount},
                )
                for i in gr.pool_ids
            ]
            purchase_cost_sum = sum(pool_rows[i].purchase_amount for i in gr.pool_ids)
            results[idx] = ResultRow(
                excel_row=r.excel_row,
                company_raw=r.company_raw,
                matched_company=m.raw_matched_name,
                match_score=m.score,
                mainsheet_sale_amount=r.sale_amount,
                broker_sale_amount=gr.primary_sum,
                amount_match=abs(r.sale_amount - gr.primary_sum) < 1e-9,
                amount_delta=r.sale_amount - gr.primary_sum,
                mainsheet_units=r.units,
                broker_units=gr.secondary_sum,
                units_match=abs(r.units - gr.secondary_sum) < 1e-9,
                units_delta=r.units - gr.secondary_sum,
                mainsheet_purchase_date=r.purchase_date,
                resolved_purchase_date=gr.resolved_date,
                all_dates=gr.all_dates,
                mainsheet_purchase_cost=r.purchase_cost,
                resolved_purchase_cost=purchase_cost_sum,
                group_status=gr.status,
                group_size=len(gr.pool_ids),
                contributing_rows=contributing,
            )

    for idx, r, m in unmatched:
        results[idx] = ResultRow(
            excel_row=r.excel_row,
            company_raw=r.company_raw,
            matched_company=None,
            match_score=0.0,
            mainsheet_sale_amount=r.sale_amount,
            broker_sale_amount=0.0,
            amount_match=False,
            amount_delta=r.sale_amount,
            mainsheet_units=r.units,
            broker_units=0.0,
            units_match=False,
            units_delta=r.units,
            mainsheet_purchase_date=r.purchase_date,
            resolved_purchase_date=None,
            all_dates=[],
            mainsheet_purchase_cost=r.purchase_cost,
            resolved_purchase_cost=None,
            group_status="no_company_match",
            group_size=0,
            contributing_rows=[],
        )

    return results


def process_stcg(main_rows: List[mainsheet.MainRow], stcg_rows: List[stcg.StcgRow]) -> List[ResultRow]:
    targets_main = [r for r in main_rows if mainsheet.is_short_term(r.term)]
    candidates = stcg.company_candidates(stcg_rows)
    match_cache = _match_all(targets_main, candidates)

    pool_by_key = defaultdict(list)
    for r in stcg_rows:
        pool_by_key[r.company_key].append(r)

    groups_by_key = defaultdict(list)
    unmatched = []
    for idx, r in enumerate(targets_main):
        m = match_cache[r.company_raw]
        if m.matched_key is None:
            unmatched.append((idx, r, m))
        else:
            groups_by_key[m.matched_key].append((idx, r, m))

    results: List[Optional[ResultRow]] = [None] * len(targets_main)

    for key, items in groups_by_key.items():
        pool_rows = pool_by_key[key]
        targets = [grouping.Target(id=idx, primary=r.sale_amount) for idx, r, m in items]
        pool = [
            grouping.PoolItem(id=i, primary=pr.sell_amount, date=pr.buy_date)
            for i, pr in enumerate(pool_rows)
        ]
        group_results = {gr.target_id: gr for gr in grouping.match_groups(targets, pool, use_secondary=False)}

        for idx, r, m in items:
            gr = group_results[idx]
            contributing = [
                ContributingRow(
                    excel_row=pool_rows[i].excel_row,
                    date=pool_rows[i].buy_date,
                    amount=pool_rows[i].sell_amount,
                    extra={"buy_qty": pool_rows[i].buy_qty, "buy_amount": pool_rows[i].buy_amount},
                )
                for i in gr.pool_ids
            ]
            results[idx] = ResultRow(
                excel_row=r.excel_row,
                company_raw=r.company_raw,
                matched_company=m.raw_matched_name,
                match_score=m.score,
                mainsheet_sale_amount=r.sale_amount,
                broker_sale_amount=gr.primary_sum,
                amount_match=abs(r.sale_amount - gr.primary_sum) < 1e-9,
                amount_delta=r.sale_amount - gr.primary_sum,
                mainsheet_units=None,
                broker_units=None,
                units_match=None,
                units_delta=None,
                mainsheet_purchase_date=r.purchase_date,
                resolved_purchase_date=gr.resolved_date,
                all_dates=gr.all_dates,
                mainsheet_purchase_cost=None,
                resolved_purchase_cost=None,
                group_status=gr.status,
                group_size=len(gr.pool_ids),
                contributing_rows=contributing,
            )

    for idx, r, m in unmatched:
        results[idx] = ResultRow(
            excel_row=r.excel_row,
            company_raw=r.company_raw,
            matched_company=None,
            match_score=0.0,
            mainsheet_sale_amount=r.sale_amount,
            broker_sale_amount=0.0,
            amount_match=False,
            amount_delta=r.sale_amount,
            mainsheet_units=None,
            broker_units=None,
            units_match=None,
            units_delta=None,
            mainsheet_purchase_date=r.purchase_date,
            resolved_purchase_date=None,
            all_dates=[],
            mainsheet_purchase_cost=None,
            resolved_purchase_cost=None,
            group_status="no_company_match",
            group_size=0,
            contributing_rows=[],
        )

    return results


def run(mainsheet_path: str, ltcg_path: str, stcg_path: str):
    main_rows = mainsheet.load_mainsheet(mainsheet_path)
    ltcg_rows = ltcg.load_ltcg(ltcg_path)
    stcg_rows = stcg.load_stcg(stcg_path)

    ltcg_results = process_ltcg(main_rows, ltcg_rows)
    stcg_results = process_stcg(main_rows, stcg_rows)

    return {
        "ltcg": ltcg_results,
        "stcg": stcg_results,
    }
