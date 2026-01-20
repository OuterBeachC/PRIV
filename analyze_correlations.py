#!/usr/bin/env python3
"""
Pricing Correlation Analysis: AOS Corporate Finance Assets vs Portfolio
Analyzes the correlation between individual AOS Corporate Finance asset prices
and the overall portfolio pricing changes.
"""

import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

# Connect to database
conn = sqlite3.connect("priv_data.db")

# Load all data
print("Loading data from database...")
df = pd.read_sql("SELECT * FROM financial_data", conn)
conn.close()

print(f"Total records loaded: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSource identifiers: {df['source_identifier'].unique()}")
print(f"Asset breakdown types: {df['asset_breakdown'].unique()}")

# Convert date to datetime
df["date"] = pd.to_datetime(df["date"])

# Calculate price for all assets
df["price"] = df["market_value"] / df["par_value"] * 100

print("\n" + "="*80)
print("PRICING CORRELATION ANALYSIS: AOS CORPORATE FINANCE ASSETS")
print("="*80)

# Analyze each fund separately
for fund in df["source_identifier"].unique():
    print(f"\n{'='*80}")
    print(f"FUND: {fund}")
    print(f"{'='*80}")

    fund_df = df[df["source_identifier"] == fund].copy()

    # Filter AOS Corporate Finance assets
    aos_df = fund_df[fund_df["asset_breakdown"] == "AOS Corporate Finance"].copy()

    if aos_df.empty:
        print(f"No AOS Corporate Finance assets found in {fund}")
        continue

    print(f"\nAOS Corporate Finance assets in {fund}: {aos_df['name'].nunique()}")
    print(f"Date range: {aos_df['date'].min().date()} to {aos_df['date'].max().date()}")
    print(f"Total observations: {len(aos_df)}")

    # Get unique AOS assets
    aos_assets = aos_df['name'].unique()
    print(f"\nAssets:")
    for i, asset in enumerate(aos_assets, 1):
        print(f"  {i}. {asset}")

    # Calculate overall portfolio price (weighted by market value)
    portfolio_daily = fund_df.groupby("date").apply(
        lambda x: (x["market_value"] * (x["market_value"] / x["par_value"] * 100)).sum() / x["market_value"].sum()
    ).reset_index(name="portfolio_price")

    # Calculate AOS-only portfolio price
    aos_portfolio_daily = aos_df.groupby("date").apply(
        lambda x: (x["market_value"] * (x["market_value"] / x["par_value"] * 100)).sum() / x["market_value"].sum()
    ).reset_index(name="aos_portfolio_price")

    # Calculate price changes
    portfolio_daily = portfolio_daily.sort_values("date")
    portfolio_daily["portfolio_pct_change"] = portfolio_daily["portfolio_price"].pct_change() * 100

    aos_portfolio_daily = aos_portfolio_daily.sort_values("date")
    aos_portfolio_daily["aos_portfolio_pct_change"] = aos_portfolio_daily["aos_portfolio_price"].pct_change() * 100

    # Create price change data for each AOS asset
    correlations = []

    for asset in aos_assets:
        asset_df = aos_df[aos_df["name"] == asset].copy()
        asset_df = asset_df.sort_values("date")
        asset_df["asset_pct_change"] = asset_df["price"].pct_change() * 100

        # Merge with portfolio changes
        merged = asset_df.merge(portfolio_daily, on="date", how="inner")
        merged = merged.merge(aos_portfolio_daily, on="date", how="inner")

        # Remove NaN values
        merged_clean = merged.dropna(subset=["asset_pct_change", "portfolio_pct_change", "aos_portfolio_pct_change"])

        if len(merged_clean) > 1:
            # Calculate correlations
            corr_overall = merged_clean["asset_pct_change"].corr(merged_clean["portfolio_pct_change"])
            corr_aos = merged_clean["asset_pct_change"].corr(merged_clean["aos_portfolio_pct_change"])

            # Calculate volatility metrics
            asset_volatility = merged_clean["asset_pct_change"].std()
            portfolio_volatility = merged_clean["portfolio_pct_change"].std()

            # Average market value
            avg_mv = asset_df["market_value"].mean()

            correlations.append({
                "Asset": asset[:60] + "..." if len(asset) > 60 else asset,
                "Full_Name": asset,
                "Correlation_vs_Portfolio": corr_overall,
                "Correlation_vs_AOS_Portfolio": corr_aos,
                "Asset_Volatility": asset_volatility,
                "Portfolio_Volatility": portfolio_volatility,
                "Avg_Market_Value": avg_mv,
                "Observations": len(merged_clean)
            })

    # Create correlation dataframe
    if correlations:
        corr_df = pd.DataFrame(correlations)
        corr_df = corr_df.sort_values("Correlation_vs_Portfolio", ascending=False)

        print(f"\n{'-'*80}")
        print(f"CORRELATION ANALYSIS RESULTS FOR {fund}")
        print(f"{'-'*80}")

        print(f"\nTop 5 Assets Most Correlated with Overall Portfolio:")
        print(corr_df[["Asset", "Correlation_vs_Portfolio", "Avg_Market_Value", "Observations"]].head(5).to_string(index=False))

        print(f"\nTop 5 Assets Least Correlated (or Negatively Correlated) with Overall Portfolio:")
        print(corr_df[["Asset", "Correlation_vs_Portfolio", "Avg_Market_Value", "Observations"]].tail(5).to_string(index=False))

        print(f"\nCorrelation with AOS Portfolio vs Overall Portfolio:")
        print(corr_df[["Asset", "Correlation_vs_Portfolio", "Correlation_vs_AOS_Portfolio"]].to_string(index=False))

        print(f"\nVolatility Analysis:")
        print(corr_df[["Asset", "Asset_Volatility", "Portfolio_Volatility"]].to_string(index=False))

        # Summary statistics
        print(f"\n{'-'*80}")
        print(f"SUMMARY STATISTICS FOR {fund}")
        print(f"{'-'*80}")
        print(f"Average Correlation (vs Portfolio): {corr_df['Correlation_vs_Portfolio'].mean():.4f}")
        print(f"Median Correlation (vs Portfolio): {corr_df['Correlation_vs_Portfolio'].median():.4f}")
        print(f"Std Dev of Correlations: {corr_df['Correlation_vs_Portfolio'].std():.4f}")
        print(f"Min Correlation: {corr_df['Correlation_vs_Portfolio'].min():.4f}")
        print(f"Max Correlation: {corr_df['Correlation_vs_Portfolio'].max():.4f}")

        print(f"\nAverage Correlation (vs AOS Portfolio): {corr_df['Correlation_vs_AOS_Portfolio'].mean():.4f}")
        print(f"Median Correlation (vs AOS Portfolio): {corr_df['Correlation_vs_AOS_Portfolio'].median():.4f}")

        print(f"\nAverage Asset Volatility: {corr_df['Asset_Volatility'].mean():.4f}%")
        print(f"Portfolio Volatility: {corr_df['Portfolio_Volatility'].iloc[0]:.4f}%")

        # Save detailed results to CSV
        output_file = f"{fund}_aos_correlation_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
        corr_df.to_csv(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")

        # Create correlation matrix for visualization
        print(f"\n{'-'*80}")
        print(f"CREATING CORRELATION VISUALIZATIONS FOR {fund}")
        print(f"{'-'*80}")

        # Prepare data for correlation matrix
        price_changes_dict = {"Date": portfolio_daily["date"].values}
        price_changes_dict["Overall_Portfolio"] = portfolio_daily["portfolio_pct_change"].values
        price_changes_dict["AOS_Portfolio"] = aos_portfolio_daily.set_index("date").reindex(portfolio_daily["date"])["aos_portfolio_pct_change"].values

        for asset in aos_assets:
            asset_df = aos_df[aos_df["name"] == asset].copy()
            asset_df = asset_df.sort_values("date")
            asset_df["asset_pct_change"] = asset_df["price"].pct_change() * 100

            # Create short name
            short_name = asset[:30] + "..." if len(asset) > 30 else asset

            # Align with portfolio dates
            asset_indexed = asset_df.set_index("date")["asset_pct_change"].reindex(portfolio_daily["date"])
            price_changes_dict[short_name] = asset_indexed.values

        price_changes_df = pd.DataFrame(price_changes_dict)

        # Calculate correlation matrix
        correlation_matrix = price_changes_df.drop("Date", axis=1).corr()

        # Save correlation matrix
        corr_matrix_file = f"{fund}_correlation_matrix_{datetime.now().strftime('%Y%m%d')}.csv"
        correlation_matrix.to_csv(corr_matrix_file)
        print(f"Correlation matrix saved to: {corr_matrix_file}")

        # Create heatmap
        plt.figure(figsize=(14, 12))
        sns.heatmap(correlation_matrix, annot=True, fmt='.2f', cmap='RdYlGn', center=0,
                    square=True, linewidths=0.5, cbar_kws={"shrink": 0.8})
        plt.title(f'{fund} - AOS Corporate Finance Price Change Correlations', fontsize=14, fontweight='bold')
        plt.tight_layout()
        heatmap_file = f"{fund}_correlation_heatmap_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(heatmap_file, dpi=300, bbox_inches='tight')
        print(f"Correlation heatmap saved to: {heatmap_file}")
        plt.close()

        # Create scatter plots for top correlated assets
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'{fund} - Asset Price Changes vs Portfolio Price Changes', fontsize=14, fontweight='bold')

        top_4_assets = corr_df.head(4)

        for idx, (_, row) in enumerate(top_4_assets.iterrows()):
            ax = axes[idx // 2, idx % 2]

            asset_name = row["Full_Name"]
            asset_df = aos_df[aos_df["name"] == asset_name].copy()
            asset_df = asset_df.sort_values("date")
            asset_df["asset_pct_change"] = asset_df["price"].pct_change() * 100

            merged = asset_df.merge(portfolio_daily, on="date", how="inner")
            merged_clean = merged.dropna(subset=["asset_pct_change", "portfolio_pct_change"])

            ax.scatter(merged_clean["portfolio_pct_change"], merged_clean["asset_pct_change"],
                      alpha=0.6, s=50)

            # Add trend line
            if len(merged_clean) > 1:
                z = np.polyfit(merged_clean["portfolio_pct_change"], merged_clean["asset_pct_change"], 1)
                p = np.poly1d(z)
                x_line = np.linspace(merged_clean["portfolio_pct_change"].min(),
                                    merged_clean["portfolio_pct_change"].max(), 100)
                ax.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2)

            ax.set_xlabel("Portfolio % Change", fontsize=10)
            ax.set_ylabel("Asset % Change", fontsize=10)
            short_name = asset_name[:40] + "..." if len(asset_name) > 40 else asset_name
            ax.set_title(f"{short_name}\nCorr: {row['Correlation_vs_Portfolio']:.3f}", fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5, alpha=0.3)
            ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5, alpha=0.3)

        plt.tight_layout()
        scatter_file = f"{fund}_correlation_scatterplots_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(scatter_file, dpi=300, bbox_inches='tight')
        print(f"Scatter plots saved to: {scatter_file}")
        plt.close()

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
