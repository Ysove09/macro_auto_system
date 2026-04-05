from datetime import datetime, timedelta
import pytz

from db import init_db, save_news_result, save_latest_decision, load_latest_decision
from news_fetcher import fetch_latest_news
from news_analyzer import analyze_news
from decision_engine import merge_results
from quadrant_engine import get_base_decision
from macro_regime import get_auto_quadrants

BJ_TZ = pytz.timezone("Asia/Shanghai")


def bj_now_str():
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")


def clean_text(text: str) -> str:
    if not text:
        return ""
    return text.strip().strip("；;，,。 \n\t")


def get_previous_fallback(latest_df):
    """
    如果本轮宏观/新闻抓取失败，就沿用上一条有效结果
    """
    if latest_df.empty:
        return {
            "china_quadrant": "衰退",
            "us_quadrant": "衰退",
            "base_explanation": "暂无历史有效基础判断，使用默认衰退象限",
            "news_explanation": "",
            "macro_update_time": "",
            "news_update_time": "",
            "status_note": "系统首次启动，暂无历史兜底数据",
            "A股": "空仓",
            "黄金": "空仓",
            "加密": "空仓",
            "商品": "空仓",
        }

    row = latest_df.iloc[0]
    return {
        "china_quadrant": row.get("china_quadrant", "衰退"),
        "us_quadrant": row.get("us_quadrant", "衰退"),
        "base_explanation": row.get("base_explanation", "沿用上次基础判断"),
        "news_explanation": row.get("news_explanation", ""),
        "macro_update_time": row.get("macro_update_time", ""),
        "news_update_time": row.get("news_update_time", ""),
        "status_note": row.get("status_note", ""),
        "A股": row.get("a_share_view", "空仓"),
        "黄金": row.get("gold_view", "空仓"),
        "加密": row.get("crypto_view", "空仓"),
        "商品": row.get("commodity_view", "空仓"),
    }


def combine_base_and_news(base_result, news_result):
    final_result = base_result.copy()

    for asset in ["A股", "黄金", "加密", "商品"]:
        if news_result.get(asset) in ["开多", "开空", "空仓"]:
            final_result[asset] = news_result[asset]

    # A股只能 开多 / 空仓
    if final_result["A股"] == "开空":
        final_result["A股"] = "空仓"

    final_result["china_quadrant"] = base_result.get("china_quadrant", "")
    final_result["us_quadrant"] = base_result.get("us_quadrant", "")
    final_result["base_explanation"] = base_result.get("base_explanation", "")
    final_result["news_explanation"] = clean_text(news_result.get("说明", ""))

    final_result["说明"] = (
        f"基础判断：{final_result['base_explanation']}\n"
        f"新闻修正：{final_result['news_explanation'] if final_result['news_explanation'] else '本轮未触发明确新闻修正规则'}"
    )

    return final_result


def run_auto_update(force=False):
    init_db()
    latest_df = load_latest_decision()
    previous = get_previous_fallback(latest_df)

    status_messages = []
    macro_update_time = previous.get("macro_update_time", "")
    news_update_time = previous.get("news_update_time", "")

    # ===== 1. 宏观数据 =====
    try:
        macro_state = get_auto_quadrants()
        china_quadrant = macro_state["china_quadrant"]
        us_quadrant = macro_state["us_quadrant"]
        china_reason = macro_state["china_reason"]
        us_reason = macro_state["us_reason"]
        macro_update_time = bj_now_str()

        base_result = get_base_decision(
            china_quadrant=china_quadrant,
            us_quadrant=us_quadrant,
            china_reason=china_reason,
            us_reason=us_reason,
        )

    except Exception as e:
        status_messages.append(f"宏观数据抓取失败，沿用上次有效结果：{str(e)}")

        base_result = {
            "A股": previous["A股"],
            "黄金": previous["黄金"],
            "加密": previous["加密"],
            "商品": previous["商品"],
            "china_quadrant": previous["china_quadrant"],
            "us_quadrant": previous["us_quadrant"],
            "base_explanation": previous["base_explanation"],
            "说明": ""
        }

    # ===== 2. 新闻数据 =====
    all_results = []

    try:
        news_list = fetch_latest_news()
        news_update_time = bj_now_str()

        for news in news_list:
            try:
                result = analyze_news(news["title"])
                save_news_result(
                    news["title"],
                    news["source"],
                    news["published"],
                    result
                )
                all_results.append(result)
            except Exception as e:
                status_messages.append(f"单条新闻处理失败：{str(e)}")

    except Exception as e:
        status_messages.append(f"新闻抓取失败，沿用上次有效结果：{str(e)}")

    news_result = merge_results(all_results)
    final_result = combine_base_and_news(base_result, news_result)

    final_result["macro_update_time"] = macro_update_time
    final_result["news_update_time"] = news_update_time

    if status_messages:
        final_result["status_note"] = "；".join(status_messages)
    else:
        final_result["status_note"] = "系统运行正常"

    save_latest_decision(final_result)
    return final_result


def should_auto_update():
    latest_df = load_latest_decision()
    if latest_df.empty:
        return True

    latest_time_str = latest_df.iloc[0]["update_time"]
    latest_time = datetime.strptime(latest_time_str, "%Y-%m-%d %H:%M:%S")
    latest_time = BJ_TZ.localize(latest_time)

    now = datetime.now(BJ_TZ)
    return now - latest_time >= timedelta(hours=1)
