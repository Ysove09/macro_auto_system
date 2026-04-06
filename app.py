import os
import io
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

from db import init_db, load_latest_decision, load_recent_news
from auto_update import run_auto_update, should_auto_update
from market_data import get_market_snapshot

BJ_TZ = pytz.timezone("Asia/Shanghai")
REPORTS_DIR = "reports"

# 这里写你自己的 GitHub 仓库信息
GITHUB_USER = "Ysove09"
GITHUB_REPO = "macro_auto_system"


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


def infer_status_level(status_note: str):
    text = safe_text(status_note, "系统运行正常")
    if "失败" in text or "异常" in text:
        return "warn"
    if "错误" in text or "崩" in text:
        return "error"
    return "ok"


def render_signal_card(title, signal):
    color_map = {
        "开多": ("#153826", "#7CFFB2"),
        "开空": ("#4A1F24", "#FF9B9B"),
        "空仓": ("#343A46", "#D9DEE8"),
    }
    bg, fg = color_map.get(signal, ("#343A46", "#D9DEE8"))

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border-radius:18px;
            padding:22px 22px;
            min-height:135px;
            border:1px solid rgba(255,255,255,0.08);
            box-shadow: 0 10px 25px rgba(0,0,0,0.18);
        ">
            <div style="
                font-size:15px;
                color:#d0d4dc;
                margin-bottom:18px;
                letter-spacing:0.5px;
            ">
                {title}
            </div>
            <div style="
                font-size:42px;
                font-weight:800;
                color:{fg};
                line-height:1.1;
            ">
                {signal}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_box(title, value, level="normal"):
    color_map = {
        "ok": "#143625",
        "warn": "#5A4520",
        "error": "#4A1F24",
        "normal": "#22324A"
    }
    bg = color_map.get(level, "#22324A")

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border-radius:16px;
            padding:16px 18px;
            min-height:92px;
            border:1px solid rgba(255,255,255,0.06);
        ">
            <div style="
                font-size:13px;
                color:#c8cfda;
                margin-bottom:10px;
                letter-spacing:0.3px;
            ">
                {title}
            </div>
            <div style="
                font-size:20px;
                font-weight:700;
                color:white;
                white-space:pre-line;
                line-height:1.5;
            ">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_logo():
    logo_path = "24CF20B4-22EB-4000-A7B2-C171782EC782.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=170)
    else:
        st.info("未找到 Logo 图片，请检查图片文件名是否正确。")


def render_header():
    left, right = st.columns([1, 5])

    with left:
        render_logo()

    with right:
        st.markdown(
            """
            <div style="padding-top:10px;">
                <div style="
                    font-size:44px;
                    font-weight:900;
                    color:white;
                    letter-spacing:0.5px;
                    line-height:1.2;
                    margin-bottom:10px;
                ">
                    东山对冲基金宏观决策系统
                </div>
                <div style="
                    font-size:18px;
                    color:#c7ceda;
                    margin-bottom:10px;
                ">
                    一生只做三件事：热爱、坚持、收获
                </div>
                <div style="
                    font-size:14px;
                    color:#97a3b6;
                ">
                    宏观判断 · 新闻修正 · 实时跟踪
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_section_title(title, subtitle=""):
    st.markdown(
        f"""
        <div style="margin-top:10px; margin-bottom:16px;">
            <div style="font-size:24px; font-weight:800; color:white;">{title}</div>
            {"<div style='font-size:14px; color:#9aa5b5; margin-top:6px;'>" + subtitle + "</div>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_footer():
    st.markdown("---")
    st.markdown(
        """
        <div style="
            text-align:center;
            color:#8d98aa;
            font-size:13px;
            padding-top:8px;
            padding-bottom:6px;
        ">
            © 2026 Dongshan Hedge Fund Research System. All Rights Reserved.
        </div>
        """,
        unsafe_allow_html=True
    )


def render_news_brief():
    render_section_title("研究简报", "最近抓取新闻（最新 3 条）")
    recent_news = load_recent_news(limit=3)

    if not recent_news.empty:
        for idx, item in recent_news.iterrows():
            title = safe_text(item["news_title"], "无标题")
            source = safe_text(item["source"], "未知")
            published = to_beijing_time_str(item["published"])
            explanation = safe_text(item["explanation"], "暂无说明")

            st.markdown(
                f"""
                <div style="
                    background:rgba(255,255,255,0.025);
                    border:1px solid rgba(255,255,255,0.06);
                    border-radius:16px;
                    padding:18px 18px 16px 18px;
                    margin-bottom:14px;
                ">
                    <div style="
                        font-size:18px;
                        font-weight:700;
                        color:white;
                        line-height:1.6;
                        margin-bottom:8px;
                    ">
                        {idx + 1}. {title}
                    </div>
                    <div style="
                        font-size:13px;
                        color:#9eabbe;
                        margin-bottom:10px;
                    ">
                        {source} ｜ {published}
                    </div>
                    <div style="
                        font-size:14px;
                        color:#d4dae4;
                        line-height:1.8;
                    ">
                        {explanation}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.write("暂无新闻数据。")


def get_repo_reports():
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR, exist_ok=True)

    files = []
    for file_name in os.listdir(REPORTS_DIR):
        if file_name.lower() == "readme.md":
            continue

        file_path = os.path.join(REPORTS_DIR, file_name)
        if os.path.isfile(file_path):
            files.append({
                "file_name": file_name,
                "file_path": file_path,
                "title": Path(file_name).stem,
                "mtime": os.path.getmtime(file_path)
            })

    files = sorted(files, key=lambda x: x["mtime"], reverse=True)
    return files


def preview_repo_file(file_path, file_name):
    suffix = file_name.lower().split(".")[-1]

    st.markdown(f"### {Path(file_name).stem}")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    st.download_button(
        label=f"下载 {file_name}",
        data=file_bytes,
        file_name=file_name,
        use_container_width=True
    )

    if suffix in ["txt", "md", "py", "json", "csv"]:
        try:
            if suffix == "csv":
                df = pd.read_csv(io.BytesIO(file_bytes))
                st.dataframe(df, use_container_width=True)
            else:
                content = file_bytes.decode("utf-8", errors="ignore")
                st.text_area("内容预览", content, height=300)
        except Exception as e:
            st.warning(f"预览失败：{e}")

    elif suffix in ["png", "jpg", "jpeg", "webp"]:
        st.image(file_bytes, use_container_width=True)

    elif suffix == "pdf":
        encoded_name = quote(file_name)
        pdf_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/reports/{encoded_name}"
        st.info("当前浏览器对嵌入式 PDF 兼容性较弱，建议点击下面按钮在新标签页阅读。")
        st.link_button("新标签页打开 PDF", pdf_url, use_container_width=True)

    elif suffix in ["doc", "docx"]:
        st.info("Word 文件暂不支持网页内直接预览，请下载后阅读。")

    else:
        st.info("该文件类型暂不支持在线预览，但可下载阅读。")


def preview_uploaded_file(uploaded_file):
    file_name = uploaded_file.name
    suffix = file_name.lower().split(".")[-1]
    file_bytes = uploaded_file.read()

    st.markdown(f"### 临时预览：{Path(file_name).stem}")

    if suffix in ["txt", "md", "py", "json", "csv"]:
        try:
            if suffix == "csv":
                df = pd.read_csv(io.BytesIO(file_bytes))
                st.dataframe(df, use_container_width=True)
            else:
                content = file_bytes.decode("utf-8", errors="ignore")
                st.text_area("内容预览", content, height=300)
        except Exception as e:
            st.warning(f"预览失败：{e}")

    elif suffix in ["png", "jpg", "jpeg", "webp"]:
        st.image(file_bytes, use_container_width=True)

    elif suffix == "pdf":
        st.info("临时上传的 PDF 建议下载阅读，或放到 reports/ 文件夹后使用新标签页打开。")
        st.download_button(
            label=f"下载 {file_name}",
            data=file_bytes,
            file_name=file_name,
            use_container_width=True
        )

    elif suffix in ["doc", "docx"]:
        st.info("Word 文件暂不支持网页内直接预览，但可以下载。")
        st.download_button(
            label=f"下载 {file_name}",
            data=file_bytes,
            file_name=file_name,
            use_container_width=True
        )

    else:
        st.info("该文件类型暂不支持在线预览。")


def render_report_list():
    render_section_title("行情分析", "研究文件列表")

    reports = get_repo_reports()

    if not reports:
        st.info("当前 reports/ 文件夹里还没有正式研究文件。")
        return

    if "selected_report" not in st.session_state:
        st.session_state.selected_report = None

    for idx, report in enumerate(reports):
        upload_time = datetime.fromtimestamp(report["mtime"], BJ_TZ).strftime("%Y-%m-%d %H:%M")
        title = safe_text(report["title"], "未命名文件")

        st.markdown(
            f"""
            <div style="
                background:#f2f2f2;
                border-radius:16px;
                padding:22px 18px;
                margin-bottom:14px;
            ">
                <div style="
                    display:flex;
                    align-items:flex-end;
                    justify-content:space-between;
                    gap:12px;
                    flex-wrap:wrap;
                ">
                    <div style="
                        font-size:42px;
                        font-weight:800;
                        color:#e53935;
                        line-height:1.2;
                    ">
                        {title}
                    </div>
                    <div style="
                        font-size:14px;
                        color:#666666;
                        white-space:nowrap;
                        padding-bottom:6px;
                    ">
                        上传时间：{upload_time}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button(f"阅读全文 {idx + 1}", key=f"read_{idx}", use_container_width=True):
                st.session_state.selected_report = report["file_name"]
        with c2:
            with open(report["file_path"], "rb") as f:
                st.download_button(
                    label=f"下载文件 {idx + 1}",
                    data=f.read(),
                    file_name=report["file_name"],
                    key=f"download_{idx}",
                    use_container_width=True
                )

    if st.session_state.selected_report:
        selected = None
        for report in reports:
            if report["file_name"] == st.session_state.selected_report:
                selected = report
                break

        if selected:
            st.markdown("---")
            preview_repo_file(selected["file_path"], selected["file_name"])


st.set_page_config(
    page_title="东山对冲基金宏观决策系统",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

st.sidebar.title("功能导航")
page = st.sidebar.radio("请选择页面", ["首页总览", "行情分析"])

st.sidebar.markdown("---")
st.sidebar.caption("版本：V1.0")
st.sidebar.caption("自动化规则：仅在首页总览打开时，若距离上次更新超过1小时，则自动更新一次")

if st.sidebar.button("立即自动更新", use_container_width=True):
    with st.spinner("正在抓取新闻并更新决策..."):
        run_auto_update(force=True)
    st.sidebar.success("更新完成，请刷新页面查看。")

# 只在首页自动检查更新
if page == "首页总览" and should_auto_update():
    try:
        with st.spinner("系统检测到超过1小时未更新，正在自动抓取新数据..."):
            run_auto_update()
    except Exception as e:
        st.warning(f"自动更新失败，但页面仍会显示最近一次有效结果：{e}")


if page == "首页总览":
    latest_df = load_latest_decision()

    render_header()
    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    @st.fragment(run_every="60s")
    def live_market_panel():
        render_section_title("实时行情", "跟踪主要风险资产与宏观敏感品种")

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

        render_section_title("当前建议", "核心决策视图")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_signal_card("A股", row["a_share_view"])
        with c2:
            render_signal_card("黄金", row["gold_view"])
        with c3:
            render_signal_card("加密", row["crypto_view"])
        with c4:
            render_signal_card("商品", row["commodity_view"])

        st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

        render_section_title("系统状态", "最近有效更新与当前运行状态")

        s1, s2, s3 = st.columns(3)
        with s1:
            render_status_box("最近更新时间（北京时间）", update_time, "normal")
        with s2:
            combined_time = f"宏观：{macro_update_time}\n新闻：{news_update_time}"
            render_status_box("宏观 / 新闻更新时间", combined_time, "normal")
        with s3:
            render_status_box("系统状态", status_note, infer_status_level(status_note))

        st.markdown("---")

        base_text = safe_text(row.get("base_explanation"), "暂无基础判断说明")
        news_text = safe_text(row.get("news_explanation"), "本轮未触发明确新闻修正规则")

        left, right = st.columns(2)

        with left:
            render_section_title("基础判断")
            st.info(base_text)

        with right:
            render_section_title("新闻修正")
            st.warning(news_text)

        st.markdown("---")
        render_news_brief()

        with st.expander("数据来源说明 / 免责声明"):
            st.write("1. 中国宏观数据用于判定中国象限。")
            st.write("2. 美国宏观数据用于判定美国象限。")
            st.write("3. 新闻数据只用于修正，不单独决定长期基础判断。")
            st.write("4. 本系统仅作研究展示，不构成任何投资建议。")

    else:
        st.warning("当前还没有自动更新结果，请点击左侧“立即自动更新”。")

    render_footer()

elif page == "行情分析":
    render_header()
    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    render_report_list()

    st.markdown("---")
    render_section_title("临时上传预览", "仅用于当前会话预览，不会自动保存给所有访问者")

    uploaded_file = st.file_uploader(
        "上传文件进行临时预览",
        type=["txt", "md", "csv", "pdf", "png", "jpg", "jpeg", "webp", "json", "doc", "docx"]
    )

    if uploaded_file is not None:
        preview_uploaded_file(uploaded_file)

    render_footer()
