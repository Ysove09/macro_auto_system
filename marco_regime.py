import akshare as ak
import pandas as pd


# =========================================================
# 桥水风格公开版：多因子宏观象限判定
# ---------------------------------------------------------
# 说明：
# 1. 不是桥水内部原版，而是“增长 + 通胀 + 流动性 + 信用 + 油价/实际利率”的公开版近似框架
# 2. 输出：
#    - china_quadrant
#    - us_quadrant
#    - china_reason
#    - us_reason
# 3. A股/现金/中国债看中国；黄金/加密/商品看美国
# =========================================================


def _to_numeric_series(df, value_cols=("今值", "现值")):
    temp = df.copy()
    value_col = None
    for c in value_cols:
        if c in temp.columns:
            value_col = c
            break
    if value_col is None:
        raise ValueError(f"未找到数值列: {value_cols}")

    temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce")
    temp = temp.dropna(subset=[value_col]).reset_index(drop=True)
    return temp, value_col


def _find_date_col(df):
    for c in ["日期", "时间", "月份"]:
        if c in df.columns:
            return c
    return None


def _last_two(df, value_col=None):
    """
    取最近两期有效数据
    """
    temp = df.copy()

    if value_col is None:
        temp, value_col = _to_numeric_series(temp)
    else:
        temp[value_col] = pd.to_numeric(temp[value_col], errors="coerce")
        temp = temp.dropna(subset=[value_col]).reset_index(drop=True)

    if len(temp) < 2:
        raise ValueError("有效数据不足两期")

    date_col = _find_date_col(temp)

    latest = temp.iloc[-1]
    prev = temp.iloc[-2]

    return {
        "latest": float(latest[value_col]),
        "prev": float(prev[value_col]),
        "latest_date": str(latest[date_col]) if date_col else "",
        "prev_date": str(prev[date_col]) if date_col else "",
    }


def _direction(latest, prev):
    if latest > prev:
        return 1
    elif latest < prev:
        return -1
    return 0


def _safe_str(x):
    return "" if x is None else str(x)


def _score_to_quadrant(growth_score, inflation_score):
    """
    四象限映射（可后续继续按你的旧规则微调）
    growth_score >= 0 表示增长偏改善
    inflation_score >= 0 表示通胀偏上行
    """
    if growth_score >= 0 and inflation_score < 0:
        return "复苏"
    elif growth_score >= 0 and inflation_score >= 0:
        return "过热"
    elif growth_score < 0 and inflation_score >= 0:
        return "滞胀"
    else:
        return "衰退"


def _build_reason(title, items):
    lines = [title]
    for item in items:
        lines.append(
            f"{item['name']}: {item['prev_date']}={item['prev']} → {item['latest_date']}={item['latest']}"
        )
    return "\n".join(lines)


def get_auto_quadrants():
    # =====================================================
    # 中国：增长 + 通胀 + 流动性/信用脉冲
    # -----------------------------------------------------
    # 增长因子：
    #   - PMI（制造业景气）
    #   - PPI（工业价格/景气代理）
    #
    # 通胀因子：
    #   - CPI
    #   - PPI（兼具通胀属性）
    #
    # 流动性/信用脉冲：
    #   - 社融增量（信用扩张代理）
    # =====================================================

    china_cpi_df = ak.macro_china_cpi()
    china_ppi_df = ak.macro_china_ppi()
    china_pmi_df = ak.macro_china_pmi()
    china_shrzgm_df = ak.macro_china_shrzgm()

    china_cpi = _last_two(china_cpi_df)
    china_ppi = _last_two(china_ppi_df)
    china_pmi = _last_two(china_pmi_df, value_col="制造业-指数")
    china_shrzgm = _last_two(china_shrzgm_df, value_col="社会融资规模增量")

    # 中国增长分：PMI + PPI改善 + 社融改善
    china_growth_score = (
        _direction(china_pmi["latest"], china_pmi["prev"])
        + _direction(china_ppi["latest"], china_ppi["prev"])
        + _direction(china_shrzgm["latest"], china_shrzgm["prev"])
    )

    # 中国通胀分：CPI + PPI
    china_inflation_score = (
        _direction(china_cpi["latest"], china_cpi["prev"])
        + _direction(china_ppi["latest"], china_ppi["prev"])
    )

    china_quadrant = _score_to_quadrant(china_growth_score, china_inflation_score)

    china_reason = _build_reason("中国象限依据：", [
        {"name": "CPI", **china_cpi},
        {"name": "PPI", **china_ppi},
        {"name": "PMI", **china_pmi},
        {"name": "社融增量", **china_shrzgm},
    ])

    # =====================================================
    # 美国：增长 + 通胀 + 油价与实际利率
    # -----------------------------------------------------
    # 增长因子：
    #   - 零售销售
    #   - 失业率（反向）
    #
    # 通胀因子：
    #   - CPI月率
    #   - 核心PPI
    #
    # 油价与实际利率：
    #   - 油价用最近两期变化（通过 market_data 里已有原油价格模块仅展示，
    #     这里为了减少文件依赖，先不直接取原油期货行情，后面如你需要我可再并入）
    #   - 实际利率代理：10Y名义利率 - CPI
    # =====================================================

    usa_cpi_df = ak.macro_usa_cpi_monthly()
    usa_ppi_df = ak.macro_usa_core_ppi()
    usa_retail_df = ak.macro_usa_retail_sales()
    usa_unemp_df = ak.macro_usa_unemployment_rate()
    us_rate_df = ak.bond_zh_us_rate(start_date="20200101")

    usa_cpi = _last_two(usa_cpi_df)
    usa_ppi = _last_two(usa_ppi_df)
    usa_retail = _last_two(usa_retail_df)
    usa_unemp = _last_two(usa_unemp_df)

    # 美国10Y收益率最近两期
    us_rate_df = us_rate_df.copy()
    us_rate_df["美国国债收益率10年"] = pd.to_numeric(us_rate_df["美国国债收益率10年"], errors="coerce")
    us_rate_df = us_rate_df.dropna(subset=["美国国债收益率10年"]).reset_index(drop=True)

    if len(us_rate_df) < 2:
        raise ValueError("美国10年期国债收益率有效数据不足两期")

    us10_latest = float(us_rate_df.iloc[-1]["美国国债收益率10年"])
    us10_prev = float(us_rate_df.iloc[-2]["美国国债收益率10年"])
    us10_latest_date = _safe_str(us_rate_df.iloc[-1]["日期"])
    us10_prev_date = _safe_str(us_rate_df.iloc[-2]["日期"])

    # 实际利率代理：10Y - CPI
    real_yield_latest = us10_latest - usa_cpi["latest"]
    real_yield_prev = us10_prev - usa_cpi["prev"]

    # 美国增长分：零售销售改善 - 失业率上升
    usa_growth_score = (
        _direction(usa_retail["latest"], usa_retail["prev"])
        - _direction(usa_unemp["latest"], usa_unemp["prev"])
    )

    # 美国通胀分：CPI + 核心PPI + 实际利率下行（利多通胀资产，记正）
    usa_inflation_score = (
        _direction(usa_cpi["latest"], usa_cpi["prev"])
        + _direction(usa_ppi["latest"], usa_ppi["prev"])
        - _direction(real_yield_latest, real_yield_prev)
    )

    us_quadrant = _score_to_quadrant(usa_growth_score, usa_inflation_score)

    us_reason_lines = [
        "美国象限依据：",
        f"CPI: {usa_cpi['prev_date']}={usa_cpi['prev']} → {usa_cpi['latest_date']}={usa_cpi['latest']}",
        f"核心PPI: {usa_ppi['prev_date']}={usa_ppi['prev']} → {usa_ppi['latest_date']}={usa_ppi['latest']}",
        f"零售销售: {usa_retail['prev_date']}={usa_retail['prev']} → {usa_retail['latest_date']}={usa_retail['latest']}",
        f"失业率: {usa_unemp['prev_date']}={usa_unemp['prev']} → {usa_unemp['latest_date']}={usa_unemp['latest']}",
        f"美国10Y: {us10_prev_date}={us10_prev} → {us10_latest_date}={us10_latest}",
        f"实际利率代理(10Y-CPI): 上期={round(real_yield_prev, 2)} → 本期={round(real_yield_latest, 2)}",
    ]
    us_reason = "\n".join(us_reason_lines)

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
