"""Evidence gates that prevent premature Phase 2 performance claims."""

from __future__ import annotations

from typing import Any

import pandas as pd

from cfd.evaluation.phase2 import add_episode_ids


def audit_phase2_readiness(panel: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """Check whether real panel data support model development and final testing.

    A failed gate is a useful result: it explains exactly which evidence is
    absent. It must not be bypassed by generated observations or by reopening
    the consumed Phase 1 holdout.
    """

    policy = config["evaluation_policy"]
    required = {"cik", "sector", "decision_at", "deterioration_label"}
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"Phase 2 panel is missing required columns: {missing}")
    data = add_episode_ids(panel)
    data["decision_at"] = pd.to_datetime(data["decision_at"])
    sector_rows: list[dict[str, Any]] = []
    for sector, group in data.groupby("sector"):
        sector_rows.append(
            {
                "sector": str(sector),
                "issuers": int(group["cik"].nunique()),
                "episodes": int(group["deterioration_episode_start"].sum()),
                "first_decision_at": str(group["decision_at"].min().date()),
                "last_decision_at": str(group["decision_at"].max().date()),
                "issuer_gate_passed": bool(
                    group["cik"].nunique() >= int(policy["minimum_issuers_per_sector"])
                ),
                "episode_gate_passed": bool(
                    group["deterioration_episode_start"].sum()
                    >= int(policy["minimum_episodes_per_sector"])
                ),
            }
        )
    untouched_start = policy.get("untouched_test_start")
    consumed_start = pd.Timestamp(policy["consumed_benchmark_start"])
    test_boundary_valid = (
        untouched_start is not None and pd.Timestamp(untouched_start) > consumed_start
    )
    active_population_evidence = {"exchange", "selection_as_of"}.issubset(panel.columns)
    gates = {
        "real_panel_present": len(panel) > 0,
        "sector_sample_sizes_pass": bool(sector_rows)
        and all(row["issuer_gate_passed"] and row["episode_gate_passed"] for row in sector_rows),
        "active_population_lineage_present": active_population_evidence,
        "new_untouched_test_boundary_registered": test_boundary_valid,
    }
    return {
        "phase2_version": config["version"],
        "status": "ready" if all(gates.values()) else "not_ready",
        "gates": gates,
        "sector_evidence": sector_rows,
        "consumed_benchmark_start": str(consumed_start.date()),
        "untouched_test_start": str(untouched_start) if untouched_start else None,
        "final_test_may_be_opened": all(gates.values()),
        "interpretation": (
            "Readiness is an evidence check, not a model score. A not-ready result prevents a "
            "Phase 2 performance claim but does not prevent development-only analysis. Phase 2 "
            "intentionally studies active issuers, so results retain survivorship bias and must "
            "not be generalized to delisted or failed companies."
        ),
    }
