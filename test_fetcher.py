import asyncio
from app.services.news_fetcher import fetch_news
from app.services.llm_analyzer import analyze_articles

async def test():
    articles = await fetch_news("Bitcoin")
    print(f"Fetched {len(articles)} articles")
    
    result = await analyze_articles("Bitcoin", articles)
    print(result)

asyncio.run(test())