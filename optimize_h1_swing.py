import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def optimize_h1_swing():
    if not mt5.initialize():
        print("MT5 Init failed")
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()

    # Calculate 200 EMA on H1 (trend filter)
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # Major H4 Swing Points (lookback 15 bars on each side on H1 = ~15-20 hours)
    pivot_span = 12
    df['swing_high'] = False
    df['swing_low'] = False

    for i in range(pivot_span, len(df) - pivot_span):
        high_val = df['high'].iloc[i]
        low_val = df['low'].iloc[i]

        if high_val == df['high'].iloc[i - pivot_span : i + pivot_span + 1].max():
            df.loc[df.index[i], 'swing_high'] = True
        if low_val == df['low'].iloc[i - pivot_span : i + pivot_span + 1].min():
            df.loc[df.index[i], 'swing_low'] = True

    experiments = [
        {"name": "A. Min Displacement $8 + FVG + 1:3 R:R", "min_disp": 8.0, "rr": 3.0, "trend": False},
        {"name": "B. Min Displacement $12 + FVG + 1:3 R:R", "min_disp": 12.0, "rr": 3.0, "trend": False},
        {"name": "C. Min Displacement $12 + FVG + 1:4 R:R", "min_disp": 12.0, "rr": 4.0, "trend": False},
        {"name": "D. Min Displacement $12 + FVG + 1:4 R:R + 200 EMA Trend Filter", "min_disp": 12.0, "rr": 4.0, "trend": True},
        {"name": "E. Min Displacement $15 + FVG + 1:5 R:R (Positional Target)", "min_disp": 15.0, "rr": 5.0, "trend": False},
    ]

    all_res = []

    for exp in experiments:
        trades = []
        active_obs = []

        for i in range(50, len(df) - 60):
            row = df.iloc[i]
            c, o, h, l, t, ema = row['close'], row['open'], row['high'], row['low'], row['time'], row['ema200']

            # Check Bearish Setup
            if not exp["trend"] or c < ema:
                # Find recent major swing high
                sh_history = df.iloc[max(0, i-80) : i-3]
                sh_pts = sh_history[sh_history['swing_high']]
                if len(sh_pts) > 0:
                    last_sh = sh_pts['high'].max()
                    recent_high = df['high'].iloc[i-3 : i+1].max()

                    # Sweep of major high
                    if recent_high > last_sh:
                        # Displacement check
                        disp = o - c
                        if c < o and disp >= exp["min_disp"]:
                            # Fair Value Gap check (Low of candle i-2 > High of candle i)
                            c_prev2 = df.iloc[i-2]
                            if c_prev2['low'] > h: # clean imbalance / FVG!
                                cand_ob = df.iloc[i-1]
                                active_obs.append({
                                    "type": "BEARISH",
                                    "created_idx": i,
                                    "time": t,
                                    "ob_high": cand_ob['high'],
                                    "ob_low": cand_ob['low'],
                                    "sl": recent_high + 2.0,
                                    "mitigated": False
                                })

            # Check Bullish Setup
            if not exp["trend"] or c > ema:
                sl_history = df.iloc[max(0, i-80) : i-3]
                sl_pts = sl_history[sl_history['swing_low']]
                if len(sl_pts) > 0:
                    last_sl = sl_pts['low'].min()
                    recent_low = df['low'].iloc[i-3 : i+1].min()

                    if recent_low < last_sl:
                        disp = c - o
                        if c > o and disp >= exp["min_disp"]:
                            c_prev2 = df.iloc[i-2]
                            if c_prev2['high'] < l: # clean bullish FVG
                                cand_ob = df.iloc[i-1]
                                active_obs.append({
                                    "type": "BULLISH",
                                    "created_idx": i,
                                    "time": t,
                                    "ob_high": cand_ob['high'],
                                    "ob_low": cand_ob['low'],
                                    "sl": recent_low - 2.0,
                                    "mitigated": False
                                })

            # Retest checks
            for ob in active_obs:
                if ob["mitigated"]: continue
                if i - ob["created_idx"] < 1: continue
                if i - ob["created_idx"] > 72: # expires after 72 hours (3 days)
                    ob["mitigated"] = True
                    continue

                if ob["type"] == "BEARISH":
                    if h >= ob["ob_low"] and h <= (ob["ob_high"] + 3.0):
                        entry = ob["ob_low"]
                        sl = ob["sl"]
                        risk = sl - entry
                        if risk < 3.0 or risk > 35.0:
                            ob["mitigated"] = True
                            continue

                        tp1 = entry - (risk * 2.0)
                        tp2 = entry - (risk * exp["rr"])

                        pnl_r = 0.0
                        tp1_hit = False
                        f_bars = df.iloc[i+1 : min(i+200, len(df))]

                        for _, fb in f_bars.iterrows():
                            if not tp1_hit and fb['low'] <= tp1:
                                tp1_hit = True

                            cur_sl = entry if tp1_hit else sl
                            if fb['high'] >= cur_sl:
                                pnl_r = 1.0 if tp1_hit else -1.0 # 50% at 2R = +1.0R
                                break

                            if fb['low'] <= tp2:
                                pnl_r = 1.0 + (exp["rr"] * 0.5) if tp1_hit else exp["rr"]
                                break

                        if pnl_r == 0.0 and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            diff = entry - last_c
                            final_r = diff / risk
                            pnl_r = 1.0 + (final_r * 0.5) if tp1_hit else final_r

                        trades.append(pnl_r)
                        ob["mitigated"] = True

                elif ob["type"] == "BULLISH":
                    if l <= ob["ob_high"] and l >= (ob["ob_low"] - 3.0):
                        entry = ob["ob_high"]
                        sl = ob["sl"]
                        risk = entry - sl
                        if risk < 3.0 or risk > 35.0:
                            ob["mitigated"] = True
                            continue

                        tp1 = entry + (risk * 2.0)
                        tp2 = entry + (risk * exp["rr"])

                        pnl_r = 0.0
                        tp1_hit = False
                        f_bars = df.iloc[i+1 : min(i+200, len(df))]

                        for _, fb in f_bars.iterrows():
                            if not tp1_hit and fb['high'] >= tp1:
                                tp1_hit = True

                            cur_sl = entry if tp1_hit else sl
                            if fb['low'] <= cur_sl:
                                pnl_r = 1.0 if tp1_hit else -1.0
                                break

                            if fb['high'] >= tp2:
                                pnl_r = 1.0 + (exp["rr"] * 0.5) if tp1_hit else exp["rr"]
                                break

                        if pnl_r == 0.0 and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            diff = last_c - entry
                            final_r = diff / risk
                            pnl_r = 1.0 + (final_r * 0.5) if tp1_hit else final_r

                        trades.append(pnl_r)
                        ob["mitigated"] = True

        if len(trades) > 0:
            ts = pd.Series(trades)
            tot = len(ts)
            wins = (ts > 0.05).sum()
            losses = (ts < -0.05).sum()
            wr = (wins / tot) * 100.0
            net_r = ts.sum()
            gross_win = ts[ts > 0].sum()
            gross_loss = abs(ts[ts < 0].sum())
            pf = gross_win / gross_loss if gross_loss > 0 else np.nan
            cum = ts.cumsum()
            dd = (cum.cummax() - cum).max()

            all_res.append({
                "Model": exp["name"],
                "Trades": tot,
                "Trades/Mo": f"{tot/20.0:.1f}",
                "Win Rate": f"{wr:.1f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max DD (R)": f"-{dd:.1f} R"
            })

    res_df = pd.DataFrame(all_res)
    print("\n" + "="*95)
    print("       H1/H4 ORDER BLOCK & SWING OPTIMIZATION STUDY (20 MONTHS / 10,000 H1 BARS)")
    print("="*95)
    print(res_df.to_string(index=False))
    print("="*95)

if __name__ == "__main__":
    optimize_h1_swing()
