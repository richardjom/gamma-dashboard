import yfinance as yf
import pandas as pd
import pyperclip

# --- CONFIGURATION ---
ETF_SYMBOL = "QQQ"       
FUTURES_SYMBOL = "NQ=F"  

def get_full_dashboard():
    print(f"--- Fetching FULL DATA for {ETF_SYMBOL} & {FUTURES_SYMBOL} ---")
    
    # 1. Fetch Prices & Ratio
    tickers = yf.Tickers(f"{ETF_SYMBOL} {FUTURES_SYMBOL}")
    
    # We fetch the most recent data available
    etf_info = tickers.tickers[ETF_SYMBOL].info
    fut_info = tickers.tickers[FUTURES_SYMBOL].info
    
    # Logic to get the live price (regular or pre-market)
    etf_price = etf_info.get('regularMarketPrice') or etf_info.get('previousClose')
    fut_price = fut_info.get('regularMarketPrice') or fut_info.get('previousClose')
    
    if not etf_price or not fut_price:
        print("Error: Could not fetch prices.")
        return

    ratio = fut_price / etf_price
    print(f"Current Ratio: {ratio:.4f}")
    print(f"Live NQ Price: {fut_price}")

    # 2. Fetch Options Chain
    tk = yf.Ticker(ETF_SYMBOL)
    exps = tk.options
    nearest_expiry = exps[0] # usually 0DTE or 1DTE
    print(f"Expiry Used: {nearest_expiry}")
    
    opt = tk.option_chain(nearest_expiry)
    calls = opt.calls
    puts = opt.puts

    # --- PART A: MASTER WALLS (Highest OI) ---
    # The absolute biggest levels on the board
    c_wall_row = calls.loc[calls['openInterest'].idxmax()]
    p_wall_row = puts.loc[puts['openInterest'].idxmax()]
    
    qqq_cw = c_wall_row['strike']
    qqq_pw = p_wall_row['strike']
    qqq_piv = (qqq_cw + qqq_pw) / 2
    
    # --- PART B: EXPECTED MOVE (IV) ---
    try:
        # Find strike closest to current price to get ATM IV
        atm_strike = calls.iloc[(calls['strike'] - etf_price).abs().argsort()[:1]]
        atm_iv = atm_strike['impliedVolatility'].values[0]
        
        # Rule of 16 (Standard Day Move)
        daily_move_pct = atm_iv / 16
        qqq_range = etf_price * daily_move_pct
        
        # Calculate Bands based on CURRENT Price
        qqq_emh = etf_price + qqq_range
        qqq_eml = etf_price - qqq_range
        
        print(f"Implied Volatility: {atm_iv*100:.2f}%")
        
    except Exception as e:
        print(f"IV Error: {e}")
        qqq_emh = qqq_cw
        qqq_eml = qqq_pw

    # --- PART C: GRANULAR GRID (Top 3 Clusters) ---
    # We take the top 3 largest open interest strikes for intraday levels
    top_calls = calls.nlargest(3, 'openInterest')['strike'].values
    top_puts = puts.nlargest(3, 'openInterest')['strike'].values
    top_calls.sort()
    top_puts.sort()
    
    # --- CONVERT ALL TO NQ ---
    to_nq = lambda x: round(x * ratio, 2)
    
    # Master
    nq_cw = to_nq(qqq_cw)
    nq_pw = to_nq(qqq_pw)
    nq_piv = to_nq(qqq_piv)
    nq_emh = to_nq(qqq_emh)
    nq_eml = to_nq(qqq_eml)
    
    # Grid (Call 1-3, Put 1-3)
    g_c1 = to_nq(top_calls[0])
    g_c2 = to_nq(top_calls[1])
    g_c3 = to_nq(top_calls[2])
    
    g_p1 = to_nq(top_puts[0])
    g_p2 = to_nq(top_puts[1])
    g_p3 = to_nq(top_puts[2])

    # --- OUTPUT STRING ---
    # Format: "CW,PW,Piv,EMH,EML, C1,C2,C3, P1,P2,P3" (11 items)
    pine_string = f"{nq_cw},{nq_pw},{nq_piv},{nq_emh},{nq_eml},{g_c1},{g_c2},{g_c3},{g_p1},{g_p2},{g_p3}"
    
    pyperclip.copy(pine_string)
    
    print("\n" + "="*50)
    print(f"COPIED TO CLIPBOARD: {pine_string}")
    print("="*50)
    print(f"Master Resist: {nq_cw}")
    print(f"Pivot:         {nq_piv}")
    print(f"Master Support:{nq_pw}")
    print(f"IV High:       {nq_emh}")
    print("="*50)
    print("Paste this string into your TradingView indicator settings.")

if __name__ == "__main__":
    get_full_dashboard()