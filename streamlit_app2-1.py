import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
import io

st.set_page_config(layout="wide")
st.title("📊 Financial Holdings: Multi-Fund Dashboard")

# === Load Data Function ===
@st.cache_data
def load_data(fund_symbol):
    conn = sqlite3.connect("priv_data.db")
    
    try:
        # Filter by source_identifier column (using parameterized query to prevent SQL injection)
        df = pd.read_sql(
            "SELECT * FROM financial_data WHERE source_identifier = ?",
            conn,
            params=(fund_symbol,)
        )
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        st.error(f"Error loading data for {fund_symbol}: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

# === Date Filter Section on Main Page ===
st.markdown("---")

# Preload dates for all funds
df_priv_dates = load_data("PRIV")
df_prsd_dates = load_data("PRSD")
df_hiys_dates = load_data("HIYS")

available_dates_priv = sorted(df_priv_dates["date"].dt.date.unique(), reverse=True) if not df_priv_dates.empty else []
available_dates_prsd = sorted(df_prsd_dates["date"].dt.date.unique(), reverse=True) if not df_prsd_dates.empty else []
available_dates_hiys = sorted(df_hiys_dates["date"].dt.date.unique(), reverse=True) if not df_hiys_dates.empty else []

col_date_priv, col_date_prsd, col_date_hiys = st.columns(3)

with col_date_priv:
    if available_dates_priv:
        selected_date_priv = st.selectbox("📅 PRIV Current Date", available_dates_priv, key="main_priv_date")

with col_date_prsd:
    if available_dates_prsd:
        selected_date_prsd = st.selectbox("📅 PRSD Current Date", available_dates_prsd, key="main_prsd_date")

with col_date_hiys:
    if available_dates_hiys:
        selected_date_hiys = st.selectbox("📅 HIYS Current Date", available_dates_hiys, key="main_hiys_date")

st.markdown("---")

# === Fund Configuration ===
FUND_CONFIG = {
    "PRIV": {
        "name": "SPDR® SSGA IG Public & Private Credit ETF",
        "url": "https://www.ssga.com/us/en/intermediary/etfs/spdr-ssga-ig-public-private-credit-etf-priv"
    },
    "PRSD": {
        "name": "State Street® Short Duration IG Public & Private Credit ETF", 
        "url": "https://www.ssga.com/us/en/intermediary/etfs/state-street-short-duration-ig-public-private-credit-etf-prsd"
    },
    "HIYS": {
        "name": "Invesco High Yield Select ETF",
        "url": "https://www.invesco.com/us/en/financial-products/etfs/invesco-high-yield-select-etf.html"
    }
}

# === Sidebar Fund Selection for Combined Export Menu ===
st.sidebar.markdown("---")
st.sidebar.header("🔄 Combined Export Menu")

export_fund_selection = st.sidebar.radio(
    "Select Fund for Export",
    ["PRIV", "PRSD", "HIYS"],
    key="export_fund_selection"
)

# Load data for the selected export fund
export_df = load_data(export_fund_selection)

# === Bulk Export Options for Combined Menu ===
if not export_df.empty:
    asset_types = export_df["asset_breakdown"].dropna().unique()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"📦 {export_fund_selection} Bulk Export Options")

    bulk_export_type = st.sidebar.radio(
        f"{export_fund_selection} Bulk Export Type",
        ["All Data", "By Asset Type", "AOS Corporate Finance Only", "Date Range All Assets"],
        key=f"combined_bulk_type"
    )

    bulk_data = None
    bulk_filename = ""
    
    if bulk_export_type == "All Data":
        bulk_data = export_df.copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"{export_fund_selection}_all_financial_data_{datetime.now().strftime('%Y%m%d')}.csv"
        
    elif bulk_export_type == "By Asset Type":
        selected_bulk_types = st.sidebar.multiselect(f"Select {export_fund_selection} Asset Types for Bulk Export", asset_types, key=f"combined_bulk_types")
        if selected_bulk_types:
            bulk_data = export_df[export_df["asset_breakdown"].isin(selected_bulk_types)].copy()
            bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
            bulk_filename = f"{export_fund_selection}_bulk_export_{'_'.join(selected_bulk_types)}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    elif bulk_export_type == "AOS Corporate Finance Only":
        bulk_data = export_df[export_df["asset_breakdown"] == "AOS Corporate Finance"].copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"{export_fund_selection}_aos_corporate_finance_{datetime.now().strftime('%Y%m%d')}.csv"
        
    elif bulk_export_type == "Date Range All Assets":
        min_date = export_df["date"].dt.date.min()
        max_date = export_df["date"].dt.date.max()
        bulk_start = st.sidebar.date_input(f"{export_fund_selection} Bulk Start Date", value=min_date, key=f"combined_bulk_start")
        bulk_end = st.sidebar.date_input(f"{export_fund_selection} Bulk End Date", value=max_date, key=f"combined_bulk_end")
        
        bulk_data = export_df[
            (export_df["date"].dt.date >= bulk_start) & 
            (export_df["date"].dt.date <= bulk_end)
        ].copy()
        bulk_data["price"] = bulk_data["market_value"] / bulk_data["par_value"] * 100
        bulk_filename = f"{export_fund_selection}_date_range_export_{bulk_start}_{bulk_end}.csv"
    
    # Direct download button
    st.sidebar.markdown("---")
    if bulk_data is not None and not bulk_data.empty:
        # Format date for export
        bulk_data["date"] = bulk_data["date"].dt.strftime("%Y-%m-%d")
        
        csv_buffer = io.StringIO()
        bulk_data.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.sidebar.download_button(
            label=f"📥 Download {export_fund_selection} Export",
            data=csv_data,
            file_name=bulk_filename,
            mime="text/csv",
            key=f"combined_bulk_download"
        )
    else:
        st.sidebar.info("Select options above to generate export")

# === Create Tabs ===
tab1, tab2, tab3 = st.tabs(["📈 PRIV", "📊 PRSD", "🔄 HIYS Comparison"])

# === Function to render dashboard for a specific fund ===
def render_fund_dashboard(fund_symbol, df, selected_date):
    if df.empty:
        st.warning(f"No data available for {fund_symbol}")
        return
    
    fund_info = FUND_CONFIG[fund_symbol]
    st.markdown(f"### {fund_info['name']} ({fund_symbol})")
    
    # Get all available dates
    available_dates = sorted(df["date"].dt.date.unique(), reverse=True)
    
    # Get previous available date
    if selected_date and selected_date in available_dates:
        current_idx = available_dates.index(selected_date)
        previous_date = available_dates[current_idx + 1] if current_idx + 1 < len(available_dates) else None
    else:
        previous_date = None

    # === Filter Data by Date (no asset type filtering) ===
    df_current = df[df["date"].dt.date == selected_date] if selected_date else pd.DataFrame()
    df_previous = df[df["date"].dt.date == previous_date] if previous_date else pd.DataFrame(columns=df.columns)

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
        if not new_assets.empty:
            export_new = new_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
            csv_buffer = io.StringIO()
            export_new.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            st.download_button(
                label="📥 New Assets",
                data=csv_data,
                file_name=f"{fund_symbol}_new_assets_{selected_date}.csv",
                mime="text/csv",
                key=f"{fund_symbol}_export_new"
            )
        else:
            st.info("No new assets")

    with col_export2:
        if not removed_assets.empty:
            export_removed = removed_assets.reset_index()[["name", "par_value", "market_value", "asset_breakdown"]]
            csv_buffer = io.StringIO()
            export_removed.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            st.download_button(
                label="📥 Removed Assets",
                data=csv_data,
                file_name=f"{fund_symbol}_removed_assets_{selected_date}.csv",
                mime="text/csv",
                key=f"{fund_symbol}_export_removed"
            )
        else:
            st.info("No removed assets")

    with col_export3:
        if not par_changes.empty:
            export_changes = par_changes.reset_index()[["name", "par_value_prev", "par_value", "par_change", "asset_breakdown"]]
            csv_buffer = io.StringIO()
            export_changes.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            st.download_button(
                label="📥 Par Changes",
                data=csv_data,
                file_name=f"{fund_symbol}_par_changes_{selected_date}.csv",
                mime="text/csv",
                key=f"{fund_symbol}_export_changes"
            )
        else:
            st.info("No par value changes")

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

        if not aos_current_date.empty:
            # Format the date column
            aos_current_date_display = aos_current_date.copy()
            aos_current_date_display["date_formatted"] = aos_current_date_display["date"].dt.strftime("%m/%d/%Y")

            st.dataframe(
                aos_current_date_display[
                    ["date_formatted", "name", "market_value", "par_value", "price", "price_pct_change", "market_value_change"]
                ].rename(columns={"date_formatted": "date"}),
                use_container_width=True,
                hide_index=True
            )

            # Export button for AOS current data
            aos_export = aos_current_date[
                ["date", "name", "market_value", "par_value", "price", "price_pct_change", "market_value_change"]
            ].copy()
            aos_export["date"] = aos_export["date"].dt.strftime("%Y-%m-%d")
            
            csv_buffer = io.StringIO()
            aos_export.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label=f"📥 Download {fund_symbol} AOS Current Data",
                data=csv_data,
                file_name=f"{fund_symbol}_aos_current_data_{selected_date}.csv",
                mime="text/csv",
                key=f"{fund_symbol}_aos_current_download"
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
                csv_buffer = io.StringIO()
                weekly_summary.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label=f"📥 Download {fund_symbol} Weekly Summary",
                    data=csv_data,
                    file_name=f"{fund_symbol}_aos_weekly_summary_{datetime.now().strftime('%Y%m%d')}.csv",
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
            index_export = index_daily_sorted[["date", "Weighted Index", "Weighted Index % Change", "MA_30", "MA_60", "MA_200"]].copy()
            index_export["date"] = index_export["date"].dt.strftime("%Y-%m-%d")
            
            csv_buffer = io.StringIO()
            index_export.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label=f"📥 Download {fund_symbol} Weighted Index Data",
                data=csv_data,
                file_name=f"{fund_symbol}_weighted_index_pct_changes_{datetime.now().strftime('%Y%m%d')}.csv",
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
            last_5_export = last_5_df[["date", "clean_name", "price", "price_pct_change", "market_value", "par_value"]].copy()
            last_5_export["date"] = last_5_export["date"].dt.strftime("%Y-%m-%d")
            
            csv_buffer = io.StringIO()
            last_5_export.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label=f"📥 Download {fund_symbol} Last 5 Days Data",
                data=csv_data,
                file_name=f"{fund_symbol}_last_5_days_{datetime.now().strftime('%Y%m%d')}.csv",
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


# === Function to render HIYS comparison dashboard ===
def render_hiys_comparison():
    st.markdown("### 🔄 AP Grange Holdings LLC - Cross-Fund Price Comparison")
    st.markdown("Compare the price (Market Value / Par Value × 100) of AP Grange Holdings LLC across PRIV, PRSD, and HIYS funds.")
    
    # Load data for all three funds
    df_priv = load_data("PRIV")
    df_prsd = load_data("PRSD")
    df_hiys = load_data("HIYS")
    
    # Function to extract AP Grange data and calculate price
    def get_ap_grange_data(df, fund_name):
        if df.empty:
            return pd.DataFrame()
        
        # Filter for AP Grange Holdings LLC (case-insensitive search)
        ap_grange_df = df[df["name"].str.upper().str.contains("AP GRANGE HOLDINGS", na=False)].copy()
        
        if ap_grange_df.empty:
            return pd.DataFrame()
        
        # Calculate price = market_value / par_value * 100
        ap_grange_df["price"] = ap_grange_df["market_value"] / ap_grange_df["par_value"] * 100
        ap_grange_df["fund"] = fund_name
        ap_grange_df["date"] = pd.to_datetime(ap_grange_df["date"])
        
        return ap_grange_df[["date", "name", "market_value", "par_value", "price", "fund"]]
    
    # Get AP Grange data from each fund
    priv_ap_grange = get_ap_grange_data(df_priv, "PRIV")
    prsd_ap_grange = get_ap_grange_data(df_prsd, "PRSD")
    hiys_ap_grange = get_ap_grange_data(df_hiys, "HIYS")
    
    # Combine all data
    all_ap_grange = pd.concat([priv_ap_grange, prsd_ap_grange, hiys_ap_grange], ignore_index=True)
    
    if all_ap_grange.empty:
        st.warning("No AP Grange Holdings LLC data found in any fund.")
        return
    
    # Sort by date
    all_ap_grange = all_ap_grange.sort_values(["fund", "date"])
    
    # Calculate daily price change per fund
    all_ap_grange["price_pct_change"] = all_ap_grange.groupby("fund")["price"].pct_change() * 100
    
    # === Summary Metrics ===
    st.markdown("---")
    st.subheader("📊 Current Price Comparison")
    
    col1, col2, col3 = st.columns(3)
    
    # Get latest price for each fund
    for col, fund_name, fund_df in [(col1, "PRIV", priv_ap_grange), 
                                      (col2, "PRSD", prsd_ap_grange), 
                                      (col3, "HIYS", hiys_ap_grange)]:
        with col:
            if not fund_df.empty:
                # Sort by date and calculate pct change for this fund
                fund_df_sorted = fund_df.sort_values("date").copy()
                fund_df_sorted["price_pct_change"] = fund_df_sorted["price"].pct_change() * 100
                
                latest = fund_df_sorted.iloc[-1]
                latest_pct = fund_df_sorted["price_pct_change"].iloc[-1] if len(fund_df_sorted) > 1 else None
                
                st.metric(
                    label=f"{fund_name} Price",
                    value=f"{latest['price']:.4f}",
                    delta=f"{latest_pct:.2f}%" if latest_pct is not None and pd.notna(latest_pct) else None
                )
                st.caption(f"As of {latest['date'].strftime('%m/%d/%Y')}")
            else:
                st.info(f"No {fund_name} data")
    
    # === Price Comparison Table ===
    st.markdown("---")
    st.subheader("📋 Asset-Level Price and Value Movements")
    
    # Create a comparison table with latest data from each fund
    comparison_data = []
    for fund_name, fund_df in [("PRIV", priv_ap_grange), ("PRSD", prsd_ap_grange), ("HIYS", hiys_ap_grange)]:
        if not fund_df.empty:
            # Sort and calculate pct change
            fund_df_sorted = fund_df.sort_values("date").copy()
            fund_df_sorted["price_pct_change"] = fund_df_sorted["price"].pct_change() * 100
            
            latest = fund_df_sorted.iloc[-1]
            latest_pct = fund_df_sorted["price_pct_change"].iloc[-1] if len(fund_df_sorted) > 1 else None
            
            comparison_data.append({
                "Fund": fund_name,
                "Date": latest["date"].strftime("%m/%d/%Y"),
                "Name": latest["name"],
                "Market Value": latest["market_value"],
                "Par Value": latest["par_value"],
                "Price": latest["price"],
                "Price % Change": latest_pct if pd.notna(latest_pct) else None
            })
    
    if comparison_data:
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        # Export button
        csv_buffer = io.StringIO()
        comparison_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Download Comparison Data",
            data=csv_data,
            file_name=f"ap_grange_comparison_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="hiys_comparison_download"
        )
    
    # === Price Over Time Chart ===
    st.markdown("---")
    st.subheader("📈 Price Comparison Over Time")
    
    if not all_ap_grange.empty:
        # Date range selector
        date_range_option = st.radio(
            "Choose date range:",
            ["Last 30 Days", "Last 60 Days", "Last 90 Days", "All Available Data"],
            horizontal=True,
            key="hiys_date_range"
        )
        
        chart_df = all_ap_grange.copy()
        
        if date_range_option != "All Available Data":
            all_dates = sorted(chart_df["date"].dt.date.unique(), reverse=True)
            
            if date_range_option == "Last 30 Days":
                num_days = 30
            elif date_range_option == "Last 60 Days":
                num_days = 60
            elif date_range_option == "Last 90 Days":
                num_days = 90
            
            selected_dates = all_dates[:num_days]
            chart_df = chart_df[chart_df["date"].dt.date.isin(selected_dates)]
        
        # Price chart
        price_chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=2).encode(
            x=alt.X("date:T", title="Date", axis=alt.Axis(labelAngle=-45, format="%m/%d/%y")),
            y=alt.Y("price:Q", title="Price (MV/PV × 100)", scale=alt.Scale(zero=False)),
            color=alt.Color("fund:N", title="Fund", scale=alt.Scale(
                domain=["PRIV", "PRSD", "HIYS"],
                range=["#1f77b4", "#ff7f0e", "#2ca02c"]
            )),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%m/%d/%Y"),
                alt.Tooltip("fund:N", title="Fund"),
                alt.Tooltip("price:Q", title="Price", format=".4f"),
                alt.Tooltip("market_value:Q", title="Market Value", format="$,.2f"),
                alt.Tooltip("par_value:Q", title="Par Value", format="$,.2f")
            ]
        ).properties(height=400, title="AP Grange Holdings LLC - Price Comparison Across Funds")
        
        st.altair_chart(price_chart, use_container_width=True)
        
        # === Price Percentage Change Chart ===
        st.markdown("### 📉 Daily Price % Change Comparison")
        
        pct_change_df = chart_df.dropna(subset=["price_pct_change"])
        
        if not pct_change_df.empty:
            pct_chart = alt.Chart(pct_change_df).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X("date:T", title="Date", axis=alt.Axis(labelAngle=-45, format="%m/%d/%y")),
                y=alt.Y("price_pct_change:Q", title="Daily % Change", scale=alt.Scale(zero=False)),
                color=alt.Color("fund:N", title="Fund", scale=alt.Scale(
                    domain=["PRIV", "PRSD", "HIYS"],
                    range=["#1f77b4", "#ff7f0e", "#2ca02c"]
                )),
                tooltip=[
                    alt.Tooltip("date:T", title="Date", format="%m/%d/%Y"),
                    alt.Tooltip("fund:N", title="Fund"),
                    alt.Tooltip("price_pct_change:Q", title="% Change", format=".2f")
                ]
            )
            
            # Add zero line
            zero_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='gray', strokeDash=[2,2], opacity=0.5
            ).encode(y=alt.Y('y:Q'))
            
            combined_pct_chart = (pct_chart + zero_line).properties(
                height=400, 
                title="AP Grange Holdings LLC - Daily % Change Comparison"
            )
            
            st.altair_chart(combined_pct_chart, use_container_width=True)
        
        # === Historical Data Table ===
        st.markdown("---")
        st.subheader("📜 Historical Data")
        
        # Pivot table showing prices by date and fund
        pivot_df = chart_df.pivot_table(
            index="date",
            columns="fund",
            values="price",
            aggfunc="first"
        ).reset_index()
        
        pivot_df["date"] = pivot_df["date"].dt.strftime("%m/%d/%Y")
        pivot_df = pivot_df.sort_values("date", ascending=False)
        
        st.dataframe(pivot_df, use_container_width=True, hide_index=True)
        
        # Export historical data
        export_df = all_ap_grange.copy()
        export_df["date"] = export_df["date"].dt.strftime("%Y-%m-%d")
        
        csv_buffer = io.StringIO()
        export_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Download Full Historical Data",
            data=csv_data,
            file_name=f"ap_grange_historical_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="hiys_historical_download"
        )
    
    # === Disclosure ===
    st.markdown("---")
    st.markdown("""
    **Disclosure:** All information displayed here is public and is not in any way to be construed as investment advice or solicitation. 
    Data is sourced from SSGA (PRIV, PRSD) and Invesco (HIYS) and we make no claims to veracity or accuracy of the data. 
    It is presented for academic and research purposes only.
    """)


# === Render Dashboards in Tabs ===
with tab1:
    df_priv = load_data("PRIV")
    render_fund_dashboard("PRIV", df_priv, selected_date_priv if 'selected_date_priv' in locals() else None)

with tab2:
    df_prsd = load_data("PRSD")
    render_fund_dashboard("PRSD", df_prsd, selected_date_prsd if 'selected_date_prsd' in locals() else None)

with tab3:
    render_hiys_comparison()