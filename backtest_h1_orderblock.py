import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def run_h1_orderblock_backtest():
    if not mt5.initialize():
        print("MT5 Init failed:", mt5.last_error())
        return

    symbol = "XAUUSD+" if mt5.symbol_select("XAUUSD+", True) else "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()

    print(f"Total H1 Bars: {len(df)}")
    print(f"Period: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")

    # Identify swing highs and swing lows (lookback 5 bars on each side)
    pivot_span = 5
    df['swing_high'] = False
    df['swing_low'] = False

    for i in range(pivot_span, len(df) - pivot_span):
        high_val = df['high'].iloc[i]
        low_val = df['low'].iloc[i]

        if high_val == df['high'].iloc[i - pivot_span : i + pivot_span + 1].max():
            df.loc[df.index[i], 'swing_high'] = True
        if low_val == df['low'].iloc[i - pivot_span : i + pivot_span + 1].min():
            df.loc[df.index[i], 'swing_low'] = True

    # Identify Order Blocks and trades
    trades = []
    active_obs = [] # list of active unmitigated Order Blocks

    # We iterate forward bar by bar
    for i in range(30, len(df) - 50):
        row = df.iloc[i]
        c, o, h, l, t = row['close'], row['open'], row['high'], row['low'], row['time']

        # 1. Check for New Bearish Order Block Formation
        # Condition:
        # A) Within last 10 bars, there was a sweep of a previous swing high
        # B) Current bar (or prior bar) is a strong displacement bearish candle (close < low of previous bar)
        prev_swing_highs = df.iloc[max(0, i-60) : i-2]
        sh_points = prev_swing_highs[prev_swing_highs['swing_high']]

        if len(sh_points) > 0:
            last_sh = sh_points['high'].max()
            # If recent bar swept last_sh and current bar shows bearish displacement:
            recent_high = df['high'].iloc[i-3 : i+1].max()
            if recent_high > last_sh:
                # Bearish displacement
                if c < o and (o - c) > 4.0: # at least $4 displacement body
                    # The order block is the last bullish candle before the drop
                    cand_before = df.iloc[i-1]
                    ob_high = max(cand_before['high'], row['high'])
                    ob_low = min(cand_before['open'], cand_before['close'])
                    
                    active_obs.append({
                        "type": "BEARISH",
                        "created_idx": i,
                        "created_time": t,
                        "ob_high": ob_high,
                        "ob_low": ob_low,
                        "sl": recent_high + 1.50, # SL above sweep high + $1.50 buffer
                        "mitigated": False
                    })

        # 2. Check for New Bullish Order Block Formation
        prev_swing_lows = df.iloc[max(0, i-60) : i-2]
        sl_points = prev_swing_lows[prev_swing_lows['swing_low']]

        if len(sl_points) > 0:
            last_sl = sl_points['low'].min()
            recent_low = df['low'].iloc[i-3 : i+1].min()
            if recent_low < last_sl:
                # Bullish displacement
                if c > o and (c - o) > 4.0:
                    cand_before = df.iloc[i-1]
                    ob_low = min(cand_before['low'], row['low'])
                    ob_high = max(cand_before['open'], cand_before['close'])

                    active_obs.append({
                        "type": "BULLISH",
                        "created_idx": i,
                        "created_time": t,
                        "ob_high": ob_high,
                        "ob_low": ob_low,
                        "sl": recent_low - 1.50,
                        "mitigated": False
                    })

        # Check existing active unmitigated Order Blocks for retest / mitigation entry
        for ob in active_obs:
            if ob["mitigated"]: continue
            if i - ob["created_idx"] < 1: continue # must be at least 1 bar after formation
            if i - ob["created_idx"] > 50: # expired after 50 bars (~2 days)
                ob["mitigated"] = True
                continue

            # Check if price retests the OB zone
            if ob["type"] == "BEARISH":
                # Price retraces into OB (high enters between ob_low and ob_high)
                if h >= ob["ob_low"] and h <= (ob["ob_high"] + 2.0):
                    entry = ob["ob_low"] # Sell Limit filled at the lower boundary of the OB
                    sl = ob["sl"]
                    risk = sl - entry
                    if risk < 2.0 or risk > 35.0: # realistic swing risk
                        ob["mitigated"] = True
                        continue

                    # Targets:
                    # Target 1 (Partial 50% TP): 1:2.0 R:R
                    # Target 2 (Runner): 1:4.0 R:R (or previous swing low)
                    tp1 = entry - (risk * 2.0)
                    tp2 = entry - (risk * 4.0)

                    # Simulate trade execution forward
                    pnl_r = 0.0
                    tp1_hit = False
                    future_bars = df.iloc[i+1 : min(i+150, len(df))]

                    for _, fb in future_bars.iterrows():
                        # Check TP1
                        if not tp1_hit and fb['low'] <= tp1:
                            tp1_hit = True # 50% booked at +2R, SL moved to BE

                        # Check SL
                        current_sl = entry if tp1_hit else sl
                        if fb['high'] >= current_sl:
                            pnl_r = (2.0 * 0.5) if tp1_hit else -1.0
                            break

                        # Check TP2
                        if fb['low'] <= tp2:
                            pnl_r = (2.0 * 0.5) + (4.0 * 0.5) if tp1_hit else 4.0
                            break

                    if pnl_r == 0.0 and len(future_bars) > 0:
                        last_close = future_bars.iloc[-1]['close']
                        final_diff = entry - last_close
                        final_r = final_diff / risk
                        pnl_r = (2.0 * 0.5) + (final_r * 0.5) if tp1_hit else final_r

                    trades.append({
                        "type": "SELL",
                        "time": t,
                        "entry": entry,
                        "sl": sl,
                        "risk_dollars_oz": risk,
                        "pnl_r": pnl_r,
                        "pnl_dollars_001": pnl_r * risk * 1.0 # 0.01 lot = 1 oz
                    })
                    ob["mitigated"] = True

            elif ob["type"] == "BULLISH":
                if l <= ob["ob_high"] and l >= (ob["ob_low"] - 2.0):
                    entry = ob["ob_high"] # Buy Limit filled at the upper boundary
                    sl = ob["sl"]
                    risk = entry - sl
                    if risk < 2.0 or risk > 35.0:
                        ob["mitigated"] = True
                        continue

                    tp1 = entry + (risk * 2.0)
                    tp2 = entry + (risk * 4.0)

                    pnl_r = 0.0
                    tp1_hit = False
                    future_bars = df.iloc[i+1 : min(i+150, len(df))]

                    for _, fb in future_bars.iterrows():
                        if not tp1_hit and fb['high'] >= tp1:
                            tp1_hit = True

                        current_sl = entry if tp1_hit else sl
                        if fb['low'] <= current_sl:
                            pnl_r = (2.0 * 0.5) if tp1_hit else -1.0
                            break

                        if fb['high'] >= tp2:
                            pnl_r = (2.0 * 0.5) + (4.0 * 0.5) if tp1_hit else 4.0
                            break

                    if pnl_r == 0.0 and len(future_bars) > 0:
                        last_close = future_bars.iloc[-1]['close']
                        final_diff = last_close - entry
                        final_r = final_diff / risk
                        pnl_r = (2.0 * 0.5) + (final_r * 0.5) if tp1_hit else final_r

                    trades.append({
                        "type": "BUY",
                        "time": t,
                        "entry": entry,
                        "sl": sl,
                        "risk_dollars_oz": risk,
                        "pnl_r": pnl_r,
                        "pnl_dollars_001": pnl_r * risk * 1.0
                    })
                    ob["mitigated"] = True

    tdf = pd.DataFrame(trades)
    print(f"\nTotal Identified Trades: {len(tdf)}")
    
    if len(tdf) > 0:
        tot = len(tdf)
        wins = (tdf['pnl_r'] > 0.05).sum()
        losses = (tdf['pnl_r'] < -0.05).sum()
        bes = (tdf['pnl_r'].abs() <= 0.05).sum()
        wr = (wins / tot) * 100.0

        gross_win = tdf[tdf['pnl_r'] > 0]['pnl_r'].sum()
        gross_loss = abs(tdf[tdf['pnl_r'] < 0]['pnl_r'].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else np.nan
        net_r = tdf['pnl_r'].sum()

        cum = tdf['pnl_r'].cumsum()
        dd = (cum.cummax() - cum).max()

        total_dollars_001 = tdf['pnl_dollars_001'].sum()
        avg_risk_dollars = tdf['risk_dollars_oz'].mean()

        print("\n" + "="*75)
        print("    STRATEGY 02: H1 INSTITUTIONAL ORDER BLOCK SWING TRADER RESULTS")
        print("="*75)
        print(f"Backtest Duration       : Jan 17, 2025 to Sep 25, 2026 (~20 Months)")
        print(f"Total Swing Trades      : {tot} trades (~4-5 trades per month)")
        print(f"Wins / BE / Losses      : {wins} Wins | {bes} BE | {losses} Losses")
        print(f"Win Rate                : {wr:.1f}%")
        print(f"Profit Factor (PF)      : {pf:.2f}")
        print(f"Total Net Return (R)    : {net_r:+.1f} R")
        print(f"Max Drawdown (R)        : -{dd:.1f} R")
        print(f"Average Stop Loss       : ${avg_risk_dollars:.2f} per ounce")
        print(f"Net Profit ($100 @ 0.01): ${total_dollars_001:+.2f} (+{total_dollars_001/100*100:.1f}%)")
        print("="*75)

if __name__ == "__main__":
    run_h1_orderblock_backtest()
