import akshare as ak
import pandas as pd
import yfinance as yf


# =========================================================
# 桥水风格公开版：多因子宏观象限判定
# ---------------------------------------------------------
# 说明：
# 1. 不是桥水内部原版，而是“增长 + 通胀 + 流动性 + 信用 + 油价 + 实际利率”的公开版近似框架
# 2. 输出：
#    - china_quadrant
#    - us_quadrant
#    - china_reason
#    - us_reason
# 3. A股/现金/中国债看中国；黄金/加密/商品看美国
# =========================================================


def _direction(latest, prev):
    if latest > prev:
        return 1
    elif latest < prev:
        return -1
    return 0


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _last_two_from_report(df, value_col="今值", date_col="日期", forecast_col="预测值"):
    """
    适用于 Jin10 风格接口:
    列通常包含: 日期 / 今值 / 前值 / 预测值
    """
    temp = df.copy()

    temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce")
    temp = temp.dropna(subset=[value_col]).reset_index(drop=True)

    if len(temp) < 2:
        raise ValueError(f"报告数据不足两期: {value_col}")

    latest = temp.iloc[-1]
    prev = temp.iloc[-2]

    latest_val = _safe_float(latest[value_col])
    prev_val = _safe_float(prev[value_col])

    latest_date = str(latest[date_col]) if date_col in temp.columns else ""
    prev_date = str(prev[date_col]) if date_col in temp.columns else ""

    forecast_val = None
    if forecast_col in temp.columns:
        try:
            forecast_val = float(latest[forecast_col])
        except Exception:
            forecast_val = None

    surprise = None
    if forecast_val is not None:
        surprise = latest_val - forecast_val

    return {
        "latest": latest_val,
        "prev": prev_val,
        "latest_date": latest_date,
        "prev_date": prev_date,
        "surprise": surprise,
    }


def _last_two_from_simple(df, value_col, date_col):
    """
    适用于中国 PMI / 社融这类自定义列
    """
    temp = df.copy()
    temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce")
    temp = temp.dropna(subset=[value_col]).reset_index(drop=True)

    if len(temp) < 2:
        raise ValueError(f"简单数据不足两期: {value_col}")

    latest = temp.iloc[-1]
    prev = temp.iloc[-2]

    return {
        "latest": _safe_float(latest[value_col]),
        "prev": _safe_float(prev[value_col]),
        "latest_date": str(latest[date_col]) if date_col in temp.columns else "",
        "prev_date": str(prev[date_col]) if date_col in temp.columns else "",
        "surprise": None,
    }


def _last_two_us_10y():
    df = ak.bond_zh_us_rate(start_date="20200101").copy()
    value_col = "美国国债收益率10年"
    date_col = "日期"

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[value_col]).reset_index(drop=True)

    if len(df) < 2:
        raise ValueError("美国10Y收益率数据不足两期")

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    return {
        "latest": _safe_float(latest[value_col]),
        "prev": _safe_float(prev[value_col]),
        "latest_date": str(latest[date_col]),
        "prev_date": str(prev[date_col]),
        "surprise": None,
    }


def _last_two_oil():
    """
    原油：用 CL=F 最近 5 个日线收盘
    """
    hist = yf.Ticker("CL=F").history(period="7d", interval="1d")

    if hist is None or hist.empty:
        raise ValueError("原油数据为空")

    hist = hist.reset_index()
    hist["Close"] = pd.to_numeric(hist["Close"], errors="coerce")
    hist = hist.dropna(subset=["Close"]).reset_index(drop=True)

    if len(hist) < 2:
        raise ValueError("原油数据不足两期")

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]

    latest_date = str(latest["Date"])[:10]
    prev_date = str(prev["Date"])[:10]

    return {
        "latest": _safe_float(latest["Close"]),
        "prev": _safe_float(prev["Close"]),
        "latest_date": latest_date,
        "prev_date": prev_date,
        "surprise": None,
    }


def _score_to_quadrant(growth_score, inflation_score):
    """
    四象限映射：
    - 增长强 + 通胀弱  -> 复苏
    - 增长强 + 通胀强  -> 过热
    - 增长弱 + 通胀强  -> 滞胀
    - 增长弱 + 通胀弱  -> 衰退
    """
    if growth_score >= 0 and inflation_score < 0:
        return "复苏"
    elif growth_score >= 0 and inflation_score >= 0:
        return "过热"
    elif growth_score < 0 and inflation_score >= 0:
        return "滞胀"
    else:
        return "衰退"


def _fmt_reason_line(name, d):
    surprise_txt = ""
    if d.get("surprise") is not None:
        surprise_txt = f"；surprise={round(d['surprise'], 2)}"
    return f"{name}: {d['prev_date']}={d['prev']} → {d['latest_date']}={d['latest']}{surprise_txt}"


def get_auto_quadrants():
    # =====================================================
    # 中国：增长 + 通胀 + 信用脉冲
    # =====================================================
    china_cpi_df = ak.macro_china_cpi_yearly()
    china_ppi_df = ak.macro_china_ppi_yearly()
    china_pmi_df = ak.macro_china_pmi()
    china_shrzgm_df = ak.macro_china_shrzgm()

    china_cpi = _last_two_from_report(china_cpi_df, value_col="今值", date_col="日期", forecast_col="预测值")
    china_ppi = _last_two_from_report(china_ppi_df, value_col="今值", date_col="日期", forecast_col="预测值")
    china_pmi = _last_two_from_simple(china_pmi_df, value_col="制造业-指数", date_col="月份")
    china_shrzgm = _last_two_from_simple(china_shrzgm_df, value_col="社会融资规模增量", date_col="月份")

    # 中国增长分
    china_growth_score = (
        _direction(china_pmi["latest"], china_pmi["prev"])
        + _direction(china_shrzgm["latest"], china_shrzgm["prev"])
        + _direction(china_ppi["latest"], china_ppi["prev"])
    )

    # 中国通胀分
    china_inflation_score = (
        _direction(china_cpi["latest"], china_cpi["prev"])
        + _direction(china_ppi["latest"], china_ppi["prev"])
        + (_direction(china_cpi["surprise"], 0) if china_cpi["surprise"] is not None else 0)
        + (_direction(china_ppi["surprise"], 0) if china_ppi["surprise"] is not None else 0)
    )

    china_quadrant = _score_to_quadrant(china_growth_score, china_inflation_score)

    china_reason = "\n".join([
        "中国象限依据：",
        _fmt_reason_line("CPI年率", china_cpi),
        _fmt_reason_line("PPI年率", china_ppi),
        _fmt_reason_line("制造业PMI", china_pmi),
        _fmt_reason_line("社融增量", china_shrzgm),
        f"中国增长分={china_growth_score}，中国通胀分={china_inflation_score}",
    ])

    # =====================================================
    # 美国：增长 + 通胀 + 油价 + 实际利率
    # =====================================================
    usa_cpi_df = ak.macro_usa_cpi_monthly()
    usa_ppi_df = ak.macro_usa_core_ppi()
    usa_retail_df = ak.macro_usa_retail_sales()
    usa_unemp_df = ak.macro_usa_unemployment_rate()

    usa_cpi = _last_two_from_report(usa_cpi_df, value_col="今值", date_col="日期", forecast_col="预测值")
    usa_ppi = _last_two_from_report(usa_ppi_df, value_col="今值", date_col="日期", forecast_col="预测值")
    usa_retail = _last_two_from_report(usa_retail_df, value_col="今值", date_col="日期", forecast_col="预测值")
    usa_unemp = _last_two_from_report(usa_unemp_df, value_col="今值", date_col="日期", forecast_col="预测值")
    us10 = _last_two_us_10y()
    oil = _last_two_oil()

    real_yield_latest = us10["latest"] - usa_cpi["latest"]
    real_yield_prev = us10["prev"] - usa_cpi["prev"]

    # 美国增长分
    usa_growth_score = (
        _direction(usa_retail["latest"], usa_retail["prev"])
        + (_direction(usa_retail["surprise"], 0) if usa_retail["surprise"] is not None else 0)
        - _direction(usa_unemp["latest"], usa_unemp["prev"])
    )

    # 美国通胀分
    usa_inflation_score = (
        _direction(usa_cpi["latest"], usa_cpi["prev"])
        + _direction(usa_ppi["latest"], usa_ppi["prev"])
        + (_direction(usa_cpi["surprise"], 0) if usa_cpi["surprise"] is not None else 0)
        + (_direction(usa_ppi["surprise"], 0) if usa_ppi["surprise"] is not None else 0)
        + _direction(oil["latest"], oil["prev"])
        - _direction(real_yield_latest, real_yield_prev)
    )

    us_quadrant = _score_to_quadrant(usa_growth_score, usa_inflation_score)

    us_reason = "\n".join([
        "美国象限依据：",
        _fmt_reason_line("CPI月率", usa_cpi),
        _fmt_reason_line("核心PPI", usa_ppi),
        _fmt_reason_line("零售销售", usa_retail),
        _fmt_reason_line("失业率", usa_unemp),
        _fmt_reason_line("原油", oil),
        _fmt_reason_line("美国10Y", us10),
        f"实际利率代理(10Y-CPI): {round(real_yield_prev, 2)} → {round(real_yield_latest, 2)}",
        f"美国增长分={usa_growth_score}，美国通胀分={usa_inflation_score}",
    ])

    return {
        "china_quadrant": china_quadrant,
        "us_quadrant": us_quadrant,
        "china_reason": china_reason,
        "us_reason": us_reason,
        "china_growth_score": china_growth_score,
        "china_inflation_score": china_inflation_score,
        "us_growth_score": usa_growth_score,
        "us_inflation_score": usa_inflation_score,
    }
