"""Phase 2 universe selection using the frozen Phase 1 sampling mechanism."""

from __future__ import annotations

from typing import Any

import pandas as pd

from cfd.universe import select_final_universe

REQUIRED_ELIGIBILITY_COLUMNS = {
    "cik",
    "sector",
    "industry",
    "eligible",
    "median_total_assets",
    "median_revenue",
}


def select_phase2_universe(
    eligibility_audit: pd.DataFrame,
    *,
    target_per_sector: int | dict[str, int] = 42,
    seed: int = 42,
) -> pd.DataFrame:
    """Select eligible companies and freeze a reproducible reserve order.

    ``deterministic_score`` behaves like a seeded random draw: CIKs receive a
    pseudo-random hash score, but the same seed and candidate data always give
    the same result. Industry and size-tier round-robin selection prevents a
    large stratum from dominating the sector sample.
    """

    missing = REQUIRED_ELIGIBILITY_COLUMNS - set(eligibility_audit.columns)
    if missing:
        raise ValueError(f"Eligibility audit is missing columns: {sorted(missing)}")
    eligible = eligibility_audit.loc[eligibility_audit["eligible"].astype(bool)].copy()
    eligible["cik"] = eligible["cik"].astype(str).str.zfill(10)
    if eligible["cik"].duplicated().any():
        raise ValueError("Eligibility audit contains duplicate eligible CIKs")
    sectors = sorted(eligible["sector"].dropna().unique())
    if sectors != ["Consumer Discretionary", "Utilities"]:
        raise ValueError(f"Phase 2 requires the two controlled sectors; found {sectors}")
    counts = eligible.groupby("sector")["cik"].nunique()
    targets = (
        {sector: int(target_per_sector) for sector in sectors}
        if isinstance(target_per_sector, int)
        else {sector: int(target_per_sector[sector]) for sector in sectors}
    )
    insufficient = counts.loc[[counts[sector] < targets[sector] for sector in counts.index]]
    if not insufficient.empty:
        raise ValueError(
            "Not enough eligible active companies for Phase 2: "
            f"{insufficient.to_dict()}. Expand mapped candidates without changing the seed."
        )
    selected = select_final_universe(
        eligible,
        per_sector=target_per_sector,
        seed=seed,
    )
    selected["selection_as_of"] = pd.Timestamp("2026-08-02")
    selected["financial_history_cutoff"] = pd.Timestamp("2025-12-31")
    version_counts = "-".join(f"{sector[:1]}{targets[sector]}" for sector in sectors)
    selected["universe_version"] = f"phase2-active-issuers-{version_counts}-v2"
    selected["sampling_method"] = "seeded_stratified_random_without_replacement"
    selected["eligibility_applied_before_sampling"] = True
    selected["outcome_information_used"] = False
    final_counts = (
        selected.loc[selected["selection_status"] == "SELECTED"]
        .groupby("sector")["cik"]
        .nunique()
    )
    if final_counts.to_dict() != targets:
        raise ValueError(f"Phase 2 selection did not preserve sector targets: {final_counts}")
    return selected.reset_index(drop=True)


def replace_certification_failures(
    frozen_universe: pd.DataFrame,
    certification: pd.DataFrame,
    *,
    target_per_sector: int = 42,
    retain_flagged_shortfall: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace failed selections from the frozen same-sector reserve order.

    Certification can concern KPI coverage, continuity, point-in-time lineage,
    or another preregistered data-quality rule. Outcomes and model results are
    deliberately absent from this function.
    """

    universe = frozen_universe.copy()
    audit = certification.copy()
    universe["cik"] = universe["cik"].astype(str).str.zfill(10)
    audit["cik"] = audit["cik"].astype(str).str.zfill(10)
    if audit["cik"].duplicated().any():
        raise ValueError("Certification contains duplicate CIKs")
    status = audit.set_index("cik")["certified"].astype(bool)
    missing = sorted(set(universe["cik"]) - set(status.index))
    if missing:
        raise ValueError(f"Certification is missing {len(missing)} sampled or reserve issuers")
    final_rows: list[pd.Series] = []
    replacement_rows: list[dict[str, Any]] = []
    for sector, sector_universe in universe.groupby("sector", sort=True):
        chosen = sector_universe.loc[
            sector_universe["selection_status"] == "SELECTED"
        ].sort_values("random_rank")
        passed = chosen.loc[chosen["cik"].map(status)].copy()
        failed = chosen.loc[~chosen["cik"].map(status)].copy()
        reserves = sector_universe.loc[
            (sector_universe["selection_status"] == "RESERVE")
            & sector_universe["cik"].map(status)
        ].sort_values(["random_rank", "random_score", "cik"])
        if len(reserves) < len(failed) and not retain_flagged_shortfall:
            raise ValueError(
                f"Insufficient certified {sector} reserves: need {len(failed)}, "
                f"have {len(reserves)}"
            )
        replacements = reserves.head(len(failed)).copy()
        replaceable_failed = failed.head(len(replacements))
        retained_failed = failed.iloc[len(replacements) :].copy()
        for (_, removed), (_, replacement) in zip(
            replaceable_failed.iterrows(), replacements.iterrows(), strict=True
        ):
            replacement["selection_status"] = "SELECTED"
            replacement["random_rank"] = int(removed["random_rank"])
            replacement_rows.append(
                {
                    "sector": sector,
                    "removed_cik": removed["cik"],
                    "replacement_cik": replacement["cik"],
                    "replacement_rank": int(removed["random_rank"]),
                    "replacement_source": "frozen_same_sector_reserve",
                    "failed_rules": audit.set_index("cik").loc[
                        removed["cik"], "failed_rules"
                    ],
                    "outcome_information_used": False,
                }
            )
            passed = pd.concat([passed, replacement.to_frame().T], ignore_index=True)
        for _, retained in retained_failed.iterrows():
            retained["quality_tier"] = "FLAGGED_INSUFFICIENT_CERTIFIED_RESERVE"
            replacement_rows.append(
                {
                    "sector": sector,
                    "removed_cik": pd.NA,
                    "replacement_cik": retained["cik"],
                    "replacement_rank": int(retained["random_rank"]),
                    "replacement_source": "retained_with_quality_flag",
                    "failed_rules": audit.set_index("cik").loc[
                        retained["cik"], "failed_rules"
                    ],
                    "outcome_information_used": False,
                }
            )
            passed = pd.concat([passed, retained.to_frame().T], ignore_index=True)
        if len(passed) != target_per_sector:
            raise ValueError(f"Replacement did not produce {target_per_sector} {sector} issuers")
        final_rows.extend(row for _, row in passed.iterrows())
    final = pd.DataFrame(final_rows).sort_values(["sector", "random_rank", "cik"])
    replacements = pd.DataFrame(replacement_rows)
    if final["cik"].duplicated().any() or len(final) != target_per_sector * 2:
        raise ValueError("Final certified Phase 2 universe has invalid size or duplicate issuers")
    return final.reset_index(drop=True), replacements
