"""Stage 20: freeze the Phase 2 active-company sample and reserve order."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.phase2.universe import select_phase2_universe


def run_stage_20(eligibility_path: Path | None = None) -> dict[str, Any]:
    """Select from a real all-candidate eligibility audit; never fabricate rows."""

    root = repository_root()
    source = eligibility_path or root / "data" / "processed" / "phase2_company_eligibility.parquet"
    if not source.exists():
        raise FileNotFoundError(
            f"Real all-candidate eligibility audit not found at {source}. Build it from the SEC "
            "active-issuer population before running Stage 20."
        )
    config = read_yaml(root / "configs" / "phase2.yml")
    policy = config["universe_policy"]
    audit = pd.read_parquet(source)
    frozen = select_phase2_universe(
        audit,
        target_per_sector={
            sector: int(value) for sector, value in policy["target_count_by_sector"].items()
        },
        seed=int(policy["random_seed"]),
    )
    canonical = frozen.sort_values(["sector", "selection_status", "random_rank", "cik"])[
        ["cik", "sector", "selection_status", "random_rank"]
    ].to_json(orient="records")
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    frozen.to_parquet(processed / "phase2_frozen_universe.parquet", index=False)
    frozen.to_csv(reports / "phase2_frozen_universe_and_reserves.csv", index=False)
    result = {
        "status": "complete",
        "universe_version": str(frozen["universe_version"].iloc[0]),
        "selection_as_of": str(policy["selection_as_of"]),
        "financial_history_cutoff": str(policy["financial_history_cutoff"]),
        "random_seed": int(policy["random_seed"]),
        "selected_companies": int((frozen["selection_status"] == "SELECTED").sum()),
        "reserve_companies": int((frozen["selection_status"] == "RESERVE").sum()),
        "sector_counts": frozen.loc[frozen["selection_status"] == "SELECTED"].groupby(
            "sector"
        )["cik"].nunique().to_dict(),
        "selection_sha256": digest,
        "outcomes_or_model_results_used": False,
    }
    (reports / "stage20_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
