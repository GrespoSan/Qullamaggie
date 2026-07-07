import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Qullamaggie Surfing Screener", layout="wide")
st.title("Qullamaggie Surfing Screener")

with st.sidebar:
    ma_type = st.selectbox("Tipo MA", ["EMA", "SMA"])
    len1 = st.number_input("MA1", 1, 200, 10)
    len2 = st.number_input("MA2", 1, 200, 20)
    len3 = st.number_input("MA3", 1, 200, 50)
uploaded = st.file_uploader("Lista ticker (.txt)", type="txt")

def calc_ma(s, l, t):
    return s.ewm(span=l, adjust=False).mean() if t == "EMA" else s.rolling(l).mean()

def analyze(t):
    try:
        df = yf.download(t, period="6mo", progress=False, auto_adjust=False)
        if len(df) < 60: return None
        
        # --- FIX COLONNE MULTIINDEX ---
        # Se yFinance restituisce colonne MultiIndex, teniamo solo il primo livello (Open, High, ecc.)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Squeeze e conversione esplicita in Series 1D per evitare problemi con numpy/plotly
        c = df["Close"].squeeze()
        l = df["Low"].squeeze()
        
        m1, m2, m3 = calc_ma(c, len1, ma_type), calc_ma(c, len2, ma_type), calc_ma(c, len3, ma_type)
        close, low, ma1, ma2, ma3 = c.iloc[-1], l.iloc[-1], m1.iloc[-1], m2.iloc[-1], m3.iloc[-1]
        
        trend = 40 if close > ma1 > ma2 > ma3 else 25 if close > ma2 > ma3 else 10 if close > ma3 else 0
        d1 = abs(low - ma1) / ma1
        d2 = abs(low - ma2) / ma2
        prox = 30 if low >= ma2 and d1 <= 0.015 else 20 if low >= ma3 and d2 <= 0.02 else 10 if low >= ma3 else 0
        
        win = c.tail(20)
        # .to_numpy().flatten() assicura che polyfit riceva un array 1D pulito
        slope = np.polyfit(np.arange(len(win)), win.to_numpy().flatten(), 1)[0]
        smooth = win.diff().std() / win.mean()
        lin = 30 if slope > 0 and smooth < 0.02 else 15 if slope > 0 else 0
        score = trend + prox + lin
        
        state = "Uptrend" if close > ma2 > ma3 else "Neutral" if close > ma3 else "Downtrend"
        
        out = df.copy()
        out["MA1"] = m1
        out["MA2"] = m2
        out["MA3"] = m3
        return {"Ticker": t, "Trend": state, "Score": round(score, 1), "Prezzo": round(float(close), 2), "df": out}
    except Exception as e:
        # In produzione puoi rimettere "return None", utile stampare l'errore in console se si blocca
        print(f"Errore con {t}: {e}")
        return None

if st.button("Scansiona"):
    txt = uploaded.getvalue().decode() if uploaded else "AAPL,MSFT,NVDA,META,AMZN"
    tickers = [x.strip().upper() for x in txt.replace(",", " ").split() if x.strip()]
    res = []
    pb = st.progress(0)
    for i, t in enumerate(tickers):
        r = analyze(t)
        if r: res.append(r)
        pb.progress((i + 1) / len(tickers))
    st.session_state["res"] = res

if "res" in st.session_state:
    res = st.session_state["res"]
    if res:
        df = pd.DataFrame([{k: v for k, v in r.items() if k != "df"} for r in res]).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True)
        tk = st.selectbox("Grafico", df["Ticker"])
        r = next(x for x in res if x["Ticker"] == tk)
        d = r["df"]
        
        # Disegnamo il grafico passando i dati convertiti in modo pulito a Plotly
        fig = go.Figure([go.Candlestick(
            x=d.index,
            open=d["Open"].squeeze(),
            high=d["High"].squeeze(),
            low=d["Low"].squeeze(),
            close=d["Close"].squeeze(),
            name="Price"
        )])
        fig.add_scatter(x=d.index, y=d["MA1"].squeeze(), name="MA1")
        fig.add_scatter(x=d.index, y=d["MA2"].squeeze(), name="MA2")
        fig.add_scatter(x=d.index, y=d["MA3"].squeeze(), name="MA3")
        fig.update_layout(xaxis_rangeslider_visible=False, height=700)
        st.plotly_chart(fig, use_container_width=True)