from datetime import datetime, timedelta
import pytz

from db import init_db, save_news_result, save_latest_decision, load_latest_decision
from news_fetcher import fetch_latest_news
from news_analyzer import analyze_news
from decision_engine import merge_results
from quadrant_engine import get_base_decision

BJ_TZ = pytz.timezone("Asia/Shanghai")


def clean_text(text: str) -> str:
    if not text:
        return ""
    return text.strip().strip("；;，,。 \n\t")


def combine_base_and_news(base_result, news_result):
    final_result = base_result.copy()

    # 新闻覆盖基础信号
    for asset in ["A股", "黄金", "加密", "商品"]:
        if news_result.get(asset) in ["开多", "开空", "空仓"]:
            final_result[asset] = news_result[asset]

    # A股强制限制：只能 开多 / 空仓
    if final_result["A股"] == "开空":
        final_result["A股"] = "空仓"

    final_result["china_quadrant"] = base_result.get("china_quadrant", "")
    final_result["us_quadrant"] = base_result.get("us_quadrant", "")
    final_result["base_explanation"] = base_result.get("base_explanation", "")
    final_result["news_explanation"] = clean_text(news_result.get("说明", ""))

    # 自动决策说明里不再放“最终结论”
    final_result["说明"] = (
        f"基础判断：{final_result['base_explanation']}\n"
        f"新闻修正：{final_result['news_explanation'] if final_result['news_explanation'] else '本轮未触发明确新闻修正规则'}"
    )

    return final_result


def run_auto_update(force=False):
    init_db()

    # ===== 这里填你自己的象限原因 =====
    china_quadrant = "复苏"
    us_quadrant = "滞胀"

    china_reason = "可手动填写，例如：中国 PPI 回升、社融改善、PMI 回到扩张区间"
    us_reason = "可手动填写，例如：美国 CPI 粘性偏强、油价抬升、增长放缓"
    # ============================

    base_result = get_base_decision(
        china_quadrant=china_quadrant,
        us_quadrant=us_quadrant,
        china_reason=china_reason,
        us_reason=us_reason,
    )

    news_list = fetch_latest_news()
    all_results = []

    for news in news_list:
        result = analyze_news(news["title"])
        save_news_result(
            news["title"],
            news["source"],
            news["published"],
            result
        )
        all_results.append(result)

    news_result = merge_results(all_results)
    final_result = combine_base_and_news(base_result, news_result)

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
