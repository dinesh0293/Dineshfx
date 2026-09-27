import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def test_smc_mss():
    if not mt5.initialize():
        print("MT5 Init failed")
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()

    # Swing detection (pivot 5)
    span = 5
    df['sh'] = False
    df['sl'] = False

    for i in range(span, len(df) - span):
        if df['high'].iloc[i] == df['high'].iloc[i - span : i + span + 1].max():
            df.loc[df.index[i], 'sh'] = True
        if df['low'].iloc[i] == df['low'].iloc[i - span : i + span + 1].min():
            df.loc[df.index[i], 'sl'] = True

    # Test different RR targets: 1:1.5, 1:2.0, 1:2.5, 1:3.0
    rr_targets = [1.5, 2.0, 2.5, 3.0]

    for target_rr in rr_targets:
        trades = []

        for i in range(30, len(df) - 60):
            row = df.iloc[i]
            c, o, h, l, t = row['close'], row['open'], row['high'], row['low'], row['time']

            # Find previous swing high and swing low
            past = df.iloc[max(0, i-40) : i-1]
            sh_pts = past[past['sh']]
            sl_pts = past[past['sl']]

            if len(sh_pts) == 0 or len(sl_pts) == 0: continue

            last_sh_price = sh_pts['high'].iloc[-1]
            last_sl_price = sl_pts['low'].iloc[-1]

            # 1. Bearish MSS Setup:
            # - Price recently swept last_sh_price (high > last_sh_price within last 5 bars)
            # - Current bar closes below last_sl_price (Market Structure Shift!)
            recent_high = df['high'].iloc[max(0, i-6) : i+1].max()
            if recent_high > last_sh_price and c < last_sl_price and o > last_sl_price:
                entry = c
                stop_loss = recent_high + 1.50
                risk = stop_loss - entry

                if 3.0 <= risk <= 30.0:
                    tp = entry - (risk * target_rr)

                    pnl_r = None
                    subs = df.iloc[i+1 : min(i+150, len(df))]

                    for _, s in subs.iterrows():
                        if s['high'] >= stop_loss:
                            pnl_r = -1.0
                            break
                        if s['low'] <= tp:
                            pnl_r = target_rr
                            break

                    if pnl_r is None and len(subs) > 0:
                        diff = entry - subs.iloc[-1]['close']
                        pnl_r = diff / risk
                    elif pnl_r is None:
                        pnl_r = 0.0

                    trades.append(pnl_r)

            # 2. Bullish MSS Setup:
            # - Price recently swept last_sl_price (low < last_sl_price within last 5 bars)
            # - Current bar closes above last_sh_price (Bullish Market Structure Shift!)
            recent_low = df['low'].iloc[max(0, i-6) : i+1].min()
            if recent_low < last_sl_price and c > last_sh_price and o < last_sh_price:
                entry = c
                stop_loss = recent_low - 1.50
                risk = entry - stop_loss

                if 3.0 <= risk <= 30.0:
                    tp = entry + (risk * target_rr)

                    pnl_r = None
                    subs = df.iloc[i+1 : min(i+150, len(df))]

                    for _, s in subs.iterrows():
                        if s['low'] <= stop_loss:
                            pnl_r = -1.0
                            break
                        if s['high'] >= tp:
                            pnl_r = target_rr
                            break

                    if pnl_r is None and len(subs) > 0:
                        diff = subs.iloc[-1]['close'] - entry
                        pnl_r = diff / risk
                    elif pnl_r is None:
                        pnl_r = 0.0

                    trades.append(pnl_r)

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

            print(f"Target 1:{target_rr} R:R | Trades: {tot} | Win Rate: {wr:.1f}% | Profit Factor: {pf:.2f} | Net R: {net_r:+.1f} R | Max DD: -{dd:.1f} R")

if __name__ == "__main__":
    test_smc_mss()
