# test_fetch.py, to test fetch_news function and NEWS_API_KEY

import asyncio
from app.services.news_fetcher import fetch_news

async def test():
    articles = await fetch_news("Bitcoin")
    print(f"Найдено статей: {len(articles)}")
    for a in articles[:3]:
        print(a["title"], "-", a["source"])

asyncio.run(test())