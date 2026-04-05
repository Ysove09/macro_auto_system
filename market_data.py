import datetime as dt
import pytz
import akshare as ak
import yfinance as yf
import streamlit as st


CN_TZ = pytz.timezone("Asia/Shanghai")


def now_cn():
    return dt.datetime.now(CN_TZ)


def is_cn_stock_open():
    now = now_cn()
    if now.weekday() >= 5:
        return False

    t = now.time()
    morning = dt.time(9, 30) <= t <= dt.time(11, 30)
    afternoon = dt.time(13, 0) <= t <= dt.time(15, 0)
    return morning or afternoon


def is_cn_futures_open():
    now = now_cn()
    wd = now.weekday()
    t = now.time()

    day_1 = dt.time(9, 0) <= t <= dt.time(10, 15)
    day_2 = dt.time(10, 30) <= t <= dt.time(11, 30)
    day_3 = dt.time(13, 30) <= t <= dt.time(15, 0)
    night_1 = dt.time(21, 0) <= t <= dt.time(23, 59, 59)
    night_2 = dt.time(0, 0) <= t <= dt.time(2, 30)

    if wd < 5 and (day_1 or day_2 or day_3 or night_1):
        return True
    if wd in [1, 2, 3, 4, 5] and night_2:
        return True
    return False


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


@st.cache_data(ttl=60)
def get_sse_price():
    """
    上证指数：盘中用最新价，非盘中用昨收
    """
    df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    row = df[df["名称"] == "上证指数"].iloc[0]

    latest = _safe_float(row["最新价"])
    prev_close = _safe_float(row["昨收"])

    if is_cn_stock_open():
        price = latest
        status = "实时"
    else:
        price = prev_close
        status = "上个交易日收盘"

    change = price - prev_close
    pct = (change / prev_close * 100) if prev_close else 0

    return {
        "name": "上证指数",
        "price": round(price, 2),
        "status": status,
        "unit": "点",
        "change": round(change, 2),
        "pct": round(pct, 2),
    }


@st.cache_data(ttl=60)
def get_hujin_price():
    """
    沪金：用黄金期货连续/主力近似显示
    """
    df = ak.futures_zh_realtime(symbol="黄金")

    if "name" in df.columns:
        target = df[df["name"].astype(str).str.contains("连续", na=False)]
        row = target.iloc[0] if not target.empty else df.iloc[0]
    else:
        row = df.iloc[0]

    trade = _safe_float(row["trade"])
    preclose = _safe_float(row["preclose"])

    if is_cn_futures_open():
        price = trade
        status = "实时"
    else:
        price = preclose
        status = "上个交易日价格"

    change = price - preclose
    pct = (change / preclose * 100) if preclose else 0

    return {
        "name": "沪金",
        "price": round(price, 2),
        "status": status,
        "unit": "元/克",
        "change": round(change, 2),
        "pct": round(pct, 2),
    }


@st.cache_data(ttl=60)
def get_oil_price():
    """
    原油期货：用国内原油期货连续/主力近似显示
    """
    df = ak.futures_zh_realtime(symbol="原油")

    if "name" in df.columns:
        target = df[df["name"].astype(str).str.contains("连续", na=False)]
        row = target.iloc[0] if not target.empty else df.iloc[0]
    else:
        row = df.iloc[0]

    trade = _safe_float(row["trade"])
    preclose = _safe_float(row["preclose"])

    if is_cn_futures_open():
        price = trade
        status = "实时"
    else:
        price = preclose
        status = "上个交易日价格"

    change = price - preclose
    pct = (change / preclose * 100) if preclose else 0

    return {
        "name": "原油期货",
        "price": round(price, 2),
        "status": status,
        "unit": "元/桶",
        "change": round(change, 2),
        "pct": round(pct, 2),
    }


@st.cache_data(ttl=60)
def get_btc_spot():
    """
    BTC 现货：7x24，直接显示最新价
    """
    ticker = yf.Ticker("BTC-USD")
    intraday = ticker.history(period="2d", interval="1m")
    daily = ticker.history(period="5d", interval="1d")

    if intraday.empty:
        latest = _safe_float(daily["Close"].dropna().iloc[-1])
    else:
        latest = _safe_float(intraday["Close"].dropna().iloc[-1])

    if len(daily["Close"].dropna()) >= 2:
        prev_close = _safe_float(daily["Close"].dropna().iloc[-2])
    else:
        prev_close = latest

    change = latest - prev_close
    pct = (change / prev_close * 100) if prev_close else 0

    return {
        "name": "BTC现货",
        "price": round(latest, 2),
        "status": "实时",
        "unit": "USD",
        "change": round(change, 2),
        "pct": round(pct, 2),
    }


@st.cache_data(ttl=60)
def get_market_snapshot():
    return {
        "sse": get_sse_price(),
        "btc": get_btc_spot(),
        "gold": get_hujin_price(),
        "oil": get_oil_price(),
        "update_time": now_cn().strftime("%Y-%m-%d %H:%M:%S"),
    }
