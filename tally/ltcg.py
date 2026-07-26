"""Parser for the broker LTCG (long-term capital gains) report.

The sheet is a free-form report, not a clean table:
  - company header rows look like "543458 - AWL AGRI BUSINESS LTD~INF209K01165"
    (scrip code - company name ~ ISIN), with data in column A only.
  - one or more data rows follow, keyed by scrip code in column A, with a
    purchase date in column B, quantity in column C, purchase amount in
    column E, sale date in column K and sale amount in column N.
  - a "TOTAL<code> - <name>~<isin>" subtotal row closes each block.
  - the file also has title/summary/account-header rows scattered through it.

Rather than trying to detect block boundaries, we scan top-to-bottom and
forward-fill "current company" from the last header row seen. Real data rows
are identified structurally (numeric scrip code in col A + a date in col B),
which safely skips every title/total/summary row regardless of file layout
quirks.
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

COL = {
    "code_or_header": 0,   # A
    "purchase_date": 1,    # B
    "qty": 2,              # C
    "purchase_amount": 4,  # E
    "sale_date": 10,       # K
    "sale_amount": 13,     # N
}

_HEADER_RE = re.compile(r"^\s*\d+\s*-\s*(.+?)~([A-Za-z0-9]+)\s*$")
_NUMERIC_RE = re.compile(r"^\s*\d+\s*$")


@dataclass
class LtcgRow:
    excel_row: int
    company_key: str        # normalized company name (see name_match.normalize)
    company_raw: str        # raw company name as it appears in the header row
    isin: str
    purchase_date: Optional[str]
    qty: float
    purchase_amount: float
    sale_date: Optional[str]
    sale_amount: float


def _num(val) -> float:
    try:
        if pd.isna(val):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _looks_like_date(val) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return True


def _fmt_date(val) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)


def load_ltcg(path: str) -> List[LtcgRow]:
    from . import name_match

    df = pd.read_excel(path, sheet_name=0, header=None)
    rows: List[LtcgRow] = []

    current_name: Optional[str] = None
    current_isin: str = ""

    for i in range(len(df)):
        r = df.iloc[i]
        col_a = r[COL["code_or_header"]]
        col_a_str = str(col_a) if col_a is not None and not pd.isna(col_a) else ""

        header_match = _HEADER_RE.match(col_a_str)
        if header_match:
            current_name = header_match.group(1).strip()
            current_isin = header_match.group(2).strip()
            continue

        if col_a_str.strip().upper().startswith("TOTAL"):
            continue

        if not _NUMERIC_RE.match(col_a_str):
            continue  # title / summary / account-header / blank row

        purchase_date_raw = r[COL["purchase_date"]]
        if not _looks_like_date(purchase_date_raw):
            continue  # numeric col A but no date in col B -> not a data row

        if current_name is None:
            continue  # data row appeared before any header we recognise

        rows.append(
            LtcgRow(
                excel_row=i + 1,
                company_key=name_match.normalize(current_name),
                company_raw=current_name,
                isin=current_isin,
                purchase_date=_fmt_date(purchase_date_raw),
                qty=_num(r[COL["qty"]]),
                purchase_amount=_num(r[COL["purchase_amount"]]),
                sale_date=_fmt_date(r[COL["sale_date"]]),
                sale_amount=_num(r[COL["sale_amount"]]),
            )
        )

    return rows


def company_candidates(rows: List[LtcgRow]) -> Dict[str, str]:
    """normalized name -> raw display name, for fuzzy matching."""
    out: Dict[str, str] = {}
    for row in rows:
        out.setdefault(row.company_key, row.company_raw)
    return out
