"""Fuzzy matching of company names across MainSheet, LTCG and STCG sheets.

The three sources spell company names differently, e.g.:
  MainSheet: "IPCA LABORATORIES LIMITED#NEW EQUITY SHARES WITH FACE VALUE RE.1/- AFTER SUB-DIVISON"
  LTCG:      "IPCA LABORATORIES LTD."
  STCG:      "CMS INFO SYSTEMS LTD"  (MainSheet: "CMS INFO SYSTEMS LIMITED # EQUITY SHARES")

normalize() strips the share-class boilerplate and common suffix variants so the
remaining core name can be fuzzy-matched with rapidfuzz.
"""
import re
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz, process

_ISIN_SUFFIX_RE = re.compile(r"~[A-Z0-9]+$")
_SHARE_BOILERPLATE_RE = re.compile(r"\bEQUITY SHARES\b.*$", re.IGNORECASE)
_TRAILING_MARKER_RE = re.compile(r"-\$$")
_PUNCT_RE = re.compile(r"[^A-Z0-9 ]+")
_WS_RE = re.compile(r"\s+")

_SUFFIX_MAP = [
    (re.compile(r"\bLIMITED\b"), "LTD"),
    (re.compile(r"\bLTD\.\b"), "LTD"),
    (re.compile(r"\bPRIVATE\b"), "PVT"),
    (re.compile(r"\bCOMPANY\b"), "CO"),
    (re.compile(r"\bCORPORATION\b"), "CORP"),
]

# Default acceptance threshold for rapidfuzz token_sort_ratio (0-100).
MATCH_THRESHOLD = 60


def normalize(raw_name: str) -> str:
    """Collapse a raw company name string down to a comparable core name."""
    if raw_name is None:
        return ""
    name = str(raw_name).upper()
    name = _ISIN_SUFFIX_RE.sub("", name)
    name = _SHARE_BOILERPLATE_RE.sub("", name)
    # MainSheet also uses '#' or ' - ' as a separator before share-class text
    # even when it doesn't literally say "EQUITY SHARES" up front.
    name = re.split(r"#", name, maxsplit=1)[0]
    name = _TRAILING_MARKER_RE.sub("", name)
    for pattern, repl in _SUFFIX_MAP:
        name = pattern.sub(repl, name)
    name = _PUNCT_RE.sub(" ", name)
    name = _WS_RE.sub(" ", name).strip()
    return name


@dataclass
class MatchResult:
    matched_key: Optional[str]
    raw_matched_name: Optional[str]
    score: float


def best_match(main_company_raw: str, candidates: dict) -> MatchResult:
    """Find the best-matching broker company for a MainSheet company name.

    candidates: dict of {normalized_name: raw_display_name} gathered from the
    broker sheet (LTCG header rows or STCG company column).
    """
    normalized_target = normalize(main_company_raw)
    if not normalized_target or not candidates:
        return MatchResult(None, None, 0.0)

    result = process.extractOne(
        normalized_target,
        list(candidates.keys()),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=MATCH_THRESHOLD,
    )
    if result is None:
        return MatchResult(None, None, 0.0)

    matched_key, score, _ = result
    return MatchResult(matched_key, candidates[matched_key], score)
