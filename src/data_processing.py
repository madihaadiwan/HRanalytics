"""Data loading, cleaning and feature engineering for the HR Analytics dashboard.

All logic here is plain pandas/numpy (no Streamlit), so it can be unit-tested and
re-used from scripts or notebooks.

Main entry points
-----------------
load_raw(...)       -> raw DataFrame from the bundled workbook or an uploaded file
clean_data(raw)     -> (clean_df, cleaning_log_df, summary_dict)
outlier_summary(df) -> IQR-based outlier report for numeric columns
column_profile(df)  -> per-column dtype / missing / unique / range profile
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "HR_Analytics.xlsx"

EXPECTED_COLUMNS = [
    "EmpID", "Age", "AgeGroup", "Attrition", "BusinessTravel", "DailyRate",
    "Department", "DistanceFromHome", "Education", "EducationField",
    "EmployeeCount", "EmployeeNumber", "EnvironmentSatisfaction", "Gender",
    "HourlyRate", "JobInvolvement", "JobLevel", "JobRole", "JobSatisfaction",
    "MaritalStatus", "MonthlyIncome", "SalarySlab", "MonthlyRate",
    "NumCompaniesWorked", "Over18", "OverTime", "PercentSalaryHike",
    "PerformanceRating", "RelationshipSatisfaction", "StandardHours",
    "StockOptionLevel", "TotalWorkingYears", "TrainingTimesLastYear",
    "WorkLifeBalance", "YearsAtCompany", "YearsInCurrentRole",
    "YearsSinceLastPromotion", "YearsWithCurrManager",
]

CONSTANT_COLUMNS = ["EmployeeCount", "Over18", "StandardHours"]
REDUNDANT_COLUMNS = ["EmployeeNumber"]  # duplicates EmpID as an identifier

SATISFACTION_COLS = [
    "EnvironmentSatisfaction", "JobSatisfaction",
    "RelationshipSatisfaction", "WorkLifeBalance",
]

EDUCATION_LABELS = {1: "Below College", 2: "College", 3: "Bachelor", 4: "Master", 5: "Doctor"}
SCORE_LABELS = {1: "1 - Low", 2: "2 - Medium", 3: "3 - High", 4: "4 - Very High"}
WLB_LABELS = {1: "1 - Bad", 2: "2 - Good", 3: "3 - Better", 4: "4 - Best"}
PERFORMANCE_LABELS = {3: "3 - Excellent", 4: "4 - Outstanding"}

BUSINESS_TRAVEL_MAP = {
    "nontravel": "Non-Travel",
    "travelrarely": "Travel Rarely",
    "travelfrequently": "Travel Frequently",
}

# Rule-based attrition risk factors (documented in the README / Drivers tab)
RISK_FACTORS = {
    "Works overtime": "OverTime = Yes",
    "Low job satisfaction": "JobSatisfaction <= 2",
    "Low work-life balance": "WorkLifeBalance <= 2",
    "Low environment satisfaction": "EnvironmentSatisfaction <= 2",
    "No stock options": "StockOptionLevel = 0",
    "Frequent business travel": "BusinessTravel = Travel Frequently",
}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_raw(source: bytes | None = None, filename: str | None = None) -> pd.DataFrame:
    """Load the raw dataset.

    Parameters
    ----------
    source   : bytes of an uploaded file, or ``None`` to use the bundled workbook.
    filename : original filename of the upload (used to detect CSV vs Excel).
    """
    if source is None:
        return pd.read_excel(DEFAULT_DATA_PATH)
    buffer = io.BytesIO(source)
    if filename and filename.lower().endswith(".csv"):
        return pd.read_csv(buffer)
    return pd.read_excel(buffer)


def validate_schema(raw: pd.DataFrame) -> None:
    """Raise a helpful ValueError if required columns are missing."""
    missing = [c for c in EXPECTED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(
            "The dataset is missing required column(s): " + ", ".join(missing)
        )


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Clean the raw HR dataset and engineer analysis features.

    Returns
    -------
    df       : cleaned + enriched DataFrame
    log      : DataFrame documenting every cleaning step (Step / Action / Affected)
    summary  : dict of headline numbers about the cleaning process
    """
    validate_schema(raw)
    log: list[dict] = []

    def add(step: str, action: str, affected: int | str = 0) -> None:
        log.append({"Step": step, "Action": action, "Affected": affected})

    df = raw.copy()
    raw_rows, raw_cols = df.shape
    cols_before = set(df.columns)

    # 1 ── Whitespace in text columns ------------------------------------------------
    text_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    trimmed = 0
    for c in text_cols:
        mask = df[c].notna()
        original = df.loc[mask, c].astype(str)
        stripped = original.str.strip()
        trimmed += int((original != stripped).sum())
        df.loc[mask, c] = stripped
    add("Text hygiene", "Trimmed leading/trailing whitespace in text columns", trimmed)

    # 2 ── Inconsistent category spelling (BusinessTravel) ----------------------------
    standard_raw = {"Non-Travel", "Travel_Rarely", "Travel_Frequently"}
    inconsistent = int((~df["BusinessTravel"].isin(standard_raw)).sum())
    key = (
        df["BusinessTravel"].astype(str).str.lower()
        .str.replace(r"[\s_\-]", "", regex=True)
    )
    df["BusinessTravel"] = key.map(BUSINESS_TRAVEL_MAP).fillna(df["BusinessTravel"])
    add(
        "Standardise categories",
        "BusinessTravel: merged 'TravelRarely' into 'Travel_Rarely' and relabelled to "
        "'Non-Travel' / 'Travel Rarely' / 'Travel Frequently'",
        inconsistent,
    )

    # 3 ── Duplicates -----------------------------------------------------------------
    full_dups = int(df.duplicated().sum())
    df = df.drop_duplicates()
    add("Remove duplicates", "Dropped exact duplicate rows (all columns identical)", full_dups)

    id_dups = int(df.duplicated(subset="EmpID").sum())
    df = df.drop_duplicates(subset="EmpID", keep="first")
    add(
        "Remove duplicates",
        "Dropped repeated EmpIDs whose rows differed only in YearsWithCurrManager "
        "(kept the first occurrence so each employee appears once)",
        id_dups,
    )

    # 4 ── Invalid target values ------------------------------------------------------
    bad_target = int((~df["Attrition"].isin(["Yes", "No"])).sum())
    if bad_target:
        df = df[df["Attrition"].isin(["Yes", "No"])]
    add("Validate target", "Rows where Attrition is not Yes/No removed", bad_target)

    # 5 ── Missing values: YearsWithCurrManager --------------------------------------
    missing_mask = df["YearsWithCurrManager"].isna()
    n_missing = int(missing_mask.sum())
    df["MgrYearsImputed"] = missing_mask
    group_median = df.groupby("YearsInCurrentRole")["YearsWithCurrManager"].transform("median")
    fill_values = group_median.fillna(df["YearsWithCurrManager"].median())
    df.loc[missing_mask, "YearsWithCurrManager"] = fill_values[missing_mask]
    add(
        "Impute missing",
        "YearsWithCurrManager: filled with the median for the same YearsInCurrentRole "
        "(correlation ≈ 0.71); flagged in column MgrYearsImputed",
        n_missing,
    )

    over_cap = int((df["YearsWithCurrManager"] > df["YearsAtCompany"]).sum())
    df["YearsWithCurrManager"] = np.minimum(df["YearsWithCurrManager"], df["YearsAtCompany"])
    df["YearsWithCurrManager"] = df["YearsWithCurrManager"].round().astype(int)
    add(
        "Fix logical errors",
        "YearsWithCurrManager capped at YearsAtCompany (cannot exceed tenure)",
        over_cap,
    )

    # 6 ── Logical validation (flag only – values are plausible, never silently edited) ─
    checks = {
        "YearsAtCompany > TotalWorkingYears": (df["YearsAtCompany"] > df["TotalWorkingYears"]).sum(),
        "YearsInCurrentRole > YearsAtCompany": (df["YearsInCurrentRole"] > df["YearsAtCompany"]).sum(),
        "YearsSinceLastPromotion > YearsAtCompany": (df["YearsSinceLastPromotion"] > df["YearsAtCompany"]).sum(),
        "Age < 18": (df["Age"] < 18).sum(),
        "MonthlyIncome <= 0": (df["MonthlyIncome"] <= 0).sum(),
    }
    add(
        "Validate logic",
        "Consistency checks → " + "; ".join(f"{k}: {int(v)}" for k, v in checks.items()),
        int(sum(checks.values())),
    )

    # 7 ── Drop non-informative columns ----------------------------------------------
    to_drop = [c for c in CONSTANT_COLUMNS + REDUNDANT_COLUMNS if c in df.columns]
    df = df.drop(columns=to_drop)
    add(
        "Drop columns",
        "Removed constant columns (EmployeeCount, Over18, StandardHours) and the redundant "
        "identifier EmployeeNumber",
        len(to_drop),
    )

    # 8 ── Feature engineering --------------------------------------------------------
    df["AttritionFlag"] = (df["Attrition"] == "Yes").astype(int)

    df["AgeGroup"] = pd.cut(
        df["Age"], bins=[17, 25, 35, 45, 55, 120],
        labels=["18-25", "26-35", "36-45", "46-55", "55+"],
    )
    df["SalarySlab"] = pd.Categorical(
        df["SalarySlab"], categories=["Upto 5k", "5k-10k", "10k-15k", "15k+"], ordered=True
    )
    df["TenureBand"] = pd.cut(
        df["YearsAtCompany"], bins=[-1, 1, 5, 10, 20, 100],
        labels=["0-1 yrs", "2-5 yrs", "6-10 yrs", "11-20 yrs", "20+ yrs"],
    )
    df["ExperienceBand"] = pd.cut(
        df["TotalWorkingYears"], bins=[-1, 2, 5, 10, 20, 100],
        labels=["0-2 yrs", "3-5 yrs", "6-10 yrs", "11-20 yrs", "20+ yrs"],
    )
    df["DistanceBand"] = pd.cut(
        df["DistanceFromHome"], bins=[0, 5, 15, 1000],
        labels=["Near (1-5)", "Medium (6-15)", "Far (16+)"],
    )
    df["PromotionGap"] = pd.cut(
        df["YearsSinceLastPromotion"], bins=[-1, 1, 3, 7, 100],
        labels=["0-1 yrs", "2-3 yrs", "4-7 yrs", "8+ yrs"],
    )
    df["EducationLevel"] = pd.Categorical(
        df["Education"].map(EDUCATION_LABELS),
        categories=list(EDUCATION_LABELS.values()), ordered=True,
    )
    df["AvgSatisfaction"] = df[SATISFACTION_COLS].mean(axis=1).round(2)

    level_median = df.groupby("JobLevel")["MonthlyIncome"].transform("median")
    df["IncomeVsLevelMedian"] = (df["MonthlyIncome"] / level_median).round(2)
    df["PayPosition"] = pd.cut(
        df["IncomeVsLevelMedian"], bins=[0, 0.8, 1.2, np.inf], right=False,
        labels=["Below peers (<80%)", "In line (80-120%)", "Above peers (>120%)"],
    )

    risk = pd.DataFrame({
        "Works overtime": df["OverTime"].eq("Yes"),
        "Low job satisfaction": df["JobSatisfaction"] <= 2,
        "Low work-life balance": df["WorkLifeBalance"] <= 2,
        "Low environment satisfaction": df["EnvironmentSatisfaction"] <= 2,
        "No stock options": df["StockOptionLevel"] == 0,
        "Frequent business travel": df["BusinessTravel"].eq("Travel Frequently"),
    })
    df["RiskFactorCount"] = risk.sum(axis=1).astype(int)
    names = np.array(risk.columns)
    df["RiskDrivers"] = [", ".join(names[row]) for row in risk.to_numpy()]

    engineered = [
        "AttritionFlag", "TenureBand", "ExperienceBand", "DistanceBand", "PromotionGap",
        "EducationLevel", "AvgSatisfaction", "IncomeVsLevelMedian", "PayPosition",
        "RiskFactorCount", "RiskDrivers", "MgrYearsImputed",
    ]
    add(
        "Feature engineering",
        "Added analysis columns: " + ", ".join(engineered)
        + "; rebuilt AgeGroup from Age and made SalarySlab an ordered category",
        len(engineered),
    )

    df = df.reset_index(drop=True)
    add("Result", f"Clean dataset: {len(df):,} rows × {df.shape[1]} columns", len(df))

    summary = {
        "raw_rows": raw_rows,
        "raw_cols": raw_cols,
        "clean_rows": len(df),
        "clean_cols": df.shape[1],
        "full_duplicates": full_dups,
        "id_duplicates": id_dups,
        "missing_imputed": n_missing,
        "label_fixes": inconsistent,
        "columns_dropped": to_drop,
        "columns_added": [c for c in df.columns if c not in cols_before],
    }
    return df, pd.DataFrame(log), summary


# --------------------------------------------------------------------------- #
# Profiling helpers
# --------------------------------------------------------------------------- #
def outlier_summary(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """IQR (1.5×) outlier report. Outliers are reported, not removed – they are
    plausible HR values (e.g. long-tenured staff, high earners)."""
    columns = columns or [
        "Age", "MonthlyIncome", "TotalWorkingYears", "YearsAtCompany",
        "YearsInCurrentRole", "YearsSinceLastPromotion", "NumCompaniesWorked",
        "DistanceFromHome", "TrainingTimesLastYear", "PercentSalaryHike",
    ]
    rows = []
    for c in columns:
        s = df[c]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        rows.append({
            "Column": c, "Lower fence": round(lo, 1), "Upper fence": round(hi, 1),
            "Outliers": n_out, "% of rows": round(n_out / len(s) * 100, 1),
            "Max": s.max(),
        })
    return pd.DataFrame(rows).sort_values("Outliers", ascending=False).reset_index(drop=True)


def column_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Compact per-column profile used on the Data Quality tab."""
    rows = []
    for c in df.columns:
        s = df[c]
        numeric = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        rows.append({
            "Column": c,
            "Type": str(s.dtype),
            "Missing": int(s.isna().sum()),
            "Unique": int(s.nunique()),
            "Min": s.min() if numeric else "",
            "Max": s.max() if numeric else "",
            "Mean": round(float(s.mean()), 2) if numeric else "",
        })
    out = pd.DataFrame(rows)
    # mixed-type object columns break Arrow serialisation in Streamlit → store as text
    for c in ["Min", "Max", "Mean"]:
        out[c] = out[c].astype(str)
    return out
