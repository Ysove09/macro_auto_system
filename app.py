import os
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

from db import init_db, load_latest_decision, load_recent_news
from auto_update import run_auto_update, should_auto_update
from market_data import get_market_snapshot

try:
    import fitz  # pymupdf
except Exception:
    fitz = None

BJ_TZ = pytz.timezone("Asia/Shanghai")
REPORTS_DIR = "reports"


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
    if "失败" in text or "异常" in text or "沿用上次有效结果" in text:
        return "warn"
    if "错误" in text or "崩" in text:
        return "error"
    return "ok"


def parse_system_status(status_note: str):
    text = safe_text(status_note, "系统运行正常")

    if text == "系统运行正常":
        return {
            "title": "系统运行正常",
            "desc": "本轮宏观与新闻更新正常完成。",
            "level": "ok",
            "raw": ""
        }

    if "沿用上次有效结果" in text or "抓取失败" in text:
        return {
            "title": "部分数据源失败",
            "desc": "系统已自动沿用上次有效结果，当前页面仍可正常使用。",
            "level": "warn",
            "raw": text
        }

    if "错误" in text or "崩" in text:
        return {
            "title": "本轮更新失败",
            "desc": "请稍后重试，或手动点击“立即自动更新”。",
            "level": "error",
            "raw": text
        }

    return {
        "title": "系统状态待确认",
        "desc": text,
        "level": "normal",
        "raw": text
    }


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


def get_previous_decision():
    db_candidates = ["macro_decision.db", "macro_auto.db"]

    for db_path in db_candidates:
        if not os.path.exists(db_path):
            continue

        try:
            conn = sqlite3.connect(db_path)
            query = """
                SELECT *
                FROM latest_decision
                ORDER BY id DESC
                LIMIT 1 OFFSET 1
            """
            df = pd.read_sql_query(query, conn)
            conn.close()

            if not df.empty:
                return df.iloc[0]
        except Exception:
            continue

    return None


def render_change_summary(current_row):
    previous_row = get_previous_decision()

    render_section_title("本次结论变化", "与上一条有效结果对比")

    if previous_row is None:
        st.info("当前暂无可对比的上一条记录。")
        return

    assets = [
        ("A股", "a_share_view"),
        ("黄金", "gold_view"),
        ("加密", "crypto_view"),
        ("商品", "commodity_view"),
    ]

    changes = []
    for label, col in assets:
        prev_val = safe_text(previous_row.get(col), "")
        curr_val = safe_text(current_row.get(col), "")
        if prev_val != curr_val:
            changes.append((label, prev_val, curr_val))

    if not changes:
        st.success("本轮无变化，四类资产建议与上一条记录一致。")
        return

    cols = st.columns(min(4, len(changes)))
    for i, (label, prev_val, curr_val) in enumerate(changes):
        with cols[i % len(cols)]:
            st.markdown(
                f"""
                <div style="
                    background:#22324A;
                    border-radius:14px;
                    padding:16px 18px;
                    min-height:92px;
                    border:1px solid rgba(255,255,255,0.06);
                ">
                    <div style="font-size:14px;color:#c8cfda;margin-bottom:10px;">{label}</div>
                    <div style="font-size:16px;color:#9fb0c8;margin-bottom:6px;">{prev_val}</div>
                    <div style="font-size:18px;color:#ffffff;">→ {curr_val}</div>
                </div>
                """,
                unsafe_allow_html=True
            )


def is_pinned_report(file_name: str):
    return file_name.startswith("置顶_") or file_name.startswith("[置顶]")


def clean_report_title(file_name: str):
    title = Path(file_name).stem
    title = title.replace("置顶_", "", 1)
    title = title.replace("[置顶]", "", 1)
    return title.strip()


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
                "title": clean_report_title(file_name),
                "mtime": os.path.getmtime(file_path),
                "pinned": is_pinned_report(file_name),
            })

    files = sorted(files, key=lambda x: (not x["pinned"], -x["mtime"]))
    return files


def render_pdf_pages(file_path):
    if fitz is None:
        st.warning("当前环境未安装 pymupdf，暂时无法站内阅读 PDF。请先在 requirements.txt 里加入：pymupdf")
        return

    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        st.caption(f"共 {page_count} 页")

        for i in range(page_count):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            img_bytes = pix.tobytes("png")
            st.image(img_bytes, use_container_width=True)
            st.markdown(
                f"<div style='text-align:center;color:#8d98aa;font-size:12px;margin-top:-6px;margin-bottom:16px;'>第 {i+1} 页</div>",
                unsafe_allow_html=True
            )

        doc.close()
    except Exception as e:
        st.error(f"PDF 站内阅读失败：{e}")


def render_report_reader(file_name):
    file_path = os.path.join(REPORTS_DIR, file_name)

    if not os.path.exists(file_path):
        st.error("文件不存在。")
        return

    suffix = file_name.lower().split(".")[-1]
    title = clean_report_title(file_name)
    upload_time = datetime.fromtimestamp(os.path.getmtime(file_path), BJ_TZ).strftime("%Y-%m-%d %H:%M")

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("返回列表", use_container_width=True):
            st.session_state.selected_report = None
            st.rerun()
    with c2:
        st.empty()

    render_section_title(title, f"上传时间：{upload_time}")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    st.download_button(
        label=f"下载 {file_name}",
        data=file_bytes,
        file_name=file_name,
        use_container_width=True
    )

    st.markdown("---")

    if suffix == "pdf":
        render_pdf_pages(file_path)

    elif suffix in ["txt", "md", "py", "json"]:
        try:
            content = file_bytes.decode("utf-8", errors="ignore")
            st.text_area("内容", content, height=700)
        except Exception as e:
            st.error(f"读取文本失败：{e}")

    elif suffix == "csv":
        try:
            df = pd.read_csv(file_path)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"读取 CSV 失败：{e}")

    elif suffix in ["png", "jpg", "jpeg", "webp"]:
        st.image(file_bytes, use_container_width=True)

    elif suffix in ["doc", "docx"]:
        st.info("Word 文件暂不支持站内直接阅读，请下载后查看。")

    else:
        st.info("该文件类型暂不支持站内直接阅读，请下载后查看。")


def render_report_cards():
    render_section_title("行情分析", "研究文件列表")

    reports = get_repo_reports()

    if not reports:
        st.info("当前 reports/ 文件夹里还没有正式研究文件。")
        return

    if "selected_report" not in st.session_state:
        st.session_state.selected_report = None

    for report in reports:
        upload_time = datetime.fromtimestamp(report["mtime"], BJ_TZ).strftime("%Y-%m-%d %H:%M")
        title = safe_text(report["title"], "未命名文件")
        file_name = report["file_name"]
        file_path = report["file_path"]
        pinned = report["pinned"]

        badge_html = ""
        if pinned:
            badge_html = """
            <span style="
                background:#c62828;
                color:white;
                font-size:12px;
                padding:4px 10px;
                border-radius:999px;
                margin-left:10px;
                vertical-align:middle;
            ">置顶</span>
            """

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
                        {badge_html}
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
            if st.button("阅读全文", key=f"read_{file_name}", use_container_width=True):
                st.session_state.selected_report = file_name
                st.rerun()

        with c2:
            with open(file_path, "rb") as f:
                st.download_button(
                    label="下载全文",
                    data=f.read(),
                    file_name=file_name,
                    key=f"download_{file_name}",
                    use_container_width=True
                )


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
        raw_status_note = safe_text(row.get("status_note"), "系统运行正常")
        status_info = parse_system_status(raw_status_note)

        if not macro_update_time:
            macro_update_time = update_time

        if not news_update_time:
            news_update_time = update_time

        render_change_summary(row)
        st.markdown("---")

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
            system_status_text = f"{status_info['title']}\n{status_info['desc']}"
            render_status_box("系统状态", system_status_text, status_info["level"])

        if status_info["raw"]:
            with st.expander("查看详细错误信息"):
                st.code(status_info["raw"])

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

    if "selected_report" not in st.session_state:
        st.session_state.selected_report = None

    if st.session_state.selected_report:
        render_report_reader(st.session_state.selected_report)
    else:
        render_report_cards()

    render_footer()
