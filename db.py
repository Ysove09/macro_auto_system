import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "macro_auto.db"


def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        news_title TEXT,
        source TEXT,
        published TEXT,
        a_share_view TEXT,
        gold_view TEXT,
        crypto_view TEXT,
        commodity_view TEXT,
        explanation TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS latest_decision (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        update_time TEXT,
        china_quadrant TEXT,
        us_quadrant TEXT,
        a_share_view TEXT,
        gold_view TEXT,
        crypto_view TEXT,
        commodity_view TEXT,
        base_explanation TEXT,
        news_explanation TEXT,
        final_explanation TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_news_result(news_title, source, published, result):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*)
    FROM news_analysis
    WHERE news_title = ? AND published = ?
    """, (news_title, published))

    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("""
        INSERT INTO news_analysis
        (news_title, source, published, a_share_view, gold_view, crypto_view, commodity_view, explanation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            news_title,
            source,
            published,
            result["A股"],
            result["黄金"],
            result["加密"],
            result["商品"],
            result["说明"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()

    conn.close()


def save_latest_decision(result):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO latest_decision
    (update_time, china_quadrant, us_quadrant, a_share_view, gold_view, crypto_view, commodity_view,
     base_explanation, news_explanation, final_explanation)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        result.get("china_quadrant", ""),
        result.get("us_quadrant", ""),
        result["A股"],
        result["黄金"],
        result["加密"],
        result["商品"],
        result.get("base_explanation", ""),
        result.get("news_explanation", ""),
        result.get("说明", "")
    ))

    conn.commit()
    conn.close()


def load_news_history():
    conn = get_conn()
    df = pd.read_sql_query("""
    SELECT id, news_title, source, published, a_share_view, gold_view, crypto_view, commodity_view, explanation, created_at
    FROM news_analysis
    ORDER BY id DESC
    LIMIT 20
    """, conn)
    conn.close()
    return df


def load_latest_decision():
    conn = get_conn()
    df = pd.read_sql_query("""
    SELECT *
    FROM latest_decision
    ORDER BY id DESC
    LIMIT 1
    """, conn)
    conn.close()
    return df


def load_recent_news(limit=5):
    conn = get_conn()
    df = pd.read_sql_query(f"""
    SELECT news_title, source, published, explanation
    FROM news_analysis
    ORDER BY id DESC
    LIMIT {limit}
    """, conn)
    conn.close()
    return df
