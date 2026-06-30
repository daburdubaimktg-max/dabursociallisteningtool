"""Competitor Social Media Growth — Streamlit dashboard.

Interactive front-end over the same follower store that backs the Excel export.
Filter by platform / category / region / brand / month window; see KPIs, the growth
leaderboard, follower trend charts, the IG-vs-TikTok combined view, and drill down to
the underlying snapshots. Download the live Excel workbook from the sidebar.

Reach only: this dashboard tracks follower growth and never blends it with sentiment
(CLAUDE.md Rule 2).

Run:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard_export.excel import workbook_bytes
from growth.frame import long_rows
from growth.pipeline import seed_history
from growth.store import GrowthStore

st.set_page_config(page_title="Competitor Social Growth", page_icon="📈", layout="wide")


# --- data ---------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading follower history…")
def get_store() -> GrowthStore:
    store = GrowthStore()
    seed_history(store)
    return store


@st.cache_data(show_spinner=False)
def get_frame() -> pd.DataFrame:
    df = pd.DataFrame(long_rows(get_store()))
    # brand-level series sum handles within the same brand+platform+period
    return df


def _excel_bytes() -> bytes:
    return workbook_bytes(get_store())


store = get_store()
df = get_frame()

# --- sidebar filters ----------------------------------------------------------
st.sidebar.title("📈 Filters")
platforms = st.sidebar.multiselect(
    "Platform", ["instagram", "tiktok"], default=["instagram", "tiktok"]
)
categories = sorted(df["category"].unique())
regions = sorted(df["region"].unique())
sel_cats = st.sidebar.multiselect("Category", categories, default=[])
sel_regions = st.sidebar.multiselect("Region", regions, default=[])

mask = df["platform"].isin(platforms)
if sel_cats:
    mask &= df["category"].isin(sel_cats)
if sel_regions:
    mask &= df["region"].isin(sel_regions)
fdf = df[mask].copy()

all_brands = sorted(fdf["brand"].unique())
sel_brands = st.sidebar.multiselect("Brand", all_brands, default=[])
if sel_brands:
    fdf = fdf[fdf["brand"].isin(sel_brands)]

periods = sorted(fdf["period"].unique())
if periods:
    start, end = st.sidebar.select_slider(
        "Month window", options=periods, value=(periods[0], periods[-1])
    )
    fdf = fdf[(fdf["period"] >= start) & (fdf["period"] <= end)]

st.sidebar.divider()
st.sidebar.download_button(
    "⬇️ Download Excel dashboard",
    data=_excel_bytes(),
    file_name="competitor_growth_dashboard.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    width="stretch",
)
st.sidebar.caption("Reach dimension only — follower growth is never blended with sentiment.")

# --- header -------------------------------------------------------------------
st.title("Competitor Social Media Growth")
st.caption("Instagram + TikTok follower growth for tracked competitor brands.")

if fdf.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# brand × platform × period series (sum across handles of the same brand)
series = (
    fdf.groupby(["platform", "brand", "category", "region", "period"], as_index=False)["followers"]
    .sum()
    .sort_values("period")
)


def latest_per_brand(frame: pd.DataFrame) -> pd.DataFrame:
    idx = frame.groupby(["platform", "brand"])["period"].idxmax()
    return frame.loc[idx]


def first_per_brand(frame: pd.DataFrame) -> pd.DataFrame:
    idx = frame.groupby(["platform", "brand"])["period"].idxmin()
    return frame.loc[idx]


latest = latest_per_brand(series)
first = first_per_brand(series)

# --- KPI row ------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Brands tracked", latest["brand"].nunique())
c2.metric("Latest total followers", f"{int(latest['followers'].sum()):,}")
gain = int(latest["followers"].sum() - first["followers"].sum())
c3.metric("Net follower gain (window)", f"{gain:,}")
c4.metric("Months covered", f"{series['period'].min()} → {series['period'].max()}")

# growth (start→end within the filtered window) per brand+platform
merged = first.merge(
    latest, on=["platform", "brand", "category", "region"], suffixes=("_start", "_end")
)
merged = merged[merged["period_start"] != merged["period_end"]].copy()
merged["delta"] = merged["followers_end"] - merged["followers_start"]
merged["growth_pct"] = (merged["delta"] / merged["followers_start"]).where(
    merged["followers_start"] > 0
)

tab_over, tab_lead, tab_trend, tab_combined, tab_data = st.tabs(
    ["Overview", "Growth leaderboard", "Trends", "Combined (IG vs TikTok)", "Data"]
)

# --- Overview -----------------------------------------------------------------
with tab_over:
    left, right = st.columns(2)
    with left:
        st.subheader("Top movers — absolute gain")
        top = merged.sort_values("delta", ascending=False).head(15)
        st.dataframe(
            top[["platform", "brand", "followers_start", "followers_end", "delta", "growth_pct"]]
            .rename(
                columns={
                    "followers_start": "start",
                    "followers_end": "end",
                    "growth_pct": "growth %",
                }
            )
            .style.format(
                {"start": "{:,.0f}", "end": "{:,.0f}", "delta": "{:+,.0f}", "growth %": "{:+.1%}"}
            ),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.subheader("Share of latest followers")
        sov = latest.groupby("brand")["followers"].sum().sort_values(ascending=False).head(15)
        st.bar_chart(sov)

    st.subheader("Latest followers by category")
    by_cat = latest.pivot_table(
        index="category", columns="platform", values="followers", aggfunc="sum", fill_value=0
    )
    st.bar_chart(by_cat)

# --- Leaderboard --------------------------------------------------------------
with tab_lead:
    st.subheader("Follower-growth leaderboard")
    metric = st.radio("Rank by", ["Absolute gain", "Growth %"], horizontal=True)
    sort_col = "delta" if metric == "Absolute gain" else "growth_pct"
    board = merged.sort_values(sort_col, ascending=False)[
        [
            "platform",
            "brand",
            "category",
            "region",
            "period_start",
            "followers_start",
            "period_end",
            "followers_end",
            "delta",
            "growth_pct",
        ]
    ].rename(
        columns={
            "period_start": "from",
            "followers_start": "start",
            "period_end": "to",
            "followers_end": "end",
            "growth_pct": "growth %",
        }
    )
    st.dataframe(
        board.style.format(
            {"start": "{:,.0f}", "end": "{:,.0f}", "delta": "{:+,.0f}", "growth %": "{:+.1%}"}
        ),
        width="stretch",
        hide_index=True,
        height=520,
    )

# --- Trends -------------------------------------------------------------------
with tab_trend:
    st.subheader("Follower trajectories")
    default_brands = list(latest.sort_values("followers", ascending=False)["brand"].unique()[:6])
    chart_brands = st.multiselect(
        "Brands to plot", sorted(series["brand"].unique()), default=default_brands
    )
    plat_for_chart = st.radio("Platform", platforms, horizontal=True)
    cdf = series[(series["brand"].isin(chart_brands)) & (series["platform"] == plat_for_chart)]
    if cdf.empty:
        st.info("Pick at least one brand present on this platform.")
    else:
        wide = cdf.pivot_table(
            index="period", columns="brand", values="followers", aggfunc="sum"
        ).sort_index()
        st.line_chart(wide)

# --- Combined -----------------------------------------------------------------
with tab_combined:
    st.subheader("Instagram vs TikTok — latest followers (separate columns, never fused)")
    ig = latest[latest["platform"] == "instagram"].set_index("brand")["followers"]
    tt = latest[latest["platform"] == "tiktok"].set_index("brand")["followers"]
    comb = pd.DataFrame({"instagram": ig, "tiktok": tt}).fillna(0).astype(int)
    comb["total audience"] = comb["instagram"] + comb["tiktok"]
    comb = comb.sort_values("total audience", ascending=False)
    st.dataframe(comb.style.format("{:,.0f}"), width="stretch", height=520)

# --- Data / drill-down --------------------------------------------------------
with tab_data:
    st.subheader("Underlying snapshots")
    st.caption("Every KPI above drills down to these rows. Use the sidebar to filter.")
    st.dataframe(
        fdf.sort_values(["brand", "platform", "period"]),
        width="stretch",
        hide_index=True,
        height=520,
    )
    st.download_button(
        "⬇️ Download filtered data (CSV)",
        data=fdf.to_csv(index=False).encode("utf-8"),
        file_name="follower_snapshots.csv",
        mime="text/csv",
    )
