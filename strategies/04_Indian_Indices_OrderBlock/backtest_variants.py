import yfinance as yf
import pandas as pd
import numpy as np

def run_multi_variant_backtest():
    df = yf.download('^NSEI', period='60d', interval='15m', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    
    # Calculate Daily 50 EMA for trend filter comparison
    daily_df = yf.download('^NSEI', period='300d', interval='1d', progress=False)
    if isinstance(daily_df.columns, pd.MultiIndex):
        daily_df.columns = daily_df.columns.get_level_values(0)
    daily_ema = daily_df['Close'].ewm(span=50, adjust=False).mean()
    daily_trend = {}
    for dt, close_val in daily_df['Close'].items():
        daily_trend[dt.date()] = close_val > daily_ema.loc[dt]
        
    highs = df['High'].values
    lows = df['Low'].values
    opens = df['Open'].values
    closes = df['Close'].values
    times = df.index
    n = len(df)
    
    pivot_span = 8
    min_disp = 65.0
    sl_buffer = 12.0
    lot_size = 25
    fee_per_trade = 80.0
    
    for variant in ['A_EXIT_AT_TP1_1.5R', 'B_MOVE_BE_AT_TP1_EXIT_TP2', 'C_TREND_FILTERED_DAILY_EMA']:
        trades = []
        active_obs = []
        
        for i in range(pivot_span * 2, n):
            curr_time = times[i]
            curr_high = highs[i]
            curr_low = lows[i]
            curr_open = opens[i]
            curr_close = closes[i]
            
            # Trend filter
            d_date = curr_time.date()
            is_bull_trend = daily_trend.get(d_date, True)
            
            # Manage active
            for ob in active_obs:
                if not ob['active']:
                    continue
                if ob['in_trade']:
                    if ob['type'] == 'BEARISH':
                        if curr_high >= ob['current_sl']:
                            exit_p = ob['current_sl']
                            pnl_pts = ob['entry_price'] - exit_p
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': pnl_pts > 0, 'be': ob['be_locked'] and pnl_pts == 0})
                            continue
                            
                        if variant == 'A_EXIT_AT_TP1_1.5R':
                            if curr_low <= ob['tp1_price']:
                                exit_p = ob['tp1_price']
                                pnl_pts = ob['entry_price'] - exit_p
                                ob['active'] = False
                                trades.append({'pnl_pts': pnl_pts, 'win': True, 'be': False})
                                continue
                        else:
                            if not ob['be_locked'] and curr_low <= ob['tp1_price']:
                                ob['be_locked'] = True
                                ob['current_sl'] = ob['entry_price']
                            if curr_low <= ob['tp2_price']:
                                exit_p = ob['tp2_price']
                                pnl_pts = ob['entry_price'] - exit_p
                                ob['active'] = False
                                trades.append({'pnl_pts': pnl_pts, 'win': True, 'be': False})
                                continue
                                
                    elif ob['type'] == 'BULLISH':
                        if curr_low <= ob['current_sl']:
                            exit_p = ob['current_sl']
                            pnl_pts = exit_p - ob['entry_price']
                            ob['active'] = False
                            trades.append({'pnl_pts': pnl_pts, 'win': pnl_pts > 0, 'be': ob['be_locked'] and pnl_pts == 0})
                            continue
                            
                        if variant == 'A_EXIT_AT_TP1_1.5R':
                            if curr_high >= ob['tp1_price']:
                                exit_p = ob['tp1_price']
                                pnl_pts = exit_p - ob['entry_price']
                                ob['active'] = False
                                trades.append({'pnl_pts': pnl_pts, 'win': True, 'be': False})
                                continue
                        else:
                            if not ob['be_locked'] and curr_high >= ob['tp1_price']:
                                ob['be_locked'] = True
                                ob['current_sl'] = ob['entry_price']
                            if curr_high >= ob['tp2_price']:
                                exit_p = ob['tp2_price']
                                pnl_pts = exit_p - ob['entry_price']
                                ob['active'] = False
                                trades.append({'pnl_pts': pnl_pts, 'win': True, 'be': False})
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
                            
            # Check swing
            p_idx = i - pivot_span
            pivot_high = highs[p_idx]
            pivot_low = lows[p_idx]
            
            # Bearish
            is_sh = all(highs[p_idx - k] < pivot_high and highs[p_idx + k] < pivot_high for k in range(1, pivot_span + 1))
            if is_sh:
                if variant != 'C_TREND_FILTERED_DAILY_EMA' or not is_bull_trend:
                    disp = pivot_high - min(lows[p_idx + 1 : i + 1])
                    if disp >= min_disp:
                        ob_offset = p_idx
                        for c in range(p_idx, min(p_idx + 5, n)):
                            if closes[c] > opens[c]:
                                ob_offset = c
                                break
                        entry = min(opens[ob_offset], closes[ob_offset])
                        sl = max(pivot_high, highs[ob_offset]) + sl_buffer
                        risk = sl - entry
                        if risk > 0:
                            active_obs.append({
                                'type': 'BEARISH',
                                'entry_price': entry,
                                'sl_price': sl,
                                'current_sl': sl,
                                'risk_dist': risk,
                                'tp1_price': entry - (risk * 1.5),
                                'tp2_price': entry - (risk * 2.5),
                                'be_locked': False,
                                'in_trade': False,
                                'active': True
                            })
                            
            # Bullish
            is_sl = all(lows[p_idx - k] > pivot_low and lows[p_idx + k] > pivot_low for k in range(1, pivot_span + 1))
            if is_sl:
                if variant != 'C_TREND_FILTERED_DAILY_EMA' or is_bull_trend:
                    disp = max(highs[p_idx + 1 : i + 1]) - pivot_low
                    if disp >= min_disp:
                        ob_offset = p_idx
                        for c in range(p_idx, min(p_idx + 5, n)):
                            if closes[c] < opens[c]:
                                ob_offset = c
                                break
                        entry = max(opens[ob_offset], closes[ob_offset])
                        sl = min(pivot_low, lows[ob_offset]) - sl_buffer
                        risk = entry - sl
                        if risk > 0:
                            active_obs.append({
                                'type': 'BULLISH',
                                'entry_price': entry,
                                'sl_price': sl,
                                'current_sl': sl,
                                'risk_dist': risk,
                                'tp1_price': entry + (risk * 1.5),
                                'tp2_price': entry + (risk * 2.5),
                                'be_locked': False,
                                'in_trade': False,
                                'active': True
                            })
                            
        # Report
        tdf = pd.DataFrame(trades)
        tdf['net_inr'] = (tdf['pnl_pts'] * lot_size) - fee_per_trade
        total_t = len(tdf)
        wins = tdf[tdf['pnl_pts'] > 0]
        losses = tdf[tdf['pnl_pts'] < 0]
        be = tdf[tdf['pnl_pts'] == 0]
        gp = wins['pnl_pts'].sum() * lot_size
        gl = abs(losses['pnl_pts'].sum()) * lot_size
        pf = gp / gl if gl > 0 else 999.0
        net = tdf['net_inr'].sum()
        cum = tdf['net_inr'].cumsum()
        max_dd = (cum.cummax() - cum).max()
        
        print(f"\n>>> VARIANT: {variant}")
        print(f"Total Trades: {total_t} | Win Rate: {len(wins)/total_t*100:.1f}% | BE Trades: {len(be)}")
        print(f"Gross Profit: Rs. {gp:,.2f} | Gross Loss: Rs. {gl:,.2f}")
        print(f"Net Profit (1 Lot): Rs. {net:,.2f} | PF: {pf:.2f} | Max DD: Rs. {max_dd:,.2f}")

if __name__ == '__main__':
    run_multi_variant_backtest()
