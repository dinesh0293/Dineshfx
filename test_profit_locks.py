import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def run_profit_lock_study():
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

    days = df['date'].unique()

    # Define Profit Lock configurations
    # mode:
    # - "none": standard SL / TP
    # - "be_trigger": trigger at trigger_r, move SL to entry (0R)
    # - "lock_step": trigger at trigger_r, move SL to lock_r
    # - "multi_step": stepped profit lock: at 1.5R -> 0.0R, at 2.5R -> 1.0R, at 3.5R -> 2.0R
    # - "trailing": trail SL behind peak by trail_dist_r once trigger_r is reached

    configs = [
        {"name": "1. Baseline (No Profit Lock - SL to TP)", "type": "none"},
        {"name": "2. BE at +1.0R (Lock to 0.0R)", "type": "lock_step", "trigger": 1.0, "lock": 0.0},
        {"name": "3. BE at +1.5R (Lock to 0.0R)", "type": "lock_step", "trigger": 1.5, "lock": 0.0},
        {"name": "4. BE at +2.0R (Lock to 0.0R)", "type": "lock_step", "trigger": 2.0, "lock": 0.0},
        {"name": "5. Profit Lock: Trigger +1.5R -> Lock +0.5R", "type": "lock_step", "trigger": 1.5, "lock": 0.5},
        {"name": "6. Profit Lock: Trigger +2.0R -> Lock +1.0R", "type": "lock_step", "trigger": 2.0, "lock": 1.0},
        {"name": "7. Profit Lock: Trigger +2.5R -> Lock +1.5R", "type": "lock_step", "trigger": 2.5, "lock": 1.5},
        {"name": "8. Multi-Step Lock (1.5R->BE, 2.5R->+1R, 3.5R->+2R)", "type": "multi_step"},
        {"name": "9. Trailing Stop (Trigger +2.0R, Trail 1.5R behind peak)", "type": "trailing", "trigger": 2.0, "trail": 1.5}
    ]

    all_results = []

    for cfg in configs:
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
            if r_size < 3.0 or r_size > 60.0: continue

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

                # High Sweep
                if h > r_h:
                    sweep_depth = h - r_h
                    if 0.30 <= sweep_depth <= 5.0:
                        if c < r_h and c < o: # Displacement
                            is_sell = True

                # Low Sweep
                elif l < r_l:
                    sweep_depth = r_l - l
                    if 0.30 <= sweep_depth <= 5.0:
                        if c > r_l and c > o: # Displacement
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
                    if rr_target < 1.0: continue

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
                    pnl_r = None
                    current_sl_r = -1.0 # in terms of R (-1.0 = initial SL)
                    peak_r = 0.0

                    for _, s in subs.iterrows():
                        # Calculate current candle favorable excursion and adverse excursion
                        if direction == "SELL":
                            cand_fav_price = entry - s['low']
                            cand_adv_price = s['high'] - entry
                        else:
                            cand_fav_price = s['high'] - entry
                            cand_adv_price = entry - s['low']

                        cand_fav_r = cand_fav_price / risk
                        peak_r = max(peak_r, cand_fav_r)

                        # Check profit lock updates based on peak_r
                        if cfg["type"] == "lock_step":
                            if peak_r >= cfg["trigger"]:
                                current_sl_r = max(current_sl_r, cfg["lock"])
                        elif cfg["type"] == "multi_step":
                            if peak_r >= 3.5:
                                current_sl_r = max(current_sl_r, 2.0)
                            elif peak_r >= 2.5:
                                current_sl_r = max(current_sl_r, 1.0)
                            elif peak_r >= 1.5:
                                current_sl_r = max(current_sl_r, 0.0)
                        elif cfg["type"] == "trailing":
                            if peak_r >= cfg["trigger"]:
                                trail_sl = peak_r - cfg["trail"]
                                current_sl_r = max(current_sl_r, trail_sl)

                        # Check if TP reached
                        if cand_fav_r >= rr_target:
                            pnl_r = rr_target
                            break

                        # Check if SL hit:
                        # In terms of R: adverse R is -cand_adv_price/risk.
                        # If current_sl_r is negative (e.g. -1.0): SL is hit if cand_adv_price/risk >= 1.0.
                        # If current_sl_r is positive (e.g. +0.5): SL is locked in profit. It gets hit if price drops below entry + 0.5R,
                        # i.e., lowest favorable price drops below 0.5R.
                        # Let's check low/high of candle:
                        if direction == "SELL":
                            # In sell: adverse movement is high.
                            # If current_sl_r <= 0, SL price is entry + abs(current_sl_r)*risk.
                            # If current_sl_r > 0, SL price is entry - current_sl_r*risk.
                            sl_price = entry - (current_sl_r * risk)
                            if s['high'] >= sl_price:
                                pnl_r = current_sl_r
                                break
                        else:
                            # In buy: adverse movement is low.
                            # sl_price is entry + current_sl_r*risk.
                            sl_price = entry + (current_sl_r * risk)
                            if s['low'] <= sl_price:
                                pnl_r = current_sl_r
                                break

                    # If trade not closed by end of session, close at market
                    if pnl_r is None:
                        if len(subs) > 0:
                            last_c = subs.iloc[-1]['close']
                            diff = (entry - last_c) if direction == "SELL" else (last_c - entry)
                            pnl_r = diff / risk
                        else:
                            pnl_r = 0.0

                    trades.append(pnl_r)

        if len(trades) > 0:
            ts = pd.Series(trades)
            tot = len(ts)
            wins = (ts > 0.05).sum()
            losses = (ts < -0.05).sum()
            bes = (abs(ts) <= 0.05).sum()
            wr = (wins / tot) * 100.0
            net_r = ts.sum()
            gross_win = ts[ts > 0].sum()
            gross_loss = abs(ts[ts < 0].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else np.nan
            
            cum = ts.cumsum()
            dd = (cum.cummax() - cum).max()

            all_results.append({
                "Configuration": cfg["name"],
                "Trades": tot,
                "Win": wins,
                "BE": bes,
                "Loss": losses,
                "Win Rate": f"{wr:.1f}%",
                "Profit Factor": f"{pf:.2f}",
                "Net Return (R)": f"{net_r:+.1f} R",
                "Max DD (R)": f"-{dd:.1f} R"
            })

    res_df = pd.DataFrame(all_results)
    print("\n" + "="*110)
    print("      PROFIT LOCK MECHANISM COMPARISON - XAUUSD 80,000 M5 BARS (VANTAGE MARKETS)")
    print("="*110)
    print(res_df.to_string(index=False))
    print("="*110)

if __name__ == "__main__":
    run_profit_lock_study()
