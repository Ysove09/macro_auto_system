import datetime as dt
import pytz
import akshare as ak
import yfinance as yf
import streamlit as st


CN_TZ = pytz.timezone("Asia/Shanghai")


def now_cn():
    return dt.datetime.now(CN_TZ)


def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _fallback(name, unit):
    return {
        "name": name,
        "price": None,
        "status": "数据异常",
        "unit": unit,
        "change": None,
        "pct": None,
    }


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


@st.cache_data(ttl=60)
def get_sse_price():
    try:
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        row = df[df["名称"] == "上证指数"].iloc[0]

        latest = _safe_float(row["最新价"])
        prev_close = _safe_float(row["昨收"], latest)

        if latest is None:
            return _fallback("上证指数", "点")

        if is_cn_stock_open():
            price = latest
            status = "实时"
        else:
            price = prev_close
            status = "上个交易日收盘"

        change = price - prev_close if prev_close is not None else None
        pct = (change / prev_close * 100) if prev_close else None

        return {
            "name": "上证指数",
            "price": round(price, 2),
            "status": status,
            "unit": "点",
            "change": round(change, 2) if change is not None else None,
            "pct": round(pct, 2) if pct is not None else None,
        }
    except Exception:
        return _fallback("上证指数", "点")


@st.cache_data(ttl=60)
def get_hujin_price():
    try:
        df = ak.futures_zh_realtime(symbol="黄金")

        if "name" in df.columns:
            target = df[df["name"].astype(str).str.contains("连续", na=False)]
            row = target.iloc[0] if not target.empty else df.iloc[0]
        else:
            row = df.iloc[0]

        trade = _safe_float(row["trade"])
        preclose = _safe_float(row["preclose"], trade)

        if trade is None:
            return _fallback("沪金", "元/克")

        if is_cn_futures_open():
            price = trade
            status = "实时"
        else:
            price = preclose
            status = "上个交易日价格"

        change = price - preclose if preclose is not None else None
        pct = (change / preclose * 100) if preclose else None

        return {
            "name": "沪金",
            "price": round(price, 2),
            "status": status,
            "unit": "元/克",
            "change": round(change, 2) if change is not None else None,
            "pct": round(pct, 2) if pct is not None else None,
        }
    except Exception:
        return _fallback("沪金", "元/克")


@st.cache_data(ttl=60)
def get_oil_price():
    try:
        df = ak.futures_zh_realtime(symbol="原油")

        if "name" in df.columns:
            target = df[df["name"].astype(str).str.contains("连续", na=False)]
            row = target.iloc[0] if not target.empty else df.iloc[0]
        else:
            row = df.iloc[0]

        trade = _safe_float(row["trade"])
        preclose = _safe_float(row["preclose"], trade)

        if trade is None:
            return _fallback("原油期货", "元/桶")

        if is_cn_futures_open():
            price = trade
            status = "实时"
        else:
            price = preclose
            status = "上个交易日价格"

        change = price - preclose if preclose is not None else None
        pct = (change / preclose * 100) if preclose else None

        return {
            "name": "原油期货",
            "price": round(price, 2),
            "status": status,
            "unit": "元/桶",
            "change": round(change, 2) if change is not None else None,
            "pct": round(pct, 2) if pct is not None else None,
        }
    except Exception:
        return _fallback("原油期货", "元/桶")


@st.cache_data(ttl=60)
def get_btc_spot():
    try:
        ticker = yf.Ticker("BTC-USD")
        intraday = ticker.history(period="2d", interval="1m")
        daily = ticker.history(period="5d", interval="1d")

        if intraday is not None and not intraday.empty:
            latest = _safe_float(intraday["Close"].dropna().iloc[-1])
        elif daily is not None and not daily.empty:
            latest = _safe_float(daily["Close"].dropna().iloc[-1])
        else:
            return _fallback("BTC现货", "USD")

        if daily is not None and len(daily["Close"].dropna()) >= 2:
            prev_close = _safe_float(daily["Close"].dropna().iloc[-2], latest)
        else:
            prev_close = latest

        change = latest - prev_close if prev_close is not None else None
        pct = (change / prev_close * 100) if prev_close else None

        return {
            "name": "BTC现货",
            "price": round(latest, 2),
            "status": "实时",
            "unit": "USD",
            "change": round(change, 2) if change is not None else None,
            "pct": round(pct, 2) if pct is not None else None,
        }
    except Exception:
        return _fallback("BTC现货", "USD")


@st.cache_data(ttl=60)
def get_market_snapshot():
    return {
        "sse": get_sse_price(),
        "btc": get_btc_spot(),
        "gold": get_hujin_price(),
        "oil": get_oil_price(),
        "update_time": now_cn().strftime("%Y-%m-%d %H:%M:%S"),
    }
