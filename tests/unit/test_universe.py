from pathlib import Path

import pandas as pd

from cfd.universe import balanced_sample, load_sic_rules, map_sic, select_final_universe


def test_sic_mapping_separates_cyclical_and_defensive_sectors() -> None:
    rules = load_sic_rules(Path("configs/sic_mapping.yml"))
    assert map_sic(5812, rules) == ("Consumer Discretionary", "Restaurants")
    assert map_sic(4911, rules) == ("Utilities", "Electric Utilities")
    assert map_sic(6021, rules) is None


def test_balanced_sample_is_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "cik": [f"{number:010d}" for number in range(20)],
            "industry": ["A", "B"] * 10,
        }
    )
    first = balanced_sample(frame, target=10, strata=["industry"], seed=20260802)
    second = balanced_sample(frame, target=10, strata=["industry"], seed=20260802)
    assert first["cik"].tolist() == second["cik"].tolist()
    assert first["industry"].value_counts().to_dict() == {"A": 5, "B": 5}


def test_final_selection_has_exact_sector_targets_and_reserves() -> None:
    rows = []
    for sector_index, sector in enumerate(["Consumer Discretionary", "Utilities"]):
        for number in range(35):
            rows.append(
                {
                    "cik": f"{sector_index + 1}{number:09d}",
                    "sector": sector,
                    "industry": f"industry-{number % 3}",
                    "median_total_assets": float(number + 1),
                    "median_revenue": float(number + 2),
                }
            )
    result = select_final_universe(pd.DataFrame(rows), per_sector=30, seed=20260802)
    selected = result.loc[result["selection_status"] == "SELECTED"]
    assert selected.groupby("sector").size().to_dict() == {
        "Consumer Discretionary": 30,
        "Utilities": 30,
    }
    assert (result["selection_status"] == "RESERVE").sum() == 10
