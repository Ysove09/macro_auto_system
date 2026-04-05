def analyze_news(news_text: str):
    text = news_text.lower().replace(" ", "")

    result = {
        "A股": "空仓",
        "黄金": "空仓",
        "加密": "空仓",
        "商品": "空仓",
        "说明": ""
    }

    # 1. 美联储鹰派 / 降息推迟 / 美元强 / 实际利率强
    if (
        ("美联储" in news_text and ("鹰" in news_text or "强硬" in news_text))
        or ("降息" in news_text and "推迟" in news_text)
        or ("federalreserve" in text)
        or ("fed" in text and ("hawkish" in text or "higherrates" in text or "strongerdollar" in text))
        or ("risingyields" in text)
        or ("strongerdollar" in text)
    ):
        result["A股"] = "开空"
        result["黄金"] = "开空"
        result["加密"] = "开空"
        result["商品"] = "空仓"
        result["说明"] = "美元和实际利率预期偏强时，通常压制黄金与风险资产。"

    # 2. 中国刺激政策 / 地产政策 / 降准 / 稳增长
    elif (
        ("中国" in news_text and "刺激" in news_text)
        or ("地产" in news_text and "政策" in news_text)
        or ("降准" in news_text)
        or ("降息" in news_text and "中国" in news_text)
        or ("稳增长" in news_text)
        or ("chinastimulus" in text)
        or ("propertysupport" in text)
        or ("easingpolicy" in text)
    ):
        result["A股"] = "开多"
        result["黄金"] = "空仓"
        result["加密"] = "空仓"
        result["商品"] = "开多"
        result["说明"] = "国内稳增长和宽信用政策，通常利好A股及顺周期商品。"

    # 3. 战争 / 冲突升级 / 避险 / 地缘风险
    elif (
        ("战争" in news_text)
        or ("避险" in news_text)
        or ("冲突升级" in news_text)
        or ("地缘" in news_text)
        or ("风险事件" in news_text)
        or ("iranwar" in text)
        or ("war" in text)
        or ("geopoliticaltensions" in text)
        or ("safehaven" in text)
        or ("blockadefears" in text)
    ):
        result["A股"] = "开空"
        result["黄金"] = "开多"
        result["加密"] = "开空"
        result["商品"] = "空仓"
        result["说明"] = "风险事件上升时，黄金通常受益，权益和高波动资产承压。"

    # 4. 比特币 / ETF / 净流入 / 回暖
    elif (
        ("比特币" in news_text and "etf" in text)
        or ("比特币" in news_text and "净流入" in news_text)
        or ("etf" in text and "净流入" in news_text)
        or ("比特币" in news_text and "回暖" in news_text)
        or ("加密" in news_text and "利好" in news_text)
        or ("bitcoin" in text and "etf" in text)
        or ("bitcoin" in text and "inflow" in text)
        or ("crypto" in text and "rebound" in text)
        or ("marketrebound" in text and "bitcoin" in text)
    ):
        result["A股"] = "空仓"
        result["黄金"] = "空仓"
        result["加密"] = "开多"
        result["商品"] = "空仓"
        result["说明"] = "ETF资金流入和情绪回暖通常利好加密资产风险偏好。"

    # 5. 通胀 / 油价 / 黄金价格波动
    elif (
        ("通胀" in news_text and "上行" in news_text)
        or ("油价" in news_text and "大涨" in news_text)
        or ("原油" in news_text and "上涨" in news_text)
        or ("goldprices" in text and "slide" in text)
        or ("goldslides" in text)
        or ("oilsurges" in text)
        or ("inflation" in text and "rise" in text)
    ):
        result["A股"] = "空仓"
        result["黄金"] = "开多"
        result["加密"] = "空仓"
        result["商品"] = "开多"
        result["说明"] = "通胀与油价上行通常利好商品和黄金。"

    return result