import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def backtest_liquidity_sweep():
    if not mt5.initialize():
        print("MT5 Init failed:", mt5.last_error())
        return

    symbol = "XAUUSD+"
    if not mt5.symbol_select(symbol, True):
        symbol = "XAUUSD"
        if not mt5.symbol_select(symbol, True):
            print("Cannot find XAUUSD or XAUUSD+")
            mt5.shutdown()
            return

    # Fetch 80,000 bars (~13.5 months)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 80000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    mt5.shutdown()

    print(f"Loaded {len(df):,} M5 bars for {symbol} from {df['time'].min()} to {df['time'].max()}")

    days = df['date'].unique()

    # Test parameter variations:
    # 1. Sweep Definition:
    #    Type A: Wick sweep on single candle (High > r_h and Close < r_h)
    #    Type B: False breakout sweep (1 candle closes outside, next candle closes back inside)
    # 2. Targets: 1:1.5 R:R, 1:2.0 R:R, 1:2.5 R:R, and Target Midpoint (50%)
    
    variations = [
        {"name": "Single-Candle Sweep (Wick Rejection)", "type": "wick", "rr": 1.5},
        {"name": "Single-Candle Sweep (Wick Rejection)", "type": "wick", "rr": 2.0},
        {"name": "Single-Candle Sweep (Wick Rejection)", "type": "wick", "rr": 2.5},
        {"name": "Confirmed Fakeout (Close out -> Close back in)", "type": "fakeout", "rr": 1.5},
        {"name": "Confirmed Fakeout (Close out -> Close back in)", "type": "fakeout", "rr": 2.0},
        {"name": "Confirmed Fakeout (Close out -> Close back in)", "type": "fakeout", "rr": 2.5},
        {"name": "Sweep Targeting Range Midpoint (50%)", "type": "wick", "rr": "midpoint"},
    ]

    summary = []

    for v in variations:
        trades = []

        for d in days:
            day_df = df[df['date'] == d]
            if len(day_df) < 30: continue

            # London Range: 11:00 - 15:55 Broker Time (04:00 - 08:55 EST)
            r_start = datetime(d.year, d.month, d.day, 11, 0)
            r_end = datetime(d.year, d.month, d.day, 15, 55)
            r_bars = day_df[(day_df['time'] >= r_start) & (day_df['time'] <= r_end)]
            if len(r_bars) == 0: continue
            
            r_h = r_bars['high'].max()
            r_l = r_bars['low'].min()
            r_mid = (r_h + r_l) / 2.0
            if r_h <= r_l: continue

            # NY Open Window: 16:00 - 18:30 Broker Time (09:00 - 11:30 EST)
            t_start = datetime(d.year, d.month, d.day, 16, 0)
            t_end = datetime(d.year, d.month, d.day, 18, 30)
            t_bars = day_df[(day_df['time'] >= t_start) & (day_df['time'] <= t_end)]
            if len(t_bars) < 2: continue

            trade_taken = False
            prev_outside = None # Tracks if previous bar was outside

            for i in range(len(t_bars)):
                if trade_taken: break
                row = t_bars.iloc[i]
                c, o, h, l, t = row['close'], row['open'], row['high'], row['low'], row['time']

                # --- TYPE A: WICK SWEEP (Pierced extreme but closed inside) ---
                if v["type"] == "wick":
                    # Bearish Sweep of High: Pierced above London High, closed back inside
                    if h > r_h and c < r_h:
                        entry = c
                        sl = h + 0.50 # buffer above sweep wick
                        risk = sl - entry
                        if risk <= 0.20 or risk > 15.0: continue # realistic stop distance filter
                        
                        if v["rr"] == "midpoint":
                            tp = r_mid
                            rr_actual = (entry - tp) / risk if (entry - tp) > 0 else 1.0
                        else:
                            tp = entry - (risk * v["rr"])
                            rr_actual = v["rr"]

                        direction = "SELL"
                        trade_taken = True

                    # Bullish Sweep of Low: Pierced below London Low, closed back inside
                    elif l < r_l and c > r_l:
                        entry = c
                        sl = l - 0.50 # buffer below sweep wick
                        risk = entry - sl
                        if risk <= 0.20 or risk > 15.0: continue
                        
                        if v["rr"] == "midpoint":
                            tp = r_mid
                            rr_actual = (tp - entry) / risk if (tp - entry) > 0 else 1.0
                        else:
                            tp = entry + (risk * v["rr"])
                            rr_actual = v["rr"]

                        direction = "BUY"
                        trade_taken = True

                # --- TYPE B: FAKEOUT REVERSAL (1 bar closed outside, current closes back inside) ---
                elif v["type"] == "fakeout":
                    if prev_outside == "HIGH" and c < r_h:
                        entry = c
                        highest_wick = max(t_bars.iloc[i-1]['high'], h)
                        sl = highest_wick + 0.50
                        risk = sl - entry
                        if risk <= 0.20 or risk > 15.0: continue
                        tp = entry - (risk * v["rr"])
                        rr_actual = v["rr"]
                        direction = "SELL"
                        trade_taken = True
                    elif prev_outside == "LOW" and c > r_l:
                        entry = c
                        lowest_wick = min(t_bars.iloc[i-1]['low'], l)
                        sl = lowest_wick - 0.50
                        risk = entry - sl
                        if risk <= 0.20 or risk > 15.0: continue
                        tp = entry + (risk * v["rr"])
                        rr_actual = v["rr"]
                        direction = "BUY"
                        trade_taken = True

                    # Update prev_outside status
                    if c > r_h:
                        prev_outside = "HIGH"
                    elif c < r_l:
                        prev_outside = "LOW"
                    else:
                        prev_outside = None

                if trade_taken:
                    # Check outcome over subsequent bars of the day
                    subs = day_df[day_df['time'] > t]
                    pnl_r = 0.0
                    for _, s in subs.iterrows():
                        if direction == "SELL":
                            if s['high'] >= sl:
                                pnl_r = -1.0
                                break
                            elif s['low'] <= tp:
                                pnl_r = rr_actual
                                break
                        else: # BUY
                            if s['low'] <= sl:
                                pnl_r = -1.0
                                break
                            elif s['high'] >= tp:
                                pnl_r = rr_actual
                                break

                    # If not hit by end of day, close at market
                    if pnl_r == 0.0 and len(subs) > 0:
                        last_c = subs.iloc[-1]['close']
                        diff = (entry - last_c) if direction == "SELL" else (last_c - entry)
                        pnl_r = diff / risk

                    trades.append(pnl_r)

        if len(trades) > 0:
            ts = pd.Series(trades)
            tot = len(ts)
            wins = (ts > 0).sum()
            losses = (ts <= 0).sum()
            wr = (wins / tot) * 100.0
            net_r = ts.sum()
            gross_win = ts[ts > 0].sum()
            gross_loss = abs(ts[ts <= 0].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else np.nan
            
            # Max Drawdown
            cum = ts.cumsum()
            dd = (cum.cummax() - cum).max()
            
            summary.append({
                "Strategy Model": v["name"],
                "Target R:R": f"1:{v['rr']}" if v['rr'] != "midpoint" else "50% Midpoint",
                "Total Trades": tot,
                "Wins": wins,
                "Losses": losses,
                "Win Rate (%)": f"{wr:.2f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max Drawdown (R)": f"-{dd:.1f} R",
                "Return on $10k (1% risk)": f"${net_r * 100:+,.0f} ({net_r:+.1f}%)"
            })

    res_df = pd.DataFrame(summary)
    print("\n" + "="*95)
    print("       XAUUSD LIQUIDITY SWEEP & REVERSAL (JUDAS SWING) BACKTEST RESULTS")
    print("="*95)
    print(res_df.to_string(index=False))
    print("="*95)
    res_df.to_csv("xauusd_sweep_strategy_results.csv", index=False)
    print("\nSaved results to: xauusd_sweep_strategy_results.csv")

if __name__ == "__main__":
    backtest_liquidity_sweep()
