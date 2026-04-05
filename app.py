import streamlit as st
from db import init_db, load_news_history, load_latest_decision, load_recent_news
from auto_update import run_auto_update

st.set_page_config(
    page_title="自动宏观资产决策系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

st.sidebar.title("功能导航")
page = st.sidebar.radio("请选择页面", ["首页总览", "历史新闻记录"])

st.sidebar.markdown("---")
st.sidebar.caption("版本：V1.0")

if st.sidebar.button("立即自动更新", use_container_width=True):
    with st.spinner("正在抓取新闻并更新决策..."):
        run_auto_update()
    st.sidebar.success("更新完成，请查看首页。")

if page == "首页总览":
    st.title("自动宏观资产决策系统")
    st.caption("基于象限判断 + 实时新闻修正")

    latest_df = load_latest_decision()

    if not latest_df.empty:
        row = latest_df.iloc[0]

        st.subheader(f"最近更新时间：{row['update_time']}")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("A股当前建议", row["a_share_view"])
            st.metric("黄金当前建议", row["gold_view"])

        with col2:
            st.metric("加密当前建议", row["crypto_view"])
            st.metric("商品当前建议", row["commodity_view"])

        st.markdown("---")

        # 说明区拆分
        final_explanation = row.get("final_explanation", "")
        base_text = ""
        news_text = ""
        conclusion_text = ""

        if isinstance(final_explanation, str) and final_explanation:
            lines = [x.strip() for x in final_explanation.split("\n") if x.strip()]
            for line in lines:
                if line.startswith("基础判断："):
                    base_text = line.replace("基础判断：", "").strip()
                elif line.startswith("新闻修正："):
                    news_text = line.replace("新闻修正：", "").strip()
                elif line.startswith("最终结论："):
                    conclusion_text = line.replace("最终结论：", "").strip()

        st.markdown("## 自动决策说明")

        c1, c2, c3 = st.columns(3)

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
                st.warning("暂无新闻修正")

        with c3:
            st.markdown("### 最终结论")
            if conclusion_text:
                st.success(conclusion_text)
            else:
                st.success("暂无最终结论")

        st.markdown("---")

        # 最近抓取新闻
        st.markdown("## 最近抓取新闻")
        recent_news = load_recent_news(limit=5)

        if not recent_news.empty:
            for i, item in recent_news.iterrows():
                with st.expander(f"{item['news_title']}"):
                    st.write(f"**来源：** {item['source']}")
                    st.write(f"**发布时间：** {item['published']}")
                    if item["explanation"]:
                        st.write(f"**分析说明：** {item['explanation']}")
        else:
            st.write("暂无新闻数据。")

    else:
        st.warning("当前还没有自动更新结果，请点击左侧“立即自动更新”。")

elif page == "历史新闻记录":
    st.title("历史新闻记录")

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

        show_df.columns = [
            "新闻标题",
            "来源",
            "发布时间",
            "A股",
            "黄金",
            "加密",
            "商品"
        ]

        st.dataframe(show_df, use_container_width=True, hide_index=True)

    else:
        st.write("当前还没有新闻记录。")
