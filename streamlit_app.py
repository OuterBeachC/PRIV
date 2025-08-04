# streamlit_app.py

import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
import io

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

# === CSV Export Functions ===
def get_time_series_data(asset_name, start_date, end_date):
    """Get time series data for a specific asset within date range"""
    filtered_df = df[
        (df["name"] == asset_name) & 
        (df["date"].dt.date >= start_date) & 
        (df["date"].dt.date <= end_date)
    ].copy()
    
    # Sort by date
    filtered_df = filtered_df.sort_values("date")
    
    # Calculate additional metrics
    filtered_df["price"] = filtered_df["market_value"] / filtered_df["par_value"] * 100
    filtered_df["price_change"] = filtered_df["price"].diff()
    filtered_df["price_pct_change"] = filtered_df["price"].pct_change() * 100
    filtered_df["market_value_change"] = filtered_df["market_value"].diff()
    
    return filtered_df

def create_csv_download(dataframe, filename):
    """Create CSV download link"""
    csv_buffer = io.StringIO()
    dataframe.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    
    return st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv"
    )

# === Sidebar Filters ===
st.sidebar.header("🔎 Filters")

available_dates = sorted(df["date"].dt.date.unique(), reverse=True)
selected_date = st.sidebar.selectbox("Current Date", available_dates)

# Get previous available date
current_idx = available_dates.index(selected_date)
previous_date = available_dates[current_idx + 1] if current_idx + 1 < len(available_dates) else None

asset_types = df["asset_breakdown"].dropna().unique()
selected_types = st.sidebar.multiselect("Asset Types", asset_types, default=asset_types)

# === CSV Export Section in Sidebar ===
st.sidebar.markdown("---")
st.sidebar.header("📥 CSV Export")

# Asset selection for export
unique_assets = sorted(df["name"].unique())
selected_asset = st.sidebar.selectbox("Select Asset for Export", unique_assets)

# Date range selection for export
min_date = df["date"].dt.date.min()
max_date = df["date"].dt.date.max()

export_start_date = st.sidebar.date_input(
    "Export Start Date", 
    value=min_date,
    min_value=min_date,
    max_value=max_date
)

export_end_date = st.sidebar.date_input(
    "Export End Date", 
    value=max_date,
    min_value=min_date,
    max_value=max_date
)

# Export options
export_columns = st.sidebar.multiselect(
    "Select Columns to Export",
    ["date", "name", "identifier", "par_value", "market_value", "asset_breakdown", "price", "price_change", "price_pct_change", "market_value_change"],
    default=["date", "name", "par_value", "market_value", "price", "price_change", "price_pct_change"]
)

# Generate export data and download button
if st.sidebar.button("Generate Export Data"):
    if selected_asset and export_start_date <= export_end_date:
        export_data = get_time_series_data(selected_asset, export_start_date, export_end_date)
        
        if not export_data.empty:
            # Select only requested columns
            export_data_filtered = export_data[export_columns].copy()
            
            # Format date for better readability
            if "date" in export_columns:
                export_data_filtered["date"] = export_data_filtered["date"].dt.strftime("%Y-%m-%d")
            
            # Store in session state for download
            st.session_state.export_data = export_data_filtered
            st.session_state.export_filename = f"{selected_asset.replace(' ', '_')}_{export_start_date}_{export_end_date}.csv"
            
            st.sidebar.success(f"✅ Export data generated! {len(export_data_filtered)} rows")
        else:
            st.sidebar.error("❌ No data found for selected criteria")
    else:
        st.sidebar.error("❌ Please check your date range")

# Download button (only show if export data exists)
if hasattr(st.session_state, 'export_data'):
    st.sidebar.markdown("### Download Ready")
    create_csv_download(st.session_state.export_data, st.session_state.export_filename)
    
    # Show preview of export data
    with st.sidebar.expander("Preview Export Data"):
        st.dataframe(st.session_state.export_data.head(10), use_container_width=True)

# === Bulk Export Options ===
st.sidebar.markdown("---")
st.sidebar.header("📦 Bulk Export Options")

bulk_export_type = st.sidebar.radio(
    "Bulk Export Type",
    ["All Data", "By Asset Type", "AOS Corporate Finance Only", "Date Range All Assets"]
)

if st.sidebar.button("Generate Bulk Export"):
    bulk_data = None
    bulk_filename = ""
    
    if bulk_export_type == "All Data":
        bulk_data = df.copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"all_financial_data_{datetime.now().strftime('%Y%m%d')}.csv"
        
    elif bulk_export_type == "By Asset Type":
        selected_bulk_types = st.sidebar.multiselect("Select Asset Types for Bulk Export", asset_types)
        if selected_bulk_types:
            bulk_data = df[df["asset_breakdown"].isin(selected_bulk_types)].copy()
            bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
            bulk_filename = f"bulk_export_{'_'.join(selected_bulk_types)}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    elif bulk_export_type == "AOS Corporate Finance Only":
        bulk_data = df[df["asset_breakdown"] == "AOS Corporate Finance"].copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"aos_corporate_finance_{datetime.now().strftime('%Y%m%d')}.csv"
        
    elif bulk_export_type == "Date Range All Assets":
        bulk_start = st.sidebar.date_input("Bulk Start Date", value=min_date, key="bulk_start")
        bulk_end = st.sidebar.date_input("Bulk End Date", value=max_date, key="bulk_end")
        
        bulk_data = df[
            (df["date"].dt.date >= bulk_start) & 
            (df["date"].dt.date <= bulk_end)
        ].copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"date_range_export_{bulk_start}_{bulk_end}.csv"
    
    if bulk_data is not None and not bulk_data.empty:
        # Format date for export
        bulk_data["date"] = bulk_data["date"].dt.strftime("%Y-%m-%d")
        
        st.session_state.bulk_export_data = bulk_data
        st.session_state.bulk_export_filename = bulk_filename
        st.sidebar.success(f"✅ Bulk export ready! {len(bulk_data)} rows")
    else:
        st.sidebar.error("❌ No data available for bulk export")

# Bulk download button
if hasattr(st.session_state, 'bulk_export_data'):
    st.sidebar.markdown("### Bulk Download Ready")
    create_csv_download(st.session_state.bulk_export_data, st.session_state.bulk_export_filename)

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

# === Export Current View Section ===
st.markdown("---")
st.markdown("### 📤 Export Current View")

col_export1, col_export2, col_export3 = st.columns(3)

with col_export1:
    if st.button("Export New Assets"):
        if not new_assets.empty:
            export_new = new_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
            st.session_state.current_view_export = export_new
            st.session_state.current_view_filename = f"new_assets_{selected_date}.csv"

with col_export2:
    if st.button("Export Removed Assets"):
        if not removed_assets.empty:
            export_removed = removed_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
            st.session_state.current_view_export = export_removed
            st.session_state.current_view_filename = f"removed_assets_{selected_date}.csv"

with col_export3:
    if st.button("Export Par Changes"):
        if not par_changes.empty:
            export_changes = par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_breakdown"]]
            st.session_state.current_view_export = export_changes
            st.session_state.current_view_filename = f"par_changes_{selected_date}.csv"

# Show download button for current view exports
if hasattr(st.session_state, 'current_view_export'):
    create_csv_download(st.session_state.current_view_export, st.session_state.current_view_filename)

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

# Export button for AOS current data
if st.button("Export AOS Current Data"):
    aos_export = aos_current_date[
        ["date_formatted", "name", "market_value", "par_value", "price", "price_pct_change", "market_value_change"]
    ].rename(columns={"date_formatted": "date"})
    st.session_state.aos_current_export = aos_export
    st.session_state.aos_current_filename = f"aos_current_data_{selected_date}.csv"

if hasattr(st.session_state, 'aos_current_export'):
    create_csv_download(st.session_state.aos_current_export, st.session_state.aos_current_filename)

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
    
    # Export button for weekly data
    if st.button("Export Weekly Summary"):
        st.session_state.weekly_export = weekly_summary
        st.session_state.weekly_filename = f"aos_weekly_summary_{datetime.now().strftime('%Y%m%d')}.csv"
    
    if hasattr(st.session_state, 'weekly_export'):
        create_csv_download(st.session_state.weekly_export, st.session_state.weekly_filename)
    
    # Create stacked bar chart
    stacked_bar_chart = alt.Chart(weekly_summary).mark_bar().encode(
        x=alt.X("week:N", title="Week", sort=alt.SortField("week", order="ascending")),
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

# Export button for index data
if st.button("Export Weighted Index Data"):
    index_export = index_daily.copy()
    index_export["date"] = index_export["date"].dt.strftime("%Y-%m-%d")
    st.session_state.index_export = index_export
    st.session_state.index_filename = f"weighted_index_{datetime.now().strftime('%Y%m%d')}.csv"

if hasattr(st.session_state, 'index_export'):
    create_csv_download(st.session_state.index_export, st.session_state.index_filename)

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
    color=alt.Color("Asset:N", title="Asset", scale=alt.Scale(range=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])),
    tooltip=["date:T", "Asset:N", "Price:Q"]
)

# Moving averages as dashed lines
ma_lines = alt.Chart(ma_data).mark_line(strokeDash=[5,5], opacity=0.7).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("Price:Q", title="Price", scale=alt.Scale(domain=[100, chart_data_melted["Price"].max() * 1.02])),
    color=alt.Color("Asset:N", title="Asset", scale=alt.Scale(range=["#9467bd", "#8c564b", "#e377c2"])),
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

# Export button for last 5 days data
if st.button("Export Last 5 Days Data"):
    last_5_export = last_5_df[["date", "clean_name", "price", "market_value", "par_value"]].copy()
    last_5_export["date"] = last_5_export["date"].dt.strftime("%Y-%m-%d")
    st.session_state.last_5_export = last_5_export
    st.session_state.last_5_filename = f"last_5_days_{datetime.now().strftime('%Y%m%d')}.csv"

if hasattr(st.session_state, 'last_5_export'):
    create_csv_download(st.session_state.last_5_export, st.session_state.last_5_filename)

# Create the chart for last 5 business days
last_5_chart = alt.Chart(last_5_df).mark_line(point=True).encode(
    x=alt.X("date:T", title="Date"),
    y=alt.Y("price:Q", title="Price", scale=alt.Scale(domain=[last_5_df["price"].min() * 0.99, last_5_df["price"].max() * 1.01])),
    color=alt.Color("clean_name:N", title="Asset"),
    tooltip=["date:T", "clean_name:N", "price:Q"]
).properties(height=400)

st.altair_chart(last_5_chart, use_container_width=True)

# === Disclosure ===
st.markdown("---")
st.markdown("""
**Disclosure:** All information displayed here is public and is not in any way to be construed as investment advice or solicitation. All data is sourced from https://www.ssga.com/us/en/intermediary/etfs/spdr-ssga-ig-public-private-credit-etf-priv and we make no claims to veracity or accuracy of the data. It is presented for academic and research purposes only.
""")