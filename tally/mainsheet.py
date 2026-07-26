"""Parser for the MainSheet (tax portal capital gains export).

Row 0 is the header; every row after that is one equity transaction.
Columns are addressed by their Excel letter per the confirmed layout:
  D=Company, E=Sale Amount, H=Sale Date, I=Purchase Cost, K=Purchase Date,
  Q=No. of Shares/Units, C=Long-Term/Short-Term.
"""
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

COL = {
    "term": 2,           # C: Long-Term/ Short-Term
    "company": 3,        # D
    "sale_amount": 4,    # E
    "sale_date": 7,      # H
    "purchase_cost": 8,  # I
    "purchase_date": 10, # K
    "units": 16,         # Q
}


@dataclass
class MainRow:
    excel_row: int  # 1-based row number as it appears in Excel (header = row 1)
    term: str
    company_raw: str
    sale_amount: float
    sale_date: Optional[str]
    purchase_cost: float
    purchase_date: Optional[str]
    units: float


def _num(val) -> float:
    try:
        if pd.isna(val):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _text(val) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val).strip()


def load_mainsheet(path: str) -> List[MainRow]:
    df = pd.read_excel(path, sheet_name=0, header=None)
    rows: List[MainRow] = []
    for i in range(1, len(df)):  # skip header row 0
        r = df.iloc[i]
        company = _text(r[COL["company"]])
        if not company:
            continue
        term = (_text(r[COL["term"]]) or "").strip()
        rows.append(
            MainRow(
                excel_row=i + 1,
                term=term,
                company_raw=company,
                sale_amount=_num(r[COL["sale_amount"]]),
                sale_date=_text(r[COL["sale_date"]]),
                purchase_cost=_num(r[COL["purchase_cost"]]),
                purchase_date=_text(r[COL["purchase_date"]]),
                units=_num(r[COL["units"]]),
            )
        )
    return rows


def is_long_term(term: str) -> bool:
    return term.strip().lower().startswith("long-term")


def is_short_term(term: str) -> bool:
    return term.strip().lower().startswith("short-term")
