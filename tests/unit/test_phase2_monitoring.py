import pandas as pd

from cfd.phase2.monitoring import feature_monitoring_report, population_stability_index


def test_population_stability_index_increases_for_shifted_distribution() -> None:
    reference = pd.Series(range(100), dtype=float)
    same = population_stability_index(reference, reference)
    shifted = population_stability_index(reference, reference + 100)
    assert same == 0
    assert shifted > same


def test_monitoring_report_maps_drift_to_preregistered_action() -> None:
    reference = pd.DataFrame({"leverage": range(100)})
    current = pd.DataFrame({"leverage": range(100, 200)})
    config = {
        "monitoring": {
            "population_stability_warning": 0.10,
            "population_stability_escalation": 0.25,
            "missingness_increase_warning": 0.05,
            "actions": {"feature_drift_warning": "investigate_before_retraining"},
        }
    }
    report = feature_monitoring_report(reference, current, ["leverage"], config)
    assert report.iloc[0]["severity"] == "escalation"
    assert report.iloc[0]["action"] == "investigate_before_retraining"
