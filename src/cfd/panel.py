"""Filing-aware company-quarter panel construction and pre-model certification."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, cast

import numpy as np
import pandas as pd

from cfd.normalization.companyfacts import normalize_fiscal_quarters, quarterly_wide

KPI_COLUMNS = [
    "interest_coverage_ttm",
    "free_cash_flow_margin_ttm",
    "total_debt_to_assets",
]
DURATION_COLUMNS = [
    "revenue",
    "operating_income",
    "interest_expense",
    "operating_cash_flow",
    "capital_expenditures",
    "net_income",
]
QUARTER_NUMBER = {"FQ1": 1, "FQ2": 2, "FQ3": 3, "FQ4": 4}


def filing_decisions(facts: pd.DataFrame, *, cutoff: date) -> pd.DataFrame:
    """Return one conservative decision date for each issuer fiscal quarter."""

    eligible = facts.loc[
        facts["fiscal_period"].isin(["Q1", "Q2", "Q3", "FY"])
        & (facts["filed_at"].dt.date <= cutoff)
        & facts["fiscal_year"].notna()
    ].copy()
    eligible["fiscal_quarter"] = eligible["fiscal_period"].map(
        {"Q1": "FQ1", "Q2": "FQ2", "Q3": "FQ3", "FY": "FQ4"}
    )
    eligible["expected_form"] = np.where(eligible["fiscal_quarter"].eq("FQ4"), "10-K", "10-Q")
    eligible = eligible.loc[
        eligible.apply(lambda row: str(row["form"]).startswith(row["expected_form"]), axis=1)
    ]
    decisions = (
        eligible.groupby(["cik", "fiscal_year", "fiscal_quarter"], as_index=False)
        .agg(
            decision_at=("filed_at", "min"),
            period_end=("end_date", "max"),
        )
        .sort_values(["cik", "fiscal_year", "fiscal_quarter"])
    )
    decisions["fiscal_year"] = decisions["fiscal_year"].astype(int)
    decisions["fiscal_quarter_number"] = decisions["fiscal_quarter"].map(QUARTER_NUMBER)
    decisions = decisions.loc[
        decisions["fiscal_year"].between(2012, cutoff.year)
        & (decisions["period_end"].dt.date <= cutoff)
    ]
    decisions["decision_key"] = (
        decisions["cik"]
        + "|"
        + decisions["fiscal_year"].astype(str)
        + "|"
        + decisions["fiscal_quarter"]
    )
    if decisions["decision_key"].duplicated().any():
        raise ValueError("Duplicate filing decision keys")
    return cast(pd.DataFrame, decisions.reset_index(drop=True))


def _point_in_time_company_rows(
    company_facts: pd.DataFrame, decisions: pd.DataFrame
) -> pd.DataFrame:
    """Build incremental filing vintages without retrospective restatement leakage.

    Original filings become usable on their filing date. Amendments and later comparative
    disclosures replace the affected fiscal-year normalization only for decisions made on or
    after the later filing date; prior decision rows are never rewritten.
    """

    normalized_cache = pd.DataFrame()
    previous_decision: pd.Timestamp | None = None
    rows: list[dict[str, Any]] = []
    for decision in decisions.sort_values("decision_at").itertuples(index=False):
        decision = cast(Any, decision)
        decision_at = pd.Timestamp(decision.decision_at)
        newly_available = company_facts.loc[company_facts["filed_at"] <= decision_at]
        if previous_decision is not None:
            newly_available = newly_available.loc[newly_available["filed_at"] > previous_decision]
        affected_years = set(newly_available["fiscal_year"].dropna().astype(int))
        affected_years.add(int(decision.fiscal_year))
        known_affected = company_facts.loc[
            (company_facts["filed_at"] <= decision_at)
            & company_facts["fiscal_year"].isin(affected_years)
        ]
        updated = normalize_fiscal_quarters(known_affected, cutoff=decision_at.date())
        if not normalized_cache.empty:
            normalized_cache = normalized_cache.loc[
                ~normalized_cache["fiscal_year"].isin(affected_years)
            ]
        normalized_cache = pd.concat([normalized_cache, updated], ignore_index=True, sort=False)
        previous_decision = decision_at
        if normalized_cache.empty:
            continue

        wide = quarterly_wide(normalized_cache)
        availability = normalized_cache.pivot_table(
            index=["cik", "fiscal_year", "fiscal_quarter"],
            columns="concept",
            values="available_at",
            aggfunc="max",
        ).add_suffix("_available_at")
        wide = wide.merge(
            availability.reset_index(),
            on=["cik", "fiscal_year", "fiscal_quarter"],
            how="left",
            validate="one_to_one",
        )
        wide["quarter_index"] = wide["fiscal_year"].astype(int) * 4 + wide[
            "fiscal_quarter_number"
        ].astype(int)
        current_index = int(decision.fiscal_year) * 4 + int(decision.fiscal_quarter_number)
        history = (
            wide.loc[wide["quarter_index"] <= current_index].sort_values("quarter_index").copy()
        )
        for concept in set(
            [
                *DURATION_COLUMNS,
                "cash_and_equivalents",
                "current_assets",
                "current_liabilities",
                "short_term_debt",
                "long_term_debt",
                "total_debt",
                "total_assets",
            ]
        ):
            available_column = f"{concept}_available_at"
            if concept in history and available_column in history:
                history.loc[history[available_column] > decision.decision_at, concept] = np.nan
        current = history.loc[history["quarter_index"] == current_index]
        if current.empty:
            continue
        current_row = current.iloc[-1]
        trailing = history.tail(4)
        row = cast(dict[str, Any], current_row.to_dict())
        row.update(
            {
                "decision_key": decision.decision_key,
                "decision_at": pd.Timestamp(decision.decision_at),
                "period_end": pd.Timestamp(decision.period_end),
                "ttm_quarters_present": len(trailing),
            }
        )
        for concept in DURATION_COLUMNS:
            values = trailing.get(concept, pd.Series(dtype=float))
            row[f"{concept}_ttm"] = values.sum(min_count=4) if len(values) == 4 else np.nan
        relevant = normalized_cache.loc[
            (
                normalized_cache["fiscal_year"].astype(int) * 4
                + normalized_cache["fiscal_quarter"].map(QUARTER_NUMBER).astype(int)
            ).between(current_index - 3, current_index)
            & (normalized_cache["available_at"] <= decision_at)
        ]
        row["accession_numbers_json"] = json.dumps(
            sorted(relevant["accession_number"].dropna().astype(str).unique().tolist())
        )
        row["maximum_source_available_at"] = relevant["available_at"].max()
        row["preferred_tag_share"] = float((relevant["tag_priority"] == 0).mean())
        row["derived_fact_share"] = float(relevant["is_derived"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def calculate_kpis(
    panel: pd.DataFrame, *, minimum_interest_expense: float = 1_000_000
) -> pd.DataFrame:
    result = panel.copy()
    interest = result["interest_expense_ttm"].abs()
    result["interest_denominator_invalid"] = interest.lt(minimum_interest_expense) | interest.isna()
    result["revenue_denominator_invalid"] = (
        result["revenue_ttm"].le(0) | result["revenue_ttm"].isna()
    )
    result["assets_denominator_invalid"] = (
        result["total_assets"].le(0) | result["total_assets"].isna()
    )
    result["negative_operating_income"] = result["operating_income_ttm"].lt(0)
    result["interest_coverage_ttm"] = np.where(
        result["interest_denominator_invalid"],
        np.nan,
        result["operating_income_ttm"] / interest,
    )
    result["free_cash_flow_ttm"] = (
        result["operating_cash_flow_ttm"] - result["capital_expenditures_ttm"]
    )
    result["free_cash_flow_margin_ttm"] = np.where(
        result["revenue_denominator_invalid"],
        np.nan,
        result["free_cash_flow_ttm"] / result["revenue_ttm"],
    )
    result["total_debt_to_assets"] = np.where(
        result["assets_denominator_invalid"],
        np.nan,
        result["total_debt"] / result["total_assets"],
    )
    result["operating_margin_ttm"] = np.where(
        result["revenue_denominator_invalid"],
        np.nan,
        result["operating_income_ttm"] / result["revenue_ttm"],
    )
    current_assets = (
        result["current_assets"]
        if "current_assets" in result
        else pd.Series(np.nan, index=result.index)
    )
    current_liabilities = (
        result["current_liabilities"]
        if "current_liabilities" in result
        else pd.Series(np.nan, index=result.index)
    )
    cash = (
        result["cash_and_equivalents"]
        if "cash_and_equivalents" in result
        else pd.Series(np.nan, index=result.index)
    )
    result["current_ratio"] = current_assets / current_liabilities.replace(0, np.nan)
    result["cash_to_assets"] = cash / result["total_assets"].replace(0, np.nan)
    for kpi in KPI_COLUMNS:
        result[f"{kpi}_missing"] = result[kpi].isna()
    return result


def add_macro_vintages(
    panel: pd.DataFrame, macro: pd.DataFrame, macro_config: list[dict[str, Any]]
) -> pd.DataFrame:
    """Aggregate each series over the 92 days ending at the issuer period end, as then known."""

    result = panel.copy()
    source = macro.copy()
    for column in ["observation_date", "realtime_start", "realtime_end"]:
        source[column] = pd.to_datetime(source[column], errors="coerce")
    max_available: list[Any] = [pd.NaT] * len(result)
    for specification in macro_config:
        series_id = str(specification["series_id"])
        series = source.loc[source["series_id"] == series_id].copy()
        if bool(specification["vintage_required"]):
            series["available_at"] = series["realtime_start"]
        else:
            series["available_at"] = series["observation_date"] + pd.Timedelta(days=1)
        values: list[float] = []
        availabilities: list[Any] = []
        for row in result.itertuples(index=False):
            row = cast(Any, row)
            start = row.period_end - pd.Timedelta(days=92)
            eligible = series.loc[
                series["observation_date"].between(start, row.period_end)
                & (series["available_at"] <= row.decision_at)
            ]
            if eligible.empty:
                values.append(np.nan)
                availabilities.append(pd.NaT)
                continue
            latest = eligible.sort_values("available_at").drop_duplicates(
                "observation_date", keep="last"
            )
            aggregation = str(specification["quarterly_aggregation"])
            value = latest["value"].sum() if aggregation == "sum" else latest["value"].mean()
            values.append(float(value))
            availabilities.append(latest["available_at"].max())
        result[series_id] = values
        current_max = pd.Series(max_available, index=result.index, dtype="datetime64[ns]")
        series_available = pd.Series(availabilities, index=result.index, dtype="datetime64[ns]")
        max_available = pd.concat([current_max, series_available], axis=1).max(axis=1).tolist()
    result["macro_available_at_max"] = max_available
    return result


def add_peer_context(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    result["calendar_quarter"] = result["period_end"].dt.to_period("Q").astype(str)
    for kpi in KPI_COLUMNS:
        sector_group = result.groupby(["calendar_quarter", "sector"])[kpi]
        industry_group = result.groupby(["calendar_quarter", "sector", "industry"])[kpi]
        result[f"{kpi}_sector_median"] = sector_group.transform("median")
        result[f"{kpi}_industry_median"] = industry_group.transform("median")
        result[f"{kpi}_sector_percentile"] = sector_group.rank(pct=True)
        result[f"{kpi}_vs_sector_median"] = result[kpi] - result[f"{kpi}_sector_median"]
    return result


def build_point_in_time_panel(
    facts: pd.DataFrame,
    metadata: pd.DataFrame,
    macro: pd.DataFrame,
    macro_config: list[dict[str, Any]],
    *,
    cutoff: date,
) -> pd.DataFrame:
    decisions = filing_decisions(facts, cutoff=cutoff)
    company_frames: list[pd.DataFrame] = []
    for cik, company_decisions in decisions.groupby("cik", sort=True):
        company_facts = facts.loc[facts["cik"] == cik].copy()
        company_frame = _point_in_time_company_rows(company_facts, company_decisions)
        if not company_frame.empty:
            company_frames.append(company_frame)
    panel = pd.concat(company_frames, ignore_index=True)
    panel = calculate_kpis(panel)
    metadata_columns = ["cik", "company_name", "ticker", "sector", "industry", "size_tier"]
    panel = panel.merge(metadata[metadata_columns], on="cik", how="left", validate="many_to_one")
    panel = add_macro_vintages(panel, macro, macro_config)
    panel = add_peer_context(panel)
    panel = panel.sort_values(["decision_at", "cik"]).reset_index(drop=True)
    if panel["decision_key"].duplicated().any():
        raise ValueError("Point-in-time panel contains duplicate decision keys")
    if (panel["maximum_source_available_at"] > panel["decision_at"]).any():
        raise ValueError("Financial information entered the panel before availability")
    known_macro = panel["macro_available_at_max"].notna()
    if (
        panel.loc[known_macro, "macro_available_at_max"] > panel.loc[known_macro, "decision_at"]
    ).any():
        raise ValueError("Macro vintage entered the panel before availability")
    return panel


def _maximum_consecutive(mask: pd.Series, positions: pd.Series) -> int:
    valid = sorted(set(positions.loc[mask].astype(int).tolist()))
    maximum = current = 0
    previous: int | None = None
    for position in valid:
        current = current + 1 if previous is not None and position == previous + 1 else 1
        maximum = max(maximum, current)
        previous = position
    return maximum


def certify_panel(
    panel: pd.DataFrame,
    *,
    universe_version: str,
    minimum_observed: int = 24,
    minimum_consecutive: int = 16,
    minimum_coverage: float = 0.80,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return rule-level evidence and a company-level certification summary."""

    rules: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for cik, company in panel.groupby("cik", sort=True):
        company = company.sort_values(["fiscal_year", "fiscal_quarter_number"])
        positions = company["fiscal_year"] * 4 + company["fiscal_quarter_number"]
        all_pass = True
        failed: list[str] = []
        for kpi in KPI_COLUMNS:
            valid = company[kpi].notna() & np.isfinite(company[kpi])
            observed = int(valid.sum())
            consecutive = _maximum_consecutive(valid, positions)
            first_valid = positions.loc[valid].min() if valid.any() else positions.max() + 1
            expected = max(int(positions.max() - first_valid + 1), 0)
            coverage = observed / expected if expected else 0.0
            prefix = "KPI_" + kpi.upper()
            evidence = [
                (
                    f"{prefix}_OBSERVATIONS",
                    observed,
                    minimum_observed,
                    observed >= minimum_observed,
                ),
                (
                    f"{prefix}_CONTINUITY",
                    consecutive,
                    minimum_consecutive,
                    consecutive >= minimum_consecutive,
                ),
                (f"{prefix}_COVERAGE", coverage, minimum_coverage, coverage >= minimum_coverage),
            ]
            for rule_code, observed_value, required_value, passed in evidence:
                rules.append(
                    {
                        "universe_version": universe_version,
                        "cik": cik,
                        "sector": company["sector"].iloc[0],
                        "rule_code": rule_code,
                        "passed": bool(passed),
                        "observed_value": float(observed_value),
                        "required_value": float(required_value),
                        "evidence_as_of": company["decision_at"].max(),
                    }
                )
                if not passed:
                    all_pass = False
                    failed.append(rule_code)
        lineage_checks: dict[str, bool] = {
            "DUPLICATE_DECISION_KEY": bool(not company["decision_key"].duplicated().any()),
            "POINT_IN_TIME_LEAKAGE": bool(
                not (company["maximum_source_available_at"] > company["decision_at"]).any()
            ),
            "MACRO_VINTAGE_LEAKAGE": bool(
                not (
                    company["macro_available_at_max"].notna()
                    & (company["macro_available_at_max"] > company["decision_at"])
                ).any()
            ),
            "MATERIAL_LINEAGE_BREAK": bool(company["accession_numbers_json"].notna().all()),
        }
        for rule_code, passed in lineage_checks.items():
            rules.append(
                {
                    "universe_version": universe_version,
                    "cik": cik,
                    "sector": company["sector"].iloc[0],
                    "rule_code": rule_code,
                    "passed": bool(passed),
                    "observed_value": float(bool(passed)),
                    "required_value": 1.0,
                    "evidence_as_of": company["decision_at"].max(),
                }
            )
            if not passed:
                all_pass = False
                failed.append(rule_code)
        summaries.append(
            {
                "cik": cik,
                "company_name": company["company_name"].iloc[0],
                "ticker": company["ticker"].iloc[0],
                "sector": company["sector"].iloc[0],
                "certified": all_pass,
                "failed_rules": json.dumps(failed),
            }
        )
    return pd.DataFrame(rules), pd.DataFrame(summaries)
