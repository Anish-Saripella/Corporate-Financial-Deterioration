"""Extract and normalize SEC Company Facts into standalone fiscal-quarter observations."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from cfd.config import read_yaml

PERIODIC_FORMS = {"10-Q", "10-Q/A", "10-K", "10-K/A"}
FISCAL_QUARTER_MAP = {"Q1": "FQ1", "Q2": "FQ2", "Q3": "FQ3", "FY": "FQ4"}


def load_concept_config(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], read_yaml(Path(path))["concepts"])


def extract_company_facts(
    payload: dict[str, Any],
    concept_config: dict[str, Any],
) -> pd.DataFrame:
    """Extract configured US-GAAP facts while preserving every accession-aware context."""

    cik = str(payload["cik"]).zfill(10)
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []
    for concept, specification in concept_config.items():
        for priority, tag in enumerate(specification["preferred_tags"]):
            fact = us_gaap.get(tag)
            if not fact:
                continue
            expected_unit = specification.get("unit", "USD")
            for unit, observations in fact.get("units", {}).items():
                if unit != expected_unit:
                    continue
                for observation in observations:
                    form = observation.get("form")
                    if form not in PERIODIC_FORMS:
                        continue
                    rows.append(
                        {
                            "cik": cik,
                            "entity_name": payload.get("entityName"),
                            "concept": concept,
                            "taxonomy_tag": tag,
                            "tag_priority": priority,
                            "statement": specification["statement"],
                            "period_type": specification["period_type"],
                            "unit": unit,
                            "start_date": observation.get("start"),
                            "end_date": observation.get("end"),
                            "value": observation.get("val"),
                            "accession_number": observation.get("accn"),
                            "fiscal_year": observation.get("fy"),
                            "fiscal_period": observation.get("fp"),
                            "form": form,
                            "filed_at": observation.get("filed"),
                            "frame": observation.get("frame"),
                        }
                    )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ["start_date", "end_date", "filed_at"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="coerce").astype("Int64")
    frame["duration_days"] = (frame["end_date"] - frame["start_date"]).dt.days + 1
    return frame.dropna(
        subset=["end_date", "filed_at", "value", "accession_number", "fiscal_year", "fiscal_period"]
    )


def _select_record(group: pd.DataFrame, *, prefer_quarter: bool) -> pd.Series:
    candidates = group.copy()
    if prefer_quarter:
        quarterly = candidates.loc[candidates["duration_days"].between(60, 130)]
        if not quarterly.empty:
            candidates = quarterly
    candidates = candidates.sort_values(
        ["tag_priority", "filed_at", "duration_days", "accession_number"],
        ascending=[True, False, True, False],
    )
    return candidates.iloc[0]


def _instant_quarters(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid = frame.loc[frame["fiscal_period"].isin(FISCAL_QUARTER_MAP)]
    for (_cik, _concept, _fiscal_year, fiscal_period), group in valid.groupby(
        ["cik", "concept", "fiscal_year", "fiscal_period"], sort=True
    ):
        selected = _select_record(group, prefer_quarter=False)
        row = cast(dict[str, Any], selected.to_dict())
        row["fiscal_quarter"] = FISCAL_QUARTER_MAP[str(fiscal_period)]
        row["available_at"] = selected["filed_at"]
        row["is_derived"] = False
        rows.append(row)
    return rows


def _duration_quarters(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid = frame.loc[frame["fiscal_period"].isin(FISCAL_QUARTER_MAP)]
    for (_cik, _concept, _fiscal_year), annual_group in valid.groupby(
        ["cik", "concept", "fiscal_year"]
    ):
        selected_by_period: dict[str, pd.Series] = {}
        for fiscal_period, period_group in annual_group.groupby("fiscal_period"):
            prefer_quarter = str(fiscal_period) in {"Q1", "Q2", "Q3"}
            selected_by_period[str(fiscal_period)] = _select_record(
                period_group, prefer_quarter=prefer_quarter
            )

        standalone: dict[str, dict[str, Any]] = {}
        for fiscal_period in ["Q1", "Q2", "Q3"]:
            selected = selected_by_period.get(fiscal_period)
            if selected is None:
                continue
            value = float(selected["value"])
            derived = False
            dependencies = [selected]
            duration = selected["duration_days"]
            if fiscal_period == "Q2" and pd.notna(duration) and duration > 130:
                previous = standalone.get("Q1")
                if previous is None:
                    continue
                value -= float(previous["value"])
                derived = True
                dependencies.append(pd.Series(previous))
            elif fiscal_period == "Q3" and pd.notna(duration) and duration > 130:
                previous_q1 = standalone.get("Q1")
                previous_q2 = standalone.get("Q2")
                if previous_q1 is None or previous_q2 is None:
                    continue
                value -= float(previous_q1["value"]) + float(previous_q2["value"])
                derived = True
                dependencies.extend([pd.Series(previous_q1), pd.Series(previous_q2)])
            row = cast(dict[str, Any], selected.to_dict())
            row["value"] = value
            row["fiscal_quarter"] = FISCAL_QUARTER_MAP[fiscal_period]
            row["available_at"] = max(item["filed_at"] for item in dependencies)
            row["is_derived"] = derived
            standalone[fiscal_period] = row
            rows.append(row)

        annual = selected_by_period.get("FY")
        if annual is not None and all(period in standalone for period in ["Q1", "Q2", "Q3"]):
            q4_value = float(annual["value"]) - sum(
                float(standalone[period]["value"]) for period in ["Q1", "Q2", "Q3"]
            )
            row = cast(dict[str, Any], annual.to_dict())
            row["value"] = q4_value
            row["fiscal_quarter"] = "FQ4"
            row["available_at"] = max(
                [annual["filed_at"]]
                + [standalone[period]["available_at"] for period in ["Q1", "Q2", "Q3"]]
            )
            row["is_derived"] = True
            rows.append(row)
    return rows


def normalize_fiscal_quarters(
    facts: pd.DataFrame,
    *,
    cutoff: date,
) -> pd.DataFrame:
    """Build final-cutoff standalone fiscal quarters for eligibility and selection."""

    if facts.empty:
        return facts.copy()
    eligible = facts.loc[
        (facts["filed_at"].dt.date <= cutoff)
        & (facts["end_date"].dt.year >= 2011)
        & (facts["end_date"].dt.year <= cutoff.year)
    ].copy()
    rows = _instant_quarters(eligible.loc[eligible["period_type"] == "instant"])
    rows.extend(_duration_quarters(eligible.loc[eligible["period_type"] == "duration"]))
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["fiscal_year"] = result["fiscal_year"].astype(int)
    result["available_at"] = pd.to_datetime(result["available_at"])
    result["mapping_version"] = "us-gaap-v1"
    return result.sort_values(["cik", "fiscal_year", "fiscal_quarter", "concept"])


def quarterly_wide(quarters: pd.DataFrame) -> pd.DataFrame:
    """Pivot normalized concepts into one row per company fiscal quarter."""

    if quarters.empty:
        return quarters.copy()
    values = quarters.pivot_table(
        index=["cik", "fiscal_year", "fiscal_quarter"],
        columns="concept",
        values="value",
        aggfunc="first",
    ).reset_index()
    availability = quarters.groupby(["cik", "fiscal_year", "fiscal_quarter"], as_index=False).agg(
        quarter_available_at=("available_at", "max")
    )
    result = values.merge(availability, on=["cik", "fiscal_year", "fiscal_quarter"])
    if "total_debt" not in result:
        result["total_debt"] = np.nan
    debt_components = [
        column for column in ["short_term_debt", "long_term_debt"] if column in result
    ]
    if debt_components:
        component_total = result[debt_components].sum(axis=1, min_count=1)
        result["total_debt"] = result["total_debt"].fillna(component_total)
    order = {"FQ1": 1, "FQ2": 2, "FQ3": 3, "FQ4": 4}
    result["fiscal_quarter_number"] = result["fiscal_quarter"].map(order)
    return result.sort_values(["cik", "fiscal_year", "fiscal_quarter_number"])
