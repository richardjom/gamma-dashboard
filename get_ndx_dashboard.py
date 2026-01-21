import yfinance as yf
import pandas as pd
import pyperclip

# --- CONFIGURATION ---
# We use ^NDX (Index) instead of QQQ. It matches NQ pricing almost 1:1.
INDEX_SYMBOL = "^NDX"       
FUTURES_SYMBOL = "NQ=F"  

def get_ndx_dashboard():
    print(f"--- Fetching INSTITUTIONAL DATA for {INDEX_SYMBOL} ---")
    
    # 1. Fetch Prices
    tickers = yf.Tickers(f"{INDEX_SYMBOL} {FUTURES_SYMBOL}")
    
    # Get Data
    try:
        ndx_info = tickers.tickers[INDEX_SYMBOL].info
        fut_info = tickers.tickers[FUTURES_SYMBOL].info
        
        # Prices (Handle potential missing keys)
        ndx_price = ndx_info.get('regularMarketPrice') or ndx_info.get('previousClose')
        fut_price = fut_info.get('regularMarketPrice') or fut_info.get('previousClose')
    except:
        print("Error: Could not fetch price data. Check internet connection.")
        return

    # 2. Calculate Basis (The small difference between Futures and Spot Index)
    # NQ trades slightly higher/lower than NDX due to 'Cost of Carry'
    basis_ratio = fut_price / ndx_price
    print(f"Spot Index: {ndx_price}")
    print(f"Futures:    {fut_price}")
    print(f"Basis Mult: {basis_ratio:.5f} (Adjustment factor)")

    # 3. Fetch Options Chain for NDX
    tk = yf.Ticker(INDEX_SYMBOL)
    try:
        exps = tk.options
        if not exps:
            print("Error: No options data found for ^NDX (Yahoo API issue).")
            return
        nearest_expiry = exps[0] 
        print(f"Expiry Used: {nearest_expiry}")
        
        opt = tk.option_chain(nearest_expiry)
        calls = opt.calls
        puts = opt.puts
    except Exception as e:
        print(f"Options Error: {e}")
        return

    # --- PART A: MASTER WALLS ---
    # Find absolute max Open Interest
    c_wall_row = calls.loc[calls['openInterest'].idxmax()]
    p_wall_row = puts.loc[puts['openInterest'].idxmax()]
    
    raw_cw = c_wall_row['strike']
    raw_pw = p_wall_row['strike']
    raw_piv = (raw_cw + raw_pw) / 2
    
    # --- PART B: EXPECTED MOVE (IV) ---
    try:
        # Get ATM IV
        atm_strike = calls.iloc[(calls['strike'] - ndx_price).abs().argsort()[:1]]
        atm_iv = atm_strike['impliedVolatility'].values[0]
        
        daily_move_pct = atm_iv / 16
        range_pts = ndx_price * daily_move_pct
        
        raw_emh = ndx_price + range_pts
        raw_eml = ndx_price - range_pts
        print(f"Implied Volatility: {atm_iv*100:.2f}%")
    except:
        raw_emh = raw_cw
        raw_eml = raw_pw

    # --- PART C: GRANULAR GRID (Top 3) ---
    top_calls = calls.nlargest(3, 'openInterest')['strike'].values
    top_puts = puts.nlargest(3, 'openInterest')['strike'].values
    top_calls.sort()
    top_puts.sort()
    
    # --- CONVERT TO FUTURES PRICE ---
    # We multiply by the basis ratio to adjust Index levels to Futures levels
    to_fut = lambda x: round(x * basis_ratio, 2)
    
    # Master
    nq_cw = to_fut(raw_cw)
    nq_pw = to_fut(raw_pw)
    nq_piv = to_fut(raw_piv)
    nq_emh = to_fut(raw_emh)
    nq_eml = to_fut(raw_eml)
    
    # Grid
    g_c1 = to_fut(top_calls[0])
    g_c2 = to_fut(top_calls[1])
    g_c3 = to_fut(top_calls[2])
    
    g_p1 = to_fut(top_puts[0])
    g_p2 = to_fut(top_puts[1])
    g_p3 = to_fut(top_puts[2])

    # --- OUTPUT ---
    pine_string = f"{nq_cw},{nq_pw},{nq_piv},{nq_emh},{nq_eml},{g_c1},{g_c2},{g_c3},{g_p1},{g_p2},{g_p3}"
    pyperclip.copy(pine_string)
    
    print("\n" + "="*50)
    print(f"COPIED NDX DATA: {pine_string}")
    print("="*50)
    print(f"NDX Call Wall: {raw_cw} -> NQ: {nq_cw}")
    print(f"NDX Put Wall:  {raw_pw} -> NQ: {nq_pw}")
    print("="*50)

if __name__ == "__main__":
    get_ndx_dashboard()