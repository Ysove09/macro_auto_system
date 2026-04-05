import streamlit as st
from datetime import datetime
import pytz

from db import init_db, load_news_history, load_latest_decision, load_recent_news
from auto_update import run_auto_update, should_auto_update
from market_data import get_market_snapshot

BJ_TZ = pytz.timezone("Asia/Shanghai")


def to_beijing_time_str(value):
    if not value:
        return ""

    try:
        if "T" in value:
            dt_obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt_obj = dt_obj.astimezone(BJ_TZ)
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt_obj = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


st.set_page_config(
    page_title="自动宏观资产决策系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

# 页面加载时：如果超过 1 小时没更新，就自动更新一次
if should_auto_update():
    run_auto_update()

st.sidebar.title("功能导航")
page = st.sidebar.radio("请选择页面", ["首页总览", "历史新闻记录"])

st.sidebar.markdown("---")
st.sidebar.caption("版本：V1.0")
st.sidebar.caption("更新时间规则：打开页面时检查，超过1小时自动抓取；按钮点击可立即抓取")

if st.sidebar.button("立即自动更新", use_container_width=True):
    with st.spinner("正在抓取新闻并更新决策..."):
        run_auto_update(force=True)
    st.sidebar.success("更新完成，请刷新页面查看。")


def format_metric_value(price, unit):
    return f"{price:,.2f} {unit}"


def format_metric_delta(change, pct):
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f} ({sign}{pct:.2f}%)"


if page == "首页总览":
    st.title("自动宏观资产决策系统")
    st.caption("基于象限判断 + 实时新闻修正")

    @st.fragment(run_every="60s")
    def live_market_panel():
        st.markdown("## 实时行情")
        market = get_market_snapshot()

        st.caption(f"行情更新时间（北京时间）：{market['update_time']}")

        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric(
                label=f"{market['sse']['name']}（{market['sse']['status']}）",
                value=format_metric_value(market["sse"]["price"], market["sse"]["unit"]),
                delta=format_metric_delta(market["sse"]["change"], market["sse"]["pct"]),
            )

        with m2:
            st.metric(
                label=f"{market['btc']['name']}（{market['btc']['status']}）",
                value=format_metric_value(market["btc"]["price"], market["btc"]["unit"]),
                delta=format_metric_delta(market["btc"]["change"], market["btc"]["pct"]),
            )

        with m3:
            st.metric(
                label=f"{market['gold']['name']}（{market['gold']['status']}）",
                value=format_metric_value(market["gold"]["price"], market["gold"]["unit"]),
                delta=format_metric_delta(market["gold"]["change"], market["gold"]["pct"]),
            )

        with m4:
            st.metric(
                label=f"{market['oil']['name']}（{market['oil']['status']}）",
                value=format_metric_value(market["oil"]["price"], market["oil"]["unit"]),
                delta=format_metric_delta(market["oil"]["change"], market["oil"]["pct"]),
            )

    live_market_panel()

    st.markdown("---")

    latest_df = load_latest_decision()

    if not latest_df.empty:
        row = latest_df.iloc[0]

        st.subheader(f"最近更新时间（北京时间）：{to_beijing_time_str(row['update_time'])}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("A股当前建议", row["a_share_view"])
            st.metric("黄金当前建议", row["gold_view"])

        with col2:
            st.metric("加密当前建议", row["crypto_view"])
            st.metric("商品当前建议", row["commodity_view"])

        st.markdown("---")
        st.markdown("## 自动决策说明")

        base_text = row.get("base_explanation", "")
        news_text = row.get("news_explanation", "")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### 基础判断")
            if base_text:
                st.info(base_text)
            else:
                st.info("暂无基础判断说明")

        with c2:
            st.markdown("### 新闻修正")
            if news_text:
                st.warning(news_text)
            else:
                st.warning("本轮未触发明确新闻修正规则")

        st.markdown("---")
        st.markdown("## 最近抓取新闻")

        recent_news = load_recent_news(limit=5)

        if not recent_news.empty:
            for _, item in recent_news.iterrows():
                with st.expander(f"{item['news_title']}"):
                    st.write(f"**来源：** {item['source']}")
                    st.write(f"**发布时间（北京时间）：** {to_beijing_time_str(item['published'])}")
                    if item["explanation"]:
                        st.write(f"**分析说明：** {item['explanation']}")
        else:
            st.write("暂无新闻数据。")

    else:
        st.warning("当前还没有自动更新结果，请点击左侧“立即自动更新”。")

elif page == "历史新闻记录":
    st.title("历史新闻记录（最多保留20条）")

    df = load_news_history()

    if not df.empty:
        show_df = df[[
            "news_title",
            "source",
            "published",
            "a_share_view",
            "gold_view",
            "crypto_view",
            "commodity_view"
        ]].copy()

        show_df["published"] = show_df["published"].apply(to_beijing_time_str)

        show_df.columns = [
            "新闻标题",
            "来源",
            "发布时间（北京时间）",
            "A股",
            "黄金",
            "加密",
            "商品"
        ]

        st.dataframe(show_df, use_container_width=True, hide_index=True)
    else:
        st.write("当前还没有新闻记录。")
