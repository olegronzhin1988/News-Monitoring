# news_fetcher.py, service function 

import httpx
from app.core.config import settings as stngs

# Exception for news api errors
class NewsAPIError(Exception):
    pass

async def fetch_news(topic:str,
                     language:str="en") -> list[dict]:
    
    async with httpx.AsyncClient() as client:
        url="https://newsapi.org/v2/everything"
        params ={
            "q":topic,
            "language":language,
            "apiKey":stngs.NEWS_API_KEY,
            "sortBy":"publishedAt"}
        
        response = await client.get(url, params=params)
# Exceptions, used isntead of returned empty list.
# This way we can separate errors from no news on topic cases.
# Exception - Wrong/old key
    if response.status_code == 401:
        raise NewsAPIError(f"News API key error: {response.status_code}: {response.text}")

# Exception - rate limit error    
    if response.status_code == 429:
        raise NewsAPIError(f"News API rate limit error: {response.status_code}: {response.text}")

# Other exception
    if response.status_code != 200:
        raise NewsAPIError(f"News API returned:{response.status_code}:{response.text}")

# Extracting data and checking status
    data = response.json()
    if data.get("status") !="ok":
        raise NewsAPIError(f"News API error: {data.get('message', 'unknown error')}")

# Extracting raw articles
    articles_raw = data.get("articles", [])

# Formatting raw articles into articles with required fields
    articles = [
        {
        "title": article.get("title", ""),
        "description": article.get("description", ""),
        "url": article.get("url", ""),
        "published_at": article.get("publishedAt", ""),
        "source": article.get("source",{}).get("name", "Unknown"),
        }
        for article in articles_raw

# Filtering articles with empty or "[Removed]" titles
        if article.get("title") and article.get("title") != "[Removed]"
    ]
    return articles