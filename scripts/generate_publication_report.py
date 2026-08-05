"""Build the Phase 1 publication-style research report and supporting figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "outputs/powerbi_stage17/Corporate_Financial_Deterioration_PowerBI_Import.xlsx"
OUT = ROOT / "reports/publication"
FIG = ROOT / "reports/figures/publication"

NAVY = "17365D"
BLUE = "2E75B6"
PALE = "EAF1F8"
GRAY = "667085"
RED = "B42318"
AMBER = "D97706"
GREEN = "067647"


def font(run, size: float = 10.5, bold: bool = False, color: str = "202124", italic: bool = False) -> None:
    run.font.name = "Calibri"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: list[int]) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=True):
            set_cell_width(cell, width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tc_pr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side, value in (("top", 80), ("bottom", 80), ("start", 120), ("end", 120)):
                node = OxmlElement(f"w:{side}")
                node.set(qn("w:w"), str(value))
                node.set(qn("w:type"), "dxa")
                margins.append(node)
            tc_pr.append(margins)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for idx, value in enumerate(headers):
        cell = table.rows[0].cells[idx]
        shade(cell, PALE)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        font(p.add_run(value), 9, True, NAVY)
    for values in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(values):
            p = cells[idx].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            font(p.add_run(value), 8.7)
    set_table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_body(doc: Document, text: str, bold_lead: str | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.10
    if bold_lead and text.startswith(bold_lead):
        font(p.add_run(bold_lead), bold=True, color=NAVY)
        text = text[len(bold_lead) :]
    font(p.add_run(text))


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(-0.25)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.167
    font(p.add_run(text), 10.3)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    font(p.add_run(text), {1: 16, 2: 13, 3: 12}[level], True, NAVY if level < 3 else BLUE)


def add_figure(doc: Document, path: Path, caption: str, width: float = 6.3) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    font(cap.add_run(caption), 8.5, italic=True, color=GRAY)


def make_figures(watch: pd.DataFrame, model: pd.DataFrame, portfolio: pd.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False})

    bands = ["Low", "Moderate", "High", "Severe"]
    counts = watch.groupby(["sector", "risk_band"]).size().unstack(fill_value=0).reindex(columns=bands)
    ax = counts.plot(kind="bar", stacked=True, color=["#5B8FF9", "#F6BD16", "#E8684A", "#B42318"], figsize=(8.2, 4.2))
    ax.set(title="Latest risk-band composition by sector", xlabel="", ylabel="Companies")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(title="Risk band", ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    plt.tight_layout(); plt.savefig(FIG / "risk_band_by_sector.png", dpi=220); plt.close()

    top = watch.nlargest(10, "probability").sort_values("probability")
    colors = ["#B42318" if x == "Severe" else "#D97706" for x in top["risk_band"]]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.barh(top["ticker"], top["probability"] * 100, color=colors)
    ax.set(title="Highest latest deterioration-risk estimates", xlabel="Estimated deterioration risk (%)", ylabel="")
    ax.axvline(watch.loc[watch.alert, "threshold"].median() * 100, color=f"#{NAVY}", ls="--", lw=1.2, label="Median alert threshold")
    ax.legend(frameon=False, loc="lower right")
    plt.tight_layout(); plt.savefig(FIG / "top_risk_companies.png", dpi=220); plt.close()

    metrics = portfolio.set_index("sector")[["median_interest_coverage_x", "median_free_cash_flow_margin", "median_debt_to_assets"]]
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.5))
    labels = [("median_interest_coverage_x", "Interest coverage", "x", 1), ("median_free_cash_flow_margin", "FCF margin", "%", 100), ("median_debt_to_assets", "Debt/assets", "%", 100)]
    for ax, (col, title, unit, scale) in zip(axes, labels, strict=True):
        vals = metrics[col] * scale
        ax.bar(["Consumer\nDiscretionary", "Utilities"], vals, color=[f"#{BLUE}", f"#{AMBER}"])
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.tick_params(axis="x", labelsize=8)
        ax.axhline(0, color="#98A2B3", lw=0.7)
    fig.suptitle("Sector-level financial condition at the latest evaluated snapshot", fontweight="bold")
    plt.tight_layout(); plt.savefig(FIG / "sector_kpi_comparison.png", dpi=220); plt.close()

    hold = model[model["evaluation_sample"].eq("Locked final holdout")].set_index("sector")
    plot = hold.loc[["Consumer Discretionary", "Utilities"], ["PR_AUC", "recall", "precision"]]
    ax = plot.plot(kind="bar", figsize=(8.2, 4.2), color=[f"#{NAVY}", f"#{BLUE}", f"#{AMBER}"])
    ax.set(title="Locked-holdout discrimination and alert-quality metrics", xlabel="", ylabel="Metric value", ylim=(0, 0.7))
    ax.tick_params(axis="x", rotation=0)
    ax.legend(frameon=False, ncol=3, loc="upper center")
    plt.tight_layout(); plt.savefig(FIG / "holdout_sector_performance.png", dpi=220); plt.close()

    champ = model[
        model["is_champion"]
        & model["evaluation_sample"].str.contains("OOF")
        & model["sector"].eq("Overall")
    ].copy()
    champ = champ.sort_values("fold_id")
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    ax.plot(champ["fold_id"].astype(str), champ["PR_AUC"], marker="o", color=f"#{NAVY}", label="PR-AUC")
    ax.plot(champ["fold_id"].astype(str), champ["Brier_score"], marker="o", color=f"#{AMBER}", label="Brier score")
    ax.set(title="Champion out-of-fold performance across expanding-window folds", xlabel="Temporal fold", ylabel="Metric value")
    ax.legend(frameon=False)
    plt.tight_layout(); plt.savefig(FIG / "temporal_fold_stability.png", dpi=220); plt.close()


def configure_styles(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5); section.page_height = Inches(11)
    section.top_margin = Inches(1); section.bottom_margin = Inches(1)
    section.left_margin = Inches(1); section.right_margin = Inches(1)
    section.header_distance = Inches(0.492); section.footer_distance = Inches(0.492)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"; normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6); normal.paragraph_format.line_spacing = 1.10
    for level, size, before, after in ((1, 16, 16, 8), (2, 13, 12, 6), (3, 12, 8, 4)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Calibri"; style.font.size = Pt(size); style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(NAVY if level < 3 else BLUE)
        style.paragraph_format.space_before = Pt(before); style.paragraph_format.space_after = Pt(after)


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    portfolio = pd.read_excel(WORKBOOK, "Portfolio")
    watch = pd.read_excel(WORKBOOK, "Watchlist", dtype={"cik": str})
    model = pd.read_excel(WORKBOOK, "ModelPerformance")
    make_figures(watch, model, portfolio)
    hold = model[model["evaluation_sample"].eq("Locked final holdout")].set_index("sector")

    doc = Document()
    configure_styles(doc)
    section = doc.sections[0]
    hp = section.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    font(hp.add_run("CORPORATE FINANCIAL DETERIORATION | PHASE 1 RESEARCH"), 8.5, True, GRAY)
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(fp.add_run("Independent analytical research | Not investment advice or a default-probability model"), 8, color=GRAY)

    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(92); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(p.add_run("FINANCIAL RISK & DATA SCIENCE RESEARCH"), 10, True, AMBER)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(8)
    font(p.add_run("Corporate Financial Deterioration Early-Warning Platform"), 27, True, NAVY)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(24)
    font(p.add_run("A point-in-time, experimentally governed study of debt-service capacity across Consumer Discretionary and Utilities issuers"), 13, color=BLUE)
    add_table(doc, ["Research design", "Coverage", "Decision use"], [["Expanding-window validation with locked holdout", "60 issuers | 3,150 company-quarters", "Analyst prioritization and surveillance"]], [3120, 3120, 3120])
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(90)
    font(p.add_run("Phase 1 publication report | Data snapshot 10 December 2024 | Prepared 5 August 2026"), 10, color=GRAY)
    doc.add_page_break()

    add_heading(doc, "Executive summary")
    add_body(doc, "Research objective. This study tests whether filing-aware public fundamentals and macroeconomic data can identify weakening debt-service capacity over the subsequent four fiscal quarters. The output is a ranked early-warning estimate for analyst triage; it is explicitly not a bankruptcy, default, valuation, or investment-recommendation model.", "Research objective.")
    add_body(doc, "Experimental design. A frozen universe of 60 currently listed U.S. issuers (30 per sector) was observed at company-fiscal-quarter frequency. SEC fundamentals were normalized across issuer calendars and XBRL concepts, macro variables were joined under historical-availability rules, and all model selection used expanding-window out-of-fold predictions with label-availability embargoes. A 2023+ period was held untouched until the champion specification was frozen.", "Experimental design.")
    add_body(doc, "Principal result. The gradient-boosted champion produced 0.397 PR-AUC, 0.563 recall, 0.333 precision, 1.966 top-decile lift, and 0.159 Brier score on 457 locked-holdout observations. Consumer Discretionary generalized better than Utilities (PR-AUC 0.468 versus 0.332), indicating economically meaningful sector heterogeneity and a need for expanded sector-specific validation.", "Principal result.")
    add_body(doc, "Portfolio finding. At the latest evaluated company snapshot, 22 of 60 firms were alerted, 6 were classified Severe, and mean estimated deterioration risk was 28.13%. Both sectors recorded 11 alerts, but Utilities displayed weaker median interest coverage (2.62x), negative median free-cash-flow margin (-16.39%), and higher debt-to-assets (38.18%) than Consumer Discretionary.", "Portfolio finding.")
    add_body(doc, "Research judgment. The evidence supports use as a transparent screening layer when alerts are paired with company history, forecast uncertainty, sector context, and human review. It does not support automated credit decisions or population-level default inference.", "Research judgment.")
    add_figure(doc, FIG / "risk_band_by_sector.png", "Figure 1. Latest evaluated risk-band distribution. Source: certified Power BI import workbook.")

    add_heading(doc, "1. Research question and experimental hypotheses")
    add_body(doc, "The primary question is whether observable changes in coverage, cash generation, leverage, peer-relative positioning, forecasted KPI trajectories, and macro conditions contain stable information about future debt-service deterioration. The unit of analysis is a filing-aware company-quarter decision point; the estimand is predictive ranking and calibrated early-warning performance, not a causal treatment effect.")
    add_table(doc, ["Hypothesis", "Empirical test", "Decision criterion"], [
        ["H1: multivariate signals improve ranking", "Compare prespecified feature increments by temporal OOF PR-AUC", "Improvement must persist across folds and sectors"],
        ["H2: forecasts add forward-looking information", "Add leakage-safe 1Q/4Q KPI forecasts after historical and peer features", "Incremental OOF value without holdout tuning"],
        ["H3: performance is regime- and sector-sensitive", "Report fold, sector, calibration, and final-holdout slices", "No pooled metric may conceal weak subgroups"],
    ], [1800, 4200, 3360])
    add_body(doc, "The study is observational and predictive. Consequently, feature importance is interpreted as conditional predictive association. It cannot establish that changing a balance-sheet variable would cause a corresponding change in deterioration risk.")

    add_heading(doc, "2. Data architecture and point-in-time research controls")
    add_body(doc, "Source selection. SEC EDGAR supplies public company fundamentals and filing dates; FRED/ALFRED supplies macroeconomic series. Public sources improve auditability and cost reproducibility, but introduce taxonomy heterogeneity, reporting lags, revisions, and limited distressed-firm coverage. Each acquisition is governed by a manifest with source parameters, retrieval time, checksum, and software version.")
    add_body(doc, "Panel construction. XBRL facts were mapped to economically consistent concepts, normalized to issuer fiscal quarters, and retained with filing/availability dates. This matters because a conventional calendar-quarter join can silently expose data before the market could have observed it. Decision keys preserve company, reporting period, and decision timestamp; the certified history contains 3,150 unique keys.")
    add_body(doc, "Universe controls. Eligibility required coverage of interest coverage, free-cash-flow margin, and debt-to-assets with continuity and denominator checks. Fourteen sampled firms were replaced under prespecified rules. This creates a cleaner experiment but induces survivorship and availability bias; those biases are disclosed rather than hidden in aggregate performance.")
    add_table(doc, ["Analytical layer", "Method choice", "Why the method fits financial data"], [
        ["Accounting normalization", "Concept mapping plus fiscal-period standardization", "Issuer taxonomies and fiscal calendars are nonuniform; economic definitions must be aligned before cross-sectional comparison."],
        ["Point-in-time join", "Availability-date/as-of logic", "Prevents look-ahead bias from late filings, revised macro series, and future labels."],
        ["Peer context", "Within-sector percentile ranks", "Financial ratios are structurally sector-dependent; peer ranks reduce misleading level comparisons."],
        ["Missingness", "Preserve legitimate nulls; fold-local preprocessing", "Zero imputation would manufacture economic states, while global preprocessing would leak future distribution information."],
    ], [1800, 2700, 4860])

    add_heading(doc, "3. Financial constructs, label design, and measurement validity")
    add_body(doc, "Interest coverage is the central debt-service construct because it compares operating earnings with interest burden. Free-cash-flow margin measures internally generated liquidity after investment needs. Debt-to-assets represents balance-sheet leverage and creditor claim intensity. The three measures are complementary: coverage captures service capacity, cash flow captures funding resilience, and leverage captures structural exposure.")
    add_body(doc, "The deterioration event is defined prospectively: future interest coverage must fall below 1.5x and decline at least 40% from the current level within the four-quarter horizon. The joint absolute-and-relative rule avoids labeling a small decline from an already strong level as severe while still recognizing economically consequential weakening. Adjacent quarterly horizons overlap, so observations are serially dependent and standard IID interpretations are inappropriate.")
    add_figure(doc, FIG / "sector_kpi_comparison.png", "Figure 2. Latest sector medians use separate axes because coverage is a multiple while margin and leverage are percentages.")

    add_heading(doc, "4. Forecasting methodology: matching model structure to temporal financial data")
    add_body(doc, "Why time-series methods are necessary. Quarterly fundamentals contain persistence, trend, seasonality-like fiscal effects, structural breaks, irregular volatility, and macro sensitivity. Random train/test splits would mix regimes and overstate generalization. Forecast models therefore use only information available before each origin and are evaluated at fixed 1Q and 4Q horizons.")
    add_table(doc, ["Method", "Financial rationale", "Role in the experiment"], [
        ["Random walk", "Many accounting ratios are persistent and difficult to beat out of sample.", "Mandatory naive benchmark; prevents complexity from receiving credit for persistence."],
        ["Drift", "Allows gradual balance-sheet or margin trajectories.", "Tests whether a simple secular trend adds value over the last observation."],
        ["Local level", "Treats the latent financial condition as evolving with measurement noise.", "Robust structural model for noisy quarterly ratios; prespecified source of forecast features."],
        ["Local linear trend", "Allows both level and slope to evolve.", "Appropriate when operating or leverage trajectories change gradually, but can be unstable in short histories."],
        ["Regression DLM", "Links latent KPI dynamics to macro covariates.", "Tests whether rates and business-cycle conditions improve forecasts without assuming static relationships."],
    ], [1700, 4000, 3660])
    add_body(doc, "Model selection emphasizes horizon-specific RMSE and interval coverage rather than in-sample fit. Prediction intervals are essential in financial analysis because a point forecast can imply false precision. Observed under-coverage for several four-quarter forecasts is retained as a limitation and argues for conformal or regime-adaptive intervals in Phase 2.")

    add_heading(doc, "5. Classification methodology and model governance")
    add_body(doc, "Regularized logistic regression provides a linear, directionally interpretable benchmark and controls coefficient instability under correlated ratios. Gradient-boosted trees capture nonlinear thresholds and interactions common in financial deterioration - for example, leverage may be tolerable when coverage and cash generation are strong but hazardous when both weaken. Tree depth, regularization, and feature increments are constrained to reduce variance and preserve auditability.")
    add_body(doc, "Feature increments were prespecified: historical fundamentals, peer-relative ranks, leakage-safe forecasts, macro variables, and limited sector interactions. Choosing the method at each increment is important: peer normalization addresses cross-sectional structure; time-series forecasts summarize trajectory; macro features represent common shocks; restricted interactions allow heterogeneous sensitivities without an uncontrolled search.")
    add_body(doc, "Class imbalance makes accuracy unsuitable. PR-AUC evaluates ranking quality for the positive class, recall measures event capture, precision measures analyst workload quality, top-decile lift measures concentration in the highest-priority queue, Brier score evaluates probabilistic accuracy, and calibration error tests whether numerical risks correspond to observed frequencies. No single metric is sufficient for a surveillance product.")

    add_heading(doc, "6. Temporal validation, leakage prevention, and champion selection")
    add_body(doc, "Three expanding-window folds simulate repeated deployment through time. Preprocessing, calibration, model fitting, and forecast generation are performed inside each fold. Label-availability embargoes exclude outcomes that would not yet be observable. Development probabilities shown in downstream products are out of fold; training-history rows with no defensible out-of-sample score remain explicitly unscored.")
    add_body(doc, "The champion was selected using development OOF PR-AUC first, then calibration, sector/time stability, interpretability, and simplicity. The final 2023+ holdout was evaluated exactly once after the champion record was frozen and hashed. The holdout alert-rate increase to 35.45% is treated as distribution shift, not an opportunity for retrospective threshold tuning.")
    add_figure(doc, FIG / "temporal_fold_stability.png", "Figure 3. Temporal OOF results expose regime sensitivity that a random split would conceal.")

    add_heading(doc, "7. Empirical results")
    add_table(doc, ["Locked-holdout slice", "N", "PR-AUC", "Recall", "Precision", "Lift", "Brier"], [
        [name, f"{int(row.observations):,}", f"{row.PR_AUC:.3f}", f"{row.recall:.3f}", f"{row.precision:.3f}", f"{row.top_decile_lift:.2f}x", f"{row.Brier_score:.3f}"]
        for name, row in hold.loc[["Overall", "Consumer Discretionary", "Utilities"]].iterrows()
    ], [2400, 700, 1100, 1100, 1200, 1100, 1760])
    add_body(doc, "The overall top-decile lift of 1.97x indicates useful concentration of deterioration events in the highest-risk queue. Recall of 56.3% implies that the model identifies more than half of events at the frozen threshold, while precision of 33.3% means approximately one in three alerts corresponds to an observed event under the study definition. This trade-off may be acceptable for low-cost analyst screening but not for automated adverse action.")
    add_body(doc, "The Utilities gap is material: PR-AUC and precision are lower even though Brier score is slightly better, demonstrating why discrimination and calibration must be evaluated separately. A model can produce numerically conservative probabilities while ranking positive cases imperfectly. Sector-specific recalibration, richer utility drivers, and broader samples are therefore Phase 2 priorities.")
    add_figure(doc, FIG / "holdout_sector_performance.png", "Figure 4. Locked-holdout sector results. Higher PR-AUC, recall, and precision are better.")

    add_heading(doc, "8. Latest portfolio surveillance results")
    add_body(doc, "The latest evaluated watchlist contains 60 unique issuers and reconciles to 22 alerts (36.67%), 6 Severe classifications, and a 28.13% mean risk estimate. Consumer Discretionary and Utilities each contribute 11 alerts, but the underlying economics differ: the Utilities median combines thinner coverage with negative free-cash-flow margin and higher leverage.")
    add_figure(doc, FIG / "top_risk_companies.png", "Figure 5. Highest latest risk estimates; company rankings are analytical screening outputs, not investment recommendations.")
    add_body(doc, "The highest risk names should be investigated through an analyst workflow: review filing recency, reconcile the source facts, inspect KPI and forecast paths, assess one-off accounting items, compare peers, and document whether the signal reflects operating deterioration, financing structure, capital expenditure, or model uncertainty. The risk reason is a diagnostic prompt rather than a causal explanation.")

    add_heading(doc, "9. Power BI analytical product and Stage 17 delivery")
    add_body(doc, "The Power BI package embeds four certified tables at distinct grains: a two-row sector portfolio table, a 60-row latest-company watchlist, 3,150 company-quarter history rows, and 93 model/fold/sector performance rows. The semantic model uses one-to-many sector and company relationships while leaving performance disconnected to avoid ambiguous cross-grain filtering.")
    add_body(doc, "The four-page architecture separates decision layers: Portfolio Overview for risk concentration, Analyst Watchlist for triage, Company Detail for temporal diagnostics, and Model Performance for governance. Percentages, ratios, and coverage multiples are intentionally separated; interest coverage and debt-to-assets are not placed on a shared raw axis. A visible disclaimer is required wherever risk estimates are summarized.")
    add_body(doc, "Artifact audit note. The PBIX opens as a valid package and contains the four named pages and embedded data model. The supplied authoring-canvas screenshots reconcile the headline KPIs, but they also show several unbound placeholder visuals. Those visual bindings require a future Power BI Desktop editing pass before the dashboard should be described as presentation-ready; the repository records this limitation explicitly.")

    add_heading(doc, "10. Limitations and threats to validity")
    for item in [
        "Survivorship and selection bias: the universe contains currently listed firms and excludes delisted/distressed histories, limiting inference about severe credit outcomes.",
        "External validity: two sectors and 60 firms cannot establish robustness across banks, industrials, healthcare, energy, or international accounting regimes.",
        "Outcome construction: the deterioration label is economically motivated but researcher-defined; alternative coverage thresholds or horizons may change event prevalence.",
        "Serial dependence: overlapping four-quarter labels and repeated issuers reduce the effective independent sample size and narrow the set of defensible statistical claims.",
        "Measurement error: XBRL tag diversity, restatements, fiscal-calendar irregularities, denominator sensitivity, and macro vintage proxies can affect features.",
        "Forecast uncertainty: several 4Q interval estimates under-cover, so downstream forecast features should not be treated as exact expected states.",
        "Distribution shift: the locked holdout alert rate and Utilities performance differ from development, indicating temporal and sector instability.",
        "Non-causality: importance and risk reasons describe predictive associations; they do not identify management actions that would cause risk to decline.",
        "Operational validation: no cost-sensitive threshold study, analyst-capacity simulation, prospective shadow deployment, or realized P&L/credit-loss backtest has yet been completed.",
        "Dashboard readiness: several supplied Power BI visuals remain unbound placeholders even though the package, model, pages, and headline reconciliation are valid.",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "11. Conclusions and practical interpretation")
    add_body(doc, "Phase 1 demonstrates that disciplined data engineering and experimental governance can turn free public financial data into a credible early-warning prototype. The strongest contribution is not a single algorithm; it is the alignment of financial constructs, point-in-time data, time-series forecasting, imbalance-aware classification metrics, temporal validation, and transparent release controls.")
    add_body(doc, "The model shows meaningful ranking value and economically interpretable portfolio signals, especially in Consumer Discretionary. At the same time, moderate precision, sector heterogeneity, forecast-interval under-coverage, and survivorship bias constrain deployment. The appropriate conclusion is controlled analyst augmentation: prioritize review, surface evidence, measure uncertainty, and preserve human judgment.")

    add_heading(doc, "12. Phase 2 research and product roadmap")
    add_table(doc, ["Priority", "Phase 2 goal", "Why it matters", "Acceptance evidence"], [
        ["1", "Expand to point-in-time listed and delisted histories across additional sectors", "Reduces survivorship bias and tests cross-sector transportability", "Frozen broader universe; sector/time holdouts; coverage audit"],
        ["2", "Prospective shadow scoring with drift monitoring", "Retrospective results do not prove live operational stability", "Scheduled scores; PSI/drift alerts; realized-outcome registry"],
        ["3", "Sector-aware and regime-aware calibration", "Utilities show weaker ranking/precision and higher calibration error", "Predeclared recalibration study with untouched evaluation windows"],
        ["4", "Probabilistic and conformal forecast intervals", "Current 4Q intervals under-cover and may overstate certainty", "Empirical coverage near nominal across KPI, sector, and horizon"],
        ["5", "Cost-sensitive threshold and analyst-capacity optimization", "Alert value depends on review cost, missed-event cost, and queue size", "Decision-curve analysis and capacity-constrained backtest"],
        ["6", "Explainability and analyst evidence packets", "Global feature importance is insufficient for individual review", "Local explanations tied to source facts, peer context, and uncertainty"],
        ["7", "Complete Power BI visual bindings and usability testing", "A valid model package is not yet a polished decision interface", "All required visuals populated; accessibility QA; analyst task testing"],
        ["8", "Benchmark modern survival, sequence, and panel methods", "Alternative methods may better model time-to-event and repeated-company structure", "Temporal comparisons versus current baselines with complexity penalties"],
    ], [700, 2850, 2980, 2830])
    add_body(doc, "Phase 2 should retain the Phase 1 governance principle: every increase in methodological sophistication must earn its place through leakage-safe out-of-time evidence, calibration, stability, interpretability, and operational utility. Deep or sequence models should not be adopted merely because they are modern; their data requirements and variance must be justified against transparent baselines.")

    doc.add_page_break()
    add_heading(doc, "Appendix A. Reproducibility and release evidence")
    add_table(doc, ["Control", "Phase 1 implementation"], [
        ["Environment", "Python 3.12 project with locked dependencies and deterministic commands"],
        ["Lineage", "SEC/FRED acquisition manifests, checksums, versioned configurations, and point-in-time policies"],
        ["Model governance", "OOF development predictions, fold-local transformations, frozen champion, one-time holdout"],
        ["Power BI reconciliation", "2 portfolio rows, 60 unique CIKs, 3,150 unique decision keys, 93 performance rows"],
        ["Release artifacts", "Certified XLSX, PBIX, four page screenshots, validation notes, source documentation, and tests"],
    ], [2600, 6760])
    add_body(doc, "Primary internal references: README.md; docs/point_in_time_policy.md; docs/label_specification.md; docs/model_card.md; docs/modeling_lineage.md; docs/stages_0_7_execution.md through docs/stages_17_18_execution.md; and the certified Power BI import workbook. External data originate from SEC EDGAR and FRED/ALFRED under their respective public usage policies.")
    add_body(doc, "Disclaimer. This report is an analytical portfolio project for research and demonstration. It is not investment advice, a credit rating, a bankruptcy/default model, or a substitute for audited financial statements and professional judgment.")

    path = OUT / "Corporate_Financial_Deterioration_Phase1_Research_Report.docx"
    doc.save(path)
    return path


if __name__ == "__main__":
    print(build())
