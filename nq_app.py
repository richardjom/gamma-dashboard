import streamlit as st
import finnhub
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

st.set_page_config(page_title="NQ Precision Map", layout="wide")

# Title
st.title("📊 NQ Complete Precision Map")
st.markdown("Real-time GEX analysis for NQ futures using QQQ options")

# Sidebar inputs
st.sidebar.header("⚙️ Configuration")
finnhub_key = st.sidebar.text_input("Finnhub API Key", value="csie7q9r01qt46e7sjm0csie7q9r01qt46e7sjmg", type="password")

if st.sidebar.button("🔄 Run Analysis", type="primary"):
    
    with st.spinner("Fetching data..."):
        
        # 1. Price Anchor
        client = finnhub.Client(api_key=finnhub_key)
        try:
            quote = client.quote("QQQ")
            qqq_price = quote.get('c', 0)
            if qqq_price == 0:
                st.error("Could not fetch QQQ price")
                st.stop()
        except Exception as e:
            st.error(f"Error fetching QQQ price: {e}")
            st.stop()
        
        # AUTO-FETCH NQ FUTURES PRICE
        try:
            nq_ticker = yf.Ticker("NQ=F")
            nq_data = nq_ticker.history(period="1d")
            if not nq_data.empty:
                nq_now = nq_data['Close'].iloc[-1]
                st.sidebar.success(f"✅ NQ auto-fetched: {nq_now:.2f}")
            else:
                st.sidebar.warning("⚠️ NQ data empty, using fallback")
                nq_now = 24780
        except Exception as e:
            st.sidebar.warning(f"⚠️ NQ fetch failed, using fallback")
            nq_now = 24780
        
        ratio = nq_now / qqq_price
        
        # Display Live Prices
        col1, col2, col3 = st.columns(3)
        col1.metric("NQ Price", f"{nq_now:.2f}")
        col2.metric("QQQ Price", f"${qqq_price:.2f}")
        col3.metric("Ratio", f"{ratio:.4f}")
        
        # 2. Options Data
        qqq = yf.Ticker("QQQ")
        today = datetime.now().strftime('%Y-%m-%d')
        available_expirations = qqq.options
        
        target_expiration = None
        expiration_label = ""
        
        if today in available_expirations:
            target_expiration = today
            expiration_label = "0DTE (Today)"
        else:
            today_dt = datetime.now()
            future_expirations = []
            
            for exp in available_expirations:
                exp_dt = datetime.strptime(exp, '%Y-%m-%d')
                if exp_dt >= today_dt:
                    future_expirations.append((exp, exp_dt))
            
            if future_expirations:
                future_expirations.sort(key=lambda x: x[1])
                target_expiration = future_expirations[0][0]
                days_until = (future_expirations[0][1] - today_dt).days
                expiration_label = f"{days_until}DTE ({target_expiration})"
            else:
                st.error("No valid future expirations available")
                st.stop()
        
        st.info(f"📅 Using Expiration: **{expiration_label}**")
        
        opts = qqq.option_chain(target_expiration)
        df = pd.concat([opts.calls.assign(type='call'), opts.puts.assign(type='put')], ignore_index=True)
        
        # Data Cleaning
        df = df[df['volume'].notna() & (df['volume'] > 10)].copy()
        df = df[df['openInterest'].notna() & (df['openInterest'] > 0)].copy()
        df = df[df['impliedVolatility'].notna() & (df['impliedVolatility'] > 0)].copy()
        df = df[(df['strike'] > qqq_price * 0.98) & (df['strike'] < qqq_price * 1.02)].copy()
        
        if len(df) == 0:
            st.error("No valid options data after filtering")
            st.stop()
        
        # 3. Expected Move
        atm_strike = df.iloc[(df['strike'] - qqq_price).abs().argsort()[:1]]['strike'].values[0]
        atm_opts = df[df['strike'] == atm_strike]
        
        atm_call = atm_opts[atm_opts['type'] == 'call']
        atm_put = atm_opts[atm_opts['type'] == 'put']
        
        if len(atm_call) > 0 and len(atm_put) > 0:
            call_mid = (atm_call.iloc[0]['bid'] + atm_call.iloc[0]['ask']) / 2
            put_mid = (atm_put.iloc[0]['bid'] + atm_put.iloc[0]['ask']) / 2
            straddle = call_mid + put_mid
        else:
            straddle = atm_opts['lastPrice'].sum() if len(atm_opts) > 0 else qqq_price * 0.012
        
        nq_em_full = (straddle * 1.25 if straddle > 0 else qqq_price * 0.012) * ratio
        nq_em_050, nq_em_025 = nq_em_full * 0.50, nq_em_full * 0.25
        
        # 4. GEX Logic
        r, q, T = 0.045, 0.007, 1/252
        
        def calc_gamma(S, K, iv):
            if not iv or iv <= 0: return 0
            try:
                d1 = (np.log(S/K) + (r - q + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
                return np.exp(-q*T) * norm.pdf(d1) / (S * iv * np.sqrt(T))
            except:
                return 0
        
        df['gamma'] = df.apply(lambda x: calc_gamma(qqq_price, x['strike'], x['impliedVolatility']), axis=1)
        df['GEX'] = df.apply(lambda x: x['openInterest'] * x['gamma'] * (qqq_price**2) * 0.01 * (1 if x['type'] == 'call' else -1), axis=1)
        
        # 5. Extract Levels
        calls = df[df['type'] == 'call'].sort_values('GEX', ascending=False)
        puts = df[df['type'] == 'put'].sort_values('GEX')
        
        # Display GEX Tables
        st.subheader("🔍 GEX Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🔴 Top Call Strikes (Resistance)")
            st.dataframe(
                calls[['strike', 'GEX', 'openInterest', 'volume']].head(5).style.format({
                    'strike': '${:.2f}',
                    'GEX': '{:,.0f}',
                    'openInterest': '{:,.0f}',
                    'volume': '{:,.0f}'
                }),
                use_container_width=True
            )
        
        with col2:
            st.markdown("#### 🟢 Top Put Strikes (Support)")
            st.dataframe(
                puts[['strike', 'GEX', 'openInterest', 'volume']].head(5).style.format({
                    'strike': '${:.2f}',
                    'GEX': '{:,.0f}',
                    'openInterest': '{:,.0f}',
                    'volume': '{:,.0f}'
                }),
                use_container_width=True
            )
        
        if len(calls) == 0 or len(puts) == 0:
            st.error("Insufficient call/put data")
            st.stop()
        
        # Extract strikes
        p_wall_strike = calls.iloc[0]['strike']
        p_floor_strike = puts.iloc[0]['strike']
        
        if p_floor_strike == p_wall_strike and len(puts) > 1:
            p_floor_strike = puts.iloc[1]['strike']
        
        s_wall_strike = p_wall_strike + 2
        for i in range(1, len(calls)):
            if calls.iloc[i]['strike'] != p_wall_strike:
                s_wall_strike = calls.iloc[i]['strike']
                break
        
        s_floor_strike = p_floor_strike - 2
        for i in range(1, len(puts)):
            candidate = puts.iloc[i]['strike']
            if candidate != p_floor_strike and candidate != p_wall_strike and candidate != s_wall_strike:
                s_floor_strike = candidate
                break
        
        g_flip_strike = df.groupby('strike')['GEX'].sum().abs().idxmin()
        
        # 6. Results
        results = [
            ("Target Res", (p_wall_strike * ratio) + 35, 3.0, "🎯"),
            ("Primary Wall", p_wall_strike * ratio, 5.0, "🔴"),
            ("Primary Floor", p_floor_strike * ratio, 5.0, "🟢"),
            ("Target Supp", (p_floor_strike * ratio) - 35, 3.0, "🎯"),
            ("Secondary Wall", s_wall_strike * ratio, 3.0, "🟠"),
            ("Secondary Flr", s_floor_strike * ratio, 3.0, "🟡"),
            ("Gamma Flip", g_flip_strike * ratio, 10.0, "⚡"),
            ("Upper 0.50 Dev", nq_now + nq_em_050, 5.0, "📊"),
            ("Upper 0.25 Dev", nq_now + nq_em_025, 3.0, "📊"),
            ("Lower 0.25 Dev", nq_now - nq_em_025, 3.0, "📊"),
            ("Lower 0.50 Dev", nq_now - nq_em_050, 5.0, "📊")
        ]
        
        st.subheader("🎯 NQ Precision Levels")
        
        # Create results dataframe
        results_df = pd.DataFrame(results, columns=['Level', 'Price', 'Width', 'Icon'])
        results_df['Price'] = results_df['Price'].round(2)
        
        # Display as styled table
        st.dataframe(
            results_df.style.format({'Price': '{:.2f}', 'Width': '{:.1f}'}),
            use_container_width=True,
            height=450
        )
        
        # Summary metrics
        st.subheader("📈 Summary")
        col1, col2 = st.columns(2)
        col1.metric("Straddle Premium", f"${straddle:.2f}")
        col2.metric("NQ Expected Move", f"{nq_em_full:.2f} pts")

else:
    st.info("👈 Click 'Run Analysis' in the sidebar to start")