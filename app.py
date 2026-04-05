import streamlit as st
from db import init_db, load_news_history, load_latest_decision
from auto_update import run_auto_update

st.set_page_config(page_title="自动宏观资产决策系统", layout="wide")

init_db()

st.sidebar.title("功能导航")
page = st.sidebar.radio("请选择页面", ["首页总览", "历史新闻记录"])

st.sidebar.markdown("---")

if st.sidebar.button("立即自动更新"):
    run_auto_update()
    st.sidebar.success("自动更新完成，请刷新页面查看最新结果。")

if page == "首页总览":
    st.title("自动宏观资产决策系统")

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

        st.markdown("### 自动决策说明")
        st.info(row["summary"])
    else:
        st.warning("当前还没有自动更新结果，请先点击左侧“立即自动更新”。")

elif page == "历史新闻记录":
    st.title("历史新闻分析记录")

    df = load_news_history()

    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("当前还没有新闻记录。")