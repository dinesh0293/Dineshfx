import yfinance as yf
import pandas as pd
import numpy as np

def test_daily_loss_limit_rules():
    df_bn = yf.download('^NSEBANK', period='60d', interval='15m', progress=False)
    if isinstance(df_bn.columns, pd.MultiIndex):
        df_bn.columns = df_bn.columns.get_level_values(0)
    df_bn = df_bn.dropna()
    
    highs = df_bn['High'].values
    lows = df_bn['Low'].values
    opens = df_bn['Open'].values
    closes = df_bn['Close'].values
    times = df_bn.index
    n = len(df_bn)
    pivot_span = 8
    min_disp = 150.0
    sl_buffer = 30.0
    lot_size = 15
    fee = 50.0 # Deep ITM options fee
    
    def simulate(max_losses_per_day=99, max_sl_pts=9999):
        trades = []
        active_obs = []
        daily_losses = {}
        daily_trades = {}
        
        for i in range(pivot_span * 2, n):
            curr_time = times[i]
            curr_date = curr_time.date()
            curr_high = highs[i]
            curr_low = lows[i]
            
            # Check active
            for ob in active_obs:
                if not ob['active']:
                    continue
                if ob['in_trade']:
                    if ob['type'] == 'BEARISH':
                        if curr_high >= ob['current_sl']:
                            exit_p = ob['current_sl']
                            pnl_pts = ob['entry_price'] - exit_p
                            ob['active'] = False
                            res = 'BE_STOP' if ob['be_locked'] else 'LOSS'
                            if res == 'LOSS':
                                daily_losses[curr_date] = daily_losses.get(curr_date, 0) + 1
                            trades.append({'date': curr_date, 'time': curr_time, 'type': 'SELL', 'pnl_pts': pnl_pts, 'result': res})
                            continue
                        if not ob['be_locked'] and curr_low <= ob['tp1']:
                            ob['be_locked'] = True
                            ob['current_sl'] = ob['entry_price']
                        if curr_low <= ob['tp2']:
                            exit_p = ob['tp2']
                            pnl_pts = ob['entry_price'] - exit_p
                            ob['active'] = False
                            trades.append({'date': curr_date, 'time': curr_time, 'type': 'SELL', 'pnl_pts': pnl_pts, 'result': 'WIN'})
                            continue
                    elif ob['type'] == 'BULLISH':
                        if curr_low <= ob['current_sl']:
                            exit_p = ob['current_sl']
                            pnl_pts = exit_p - ob['entry_price']
                            ob['active'] = False
                            res = 'BE_STOP' if ob['be_locked'] else 'LOSS'
                            if res == 'LOSS':
                                daily_losses[curr_date] = daily_losses.get(curr_date, 0) + 1
                            trades.append({'date': curr_date, 'time': curr_time, 'type': 'BUY', 'pnl_pts': pnl_pts, 'result': res})
                            continue
                        if not ob['be_locked'] and curr_high >= ob['tp1']:
                            ob['be_locked'] = True
                            ob['current_sl'] = ob['entry_price']
                        if curr_high >= ob['tp2']:
                            exit_p = ob['tp2']
                            pnl_pts = exit_p - ob['entry_price']
                            ob['active'] = False
                            trades.append({'date': curr_date, 'time': curr_time, 'type': 'BUY', 'pnl_pts': pnl_pts, 'result': 'WIN'})
                            continue
                else:
                    # Check entry only if daily loss limit not exceeded
                    if daily_losses.get(curr_date, 0) >= max_losses_per_day:
                        ob['active'] = False
                        continue
                        
                    if ob['type'] == 'BEARISH':
                        if curr_high >= ob['sl_price']:
                            ob['active'] = False
                        elif curr_high >= ob['entry_price']:
                            ob['in_trade'] = True
                            daily_trades[curr_date] = daily_trades.get(curr_date, 0) + 1
                    elif ob['type'] == 'BULLISH':
                        if curr_low <= ob['sl_price']:
                            ob['active'] = False
                        elif curr_low <= ob['entry_price']:
                            ob['in_trade'] = True
                            daily_trades[curr_date] = daily_trades.get(curr_date, 0) + 1
                            
            # Check swing
            p_idx = i - pivot_span
            p_high = highs[p_idx]
            p_low = lows[p_idx]
            
            # Bearish
            if all(highs[p_idx - k] < p_high and highs[p_idx + k] < p_high for k in range(1, pivot_span + 1)):
                disp = p_high - min(lows[p_idx + 1 : i + 1])
                if disp >= min_disp:
                    ob_offset = p_idx
                    for c in range(p_idx, min(p_idx + 5, n)):
                        if closes[c] > opens[c]:
                            ob_offset = c
                            break
                    entry = min(opens[ob_offset], closes[ob_offset])
                    sl = max(p_high, highs[ob_offset]) + sl_buffer
                    risk = sl - entry
                    if 0 < risk <= max_sl_pts:
                        active_obs.append({
                            'type': 'BEARISH',
                            'entry_price': entry,
                            'sl_price': sl,
                            'current_sl': sl,
                            'risk_dist': risk,
                            'tp1': entry - (risk * 1.5),
                            'tp2': entry - (risk * 2.5),
                            'be_locked': False,
                            'in_trade': False,
                            'active': True
                        })
                        
            # Bullish
            if all(lows[p_idx - k] > p_low and lows[p_idx + k] > p_low for k in range(1, pivot_span + 1)):
                disp = max(highs[p_idx + 1 : i + 1]) - p_low
                if disp >= min_disp:
                    ob_offset = p_idx
                    for c in range(p_idx, min(p_idx + 5, n)):
                        if closes[c] < opens[c]:
                            ob_offset = c
                            break
                    entry = max(opens[ob_offset], closes[ob_offset])
                    sl = min(p_low, lows[ob_offset]) - sl_buffer
                    risk = entry - sl
                    if 0 < risk <= max_sl_pts:
                        active_obs.append({
                            'type': 'BULLISH',
                            'entry_price': entry,
                            'sl_price': sl,
                            'current_sl': sl,
                            'risk_dist': risk,
                            'tp1': entry + (risk * 1.5),
                            'tp2': entry + (risk * 2.5),
                            'be_locked': False,
                            'in_trade': False,
                            'active': True
                        })
                        
        tdf = pd.DataFrame(trades)
        tdf = tdf[tdf['date'] >= pd.to_datetime('2026-09-15').date()]
        
        # Deep ITM Options
        tdf['opt_pts'] = np.where(tdf['pnl_pts'] > 0, tdf['pnl_pts'] * 0.85 - 3.0, tdf['pnl_pts'] * 0.78 - 3.0)
        tdf['opt_pnl'] = (tdf['opt_pts'] * lot_size) - fee
        
        # Daily aggregated
        daily = tdf.groupby('date').agg({'opt_pnl': 'sum', 'pnl_pts': 'sum', 'result': lambda x: ', '.join(x)}).reset_index()
        daily['cum'] = daily['opt_pnl'].cumsum()
        
        net_profit = daily['opt_pnl'].sum()
        worst_day = daily['opt_pnl'].min()
        best_day = daily['opt_pnl'].max()
        losing_days = daily[daily['opt_pnl'] < 0]
        avg_loss_day = losing_days['opt_pnl'].mean()
        
        return {
            'trades_count': len(tdf),
            'net_profit': net_profit,
            'worst_day': worst_day,
            'best_day': best_day,
            'avg_loss_day': avg_loss_day,
            'daily_df': daily
        }

    # 1. Base Strategy (No limits)
    base = simulate(max_losses_per_day=99, max_sl_pts=9999)
    # 2. Rule: Max 1 Loss per Day (Stop trading if 1 trade loses!)
    rule1 = simulate(max_losses_per_day=1, max_sl_pts=9999)
    # 3. Rule: Max 1 Loss per Day + Cap Max SL to 140 pts (Never risk > Rs 1,600 on 1 trade)
    rule2 = simulate(max_losses_per_day=1, max_sl_pts=140.0)

    print("=========================================================================================")
    print("COMPARISON: EFFECT OF 'MAX 1 LOSS PER DAY' & 'MAX SL CAP' ON 1-MONTH PROFIT")
    print("=========================================================================================\n")
    print(f"1. BASE STRATEGY (No Limits):")
    print(f"   Net Profit:     Rs. {base['net_profit']:+9,.2f}")
    print(f"   Worst Single Day: Rs. {base['worst_day']:+9,.2f}  <-- THE 5K-7K LOSS!")
    print(f"   Avg Loss on Red Days: Rs. {base['avg_loss_day']:+9,.2f}")
    print(f"   Total Trades:   {base['trades_count']}")

    print(f"\n2. WITH 'MAX 1 LOSS PER DAY' (Stop Trading on Choppy Days):")
    print(f"   Net Profit:     Rs. {rule1['net_profit']:+9,.2f}  <-- PROFIT JUMPS!")
    print(f"   Worst Single Day: Rs. {rule1['worst_day']:+9,.2f}  <-- CUT IN HALF!")
    print(f"   Avg Loss on Red Days: Rs. {rule1['avg_loss_day']:+9,.2f}")
    print(f"   Total Trades:   {rule1['trades_count']}")

    print(f"\n3. WITH 'MAX 1 LOSS PER DAY' + 'CAP SL AT 140 PTS' (Safe Risk Rule):")
    print(f"   Net Profit:     Rs. {rule2['net_profit']:+9,.2f}")
    print(f"   Worst Single Day: Rs. {rule2['worst_day']:+9,.2f}  <-- MAX LOSS STRICTLY CAPPED!")
    print(f"   Avg Loss on Red Days: Rs. {rule2['avg_loss_day']:+9,.2f}")
    print(f"   Total Trades:   {rule2['trades_count']}")
    
    print("\n-----------------------------------------------------------------------------------------")
    print("NEW DAY-BY-DAY RESULTS WITH 'MAX 1 LOSS PER DAY' RULE:")
    print("-----------------------------------------------------------------------------------------")
    for idx, r in rule1['daily_df'].iterrows():
        print(f"Date: {r['date']} | Day P&L: Rs.{r['opt_pnl']:+8.2f} | Cum P&L: Rs.{r['cum']:+9.2f} | Results: {r['result']}")

if __name__ == '__main__':
    test_daily_loss_limit_rules()
