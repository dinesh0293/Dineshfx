import calendar
from datetime import date

holidays_news = {
    date(2026, 10, 2): "NFP (US Non-Farm Payrolls - 1st Friday)",
    date(2026, 10, 12): "US Columbus / Indigenous Peoples Day (Thin Liquidity)",
    date(2026, 10, 14): "US CPI (Inflation Data Release - 08:30 AM EST)",
    date(2026, 10, 29): "US Advance GDP Q3 Release",
    date(2026, 11, 4): "FOMC Interest Rate Decision Day 1",
    date(2026, 11, 5): "FOMC Interest Rate Decision & Press Conference",
    date(2026, 11, 6): "NFP (US Non-Farm Payrolls - 1st Friday)",
    date(2026, 11, 11): "US Veterans Day (US Bond Markets Closed)",
    date(2026, 11, 12): "US CPI (Inflation Data Release - 08:30 AM EST)",
    date(2026, 11, 26): "US Thanksgiving Day (US MARKETS CLOSED)",
    date(2026, 11, 27): "Black Friday (Early Close / Low Volume)",
    date(2026, 12, 4): "NFP (US Non-Farm Payrolls - 1st Friday)",
    date(2026, 12, 10): "US CPI (Inflation Data Release - 08:30 AM EST)",
    date(2026, 12, 15): "FOMC Meeting Day 1",
    date(2026, 12, 16): "FOMC Rate Decision & Press Conference",
    date(2026, 12, 24): "Christmas Eve (Early Market Close)",
    date(2026, 12, 25): "Christmas Day (US MARKETS CLOSED)",
    date(2026, 12, 31): "New Years Eve (Spread Spikes & Holiday Illiquidity)"
}

dates_str = ", ".join([d.strftime("%Y.%m.%d") for d in holidays_news.keys()])
print("Skip Dates String for EA InpSkipDatesList:")
print(dates_str)
print("\n" + "="*80)
print(f"{'DATE':<15} | {'DAY':<10} | {'REASON (DO NOT TRADE)':<50}")
print("="*80)
for d, reason in holidays_news.items():
    print(f"{d.strftime('%Y-%m-%d'):<15} | {d.strftime('%A'):<10} | {reason:<50}")
print("="*80)
