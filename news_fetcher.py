import requests


API_KEY = "YOUR_API_KEY"


def fetch_latest_news():
    """
    用新闻 API 拉取新闻。
    这里先写成通用结构，你只需要把 API_KEY 换成真实 key。
    """

    url = "https://newsapi.org/v2/everything"

    params = {
        "q": "Federal Reserve OR China stimulus OR Bitcoin ETF OR gold safe haven",
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

        return [
            {
                "title": "美联储表态偏鹰，降息预期推迟",
                "source": "API失败回退新闻源",
                "published": "2026-04-04 22:00:00"
            },
            {
                "title": "中国出台地产刺激政策，市场预期改善",
                "source": "API失败回退新闻源",
                "published": "2026-04-04 22:05:00"
            },
            {
                "title": "比特币ETF持续净流入，市场情绪回暖",
                "source": "API失败回退新闻源",
                "published": "2026-04-04 22:10:00"
            }
        ]