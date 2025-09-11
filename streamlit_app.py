# streamlit_app.py

import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
import io

st.set_page_config(layout="wide")
st.title("📊 Financial Holdings: Multi-Fund Dashboard")

# === Fund Configuration ===
FUND_CONFIG = {
    "PRIV": {
        "name": "SPDR SSGA Private Credit ETF",
        "url": "https://www.ssga.com/us/en/intermediary/etfs/spdr-ssga-ig-public-private-credit-etf-priv"
    },
    "PRSD": {
        "name": "SPDR SSGA Senior Debt ETF", 
        "url": "https://www.ssga.com/us/en/intermediary/etfs/spdr-ssga-senior-debt-etf-prsd"
    }
}

# === Load Data Function ===
@st.cache_data
def load_data(fund_symbol):
    conn = sqlite3.connect("priv_data.db")
    
    try:
        # Filter by source_identifier column
        df = pd.read_sql(f"SELECT * FROM financial_data WHERE source_identifier = '{fund_symbol}'", conn)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        st.error(f"Error loading data for {fund_symbol}: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

# === Create Tabs ===
tab1, tab2 = st.tabs(["📈 PRIV", "📊 PRSD"])

# === Function to render dashboard for a specific fund ===
def render_fund_dashboard(fund_symbol, df):
    if df.empty:
        st.warning(f"No data available for {fund_symbol}")
        return
    
    fund_info = FUND_CONFIG[fund_symbol]
    st.markdown(f"### {fund_info['name']} ({fund_symbol})")
    
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

    def create_csv_download(dataframe, filename, key=None):
        """Create CSV download link"""
        csv_buffer = io.StringIO()
        dataframe.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        return st.sidebar.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key=key
        )

    # === Sidebar Filters ===
    st.sidebar.header(f"🔎 {fund_symbol} Filters")

    available_dates = sorted(df["date"].dt.date.unique(), reverse=True)
    selected_date = st.sidebar.selectbox(f"{fund_symbol} Current Date", available_dates, key=f"{fund_symbol}_date")

    # Get previous available date
    current_idx = available_dates.index(selected_date)
    previous_date = available_dates[current_idx + 1] if current_idx + 1 < len(available_dates) else None

    asset_types = df["asset_breakdown"].dropna().unique()
    selected_types = st.sidebar.multiselect(f"{fund_symbol} Asset Types", asset_types, default=asset_types, key=f"{fund_symbol}_types")

    # === CSV Export Section in Sidebar ===
    st.sidebar.markdown("---")
    st.sidebar.header(f"📥 {fund_symbol} CSV Export")

    # Asset selection for export
    unique_assets = sorted(df["name"].unique())
    selected_asset = st.sidebar.selectbox(f"Select {fund_symbol} Asset for Export", unique_assets, key=f"{fund_symbol}_asset")

    # Date range selection for export
    min_date = df["date"].dt.date.min()
    max_date = df["date"].dt.date.max()

    export_start_date = st.sidebar.date_input(
        f"{fund_symbol} Export Start Date", 
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key=f"{fund_symbol}_start"
    )

    export_end_date = st.sidebar.date_input(
        f"{fund_symbol} Export End Date", 
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key=f"{fund_symbol}_end"
    )

    # Export options
    export_columns = st.sidebar.multiselect(
        f"Select {fund_symbol} Columns to Export",
        ["date", "name", "identifier", "par_value", "market_value", "asset_breakdown", "price", "price_change", "price_pct_change", "market_value_change"],
        default=["date", "name", "par_value", "market_value", "price", "price_change", "price_pct_change"],
        key=f"{fund_symbol}_columns"
    )

    # Generate export data and download button
    if st.sidebar.button(f"Generate {fund_symbol} Export Data", key=f"{fund_symbol}_generate"):
        if selected_asset and export_start_date <= export_end_date:
            export_data = get_time_series_data(selected_asset, export_start_date, export_end_date)
            
            if not export_data.empty:
                # Select only requested columns
                export_data_filtered = export_data[export_columns].copy()
                
                # Format date for better readability
                if "date" in export_columns:
                    export_data_filtered["date"] = export_data_filtered["date"].dt.strftime("%Y-%m-%d")
                
                # Store in session state for download
                st.session_state[f"{fund_symbol}_export_data"] = export_data_filtered
                st.session_state[f"{fund_symbol}_export_filename"] = f"{fund_symbol}_{selected_asset.replace(' ', '_')}_{export_start_date}_{export_end_date}.csv"
                
                st.sidebar.success(f"✅ {fund_symbol} export data generated! {len(export_data_filtered)} rows")
            else:
                st.sidebar.error(f"❌ No {fund_symbol} data found for selected criteria")
        else:
            st.sidebar.error("❌ Please check your date range")

    # Show preview of export data (only show if export data exists)
    if f"{fund_symbol}_export_data" in st.session_state:
        with st.sidebar.expander(f"Preview {fund_symbol} Export Data"):
            st.dataframe(st.session_state[f"{fund_symbol}_export_data"].head(10), use_container_width=True)

    # === Bulk Export Options ===
    st.sidebar.markdown("---")
    st.sidebar.header(f"📦 {fund_symbol} Bulk Export Options")

    bulk_export_type = st.sidebar.radio(
        f"{fund_symbol} Bulk Export Type",
        ["All Data", "By Asset Type", "AOS Corporate Finance Only", "Date Range All Assets"],
        key=f"{fund_symbol}_bulk_type"
    )

    if st.sidebar.button(f"Generate {fund_symbol} Bulk Export", key=f"{fund_symbol}_bulk_generate"):
        bulk_data = None
        bulk_filename = ""
        
        if bulk_export_type == "All Data":
            bulk_data = df.copy()
            bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
            bulk_filename = f"{fund_symbol}_all_financial_data_{datetime.now().strftime('%Y%m%d')}.csv"
            
        elif bulk_export_type == "By Asset Type":
            selected_bulk_types = st.sidebar.multiselect(f"Select {fund_symbol} Asset Types for Bulk Export", asset_types, key=f"{fund_symbol}_bulk_types")
            if selected_bulk_types:
                bulk_data = df[df["asset_breakdown"].isin(selected_bulk_types)].copy()
                bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
                bulk_filename = f"{fund_symbol}_bulk_export_{'_'.join(selected_bulk_types)}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        elif bulk_export_type == "AOS Corporate Finance Only":
            bulk_data = df[df["asset_breakdown"] == "AOS Corporate Finance"].copy()
            bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
            bulk_filename = f"{fund_symbol}_aos_corporate_finance_{datetime.now().strftime('%Y%m%d')}.csv"
            
        elif bulk_export_type == "Date Range All Assets":
            bulk_start = st.sidebar.date_input(f"{fund_symbol} Bulk Start Date", value=min_date, key=f"{fund_symbol}_bulk_start")
            bulk_end = st.sidebar.date_input(f"{fund_symbol} Bulk End Date", value=max_date, key=f"{fund_symbol}_bulk_end")
            
            bulk_data = df[
                (df["date"].dt.date >= bulk_start) & 
                (df["date"].dt.date <= bulk_end)
            ].copy()
            bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
            bulk_filename = f"{fund_symbol}_date_range_export_{bulk_start}_{bulk_end}.csv"
        
        if bulk_data is not None and not bulk_data.empty:
            # Format date for export
            bulk_data["date"] = bulk_data["date"].dt.strftime("%Y-%m-%d")
            
            st.session_state[f"{fund_symbol}_bulk_export_data"] = bulk_data
            st.session_state[f"{fund_symbol}_bulk_export_filename"] = bulk_filename
            st.sidebar.success(f"✅ {fund_symbol} bulk export ready! {len(bulk_data)} rows")
        else:
            st.sidebar.error(f"❌ No {fund_symbol} data available for bulk export")

    # Bulk download button
    if f"{fund_symbol}_bulk_export_data" in st.session_state:
        with st.sidebar.expander(f"Preview {fund_symbol} Bulk Export Data"):
            st.dataframe(st.session_state[f"{fund_symbol}_bulk_export_data"].head(10), use_container_width=True)

    # === Download Section at Bottom of Sidebar ===
    st.sidebar.markdown("---")
    st.sidebar.header(f"📥 {fund_symbol} Downloads")

    # Individual asset download button
    if f"{fund_symbol}_export_data" in st.session_state:
        st.sidebar.markdown(f"**{fund_symbol} Individual Asset Export:**")
        create_csv_download(st.session_state[f"{fund_symbol}_export_data"], st.session_state[f"{fund_symbol}_export_filename"], key=f"{fund_symbol}_individual_download")

    # Bulk download button
    if f"{fund_symbol}_bulk_export_data" in st.session_state:
        st.sidebar.markdown(f"**{fund_symbol} Bulk Export:**")
        create_csv_download(st.session_state[f"{fund_symbol}_bulk_export_data"], st.session_state[f"{fund_symbol}_bulk_export_filename"], key=f"{fund_symbol}_bulk_download")

    # === Filter Data by Type and Date ===
    df_current = df[(df["date"].dt.date == selected_date) & (df["asset_breakdown"].isin(selected_types))]
    df_previous = df[(df["date"].dt.date == previous_date) & (df["asset_breakdown"].isin(selected_types))] if previous_date else pd.DataFrame(columns=df.columns)

    # === Index for Comparison ===
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
    if not df_previous_indexed.empty and not common_assets.empty:
        common_assets["par_value_prev"] = df_previous_indexed["par_value"]
        common_assets["par_change"] = common_assets["par_value"] - common_assets["par_value_prev"]
        par_changes = common_assets[common_assets["par_change"] != 0]
    else:
        par_changes = pd.DataFrame()

    # === Layout ===
    st.subheader(f"📅 {fund_symbol} Comparing: {selected_date} vs {previous_date if previous_date else '—'}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Market Value", f"${df_current['market_value'].sum():,.2f}")
    col2.metric("Total Par Value", f"${df_current['par_value'].sum():,.2f}")
    col3.metric("Securities Count", len(df_current))

    # === Export Current View Section ===
    st.markdown("---")
    st.markdown(f"### 📤 Export {fund_symbol} Current View")

    col_export1, col_export2, col_export3 = st.columns(3)

    with col_export1:
        if st.button(f"Export {fund_symbol} New Assets", key=f"{fund_symbol}_export_new"):
            if not new_assets.empty:
                export_new = new_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
                st.session_state[f"{fund_symbol}_current_view_export"] = export_new
                st.session_state[f"{fund_symbol}_current_view_filename"] = f"{fund_symbol}_new_assets_{selected_date}.csv"

    with col_export2:
        if st.button(f"Export {fund_symbol} Removed Assets", key=f"{fund_symbol}_export_removed"):
            if not removed_assets.empty:
                export_removed = removed_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
                st.session_state[f"{fund_symbol}_current_view_export"] = export_removed
                st.session_state[f"{fund_symbol}_current_view_filename"] = f"{fund_symbol}_removed_assets_{selected_date}.csv"

    with col_export3:
        if st.button(f"Export {fund_symbol} Par Changes", key=f"{fund_symbol}_export_changes"):
            if not par_changes.empty:
                export_changes = par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_breakdown"]]
                st.session_state[f"{fund_symbol}_current_view_export"] = export_changes
                st.session_state[f"{fund_symbol}_current_view_filename"] = f"{fund_symbol}_par_changes_{selected_date}.csv"

    # Show download button for current view exports
    if f"{fund_symbol}_current_view_export" in st.session_state:
        st.sidebar.download_button(
            label=f"📥 Download {fund_symbol} CSV",
            data=st.session_state[f"{fund_symbol}_current_view_export"].to_csv(index=False),
            file_name=st.session_state[f"{fund_symbol}_current_view_filename"],
            mime="text/csv",
            key=f"{fund_symbol}_current_view_download"
        )

    # === Changes Section ===
    st.markdown("---")
    st.subheader(f"📈 {fund_symbol} Changes Since Previous Date")

    st.markdown("### ➕ New Assets")
    if not new_assets.empty:
        st.dataframe(new_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]], use_container_width=True, hide_index=True)
    else:
        st.info("No new assets")

    st.markdown("### ➖ Removed Assets")
    if not removed_assets.empty:
        st.dataframe(removed_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]], use_container_width=True, hide_index=True)
    else:
        st.info("No removed assets")

    st.markdown("### 🔁 Par Value Changes")
    if not par_changes.empty:
        st.dataframe(par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_breakdown"]], use_container_width=True, hide_index=True)
    else:
        st.info("No par value changes")

    # === Pie Chart Breakdown ===
    st.markdown("---")
    st.subheader(f"📊 {fund_symbol} Market Value Breakdown by Asset Type")

    if not df_current.empty:
        df_chart = df_current.groupby("asset_breakdown")["market_value"].sum().reset_index()
        df_chart["percentage"] = df_chart["market_value"] / df_chart["market_value"].sum() * 100

        bar_chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X("asset_breakdown", sort="-y", title="Asset Type"),
            y=alt.Y("percentage", title="Market %"),
            tooltip=["asset_breakdown", "percentage"]
        ).properties(height=400)

        st.altair_chart(bar_chart, use_container_width=True)
    else:
        st.info("No data available for chart")

    # === AOS Corporate Finance Section (for both PRIV and PRSD) ===
    st.markdown("---")
    st.subheader(f"🏦 {fund_symbol} AOS Corporate Finance Analysis")

    # Filter to AOS assets only
    aos_df = df[df["asset_breakdown"] == "AOS Corporate Finance"].copy()
    
    if not aos_df.empty:
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

        # Export button for AOS current data
        if st.button(f"Export {fund_symbol} AOS Current Data", key=f"{fund_symbol}_aos_current"):
            if not aos_current_date.empty:
                aos_export = aos_current_date[
                    ["date", "name", "market_value", "par_value", "price", "price_pct_change", "market_value_change"]
                ].copy()
                aos_export["date"] = aos_export["date"].dt.strftime("%Y-%m-%d")
                st.session_state[f"{fund_symbol}_aos_current_export"] = aos_export
                st.session_state[f"{fund_symbol}_aos_current_filename"] = f"{fund_symbol}_aos_current_data_{selected_date}.csv"

        if f"{fund_symbol}_aos_current_export" in st.session_state:
            st.sidebar.download_button(
                label=f"📥 Download {fund_symbol} AOS CSV",
                data=st.session_state[f"{fund_symbol}_aos_current_export"].to_csv(index=False),
                file_name=st.session_state[f"{fund_symbol}_aos_current_filename"],
                mime="text/csv",
                key=f"{fund_symbol}_aos_current_download"
            )

        if not aos_current_date.empty:
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
            st.markdown(f"### 🥧 {fund_symbol} AOS Corporate Finance Asset Breakdown")

            # Create pie chart data for AOS Corporate Finance assets
            aos_pie_data = aos_current_date.copy()
            aos_pie_data["percentage"] = aos_pie_data["market_value"] / aos_pie_data["market_value"].sum() * 100

            # Create a function to generate cleaner names for all AOS assets
            def create_clean_name(asset_name):
                """Create cleaner asset names using first 5 words"""
                words = asset_name.split()
                # Take first 5 words, or all words if fewer than 5
                clean_name = " ".join(words[:5])
                return clean_name

            aos_pie_data["clean_name"] = aos_pie_data["name"].apply(create_clean_name)

            pie_chart = alt.Chart(aos_pie_data).mark_arc(innerRadius=50).encode(
                theta=alt.Theta("market_value:Q", title="Market Value"),
                color=alt.Color("clean_name:N", title="Asset"),
                tooltip=["clean_name:N", "market_value:Q", "percentage:Q"]
            ).properties(height=400)

            st.altair_chart(pie_chart, use_container_width=True)

            # === AOS Corporate Finance Par Value Over Time ===
            st.markdown(f"### 📊 {fund_symbol} AOS Corporate Finance Par Value - Weekly Breakdown")

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
                    
                    week_label = week_end.strftime("%m/%d/%y")  
                    
                    week_df["week"] = week_label
                    week_df["week_start"] = week_start
                    week_df["week_end"] = week_end
                    weekly_data.append(week_df)

            if weekly_data:
                combined_weekly_df = pd.concat(weekly_data, ignore_index=True)
                
                # Apply clean name function to all AOS assets
                combined_weekly_df["clean_name"] = combined_weekly_df["name"].apply(create_clean_name)
                
                # Aggregate par values by week and asset
                weekly_summary = combined_weekly_df.groupby(["week", "clean_name"])["par_value"].mean().reset_index()
                
                # Export button for weekly data
                if st.button(f"Export {fund_symbol} Weekly Summary", key=f"{fund_symbol}_weekly"):
                    st.session_state[f"{fund_symbol}_weekly_export"] = weekly_summary
                    st.session_state[f"{fund_symbol}_weekly_filename"] = f"{fund_symbol}_aos_weekly_summary_{datetime.now().strftime('%Y%m%d')}.csv"
                
                if f"{fund_symbol}_weekly_export" in st.session_state:
                    st.sidebar.download_button(
                        label=f"📥 Download {fund_symbol} Weekly CSV",
                        data=st.session_state[f"{fund_symbol}_weekly_export"].to_csv(index=False),
                        file_name=st.session_state[f"{fund_symbol}_weekly_filename"],
                        mime="text/csv",
                        key=f"{fund_symbol}_weekly_download"
                    )
                
                # Create stacked bar chart
                stacked_bar_chart = alt.Chart(weekly_summary).mark_bar().encode(
                    x=alt.X("week:N", title="Week", sort=alt.SortField("week", order="ascending"), 
                            axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("par_value:Q", title="Average Par Value"),
                    color=alt.Color("clean_name:N", title="Asset"),
                    tooltip=["week:N", "clean_name:N", "par_value:Q"]
                ).properties(height=400)
                
                st.altair_chart(stacked_bar_chart, use_container_width=True)
            else:
                st.info(f"Not enough {fund_symbol} historical data available for weekly analysis.")

            # === Custom Index Calculation ===
            st.markdown(f"### 📈 {fund_symbol} Custom Index: Weighted AOS Holdings")

            st.markdown("#### All AOS Corporate Finance assets, weighted by market value (showing daily % changes)")

            # Date range selector for the chart
            st.markdown("**Select Date Range:**")
            date_range_option = st.radio(
                "Choose date range:",
                ["Last 60 Trading Days", "Last 30 Trading Days", "Last 90 Trading Days", "All Available Data"],
                horizontal=True,
                key=f"{fund_symbol}_date_range"
            )

            # Use all AOS Corporate Finance assets
            index_df = aos_df.copy() 

            # Filter by selected date range
            if date_range_option != "All Available Data":
                # Get all available trading days (sorted descending)
                all_trading_days = sorted(index_df["date"].dt.date.unique(), reverse=True)
                
                # Determine number of days based on selection
                if date_range_option == "Last 60 Trading Days":
                    num_days = 60
                elif date_range_option == "Last 30 Trading Days":
                    num_days = 30
                elif date_range_option == "Last 90 Trading Days":
                    num_days = 90
                
                # Get the last N trading days
                selected_trading_days = all_trading_days[:num_days]
                
                # Filter the dataframe to only include these dates
                index_df = index_df[index_df["date"].dt.date.isin(selected_trading_days)].copy()
                
                st.info(f"Showing data for {len(selected_trading_days)} trading days from {min(selected_trading_days)} to {max(selected_trading_days)}")

            # Add clean names for individual asset tracking
            index_df["clean_name"] = index_df["name"].apply(create_clean_name)

            # Calculate weighted index
            index_df["weight"] = index_df["market_value"]
            index_df["price_weighted"] = index_df["price"] * index_df["weight"]

            index_daily = index_df.groupby("date").agg(
                total_mv=("market_value", "sum"),
                weighted_price=("price_weighted", "sum")
            ).reset_index()

            index_daily["Weighted Index"] = index_daily["weighted_price"] / index_daily["total_mv"]

            # Sort by date and calculate percentage changes
            index_daily_sorted = index_daily.sort_values("date").copy()
            index_daily_sorted["Weighted Index % Change"] = index_daily_sorted["Weighted Index"].pct_change() * 100

            # Calculate moving averages for the percentage changes
            index_daily_sorted["MA_30"] = index_daily_sorted["Weighted Index % Change"].rolling(window=30, min_periods=1).mean()
            index_daily_sorted["MA_60"] = index_daily_sorted["Weighted Index % Change"].rolling(window=60, min_periods=1).mean()
            index_daily_sorted["MA_200"] = index_daily_sorted["Weighted Index % Change"].rolling(window=200, min_periods=1).mean()

            # Export button for index data
            if st.button(f"Export {fund_symbol} Weighted Index Data", key=f"{fund_symbol}_index"):
                index_export = index_daily_sorted[["date", "Weighted Index", "Weighted Index % Change", "MA_30", "MA_60", "MA_200"]].copy()
                index_export["date"] = index_export["date"].dt.strftime("%Y-%m-%d")
                st.session_state[f"{fund_symbol}_index_export"] = index_export
                st.session_state[f"{fund_symbol}_index_filename"] = f"{fund_symbol}_weighted_index_pct_changes_{datetime.now().strftime('%Y%m%d')}.csv"

            if f"{fund_symbol}_index_export" in st.session_state:
                st.sidebar.download_button(
                    label=f"📥 Download {fund_symbol} Index CSV",
                    data=st.session_state[f"{fund_symbol}_index_export"].to_csv(index=False),
                    file_name=st.session_state[f"{fund_symbol}_index_filename"],
                    mime="text/csv",
                    key=f"{fund_symbol}_index_download"
                )

            # Prepare individual asset percentage changes for charting
            individual_pct_changes = index_df.sort_values(["clean_name", "date"]).copy()
            individual_pct_changes["price_pct_change"] = individual_pct_changes.groupby("clean_name")["price"].pct_change() * 100

            # Pivot individual asset percentage changes
            individual_pct_pivot = individual_pct_changes.pivot_table(
                index="date", 
                columns="clean_name", 
                values="price_pct_change", 
                aggfunc="first"
            ).reset_index()

            # Combine weighted index percentage changes with individual asset percentage changes
            chart_data = individual_pct_pivot.merge(
                index_daily_sorted[["date", "Weighted Index % Change", "MA_30", "MA_60", "MA_200"]], 
                on="date", 
                how="left"
            )

            # Rename moving averages for better display
            chart_data = chart_data.rename(columns={
                "Weighted Index % Change": "Weighted Index",
                "MA_30": "30-Day MA",
                "MA_60": "60-Day MA", 
                "MA_200": "200-Day MA"
            })

            # Melt the data for charting
            chart_data_melted = chart_data.melt(
                id_vars=["date"], 
                var_name="Asset", 
                value_name="Percentage_Change"
            )

            # Remove NaN values for cleaner chart
            chart_data_melted = chart_data_melted.dropna(subset=["Percentage_Change"])

            # Create separate datasets for main lines and moving averages
            main_data = chart_data_melted[~chart_data_melted['Asset'].isin(['30-Day MA', '60-Day MA', '200-Day MA'])].copy()
            ma_data = chart_data_melted[chart_data_melted['Asset'].isin(['30-Day MA', '60-Day MA', '200-Day MA'])].copy()

            # Individual assets and weighted index as solid lines
            main_lines = alt.Chart(main_data).mark_line(strokeWidth=2).encode(
                x=alt.X("date:T", 
                        title="Date",
                        axis=alt.Axis(
                            labelAngle=-45, 
                            format="%m/%d/%y",
                            labelOverlap=False,
                            tickCount=10
                        )),
                y=alt.Y("Percentage_Change:Q", 
                        title="Daily % Change", 
                        scale=alt.Scale(zero=False)),
                color=alt.Color("Asset:N", title="Asset", scale=alt.Scale(scheme="category20")),
                tooltip=["date:T", "Asset:N", alt.Tooltip("Percentage_Change:Q", format=".2f", title="% Change")]
            )

            # Moving averages as dashed lines
            ma_lines = alt.Chart(ma_data).mark_line(strokeDash=[5,5], opacity=0.7, strokeWidth=2).encode(
                x=alt.X("date:T", 
                        title="Date",
                        axis=alt.Axis(
                            labelAngle=-45, 
                            format="%m/%d/%y",
                            labelOverlap=False,
                            tickCount=10
                        )),
                y=alt.Y("Percentage_Change:Q", 
                        title="Daily % Change",
                        scale=alt.Scale(zero=False)),
                color=alt.Color("Asset:N", title="Asset", scale=alt.Scale(scheme="set2")),
                tooltip=["date:T", "Asset:N", alt.Tooltip("Percentage_Change:Q", format=".2f", title="% Change")]
            )

            # Add horizontal line at 0%
            zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray', strokeDash=[2,2], opacity=0.5).encode(
                y=alt.Y('y:Q')
            )

            # Combine all chart elements
            combined_chart = (main_lines + ma_lines + zero_line).properties(
                height=500,
                title=f"{fund_symbol} Daily Percentage Changes - AOS Corporate Finance Assets"
            ).resolve_scale(
                color='independent'
            )

            st.altair_chart(combined_chart, use_container_width=True)

            # === Last 5 Business Days Price Chart ===
            st.markdown(f"### 📈 {fund_symbol} AOS Corporate Finance % Changes - Last 5 Business Days")

            # Get the last 5 business days from available dates
            sorted_dates = sorted(df["date"].dt.date.unique(), reverse=True)
            last_5_dates = sorted_dates[:5]

            # Prepare data for last 5 days with percentage changes
            last_5_base_df = aos_df.copy()

            # Filter and add clean names
            last_5_base_df["clean_name"] = last_5_base_df["name"].apply(create_clean_name)

            # Sort and calculate percentage changes for the last 5 days data
            last_5_sorted_df = last_5_base_df.sort_values(["clean_name", "date"]).copy()
            last_5_sorted_df["price_pct_change"] = last_5_sorted_df.groupby("clean_name")["price"].pct_change() * 100

            # Filter for last 5 business days
            last_5_df = last_5_sorted_df[last_5_sorted_df["date"].dt.date.isin(last_5_dates)].copy()

            # Export button for last 5 days data
            if st.button(f"Export {fund_symbol} Last 5 Days Data", key=f"{fund_symbol}_last5"):
                last_5_export = last_5_df[["date", "clean_name", "price", "price_pct_change", "market_value", "par_value"]].copy()
                last_5_export["date"] = last_5_export["date"].dt.strftime("%Y-%m-%d")
                st.session_state[f"{fund_symbol}_last_5_export"] = last_5_export
                st.session_state[f"{fund_symbol}_last_5_filename"] = f"{fund_symbol}_last_5_days_{datetime.now().strftime('%Y%m%d')}.csv"

            if f"{fund_symbol}_last_5_export" in st.session_state:
                st.sidebar.download_button(
                    label=f"📥 Download {fund_symbol} Last 5 Days CSV",
                    data=st.session_state[f"{fund_symbol}_last_5_export"].to_csv(index=False),
                    file_name=st.session_state[f"{fund_symbol}_last_5_filename"],
                    mime="text/csv",
                    key=f"{fund_symbol}_last_5_download"
                )

            # Filter out NaN percentage changes for the chart
            last_5_df_clean = last_5_df.dropna(subset=["price_pct_change"])

            # Create the chart for last 5 business days showing percentage changes
            if not last_5_df_clean.empty:
                last_5_chart = alt.Chart(last_5_df_clean).mark_line(point=True).encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("price_pct_change:Q", title="Daily % Change", scale=alt.Scale(zero=False)),
                    color=alt.Color("clean_name:N", title="Asset"),
                    tooltip=["date:T", "clean_name:N", alt.Tooltip("price_pct_change:Q", format=".2f", title="% Change")]
                ).properties(height=400)

                # Add horizontal line at 0%
                zero_line_last5 = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='gray', strokeDash=[2,2], opacity=0.5).encode(
                    y=alt.Y('y:Q')
                )

                # Combine chart with zero line
                last_5_combined = (last_5_chart + zero_line_last5)

                st.altair_chart(last_5_combined, use_container_width=True)
            else:
                st.info(f"No {fund_symbol} AOS data available for the last 5 business days")
        else:
            st.info(f"No {fund_symbol} AOS Corporate Finance data available for selected date")
    else:
        st.info(f"No {fund_symbol} AOS Corporate Finance assets found in this fund")

    # === Disclosure ===
    st.markdown("---")
    st.markdown(f"""
    **Disclosure:** All information displayed here is public and is not in any way to be construed as investment advice or solicitation. 
    All {fund_symbol} data is sourced from {fund_info['url']} and we make no claims to veracity or accuracy of the data. 
    It is presented for academic and research purposes only.
    """)

# === Render Dashboards in Tabs ===
with tab1:
    df_priv = load_data("PRIV")
    render_fund_dashboard("PRIV", df_priv)

with tab2:
    df_prsd = load_data("PRSD")
    render_fund_dashboard("PRSD", df_prsd)