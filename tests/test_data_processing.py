"""Unit tests for the cleaning pipeline.  Run with:  pytest -q"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_processing import (  # noqa: E402
    RISK_FACTORS, clean_data, column_profile, load_raw, outlier_summary, validate_schema,
)


@pytest.fixture(scope="module")
def cleaned():
    raw = load_raw()
    df, log, summary = clean_data(raw)
    return raw, df, log, summary


def test_duplicates_removed(cleaned):
    raw, df, _, summary = cleaned
    assert df["EmpID"].is_unique
    assert summary["full_duplicates"] + summary["id_duplicates"] == len(raw) - len(df)
    assert len(df) == 1470


def test_no_missing_values(cleaned):
    _, df, _, _ = cleaned
    assert df.isna().sum().sum() == 0


def test_business_travel_standardised(cleaned):
    _, df, _, _ = cleaned
    assert set(df["BusinessTravel"]) == {"Non-Travel", "Travel Rarely", "Travel Frequently"}


def test_non_informative_columns_dropped(cleaned):
    _, df, _, _ = cleaned
    for col in ["EmployeeCount", "Over18", "StandardHours", "EmployeeNumber"]:
        assert col not in df.columns


def test_manager_years_logic(cleaned):
    _, df, _, summary = cleaned
    assert (df["YearsWithCurrManager"] <= df["YearsAtCompany"]).all()
    assert df["MgrYearsImputed"].sum() == summary["missing_imputed"] == 57
    assert pd.api.types.is_integer_dtype(df["YearsWithCurrManager"])


def test_attrition_flag_matches_label(cleaned):
    _, df, _, _ = cleaned
    assert (df["AttritionFlag"] == (df["Attrition"] == "Yes").astype(int)).all()


def test_age_group_matches_age(cleaned):
    _, df, _, _ = cleaned
    bounds = {"18-25": (18, 25), "26-35": (26, 35), "36-45": (36, 45), "46-55": (46, 55), "55+": (56, 200)}
    for grp, (lo, hi) in bounds.items():
        ages = df.loc[df["AgeGroup"] == grp, "Age"]
        assert ages.between(lo, hi).all()


def test_engineered_features_valid(cleaned):
    _, df, _, _ = cleaned
    assert df["RiskFactorCount"].between(0, len(RISK_FACTORS)).all()
    assert df["AvgSatisfaction"].between(1, 4).all()
    assert df["TenureBand"].notna().all() and df["PayPosition"].notna().all()


def test_log_and_profiles(cleaned):
    _, df, log, _ = cleaned
    assert {"Step", "Action", "Affected"} <= set(log.columns)
    assert len(column_profile(df)) == df.shape[1]
    assert outlier_summary(df)["Outliers"].ge(0).all()


def test_schema_validation_message():
    with pytest.raises(ValueError, match="missing required column"):
        validate_schema(pd.DataFrame({"EmpID": [1]}))
