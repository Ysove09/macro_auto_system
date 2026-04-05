import datetime as dt
import pytz
import pandas as pd
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

    # 白天
    day_1 = dt.time(9, 0) <= t <= dt.time(10, 15)
    day_2 = dt.time(10, 30) <= t <= dt.time(11, 30)
    day_3 = dt.time(13, 30) <= t <= dt.time(15, 0)

    # 夜盘（简化版，适用于黄金/原油主流时段）
    night_1 = dt.time(21, 0) <= t <= dt.time(23, 59, 59)
    night_2 = dt.time(0, 0) <= t <= dt.time(2, 30)

    if wd < 5 and (day_1 or day_2 or day_3 or night_1):
        return True

    # 凌晨夜盘：周二到周六凌晨都可能是前一交易日晚盘延续
    if wd in [1, 2, 3, 4, 5] and night_2:
        return True

    return False


@st.cache_data(ttl=60)
def get_sse_price():
    """
    上证指数：开盘时显示最新价；未开盘显示昨收
    """
    df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    row = df[df["名称"] == "上证指数"].iloc[0]

    latest = float(row["最新价"])
    prev_close = float(row["昨收"])

    if is_cn_stock_open():
        price = latest
        status = "实时"
    else:
        price = prev_close
        status = "上个交易日收盘"

    return {
        "name": "上证指数",
        "price": round(price, 2),
        "status": status
    }


@st.cache_data(ttl=60)
def get_hujin_price():
    """
    沪金（用黄金期货连续/主力近似显示）
    """
    df = ak.futures_zh_realtime(symbol="黄金")

    if "name" in df.columns:
        target = df[df["name"].astype(str).str.contains("连续", na=False)]
        row = target.iloc[0] if not target.empty else df.iloc[0]
    else:
        row = df.iloc[0]

    trade = float(row["trade"])
    preclose = float(row["preclose"])

    if is_cn_futures_open():
        price = trade
        status = "实时"
    else:
        price = preclose
        status = "上个交易日价格"

    return {
        "name": "沪金",
        "price": round(price, 2),
        "status": status
    }


@st.cache_data(ttl=60)
def get_oil_price():
    """
    原油期货（用国内原油期货连续/主力近似显示）
    """
    df = ak.futures_zh_realtime(symbol="原油")

    if "name" in df.columns:
        target = df[df["name"].astype(str).str.contains("连续", na=False)]
        row = target.iloc[0] if not target.empty else df.iloc[0]
    else:
        row = df.iloc[0]

    trade = float(row["trade"])
    preclose = float(row["preclose"])

    if is_cn_futures_open():
        price = trade
        status = "实时"
    else:
        price = preclose
        status = "上个交易日价格"

    return {
        "name": "原油期货",
        "price": round(price, 2),
        "status": status
    }


@st.cache_data(ttl=60)
def get_btc_spot():
    """
    BTC 现货：7x24，直接显示最新可得价格
    """
    ticker = yf.Ticker("BTC-USD")
    hist = ticker.history(period="2d", interval="1m")

    if hist.empty:
        hist = ticker.history(period="5d", interval="1d")

    latest_price = float(hist["Close"].dropna().iloc[-1])

    return {
        "name": "BTC现货",
        "price": round(latest_price, 2),
        "status": "实时"
    }


@st.cache_data(ttl=60)
def get_market_snapshot():
    return {
        "sse": get_sse_price(),
        "btc": get_btc_spot(),
        "gold": get_hujin_price(),
        "oil": get_oil_price(),
    }
