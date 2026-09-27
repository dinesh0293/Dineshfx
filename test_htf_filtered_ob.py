import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def test_htf_filtered_ob():
    if not mt5.initialize():
        print("MT5 Init failed")
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    # Pull Daily bars to get Daily Trend
    d_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 800)
    d_df = pd.DataFrame(d_rates)
    d_df['time'] = pd.to_datetime(d_df['time'], unit='s')
    d_df['date'] = d_df['time'].dt.date
    d_df['ema50'] = d_df['close'].ewm(span=50, adjust=False).mean()

    # Pull H1 bars
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    mt5.shutdown()

    # Merge daily trend into H1 bars
    df = df.merge(d_df[['date', 'ema50']], on='date', how='left')
    df['ema50'] = df['ema50'].ffill()

    # Detect major swing points (pivot span = 10 bars = 10 hours)
    span = 8
    df['sh'] = False
    df['sl'] = False

    for i in range(span, len(df) - span):
        if df['high'].iloc[i] == df['high'].iloc[i - span : i + span + 1].max():
            df.loc[df.index[i], 'sh'] = True
        if df['low'].iloc[i] == df['low'].iloc[i - span : i + span + 1].min():
            df.loc[df.index[i], 'sl'] = True

    experiments = [
        {"name": "A. Daily Trend Filter + Sweep + 1:3 R:R", "rr": 3.0, "sweep_req": True, "trend_req": True},
        {"name": "B. Daily Trend Filter + Sweep + 1:4 R:R", "rr": 4.0, "sweep_req": True, "trend_req": True},
        {"name": "C. Daily Trend Filter + Sweep + 1:5 R:R", "rr": 5.0, "sweep_req": True, "trend_req": True},
        {"name": "D. Sweep Only (Counter-trend allowed) + 1:3 R:R", "rr": 3.0, "sweep_req": True, "trend_req": False},
        {"name": "E. Sweep Only (Counter-trend allowed) + 1:4 R:R", "rr": 4.0, "sweep_req": True, "trend_req": False},
    ]

    all_res = []

    for exp in experiments:
        obs = []
        trades = []

        for i in range(20, len(df) - 60):
            row = df.iloc[i]
            c, o, h, l, t, ema = row['close'], row['open'], row['high'], row['low'], row['time'], row['ema50']

            # Check Bearish OB formation
            if df['sh'].iloc[i]:
                cand = df.iloc[i]
                drop_price = df['low'].iloc[i+1 : i+5].min()
                drop_dist = cand['high'] - drop_price

                # Trend check
                trend_ok = (not exp["trend_req"]) or (cand['close'] < ema)

                # Sweep check: did this swing high pierce a prior swing high?
                prior_sh = df.iloc[max(0, i-60) : i-2]
                prior_sh_pts = prior_sh[prior_sh['sh']]
                sweep_ok = True
                if exp["sweep_req"] and len(prior_sh_pts) > 0:
                    last_high = prior_sh_pts['high'].max()
                    sweep_ok = (cand['high'] > last_high)

                if trend_ok and sweep_ok and drop_dist >= 8.0:
                    obs.append({
                        "type": "BEARISH",
                        "idx": i,
                        "time": cand['time'],
                        "top": cand['high'],
                        "bottom": min(cand['open'], cand['close']),
                        "sl": cand['high'] + 2.0,
                        "active": True
                    })

            # Check Bullish OB formation
            if df['sl'].iloc[i]:
                cand = df.iloc[i]
                rally_price = df['high'].iloc[i+1 : i+5].max()
                rally_dist = rally_price - cand['low']

                trend_ok = (not exp["trend_req"]) or (cand['close'] > ema)

                prior_sl = df.iloc[max(0, i-60) : i-2]
                prior_sl_pts = prior_sl[prior_sl['sl']]
                sweep_ok = True
                if exp["sweep_req"] and len(prior_sl_pts) > 0:
                    last_low = prior_sl_pts['low'].min()
                    sweep_ok = (cand['low'] < last_low)

                if trend_ok and sweep_ok and rally_dist >= 8.0:
                    obs.append({
                        "type": "BULLISH",
                        "idx": i,
                        "time": cand['time'],
                        "top": max(cand['open'], cand['close']),
                        "bottom": cand['low'],
                        "sl": cand['low'] - 2.0,
                        "active": True
                    })

            # Check retest of active OBs
            for ob in obs:
                if not ob["active"]: continue
                if i - ob["idx"] < 3: continue
                if i - ob["idx"] > 120:
                    ob["active"] = False
                    continue

                if ob["type"] == "BEARISH":
                    if row['high'] >= ob["bottom"] and row['high'] <= (ob["top"] + 1.5):
                        entry = ob["bottom"]
                        sl = ob["sl"]
                        risk = sl - entry
                        if risk < 3.0 or risk > 35.0:
                            ob["active"] = False
                            continue

                        tp = entry - (risk * exp["rr"])
                        pnl_r = 0.0
                        f_bars = df.iloc[i+1 : min(i+180, len(df))]

                        for _, fb in f_bars.iterrows():
                            if fb['high'] >= sl:
                                pnl_r = -1.0
                                break
                            if fb['low'] <= tp:
                                pnl_r = exp["rr"]
                                break

                        if pnl_r == 0.0 and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            pnl_r = (entry - last_c) / risk

                        trades.append(pnl_r)
                        ob["active"] = False

                elif ob["type"] == "BULLISH":
                    if row['low'] <= ob["top"] and row['low'] >= (ob["bottom"] - 1.5):
                        entry = ob["top"]
                        sl = ob["sl"]
                        risk = entry - sl
                        if risk < 3.0 or risk > 35.0:
                            ob["active"] = False
                            continue

                        tp = entry + (risk * exp["rr"])
                        pnl_r = 0.0
                        f_bars = df.iloc[i+1 : min(i+180, len(df))]

                        for _, fb in f_bars.iterrows():
                            if fb['low'] <= sl:
                                pnl_r = -1.0
                                break
                            if fb['high'] >= tp:
                                pnl_r = exp["rr"]
                                break

                        if pnl_r == 0.0 and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            pnl_r = (last_c - entry) / risk

                        trades.append(pnl_r)
                        ob["active"] = False

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
                "Win": wins,
                "Loss": losses,
                "Win Rate": f"{wr:.1f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max DD (R)": f"-{dd:.1f} R"
            })

    res_df = pd.DataFrame(all_res)
    print("\n" + "="*110)
    print("      HTF-FILTERED ORDER BLOCK & SWING STUDY (10,000 H1 BARS / 20 MONTHS)")
    print("="*110)
    print(res_df.to_string(index=False))
    print("="*110)

if __name__ == "__main__":
    test_htf_filtered_ob()
