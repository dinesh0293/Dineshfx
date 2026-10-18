import yfinance as yf
import pandas as pd
import numpy as np

def run_6month_comparison():
    print("================================================================================")
    print("6-MONTH REALISTIC BACKTEST COMPARISON (APRIL 15, 2026 TO OCTOBER 16, 2026)")
    print("Strategy: Institutional Order Block (Pivot=8, Retest Entry, TP1=1.5R, TP2=2.5R)")
    print("================================================================================\n")
    
    # 1. Download 6-month hourly data for both indices
    df_nifty = yf.download('^NSEI', period='730d', interval='1h', progress=False)
    df_bn    = yf.download('^NSEBANK', period='730d', interval='1h', progress=False)
    
    if isinstance(df_nifty.columns, pd.MultiIndex):
        df_nifty.columns = df_nifty.columns.get_level_values(0)
    if isinstance(df_bn.columns, pd.MultiIndex):
        df_bn.columns = df_bn.columns.get_level_values(0)
        
    start_date = '2026-04-15'
    df_nifty = df_nifty[df_nifty.index >= start_date].dropna()
    df_bn    = df_bn[df_bn.index >= start_date].dropna()
    
    print(f"Data Loaded: {df_nifty.index[0].strftime('%Y-%m-%d')} to {df_nifty.index[-1].strftime('%Y-%m-%d')}")
    print(f"Nifty 1h Bars: {len(df_nifty)} | Bank Nifty 1h Bars: {len(df_bn)}\n")
    
    def backtest_engine(df, min_disp, sl_buffer, lot_size, instrument_name, is_option=False, delta=0.85, capital_required=150000, fee=80.0):
        highs = df['High'].values
        lows = df['Low'].values
        opens = df['Open'].values
        closes = df['Close'].values
        times = df.index
        n = len(df)
        pivot_span = 8
        
        trades = []
        active_obs = []
        
        for i in range(pivot_span * 2, n):
            curr_time = times[i]
            curr_high = highs[i]
            curr_low = lows[i]
            
            # Manage active trades
            for ob in active_obs:
                if not ob['active']:
                    continue
                if ob['in_trade']:
                    if ob['type'] == 'BEARISH':
                        # Stop Loss hit
                        if curr_high >= ob['current_sl']:
                            exit_price = ob['current_sl']
                            pnl_pts = ob['entry_price'] - exit_price
                            ob['active'] = False
                            trades.append({
                                'time': curr_time,
                                'type': 'SELL',
                                'pnl_pts': pnl_pts,
                                'result': 'BE_STOP' if ob['be_locked'] else 'LOSS'
                            })
                            continue
                        # Target 1 (1.5R) -> Move SL to BE
                        if not ob['be_locked'] and curr_low <= ob['tp1']:
                            ob['be_locked'] = True
                            ob['current_sl'] = ob['entry_price']
                        # Target 2 (2.5R) -> Full Exit
                        if curr_low <= ob['tp2']:
                            exit_price = ob['tp2']
                            pnl_pts = ob['entry_price'] - exit_price
                            ob['active'] = False
                            trades.append({
                                'time': curr_time,
                                'type': 'SELL',
                                'pnl_pts': pnl_pts,
                                'result': 'WIN'
                            })
                            continue
                            
                    elif ob['type'] == 'BULLISH':
                        # Stop Loss hit
                        if curr_low <= ob['current_sl']:
                            exit_price = ob['current_sl']
                            pnl_pts = exit_price - ob['entry_price']
                            ob['active'] = False
                            trades.append({
                                'time': curr_time,
                                'type': 'BUY',
                                'pnl_pts': pnl_pts,
                                'result': 'BE_STOP' if ob['be_locked'] else 'LOSS'
                            })
                            continue
                        # Target 1 (1.5R) -> Move SL to BE
                        if not ob['be_locked'] and curr_high >= ob['tp1']:
                            ob['be_locked'] = True
                            ob['current_sl'] = ob['entry_price']
                        # Target 2 (2.5R) -> Full Exit
                        if curr_high >= ob['tp2']:
                            exit_price = ob['tp2']
                            pnl_pts = exit_price - ob['entry_price']
                            ob['active'] = False
                            trades.append({
                                'time': curr_time,
                                'type': 'BUY',
                                'pnl_pts': pnl_pts,
                                'result': 'WIN'
                            })
                            continue
                else:
                    # Waiting for Retest
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
                            
            # Pivot Detection
            p_idx = i - pivot_span
            p_high = highs[p_idx]
            p_low = lows[p_idx]
            
            # Bearish Swing High
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
                        
            # Bullish Swing Low
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
                        
        if len(trades) == 0:
            return None
            
        tdf = pd.DataFrame(trades)
        
        # P&L Calculation:
        # If Option: point gain/loss is scaled by delta (0.85) minus ~5 pts theta decay
        if is_option:
            # When in profit, delta is ~0.85 to 0.90; when in loss, delta contracts to ~0.75-0.80
            tdf['opt_pnl_pts'] = np.where(tdf['pnl_pts'] > 0, tdf['pnl_pts'] * delta - 4.0, tdf['pnl_pts'] * 0.78 - 4.0)
            tdf['gross_pnl'] = tdf['opt_pnl_pts'] * lot_size
            tdf['net_pnl']   = tdf['gross_pnl'] - fee
        else:
            tdf['gross_pnl'] = tdf['pnl_pts'] * lot_size
            tdf['net_pnl']   = tdf['gross_pnl'] - fee
            
        wins = tdf[tdf['gross_pnl'] > 0]
        losses = tdf[tdf['result'] == 'LOSS']
        be_stops = tdf[tdf['result'] == 'BE_STOP']
        
        total_trades = len(tdf)
        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(be_stops)
        win_rate = (win_count / total_trades) * 100
        
        gross_prof = wins['gross_pnl'].sum()
        gross_loss = abs(losses['gross_pnl'].sum())
        net_profit = tdf['net_pnl'].sum()
        profit_factor = gross_prof / gross_loss if gross_loss > 0 else 999.0
        
        cum_pnl = tdf['net_pnl'].cumsum()
        peak = cum_pnl.cummax()
        max_dd = (peak - cum_pnl).max()
        
        # Monthly average
        monthly_avg = net_profit / 6.0
        roi_total = (net_profit / capital_required) * 100
        roi_monthly = (monthly_avg / capital_required) * 100
        
        return {
            'instrument': instrument_name,
            'capital': capital_required,
            'trades': total_trades,
            'wins': win_count,
            'losses': loss_count,
            'be_stops': be_count,
            'win_rate': win_rate,
            'net_profit_6m': net_profit,
            'monthly_avg': monthly_avg,
            'pf': profit_factor,
            'max_dd': max_dd,
            'roi_total': roi_total,
            'roi_monthly': roi_monthly
        }
        
    # Run the 4 setups over the same 6 months
    results = []
    
    # 1. NIFTY FUTURES (1 lot = 25 qty)
    r1 = backtest_engine(df_nifty, min_disp=120.0, sl_buffer=15.0, lot_size=25, 
                         instrument_name='1. Nifty 50 Futures', is_option=False, capital_required=140000, fee=80.0)
    results.append(r1)
    
    # 2. BANK NIFTY FUTURES (1 lot = 15 qty)
    r2 = backtest_engine(df_bn, min_disp=280.0, sl_buffer=35.0, lot_size=15, 
                         instrument_name='2. Bank Nifty Futures', is_option=False, capital_required=150000, fee=85.0)
    results.append(r2)
    
    # 3. DEEP ITM OPTIONS ON NIFTY (1 lot = 25 qty, Capital ~Rs 18k)
    r3 = backtest_engine(df_nifty, min_disp=120.0, sl_buffer=15.0, lot_size=25, 
                         instrument_name='3. Deep ITM Nifty Options', is_option=True, delta=0.85, capital_required=18000, fee=50.0)
    results.append(r3)
    
    # 4. DEEP ITM OPTIONS ON BANK NIFTY (1 lot = 15 qty, Capital ~Rs 25k)
    r4 = backtest_engine(df_bn, min_disp=280.0, sl_buffer=35.0, lot_size=15, 
                         instrument_name='4. Deep ITM BankNifty Options', is_option=True, delta=0.85, capital_required=25000, fee=50.0)
    results.append(r4)
    
    rdf = pd.DataFrame(results)
    
    print("-------------------------------------------------------------------------------------------------------------------")
    print(f"{'Instrument / Setup':<28} | {'Capital':<10} | {'Trades':<6} | {'Win%':<6} | {'6-Mo Net (Rs)':<14} | {'Monthly Avg':<12} | {'PF':<5} | {'Monthly ROI':<10}")
    print("-------------------------------------------------------------------------------------------------------------------")
    for r in results:
        print(f"{r['instrument']:<28} | Rs.{r['capital']:<7} | {r['trades']:<6} | {r['win_rate']:<5.1f}% | Rs.{r['net_profit_6m']:<11,.2f} | Rs.{r['monthly_avg']:<9,.2f} | {r['pf']:<5.2f} | {r['roi_monthly']:<8.1f}%")
    print("-------------------------------------------------------------------------------------------------------------------")

if __name__ == '__main__':
    run_6month_comparison()
