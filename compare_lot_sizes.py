import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def compare_lots():
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

    # We will simulate the exact proven strategy with 75% profit lock:
    # Trigger: at 75% of distance to TP, move SL to Break-Even (0.0R)
    trades_data = []

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
                risk_pts = sl - entry
                if risk_pts <= 0.20 or risk_pts > 10.0: continue
                tp = r_mid
                reward_pts = entry - tp
                if reward_pts <= 0: continue
                rr_target = reward_pts / risk_pts
                if rr_target < 1.0: continue

                direction = "SELL"
                trade_taken = True

            elif is_buy:
                entry = c
                sl = l - 0.50
                risk_pts = entry - sl
                if risk_pts <= 0.20 or risk_pts > 10.0: continue
                tp = r_mid
                reward_pts = tp - entry
                if reward_pts <= 0: continue
                rr_target = reward_pts / risk_pts
                if rr_target < 1.0: continue

                direction = "BUY"
                trade_taken = True

            if trade_taken:
                subs = day_df[day_df['time'] > t]
                pnl_dollars_per_oz = None
                pnl_r = None
                be_active = False

                for _, s in subs.iterrows():
                    cand_fav_pts = (entry - s['low']) if direction == "SELL" else (s['high'] - entry)
                    cand_adv_pts = (s['high'] - entry) if direction == "SELL" else (entry - s['low'])

                    # Check 75% profit lock trigger
                    if (cand_fav_pts / reward_pts) >= 0.75:
                        be_active = True

                    # Check TP hit
                    if cand_fav_pts >= reward_pts:
                        pnl_dollars_per_oz = reward_pts
                        pnl_r = rr_target
                        break

                    # Check SL hit
                    if be_active:
                        # SL is at entry
                        if cand_adv_pts >= 0.0:
                            pnl_dollars_per_oz = 0.0
                            pnl_r = 0.0
                            break
                    else:
                        if cand_adv_pts >= risk_pts:
                            pnl_dollars_per_oz = -risk_pts
                            pnl_r = -1.0
                            break

                if pnl_dollars_per_oz is None:
                    if len(subs) > 0:
                        last_c = subs.iloc[-1]['close']
                        diff = (entry - last_c) if direction == "SELL" else (last_c - entry)
                        pnl_dollars_per_oz = diff
                        pnl_r = diff / risk_pts
                    else:
                        pnl_dollars_per_oz = 0.0
                        pnl_r = 0.0

                trades_data.append({
                    "date": d,
                    "direction": direction,
                    "entry": entry,
                    "sl": sl,
                    "tp": tp,
                    "risk_pts": risk_pts,
                    "pnl_dollars_per_oz": pnl_dollars_per_oz,
                    "pnl_r": pnl_r
                })

    trades_df = pd.DataFrame(trades_data)
    print(f"Total simulated trades: {len(trades_df)}")

    # On Vantage Markets:
    # 1.0 lot XAUUSD = 100 oz
    # 0.01 lot = 1 oz. Profit = pnl_dollars_per_oz * 1.0
    # 0.02 lot = 2 oz. Profit = pnl_dollars_per_oz * 2.0

    starting_balance = 100.0

    for lot in [0.01, 0.02]:
        multiplier = lot * 100.0 # 0.01 * 100 = 1 oz; 0.02 * 100 = 2 oz
        pnl_dollars = trades_df['pnl_dollars_per_oz'] * multiplier

        # Compute metrics
        tot = len(pnl_dollars)
        wins = (pnl_dollars > 0.05).sum()
        bes = (pnl_dollars.abs() <= 0.05).sum()
        losses = (pnl_dollars < -0.05).sum()
        wr = (wins / tot) * 100.0

        gross_win = pnl_dollars[pnl_dollars > 0].sum()
        gross_loss = abs(pnl_dollars[pnl_dollars < 0].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else np.nan

        net_profit = pnl_dollars.sum()
        final_balance = starting_balance + net_profit
        roi_pct = (net_profit / starting_balance) * 100.0

        # Equity curve & Max Drawdown
        equity = starting_balance + pnl_dollars.cumsum()
        min_equity = equity.min()
        peak = equity.cummax()
        drawdown_dollars = peak - equity
        max_dd_dollars = drawdown_dollars.max()
        drawdown_pct = (drawdown_dollars / peak) * 100.0
        max_dd_pct = drawdown_pct.max()

        # Consecutive losses
        loss_streak = 0
        max_loss_streak = 0
        for p in pnl_dollars:
            if p < -0.05:
                loss_streak += 1
                max_loss_streak = max(max_loss_streak, loss_streak)
            elif p > 0.05:
                loss_streak = 0

        avg_win = pnl_dollars[pnl_dollars > 0].mean() if wins > 0 else 0
        avg_loss = pnl_dollars[pnl_dollars < 0].mean() if losses > 0 else 0
        max_win = pnl_dollars.max()
        max_loss = pnl_dollars.min()

        # Margin requirement per trade (at 1:500 leverage on Vantage)
        margin_req = 2600.0 * lot / 5.0 # roughly $5.20 for 0.01 lot, $10.40 for 0.02 lot

        print(f"\n{'='*65}")
        print(f"             ACCOUNT ANALYSIS: {lot} LOT SIZE ($100 START)")
        print(f"{'='*65}")
        print(f"Starting Capital       : ${starting_balance:.2f}")
        print(f"Lowest Equity Reached  : ${min_equity:.2f} ({'SURVIVED' if min_equity > 15 else 'BLOWOUT / MARGIN CALL RISK!'})")
        print(f"Final Balance          : ${final_balance:.2f} ({roi_pct:+.1f}%)")
        print(f"Net Profit ($)         : ${net_profit:+.2f}")
        print(f"Profit Factor (PF)     : {pf:.2f}")
        print(f"Total Trades           : {tot}")
        print(f"Wins / BE / Losses     : {wins} Wins | {bes} BE | {losses} Losses")
        print(f"Win Rate (%)           : {wr:.1f}%")
        print(f"Max Losing Streak      : {max_loss_streak} consecutive losses")
        print(f"Average Win ($)        : +${avg_win:.2f}")
        print(f"Average Loss ($)       : -${abs(avg_loss):.2f}")
        print(f"Largest Win ($)        : +${max_win:.2f}")
        print(f"Largest Loss ($)       : -${abs(max_loss):.2f}")
        print(f"Peak-to-Trough DD ($)  : -${max_dd_dollars:.2f}")
        print(f"Peak-to-Trough DD (%)  : {max_dd_pct:.1f}%")
        print(f"Margin Used per Trade  : ~${margin_req:.2f} ({margin_req/starting_balance*100:.1f}% of capital)")
        print(f"Free Margin Buffer     : ${starting_balance - margin_req:.2f}")
        print(f"{'='*65}")

if __name__ == "__main__":
    compare_lots()
