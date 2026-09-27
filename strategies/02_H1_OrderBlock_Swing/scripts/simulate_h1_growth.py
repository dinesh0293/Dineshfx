import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def simulate_h1_growth():
    if not mt5.initialize():
        print("MT5 Init failed")
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    # Daily trend
    d_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 800)
    d_df = pd.DataFrame(d_rates)
    d_df['time'] = pd.to_datetime(d_df['time'], unit='s')
    d_df['date'] = d_df['time'].dt.date
    d_df['ema50'] = d_df['close'].ewm(span=50, adjust=False).mean()

    # H1 bars
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['date'] = df['time'].dt.date
    mt5.shutdown()

    df = df.merge(d_df[['date', 'ema50']], on='date', how='left')
    df['ema50'] = df['ema50'].ffill()

    span = 8
    df['sh'] = False
    df['sl'] = False

    for i in range(span, len(df) - span):
        if df['high'].iloc[i] == df['high'].iloc[i - span : i + span + 1].max():
            df.loc[df.index[i], 'sh'] = True
        if df['low'].iloc[i] == df['low'].iloc[i - span : i + span + 1].min():
            df.loc[df.index[i], 'sl'] = True

    obs = []
    trades = []

    target_rr = 4.0 # Model B: 1:4.0 R:R

    for i in range(20, len(df) - 60):
        row = df.iloc[i]
        c, o, h, l, t, ema = row['close'], row['open'], row['high'], row['low'], row['time'], row['ema50']

        # Bearish OB
        if df['sh'].iloc[i]:
            cand = df.iloc[i]
            drop_price = df['low'].iloc[i+1 : i+5].min()
            drop_dist = cand['high'] - drop_price

            trend_ok = (cand['close'] < ema)

            prior_sh = df.iloc[max(0, i-60) : i-2]
            prior_sh_pts = prior_sh[prior_sh['sh']]
            sweep_ok = True
            if len(prior_sh_pts) > 0:
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

        # Bullish OB
        if df['sl'].iloc[i]:
            cand = df.iloc[i]
            rally_price = df['high'].iloc[i+1 : i+5].max()
            rally_dist = rally_price - cand['low']

            trend_ok = (cand['close'] > ema)

            prior_sl = df.iloc[max(0, i-60) : i-2]
            prior_sl_pts = prior_sl[prior_sl['sl']]
            sweep_ok = True
            if len(prior_sl_pts) > 0:
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

        # Retest checks
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

                    tp = entry - (risk * target_rr)
                    pnl_r = 0.0
                    f_bars = df.iloc[i+1 : min(i+180, len(df))]

                    for _, fb in f_bars.iterrows():
                        if fb['high'] >= sl:
                            pnl_r = -1.0
                            break
                        if fb['low'] <= tp:
                            pnl_r = target_rr
                            break

                    if pnl_r == 0.0 and len(f_bars) > 0:
                        last_c = f_bars.iloc[-1]['close']
                        pnl_r = (entry - last_c) / risk

                    # Dollar profit on 0.01 lot (1 oz):
                    dollar_pnl = pnl_r * risk * 1.0

                    trades.append({
                        "trade": len(trades) + 1,
                        "date": t.date(),
                        "time": t,
                        "type": "SELL",
                        "risk": risk,
                        "pnl_r": pnl_r,
                        "dollar_pnl": dollar_pnl
                    })
                    ob["active"] = False

            elif ob["type"] == "BULLISH":
                if row['low'] <= ob["top"] and row['low'] >= (ob["bottom"] - 1.5):
                    entry = ob["top"]
                    sl = ob["sl"]
                    risk = entry - sl
                    if risk < 3.0 or risk > 35.0:
                        ob["active"] = False
                        continue

                    tp = entry + (risk * target_rr)
                    pnl_r = 0.0
                    f_bars = df.iloc[i+1 : min(i+180, len(df))]

                    for _, fb in f_bars.iterrows():
                        if fb['low'] <= sl:
                            pnl_r = -1.0
                            break
                        if fb['high'] >= tp:
                            pnl_r = target_rr
                            break

                    if pnl_r == 0.0 and len(f_bars) > 0:
                        last_c = f_bars.iloc[-1]['close']
                        pnl_r = (last_c - entry) / risk

                    dollar_pnl = pnl_r * risk * 1.0

                    trades.append({
                        "trade": len(trades) + 1,
                        "date": t.date(),
                        "time": t,
                        "type": "BUY",
                        "risk": risk,
                        "pnl_r": pnl_r,
                        "dollar_pnl": dollar_pnl
                    })
                    ob["active"] = False

    tdf = pd.DataFrame(trades)
    tdf['cum_profit'] = tdf['dollar_pnl'].cumsum()
    tdf['balance'] = 100.0 + tdf['cum_profit']

    print(f"Total Trades: {len(tdf)}")
    print(f"Start Date  : {tdf['date'].iloc[0]}")
    print(f"End Date    : {tdf['date'].iloc[-1]}")
    print(f"Min Balance : ${tdf['balance'].min():.2f}")
    print(f"Final Balance: ${tdf['balance'].iloc[-1]:.2f}")

    # Check when account crossed $200
    hit_200 = tdf[tdf['balance'] >= 200.0]
    if len(hit_200) > 0:
        first_row = hit_200.iloc[0]
        days_taken = (first_row['date'] - tdf['date'].iloc[0]).days
        months_taken = days_taken / 30.4375
        print("\n>>> ACCOUNT DOUBLED TO $200.00!")
        print(f"    Date Reached       : {first_row['date']}")
        print(f"    Trade Number       : Trade #{first_row['trade']} of {len(tdf)}")
        print(f"    Balance on that day: ${first_row['balance']:.2f}")
        print(f"    Calendar Days      : {days_taken} days (~{months_taken:.1f} months)")
    else:
        print("Did not reach $200")

    # Let's also check if account reached $300, $400, $500
    for target in [300.0, 400.0, 500.0]:
        hit = tdf[tdf['balance'] >= target]
        if len(hit) > 0:
            r = hit.iloc[0]
            d_taken = (r['date'] - tdf['date'].iloc[0]).days
            m_taken = d_taken / 30.4375
            print(f"    Reached ${target:.0f} on       : {r['date']} (~{m_taken:.1f} mos, Trade #{r['trade']}) - Balance: ${r['balance']:.2f}")

if __name__ == "__main__":
    simulate_h1_growth()
