import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def optimize_sweep():
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

    # Calculate 1-hour EMA (approx 12 M5 bars) and 4-hour EMA (approx 48 M5 bars)
    df['ema_trend'] = df['close'].ewm(span=48, adjust=False).mean()

    days = df['date'].unique()

    # Tests to run:
    # 1. Baseline: Sweep targeting Midpoint
    # 2. Alteration A: Break-even at 1:1.5 + Trailing to Midpoint
    # 3. Alteration B: Displacement confirmation (Bearish close breaking prior candle low)
    # 4. Alteration C: Partial profit (50% at 1:2 R:R, 50% at Midpoint)
    # 5. Alteration D: Sweep depth filter (min $0.50 beyond extreme, max $6.00 beyond extreme)

    experiments = [
        {"name": "1. Baseline (Sweep to 50% Midpoint)", "mode": "baseline"},
        {"name": "2. With Sweep Depth Filter ($0.50 - $6.00 max pierce)", "mode": "depth_filter"},
        {"name": "3. With Bearish/Bullish Displacement Candle Close", "mode": "displacement"},
        {"name": "4. With Break-Even Lock at +1R", "mode": "breakeven"},
        {"name": "5. Best Combo: Depth Filter + Displacement + Midpoint Target", "mode": "combo"}
    ]

    results = []

    for exp in experiments:
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
            r_size = r_h - r_l
            if r_size < 3.0 or r_size > 60.0: continue # realistic range size

            # NY Open Window: 16:00 - 18:30 Broker Time (09:00 - 11:30 EST)
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

                # Check High Sweep
                if h > r_h:
                    sweep_depth = h - r_h
                    if exp["mode"] in ["depth_filter", "combo"]:
                        if sweep_depth < 0.30 or sweep_depth > 5.0: # avoid too small or runaways
                            continue

                    # Displacement check
                    if exp["mode"] in ["displacement", "combo"]:
                        # Candle must close back inside and close lower than open (bearish candle)
                        if c < r_h and c < o:
                            is_sell = True
                    else:
                        if c < r_h:
                            is_sell = True

                # Check Low Sweep
                elif l < r_l:
                    sweep_depth = r_l - l
                    if exp["mode"] in ["depth_filter", "combo"]:
                        if sweep_depth < 0.30 or sweep_depth > 5.0:
                            continue

                    # Displacement check
                    if exp["mode"] in ["displacement", "combo"]:
                        # Candle must close back inside and close higher than open (bullish candle)
                        if c > r_l and c > o:
                            is_buy = True
                    else:
                        if c > r_l:
                            is_buy = True

                if is_sell:
                    entry = c
                    sl = h + 0.50
                    risk = sl - entry
                    if risk <= 0.20 or risk > 10.0: continue
                    tp = r_mid
                    reward = entry - tp
                    if reward <= 0: continue
                    rr_target = reward / risk
                    if rr_target < 1.0: continue # at least 1:1 to midpoint

                    direction = "SELL"
                    trade_taken = True

                elif is_buy:
                    entry = c
                    sl = l - 0.50
                    risk = entry - sl
                    if risk <= 0.20 or risk > 10.0: continue
                    tp = r_mid
                    reward = tp - entry
                    if reward <= 0: continue
                    rr_target = reward / risk
                    if rr_target < 1.0: continue

                    direction = "BUY"
                    trade_taken = True

                if trade_taken:
                    subs = day_df[day_df['time'] > t]
                    pnl_r = 0.0
                    be_active = False

                    for _, s in subs.iterrows():
                        # Break-even check
                        if exp["mode"] == "breakeven":
                            if direction == "SELL" and (entry - s['low']) >= risk:
                                be_active = True
                            elif direction == "BUY" and (s['high'] - entry) >= risk:
                                be_active = True

                        current_sl = entry if be_active else sl

                        if direction == "SELL":
                            if s['high'] >= current_sl:
                                pnl_r = 0.0 if be_active else -1.0
                                break
                            elif s['low'] <= tp:
                                pnl_r = rr_target
                                break
                        else:
                            if s['low'] <= current_sl:
                                pnl_r = 0.0 if be_active else -1.0
                                break
                            elif s['high'] >= tp:
                                pnl_r = rr_target
                                break

                    # If not hit by end of day, close at market
                    if pnl_r == 0.0 and not be_active and len(subs) > 0:
                        last_c = subs.iloc[-1]['close']
                        diff = (entry - last_c) if direction == "SELL" else (last_c - entry)
                        pnl_r = diff / risk

                    trades.append(pnl_r)

        if len(trades) > 0:
            ts = pd.Series(trades)
            tot = len(ts)
            wins = (ts > 0).sum()
            losses = (ts < 0).sum()
            bes = (ts == 0).sum()
            wr = (wins / tot) * 100.0
            net_r = ts.sum()
            gross_win = ts[ts > 0].sum()
            gross_loss = abs(ts[ts < 0].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else np.nan
            
            cum = ts.cumsum()
            dd = (cum.cummax() - cum).max()

            results.append({
                "Strategy Model": exp["name"],
                "Total Trades": tot,
                "Wins": wins,
                "Losses": losses,
                "Win Rate (%)": f"{wr:.2f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max Drawdown (R)": f"-{dd:.1f} R",
                "Return ($10k @ 1%)": f"${net_r * 100:+,.0f} ({net_r:+.1f}%)"
            })

    res_df = pd.DataFrame(results)
    print("\n" + "="*95)
    print("           STRATEGY 2 OPTIMIZATION & ENHANCEMENT - XAUUSD RESULTS")
    print("="*95)
    print(res_df.to_string(index=False))
    print("="*95)

if __name__ == "__main__":
    optimize_sweep()
