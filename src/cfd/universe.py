"""Rules-based candidate construction and reproducible stratified selection."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cfd.config import read_yaml

PRIMARY_SUBMISSION_PATTERN = re.compile(r"^CIK\d{10}\.json$")
ELIGIBLE_EXCHANGES = {"NYSE", "NASDAQ", "NYSE American"}
ELIGIBLE_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def load_sic_rules(path: Path) -> dict[str, Any]:
    return read_yaml(path)


def map_sic(sic: int, rules: dict[str, Any]) -> tuple[str, str] | None:
    """Map an SEC SIC code into the project's controlled sector/industry taxonomy."""

    for mapping in rules["mappings"]:
        if sic in mapping.get("sic_codes", []):
            return str(mapping["sector"]), str(mapping["industry"])
        for lower, upper in mapping.get("sic_ranges", []):
            if int(lower) <= sic <= int(upper):
                return str(mapping["sector"]), str(mapping["industry"])
    return None


def _current_listing(payload: dict[str, Any]) -> tuple[str, str] | None:
    for ticker, exchange in zip(
        payload.get("tickers", []), payload.get("exchanges", []), strict=True
    ):
        if exchange in ELIGIBLE_EXCHANGES:
            return str(ticker), str(exchange)
    return None


def _has_domestic_periodic_filings(payload: dict[str, Any]) -> bool:
    recent = payload.get("filings", {}).get("recent", {})
    forms = set(recent.get("form", []))
    return "10-K" in forms and "10-Q" in forms and "20-F" not in forms and "40-F" not in forms


def _periodic_history_counts(
    payload: dict[str, Any], *, cutoff: str = "2025-12-31"
) -> tuple[int, int, str | None]:
    recent = payload.get("filings", {}).get("recent", {})
    quarterly_periods: set[str] = set()
    annual_periods: set[str] = set()
    filing_dates: list[str] = []
    for form, report_date, filing_date in zip(
        recent.get("form", []),
        recent.get("reportDate", []),
        recent.get("filingDate", []),
        strict=True,
    ):
        if not filing_date or filing_date > cutoff:
            continue
        if form in {"10-Q", "10-Q/A"} and report_date:
            quarterly_periods.add(str(report_date))
            filing_dates.append(str(filing_date))
        elif form in {"10-K", "10-K/A"} and report_date:
            annual_periods.add(str(report_date))
            filing_dates.append(str(filing_date))
    return len(quarterly_periods), len(annual_periods), min(filing_dates, default=None)


def _excluded_name(name: str, patterns: list[str]) -> bool:
    normalized = f" {name.upper()} "
    return any(pattern.upper() in normalized for pattern in patterns)


def issuer_rows_from_submissions_zip(
    archive: Path,
    sic_rules: dict[str, Any],
    *,
    filing_history_cutoff: str = "2025-12-31",
) -> pd.DataFrame:
    """Read only primary current-filer JSON members from the SEC bulk archive."""

    rows: list[dict[str, Any]] = []
    override_exclusions = {
        str(item["cik"]).zfill(10): str(item["reason"])
        for item in sic_rules.get("entity_overrides", {}).get("exclude", [])
    }
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            if not PRIMARY_SUBMISSION_PATTERN.fullmatch(member):
                continue
            payload = json.loads(source.read(member))
            try:
                sic = int(payload.get("sic") or 0)
            except (TypeError, ValueError):
                continue
            mapped = map_sic(sic, sic_rules)
            listing = _current_listing(payload)
            if mapped is None or listing is None:
                continue
            sector, industry = mapped
            ticker, exchange = listing
            name = str(payload.get("name", "")).strip()
            cik = str(payload["cik"]).zfill(10)
            quarterly_filings, annual_filings, earliest_periodic_filing = _periodic_history_counts(
                payload, cutoff=filing_history_cutoff
            )
            entity_excluded = (
                payload.get("entityType") != "operating"
                or not _has_domestic_periodic_filings(payload)
                or _excluded_name(name, sic_rules.get("exclusion_name_patterns", []))
            )
            insufficient_history = quarterly_filings < 16 or annual_filings < 6
            excluded_by_override = cik in override_exclusions
            excluded = entity_excluded or insufficient_history or excluded_by_override
            if excluded_by_override:
                override_reason = override_exclusions[cik]
                if "common equity" in override_reason:
                    reason = "NOT_PUBLIC_COMMON_EQUITY"
                elif "Staples" in override_reason or "staples" in override_reason:
                    reason = "NON_DISCRETIONARY_RETAIL"
                else:
                    reason = "NON_REGULATED_ENERGY_INFRASTRUCTURE"
            elif entity_excluded:
                reason = "EXCLUDED_ENTITY_TYPE"
            elif insufficient_history:
                reason = "INSUFFICIENT_PRELIMINARY_FILING_HISTORY"
            else:
                reason = "CANDIDATE"
            rows.append(
                {
                    "cik": cik,
                    "company_name": name,
                    "ticker": ticker,
                    "exchange": exchange,
                    "sic": sic,
                    "sic_description": payload.get("sicDescription"),
                    "sector": sector,
                    "industry": industry,
                    "fiscal_year_end": payload.get("fiscalYearEnd"),
                    "state_of_incorporation": payload.get("stateOfIncorporation"),
                    "distinct_10q_periods": quarterly_filings,
                    "distinct_10k_periods": annual_filings,
                    "earliest_periodic_filing": earliest_periodic_filing,
                    "candidate_eligible": not excluded,
                    "reason_code": reason,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("SEC submissions archive produced no mapped candidate issuers")
    return frame.sort_values(["sector", "industry", "cik"]).drop_duplicates("cik")


def deterministic_score(cik: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{cik}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / (2**64 - 1)


def balanced_sample(
    frame: pd.DataFrame,
    *,
    target: int,
    strata: Iterable[str],
    seed: int,
) -> pd.DataFrame:
    """Round-robin random selection across strata, reproducible from entity IDs and a seed."""

    if target > len(frame):
        raise ValueError(f"Cannot select {target} rows from {len(frame)}")
    working = frame.copy()
    working["random_score"] = working["cik"].map(lambda cik: deterministic_score(str(cik), seed))
    stratum_columns = list(strata)
    groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for key, group in working.groupby(stratum_columns, sort=True, dropna=False):
        normalized_key = key if isinstance(key, tuple) else (key,)
        groups[normalized_key] = group.sort_values(["random_score", "cik"]).index.tolist()
    selected: list[int] = []
    while len(selected) < target and groups:
        for key in sorted(list(groups)):
            if groups[key]:
                selected.append(groups[key].pop(0))
                if len(selected) == target:
                    break
            if not groups[key]:
                del groups[key]
    result = working.loc[selected].copy()
    result["random_rank"] = np.arange(1, len(result) + 1)
    return result


def build_candidate_pool(
    mapped_issuers: pd.DataFrame,
    *,
    per_sector: int,
    seed: int,
) -> pd.DataFrame:
    eligible = mapped_issuers.loc[mapped_issuers["candidate_eligible"]].copy()
    selections = []
    for _sector, sector_frame in eligible.groupby("sector", sort=True):
        count = min(per_sector, len(sector_frame))
        chosen = balanced_sample(
            sector_frame,
            target=count,
            strata=["industry"],
            seed=seed,
        )
        chosen["candidate_pool_status"] = "INCLUDED"
        selections.append(chosen)
    result = pd.concat(selections, ignore_index=True)
    return result.sort_values(["sector", "random_rank", "cik"]).reset_index(drop=True)


def assign_size_tiers(eligible: pd.DataFrame) -> pd.DataFrame:
    result = eligible.copy()
    result["size_tier"] = pd.NA
    for _sector, group in result.groupby("sector"):
        ranks = group["median_total_assets"].rank(method="first")
        tiers = pd.qcut(ranks, q=3, labels=["small", "medium", "large"])
        result.loc[group.index, "size_tier"] = tiers.astype("string")
    return result


def select_final_universe(
    eligible: pd.DataFrame,
    *,
    per_sector: int,
    seed: int,
) -> pd.DataFrame:
    sized = assign_size_tiers(eligible)
    outputs: list[pd.DataFrame] = []
    for sector, group in sized.groupby("sector", sort=True):
        if len(group) < per_sector:
            raise ValueError(f"{sector} has only {len(group)} eligible issuers; need {per_sector}")
        selected = balanced_sample(
            group,
            target=per_sector,
            strata=["industry", "size_tier"],
            seed=seed,
        )
        selected["selection_status"] = "SELECTED"
        selected_ids = set(selected["cik"])
        reserve = group.loc[~group["cik"].isin(selected_ids)].copy()
        reserve["random_score"] = reserve["cik"].map(
            lambda cik: deterministic_score(str(cik), seed)
        )
        reserve = reserve.sort_values(["random_score", "cik"]).reset_index(drop=True)
        reserve["random_rank"] = np.arange(per_sector + 1, per_sector + len(reserve) + 1)
        reserve["selection_status"] = "RESERVE"
        outputs.extend([selected, reserve])
    result = pd.concat(outputs, ignore_index=True)
    return result.sort_values(["sector", "selection_status", "random_rank", "cik"])
