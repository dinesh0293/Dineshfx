import yfinance as yf
import pandas as pd
import numpy as np

def run_6month_tp1_comparison():
    print("==========================================================================================")
    print("6-MONTH BACKTEST WITH TP1 (1:1.5 R:R) TARGET (APRIL 15, 2026 TO OCTOBER 16, 2026)")
    print("Capturing 1:1.5 R:R Quick Institutional Retest Expansions")
    print("==========================================================================================\n")
    
    df_nifty = yf.download('^NSEI', period='730d', interval='1h', progress=False)
    df_bn    = yf.download('^NSEBANK', period='730d', interval='1h', progress=False)
    
    if isinstance(df_nifty.columns, pd.MultiIndex):
        df_nifty.columns = df_nifty.columns.get_level_values(0)
    if isinstance(df_bn.columns, pd.MultiIndex):
        df_bn.columns = df_bn.columns.get_level_values(0)
        
    start_date = '2026-04-15'
    df_nifty = df_nifty[df_nifty.index >= start_date].dropna()
    df_bn    = df_bn[df_bn.index >= start_date].dropna()
    
    def test_engine(df, min_disp, sl_buffer, lot_size, instrument_name, is_option=False, delta=0.85, capital=150000, fee=80.0):
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
            curr_high = highs[i]
            curr_low = lows[i]
            
            for ob in active_obs:
                if not ob['active']:
                    continue
                if ob['in_trade']:
                    if ob['type'] == 'BEARISH':
                        if curr_high >= ob['sl_price']:
                            pnl_pts = ob['entry_price'] - ob['sl_price']
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': False})
                            continue
                        # Exit at TP1 (1.5R)
                        if curr_low <= ob['tp1']:
                            pnl_pts = ob['entry_price'] - ob['tp1']
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': True})
                            continue
                    elif ob['type'] == 'BULLISH':
                        if curr_low <= ob['sl_price']:
                            pnl_pts = ob['sl_price'] - ob['entry_price']
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': False})
                            continue
                        # Exit at TP1 (1.5R)
                        if curr_high >= ob['tp1']:
                            pnl_pts = ob['tp1'] - ob['entry_price']
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': True})
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
                            'risk_dist': risk,
                            'tp1': entry - (risk * 1.5),
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
                            'risk_dist': risk,
                            'tp1': entry + (risk * 1.5),
                            'in_trade': False,
                            'active': True
                        })
                        
        tdf = pd.DataFrame(trades)
        if is_option:
            tdf['opt_pnl_pts'] = np.where(tdf['pnl_pts'] > 0, tdf['pnl_pts'] * delta - 3.0, tdf['pnl_pts'] * 0.78 - 3.0)
            tdf['gross_pnl'] = tdf['opt_pnl_pts'] * lot_size
            tdf['net_pnl']   = tdf['gross_pnl'] - fee
        else:
            tdf['gross_pnl'] = tdf['pnl_pts'] * lot_size
            tdf['net_pnl']   = tdf['gross_pnl'] - fee
            
        wins = tdf[tdf['gross_pnl'] > 0]
        losses = tdf[tdf['gross_pnl'] < 0]
        
        total_t = len(tdf)
        w_cnt = len(wins)
        l_cnt = len(losses)
        wr = (w_cnt / total_t) * 100
        
        gp = wins['gross_pnl'].sum()
        gl = abs(losses['gross_pnl'].sum())
        net = tdf['net_pnl'].sum()
        pf = gp / gl if gl > 0 else 999.0
        
        cum = tdf['net_pnl'].cumsum()
        max_dd = (cum.cummax() - cum).max()
        monthly = net / 6.0
        roi_mo = (monthly / capital) * 100
        
        return {
            'instrument': instrument_name,
            'capital': capital,
            'trades': total_t,
            'win_rate': wr,
            'net_profit': net,
            'monthly_avg': monthly,
            'pf': pf,
            'max_dd': max_dd,
            'roi_monthly': roi_mo
        }

    res = []
    res.append(test_engine(df_nifty, min_disp=120.0, sl_buffer=15.0, lot_size=25, 
                           instrument_name='1. Nifty Futures (TP1 1.5R)', is_option=False, capital=140000, fee=80.0))
    res.append(test_engine(df_bn, min_disp=280.0, sl_buffer=35.0, lot_size=15, 
                           instrument_name='2. Bank Nifty Futures (TP1 1.5R)', is_option=False, capital=150000, fee=85.0))
    res.append(test_engine(df_nifty, min_disp=120.0, sl_buffer=15.0, lot_size=25, 
                           instrument_name='3. Deep ITM Nifty Options', is_option=True, delta=0.85, capital=18000, fee=50.0))
    res.append(test_engine(df_bn, min_disp=280.0, sl_buffer=35.0, lot_size=15, 
                           instrument_name='4. Deep ITM BankNifty Options', is_option=True, delta=0.85, capital=25000, fee=50.0))
                           
    print("-------------------------------------------------------------------------------------------------------------------")
    print(f"{'Setup (TP1 = 1:1.5R)':<30} | {'Capital':<10} | {'Trades':<6} | {'Win%':<6} | {'6-Mo Net (Rs)':<14} | {'Monthly Avg':<12} | {'PF':<5} | {'Monthly ROI':<10}")
    print("-------------------------------------------------------------------------------------------------------------------")
    for r in res:
        print(f"{r['instrument']:<30} | Rs.{r['capital']:<7} | {r['trades']:<6} | {r['win_rate']:<5.1f}% | Rs.{r['net_profit']:<11,.2f} | Rs.{r['monthly_avg']:<9,.2f} | {r['pf']:<5.2f} | {r['roi_monthly']:<8.1f}%")
    print("-------------------------------------------------------------------------------------------------------------------")

if __name__ == '__main__':
    run_6month_tp1_comparison()
