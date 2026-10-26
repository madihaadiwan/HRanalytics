"""Run the cleaning pipeline without the dashboard and save the results.

Usage:  python export_clean_data.py
Output: data/HR_Analytics_cleaned.csv, data/HR_Analytics_cleaned.xlsx, data/cleaning_log.csv
"""
from pathlib import Path

from src.data_processing import clean_data, load_raw

OUT = Path(__file__).parent / "data"

if __name__ == "__main__":
    df, log, summary = clean_data(load_raw())
    df.to_csv(OUT / "HR_Analytics_cleaned.csv", index=False)
    df.to_excel(OUT / "HR_Analytics_cleaned.xlsx", index=False, sheet_name="HR_Clean")
    log.to_csv(OUT / "cleaning_log.csv", index=False)
    print(log.to_string(index=False))
    print(f"\nSaved {len(df):,} rows x {df.shape[1]} columns to {OUT}")
