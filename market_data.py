from datetime import datetime, date, time, timedelta
from typing import Any, Dict, Iterable, Optional

import akshare as ak
import pandas as pd
import pytz
import requests

try:
    import china_calendar
except Exception:
    china_calendar = None

BJ_TZ = pytz.timezone("Asia/Shanghai")


# ============================================
# 2026 年中国官方节假日 / 调休工作日（手动覆盖）
# ============================================
CN_REST_DAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
    date(2026, 2, 15), date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21), date(2026, 2, 22), date(2026, 2, 23),
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4), date(2026, 5, 5),
    date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
    date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4),
    date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7),
}

CN_WORKDAYS_2026 = {
    date(2026, 1, 4),
    date(2026, 2, 14),
    date(2026, 2, 28),
    date(2026, 5, 9),
    date(2026, 9, 20),
    date(2026, 10, 10),
}


def _now_bj() -> datetime:
    return datetime.now(BJ_TZ)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).replace(",", "").replace("%", "").strip()
        if text == "" or text.lower() in {"nan", "none"}:
            return None
        return float(text)
    except Exception:
        return None


def _first_valid(obj: Any, candidates: Iterable[str]) -> Optional[float]:
    for col in candidates:
        try:
            value = obj[col]
            result = _safe_float(value)
            if result is not None:
                return result
        except Exception:
            continue
    return None


def _is_cn_workday(d: date) -> bool:
    if d in CN_WORKDAYS_2026:
        return True
    if d in CN_REST_DAYS_2026:
        return False

    if china_calendar is not None:
        try:
            return bool(china_calendar.is_workday(d))
        except Exception:
            pass

    return d.weekday() < 5


def _prev_cn_workday(d: date) -> date:
    cur = d - timedelta(days=1)
    while not _is_cn_workday(cur):
        cur -= timedelta(days=1)
    return cur


def _between(t: time, start: time, end: time) -> bool:
    return start <= t <= end


def _is_cn_stock_open(dt_obj: datetime) -> bool:
    if not _is_cn_workday(dt_obj.date()):
        return False

    t = dt_obj.time()
    am = _between(t, time(9, 30), time(11, 30))
    pm = _between(t, time(13, 0), time(15, 0))
    return am or pm


def _is_cn_futures_day_open(dt_obj: datetime) -> bool:
    if not _is_cn_workday(dt_obj.date()):
        return False

    t = dt_obj.time()
    s1 = _between(t, time(9, 0), time(10, 15))
    s2 = _between(t, time(10, 30), time(11, 30))
    s3 = _between(t, time(13, 30), time(15, 0))
    return s1 or s2 or s3


def _is_cn_futures_night_open(dt_obj: datetime) -> bool:
    t = dt_obj.time()
    today = dt_obj.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    if _between(t, time(21, 0), time(23, 59, 59)):
        return _is_cn_workday(today) and _is_cn_workday(tomorrow)

    if _between(t, time(0, 0), time(2, 30)):
        return _is_cn_workday(yesterday) and _is_cn_workday(today)

    return False


def _is_cn_futures_open(dt_obj: datetime) -> bool:
    return _is_cn_futures_day_open(dt_obj) or _is_cn_futures_night_open(dt_obj)


# ============================================
# 上证指数
# ============================================
def _fetch_sse_index() -> Dict[str, Any]:
    now = _now_bj()
    is_open = _is_cn_stock_open(now)

    result = {
        "name": "上证指数",
        "price": None,
        "change": 0.0,
        "pct": 0.0,
        "unit": "点",
        "status": "实时" if is_open else "上个交易日收盘",
    }

    try:
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        row = df[df["代码"] == "000001"].iloc[0]

        price = _first_valid(row, ["最新价", "最新", "收盘"])
        change = _first_valid(row, ["涨跌额", "涨跌"])
        pct = _first_valid(row, ["涨跌幅"])

        result["price"] = price
        result["status"] = "实时" if is_open else "上个交易日收盘"

        if is_open:
            result["change"] = 0.0 if change is None else change
            result["pct"] = 0.0 if pct is None else pct
        else:
            result["change"] = 0.0
            result["pct"] = 0.0

    except Exception:
        pass

    if result["price"] is None:
        try:
            hist = ak.stock_zh_index_daily_em(symbol="sh000001")
            if hist is not None and not hist.empty:
                last_row = hist.iloc[-1]
                result["price"] = _first_valid(last_row, ["close", "收盘"])
                result["change"] = 0.0
                result["pct"] = 0.0
                result["status"] = "上个交易日收盘"
        except Exception:
            pass

    return result


# ============================================
# BTC：多接口兜底
# ============================================
def _fetch_btc_spot() -> Dict[str, Any]:
    result = {
        "name": "BTC现货",
        "price": None,
        "change": 0.0,
        "pct": 0.0,
        "unit": "USD",
        "status": "实时",
    }

    # 1) Binance
    try:
        price_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=10
        )
        price_resp.raise_for_status()
        price_json = price_resp.json()
        price = _safe_float(price_json.get("price"))

        stat_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            timeout=10
        )
        stat_resp.raise_for_status()
        stat_json = stat_resp.json()

        result["price"] = price
        result["change"] = _safe_float(stat_json.get("priceChange")) or 0.0
        result["pct"] = _safe_float(stat_json.get("priceChangePercent")) or 0.0

        if result["price"] is not None:
            return result
    except Exception:
        pass

    # 2) Coinbase
    try:
        coinbase_resp = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=10
        )
        coinbase_resp.raise_for_status()
        coinbase_json = coinbase_resp.json()
        price = _safe_float(coinbase_json.get("data", {}).get("amount"))

        if price is not None:
            result["price"] = price
            result["change"] = 0.0
            result["pct"] = 0.0
            return result
    except Exception:
        pass

    # 3) CoinGecko
    try:
        gecko_resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10
        )
        gecko_resp.raise_for_status()
        gecko_json = gecko_resp.json()
        price = _safe_float(gecko_json.get("bitcoin", {}).get("usd"))

        if price is not None:
            result["price"] = price
            result["change"] = 0.0
            result["pct"] = 0.0
            return result
    except Exception:
        pass

    return result


# ============================================
# 国内期货通用解析
# ============================================
def _extract_row(df: pd.DataFrame, keywords: Iterable[str]) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None

    text_cols = [c for c in df.columns if df[c].dtype == "object"]

    for _, row in df.iterrows():
        joined = " ".join([str(row[c]) for c in text_cols if pd.notna(row[c])])
        for kw in keywords:
            if str(kw).lower() in joined.lower():
                return row

    return None


def _try_futures_realtime(symbol_candidates: Iterable[str], row_keywords: Iterable[str]) -> Optional[pd.Series]:
    for sym in symbol_candidates:
        try:
            df = ak.futures_zh_realtime(symbol=sym)
            row = _extract_row(df, row_keywords)
            if row is not None:
                return row
            if df is not None and not df.empty:
                return df.iloc[0]
        except Exception:
            continue
    return None


def _try_futures_spot(symbol_candidates: Iterable[str], row_keywords: Iterable[str]) -> Optional[pd.Series]:
    for sym in symbol_candidates:
        try:
            df = ak.futures_zh_spot(symbol=sym)
            row = _extract_row(df, row_keywords)
            if row is not None:
                return row
            if df is not None and not df.empty:
                return df.iloc[0]
        except Exception:
            continue
    return None


def _try_futures_main_hist(symbol_candidates: Iterable[str]) -> Optional[pd.DataFrame]:
    for sym in symbol_candidates:
        try:
            df = ak.futures_main_sina(symbol=sym)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


def _fetch_cn_futures(
    display_name: str,
    symbol_candidates: Iterable[str],
    row_keywords: Iterable[str],
    unit: str
) -> Dict[str, Any]:
    now = _now_bj()
    is_open = _is_cn_futures_open(now)

    result = {
        "name": display_name,
        "price": None,
        "change": 0.0,
        "pct": 0.0,
        "unit": unit,
        "status": "实时" if is_open else "上个交易日价格",
    }

    row = _try_futures_realtime(symbol_candidates, row_keywords)
    if row is None:
        row = _try_futures_spot(symbol_candidates, row_keywords)

    if row is not None:
        price = _first_valid(row, ["最新价", "最新", "现价", "收盘价", "最新行情价"])
        prev_close = _first_valid(row, ["昨收", "昨结算", "昨结", "前收盘价", "昨日收盘价"])
        change = _first_valid(row, ["涨跌额", "涨跌", "涨跌值"])
        pct = _first_valid(row, ["涨跌幅", "涨跌幅度"])

        result["price"] = price

        if is_open:
            if change is None and price is not None and prev_close not in (None, 0):
                change = price - prev_close
            if pct is None and change is not None and prev_close not in (None, 0):
                pct = change / prev_close * 100

            result["change"] = 0.0 if change is None else change
            result["pct"] = 0.0 if pct is None else pct
            result["status"] = "实时"
        else:
            # 非交易时段统一不显示涨跌
            result["change"] = 0.0
            result["pct"] = 0.0
            result["status"] = "上个交易日价格"

    # 如果实时接口没拿到，就退回历史连续合约收盘
    if result["price"] is None:
        hist = _try_futures_main_hist(symbol_candidates)
        if hist is not None and not hist.empty:
            last_row = hist.iloc[-1]
            close = _first_valid(last_row, ["close", "收盘", "收盘价", "最新价"])

            result["price"] = close
            result["status"] = "上个交易日价格"
            result["change"] = 0.0
            result["pct"] = 0.0

    return result


def get_market_snapshot() -> Dict[str, Any]:
    now = _now_bj()

    sse = _fetch_sse_index()
    btc = _fetch_btc_spot()

    gold = _fetch_cn_futures(
        display_name="沪金",
        symbol_candidates=["AU0", "AU", "au", "沪金"],
        row_keywords=["AU0", "AU", "au", "沪金", "黄金"],
        unit="元/克"
    )

    oil = _fetch_cn_futures(
        display_name="原油期货",
        symbol_candidates=["SC0", "SC", "sc", "原油"],
        row_keywords=["SC0", "SC", "sc", "原油"],
        unit="元/桶"
    )

    return {
        "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sse": sse,
        "btc": btc,
        "gold": gold,
        "oil": oil,
    }
