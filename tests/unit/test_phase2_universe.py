from __future__ import annotations

import pandas as pd

from cfd.phase2.universe import replace_certification_failures, select_phase2_universe


def _eligibility_rows(per_sector: int = 9) -> pd.DataFrame:
    rows = []
    for sector_number, sector in enumerate(["Consumer Discretionary", "Utilities"]):
        for index in range(per_sector):
            rows.append(
                {
                    "cik": str(sector_number * 1000 + index + 1),
                    "ticker": f"T{sector_number}{index}",
                    "sector": sector,
                    "industry": f"Industry {index % 3}",
                    "eligible": True,
                    "median_total_assets": float(index + 1),
                    "median_revenue": float(index + 1),
                }
            )
    return pd.DataFrame(rows)


def test_phase2_selection_is_seeded_stratified_and_reproducible() -> None:
    audit = _eligibility_rows()
    first = select_phase2_universe(audit, target_per_sector=6, seed=20260802)
    second = select_phase2_universe(audit, target_per_sector=6, seed=20260802)
    columns = ["cik", "sector", "selection_status", "random_rank"]
    pd.testing.assert_frame_equal(first[columns], second[columns])
    selected = first.loc[first["selection_status"] == "SELECTED"]
    assert selected.groupby("sector")["cik"].nunique().to_dict() == {
        "Consumer Discretionary": 6,
        "Utilities": 6,
    }
    # The round-robin draw covers multiple industries and all three size tiers;
    # exact industry equality is not promised when strata have different sizes.
    assert selected.groupby("sector")["industry"].nunique().min() >= 2
    assert selected.groupby("sector")["size_tier"].nunique().min() == 3
    assert not first["outcome_information_used"].any()


def test_phase2_selection_supports_confirmed_unequal_sector_targets() -> None:
    audit = _eligibility_rows(per_sector=9)
    selected = select_phase2_universe(
        audit,
        target_per_sector={"Consumer Discretionary": 7, "Utilities": 5},
    )
    counts = (
        selected.loc[selected["selection_status"] == "SELECTED"]
        .groupby("sector")["cik"]
        .nunique()
        .to_dict()
    )
    assert counts == {"Consumer Discretionary": 7, "Utilities": 5}


def test_certification_failure_uses_frozen_same_sector_reserve() -> None:
    frozen = select_phase2_universe(_eligibility_rows(), target_per_sector=6)
    certification = frozen[["cik"]].copy()
    certification["certified"] = True
    certification["failed_rules"] = "[]"
    removed = frozen.loc[
        (frozen["sector"] == "Utilities") & (frozen["selection_status"] == "SELECTED")
    ].iloc[0]
    certification.loc[certification["cik"] == removed["cik"], "certified"] = False
    certification.loc[certification["cik"] == removed["cik"], "failed_rules"] = '["KPI_COVERAGE"]'
    expected_reserve = (
        frozen.loc[(frozen["sector"] == "Utilities") & (frozen["selection_status"] == "RESERVE")]
        .sort_values(["random_rank", "random_score", "cik"])
        .iloc[0]
    )
    final, replacements = replace_certification_failures(frozen, certification, target_per_sector=6)
    assert len(final) == 12
    assert replacements.iloc[0]["replacement_cik"] == expected_reserve["cik"]
    assert replacements.iloc[0]["replacement_source"] == "frozen_same_sector_reserve"


def test_certification_shortfall_can_be_retained_with_quality_flag() -> None:
    frozen = select_phase2_universe(_eligibility_rows(per_sector=6), target_per_sector=6)
    certification = frozen[["cik"]].copy()
    certification["certified"] = True
    certification["failed_rules"] = "[]"
    failed = frozen.loc[
        (frozen["sector"] == "Utilities") & (frozen["selection_status"] == "SELECTED")
    ].iloc[0]
    certification.loc[certification["cik"] == failed["cik"], "certified"] = False
    certification.loc[
        (
            certification["cik"].isin(
                frozen.loc[
                    (frozen["sector"] == "Utilities") & (frozen["selection_status"] == "RESERVE"),
                    "cik",
                ]
            )
        ),
        "certified",
    ] = False
    certification.loc[~certification["certified"], "failed_rules"] = '["KPI_COVERAGE"]'

    final, replacements = replace_certification_failures(
        frozen,
        certification,
        target_per_sector=6,
        retain_flagged_shortfall=True,
    )

    retained = replacements.loc[replacements["replacement_source"] == "retained_with_quality_flag"]
    assert len(final) == 12
    assert retained["replacement_cik"].tolist() == [failed["cik"]]
    assert final.loc[final["cik"] == failed["cik"], "quality_tier"].iloc[0] == (
        "FLAGGED_INSUFFICIENT_CERTIFIED_RESERVE"
    )
