st.markdown("**0DTE**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_0dte['strike_delta']['strike'],
                y=data_0dte['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_0dte['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_weekly:
            st.markdown("**Weekly**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_weekly['strike_delta']['strike'],
                y=data_weekly['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_weekly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        if data_monthly:
            st.markdown("**Monthly**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=data_monthly['strike_delta']['strike'],
                y=data_monthly['strike_delta']['cumulative_delta'],
                mode='lines',
                name='Cumulative Delta',
                line=dict(color='#00D9FF', width=3),
                fill='tozeroy'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="white")
            fig.add_vline(x=data_monthly['dn_strike'], line_dash="dot", line_color="#FFD700", annotation_text="DN")
            fig.add_vline(x=qqq_price, line_dash="dash", line_color="#FF4444", annotation_text="Current")
            fig.update_layout(template="plotly_dark", plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', height=400)
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')} | CBOE • {nq_source}")

if st.sidebar.button("🔄 Refresh", width='stretch'):
    st.cache_data.clear()
    st.rerun()
