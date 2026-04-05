import requests
import streamlit as st

try:
    API_KEY = st.secrets["API_KEY"]
except Exception:
    API_KEY = "YOUR_API_KEY"


def fetch_latest_news():
    """
    用新闻 API 拉取新闻。
    云端优先读取 Streamlit secrets 里的 API_KEY。
    """

    url = "https://newsapi.org/v2/everything"

    params = {
        "q": "Federal Reserve OR China stimulus OR Bitcoin ETF OR gold safe haven OR Iran war",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "apiKey": API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        articles = data.get("articles", [])
        all_news = []

        for article in articles:
            all_news.append({
                "title": article.get("title", ""),
                "source": article.get("source", {}).get("name", "API新闻源"),
                "published": article.get("publishedAt", "")
            })

        # 去重
        unique_news = []
        seen_titles = set()

        for news in all_news:
            if news["title"] and news["title"] not in seen_titles:
                unique_news.append(news)
                seen_titles.add(news["title"])

        return unique_news

    except Exception as e:
        print("API抓取失败：", e)
        return []
