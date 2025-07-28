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

asset_types = df["asset_breakdown"].dropna().unique()
selected_types = st.sidebar.multiselect("Asset Types", asset_types, default=asset_types)

# === Filter Data by Type and Date ===
df_current = df[(df["date"].dt.date == selected_date) & (df["asset_breakdown"].isin(selected_types))]
df_previous = df[(df["date"].dt.date == previous_date) & (df["asset_breakdown"].isin(selected_types))] if previous_date else pd.DataFrame(columns=df.columns)

# === Index for Comparison ===
# Create a composite key using identifier, but fallback to name when identifier is "-"
def create_composite_key(df):
    df = df.copy()
    df['composite_key'] = df.apply(lambda row: row['name'] if row['identifier'] == '-' else row['identifier'], axis=1)
    return df.set_index('composite_key')

df_current_indexed = create_composite_key(df_current)
df_previous_indexed = create_composite_key(df_previous)

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
st.dataframe(new_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]], use_container_width=True, hide_index=True)

st.markdown("### ➖ Removed Assets")
st.dataframe(removed_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]], use_container_width=True, hide_index=True)

st.markdown("### 🔁 Par Value Changes")
st.dataframe(par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_breakdown"]], use_container_width=True, hide_index=True)

# === Pie or % Breakdown ===
st.markdown("---")
st.subheader("📊 Market Value Breakdown by Asset Type")

df_chart = df_current.groupby("asset_breakdown")["market_value"].sum().reset_index()
df_chart["percentage"] = df_chart["market_value"] / df_chart["market_value"].sum() * 100

bar_chart = alt.Chart(df_chart).mark_bar().encode(
    x=alt.X("asset_breakdown", sort="-y", title="Asset Type"),
    y=alt.Y("percentage", title="Market %"),
    tooltip=["asset_breakdown", "percentage"]
).properties(height=400)

st.altair_chart(bar_chart, use_container_width=True)

# === AOS Corporate Finance Section ===
st.markdown("---")
st.subheader("🏦 AOS Corporate Finance Analysis")

# Filter to AOS assets only
aos_df = df[df["asset_breakdown"] == "AOS Corporate Finance"].copy()
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

# === AOS Corporate Finance Pie Chart ===
st.markdown("### 🥧 AOS Corporate Finance Asset Breakdown")

# Create pie chart data for AOS Corporate Finance assets
aos_pie_data = aos_current_date.copy()
aos_pie_data["percentage"] = aos_pie_data["market_value"] / aos_pie_data["market_value"].sum() * 100

# Create a mapping for cleaner names for the pie chart
pie_name_mapping = {
    "AP FIDES HOLDINGS I LLC 6 11/30/2048": "AP Fides",
    "AP HERMES HOLDINGS I LLC 6.25 07/25/2048": "AP Hermes",
    "AP MAIA HOLDINGS I LLC 5.5 07/28/2047": "AP Maia"
}

aos_pie_data["clean_name"] = aos_pie_data["name"].map(pie_name_mapping).fillna(aos_pie_data["name"])

pie_chart = alt.Chart(aos_pie_data).mark_arc(innerRadius=50).encode(
    theta=alt.Theta("market_value:Q", title="Market Value"),
    color=alt.Color("clean_name:N", title="Asset"),
    tooltip=["clean_name:N", "market_value:Q", "percentage:Q"]
).properties(height=400)

st.altair_chart(pie_chart, use_container_width=True)

# === AOS Corporate Finance Par Value Over Time ===
st.markdown("### 📊 AOS Corporate Finance Par Value - Weekly Breakdown")

# Enhanced name mapping for all AOS Corporate Finance assets
enhanced_name_mapping = {
    "AP FIDES HOLDINGS I LLC 6 11/30/2048": "AP Fides",
    "AP HERMES HOLDINGS I LLC 6.25 07/25/2048": "AP Hermes", 
    "AP MAIA HOLDINGS I LLC 5.5 07/28/2047": "AP Maia",
    # Add more mappings as needed - you can extend this based on your other asset names
    # Example patterns (adjust based on your actual data):
    # "AP ATLAS HOLDINGS I LLC": "AP Atlas",
    # "AP TITAN HOLDINGS I LLC": "AP Titan",
}

# Get all available dates and organize into weeks
all_dates = sorted(df["date"].dt.date.unique(), reverse=True)

# Create weekly groupings (every 5 business days)
weekly_data = []
week_size = 5  # 5 business days per week

for week_num in range(min(12, len(all_dates) // week_size)):  # Show up to 12 weeks
    start_idx = week_num * week_size
    end_idx = min(start_idx + week_size, len(all_dates))
    week_dates = all_dates[start_idx:end_idx]
    
    if week_dates:
        week_df = aos_df[aos_df["date"].dt.date.isin(week_dates)].copy()
        week_start = min(week_dates)
        week_end = max(week_dates)
        
        # Format the date range for display
        if week_start == week_end:
            week_label = week_start.strftime("%m/%d/%y")
        else:
            week_label = f"{week_start.strftime('%m/%d/%y')} - {week_end.strftime('%m/%d/%y')}"
        
        week_df["week"] = week_label
        week_df["week_start"] = week_start
        week_df["week_end"] = week_end
        weekly_data.append(week_df)

if weekly_data:
    combined_weekly_df = pd.concat(weekly_data, ignore_index=True)
    
    # Apply enhanced name mapping
    combined_weekly_df["clean_name"] = combined_weekly_df["name"].map(enhanced_name_mapping).fillna(
        combined_weekly_df["name"].str.replace(r" \d+\.?\d* \d{2}/\d{2}/\d{4}", "", regex=True).str.replace(" LLC", "").str.title()
    )
    
    # Aggregate par values by week and asset
    weekly_summary = combined_weekly_df.groupby(["week", "clean_name"])["par_value"].mean().reset_index()
    
    # Create stacked bar chart
    stacked_bar_chart = alt.Chart(weekly_summary).mark_bar().encode(
        x=alt.X("week:N", title="Week", sort=alt.SortField("week", order="descending")),
        y=alt.Y("par_value:Q", title="Average Par Value"),
        color=alt.Color("clean_name:N", title="Asset"),
        tooltip=["week:N", "clean_name:N", "par_value:Q"]
    ).properties(height=400)
    
    st.altair_chart(stacked_bar_chart, use_container_width=True)
else:
    st.info("Not enough historical data available for weekly analysis.")

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

# Calculate moving averages for the Weighted Index
index_daily_sorted = index_daily.sort_values("date").copy()
index_daily_sorted["MA_30"] = index_daily_sorted["Weighted Index"].rolling(window=30, min_periods=1).mean()
index_daily_sorted["MA_60"] = index_daily_sorted["Weighted Index"].rolling(window=60, min_periods=1).mean()
index_daily_sorted["MA_200"] = index_daily_sorted["Weighted Index"].rolling(window=200, min_periods=1).mean()

# Combine weighted index with individual asset prices and moving averages
chart_data = individual_prices.merge(
    index_daily_sorted[["date", "Weighted Index", "MA_30", "MA_60", "MA_200"]], 
    on="date", 
    how="left"
)

# Rename moving averages for better display
chart_data = chart_data.rename(columns={
    "MA_30": "30-Day MA",
    "MA_60": "60-Day MA", 
    "MA_200": "200-Day MA"
})

# Display the combined chart with custom y-axis range
chart_data_melted = chart_data.melt(
    id_vars=["date"], 
    var_name="Asset", 
    value_name="Price"
)

# Create separate datasets for main lines and moving averages
main_data = chart_data_melted[~chart_data_melted['Asset'].isin(['30-Day MA', '60-Day MA', '200-Day MA'])].copy()
ma_data = chart_data_melted[chart_data_melted['Asset'].isin(['30-Day MA', '60-Day MA', '200-Day MA'])].copy()

# Individual assets and weighted index as solid lines
main_lines = alt.Chart(main_data).mark_line().encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("Price:Q", title="Price", scale=alt.Scale(domain=[100, chart_data_melted["Price"].max() * 1.02])),
    color=alt.Color("Asset:N", title="Asset"),
    tooltip=["date:T", "Asset:N", "Price:Q"]
)

# Moving averages as dashed lines
ma_lines = alt.Chart(ma_data).mark_line(strokeDash=[5,5], opacity=0.7).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("Price:Q", title="Price", scale=alt.Scale(domain=[100, chart_data_melted["Price"].max() * 1.02])),
    color=alt.Color("Asset:N", title="Asset", scale=alt.Scale(range=["#ff7f0e", "#2ca02c", "#d62728"])),
    tooltip=["date:T", "Asset:N", "Price:Q"]
)

# Combine both chart types
combined_chart = (main_lines + ma_lines).properties(height=400)

st.altair_chart(combined_chart, use_container_width=True)

# === Last 5 Business Days Price Chart ===
st.markdown("### 📈 AP Holdings Prices - Last 5 Business Days")

# Get the last 5 business days from available dates
sorted_dates = sorted(df["date"].dt.date.unique(), reverse=True)
last_5_dates = sorted_dates[:5]

# Filter index data for last 5 business days
last_5_df = index_df[index_df["date"].dt.date.isin(last_5_dates)].copy()

# Create the chart for last 5 business days
last_5_chart = alt.Chart(last_5_df).mark_line(point=True).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("price:Q", title="Price", scale=alt.Scale(domain=[last_5_df["price"].min() * 0.99, last_5_df["price"].max() * 1.01])),
    color=alt.Color("clean_name:N", title="Asset"),
    tooltip=["date:T", "clean_name:N", "price:Q"]
).properties(height=400)

st.altair_chart(last_5_chart, use_container_width=True)