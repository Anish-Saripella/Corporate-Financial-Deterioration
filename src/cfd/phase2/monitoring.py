"""Transparent drift and operating-policy monitoring for Phase 2."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


def population_stability_index(
    reference: pd.Series, current: pd.Series, *, bins: int = 10
) -> float:
    """Measure distribution drift using reference-period quantile bins.

    PSI is a diagnostic convention, not a hypothesis test. Approximately 0.10
    is commonly treated as a warning and 0.25 as material drift; project actions
    are preregistered in ``configs/phase2.yml``.
    """

    base = reference.dropna().to_numpy(dtype=float)
    recent = current.dropna().to_numpy(dtype=float)
    if len(base) < bins or len(recent) == 0:
        return np.nan
    boundaries = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 3:
        return 0.0
    boundaries[0], boundaries[-1] = -np.inf, np.inf
    base_share = np.histogram(base, bins=boundaries)[0] / len(base)
    current_share = np.histogram(recent, bins=boundaries)[0] / len(recent)
    base_share = np.clip(base_share, 1e-6, None)
    current_share = np.clip(current_share, 1e-6, None)
    return float(np.sum((current_share - base_share) * np.log(current_share / base_share)))


def feature_monitoring_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    features: Sequence[str],
    config: dict[str, Any],
) -> pd.DataFrame:
    """Return feature drift, missingness change, severity, and required action."""

    monitoring = config["monitoring"]
    rows: list[dict[str, Any]] = []
    for feature in features:
        if feature not in reference or feature not in current:
            raise ValueError(f"Monitoring feature is absent: {feature}")
        psi = population_stability_index(reference[feature], current[feature])
        missingness_change = float(
            current[feature].isna().mean() - reference[feature].isna().mean()
        )
        if np.isfinite(psi) and psi >= float(monitoring["population_stability_escalation"]):
            severity = "escalation"
        elif (
            np.isfinite(psi)
            and psi >= float(monitoring["population_stability_warning"])
        ) or missingness_change >= float(monitoring["missingness_increase_warning"]):
            severity = "warning"
        else:
            severity = "normal"
        rows.append(
            {
                "feature": feature,
                "population_stability_index": psi,
                "reference_missing_rate": float(reference[feature].isna().mean()),
                "current_missing_rate": float(current[feature].isna().mean()),
                "missingness_change": missingness_change,
                "severity": severity,
                "action": (
                    monitoring["actions"]["feature_drift_warning"]
                    if severity != "normal"
                    else "continue_monitoring"
                ),
            }
        )
    return pd.DataFrame(rows)
