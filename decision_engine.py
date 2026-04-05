def merge_results(results):
    final_result = {
        "A股": "中性",
        "黄金": "中性",
        "加密": "中性",
        "商品": "中性",
        "说明": "当前没有抓到有效新闻，因此维持默认中性判断。"
    }

    if not results:
        return final_result

    for r in results:
        if r["A股"] in ["偏多", "偏谨慎", "分化"]:
            final_result["A股"] = r["A股"]

        if r["黄金"] in ["偏多", "短期承压"]:
            final_result["黄金"] = r["黄金"]

        if r["加密"] in ["偏多", "偏谨慎", "波动加大"]:
            final_result["加密"] = r["加密"]

        if r["商品"] in ["偏多", "分化"]:
            final_result["商品"] = r["商品"]

    explanations = [
        r["说明"] for r in results
        if r.get("说明") and r["说明"] != "未识别到明显规则。"
    ]

    if explanations:
        final_result["说明"] = "；".join(list(dict.fromkeys(explanations)))

    return final_result