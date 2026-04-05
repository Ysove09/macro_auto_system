import streamlit as st
from datetime import datetime
import pytz
import pandas as pd

from db import init_db, load_news_history, load_latest_decision, load_recent_news
from auto_update import run_auto_update, should_auto_update
from market_data import get_market_snapshot

BJ_TZ = pytz.timezone("Asia/Shanghai")


def to_beijing_time_str(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    value_str = str(value).strip()
    if value_str.lower() in ["", "none", "nan"]:
        return ""

    try:
        if "T" in value_str:
            dt_obj = datetime.fromisoformat(value_str.replace("Z", "+00:00"))
            dt_obj = dt_obj.astimezone(BJ_TZ)
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt_obj = datetime.strptime(value_str, "%Y-%m-%d %H:%M:%S")
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value_str


def safe_text(value, fallback=""):
    if value is None:
        return fallback

    try:
        if pd.isna(value):
            return fallback
    except Exception:
        pass

    value_str = str(value).strip()
    if value_str.lower() in ["", "none", "nan"]:
        return fallback

    return value_str


def format_metric_value(price, unit):
    if price is None:
        return f"-- {unit}"
    return f"{price:,.2f} {unit}"


def format_metric_delta(change, pct):
    if change is None or pct is None:
        return None
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f} ({sign}{pct:.2f}%)"


def render_signal_card(title, signal):
    color_map = {
        "开多": "#163d2a",
        "开空": "#4a1f24",
        "空仓": "#3a3f4b",
    }
    bg = color_map.get(signal, "#2b2f38")

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border-radius:16px;
            padding:18px 20px;
            min-height:120px;
            border:1px solid rgba(255,255,255,0.08);
        ">
            <div style="font-size:15px; color:#d0d4dc; margin-bottom:16px;">{title}</div>
            <div style="font-size:36px; font-weight:700; color:white;">{signal}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_box(title, value, level="normal"):
    color_map = {
        "ok": "#163d2a",
        "warn": "#5a4520",
        "error": "#4a1f24",
        "normal": "#22324a"
    }
    bg = color_map.get(level, "#22324a")

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border-radius:14px;
            padding:14px 16px;
            min-height:88px;
            border:1px solid rgba(255,255,255,0.06);
        ">
            <div style="font-size:14px; color:#c8cfda; margin-bottom:10px;">{title}</div>
            <div style="font-size:20px; font-weight:600; color:white; white-space:pre-line;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def infer_status_level(status_note: str):
    text = safe_text(status_note, "系统运行正常")
    if "失败" in text or "异常" in text:
        return "warn"
    if "错误" in text or "崩" in text:
        return "error"
    return "ok"


st.set_page_config(
    page_title="东山对冲基金宏观决策系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

st.sidebar.title("功能导航")
page = st.sidebar.radio("请选择页面", ["首页总览", "历史新闻记录"])

st.sidebar.markdown("---")
st.sidebar.caption("版本：V1.0")
st.sidebar.caption("自动化规则：页面打开时若距离上次更新超过1小时，则自动更新一次")

if st.sidebar.button("立即自动更新", use_container_width=True):
    with st.spinner("正在抓取新闻并更新决策..."):
        run_auto_update(force=True)
    st.sidebar.success("更新完成，请刷新页面查看。")

if should_auto_update():
    try:
        with st.spinner("系统检测到超过1小时未更新，正在自动抓取新数据..."):
            run_auto_update()
    except Exception as e:
        st.warning(f"自动更新失败，但页面仍会显示最近一次有效结果：{e}")


if page == "首页总览":
    latest_df = load_latest_decision()

    st.title("东山对冲基金宏观决策系统")
    st.caption("一生只做三件事：热爱、坚持、收获")

    # ===== 实时行情 =====
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

    if not latest_df.empty:
        row = latest_df.iloc[0]

        update_time = to_beijing_time_str(row.get("update_time"))
        macro_update_time = to_beijing_time_str(row.get("macro_update_time"))
        news_update_time = to_beijing_time_str(row.get("news_update_time"))
        status_note = safe_text(row.get("status_note"), "系统运行正常")

        if not macro_update_time:
            macro_update_time = update_time

        if not news_update_time:
            news_update_time = update_time

        st.markdown("## 当前建议")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_signal_card("A股", row["a_share_view"])
        with c2:
            render_signal_card("黄金", row["gold_view"])
        with c3:
            render_signal_card("加密", row["crypto_view"])
        with c4:
            render_signal_card("商品", row["commodity_view"])

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("## 系统状态")

        s1, s2, s3 = st.columns(3)
        with s1:
            render_status_box("最近更新时间（北京时间）", update_time, "normal")
        with s2:
            # 修复重复/挤在一起的问题：强制换行
            combined_time = f"宏观：{macro_update_time}\n新闻：{news_update_time}"
            render_status_box("宏观 / 新闻更新时间", combined_time, "normal")
        with s3:
            render_status_box("系统状态", status_note, infer_status_level(status_note))

        st.markdown("---")

        base_text = safe_text(row.get("base_explanation"), "暂无基础判断说明")
        news_text = safe_text(row.get("news_explanation"), "本轮未触发明确新闻修正规则")

        left, right = st.columns(2)

        with left:
            st.markdown("## 基础判断")
            st.info(base_text)

        with right:
            st.markdown("## 新闻修正")
            st.warning(news_text)

        st.markdown("---")

        st.markdown("## 最近抓取新闻（最新 3 条）")
        recent_news = load_recent_news(limit=3)

        if not recent_news.empty:
            for _, item in recent_news.iterrows():
                with st.container():
                    st.markdown(
                        f"""
                        <div style="
                            border:1px solid rgba(255,255,255,0.08);
                            border-radius:14px;
                            padding:14px 16px;
                            margin-bottom:12px;
                            background:rgba(255,255,255,0.02);
                        ">
                            <div style="font-size:17px; font-weight:600; margin-bottom:8px;">
                                {safe_text(item['news_title'], '无标题')}
                            </div>
                            <div style="font-size:13px; color:#b8c0cc; margin-bottom:8px;">
                                来源：{safe_text(item['source'], '未知')} ｜ 发布时间：{to_beijing_time_str(item['published'])}
                            </div>
                            <div style="font-size:14px; color:#d7dce5;">
                                {safe_text(item['explanation'], '暂无说明')}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        else:
            st.write("暂无新闻数据。")

        with st.expander("数据来源说明 / 免责声明"):
            st.write("1. 中国宏观数据用于判定中国象限。")
            st.write("2. 美国宏观数据用于判定美国象限。")
            st.write("3. 新闻数据只用于修正，不单独决定长期基础判断。")
            st.write("4. 本系统仅作研究展示，不构成任何投资建议。")

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
