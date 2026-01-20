#!/usr/bin/env python3
"""
Enhanced analysis of AOS Corporate Finance bond coupon payment dates
by examining price movements and maturity dates
"""

import sqlite3
import csv
from datetime import datetime
from collections import defaultdict
from dateutil import parser

def parse_maturity_date(maturity_str):
    """Parse various maturity date formats"""
    if not maturity_str or maturity_str == '-':
        return None
    try:
        # Common formats: MM/DD/YYYY
        return parser.parse(maturity_str)
    except:
        return None

def analyze_coupon_payment_dates():
    """Analyze when AOS Corporate Finance bonds pay coupons"""

    conn = sqlite3.connect("priv_data.db")
    cursor = conn.cursor()

    try:
        # Query all AOS Corporate Finance bonds with complete data
        query = """
        SELECT
            name,
            identifier,
            coupon,
            maturity,
            date as observation_date,
            market_value,
            par_value
        FROM financial_data
        WHERE asset_breakdown = 'AOS Corporate Finance'
        ORDER BY name, date ASC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("No AOS Corporate Finance bonds found.")
            return

        print("=" * 100)
        print("AOS CORPORATE FINANCE BOND - COUPON PAYMENT DATE ANALYSIS")
        print("=" * 100)

        # Group data by bond
        bonds_history = defaultdict(list)
        for row in rows:
            name, identifier, coupon, maturity, obs_date, market_val, par_val = row
            bonds_history[name].append({
                'identifier': identifier,
                'coupon': coupon,
                'maturity': maturity,
                'date': obs_date,
                'market_value': market_val,
                'par_value': par_val,
                'price': (market_val / par_val * 100) if par_val and par_val != 0 else None
            })

        print(f"\nTotal unique bonds: {len(bonds_history)}\n")

        # Analyze each bond
        detailed_results = []

        for bond_name, history in sorted(bonds_history.items()):
            print("\n" + "=" * 100)
            print(f"BOND: {bond_name}")
            print("=" * 100)

            latest = history[-1]
            print(f"Latest coupon rate: {latest['coupon']}% (annual)")
            print(f"Maturity: {latest['maturity']}")
            print(f"Observations: {len(history)} data points from {history[0]['date']} to {history[-1]['date']}")

            # Parse maturity to infer payment months
            maturity_date = parse_maturity_date(latest['maturity'])
            if maturity_date:
                maturity_month = maturity_date.month
                maturity_day = maturity_date.day
                print(f"\nMaturity date: {maturity_date.strftime('%B %d, %Y')}")

                # For semi-annual bonds, payments typically occur on maturity month and 6 months later
                if maturity_month <= 6:
                    payment_months = [maturity_month, maturity_month + 6]
                else:
                    payment_months = [maturity_month - 6, maturity_month]

                month_names = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
                              5: 'May', 6: 'June', 7: 'July', 8: 'August',
                              9: 'September', 10: 'October', 11: 'November', 12: 'December'}

                print(f"\n*** ESTIMATED SEMI-ANNUAL COUPON PAYMENT SCHEDULE ***")
                print(f"    Payment months: {month_names[payment_months[0]]} and {month_names[payment_months[1]]}")
                print(f"    Payment day: Around {maturity_day}{ordinal_suffix(maturity_day)} of the month")

                # Try to parse coupon
                try:
                    coupon_rate = float(str(latest['coupon']).replace('%', '').strip())
                    semi_annual_payment = coupon_rate / 2
                    print(f"    Semi-annual coupon payment: {semi_annual_payment:.4f}% of par value")
                except (ValueError, AttributeError, TypeError):
                    print(f"    Could not calculate payment amount from coupon: {latest['coupon']}")
            else:
                print(f"\n*** Could not parse maturity date: {latest['maturity']} ***")

            # Analyze price drops that might indicate coupon payments
            print(f"\n--- Price Movement Analysis (potential ex-coupon dates) ---")

            price_drops = []
            for i in range(1, len(history)):
                prev = history[i-1]
                curr = history[i]

                if prev['price'] and curr['price']:
                    price_change = curr['price'] - prev['price']
                    price_pct_change = (price_change / prev['price']) * 100

                    # Significant price drop might indicate ex-coupon date
                    if price_change < -0.5:  # Price dropped by more than 0.5 points
                        price_drops.append({
                            'date': curr['date'],
                            'price_drop': price_change,
                            'pct_drop': price_pct_change,
                            'prev_price': prev['price'],
                            'curr_price': curr['price']
                        })

            if price_drops:
                print(f"    Found {len(price_drops)} significant price drops (potential ex-coupon dates):")
                for drop in price_drops[:10]:  # Show first 10
                    print(f"      {drop['date']}: Price dropped {drop['price_drop']:.2f} ({drop['pct_drop']:.2f}%) "
                          f"from {drop['prev_price']:.2f} to {drop['curr_price']:.2f}")
            else:
                print(f"    No significant price drops detected in the observation period")

            # Store detailed results
            detailed_results.append({
                'name': bond_name,
                'coupon': latest['coupon'],
                'maturity': latest['maturity'],
                'maturity_parsed': maturity_date.strftime('%Y-%m-%d') if maturity_date else 'Unknown',
                'payment_frequency': 'Semi-annual (typical)',
                'estimated_payment_months': f"{month_names.get(payment_months[0], 'Unknown')}, {month_names.get(payment_months[1], 'Unknown')}" if maturity_date else 'Unknown',
                'observations': len(history),
                'significant_price_drops': len(price_drops)
            })

        # Summary report
        print("\n\n" + "=" * 100)
        print("SUMMARY: COUPON PAYMENT SCHEDULE")
        print("=" * 100)

        # Export summary to CSV
        output_file = f"aos_payment_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['name', 'coupon', 'maturity', 'maturity_parsed', 'payment_frequency',
                         'estimated_payment_months', 'observations', 'significant_price_drops']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for result in detailed_results:
                writer.writerow(result)

        print(f"\n✓ Payment schedule summary exported to: {output_file}")

        print("\n" + "=" * 100)
        print("GENERAL FINDINGS:")
        print("=" * 100)
        print("\n1. PAYMENT FREQUENCY: Most US corporate bonds pay coupons SEMI-ANNUALLY")
        print("   (twice per year, every 6 months)")
        print("\n2. PAYMENT DATES: Typically based on the bond's maturity date")
        print("   - If maturity is March 15, coupons likely paid on/around March 15 and Sept 15")
        print("   - If maturity is September 14, coupons likely paid on/around March 14 and Sept 14")
        print("\n3. CALCULATION: Semi-annual payment = (Annual Coupon Rate / 2) × Par Value")
        print("\n4. EX-COUPON DATE: Bond price typically drops on ex-coupon date by approximate")
        print("   coupon amount, as new buyers won't receive the upcoming payment")
        print("\n" + "=" * 100)

    finally:
        conn.close()

def ordinal_suffix(day):
    """Return ordinal suffix for day number"""
    if 10 <= day % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return suffix

if __name__ == "__main__":
    analyze_coupon_payment_dates()
