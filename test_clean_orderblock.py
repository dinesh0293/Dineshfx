import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def test_clean_orderblock():
    if not mt5.initialize():
        print("MT5 Init failed")
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()

    # Swing detection (pivot 5)
    span = 4
    df['sh'] = False
    df['sl'] = False

    for i in range(span, len(df) - span):
        if df['high'].iloc[i] == df['high'].iloc[i - span : i + span + 1].max():
            df.loc[df.index[i], 'sh'] = True
        if df['low'].iloc[i] == df['low'].iloc[i - span : i + span + 1].min():
            df.loc[df.index[i], 'sl'] = True

    # Find Order Blocks at Swing Highs and Swing Lows:
    # A Bearish OB is the green candle at a Swing High that was followed by a sharp drop
    # A Bullish OB is the red candle at a Swing Low that was followed by a sharp rally

    experiments = [
        {"name": "1:2.0 R:R Target (Break-Even at 1.0R)", "rr": 2.0, "be": True},
        {"name": "1:2.5 R:R Target (Break-Even at 1.0R)", "rr": 2.5, "be": True},
        {"name": "1:3.0 R:R Target (Break-Even at 1.5R)", "rr": 3.0, "be": True},
        {"name": "1:2.0 R:R Target (No BE - Full Target)", "rr": 2.0, "be": False},
        {"name": "1:3.0 R:R Target (No BE - Full Target)", "rr": 3.0, "be": False},
    ]

    all_res = []

    for exp in experiments:
        obs = []
        trades = []

        for i in range(10, len(df) - 60):
            # Check for swing high
            if df['sh'].iloc[i]:
                # Candle at i is swing high
                cand = df.iloc[i]
                cand_next = df.iloc[i+1]
                # Check for strong rejection/drop (next 2-3 candles drop at least $6 from high)
                drop_price = df['low'].iloc[i+1 : i+4].min()
                if (cand['high'] - drop_price) >= 6.0:
                    obs.append({
                        "type": "BEARISH",
                        "idx": i,
                        "time": cand['time'],
                        "top": cand['high'],
                        "bottom": min(cand['open'], cand['close']),
                        "sl": cand['high'] + 2.0, # SL above swing high + $2
                        "active": True
                    })

            # Check for swing low
            if df['sl'].iloc[i]:
                cand = df.iloc[i]
                rally_price = df['high'].iloc[i+1 : i+4].max()
                if (rally_price - cand['low']) >= 6.0:
                    obs.append({
                        "type": "BULLISH",
                        "idx": i,
                        "time": cand['time'],
                        "top": max(cand['open'], cand['close']),
                        "bottom": cand['low'],
                        "sl": cand['low'] - 2.0,
                        "active": True
                    })

            # Check unmitigated OBs for retest
            row = df.iloc[i]
            for ob in obs:
                if not ob["active"]: continue
                if i - ob["idx"] < 4: continue # wait at least 4 bars after formation
                if i - ob["idx"] > 120: # expire after 5 days (120 hours)
                    ob["active"] = False
                    continue

                if ob["type"] == "BEARISH":
                    # Retest: price enters the OB zone from below
                    if row['high'] >= ob["bottom"] and row['high'] <= (ob["top"] + 1.0):
                        entry = ob["bottom"]
                        sl = ob["sl"]
                        risk = sl - entry
                        if risk < 2.5 or risk > 35.0:
                            ob["active"] = False
                            continue

                        tp = entry - (risk * exp["rr"])
                        be_trigger_dist = risk * (1.5 if exp["rr"] >= 3.0 else 1.0)

                        pnl_r = 0.0
                        be_active = False
                        f_bars = df.iloc[i+1 : min(i+150, len(df))]

                        for _, fb in f_bars.iterrows():
                            # Check BE trigger
                            if exp["be"] and not be_active and (entry - fb['low']) >= be_trigger_dist:
                                be_active = True

                            cur_sl = entry if be_active else sl
                            if fb['high'] >= cur_sl:
                                pnl_r = 0.0 if be_active else -1.0
                                break

                            if fb['low'] <= tp:
                                pnl_r = exp["rr"]
                                break

                        if pnl_r == 0.0 and not be_active and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            pnl_r = (entry - last_c) / risk

                        trades.append(pnl_r)
                        ob["active"] = False

                elif ob["type"] == "BULLISH":
                    if row['low'] <= ob["top"] and row['low'] >= (ob["bottom"] - 1.0):
                        entry = ob["top"]
                        sl = ob["sl"]
                        risk = entry - sl
                        if risk < 2.5 or risk > 35.0:
                            ob["active"] = False
                            continue

                        tp = entry + (risk * exp["rr"])
                        be_trigger_dist = risk * (1.5 if exp["rr"] >= 3.0 else 1.0)

                        pnl_r = 0.0
                        be_active = False
                        f_bars = df.iloc[i+1 : min(i+150, len(df))]

                        for _, fb in f_bars.iterrows():
                            if exp["be"] and not be_active and (fb['high'] - entry) >= be_trigger_dist:
                                be_active = True

                            cur_sl = entry if be_active else sl
                            if fb['low'] <= cur_sl:
                                pnl_r = 0.0 if be_active else -1.0
                                break

                            if fb['high'] >= tp:
                                pnl_r = exp["rr"]
                                break

                        if pnl_r == 0.0 and not be_active and len(f_bars) > 0:
                            last_c = f_bars.iloc[-1]['close']
                            pnl_r = (last_c - entry) / risk

                        trades.append(pnl_r)
                        ob["active"] = False

        if len(trades) > 0:
            ts = pd.Series(trades)
            tot = len(ts)
            wins = (ts > 0.05).sum()
            losses = (ts < -0.05).sum()
            bes = (ts.abs() <= 0.05).sum()
            wr = (wins / tot) * 100.0
            net_r = ts.sum()
            gross_win = ts[ts > 0].sum()
            gross_loss = abs(ts[ts < 0].sum())
            pf = gross_win / gross_loss if gross_loss > 0 else np.nan
            cum = ts.cumsum()
            dd = (cum.cummax() - cum).max()

            all_res.append({
                "Strategy Model": exp["name"],
                "Trades": tot,
                "Trades/Mo": f"{tot/20.0:.1f}",
                "Win": wins,
                "BE": bes,
                "Loss": losses,
                "Win Rate": f"{wr:.1f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max DD (R)": f"-{dd:.1f} R"
            })

    res_df = pd.DataFrame(all_res)
    print("\n" + "="*105)
    print("           H1 ORDER BLOCK MITIGATION RESULTS (10,000 H1 BARS / 20 MONTHS)")
    print("="*105)
    print(res_df.to_string(index=False))
    print("="*105)

if __name__ == "__main__":
    test_clean_orderblock()
