"""UI helpers: theme, CSS, KPI cards and version-safe display wrappers."""
from __future__ import annotations

import streamlit as st

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
PRIMARY = "#4F46E5"   # indigo
TEAL = "#14B8A6"
AMBER = "#F59E0B"
ROSE = "#F43F5E"
SKY = "#0EA5E9"
VIOLET = "#8B5CF6"
SLATE = "#475569"

ATTRITION_COLORS = {"No": TEAL, "Yes": ROSE}
GENDER_COLORS = {"Female": VIOLET, "Male": SKY}
SEQUENCE = [PRIMARY, TEAL, AMBER, ROSE, SKY, VIOLET, "#84CC16", "#EC4899", "#64748B"]

CSS = f"""
<style>
    .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1400px; }}
    #MainMenu, footer {{ visibility: hidden; }}

    /* Hero banner */
    .hero {{
        background: linear-gradient(120deg, {PRIMARY} 0%, {VIOLET} 55%, {SKY} 100%);
        border-radius: 18px; padding: 26px 32px; color: #fff; margin-bottom: 18px;
        box-shadow: 0 10px 30px rgba(79,70,229,.25);
    }}
    .hero h1 {{ margin: 0; font-size: 2rem; font-weight: 800; color: #fff; }}
    .hero p  {{ margin: 6px 0 0; font-size: 1rem; opacity: .92; color: #fff; }}

    /* KPI cards */
    .kpi {{
        background: #fff; border-radius: 14px; padding: 16px 18px;
        border: 1px solid #E2E8F0; border-left: 6px solid var(--accent, {PRIMARY});
        box-shadow: 0 2px 10px rgba(15,23,42,.05); height: 100%;
    }}
    .kpi .label {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .06em;
                   color: #64748B; font-weight: 600; }}
    .kpi .value {{ font-size: 1.85rem; font-weight: 800; color: #0F172A; line-height: 1.25; }}
    .kpi .sub   {{ font-size: .8rem; color: #64748B; }}
    .kpi .sub.bad  {{ color: {ROSE}; font-weight: 600; }}
    .kpi .sub.good {{ color: #0D9488; font-weight: 600; }}

    /* Insight callouts */
    .insight {{
        background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid {AMBER};
        border-radius: 10px; padding: 12px 16px; margin: 8px 0; color: #1E293B; font-size: .95rem;
    }}

    /* Section titles */
    .section-title {{
        font-size: 1.15rem; font-weight: 700; color: #0F172A; margin: 22px 0 4px;
        padding-bottom: 6px; border-bottom: 3px solid {PRIMARY}; display: inline-block;
    }}
    .section-caption {{ color: #64748B; font-size: .9rem; margin-bottom: 8px; }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; flex-wrap: wrap; }}
    .stTabs [data-baseweb="tab"] {{
        background: #EEF2FF; border-radius: 10px 10px 0 0; padding: 10px 18px; font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{ background: {PRIMARY}; color: #fff !important; }}
    .stTabs [aria-selected="true"] p {{ color: #fff !important; }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{ background: #F1F5F9; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, sub: str = "", accent: str = PRIMARY, tone: str = "") -> None:
    """Render one KPI card. ``tone`` is '', 'bad' or 'good' and colours the sub-text."""
    st.markdown(
        f'<div class="kpi" style="--accent:{accent}">'
        f'<div class="label">{label}</div><div class="value">{value}</div>'
        f'<div class="sub {tone}">{sub}&nbsp;</div></div>',
        unsafe_allow_html=True,
    )


def section(title: str, caption: str = "") -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-caption">{caption}</div>', unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="insight">💡 {text}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Version-safe wrappers (Streamlit replaced use_container_width with width="stretch")
# --------------------------------------------------------------------------- #
_chart_counter = [0]


def reset_chart_keys() -> None:
    """Call once at the top of every script run so chart keys are stable between reruns."""
    _chart_counter[0] = 0


def show_chart(fig, key: str | None = None) -> None:
    # Unique, deterministic key per chart → identical figures in different tabs
    # can never collide (Streamlit would raise DuplicateElementId otherwise).
    if key is None:
        _chart_counter[0] += 1
        key = f"chart_{_chart_counter[0]}"
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#1E293B"),
        margin=dict(l=10, r=10, t=55, b=10),
        title_font=dict(size=16),
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5),
    )
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except Exception:  # older Streamlit without width="stretch"
        st.plotly_chart(fig, use_container_width=True, key=key)


def show_table(df, **kwargs) -> None:
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kwargs)
    except Exception:  # older Streamlit without width="stretch"
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)
