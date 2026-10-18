import yfinance as yf
import pandas as pd
import numpy as np

def run_nifty_backtest(timeframe='15m', min_disp=65.0, sl_buffer=12.0, pivot_span=8, tp1_rr=1.5, tp2_rr=2.5, tp3_rr=4.0):
    print(f"\n=======================================================")
    print(f"RUNNING NIFTY 50 BACKTEST [{timeframe.upper()}] (1 LOT = 25 UNITS)")
    print(f"Parameters: Pivot={pivot_span}, MinDisp={min_disp} pts, SL Buffer={sl_buffer} pts, TP1={tp1_rr}R, TP2={tp2_rr}R")
    print(f"=======================================================\n")
    
    # Download data
    if timeframe == '15m':
        df = yf.download('^NSEI', period='60d', interval='15m', progress=False)
    else:
        df = yf.download('^NSEI', period='730d', interval='1h', progress=False)
        # Filter last ~90 days
        df = df[df.index >= '2026-07-15']
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.dropna()
    print(f"Data range: {df.index[0]} to {df.index[-1]} | Total bars: {len(df)}")
    
    highs = df['High'].values
    lows = df['Low'].values
    opens = df['Open'].values
    closes = df['Close'].values
    times = df.index
    n = len(df)
    
    trades = []
    active_obs = [] # list of dicts
    
    # Iterate through bars
    for i in range(pivot_span * 2, n):
        curr_time = times[i]
        curr_high = highs[i]
        curr_low = lows[i]
        curr_open = opens[i]
        curr_close = closes[i]
        
        # 1. Manage existing active trades
        for ob in active_obs:
            if not ob['active']:
                continue
                
            # If trade is in progress
            if ob['in_trade']:
                if ob['type'] == 'BEARISH':
                    # Check SL
                    if curr_high >= ob['current_sl']:
                        exit_price = ob['current_sl']
                        pnl_pts = ob['entry_price'] - exit_price
                        ob['active'] = False
                        ob['in_trade'] = False
                        trades.append({
                            'time': curr_time,
                            'type': 'SELL',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'BE_STOP' if ob['be_locked'] else 'LOSS',
                            'r_mult': pnl_pts / ob['risk_dist']
                        })
                        continue
                    
                    # Check TP1 (1.5R) -> Move SL to Break-Even
                    if not ob['be_locked'] and curr_low <= ob['tp1_price']:
                        ob['be_locked'] = True
                        ob['current_sl'] = ob['entry_price'] # SL to Break-Even
                        
                    # Check TP2 (2.5R) -> Full exit
                    if curr_low <= ob['tp2_price']:
                        exit_price = ob['tp2_price']
                        pnl_pts = ob['entry_price'] - exit_price
                        ob['active'] = False
                        ob['in_trade'] = False
                        trades.append({
                            'time': curr_time,
                            'type': 'SELL',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'WIN',
                            'r_mult': pnl_pts / ob['risk_dist']
                        })
                        continue
                        
                elif ob['type'] == 'BULLISH':
                    # Check SL
                    if curr_low <= ob['current_sl']:
                        exit_price = ob['current_sl']
                        pnl_pts = exit_price - ob['entry_price']
                        ob['active'] = False
                        ob['in_trade'] = False
                        trades.append({
                            'time': curr_time,
                            'type': 'BUY',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'BE_STOP' if ob['be_locked'] else 'LOSS',
                            'r_mult': pnl_pts / ob['risk_dist']
                        })
                        continue
                        
                    # Check TP1 (1.5R) -> Move SL to Break-Even
                    if not ob['be_locked'] and curr_high >= ob['tp1_price']:
                        ob['be_locked'] = True
                        ob['current_sl'] = ob['entry_price']
                        
                    # Check TP2 (2.5R) -> Full exit
                    if curr_high >= ob['tp2_price']:
                        exit_price = ob['tp2_price']
                        pnl_pts = exit_price - ob['entry_price']
                        ob['active'] = False
                        ob['in_trade'] = False
                        trades.append({
                            'time': curr_time,
                            'type': 'BUY',
                            'entry': ob['entry_price'],
                            'exit': exit_price,
                            'pnl_pts': pnl_pts,
                            'result': 'WIN',
                            'r_mult': pnl_pts / ob['risk_dist']
                        })
                        continue
            else:
                # Waiting for Retest/Entry
                # Invalidation check: Did price breach the SL price before retest?
                if ob['type'] == 'BEARISH':
                    if curr_high >= ob['sl_price']:
                        ob['active'] = False
                        continue
                    # Check entry touch
                    if curr_high >= ob['entry_price']:
                        ob['in_trade'] = True
                elif ob['type'] == 'BULLISH':
                    if curr_low <= ob['sl_price']:
                        ob['active'] = False
                        continue
                    # Check entry touch
                    if curr_low <= ob['entry_price']:
                        ob['in_trade'] = True
                        
        # 2. Check for NEW Pivot Formations (confirmed at bar i, which is pivot_span bars after the swing)
        p_idx = i - pivot_span
        pivot_high = highs[p_idx]
        pivot_low = lows[p_idx]
        
        # Check Swing High
        is_swing_high = True
        for k in range(1, pivot_span + 1):
            if highs[p_idx - k] >= pivot_high or highs[p_idx + k] >= pivot_high:
                is_swing_high = False
                break
                
        if is_swing_high:
            # Check displacement in confirmation leg
            impulse_low = min(lows[p_idx + 1 : i + 1])
            disp = pivot_high - impulse_low
            if disp >= min_disp:
                # Find last bullish candle
                ob_offset = p_idx
                for c in range(p_idx, min(p_idx + 5, n)):
                    if closes[c] > opens[c]:
                        ob_offset = c
                        break
                ob_top = highs[ob_offset]
                ob_bottom = min(opens[ob_offset], closes[ob_offset])
                entry = ob_bottom
                sl = max(pivot_high, ob_top) + sl_buffer
                risk = sl - entry
                if risk > 0:
                    tp1 = entry - (risk * tp1_rr)
                    tp2 = entry - (risk * tp2_rr)
                    active_obs.append({
                        'type': 'BEARISH',
                        'entry_price': entry,
                        'sl_price': sl,
                        'current_sl': sl,
                        'risk_dist': risk,
                        'tp1_price': tp1,
                        'tp2_price': tp2,
                        'be_locked': False,
                        'in_trade': False,
                        'active': True
                    })

        # Check Swing Low
        is_swing_low = True
        for k in range(1, pivot_span + 1):
            if lows[p_idx - k] <= pivot_low or lows[p_idx + k] <= pivot_low:
                is_swing_low = False
                break
                
        if is_swing_low:
            # Check displacement in confirmation leg
            impulse_high = max(highs[p_idx + 1 : i + 1])
            disp = impulse_high - pivot_low
            if disp >= min_disp:
                # Find last bearish candle
                ob_offset = p_idx
                for c in range(p_idx, min(p_idx + 5, n)):
                    if closes[c] < opens[c]:
                        ob_offset = c
                        break
                ob_top = max(opens[ob_offset], closes[ob_offset])
                ob_bottom = lows[ob_offset]
                entry = ob_top
                sl = min(pivot_low, ob_bottom) - sl_buffer
                risk = entry - sl
                if risk > 0:
                    tp1 = entry + (risk * tp1_rr)
                    tp2 = entry + (risk * tp2_rr)
                    active_obs.append({
                        'type': 'BULLISH',
                        'entry_price': entry,
                        'sl_price': sl,
                        'current_sl': sl,
                        'risk_dist': risk,
                        'tp1_price': tp1,
                        'tp2_price': tp2,
                        'be_locked': False,
                        'in_trade': False,
                        'active': True
                    })

    # Summary
    if len(trades) == 0:
        print("No trades triggered.")
        return
        
    tdf = pd.DataFrame(trades)
    lot_size = 25
    tdf['pnl_inr'] = tdf['pnl_pts'] * lot_size
    # Deduct ₹80 per trade for brokerage & STT/taxes
    tdf['net_inr'] = tdf['pnl_inr'] - 80.0
    
    wins = tdf[tdf['pnl_pts'] > 0]
    losses = tdf[tdf['result'] == 'LOSS']
    be_stops = tdf[tdf['result'] == 'BE_STOP']
    
    total_trades = len(tdf)
    win_count = len(wins)
    loss_count = len(losses)
    be_count = len(be_stops)
    win_rate = (win_count / total_trades) * 100
    
    gross_profit = wins['pnl_inr'].sum()
    gross_loss = abs(losses['pnl_inr'].sum())
    net_pnl = tdf['net_inr'].sum()
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
    
    cum_pnl = tdf['net_inr'].cumsum()
    peak = cum_pnl.cummax()
    drawdown = peak - cum_pnl
    max_dd = drawdown.max()
    
    print("\n----------------- PERFORMANCE RESULTS -----------------")
    print(f"Total Trades:        {total_trades}")
    print(f"Wins (Full TP2):     {win_count} ({win_rate:.1f}%)")
    print(f"Break-Even Stops:    {be_count} (hit TP1, then SL moved to BE)")
    print(f"Full Losses:         {loss_count} ({(loss_count/total_trades)*100:.1f}%)")
    print(f"Gross Profit:        Rs. {gross_profit:,.2f}")
    print(f"Gross Loss:          Rs. {gross_loss:,.2f}")
    print(f"Net Profit (1 Lot):  Rs. {net_pnl:,.2f}")
    print(f"Profit Factor (PF):  {profit_factor:.2f}")
    print(f"Max Drawdown (INR):  Rs. {max_dd:,.2f}")
    print(f"Avg Points per Trade: {tdf['pnl_pts'].mean():.1f} pts")
    print(f"Avg PnL per Trade:   Rs. {tdf['net_inr'].mean():,.2f}")
    print("-------------------------------------------------------\n")
    
    print("Recent 10 Trades Sample:")
    print(tdf[['time', 'type', 'entry', 'exit', 'pnl_pts', 'result', 'net_inr']].tail(10).to_string())

if __name__ == '__main__':
    # Run on 15m
    run_nifty_backtest(timeframe='15m', min_disp=65.0, sl_buffer=12.0)
    # Run on 1h
    run_nifty_backtest(timeframe='1h', min_disp=120.0, sl_buffer=15.0)
