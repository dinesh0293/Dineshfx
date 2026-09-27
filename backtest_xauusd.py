import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def run_orb_backtest():
    if not mt5.initialize():
        print(f"Error: MT5 initialization failed: {mt5.last_error()}")
        return

    # Check for XAUUSD or XAUUSD+
    target_symbol = "XAUUSD"
    if not mt5.symbol_select(target_symbol, True):
        target_symbol = "XAUUSD+"
        if not mt5.symbol_select(target_symbol, True):
            print("Error: Neither XAUUSD nor XAUUSD+ could be selected.")
            mt5.shutdown()
            return

    print(f"Connected to MT5. Testing on Symbol: {target_symbol}")

    # Fetch 1 year of M5 bars (approx 75,000 bars)
    bars_count = 80000
    rates = mt5.copy_rates_from_pos(target_symbol, mt5.TIMEFRAME_M5, 0, bars_count)
    if rates is None or len(rates) == 0:
        print(f"Error: No rates fetched for {target_symbol}")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.sort_values('time').reset_index(drop=True)

    start_date = df['time'].min().strftime('%Y-%m-%d')
    end_date = df['time'].max().strftime('%Y-%m-%d')
    print(f"Historical Data Loaded: {len(df):,} bars from {start_date} to {end_date}")

    # Let's test two configurations:
    # 1. London Session Range (11:00 - 15:55 Broker Time / 04:00 - 08:55 EST)
    # 2. Pre-Market Range (15:00 - 16:25 Broker Time / 08:00 - 09:25 EST)
    configs = [
        {
            "name": "London Range (04:00 - 08:55 EST / 11:00 - 15:55 Broker)",
            "range_start_h": 11, "range_start_m": 0,
            "range_end_h": 15, "range_end_m": 55,
            "trade_start_h": 16, "trade_start_m": 0,
            "trade_end_h": 17, "trade_end_m": 30,
            "rr_ratios": [1.5, 2.0, 2.5]
        },
        {
            "name": "Pre-Market Range (08:00 - 09:25 EST / 15:00 - 16:25 Broker)",
            "range_start_h": 15, "range_start_m": 0,
            "range_end_h": 16, "range_end_m": 25,
            "trade_start_h": 16, "trade_start_m": 30,
            "trade_end_h": 17, "trade_end_m": 30,
            "rr_ratios": [1.5, 2.0, 2.5]
        }
    ]

    # Pre-group bars by trading day
    df['date'] = df['time'].dt.date
    days = df['date'].unique()

    symbol_info = mt5.symbol_info(target_symbol)
    point = symbol_info.point if symbol_info else 0.01

    results_summary = []

    for cfg in configs:
        for rr in cfg["rr_ratios"]:
            trades = []
            
            for d in days:
                day_df = df[df['date'] == d].copy()
                if len(day_df) < 30:
                    continue

                # 1. Determine Range
                r_start = datetime(d.year, d.month, d.day, cfg["range_start_h"], cfg["range_start_m"])
                r_end = datetime(d.year, d.month, d.day, cfg["range_end_h"], cfg["range_end_m"])
                
                range_bars = day_df[(day_df['time'] >= r_start) & (day_df['time'] <= r_end)]
                if len(range_bars) == 0:
                    continue

                r_high = range_bars['high'].max()
                r_low = range_bars['low'].min()
                if r_high <= r_low:
                    continue

                # 2. Trade Window
                t_start = datetime(d.year, d.month, d.day, cfg["trade_start_h"], cfg["trade_start_m"])
                t_end = datetime(d.year, d.month, d.day, cfg["trade_end_h"], cfg["trade_end_m"])

                trade_bars = day_df[(day_df['time'] >= t_start) & (day_df['time'] <= t_end)]
                if len(trade_bars) == 0:
                    continue

                trade_taken = False
                for idx, row in trade_bars.iterrows():
                    if trade_taken:
                        break

                    c_close = row['close']
                    c_open = row['open']
                    c_high = row['high']
                    c_low = row['low']
                    c_time = row['time']

                    # Bullish Breakout
                    if c_close > r_high:
                        entry_price = c_close
                        sl_price = c_low - 0.50 # 50 cents buffer for Gold
                        risk_dist = entry_price - sl_price
                        if risk_dist <= 0:
                            continue
                        tp_price = entry_price + (risk_dist * rr)
                        trade_taken = True
                        direction = "BUY"

                    # Bearish Breakout
                    elif c_close < r_low:
                        entry_price = c_close
                        sl_price = c_high + 0.50 # 50 cents buffer for Gold
                        risk_dist = sl_price - entry_price
                        if risk_dist <= 0:
                            continue
                        tp_price = entry_price - (risk_dist * rr)
                        trade_taken = True
                        direction = "SELL"
                    else:
                        continue

                    # Simulate trade outcome over subsequent bars of the day
                    subsequent_bars = day_df[day_df['time'] > c_time]
                    outcome = "HOLD"
                    pnl_r = 0.0

                    for _, s_row in subsequent_bars.iterrows():
                        s_high = s_row['high']
                        s_low = s_row['low']

                        if direction == "BUY":
                            if s_low <= sl_price:
                                outcome = "LOSS"
                                pnl_r = -1.0
                                break
                            elif s_high >= tp_price:
                                outcome = "WIN"
                                pnl_r = rr
                                break
                        else: # SELL
                            if s_high >= sl_price:
                                outcome = "LOSS"
                                pnl_r = -1.0
                                break
                            elif s_low <= tp_price:
                                outcome = "WIN"
                                pnl_r = rr
                                break

                    # If neither SL nor TP hit by end of day, close at market
                    if outcome == "HOLD" and len(subsequent_bars) > 0:
                        last_close = subsequent_bars.iloc[-1]['close']
                        if direction == "BUY":
                            diff = last_close - entry_price
                        else:
                            diff = entry_price - last_close
                        pnl_r = diff / risk_dist
                        outcome = "WIN" if pnl_r > 0 else "LOSS"

                    trades.append({
                        "date": d,
                        "direction": direction,
                        "entry": entry_price,
                        "sl": sl_price,
                        "tp": tp_price,
                        "outcome": outcome,
                        "pnl_r": pnl_r
                    })

            # Calculate Performance Metrics
            if len(trades) > 0:
                tdf = pd.DataFrame(trades)
                total_trades = len(tdf)
                wins = len(tdf[tdf['pnl_r'] > 0])
                losses = len(tdf[tdf['pnl_r'] <= 0])
                win_rate = (wins / total_trades) * 100.0
                total_r = tdf['pnl_r'].sum()
                gross_win_r = tdf[tdf['pnl_r'] > 0]['pnl_r'].sum()
                gross_loss_r = abs(tdf[tdf['pnl_r'] <= 0]['pnl_r'].sum())
                profit_factor = (gross_win_r / gross_loss_r) if gross_loss_r > 0 else np.nan
                
                # Drawdown calculation in R
                tdf['cum_r'] = tdf['pnl_r'].cumsum()
                tdf['peak_r'] = tdf['cum_r'].cummax()
                tdf['dd_r'] = tdf['peak_r'] - tdf['cum_r']
                max_dd_r = tdf['dd_r'].max()

                # Expectancy (R per trade)
                expectancy = total_r / total_trades

                # $10k initial balance, 1% risk ($100 per R)
                dollar_pnl = total_r * 100.0
                dollar_return_pct = (dollar_pnl / 10000.0) * 100.0

                results_summary.append({
                    "Config": cfg["name"],
                    "Risk:Reward": f"1:{rr}",
                    "Total Trades": total_trades,
                    "Wins": wins,
                    "Losses": losses,
                    "Win Rate (%)": f"{win_rate:.2f}%",
                    "Profit Factor": f"{profit_factor:.2f}",
                    "Total Net PnL (R)": f"+{total_r:.1f} R" if total_r > 0 else f"{total_r:.1f} R",
                    "Net Return ($10k @ 1%)": f"${dollar_pnl:+,.0f} ({dollar_return_pct:+.1f}%)",
                    "Max Drawdown (R)": f"-{max_dd_r:.1f} R",
                    "Expectancy / Trade": f"{expectancy:+.2f} R"
                })

    mt5.shutdown()

    # Print Formatted Results
    print("\n" + "="*85)
    print("        XAUUSD NEW YORK OPEN BREAKOUT STRATEGY - BACKTEST RESULTS")
    print(f"        Period: {start_date} to {end_date} | Timeframe: M5 | Asset: XAUUSD")
    print("="*85)
    res_df = pd.DataFrame(results_summary)
    print(res_df.to_string(index=False))
    print("="*85)

    # Save to CSV
    res_df.to_csv("xauusd_orb_backtest_results.csv", index=False)
    print("\nSaved detailed backtest results to: xauusd_orb_backtest_results.csv")

if __name__ == "__main__":
    run_orb_backtest()
