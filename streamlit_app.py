# streamlit_app.py

import streamlit as st
import pandas as pd
import sqlite3
import altair as alt

st.set_page_config(layout="wide")
st.title("📊 Financial Holdings: Day-over-Day Dashboard")

# === Load Data ===
@st.cache_data
def load_data():
    conn = sqlite3.connect("priv_data.db")
    df = pd.read_sql("SELECT * FROM financial_data", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df

df = load_data()

# === Sidebar Filters ===
st.sidebar.header("🔎 Filters")

available_dates = sorted(df["date"].dt.date.unique(), reverse=True)
selected_date = st.sidebar.selectbox("Current Date", available_dates)

# Get previous available date
current_idx = available_dates.index(selected_date)
previous_date = available_dates[current_idx + 1] if current_idx + 1 < len(available_dates) else None

asset_types = df["asset_type"].dropna().unique()
selected_types = st.sidebar.multiselect("Asset Types", asset_types, default=asset_types)

# === Filter Data by Type and Date ===
df_current = df[(df["date"].dt.date == selected_date) & (df["asset_type"].isin(selected_types))]
df_previous = df[(df["date"].dt.date == previous_date) & (df["asset_type"].isin(selected_types))] if previous_date else pd.DataFrame(columns=df.columns)

# === Index for Comparison ===
index_cols = ["identifier", "name"]

df_current_indexed = df_current.set_index(index_cols)
df_previous_indexed = df_previous.set_index(index_cols)

# === Asset Comparison ===
new_assets = df_current_indexed[~df_current_indexed.index.isin(df_previous_indexed.index)]
removed_assets = df_previous_indexed[~df_previous_indexed.index.isin(df_current_indexed.index)]

# Compare common assets for par value changes
common_assets = df_current_indexed[df_current_indexed.index.isin(df_previous_indexed.index)].copy()
common_assets["par_value_prev"] = df_previous_indexed["par_value"]
common_assets["par_change"] = common_assets["par_value"] - common_assets["par_value_prev"]
par_changes = common_assets[common_assets["par_change"] != 0]

# === Layout ===
st.subheader(f"📅 Comparing: {selected_date} vs {previous_date if previous_date else '—'}")

col1, col2, col3 = st.columns(3)
col1.metric("Total Market Value", f"${df_current['market_value'].sum():,.2f}")
col2.metric("Total Par Value", f"${df_current['par_value'].sum():,.2f}")
col3.metric("Securities Count", len(df_current))

# === Changes Section ===
st.markdown("---")
st.subheader("📈 Changes Since Previous Date")

st.markdown("### ➕ New Assets")
st.dataframe(new_assets.reset_index()[["name", "par_value", "market_value", "asset_type"]], use_container_width=True, hide_index=True)

st.markdown("### ➖ Removed Assets")
st.dataframe(removed_assets.reset_index()[["name", "par_value", "market_value", "asset_type"]], use_container_width=True, hide_index=True)

st.markdown("### 🔁 Par Value Changes")
st.dataframe(par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_type"]], use_container_width=True, hide_index=True)

# === Pie or % Breakdown ===
st.markdown("---")
st.subheader("📊 Market Value Breakdown by Asset Type")

df_chart = df_current.groupby("asset_type")["market_value"].sum().reset_index()
df_chart["percentage"] = df_chart["market_value"] / df_chart["market_value"].sum() * 100

bar_chart = alt.Chart(df_chart).mark_bar().encode(
    x=alt.X("asset_type", sort="-y", title="Asset Type"),
    y=alt.Y("percentage", title="Market %"),
    tooltip=["asset_type", "percentage"]
).properties(height=400)

st.altair_chart(bar_chart, use_container_width=True)

# === AOS Corporate Finance Section ===
st.markdown("---")
st.subheader("🏦 AOS Corporate Finance Analysis")

# Filter to AOS assets only
aos_df = df[df["asset_type"] == "AOS Corporate Finance"].copy()
aos_df["date"] = pd.to_datetime(aos_df["date"])
aos_df.sort_values(["name", "date"], inplace=True)

# Calculate Price = Market Value / Par Value
aos_df["price"] = aos_df["market_value"] / aos_df["par_value"] * 100

# Daily Price % Change and Market Value Change
aos_df["price_pct_change"] = aos_df.groupby("name")["price"].pct_change() * 100
aos_df["market_value_change"] = aos_df.groupby("name")["market_value"].diff()

st.markdown("### 📋 Asset-Level Price and Value Movements")

# Filter to show only the selected current date
aos_current_date = aos_df[aos_df["date"].dt.date == selected_date].copy()

# Format the date column
aos_current_date["date_formatted"] = aos_current_date["date"].dt.strftime("%m/%d/%Y")

st.dataframe(
    aos_current_date[
        ["date_formatted", "name", "market_value", "par_value", "price", "price_pct_change", "market_value_change"]
    ].rename(columns={"date_formatted": "date"}),
    use_container_width=True,
    hide_index=True
)

# === Custom Index Calculation ===
st.markdown("### 📈 Custom Index: Weighted AOS Holdings")

st.markdown("#### AP Fides, AP Hermes, and AP Maia prices, weighted by market value")
index_assets = [
    "AP FIDES HOLDINGS I LLC 6 11/30/2048",
    "AP HERMES HOLDINGS I LLC 6.25 07/25/2048",
    "AP MAIA HOLDINGS I LLC 5.5 07/28/2047"
]

index_df = aos_df[aos_df["name"].isin(index_assets)].copy()

# Create a mapping for cleaner names
name_mapping = {
    "AP FIDES HOLDINGS I LLC 6 11/30/2048": "AP Fides",
    "AP HERMES HOLDINGS I LLC 6.25 07/25/2048": "AP Hermes",
    "AP MAIA HOLDINGS I LLC 5.5 07/28/2047": "AP Maia"
}

# Add clean names for individual asset tracking
index_df["clean_name"] = index_df["name"].map(name_mapping)

# Calculate weighted index
index_df["weight"] = index_df["market_value"]
index_df["price_weighted"] = index_df["price"] * index_df["weight"]

index_daily = index_df.groupby("date").agg(
    total_mv=("market_value", "sum"),
    weighted_price=("price_weighted", "sum")
).reset_index()

index_daily["Weighted Index"] = index_daily["weighted_price"] / index_daily["total_mv"]

# Prepare individual asset prices for charting
individual_prices = index_df.pivot_table(
    index="date", 
    columns="clean_name", 
    values="price", 
    aggfunc="first"
).reset_index()

# Combine weighted index with individual asset prices
chart_data = individual_prices.merge(
    index_daily[["date", "Weighted Index"]], 
    on="date", 
    how="left"
)

# Display the combined chart with custom y-axis range
chart_data_melted = chart_data.melt(
    id_vars=["date"], 
    var_name="Asset", 
    value_name="Price"
)

line_chart = alt.Chart(chart_data_melted).mark_line().encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("Price:Q", title="Price", scale=alt.Scale(domain=[100, chart_data_melted["Price"].max() * 1.02])),
    color=alt.Color("Asset:N", title="Asset"),
    tooltip=["date:T", "Asset:N", "Price:Q"]
).properties(height=400)

st.altair_chart(line_chart, use_container_width=True)