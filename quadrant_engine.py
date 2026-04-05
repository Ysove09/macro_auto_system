def get_base_decision(china_quadrant: str, us_quadrant: str, china_reason: str, us_reason: str):
    """
    根据象限给出基础决策：
    - A股：只能 开多 / 空仓
    - 黄金、加密、商品：可 开多 / 开空 / 空仓
    """

    result = {
        "A股": "空仓",
        "黄金": "空仓",
        "加密": "空仓",
        "商品": "空仓",
        "china_quadrant": china_quadrant,
        "us_quadrant": us_quadrant,
        "base_explanation": (
            f"中国象限={china_quadrant}，依据：{china_reason}\n"
            f"美国象限={us_quadrant}，依据：{us_reason}"
        ),
        "说明": ""
    }

    # =========================
    # A股：只能 开多 / 空仓
    # =========================
    if china_quadrant == "复苏":
        result["A股"] = "开多"
    else:
        result["A股"] = "空仓"

    # =========================
    # 黄金：看美国
    # =========================
    if us_quadrant in ["滞胀", "衰退"]:
        result["黄金"] = "开多"
    elif us_quadrant == "过热":
        result["黄金"] = "开空"
    else:
        result["黄金"] = "空仓"

    # =========================
    # 加密：看美国
    # =========================
    if us_quadrant == "复苏":
        result["加密"] = "开多"
    elif us_quadrant in ["衰退", "过热"]:
        result["加密"] = "开空"
    else:
        result["加密"] = "空仓"

    # =========================
    # 商品：看美国
    # =========================
    if us_quadrant in ["复苏", "滞胀"]:
        result["商品"] = "开多"
    elif us_quadrant == "过热":
        result["商品"] = "开空"
    else:
        result["商品"] = "空仓"

    return result
