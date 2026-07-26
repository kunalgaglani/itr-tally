"""Parser for the broker STCG (short-term capital gains) report.

Unlike LTCG this sheet has no header/total block structure worth tracking:
every real transaction row has the company name directly in column B, while
"Total-<company>" subtotal rows and the trailing summary section only ever
populate column A. Filtering on "column B is a company name" therefore
naturally skips all of the non-data rows.

Columns: A=scrip code, B=company name, D=buy date, J=sell amount.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

COL = {
    "scrip_code": 0,   # A
    "company": 1,      # B
    "buy_date": 3,     # D
    "buy_qty": 4,      # E
    "buy_amount": 5,   # F
    "sell_date": 6,    # G
    "sell_qty": 8,     # I
    "sell_amount": 9,  # J
}

@dataclass
class StcgRow:
    excel_row: int
    company_key: str
    company_raw: str
    buy_date: Optional[str]
    buy_qty: float
    buy_amount: float
    sell_date: Optional[str]
    sell_amount: float


def _num(val) -> float:
    try:
        if pd.isna(val):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _fmt_date(val) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)


def load_stcg(path: str) -> List[StcgRow]:
    from . import name_match

    df = pd.read_excel(path, sheet_name=0, header=None)
    rows: List[StcgRow] = []

    for i in range(len(df)):
        r = df.iloc[i]
        company_val = r[COL["company"]]
        if company_val is None or (isinstance(company_val, float) and pd.isna(company_val)):
            continue
        company_raw = str(company_val).strip()
        if not company_raw:
            continue

        buy_date_raw = r[COL["buy_date"]]
        if buy_date_raw is None or (isinstance(buy_date_raw, float) and pd.isna(buy_date_raw)):
            continue  # a company-name cell without a buy date isn't a data row

        rows.append(
            StcgRow(
                excel_row=i + 1,
                company_key=name_match.normalize(company_raw),
                company_raw=company_raw,
                buy_date=_fmt_date(buy_date_raw),
                buy_qty=_num(r[COL["buy_qty"]]),
                buy_amount=_num(r[COL["buy_amount"]]),
                sell_date=_fmt_date(r[COL["sell_date"]]),
                sell_amount=_num(r[COL["sell_amount"]]),
            )
        )

    return rows


def company_candidates(rows: List[StcgRow]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in rows:
        out.setdefault(row.company_key, row.company_raw)
    return out
