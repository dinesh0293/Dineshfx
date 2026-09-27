import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def test_fine():
    if not mt5.initialize():
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

    pct_list = [0.65, 0.70, 0.75, 0.80, 0.85]
    lock_types = [
        ("BE (0.0R)", 0.0),
        ("Lock +0.5R", 0.5),
        ("Lock +1.0R", 1.0),
        ("Lock Half-Way (0.5 * trigger)", "half")
    ]

    configs = []
    configs.append({"name": "Baseline (No Profit Lock)", "pct": 0.0, "lock": "none"})

    for pct in pct_list:
        for lt_name, lt_val in lock_types:
            configs.append({
                "name": f"Trigger at {int(pct*100)}% to TP -> {lt_name}",
                "pct": pct,
                "lock": lt_val
            })

    all_results = []

    for cfg in configs:
        trades = []

        for d in days:
            day_df = df[df['date'] == d]
            if len(day_df) < 30: continue

            # London Range: 11:00 - 15:55 Broker Time
            r_start = datetime(d.year, d.month, d.day, 11, 0)
            r_end = datetime(d.year, d.month, d.day, 15, 55)
            r_bars = day_df[(day_df['time'] >= r_start) & (day_df['time'] <= r_end)]
            if len(r_bars) == 0: continue
            
            r_h = r_bars['high'].max()
            r_l = r_bars['low'].min()
            r_mid = (r_h + r_l) / 2.0
            r_size = r_h - r_l
            if r_size < 3.0 or r_size > 60.0: continue

            # NY Open Window: 16:00 - 18:30 Broker Time
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
                    if 0.30 <= sweep_depth <= 5.0 and c < r_h:
                        is_sell = True

                # Low Sweep
                elif l < r_l:
                    sweep_depth = r_l - l
                    if 0.30 <= sweep_depth <= 5.0 and c > r_l:
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
                    current_sl_r = -1.0 # -1R
                    peak_r = 0.0

                    for _, s in subs.iterrows():
                        cand_fav_price = (entry - s['low']) if direction == "SELL" else (s['high'] - entry)
                        cand_fav_r = cand_fav_price / risk
                        peak_r = max(peak_r, cand_fav_r)

                        # Profit lock check
                        if cfg["pct"] > 0:
                            if (peak_r / rr_target) >= cfg["pct"]:
                                if cfg["lock"] == "half":
                                    lock_val = (peak_r * 0.5)
                                else:
                                    lock_val = cfg["lock"]
                                current_sl_r = max(current_sl_r, lock_val)

                        # Check TP hit
                        if cand_fav_r >= rr_target:
                            pnl_r = rr_target
                            break

                        # Check SL hit
                        sl_price = entry - (current_sl_r * risk) if direction == "SELL" else entry + (current_sl_r * risk)
                        if direction == "SELL" and s['high'] >= sl_price:
                            pnl_r = current_sl_r
                            break
                        elif direction == "BUY" and s['low'] <= sl_price:
                            pnl_r = current_sl_r
                            break

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
    # Sort by Profit Factor descending
    res_df['PF_num'] = res_df['Profit Factor'].astype(float)
    res_df = res_df.sort_values(by='PF_num', ascending=False).drop(columns=['PF_num'])
    print("\n" + "="*115)
    print("      TOP PROFIT LOCK MECHANISMS SORTED BY PROFIT FACTOR (PF)")
    print("="*115)
    print(res_df.to_string(index=False))
    print("="*115)

if __name__ == "__main__":
    test_fine()
