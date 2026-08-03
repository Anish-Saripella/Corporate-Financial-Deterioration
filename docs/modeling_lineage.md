# Modeling Pipeline Lineage

```mermaid
flowchart LR
    A[Certified local SEC and FRED cache] --> B[Point-in-time company-quarter panel]
    B --> C[Frozen deterioration labels and temporal folds]
    C --> D[Five KPI forecast candidates]
    D --> E[Forecast backtests and KPI champions]
    C --> F[Prespecified local-level forecast features]
    F --> G[Five feature increments]
    C --> G
    G --> H[Logistic regression and boosted trees]
    H --> I[Out-of-fold calibrated probabilities]
    I --> J[Frozen champion selection]
    J --> K[One-time locked-holdout evaluation]
    K --> L[Model card, figures, asset checks, run manifest]
```

Every transformation after the source cache is local and deterministic. Forecast features use
only the company history available at their decision date. Classifier preprocessing, feature
selection behavior, fitting, calibration, and threshold selection occur inside temporal training
folds. The locked holdout is accessed only after the champion selection record is written.
