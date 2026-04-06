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


def _now_bj() -> datetime:
    return datetime.now(BJ_TZ)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).replace(",", "").strip()
        if text == "" or text.lower() in {"nan", "none"}:
            return None
        return float(text)
    except Exception:
        return None


def _first_valid(row: pd.Series, candidates: Iterable[str]) -> Optional[float]:
    for col in candidates:
        if col in row.index:
            value = _safe_float(row[col])
            if value is not None:
                return value
    return None


def _is_cn_workday(d: date) -> bool:
    if china_calendar is not None:
        try:
            return bool(china_calendar.is_workday(d))
        except Exception:
            pass

    # 兜底：如果 holiday 包失效，就退化成普通工作日判断
    return d.weekday() < 5


def _prev_cn_workday(d: date) -> date:
    cur = d - timedelta(days=1)
    while not _is_cn_workday(cur):
        cur -= timedelta(days=1)
    return cur


def _next_cn_workday(d: date) -> date:
    cur = d + timedelta(days=1)
    while not _is_cn_workday(cur):
        cur += timedelta(days=1)
    return cur


def _between(t: time, start: time, end: time) -> bool:
    return start <= t <= end


def _is_cn_stock_open(dt: datetime) -> bool:
    if not _is_cn_workday(dt.date()):
        return False

    t = dt.time()
    am = _between(t, time(9, 30), time(11, 30))
    pm = _between(t, time(13, 0), time(15, 0))
    return am or pm


def _is_cn_futures_day_open(dt: datetime) -> bool:
    if not _is_cn_workday(dt.date()):
        return False

    t = dt.time()
    s1 = _between(t, time(9, 0), time(10, 15))
    s2 = _between(t, time(10, 30), time(11, 30))
    s3 = _between(t, time(13, 30), time(15, 0))
    return s1 or s2 or s3


def _is_cn_futures_night_open(dt: datetime) -> bool:
    """
    适配沪金、原油这类有夜盘的品种：
    - 21:00~23:59：要求今天是工作日，且下一个自然日也是工作日
    - 00:00~02:30：要求昨天是工作日，且今天是工作日
    """
    t = dt.time()

    if _between(t, time(21, 0), time(23, 59, 59)):
        today = dt.date()
        tomorrow = today + timedelta(days=1)
        return _is_cn_workday(today) and _is_cn_workday(tomorrow)

    if _between(t, time(0, 0), time(2, 30)):
        today = dt.date()
        yesterday = today - timedelta(days=1)
        return _is_cn_workday(yesterday) and _is_cn_workday(today)

    return False


def _is_cn_futures_open(dt: datetime) -> bool:
    return _is_cn_futures_day_open(dt) or _is_cn_futures_night_open(dt)


def _fetch_sse_index() -> Dict[str, Any]:
    now = _now_bj()
    is_open = _is_cn_stock_open(now)

    result = {
        "name": "上证指数",
        "price": None,
        "change": 0.0,
        "pct": 0.0,
        "unit": "点",
        "status": "上个交易日收盘",
    }

    try:
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        row = df[df["代码"] == "000001"].iloc[0]

        price = _first_valid(row, ["最新价", "最新", "收盘"])
        change = _first_valid(row, ["涨跌额", "涨跌"])
        pct = _first_valid(row, ["涨跌幅"])

        result["price"] = price
        result["change"] = change if change is not None else 0.0
        result["pct"] = pct if pct is not None else 0.0
        result["status"] = "实时" if is_open else "上个交易日收盘"

        # 非交易时段统一按“上个交易日收盘”展示，不强调盘中波动
        if not is_open:
            result["change"] = 0.0
            result["pct"] = 0.0

    except Exception:
        pass

    return result


def _fetch_btc_spot() -> Dict[str, Any]:
    result = {
        "name": "BTC现货",
        "price": None,
        "change": None,
        "pct": None,
        "unit": "USD",
        "status": "实时",
    }

    try:
        price_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=10
        )
        price_resp.raise_for_status()
        price_json = price_resp.json()
        result["price"] = _safe_float(price_json.get("price"))

        stat_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            timeout=10
        )
        stat_resp.raise_for_status()
        stat_json = stat_resp.json()
        result["change"] = _safe_float(stat_json.get("priceChange"))
        result["pct"] = _safe_float(stat_json.get("priceChangePercent"))

    except Exception:
        pass

    return result


def _extract_futures_row(df: pd.DataFrame, symbol_keywords: Iterable[str]) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None

    for col in ["symbol", "代码", "合约", "名称", "品种"]:
        if col in df.columns:
            text_series = df[col].astype(str)
            for kw in symbol_keywords:
                matched = df[text_series.str.contains(str(kw), case=False, na=False)]
                if not matched.empty:
                    return matched.iloc[0]

    return df.iloc[0]


def _try_fetch_futures_realtime(symbol_candidates: Iterable[str], row_keywords: Iterable[str]) -> Optional[pd.Series]:
    for sym in symbol_candidates:
        try:
            df = ak.futures_zh_realtime(symbol=sym)
            row = _extract_futures_row(df, row_keywords)
            if row is not None:
                return row
        except Exception:
            continue
    return None


def _try_fetch_futures_spot(symbol_candidates: Iterable[str], row_keywords: Iterable[str]) -> Optional[pd.Series]:
    """
    兼容一些 AKShare / 新浪期货接口版本。
    """
    for sym in symbol_candidates:
        for market in ["CF", "FF", ""]:
            try:
                if market:
                    df = ak.futures_zh_spot(symbol=sym, market=market, adjust="0")
                else:
                    df = ak.futures_zh_spot(symbol=sym)
                row = _extract_futures_row(df, row_keywords)
                if row is not None:
                    return row
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

    row = _try_fetch_futures_realtime(symbol_candidates, row_keywords)
    if row is None:
        row = _try_fetch_futures_spot(symbol_candidates, row_keywords)

    if row is None:
        return result

    price = _first_valid(row, ["最新价", "最新", "现价", "最新行情价", "收盘价"])
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
        # 非交易时段统一按“上个交易日价格”展示
        result["change"] = 0.0
        result["pct"] = 0.0
        result["status"] = "上个交易日价格"

    return result


def get_market_snapshot() -> Dict[str, Any]:
    now = _now_bj()

    sse = _fetch_sse_index()
    btc = _fetch_btc_spot()

    gold = _fetch_cn_futures(
        display_name="沪金",
        symbol_candidates=["AU0", "AU", "au", "沪金"],
        row_keywords=["AU0", "AU", "au", "沪金"],
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
