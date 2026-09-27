import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def analyze_timeline():
    if not mt5.initialize():
        print("MT5 Init failed:", mt5.last_error())
        return

    symbol = "XAUUSD+"
    if not mt5.symbol_select(symbol, True):
        symbol = "XAUUSD"
        mt5.symbol_select(symbol, True)

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 80000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    mt5.shutdown()

    start_date = df['time'].iloc[0]
    end_date = df['time'].iloc[-1]
    days = df['date'].unique()

    print(f"Dataset Start Time: {start_date}")
    print(f"Dataset End Time: {end_date}")
    print(f"Total Unique Days in Data: {len(days)}")

    trades_data = []

    for d in days:
        day_df = df[df['date'] == d]
        if len(day_df) < 30: continue

        r_start = datetime(d.year, d.month, d.day, 11, 0)
        r_end = datetime(d.year, d.month, d.day, 15, 55)
        r_bars = day_df[(day_df['time'] >= r_start) & (day_df['time'] <= r_end)]
        if len(r_bars) == 0: continue
        
        r_h = r_bars['high'].max()
        r_l = r_bars['low'].min()
        r_mid = (r_h + r_l) / 2.0
        r_size = r_h - r_l
        if r_size < 3.0 or r_size > 60.0: continue

        t_start = datetime(d.year, d.month, d.day, 16, 0)
        t_end = datetime(d.year, d.month, d.day, 18, 30)
        t_bars = day_df[(day_df['time'] >= t_start) & (day_df['time'] <= t_end)]
        if len(t_bars) < 2: continue

        trade_taken = False

        for i in range(len(t_bars)):
            if trade_taken: break
            row = t_bars.iloc[i]
            c, o, h, l, t = row['close'], row['open'], row['high'], row['low'], row['time']

            is_sell = False
            is_buy = False

            if h > r_h:
                sweep_depth = h - r_h
                if 0.30 <= sweep_depth <= 5.0 and c < r_h:
                    is_sell = True
            elif l < r_l:
                sweep_depth = r_l - l
                if 0.30 <= sweep_depth <= 5.0 and c > r_l:
                    is_buy = True

            if is_sell:
                entry = c
                sl = h + 0.50
                risk_pts = sl - entry
                if risk_pts <= 0.20 or risk_pts > 10.0: continue
                tp = r_mid
                reward_pts = entry - tp
                if reward_pts <= 0: continue
                rr_target = reward_pts / risk_pts
                if rr_target < 1.0: continue
                direction = "SELL"
                trade_taken = True
            elif is_buy:
                entry = c
                sl = l - 0.50
                risk_pts = entry - sl
                if risk_pts <= 0.20 or risk_pts > 10.0: continue
                tp = r_mid
                reward_pts = tp - entry
                if reward_pts <= 0: continue
                rr_target = reward_pts / risk_pts
                if rr_target < 1.0: continue
                direction = "BUY"
                trade_taken = True

            if trade_taken:
                subs = day_df[day_df['time'] > t]
                pnl_dollars_per_oz = None
                pnl_r = None
                be_active = False

                for _, s in subs.iterrows():
                    cand_fav_pts = (entry - s['low']) if direction == "SELL" else (s['high'] - entry)
                    cand_adv_pts = (s['high'] - entry) if direction == "SELL" else (entry - s['low'])

                    if (cand_fav_pts / reward_pts) >= 0.75:
                        be_active = True

                    if cand_fav_pts >= reward_pts:
                        pnl_dollars_per_oz = reward_pts
                        pnl_r = rr_target
                        break

                    if be_active:
                        if cand_adv_pts >= 0.0:
                            pnl_dollars_per_oz = 0.0
                            pnl_r = 0.0
                            break
                    else:
                        if cand_adv_pts >= risk_pts:
                            pnl_dollars_per_oz = -risk_pts
                            pnl_r = -1.0
                            break

                if pnl_dollars_per_oz is None:
                    if len(subs) > 0:
                        last_c = subs.iloc[-1]['close']
                        diff = (entry - last_c) if direction == "SELL" else (last_c - entry)
                        pnl_dollars_per_oz = diff
                        pnl_r = diff / risk_pts
                    else:
                        pnl_dollars_per_oz = 0.0
                        pnl_r = 0.0

                trades_data.append({
                    "date": d,
                    "datetime": t,
                    "direction": direction,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk_pts": risk_pts,
                    "pnl_dollars_001": pnl_dollars_per_oz * 1.0, # 0.01 lot = 1 oz
                    "pnl_r": pnl_r
                })

    tdf = pd.DataFrame(trades_data)
    tdf['cum_pnl'] = tdf['pnl_dollars_001'].cumsum()
    tdf['balance'] = 100.0 + tdf['cum_pnl']

    print(f"\nFirst Trade Date: {tdf['date'].iloc[0]}")
    print(f"Last Trade Date: {tdf['date'].iloc[-1]}")
    print(f"Total Trades: {len(tdf)}")

    # Find when account first reached $200
    reached_200 = tdf[tdf['balance'] >= 200.0]
    if len(reached_200) > 0:
        first_200_row = reached_200.iloc[0]
        trade_num = reached_200.index[0] + 1
        print(f"\n>>> ACCOUNT REACHED $200.00 ON:")
        print(f"   Date: {first_200_row['date']}")
        print(f"   Trade Number: #{trade_num} of {len(tdf)}")
        print(f"   Balance on that day: ${first_200_row['balance']:.2f}")
        
        # Calculate time difference from first trade
        days_taken = (first_200_row['date'] - tdf['date'].iloc[0]).days
        months_taken = days_taken / 30.4375
        print(f"   Time elapsed: {days_taken} days (~{months_taken:.1f} months)")
    else:
        print("Account did not reach $200 in the test period.")

    # Let's save the equity curve points for charting
    # Downsample points for json/html
    curve_points = []
    for idx, r in tdf.iterrows():
        curve_points.append({
            "trade": int(idx + 1),
            "date": str(r['date']),
            "pnl": round(float(r['pnl_dollars_001']), 2),
            "balance": round(float(r['balance']), 2)
        })

    import json
    with open("equity_curve_001.json", "w") as f:
        json.dump(curve_points, f, indent=2)

    print("Saved equity_curve_001.json with", len(curve_points), "points")

if __name__ == "__main__":
    analyze_timeline()
