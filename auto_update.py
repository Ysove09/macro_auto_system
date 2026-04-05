from db import init_db, save_news_result, save_latest_decision
from news_fetcher import fetch_latest_news
from news_analyzer import analyze_news
from decision_engine import merge_results
from quadrant_engine import get_base_decision


def clean_text(text: str) -> str:
    """
    清理说明文字两端多余的标点和空格
    """
    if not text:
        return ""
    return text.strip().strip("；;，,。 \n\t")


def extract_base_summary(base_text: str) -> str:
    """
    把基础说明整理成干净的一句话，避免重复“基础判断来自”
    """
    base_text = clean_text(base_text)
    if not base_text:
        return ""

    if base_text.startswith("基础判断来自"):
        base_text = base_text.replace("基础判断来自", "", 1)
        base_text = clean_text(base_text)

    return base_text


def build_final_explanation(base_result, news_result, final_result) -> str:
    """
    生成结构化说明，避免多余分号、重复前缀和冗余标点。
    """
    base_summary = extract_base_summary(base_result.get("说明", ""))
    news_summary = clean_text(news_result.get("说明", ""))
    news_summary = news_summary.replace("；", "，").replace(";", "，")
    news_summary = news_summary.replace("。", "，")
    while "，，" in news_summary:
        news_summary = news_summary.replace("，，", "，")
    news_summary = news_summary.replace("， ", "，")
    news_summary = news_summary.strip("， ")

    base_part = f"基础判断：中国象限={china_quadrant}，美国象限={us_quadrant}"

    duplicate_base_summary = f"中国象限={china_quadrant}，美国象限={us_quadrant}"
    if base_summary and base_summary != duplicate_base_summary:
        base_part += f"（{base_summary}）"

    final_part = (
        f"最终结论：A股={final_result['A股']}，黄金={final_result['黄金']}，"
        f"加密={final_result['加密']}，商品={final_result['商品']}"
    )

    parts = [base_part]
    if news_summary:
        parts.append(f"新闻修正：{news_summary}")
    parts.append(final_part)

    return "\n".join(parts)


def combine_base_and_news(base_result, news_result):
    """
    新闻结果优先覆盖基础结果，但只覆盖明确方向。
    说明文字改成结构化展示，避免重复和多余分号。
    """
    final_result = base_result.copy()

    # 新闻信号覆盖基础信号
    for asset in ["A股", "黄金", "加密", "商品"]:
        if news_result.get(asset) in ["开多", "开空", "空仓"]:
            final_result[asset] = news_result[asset]

    final_result["说明"] = build_final_explanation(base_result, news_result, final_result)
    return final_result


def run_auto_update():
    init_db()

    # 这里先手动写死象限，后面再改成自动读取宏观数据
    china_quadrant = "复苏"
    us_quadrant = "滞胀"
    globals()["china_quadrant"] = china_quadrant
    globals()["us_quadrant"] = us_quadrant

    base_result = get_base_decision(china_quadrant, us_quadrant)

    news_list = fetch_latest_news()
    print("抓到的新闻数量：", len(news_list))

    all_results = []

    for i, news in enumerate(news_list[:10], 1):
        print(f"第{i}条新闻：", news)
        result = analyze_news(news["title"])
        print("分析结果：", news["title"], "=>", result)

        save_news_result(
            news["title"],
            news["source"],
            news["published"],
            result
        )
        all_results.append(result)

    news_result = merge_results(all_results)
    final_result = combine_base_and_news(base_result, news_result)

    print("基础象限结果：", base_result)
    print("新闻合并结果：", news_result)
    print("最终合并结果：", final_result)

    save_latest_decision(final_result)

    return final_result


if __name__ == "__main__":
    result = run_auto_update()
    print("自动更新完成：", result)