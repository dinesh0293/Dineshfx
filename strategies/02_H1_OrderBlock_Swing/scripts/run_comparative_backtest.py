import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# --- 1. Fetch Historical Data from MT5 ---
if not mt5.initialize():
    print("MT5 initialization failed")
    exit()

symbol = "XAUUSD"
rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)
if rates_h1 is None:
    symbol = "XAUUSD+"
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 10000)

rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 800)
mt5.shutdown()

df_h1 = pd.DataFrame(rates_h1)
df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
df_h1['date'] = df_h1['time'].dt.date

df_d1 = pd.DataFrame(rates_d1)
df_d1['time'] = pd.to_datetime(df_d1['time'], unit='s')
df_d1['date'] = df_d1['time'].dt.date
df_d1['ema50'] = df_d1['close'].ewm(span=50, adjust=False).mean()

# Merge Daily EMA onto H1
df_h1 = df_h1.merge(df_d1[['date', 'ema50']], on='date', how='left')
df_h1['ema50'] = df_h1['ema50'].ffill()

span = 8
df_h1['sh'] = False
df_h1['sl'] = False

for i in range(span, len(df_h1) - span):
    if df_h1['high'].iloc[i] == df_h1['high'].iloc[i - span : i + span + 1].max():
        df_h1.loc[df_h1.index[i], 'sh'] = True
    if df_h1['low'].iloc[i] == df_h1['low'].iloc[i - span : i + span + 1].min():
        df_h1.loc[df_h1.index[i], 'sl'] = True

print(f"Loaded {len(df_h1)} H1 bars from {df_h1.iloc[0]['time']} to {df_h1.iloc[-1]['time']}")

# --- 2. Simulation Function ---
def simulate(mode="STANDARD", target_rr=4.0, partial_tp=True):
    obs = []
    trades = []
    
    open_positions = []
    account_balance = 100.0
    equity_curve = [100.0]
    next_ticket = 1
    
    for i in range(30, len(df_h1) - 10):
        row = df_h1.iloc[i]
        c, o, h, l, t, ema = row['close'], row['open'], row['high'], row['low'], row['time'], row['ema50']
        
        # --- A. Check for New Order Block Formation at i - span ---
        conf_idx = i - span
        if conf_idx >= span:
            cand = df_h1.iloc[conf_idx]
            
            # Bearish OB
            if df_h1['sh'].iloc[conf_idx]:
                drop_price = df_h1['low'].iloc[conf_idx + 1 : conf_idx + 5].min()
                drop_dist = cand['high'] - drop_price
                trend_ok = (cand['close'] < ema)
                
                prior_sh = df_h1.iloc[max(0, conf_idx - 60) : conf_idx - 2]
                prior_sh_pts = prior_sh[prior_sh['sh']]
                sweep_ok = True
                if len(prior_sh_pts) > 0:
                    sweep_ok = (cand['high'] > prior_sh_pts['high'].max())
                
                if trend_ok and sweep_ok and drop_dist >= 8.0:
                    new_sl = cand['high'] + 2.0
                    obs.append({
                        "id": len(obs),
                        "type": "BEARISH",
                        "idx": conf_idx,
                        "time": cand['time'],
                        "top": cand['high'],
                        "bottom": min(cand['open'], cand['close']),
                        "sl": new_sl,
                        "active": True
                    })
                    
                    # Option 2: Continuation Trailing for open SELL positions
                    for pos in open_positions:
                        if pos['type'] == 'SELL':
                            curr_gain_pts = pos['open_price'] - c
                            curr_r = curr_gain_pts / pos['initial_risk']
                            if curr_r >= 1.5:
                                if new_sl < pos['sl'] and new_sl < pos['open_price']:
                                    pos['sl'] = new_sl

            # Bullish OB
            if df_h1['sl'].iloc[conf_idx]:
                rally_price = df_h1['high'].iloc[conf_idx + 1 : conf_idx + 5].max()
                rally_dist = rally_price - cand['low']
                trend_ok = (cand['close'] > ema)
                
                prior_sl = df_h1.iloc[max(0, conf_idx - 60) : conf_idx - 2]
                prior_sl_pts = prior_sl[prior_sl['sl']]
                sweep_ok = True
                if len(prior_sl_pts) > 0:
                    sweep_ok = (cand['low'] < prior_sl_pts['low'].min())
                
                if trend_ok and sweep_ok and rally_dist >= 8.0:
                    new_sl = cand['low'] - 2.0
                    obs.append({
                        "id": len(obs),
                        "type": "BULLISH",
                        "idx": conf_idx,
                        "time": cand['time'],
                        "top": max(cand['open'], cand['close']),
                        "bottom": cand['low'],
                        "sl": new_sl,
                        "active": True
                    })
                    
                    # Option 2: Continuation Trailing for open BUY positions
                    for pos in open_positions:
                        if pos['type'] == 'BUY':
                            curr_gain_pts = c - pos['open_price']
                            curr_r = curr_gain_pts / pos['initial_risk']
                            if curr_r >= 1.5:
                                if new_sl > pos['sl'] and new_sl > pos['open_price']:
                                    pos['sl'] = new_sl

        # --- B. Bar-by-Bar Management of Open Positions ---
        surviving_pos = []
        for pos in open_positions:
            closed = False
            exit_price = 0.0
            reason = ""
            
            if pos['type'] == 'SELL':
                if h >= pos['sl']:
                    exit_price = pos['sl']
                    reason = "SL"
                    closed = True
                elif l <= pos['tp']:
                    exit_price = pos['tp']
                    reason = "TP"
                    closed = True
                else:
                    pts_gain = pos['open_price'] - l
                    r_gain = pts_gain / pos['initial_risk']
                    if r_gain >= 2.0:
                        if pos['sl'] > pos['open_price']:
                            pos['sl'] = pos['open_price']
                        
                        if mode == "STANDARD" and partial_tp and not pos['partial_done']:
                            p_vol = pos['lot'] * 0.5
                            p_gain = 2.0 * pos['initial_risk'] * (p_vol * 100.0) # Correct contract size
                            account_balance += p_gain
                            pos['lot'] -= p_vol
                            pos['partial_done'] = True

            elif pos['type'] == 'BUY':
                if l <= pos['sl']:
                    exit_price = pos['sl']
                    reason = "SL"
                    closed = True
                elif h >= pos['tp']:
                    exit_price = pos['tp']
                    reason = "TP"
                    closed = True
                else:
                    pts_gain = h - pos['open_price']
                    r_gain = pts_gain / pos['initial_risk']
                    if r_gain >= 2.0:
                        if pos['sl'] < pos['open_price']:
                            pos['sl'] = pos['open_price']
                        
                        if mode == "STANDARD" and partial_tp and not pos['partial_done']:
                            p_vol = pos['lot'] * 0.5
                            p_gain = 2.0 * pos['initial_risk'] * (p_vol * 100.0)
                            account_balance += p_gain
                            pos['lot'] -= p_vol
                            pos['partial_done'] = True

            if closed:
                pts = (pos['open_price'] - exit_price) if pos['type'] == 'SELL' else (exit_price - pos['open_price'])
                pnl_r = pts / pos['initial_risk']
                dollar_pnl = pts * (pos['lot'] * 100.0) # $1 per dollar on 0.01 lot
                account_balance += dollar_pnl
                
                trades.append({
                    "ticket": pos['ticket'],
                    "type": pos['type'],
                    "open_time": pos['open_time'],
                    "close_time": t,
                    "open_price": pos['open_price'],
                    "exit_price": exit_price,
                    "reason": reason,
                    "pnl_r": pnl_r,
                    "dollar_pnl": dollar_pnl,
                    "is_pyramid": pos['is_pyramid']
                })
            else:
                surviving_pos.append(pos)
                
        open_positions = surviving_pos

        # --- C. Check Retest Entries for Active Order Blocks ---
        max_trades = 1 if mode == "STANDARD" else 2
        
        if len(open_positions) < max_trades:
            for ob in obs:
                if not ob["active"]: continue
                if i - ob["idx"] < 3: continue
                if i - ob["idx"] > 120:
                    ob["active"] = False
                    continue
                
                # Bearish OB Retest
                if ob["type"] == "BEARISH":
                    if h >= ob["bottom"] and h <= (ob["top"] + 1.5):
                        entry = ob["bottom"]
                        sl = ob["sl"]
                        risk = sl - entry
                        if risk < 3.0 or risk > 35.0:
                            ob["active"] = False
                            continue
                        
                        tp = entry - (risk * target_rr)
                        
                        if len(open_positions) == 0:
                            open_positions.append({
                                'ticket': next_ticket,
                                'type': 'SELL',
                                'lot': 0.01,
                                'open_price': entry,
                                'sl': sl,
                                'tp': tp,
                                'open_time': t,
                                'initial_risk': risk,
                                'partial_done': False,
                                'is_pyramid': False
                            })
                            next_ticket += 1
                            ob["active"] = False
                            break
                        
                        elif len(open_positions) == 1 and mode == "PYRAMID":
                            base_pos = open_positions[0]
                            if base_pos['type'] == 'SELL':
                                gain_pts = base_pos['open_price'] - c
                                curr_r = gain_pts / base_pos['initial_risk']
                                if curr_r >= 2.0 and base_pos['sl'] <= base_pos['open_price']:
                                    open_positions.append({
                                        'ticket': next_ticket,
                                        'type': 'SELL',
                                        'lot': 0.01,
                                        'open_price': entry,
                                        'sl': sl,
                                        'tp': base_pos['tp'],
                                        'open_time': t,
                                        'initial_risk': risk,
                                        'partial_done': False,
                                        'is_pyramid': True
                                    })
                                    next_ticket += 1
                                    ob["active"] = False
                                    if sl < base_pos['sl']:
                                        base_pos['sl'] = sl
                                    break

                # Bullish OB Retest
                elif ob["type"] == "BULLISH":
                    if l <= ob["top"] and l >= (ob["bottom"] - 1.5):
                        entry = ob["top"]
                        sl = ob["sl"]
                        risk = entry - sl
                        if risk < 3.0 or risk > 35.0:
                            ob["active"] = False
                            continue
                        
                        tp = entry + (risk * target_rr)
                        
                        if len(open_positions) == 0:
                            open_positions.append({
                                'ticket': next_ticket,
                                'type': 'BUY',
                                'lot': 0.01,
                                'open_price': entry,
                                'sl': sl,
                                'tp': tp,
                                'open_time': t,
                                'initial_risk': risk,
                                'partial_done': False,
                                'is_pyramid': False
                            })
                            next_ticket += 1
                            ob["active"] = False
                            break
                        
                        elif len(open_positions) == 1 and mode == "PYRAMID":
                            base_pos = open_positions[0]
                            if base_pos['type'] == 'BUY':
                                gain_pts = c - base_pos['open_price']
                                curr_r = gain_pts / base_pos['initial_risk']
                                if curr_r >= 2.0 and base_pos['sl'] >= base_pos['open_price']:
                                    open_positions.append({
                                        'ticket': next_ticket,
                                        'type': 'BUY',
                                        'lot': 0.01,
                                        'open_price': entry,
                                        'sl': sl,
                                        'tp': base_pos['tp'],
                                        'open_time': t,
                                        'initial_risk': risk,
                                        'partial_done': False,
                                        'is_pyramid': True
                                    })
                                    next_ticket += 1
                                    ob["active"] = False
                                    if sl > base_pos['sl']:
                                        base_pos['sl'] = sl
                                    break
        
        equity_curve.append(account_balance)
        
    return trades, account_balance, equity_curve

trades_std, bal_std, eq_std = simulate("STANDARD", target_rr=4.0, partial_tp=True)
trades_std_full, bal_std_full, eq_std_full = simulate("STANDARD", target_rr=4.0, partial_tp=False)
trades_pyr, bal_pyr, eq_pyr = simulate("PYRAMID", target_rr=4.0)

def analyze(trades, final_bal, eq_curve, label):
    df_t = pd.DataFrame(trades)
    total_trades = len(df_t)
    if total_trades == 0:
        return {}
    
    wins = df_t[df_t['dollar_pnl'] > 0]
    losses = df_t[df_t['dollar_pnl'] < 0]
    bes = df_t[df_t['dollar_pnl'] == 0]
    
    win_rate = (len(wins) / total_trades) * 100.0
    gross_win = wins['dollar_pnl'].sum()
    gross_loss = abs(losses['dollar_pnl'].sum())
    pf = (gross_win / gross_loss) if gross_loss > 0 else 999.0
    net_p = final_bal - 100.0
    ret_pct = (net_p / 100.0) * 100.0
    
    eq_s = pd.Series(eq_curve)
    cum_max = eq_s.cummax()
    dd = cum_max - eq_s
    max_dd = dd.max()
    max_dd_pct = (dd / cum_max).max() * 100.0
    
    pyr_count = len(df_t[df_t['is_pyramid'] == True])
    
    return {
        "label": label,
        "trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "bes": len(bes),
        "win_rate": win_rate,
        "pf": pf,
        "net_p": net_p,
        "ret_pct": ret_pct,
        "final_bal": final_bal,
        "max_dd": max_dd,
        "max_dd_pct": max_dd_pct,
        "avg_win": wins['dollar_pnl'].mean() if len(wins) > 0 else 0,
        "avg_loss": abs(losses['dollar_pnl'].mean()) if len(losses) > 0 else 0,
        "pyr_count": pyr_count
    }

s = analyze(trades_std, bal_std, eq_std, "Standard (50% Partial + Opt 2 Trailing)")
sf = analyze(trades_std_full, bal_std_full, eq_std_full, "Standard Full Runner (Opt 2 Trailing)")
p = analyze(trades_pyr, bal_pyr, eq_pyr, "Pro Pyramid (Opt 2 + Opt 3 Pyramiding)")

print("\n" + "="*95)
print("OFFICIAL COMPARATIVE BACKTEST REPORT (10,000 H1 BARS / ~20 MONTHS ON VANTAGE XAUUSD)")
print("="*95)
print(f"{'METRIC':<32} | {'STANDARD (50% Partial)':<20} | {'STANDARD (Full Runner)':<20} | {'PRO PYRAMID (Pro)':<18}")
print("-"*95)
print(f"{'Initial Capital':<32} | {'$100.00':<20} | {'$100.00':<20} | {'$100.00':<18}")
print(f"{'Final Account Balance':<32} | ${s['final_bal']:<19.2f} | ${sf['final_bal']:<19.2f} | ${p['final_bal']:<17.2f}")
print(f"{'Total Net Profit ($)':<32} | +${s['net_p']:<18.2f} | +${sf['net_p']:<18.2f} | +${p['net_p']:<16.2f}")
print(f"{'Net Return (%)':<32} | +{s['ret_pct']:<18.1f}% | +{sf['ret_pct']:<18.1f}% | +{p['ret_pct']:<16.1f}%")
print(f"{'Profit Factor (PF)':<32} | {s['pf']:<20.2f} | {sf['pf']:<20.2f} | {p['pf']:<18.2f}")
print(f"{'Win Rate (%)':<32} | {s['win_rate']:<19.1f}% | {sf['win_rate']:<19.1f}% | {p['win_rate']:<17.1f}%")
print(f"{'Total Closed Trades':<32} | {s['trades']:<20} | {sf['trades']:<20} | {p['trades']:<18}")
print(f"{'Winning Trades':<32} | {s['wins']:<20} | {sf['wins']:<20} | {p['wins']:<18}")
print(f"{'Losing Trades':<32} | {s['losses']:<20} | {sf['losses']:<20} | {p['losses']:<18}")
print(f"{'Pyramid Trades Stacked':<32} | {'0 (Single)':<20} | {'0 (Single)':<20} | {p['pyr_count']:<18}")
print(f"{'Average Winning Trade':<32} | +${s['avg_win']:<18.2f} | +${sf['avg_win']:<18.2f} | +${p['avg_win']:<16.2f}")
print(f"{'Average Losing Trade':<32} | -${s['avg_loss']:<18.2f} | -${sf['avg_loss']:<18.2f} | -${p['avg_loss']:<16.2f}")
print(f"{'Max Drawdown ($)':<32} | -${s['max_dd']:<18.2f} | -${sf['max_dd']:<18.2f} | -${p['max_dd']:<16.2f}")
print(f"{'Max Drawdown (%)':<32} | -{s['max_dd_pct']:<18.1f}% | -{sf['max_dd_pct']:<18.1f}% | -{p['max_dd_pct']:<16.1f}%")
print("="*95)
