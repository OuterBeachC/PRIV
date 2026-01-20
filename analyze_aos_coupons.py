#!/usr/bin/env python3
"""
Analyze AOS Corporate Finance bond coupon payments and frequency
"""

import sqlite3
import csv
from datetime import datetime
from collections import defaultdict, Counter

def analyze_aos_coupons():
    """Analyze coupon payment schedules for AOS Corporate Finance bonds"""

    # Connect to database
    conn = sqlite3.connect("priv_data.db")
    cursor = conn.cursor()

    try:
        # Query all AOS Corporate Finance bonds
        query = """
        SELECT
            name,
            identifier,
            sedol,
            coupon,
            maturity,
            date as observation_date
        FROM financial_data
        WHERE asset_breakdown = 'AOS Corporate Finance'
        ORDER BY name, date DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("No AOS Corporate Finance bonds found in the database.")
            return

        print("=" * 80)
        print("AOS CORPORATE FINANCE BOND COUPON ANALYSIS")
        print("=" * 80)

        # Group by bond name to get latest data and count unique bonds
        bonds_data = {}
        all_bonds_history = defaultdict(list)

        for row in rows:
            name, identifier, sedol, coupon, maturity, obs_date = row
            if name not in bonds_data:
                bonds_data[name] = {
                    'name': name,
                    'identifier': identifier,
                    'sedol': sedol,
                    'coupon': coupon,
                    'maturity': maturity,
                    'observation_date': obs_date
                }
            all_bonds_history[name].append({
                'coupon': coupon,
                'maturity': maturity,
                'observation_date': obs_date
            })

        print(f"\nTotal unique AOS Corporate Finance bonds: {len(bonds_data)}\n")

        # Bond details
        print("\n" + "=" * 80)
        print("BOND DETAILS (Most Recent Observation)")
        print("=" * 80)

        bond_list = list(bonds_data.values())
        for idx, bond in enumerate(bond_list, 1):
            print(f"\n{idx}. {bond['name']}")
            print(f"   Identifier: {bond['identifier']}")
            print(f"   SEDOL: {bond['sedol']}")
            print(f"   Coupon: {bond['coupon']}")
            print(f"   Maturity: {bond['maturity']}")
            print(f"   Last Observed: {bond['observation_date']}")

        # Analyze coupon rates
        print("\n" + "=" * 80)
        print("COUPON RATE ANALYSIS")
        print("=" * 80)

        coupon_counter = Counter([bond['coupon'] for bond in bond_list])
        print(f"\nCoupon rate distribution:")
        for coupon, count in coupon_counter.most_common():
            print(f"  {coupon}: {count} bond(s)")

        # Analyze maturity dates
        print("\n" + "=" * 80)
        print("MATURITY DATE ANALYSIS")
        print("=" * 80)

        maturity_counter = Counter([bond['maturity'] for bond in bond_list])
        print(f"\nMaturity date distribution:")
        for maturity, count in maturity_counter.most_common():
            print(f"  {maturity}: {count} bond(s)")

        # Infer coupon payment frequency
        print("\n" + "=" * 80)
        print("COUPON PAYMENT FREQUENCY ANALYSIS")
        print("=" * 80)
        print("\nNote: Coupon payment frequency is typically inferred from bond characteristics.")
        print("Common frequencies in corporate bonds:")
        print("  - Semi-annual (every 6 months) - Most common for US corporate bonds")
        print("  - Quarterly (every 3 months)")
        print("  - Annual (once per year)")
        print("\nBased on the coupon rates shown above:")

        for bond in bond_list:
            coupon = bond['coupon']
            print(f"\n{bond['name'][:70]}...")
            print(f"  Coupon: {coupon}")

            # Try to parse coupon as a number
            try:
                if isinstance(coupon, str):
                    coupon_clean = coupon.replace('%', '').strip()
                    coupon_rate = float(coupon_clean)
                elif coupon is None:
                    print(f"  Coupon data not available")
                    continue
                else:
                    coupon_rate = float(coupon)

                print(f"  Annual coupon rate: {coupon_rate}%")
                print(f"  Likely payment frequency: Semi-annual (typical for US corporate bonds)")
                print(f"  Estimated semi-annual payment: {coupon_rate/2:.4f}% per period")
            except (ValueError, AttributeError, TypeError) as e:
                print(f"  Unable to parse coupon rate: {coupon}")

        # Export to CSV
        output_file = f"aos_coupon_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['name', 'identifier', 'sedol', 'coupon', 'maturity', 'observation_date']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for bond in bond_list:
                writer.writerow(bond)

        print(f"\n{'=' * 80}")
        print(f"Detailed data exported to: {output_file}")
        print("=" * 80)

        # Additional analysis - check for patterns in historical data
        print("\n" + "=" * 80)
        print("HISTORICAL OBSERVATION ANALYSIS")
        print("=" * 80)

        # Analyze first 3 bonds as sample
        sample_bonds = list(bonds_data.keys())[:3]
        for bond_name in sample_bonds:
            history = all_bonds_history[bond_name]
            print(f"\n{bond_name[:70]}...")
            print(f"  Number of observations: {len(history)}")

            dates = [h['observation_date'] for h in history]
            print(f"  Date range: {min(dates)} to {max(dates)}")

            # Check if coupon changed over time
            unique_coupons = set(h['coupon'] for h in history)
            if len(unique_coupons) > 1:
                print(f"  Coupon changes detected: {sorted(unique_coupons)}")
            else:
                print(f"  Coupon remained constant: {list(unique_coupons)[0]}")

    finally:
        conn.close()

if __name__ == "__main__":
    analyze_aos_coupons()
