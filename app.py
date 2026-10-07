import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 設定網頁標題與排版
st.set_page_config(
    page_title="台股智慧看盤與損益試算系統",
    page_icon="📈",
    layout="centered"
)

st.title("📈 台股智慧看盤與損益試算")
st.markdown("輸入台股代碼，即時分析**週 KD、RSI、成交量放大 3 倍**，並試算您的庫存損益！")

# ==========================================
# 側邊欄：使用者輸入區
# ==========================================
st.sidebar.header("🔍 查詢設定")
stock_code = st.sidebar.text_input("台股代碼", value="2330", max_chars=6)

st.sidebar.markdown("---")
st.sidebar.header("💰 庫存損益試算 (選填)")
enable_pnl = st.sidebar.checkbox("啟用損益試算", value=False)
buy_price = 0.0
shares = 0

if enable_pnl:
    buy_price = st.sidebar.number_input("平均買進成本 (元)", min_value=0.0, value=500.0, step=1.0)
    shares = st.sidebar.number_input("持有股數", min_value=0, value=1000, step=100)

query_btn = st.sidebar.button("開始分析", type="primary")

# ==========================================
# 主程式邏輯
# ==========================================
if query_btn or stock_code:
    ticker_symbol = f"{stock_code}.TW"
    
    with st.spinner(f"正在載入 {ticker_symbol} 歷史數據..."):
        try:
            stock = yf.Ticker(ticker_symbol)
            df = stock.history(period="6mo")
            
            if df.empty:
                st.error(f"⚠️ 查無代碼 `{stock_code}` 的資料，請確認台股代碼是否正確（例如台積電請輸入 2330）。")
                st.stop()
        except Exception as e:
            st.error(f"連線或抓取資料失敗: {e}")
            st.stop()

    # 1. 成交量與 3 倍放大計算
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    latest_volume = df['Volume'].iloc[-1]
    avg_volume_5 = df['Vol_MA5'].iloc[-2] if len(df) > 5 else latest_volume
    is_volume_3x = latest_volume >= (avg_volume_5 * 3)

    # 2. 14 日 RSI 計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    latest_rsi = df['RSI'].iloc[-1]

    # 3. 週 KD 計算
    df_weekly = df.resample('W').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()

    low_9 = df_weekly['Low'].rolling(window=9).min()
    high_9 = df_weekly['High'].rolling(window=9).max()
    rsv = (df_weekly['Close'] - low_9) / (high_9 - low_9) * 100
    df_weekly['K'] = rsv.ewm(com=2, adjust=False).mean()
    df_weekly['D'] = df_weekly['K'].ewm(com=2, adjust=False).mean()

    latest_k = df_weekly['K'].iloc[-1]
    latest_d = df_weekly['D'].iloc[-1]
    prev_k = df_weekly['K'].iloc[-2]
    prev_d = df_weekly['D'].iloc[-2]

    kd_signal = "盤整無交叉"
    signal_color = "normal"
    if prev_k <= prev_d and latest_k > latest_d:
        kd_signal = "🟢 週 KD 黃金交叉 (K 向上穿越 D)"
        signal_color = "success"
    elif prev_k >= prev_d and latest_k < latest_d:
        kd_signal = "🔴 週 KD 死亡交叉 (K 向下跌破 D)"
        signal_color = "error"

    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100

    # ==========================================
    # 畫面呈現 (Metrics 區塊)
    # ==========================================
    st.markdown(f"### 📊 【台股代碼: {stock_code}】技術分析報告")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("最新收盤價", f"{current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
    col2.metric("14日 RSI", f"{latest_rsi:.2f}")
    col3.metric("週 K / D 值", f"{latest_k:.1f} / {latest_d:.1f}")

    # 訊號狀態提示
    if signal_color == "success":
        st.success(f"**指標狀態**：{kd_signal}")
    elif signal_color == "error":
        st.error(f"**指標狀態**：{kd_signal}")
    else:
        st.info(f"**指標狀態**：{kd_signal}")

    # 成交量警示
    st.markdown("#### 📈 成交量動態")
    v_col1, v_col2 = st.columns(2)
    v_col1.metric("今日成交量", f"{latest_volume:,.0f} 股")
    v_col2.metric("近5日均量", f"{avg_volume_5:,.0f} 股")

    if is_volume_3x:
        st.warning("🔥 **【成交量警示】** 今日成交量放大達 3 倍以上！")
    else:
        st.info("💡 **【成交量提示】** 今日成交量未達放大 3 倍標準。")

    # ==========================================
    # 損益試算結果呈現
    # ==========================================
    if enable_pnl and shares > 0:
        st.markdown("---")
        st.markdown("### 💰 庫存損益試算結果")
        total_cost = buy_price * shares
        market_value = current_price * shares
        gross_profit = market_value - total_cost
        return_rate = (gross_profit / total_cost) * 100

        p1, p2, p3 = st.columns(3)
        p1.metric("持有部位總成本", f"NT$ {total_cost:,.2f}")
        p2.metric("目前總市值", f"NT$ {market_value:,.2f}")
        p3.metric("未實現損益", f"NT$ {gross_profit:+,.2f}", f"{return_rate:+.2f}%")

    # ==========================================
    # 技術分析圖表繪製 (含 KD、RSI 走勢)
    # ==========================================
    st.markdown("---")
    st.markdown("### 📉 技術指標線圖分析")
    
    tab1, tab2, tab3 = st.tabs(["📉 收盤價走勢", "📊 週 KD 指標 (K/D)", "📈 14 日 RSI 指標"])

    with tab1:
        st.caption("近半年每日收盤價走勢圖")
        st.line_chart(df['Close'])

    with tab2:
        st.caption("週 K 線與 D 線雙線對比圖（藍線：K值，橘線：D值）")
        st.line_chart(df_weekly[['K', 'D']])

    with tab3:
        st.caption("14 日 RSI 走勢圖（一般以 70 以上視為超買，30 以下視為超賣）")
        st.line_chart(df['RSI'])