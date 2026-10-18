import yfinance as yf
import pandas as pd
import numpy as np

def generate_daily_month_breakdown():
    # Download 1h and 15m data for Bank Nifty and Nifty
    df_bn = yf.download('^NSEBANK', period='60d', interval='15m', progress=False)
    if isinstance(df_bn.columns, pd.MultiIndex):
        df_bn.columns = df_bn.columns.get_level_values(0)
    df_bn = df_bn.dropna()
    
    # Let's filter the most recent complete month: September 15 to October 16, 2026 (or September 1 to September 30)
    # Let's look at df_bn date range
    print(f"Bank Nifty 15m range: {df_bn.index[0]} to {df_bn.index[-1]}")
    
    # Let's run backtest on Bank Nifty 15m (1 lot = 15 qty)
    # min_disp = 150.0, sl_buffer = 30.0, tp1 = 1.5R, tp2 = 2.5R
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
    fee = 60.0
    
    trades = []
    active_obs = []
    
    for i in range(pivot_span * 2, n):
        curr_time = times[i]
        curr_high = highs[i]
        curr_low = lows[i]
        
        for ob in active_obs:
            if not ob['active']:
                continue
            if ob['in_trade']:
                if ob['type'] == 'BEARISH':
                    if curr_high >= ob['current_sl']:
                        exit_price = ob['current_sl']
                        pnl_pts = ob['entry_price'] - exit_price
                        ob['active'] = False
                        trades.append({
                            'date': curr_time.date(),
                            'time': curr_time,
                            'type': 'SELL',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'BE_STOP' if ob['be_locked'] else 'LOSS'
                        })
                        continue
                    if not ob['be_locked'] and curr_low <= ob['tp1']:
                        ob['be_locked'] = True
                        ob['current_sl'] = ob['entry_price']
                    if curr_low <= ob['tp2']:
                        exit_price = ob['tp2']
                        pnl_pts = ob['entry_price'] - exit_price
                        ob['active'] = False
                        trades.append({
                            'date': curr_time.date(),
                            'time': curr_time,
                            'type': 'SELL',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'WIN'
                        })
                        continue
                elif ob['type'] == 'BULLISH':
                    if curr_low <= ob['current_sl']:
                        exit_price = ob['current_sl']
                        pnl_pts = exit_price - ob['entry_price']
                        ob['active'] = False
                        trades.append({
                            'date': curr_time.date(),
                            'time': curr_time,
                            'type': 'BUY',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'BE_STOP' if ob['be_locked'] else 'LOSS'
                        })
                        continue
                    if not ob['be_locked'] and curr_high >= ob['tp1']:
                        ob['be_locked'] = True
                        ob['current_sl'] = ob['entry_price']
                    if curr_high >= ob['tp2']:
                        exit_price = ob['tp2']
                        pnl_pts = exit_price - ob['entry_price']
                        ob['active'] = False
                        trades.append({
                            'date': curr_time.date(),
                            'time': curr_time,
                            'type': 'BUY',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'WIN'
                        })
                        continue
            else:
                if ob['type'] == 'BEARISH':
                    if curr_high >= ob['sl_price']:
                        ob['active'] = False
                    elif curr_high >= ob['entry_price']:
                        ob['in_trade'] = True
                elif ob['type'] == 'BULLISH':
                    if curr_low <= ob['sl_price']:
                        ob['active'] = False
                    elif curr_low <= ob['entry_price']:
                        ob['in_trade'] = True
                        
        p_idx = i - pivot_span
        p_high = highs[p_idx]
        p_low = lows[p_idx]
        
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
                if risk > 0:
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
                if risk > 0:
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
    tdf['fut_pnl'] = (tdf['pnl_pts'] * lot_size) - 80.0
    # Deep ITM Option simulation: delta 0.85
    tdf['opt_pts'] = np.where(tdf['pnl_pts'] > 0, tdf['pnl_pts'] * 0.85 - 3.0, tdf['pnl_pts'] * 0.78 - 3.0)
    tdf['opt_pnl'] = (tdf['opt_pts'] * lot_size) - 50.0
    
    # Filter last 1 month (September 15, 2026 to October 16, 2026)
    month_df = tdf[tdf['date'] >= pd.to_datetime('2026-09-15').date()]
    print("\nTotal trades in last 1 month:", len(month_df))
    
    # Group by trading day
    daily_grouped = month_df.groupby('date').agg({
        'type': lambda x: '/'.join(x),
        'pnl_pts': 'sum',
        'fut_pnl': 'sum',
        'opt_pnl': 'sum',
        'result': lambda x: ', '.join(x)
    }).reset_index()
    
    print("\nDAY BY DAY BREAKDOWN (SEPTEMBER 15 TO OCTOBER 16, 2026):")
    daily_grouped['cum_fut'] = daily_grouped['fut_pnl'].cumsum()
    daily_grouped['cum_opt'] = daily_grouped['opt_pnl'].cumsum()
    
    for idx, row in daily_grouped.iterrows():
        print(f"Date: {row['date']} | Trades: {row['type']} ({row['result']}) | Pts: {row['pnl_pts']:+6.1f} | Futures: Rs.{row['fut_pnl']:+8.2f} (Cum: Rs.{row['cum_fut']:+9.2f}) | Deep ITM: Rs.{row['opt_pnl']:+8.2f} (Cum: Rs.{row['cum_opt']:+9.2f})")

if __name__ == '__main__':
    generate_daily_month_breakdown()
