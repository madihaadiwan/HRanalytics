"""HR Analytics Dashboard – interactive Streamlit report.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_processing import (
    PERFORMANCE_LABELS,
    RISK_FACTORS,
    clean_data,
    column_profile,
    load_raw,
    outlier_summary,
)
from src.ui import (
    AMBER, ATTRITION_COLORS, GENDER_COLORS, PRIMARY, ROSE, SEQUENCE, SKY, SLATE, TEAL, VIOLET,
    hero, inject_css, insight, kpi, reset_chart_keys, section, show_chart, show_table,
)

st.set_page_config(
    page_title="HR Analytics Dashboard",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
reset_chart_keys()

# --------------------------------------------------------------------------- #
# Data loading (cached)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading and cleaning data…")
def get_data(file_bytes: bytes | None, filename: str | None):
    return clean_data(load_raw(file_bytes, filename))


@st.cache_data(show_spinner=False)
def to_excel_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="HR_Clean")
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Sidebar – data source + global filters
# --------------------------------------------------------------------------- #
st.sidebar.markdown("## 👥 HR Analytics")
upload = st.sidebar.file_uploader(
    "Optional: analyse your own file (same columns as the sample)", type=["xlsx", "csv"]
)
try:
    df_all, cleaning_log, summary = get_data(
        upload.getvalue() if upload else None, upload.name if upload else None
    )
except Exception as exc:  # noqa: BLE001 – show friendly message in the UI
    st.error(f"Could not load the dataset: {exc}")
    st.stop()

SIG = upload.name if upload else "default"
# Widget keys carry a version counter: "Reset" bumps it, which recreates every
# widget at its default (avoids writing to widget state directly).
VER = st.session_state.setdefault("filter_version", 0)
KEY = f"{SIG}_{VER}"


def options_for(frame: pd.DataFrame, col: str) -> list:
    present = set(frame[col].dropna().unique())
    if isinstance(frame[col].dtype, pd.CategoricalDtype):
        return [c for c in frame[col].cat.categories if c in present]
    return sorted(present)


FILTERS = {
    "Department": "Department",
    "JobRole": "Job role",
    "Gender": "Gender",
    "MaritalStatus": "Marital status",
    "BusinessTravel": "Business travel",
    "OverTime": "Overtime",
    "AgeGroup": "Age group",
    "SalarySlab": "Salary slab",
}
OPTIONS = {c: options_for(df_all, c) for c in FILTERS}
AGE_RANGE = (int(df_all["Age"].min()), int(df_all["Age"].max()))
INC_RANGE = (int(df_all["MonthlyIncome"].min()), int(df_all["MonthlyIncome"].max()))


def reset_filters() -> None:
    st.session_state["filter_version"] += 1


st.sidebar.markdown("### 🔎 Filters")
st.sidebar.button("↺ Reset all filters", on_click=reset_filters, key=f"reset_{KEY}")

selected: dict[str, list] = {}
for col in ["Department", "JobRole", "Gender"]:
    selected[col] = st.sidebar.multiselect(
        FILTERS[col], OPTIONS[col], default=OPTIONS[col], key=f"f_{col}_{KEY}"
    )
with st.sidebar.expander("More filters"):
    for col in ["MaritalStatus", "BusinessTravel", "OverTime", "AgeGroup", "SalarySlab"]:
        selected[col] = st.multiselect(
            FILTERS[col], OPTIONS[col], default=OPTIONS[col], key=f"f_{col}_{KEY}"
        )
age_sel = st.sidebar.slider("Age", AGE_RANGE[0], AGE_RANGE[1], AGE_RANGE, key=f"f_age_{KEY}")
inc_sel = st.sidebar.slider(
    "Monthly income", INC_RANGE[0], INC_RANGE[1], INC_RANGE, step=100, key=f"f_inc_{KEY}"
)

mask = df_all["Age"].between(*age_sel) & df_all["MonthlyIncome"].between(*inc_sel)
for col, values in selected.items():
    mask &= df_all[col].isin(values)
df = df_all[mask].copy()

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Showing {len(df):,} of {len(df_all):,} employees**")
st.sidebar.caption(
    f"Data cleaned from {summary['raw_rows']:,} raw rows. See the **Data Quality** tab for details."
)

# --------------------------------------------------------------------------- #
# Header + empty-state guard
# --------------------------------------------------------------------------- #
hero(
    "HR Analytics Dashboard",
    "Workforce composition, attrition, compensation and engagement – filter on the left, "
    "explore in the tabs below.",
)
if df.empty:
    st.warning("No employees match the current filters. Widen your selection or reset the filters.")
    st.stop()
if len(df) < 30:
    st.info("Fewer than 30 employees selected – percentages may be volatile.")

OVERALL_RATE = df["AttritionFlag"].mean() * 100


# --------------------------------------------------------------------------- #
# Reusable chart helpers
# --------------------------------------------------------------------------- #
def attr_by(frame: pd.DataFrame, col: str) -> pd.DataFrame:
    g = (
        frame.groupby(col, observed=True)["AttritionFlag"]
        .agg(Employees="size", Left="sum")
        .reset_index()
    )
    g["AttritionRate"] = (g["Left"] / g["Employees"] * 100).round(1)
    return g


def rate_bar(frame: pd.DataFrame, col: str, title: str, label: str | None = None):
    """Attrition-rate bar chart for any dimension, with company-average reference line."""
    g = attr_by(frame, col)
    overall = frame["AttritionFlag"].mean() * 100
    ordered = isinstance(frame[col].dtype, pd.CategoricalDtype) or pd.api.types.is_numeric_dtype(frame[col])
    horizontal = (not ordered) and len(g) > 5
    g["Group"] = g[col].astype(str)
    g["Label"] = g["AttritionRate"].map(lambda v: f"{v:.1f}%")
    hover = {"Employees": True, "Left": True, "AttritionRate": ":.1f", "Group": False, "Label": False}
    scale = [TEAL, AMBER, ROSE]
    rng = [0, max(40, float(g["AttritionRate"].max()))]
    if horizontal:
        fig = px.bar(
            g, x="AttritionRate", y="Group", orientation="h", text="Label", color="AttritionRate",
            color_continuous_scale=scale, range_color=rng, hover_data=hover, title=title,
        )
        fig.update_yaxes(categoryorder="total ascending", title=label or col)
        fig.update_xaxes(title="Attrition rate (%)")
        fig.add_vline(x=overall, line_dash="dash", line_color=SLATE,
                      annotation_text=f"Avg {overall:.1f}%", annotation_position="top")
    else:
        fig = px.bar(
            g, x="Group", y="AttritionRate", text="Label", color="AttritionRate",
            color_continuous_scale=scale, range_color=rng, hover_data=hover, title=title,
        )
        fig.update_xaxes(type="category", title=label or col)
        fig.update_yaxes(title="Attrition rate (%)")
        fig.add_hline(y=overall, line_dash="dash", line_color=SLATE,
                      annotation_text=f"Avg {overall:.1f}%", annotation_position="top left")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_coloraxes(showscale=False)
    return fig


def donut(frame: pd.DataFrame, col: str, title: str, colors: dict | None = None, center: str = ""):
    counts = frame[col].value_counts().rename_axis(col).reset_index(name="Employees")
    fig = px.pie(
        counts, names=col, values="Employees", hole=0.58, color=col, title=title,
        color_discrete_map=colors, color_discrete_sequence=SEQUENCE,
    )
    fig.update_traces(textinfo="percent+label", textposition="outside")
    fig.update_layout(showlegend=False)
    if center:
        fig.add_annotation(text=center, x=0.5, y=0.5, xref="paper", yref="paper",
                           showarrow=False, font=dict(size=26, color="#0F172A"))
    return fig


def pct(n: float, d: float) -> float:
    return n / d * 100 if d else 0.0


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tabs = st.tabs([
    "📊 Overview", "🚪 Attrition", "💰 Compensation", "🧑‍🤝‍🧑 Workforce",
    "😊 Satisfaction", "🎯 Drivers & Risk", "🧹 Data Quality & Export",
])

# ============================== 1. OVERVIEW ================================= #
with tabs[0]:
    left_n = int(df["AttritionFlag"].sum())
    cols = st.columns(6)
    with cols[0]:
        kpi("Headcount", f"{len(df):,}", f"{df['Department'].nunique()} departments", PRIMARY)
    with cols[1]:
        kpi("Attrition rate", f"{OVERALL_RATE:.1f}%", f"{left_n:,} employees left", ROSE, "bad")
    with cols[2]:
        kpi("Avg monthly income", f"{df['MonthlyIncome'].mean():,.0f}",
            f"Median {df['MonthlyIncome'].median():,.0f}", TEAL)
    with cols[3]:
        kpi("Avg tenure", f"{df['YearsAtCompany'].mean():.1f} yrs",
            f"Avg age {df['Age'].mean():.1f}", AMBER)
    with cols[4]:
        ot = pct((df["OverTime"] == "Yes").sum(), len(df))
        kpi("Working overtime", f"{ot:.1f}%", "of employees", SKY)
    with cols[5]:
        kpi("Avg satisfaction", f"{df['AvgSatisfaction'].mean():.2f} / 4",
            "env · job · relationship · WLB", VIOLET)

    section("Key insights", "Auto-generated from the currently filtered data.")
    stayed = df[df["AttritionFlag"] == 0]
    leavers = df[df["AttritionFlag"] == 1]

    roles = attr_by(df, "JobRole")
    roles = roles[roles["Employees"] >= 20]
    if len(roles) and left_n:
        top = roles.sort_values("AttritionRate", ascending=False).iloc[0]
        mult = top["AttritionRate"] / OVERALL_RATE if OVERALL_RATE else 0
        insight(f"<b>{top['JobRole']}</b> has the highest attrition at <b>{top['AttritionRate']:.1f}%</b> "
                f"({mult:.1f}× the company average of {OVERALL_RATE:.1f}%).")

    ot_rates = attr_by(df, "OverTime").set_index("OverTime")["AttritionRate"]
    if {"Yes", "No"} <= set(ot_rates.index) and ot_rates["No"] > 0:
        insight(f"Employees working overtime leave at <b>{ot_rates['Yes']:.1f}%</b> versus "
                f"<b>{ot_rates['No']:.1f}%</b> for those who don't "
                f"(<b>{ot_rates['Yes'] / ot_rates['No']:.1f}×</b> higher).")

    if left_n:
        early = pct((leavers["YearsAtCompany"] <= 2).sum(), left_n)
        insight(f"<b>{early:.0f}%</b> of leavers had two years or less at the company – "
                "early-tenure retention is the biggest lever.")

    slabs = attr_by(df, "SalarySlab")
    if len(slabs) > 1:
        lo, hi = slabs.iloc[0], slabs.iloc[-1]
        insight(f"Attrition falls from <b>{lo['AttritionRate']:.1f}%</b> in the <i>{lo['SalarySlab']}</i> "
                f"salary slab to <b>{hi['AttritionRate']:.1f}%</b> in the <i>{hi['SalarySlab']}</i> slab.")

    c1, c2 = st.columns([1, 1.4])
    with c1:
        status = df.assign(Status=df["Attrition"].map({"Yes": "Left", "No": "Stayed"}))
        show_chart(donut(status, "Status", "Attrition split",
                         {"Stayed": TEAL, "Left": ROSE}, f"{OVERALL_RATE:.1f}%"))
    with c2:
        show_chart(rate_bar(df, "Department", "Attrition rate by department", "Department"))

    c3, c4 = st.columns(2)
    with c3:
        role = df.groupby(["JobRole", "Attrition"], observed=True).size().reset_index(name="Employees")
        fig = px.bar(role, y="JobRole", x="Employees", color="Attrition", orientation="h",
                     color_discrete_map=ATTRITION_COLORS, title="Headcount by job role (stayed vs left)")
        fig.update_yaxes(categoryorder="total ascending", title="")
        show_chart(fig)
    with c4:
        fig = px.histogram(df, x="Age", color="Attrition", nbins=24, barmode="overlay", opacity=0.75,
                           color_discrete_map=ATTRITION_COLORS, title="Age distribution")
        fig.update_yaxes(title="Employees")
        show_chart(fig)

# ============================== 2. ATTRITION ================================ #
with tabs[1]:
    DIMENSIONS = {
        "Department": "Department", "Job role": "JobRole", "Gender": "Gender",
        "Marital status": "MaritalStatus", "Business travel": "BusinessTravel",
        "Overtime": "OverTime", "Education field": "EducationField",
        "Education level": "EducationLevel", "Age group": "AgeGroup",
        "Salary slab": "SalarySlab", "Tenure band": "TenureBand",
        "Total experience": "ExperienceBand", "Commute distance": "DistanceBand",
        "Years since promotion": "PromotionGap", "Job level": "JobLevel",
        "Stock option level": "StockOptionLevel", "Pay vs peers": "PayPosition",
        "Training times last year": "TrainingTimesLastYear",
        "Job satisfaction": "JobSatisfaction", "Work-life balance": "WorkLifeBalance",
        "Environment satisfaction": "EnvironmentSatisfaction",
        "Risk-factor count": "RiskFactorCount",
    }
    section("Attrition by segment", "Pick any dimension – the dashed line is the company average.")
    dim_label = st.selectbox("Break attrition down by", list(DIMENSIONS), index=1, key="attr_dim")
    dim_col = DIMENSIONS[dim_label]
    c1, c2 = st.columns([1.6, 1])
    with c1:
        show_chart(rate_bar(df, dim_col, f"Attrition rate by {dim_label.lower()}", dim_label))
    with c2:
        tbl = attr_by(df, dim_col).rename(columns={
            dim_col: dim_label, "Left": "Left", "AttritionRate": "Attrition %"})
        show_table(tbl.sort_values("Attrition %", ascending=False))
        st.caption("⚠️ Segments with fewer than 30 employees should be read with caution.")

    section("Two-way hot-spot map", "Where do the two dimensions combine to create the highest attrition?")
    h1, h2 = st.columns(2)
    row_label = h1.selectbox("Rows", list(DIMENSIONS), index=1, key="hm_row")
    col_label = h2.selectbox("Columns", list(DIMENSIONS), index=5, key="hm_col")
    if row_label == col_label:
        st.info("Choose two different dimensions to build the heat-map.")
    else:
        pivot = df.pivot_table(index=DIMENSIONS[row_label], columns=DIMENSIONS[col_label],
                               values="AttritionFlag", aggfunc="mean", observed=True) * 100
        fig = px.imshow(pivot.round(1), text_auto=".1f", aspect="auto",
                        color_continuous_scale=[TEAL, "#FEF3C7", ROSE],
                        labels=dict(color="Attrition %", x=col_label, y=row_label),
                        title=f"Attrition % – {row_label} × {col_label}")
        fig.update_layout(height=max(360, 45 * len(pivot) + 160))
        show_chart(fig)

    c3, c4 = st.columns(2)
    with c3:
        t = df.assign(Years=df["YearsAtCompany"].clip(upper=20))
        g = attr_by(t, "Years")
        fig = px.line(g, x="Years", y="AttritionRate", markers=True, hover_data=["Employees", "Left"],
                      title="Attrition by years at company (20 = 20+ years)")
        fig.update_traces(line_color=ROSE)
        fig.update_yaxes(title="Attrition rate (%)")
        fig.update_xaxes(title="Years at company")
        show_chart(fig)
    with c4:
        fig = px.box(df, x="Attrition", y="MonthlyIncome", color="Attrition", points=False,
                     color_discrete_map=ATTRITION_COLORS, title="Monthly income: stayed vs left")
        fig.update_layout(showlegend=False)
        show_chart(fig)

# ============================== 3. COMPENSATION ============================= #
with tabs[2]:
    med = df.groupby("Gender")["MonthlyIncome"].median()
    ratio = (med["Female"] / med["Male"] * 100) if {"Female", "Male"} <= set(med.index) else None
    below = pct((df["PayPosition"] == "Below peers (<80%)").sum(), len(df))
    cols = st.columns(4)
    with cols[0]:
        kpi("Median monthly income", f"{df['MonthlyIncome'].median():,.0f}",
            f"Mean {df['MonthlyIncome'].mean():,.0f}", PRIMARY)
    with cols[1]:
        kpi("Female / male median pay", f"{ratio:.1f}%" if ratio else "n/a",
            "Unadjusted ratio of medians", VIOLET)
    with cols[2]:
        kpi("Avg salary hike", f"{df['PercentSalaryHike'].mean():.1f}%", "last cycle", TEAL)
    with cols[3]:
        kpi("Paid below peers", f"{below:.1f}%", "< 80% of job-level median", ROSE, "bad")

    section("Pay structure")
    c1, c2 = st.columns(2)
    with c1:
        d = df.assign(JobLevel=df["JobLevel"].astype(str))
        fig = px.box(d, x="JobLevel", y="MonthlyIncome", color="Gender", points=False,
                     color_discrete_map=GENDER_COLORS,
                     category_orders={"JobLevel": ["1", "2", "3", "4", "5"]},
                     title="Monthly income by job level and gender")
        fig.update_xaxes(title="Job level")
        show_chart(fig)
    with c2:
        g = df.groupby("JobRole", observed=True)["MonthlyIncome"].mean().round(0).reset_index()
        fig = px.bar(g, y="JobRole", x="MonthlyIncome", orientation="h", text="MonthlyIncome",
                     color_discrete_sequence=[PRIMARY], title="Average monthly income by job role")
        fig.update_yaxes(categoryorder="total ascending", title="")
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
        show_chart(fig)

    c3, c4 = st.columns(2)
    with c3:
        fig = px.scatter(df, x="TotalWorkingYears", y="MonthlyIncome", color="Attrition", opacity=0.65,
                         color_discrete_map=ATTRITION_COLORS,
                         hover_data=["EmpID", "JobRole", "JobLevel"],
                         title="Income vs total experience")
        fig.update_xaxes(title="Total working years")
        show_chart(fig)
    with c4:
        d = df.assign(Rating=df["PerformanceRating"].map(PERFORMANCE_LABELS))
        fig = px.box(d, x="Rating", y="PercentSalaryHike", color="Rating", points=False,
                     color_discrete_sequence=[PRIMARY, AMBER],
                     category_orders={"Rating": list(PERFORMANCE_LABELS.values())},
                     title="Salary hike % by performance rating")
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title="Performance rating")
        show_chart(fig)

    section("Does pay drive exits?")
    c5, c6 = st.columns(2)
    with c5:
        show_chart(rate_bar(df, "SalarySlab", "Attrition rate by salary slab", "Salary slab"))
    with c6:
        show_chart(rate_bar(df, "PayPosition", "Attrition rate by pay vs job-level peers", "Pay position"))
    st.caption("Pay position = employee's income ÷ median income of their job level "
               "(below 80% = 'Below peers', above 120% = 'Above peers').")

# ============================== 4. WORKFORCE ================================ #
with tabs[3]:
    c1, c2, c3 = st.columns(3)
    with c1:
        show_chart(donut(df, "Gender", "Gender mix", GENDER_COLORS))
    with c2:
        show_chart(donut(df, "MaritalStatus", "Marital status"))
    with c3:
        show_chart(donut(df, "BusinessTravel", "Business travel"))

    c4, c5 = st.columns(2)
    with c4:
        fig = px.histogram(df, x="AgeGroup", color="Gender", barmode="group",
                           color_discrete_map=GENDER_COLORS,
                           category_orders={"AgeGroup": options_for(df_all, "AgeGroup")},
                           title="Age group by gender")
        fig.update_yaxes(title="Employees")
        show_chart(fig)
    with c5:
        edu = df.groupby("EducationLevel", observed=True).size().reset_index(name="Employees")
        fig = px.bar(edu, x="EducationLevel", y="Employees", text="Employees",
                     color_discrete_sequence=[TEAL], title="Education level")
        fig.update_xaxes(title="")
        fig.update_traces(textposition="outside", cliponaxis=False)
        show_chart(fig)

    c6, c7 = st.columns(2)
    with c6:
        fig = px.histogram(df, x="Department", color="Gender", barmode="group",
                           color_discrete_map=GENDER_COLORS, title="Department by gender")
        fig.update_yaxes(title="Employees")
        show_chart(fig)
    with c7:
        fld = df["EducationField"].value_counts().rename_axis("EducationField").reset_index(name="Employees")
        fig = px.bar(fld, y="EducationField", x="Employees", orientation="h", text="Employees",
                     color_discrete_sequence=[VIOLET], title="Education field")
        fig.update_yaxes(categoryorder="total ascending", title="")
        fig.update_traces(textposition="outside", cliponaxis=False)
        show_chart(fig)

    c8, c9 = st.columns(2)
    with c8:
        fig = px.sunburst(df, path=["Department", "JobRole"], color_discrete_sequence=SEQUENCE,
                          title="Organisation structure (click to drill down)")
        fig.update_layout(height=480)
        show_chart(fig)
    with c9:
        fig = px.histogram(df, x="YearsAtCompany", nbins=20, color_discrete_sequence=[PRIMARY],
                           title="Tenure distribution")
        fig.update_xaxes(title="Years at company")
        fig.update_yaxes(title="Employees")
        show_chart(fig)

# ============================== 5. SATISFACTION ============================= #
with tabs[4]:
    METRICS = {
        "Environment satisfaction": "EnvironmentSatisfaction",
        "Job satisfaction": "JobSatisfaction",
        "Relationship satisfaction": "RelationshipSatisfaction",
        "Work-life balance": "WorkLifeBalance",
        "Job involvement": "JobInvolvement",
    }
    section("Engagement scorecard", "Average scores on a 1–4 scale (greener = more positive).")
    grp_label = st.selectbox("Group by", ["Department", "Job role", "Gender", "Age group", "Marital status"],
                             key="sat_group")
    grp_col = {"Department": "Department", "Job role": "JobRole", "Gender": "Gender",
               "Age group": "AgeGroup", "Marital status": "MaritalStatus"}[grp_label]
    heat = df.groupby(grp_col, observed=True)[list(METRICS.values())].mean()
    heat.columns = list(METRICS)
    fig = px.imshow(heat.round(2), text_auto=".2f", aspect="auto", zmin=2.2, zmax=3.3,
                    color_continuous_scale="RdYlGn", title=f"Average scores by {grp_label.lower()}")
    fig.update_layout(height=max(300, 48 * len(heat) + 150))
    show_chart(fig)

    c1, c2 = st.columns(2)
    with c1:
        avg = df.groupby("Attrition")[list(METRICS.values())].mean()
        theta = list(METRICS) + [list(METRICS)[0]]
        fig = go.Figure()
        for status, name, color in [("No", "Stayed", TEAL), ("Yes", "Left", ROSE)]:
            if status in avg.index:
                vals = avg.loc[status].round(2).tolist()
                fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=theta, fill="toself",
                                              name=name, line_color=color, opacity=0.6))
        fig.update_layout(title="Satisfaction profile: stayed vs left",
                          polar=dict(radialaxis=dict(range=[2.2, 3.3], visible=True)))
        show_chart(fig)
    with c2:
        metric_label = st.selectbox("Attrition rate by score for", list(METRICS), index=1, key="sat_metric")
        show_chart(rate_bar(df, METRICS[metric_label], f"Attrition by {metric_label.lower()} score",
                            f"{metric_label} (1 = low, 4 = high)"))

    c3, c4 = st.columns(2)
    with c3:
        show_chart(rate_bar(df, "TrainingTimesLastYear", "Attrition by training sessions last year",
                            "Training times last year"))
    with c4:
        show_chart(rate_bar(df, "PromotionGap", "Attrition by years since last promotion",
                            "Years since promotion"))

# ============================== 6. DRIVERS & RISK =========================== #
with tabs[5]:
    NUMERIC = [
        "Age", "DailyRate", "DistanceFromHome", "Education", "EnvironmentSatisfaction", "HourlyRate",
        "JobInvolvement", "JobLevel", "JobSatisfaction", "MonthlyIncome", "MonthlyRate",
        "NumCompaniesWorked", "PercentSalaryHike", "PerformanceRating", "RelationshipSatisfaction",
        "StockOptionLevel", "TotalWorkingYears", "TrainingTimesLastYear", "WorkLifeBalance",
        "YearsAtCompany", "YearsInCurrentRole", "YearsSinceLastPromotion", "YearsWithCurrManager",
        "AttritionFlag",
    ]
    num = df[NUMERIC]
    num = num.loc[:, num.std() > 0]
    section("What correlates with leaving?", "Pearson correlation with the attrition flag (1 = left).")
    if "AttritionFlag" in num.columns and num.shape[1] > 2:
        corr = num.corr()
        att = corr["AttritionFlag"].drop("AttritionFlag").sort_values()
        d = att.rename("Correlation").rename_axis("Feature").reset_index()
        d["Direction"] = np.where(d["Correlation"] > 0, "Raises attrition", "Lowers attrition")
        fig = px.bar(d, x="Correlation", y="Feature", orientation="h", color="Direction",
                     color_discrete_map={"Raises attrition": ROSE, "Lowers attrition": TEAL},
                     title="Correlation with attrition")
        fig.update_yaxes(title="")
        fig.update_layout(height=620)
        c1, c2 = st.columns([1, 1.2])
        with c1:
            show_chart(fig)
        with c2:
            fig2 = px.imshow(corr.round(2), aspect="auto", zmin=-1, zmax=1,
                             color_continuous_scale="RdBu_r", title="Correlation matrix")
            fig2.update_layout(height=620)
            show_chart(fig2)
        st.caption("Correlation ≠ causation. Strongly collinear features (e.g. tenure, experience, "
                   "job level and income) move together.")
    else:
        st.info("Not enough variation in the selected data to compute correlations.")

    section("Rule-based attrition risk score",
            "Each employee gets one point per risk factor below. More factors → higher observed attrition.")
    c3, c4 = st.columns([1, 1.2])
    with c3:
        show_chart(rate_bar(df, "RiskFactorCount", "Attrition rate by number of risk factors",
                            "Number of risk factors"))
    with c4:
        rows = []
        for name, definition in RISK_FACTORS.items():
            has = df["RiskDrivers"].str.contains(name, regex=False)
            with_rate = df.loc[has, "AttritionFlag"].mean() * 100 if has.any() else np.nan
            without_rate = df.loc[~has, "AttritionFlag"].mean() * 100 if (~has).any() else np.nan
            lift = with_rate / without_rate if without_rate and not np.isnan(without_rate) else np.nan
            rows.append({
                "Risk factor": name, "Rule": definition, "Employees": int(has.sum()),
                "Attrition % (with)": round(with_rate, 1), "Attrition % (without)": round(without_rate, 1),
                "Lift": round(lift, 2),
            })
        show_table(pd.DataFrame(rows).sort_values("Lift", ascending=False))
        st.caption("Lift = attrition rate with the factor ÷ attrition rate without it.")

    section("🚨 Retention watch-list", "Current employees with the most risk factors – candidates for stay interviews.")
    max_f = int(df["RiskFactorCount"].max())
    threshold = st.slider("Minimum number of risk factors", 1, max(max_f, 1), min(4, max(max_f, 1)),
                          key="risk_threshold")
    watch = (
        df[(df["Attrition"] == "No") & (df["RiskFactorCount"] >= threshold)]
        .sort_values(["RiskFactorCount", "MonthlyIncome"], ascending=[False, False])
        [["EmpID", "Department", "JobRole", "Age", "MonthlyIncome", "YearsAtCompany",
          "RiskFactorCount", "RiskDrivers"]]
    )
    st.markdown(f"**{len(watch):,}** current employees have **{threshold}+** risk factors.")
    show_table(watch, height=360)
    st.download_button("⬇️ Download watch-list (CSV)", watch.to_csv(index=False).encode("utf-8"),
                       "retention_watchlist.csv", "text/csv", key="dl_watch")

# ============================== 7. DATA QUALITY & EXPORT ==================== #
with tabs[6]:
    section("Cleaning summary", "What was fixed before any analysis was run (always based on the full dataset).")
    cols = st.columns(5)
    with cols[0]:
        kpi("Raw rows", f"{summary['raw_rows']:,}", f"{summary['raw_cols']} columns", SLATE)
    with cols[1]:
        kpi("Duplicates removed", f"{summary['full_duplicates'] + summary['id_duplicates']}",
            f"{summary['full_duplicates']} exact + {summary['id_duplicates']} repeated IDs", ROSE)
    with cols[2]:
        kpi("Missing values imputed", f"{summary['missing_imputed']}", "YearsWithCurrManager", AMBER)
    with cols[3]:
        kpi("Labels standardised", f"{summary['label_fixes']}", "BusinessTravel spelling", SKY)
    with cols[4]:
        kpi("Clean dataset", f"{summary['clean_rows']:,}", f"{summary['clean_cols']} columns incl. engineered", TEAL)

    st.markdown("&nbsp;")
    show_table(cleaning_log.rename(columns={"Affected": "Rows / items affected"}))

    c1, c2 = st.columns(2)
    with c1:
        section("Outlier check (IQR rule)", "Reported but not removed – these are plausible HR values.")
        show_table(outlier_summary(df_all))
    with c2:
        section("Engineered columns")
        st.markdown(
            "- **AttritionFlag** – 1 if the employee left\n"
            "- **TenureBand / ExperienceBand / DistanceBand / PromotionGap** – binned numeric fields\n"
            "- **EducationLevel** – readable labels for Education 1-5\n"
            "- **AvgSatisfaction** – mean of environment, job, relationship and work-life scores\n"
            "- **IncomeVsLevelMedian / PayPosition** – pay relative to job-level peers\n"
            "- **RiskFactorCount / RiskDrivers** – rule-based risk score (see Drivers & Risk)\n"
            "- **MgrYearsImputed** – True where YearsWithCurrManager was imputed"
        )

    section("Column profile")
    show_table(column_profile(df_all), height=320)

    section("Browse & export", "The table respects the sidebar filters.")
    show_table(df.drop(columns=["AttritionFlag"]), height=380)
    d1, d2, _ = st.columns([1, 1, 2])
    d1.download_button("⬇️ Download filtered data (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "hr_analytics_filtered.csv", "text/csv", key="dl_csv")
    d2.download_button(
        "⬇️ Download filtered data (Excel)", to_excel_bytes(df), "hr_analytics_filtered.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx",
    )
