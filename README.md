# 👥 HR Analytics Dashboard

An interactive, cleaned and styled **Streamlit** report built on `HR_Analytics.xlsx`
(1,480 raw rows → **1,470 unique employees**, 38 → 46 columns after cleaning & feature engineering).

## Quick start

```bash
# 1. (optional) create a virtual environment, then install dependencies
pip install -r requirements.txt

# 2. launch the dashboard
streamlit run app.py
```

Or use the one-command launchers, which create a `.venv`, install requirements and start the app:

| OS | Command |
|----|---------|
| macOS / Linux | `./run_app.sh` |
| Windows | `run_app.bat` |

The app opens at <http://localhost:8501>. Requires **Python 3.9+**.

## What's inside the dashboard

| Tab | What you get |
|-----|--------------|
| 📊 **Overview** | 6 KPI cards, auto-generated key insights, attrition donut, attrition by department, headcount by role, age distribution |
| 🚪 **Attrition** | Attrition rate by any of 22 dimensions (dropdown), two-way hot-spot heat-map, attrition vs tenure curve, income of leavers vs stayers |
| 💰 **Compensation** | Pay by job level & gender, income by role, income vs experience, hike vs performance, attrition by salary slab and by *pay relative to peers* |
| 🧑‍🤝‍🧑 **Workforce** | Gender / marital / travel mix, age × gender, education, department × gender, drill-down org sunburst, tenure distribution |
| 😊 **Satisfaction** | Engagement heat-map (by dept / role / gender / age / marital), stayed-vs-left radar, attrition by score, training & promotion effects |
| 🎯 **Drivers & Risk** | Correlation with attrition, correlation matrix, rule-based risk score, factor "lift" table, **retention watch-list** (downloadable) |
| 🧹 **Data Quality & Export** | Cleaning log, outlier report, column profile, filtered data browser, CSV / Excel download |

**Global sidebar filters** (department, role, gender, marital status, travel, overtime, age group,
salary slab, age range, income range) update every chart and KPI instantly. You can also upload
another file with the same columns (`.xlsx` / `.csv`) and the dashboard re-cleans and re-renders it.

## Data cleaning performed

All steps live in `src/data_processing.py::clean_data` and are logged in the *Data Quality* tab.

| Issue found | Fix |
|-------------|-----|
| 7 exact duplicate rows | Removed |
| 3 repeated `EmpID`s (rows differed only in `YearsWithCurrManager`) | Kept first occurrence → each employee appears once |
| `BusinessTravel` had `TravelRarely` (8 rows) vs `Travel_Rarely` | Standardised; labels made readable |
| 57 missing `YearsWithCurrManager` | Imputed with the median for the same `YearsInCurrentRole` (corr ≈ 0.71); flagged in `MgrYearsImputed` |
| `YearsWithCurrManager` > `YearsAtCompany` (2 rows) | Capped at tenure |
| Constant columns `EmployeeCount`, `Over18`, `StandardHours`; redundant `EmployeeNumber` | Dropped |
| Logical consistency (tenure ≤ experience, age ≥ 18, income > 0 …) | Validated – 0 violations |
| Outliers (IQR rule) | Reported, **not** removed (plausible HR values) |

### Engineered columns

`AttritionFlag`, `TenureBand`, `ExperienceBand`, `DistanceBand`, `PromotionGap`, `EducationLevel`,
`AvgSatisfaction`, `IncomeVsLevelMedian`, `PayPosition`, `RiskFactorCount`, `RiskDrivers`, `MgrYearsImputed`.

### Risk score methodology

One point for each of: works overtime · job satisfaction ≤ 2 · work-life balance ≤ 2 ·
environment satisfaction ≤ 2 · no stock options · frequent business travel.
It is a transparent, rule-based heuristic (not a trained model); the dashboard shows the observed
attrition rate at each score so you can judge it for yourself.

## Project structure

```
hr_analytics_dashboard/
├── app.py                      # Streamlit app (UI, filters, all charts)
├── src/
│   ├── data_processing.py      # load → clean → engineer features (pure pandas, testable)
│   └── ui.py                   # theme, CSS, KPI cards, display helpers
├── data/
│   ├── HR_Analytics.xlsx       # original dataset
│   ├── HR_Analytics_cleaned.csv / .xlsx   # cleaned output
│   └── cleaning_log.csv        # step-by-step cleaning record
├── tests/test_data_processing.py   # unit tests for the cleaning pipeline
├── export_clean_data.py        # re-generate cleaned files without the UI
├── .streamlit/config.toml      # theme
├── requirements.txt            # runtime dependencies
├── requirements-dev.txt        # + pytest
├── run_app.sh / run_app.bat    # one-command launchers
└── README.md
```

## Useful commands

```bash
python export_clean_data.py        # regenerate data/HR_Analytics_cleaned.* and cleaning_log.csv
pip install -r requirements-dev.txt && pytest -q    # run unit tests
```

## Notes

* Monthly income and rates are shown in the source's own currency units (the dataset carries no currency).
* Segments with fewer than 30 employees are flagged – treat their percentages with caution.
* Correlation and risk-factor results describe association, not causation.
"# HRanalytics" 
"# HRanalytics" 
