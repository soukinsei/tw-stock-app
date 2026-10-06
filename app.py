import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 設定網頁標題與排版
st.set_page_config(
    page_title="台股智慧分析與持股管理",
    page_icon="📈",
    layout="wide"
)

def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_kd(data, n=9):
    low_min = data['Low'].rolling(window=n).min()
    high_max = data['High'].rolling(window=n).max()
    rsv = (data['Close'] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    
    k_list = [50]
    d_list = [50]
    
    for i in range(1, len(rsv)):
        k = (2/3) * k_list[-1] + (1/3) * rsv.iloc[i]
        d = (2/3) * d_list[-1] + (1/3) * k
        k_list.append(k)
        d_list.append(d)
        
    data['K'] = k_list
    data['D'] = d_list
    return data

@st.cache_data(ttl=3600)
def load_stock_data(stock_id):
    # 嘗試上市代號
    ticker_symbol = f"{stock_id}.TW"
    stock = yf.Ticker(ticker_symbol)
    df = stock.history(period="1y")
    
    if df.empty:
        # 嘗試上櫃代號
        ticker_symbol = f"{stock_id}.O"
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="1y")
        
    if df.empty:
        return None, None
        
    return df, ticker_symbol

# 網頁側邊欄（輸入區）
st.sidebar.header("📊 輸入設定")
input_stock_id = st.sidebar.text_input("股票代號 (例如 2330)", value="2330").strip()
input_buy_price = st.sidebar.number_input("您的成交價 (TWD)", min_value=0.0, value=600.0, step=0.5)
input_shares = st.sidebar.number_input("持股股數", min_value=0, value=1000, step=100)

analyze_btn = st.sidebar.button("開始分析", type="primary")

# 主頁面
st.title("📈 台股智慧分析與持股管理系統")
st.markdown("透過手機網頁隨時掌握持股損益、技術指標（KD、RSI）與多空訊號！")

if analyze_btn or input_stock_id:
    with st.spinner(f"正在載入 {input_stock_id} 的最新資料..."):
        df, ticker_symbol = load_stock_data(input_stock_id)
        
    if df is None or df.empty:
        st.error(f"找不到代號「{input_stock_id}」的台股資料，請確認代號是否正確。")
    else:
        # 1. 盈虧計算
        latest_price = df['Close'].iloc[-1]
        total_cost = input_buy_price * input_shares
        total_value = latest_price * input_shares
        profit_loss = total_value - total_cost
        profit_loss_pct = (profit_loss / total_cost) * 100 if total_cost > 0 else 0

        st.subheader("📋 持股盈虧狀態報告")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("最新成交價", f"{latest_price:.2f} TWD")
        col2.metric("持股市值", f"{total_value:,.2f} TWD")
        col3.metric("損益金額", f"{profit_loss:+,.2f} TWD", delta=f"{profit_loss_pct:+.2f}%")
        col4.metric("持股股數", f"{input_shares:,} 股")

        # 2. 計算均線、KD、RSI
        df['SMA5'] = df['Close'].rolling(window=5).mean()    # 5日線(週線)
        df['SMA20'] = df['Close'].rolling(window=20).mean()  # 20日線(月線)
        df = calculate_kd(df)
        df['RSI'] = calculate_rsi(df['Close'])

        # 3. 交易訊號判斷
        latest_k = df['K'].iloc[-1]
        latest_d = df['D'].iloc[-1]
        prev_k = df['K'].iloc[-2]
        prev_d = df['D'].iloc[-2]
        latest_rsi = df['RSI'].iloc[-1]

        st.subheader("💡 技術指標與交易訊號提示")
        
        signal_col1, signal_col2 = st.columns(2)
        with signal_col1:
            st.info(f"**當前技術數值**\n- K 值: `{latest_k:.2f}`\n- D 值: `{latest_d:.2f}`\n- RSI (14): `{latest_rsi:.2f}`")
            
        with signal_col2:
            messages = []
            if latest_k > 80:
                messages.append("🚨 **【賣出提示】** KD 指標高於 80（超買區），請注意回檔風險，建議考慮賣出！")
            
            if prev_k <= prev_d and latest_k > latest_d:
                messages.append("💡 **【買入提示】** 偵測到 KD 黃金交叉（K值向上突破D值），建議考慮購入！")
            elif latest_k > latest_d:
                messages.append("ℹ️ 目前 KD 呈現多頭排列（K > D）。")
            else:
                messages.append("ℹ️ 目前 KD 呈現空頭排列（K < D）。")
                
            for msg in messages:
                if "🚨" in msg or "💡" in msg:
                    st.warning(msg)
                else:
                    st.success(msg)

        # 4. 使用 Plotly 繪製互動式圖表
        st.subheader("📊 技術分析互動圖表 (K線、週月線、KD、RSI)")
        
        fig = make_subplots(
            rows=3, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.5, 0.25, 0.25],
            subplot_titles=(f"{ticker_symbol} K線與週/月線", "KD 指標", "RSI 指標")
        )

        # 主圖：K線與均線
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'],
            name='K線'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df['SMA5'], line=dict(color='blue', width=1.5), name='5日均線(週線)'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1.5), name='20日均線(月線)'), row=1, col=1)

        # 第二副圖：KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='red', width=1.5), name='K值'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='green', width=1.5), name='D值'), row=2, col=1)

        # 第三副圖：RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=3, col=1)

        fig.update_layout(
            height=700,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)