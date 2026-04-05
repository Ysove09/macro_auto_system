def get_base_decision(china_quadrant: str, us_quadrant: str):
    """
    根据你的象限体系给出基础决策：
    - A股、现金、中国债：看中国
    - 加密、黄金、商品：看美国
    """

    result = {
        "A股": "空仓",
        "黄金": "空仓",
        "加密": "空仓",
        "商品": "空仓",
        "说明": f"基础判断来自中国象限={china_quadrant}，美国象限={us_quadrant}"
    }

    # A股：看中国象限
    if china_quadrant == "复苏":
        result["A股"] = "开多"
    elif china_quadrant == "滞胀":
        result["A股"] = "开空"
    elif china_quadrant == "衰退":
        result["A股"] = "空仓"
    elif china_quadrant == "过热":
        result["A股"] = "开空"

    # 黄金：看美国象限
    if us_quadrant == "滞胀":
        result["黄金"] = "开多"
    elif us_quadrant == "衰退":
        result["黄金"] = "开多"
    elif us_quadrant == "复苏":
        result["黄金"] = "空仓"
    elif us_quadrant == "过热":
        result["黄金"] = "开空"

    # 加密：看美国象限
    if us_quadrant == "复苏":
        result["加密"] = "开多"
    elif us_quadrant == "滞胀":
        result["加密"] = "空仓"
    elif us_quadrant == "衰退":
        result["加密"] = "开空"
    elif us_quadrant == "过热":
        result["加密"] = "开空"

    # 商品：看美国象限
    if us_quadrant == "滞胀":
        result["商品"] = "开多"
    elif us_quadrant == "复苏":
        result["商品"] = "开多"
    elif us_quadrant == "衰退":
        result["商品"] = "空仓"
    elif us_quadrant == "过热":
        result["商品"] = "开空"

    return result