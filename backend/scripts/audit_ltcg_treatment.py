import os, sys, pandas as pd, numpy as np

sys.path.insert(0, os.path.abspath('.'))
from backend.scripts.run_trial_9_nifty_trend import RBI_TBILL_YIELDS, load_or_fetch_nifty_tri

df = load_or_fetch_nifty_tri('scratch/nifty_50_tri_2000_2015.csv')
df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
eval_df = df.loc['2007-01-01':'2015-12-31'].copy()
trading_dates = list(eval_df.index)

def test_ltcg_treatment(tax_mode='budget_2024', carry_forward=True, treat_365_as_ltcg=True):
    initial_capital = 500000.0
    brokerage = 20.0
    slippage = 0.05
    stt_sell = 0.00001
    tracking_error = 0.0010
    
    cash = initial_capital
    etf_shares = 0.0
    in_equity = False
    etf_cost = 0.0
    entry_dt = None
    
    fy_stcg = 0.0
    fy_ltcg = 0.0
    accumulated_loss = 0.0
    fy_interest = 0.0
    
    stcg_tax_total = 0.0
    ltcg_tax_total = 0.0
    debt_tax_total = 0.0
    
    current_fy = None
    daily_nav = []
    
    for i in range(len(eval_df)):
        dt = trading_dates[i]
        c_price = float(eval_df.iloc[i]['Close'])
        ema = float(eval_df.iloc[i]['EMA200'])
        year = dt.year
        fy = year if dt.month >= 4 else year - 1
        
        if current_fy is None:
            current_fy = fy
        elif fy != current_fy:
            if tax_mode == 'budget_2024':
                rate_stcg = 0.208
                rate_ltcg = 0.130
                rate_debt = 0.312
            elif tax_mode == 'hist_2007_2015':
                rate_stcg = 0.103 if current_fy <= 2007 else 0.1545
                rate_ltcg = 0.0
                rate_debt = 0.309
            else:
                rate_stcg = 0.0
                rate_ltcg = 0.0
                rate_debt = 0.0
                
            if carry_forward:
                net_stcg = fy_stcg - accumulated_loss
                if net_stcg > 0:
                    stcg_tax = net_stcg * rate_stcg
                    accumulated_loss = 0.0
                else:
                    stcg_tax = 0.0
                    accumulated_loss = -net_stcg
            else:
                stcg_tax = max(0.0, fy_stcg * rate_stcg)
                
            if rate_ltcg > 0:
                taxable_ltcg = max(0.0, fy_ltcg - 125000.0)
                ltcg_tax = taxable_ltcg * rate_ltcg
            else:
                ltcg_tax = 0.0
                
            debt_tax = max(0.0, fy_interest * rate_debt)
            total_tax = stcg_tax + ltcg_tax + debt_tax
            
            stcg_tax_total += stcg_tax
            ltcg_tax_total += ltcg_tax
            debt_tax_total += debt_tax
            
            if in_equity:
                tax_shares = total_tax / c_price if c_price > 0 else 0
                etf_shares = max(0.0, etf_shares - tax_shares)
            else:
                cash = max(0.0, cash - total_tax)
                
            current_fy = fy
            fy_stcg = 0.0
            fy_ltcg = 0.0
            fy_interest = 0.0
            
        if not in_equity:
            tbill = RBI_TBILL_YIELDS.get(year, 0.065)
            d_interest = cash * (tbill / 252.0)
            cash += d_interest
            fy_interest += d_interest
        else:
            etf_shares *= (1.0 - tracking_error / 252.0)
            
        bullish = c_price > ema
        if bullish and not in_equity:
            exec_p = c_price * (1.0 + slippage / 100.0)
            investable = cash - brokerage
            if investable > 0:
                etf_shares = investable / exec_p
                etf_cost = exec_p
                entry_dt = dt
                cash = 0.0
                in_equity = True
        elif not bullish and in_equity:
            exec_p = c_price * (1.0 - slippage / 100.0)
            gross = etf_shares * exec_p
            stt = gross * stt_sell
            net = gross - brokerage - stt
            realized_pnl = net - (etf_shares * etf_cost)
            hold_days = (dt - entry_dt).days if entry_dt else 0
            
            if treat_365_as_ltcg and hold_days > 365:
                fy_ltcg += realized_pnl
            else:
                fy_stcg += realized_pnl
                
            cash = net
            etf_shares = 0.0
            in_equity = False
            
        cur_nav = cash + (etf_shares * c_price if in_equity else 0.0)
        daily_nav.append(cur_nav)
        
    final_price = float(eval_df.iloc[-1]['Close'])
    if in_equity:
        exec_p = final_price * (1.0 - slippage / 100.0)
        gross = etf_shares * exec_p
        stt = gross * stt_sell
        net = gross - brokerage - stt
        realized_pnl = net - (etf_shares * etf_cost)
        hold_days = (eval_df.index[-1] - entry_dt).days if entry_dt else 0
        if treat_365_as_ltcg and hold_days > 365:
            fy_ltcg += realized_pnl
        else:
            fy_stcg += realized_pnl
        cash = net
        etf_shares = 0.0
        in_equity = False
        
    if tax_mode == 'budget_2024':
        rate_stcg = 0.208
        rate_ltcg = 0.130
        rate_debt = 0.312
    elif tax_mode == 'hist_2007_2015':
        rate_stcg = 0.1545
        rate_ltcg = 0.0
        rate_debt = 0.309
    else:
        rate_stcg = 0.0
        rate_ltcg = 0.0
        rate_debt = 0.0
        
    if carry_forward:
        net_stcg = fy_stcg - accumulated_loss
        term_stcg_tax = max(0.0, net_stcg * rate_stcg)
    else:
        term_stcg_tax = max(0.0, fy_stcg * rate_stcg)
        
    if rate_ltcg > 0:
        term_ltcg_tax = max(0.0, max(0.0, fy_ltcg - 125000.0) * rate_ltcg)
    else:
        term_ltcg_tax = 0.0
        
    term_debt_tax = max(0.0, fy_interest * rate_debt)
    terminal_tax = term_stcg_tax + term_ltcg_tax + term_debt_tax
    cash -= terminal_tax
    stcg_tax_total += term_stcg_tax
    ltcg_tax_total += term_ltcg_tax
    debt_tax_total += term_debt_tax
    
    n_years = len(eval_df) / 252.0
    cagr = (((cash / initial_capital) ** (1.0 / n_years)) - 1.0) * 100.0
    s_nav = pd.Series(daily_nav)
    dd = (s_nav - s_nav.cummax()) / s_nav.cummax() * 100.0
    max_dd = abs(float(dd.min()))
    calmar = cagr / max_dd
    
    cum_total_tax = stcg_tax_total + ltcg_tax_total + debt_tax_total
    
    return {
        'tax_mode': tax_mode,
        'cf': carry_forward,
        'ltcg_flag': treat_365_as_ltcg,
        'final_nav': cash,
        'cagr': cagr,
        'max_dd': max_dd,
        'calmar': calmar,
        'stcg_tax': stcg_tax_total,
        'ltcg_tax': ltcg_tax_total,
        'debt_tax': debt_tax_total,
        'total_tax': cum_total_tax
    }

print("=== COMPARATIVE LTCG TREATMENT AUDIT ===")
runs = [
    ('budget_2024', False, False),
    ('budget_2024', False, True),
    ('budget_2024', True, False),
    ('budget_2024', True, True),
    ('hist_2007_2015', False, False),
    ('hist_2007_2015', False, True),
    ('hist_2007_2015', True, False),
    ('hist_2007_2015', True, True),
]
for mode, cf, ltcg in runs:
    res = test_ltcg_treatment(mode, cf, ltcg)
    print(f"Mode: {res['tax_mode']:15} | CF: {str(res['cf']):5} | LTCG: {str(res['ltcg_flag']):5} | NAV: Rs {res['final_nav']:,.0f} | CAGR: {res['cagr']:.2f}% | MaxDD: {res['max_dd']:.2f}% | Calmar: {res['calmar']:.2f} | STCG: Rs {res['stcg_tax']:,.0f} | LTCG: Rs {res['ltcg_tax']:,.0f} | Debt: Rs {res['debt_tax']:,.0f} | Total: Rs {res['total_tax']:,.0f}")
