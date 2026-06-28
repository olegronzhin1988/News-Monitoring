# llm_analyzer.py, includes service functions for ai agents

import re
import json
import httpx
from groq import AsyncGroq
from app.core.config import settings as stngs

# Prompt for AI agent
PROMPT_ROLE="You`re an expert news analyst."
PROMPT_TOPICS="Your topic is {topic}."
PROMPT_DATA_INPUT="Your articles are {articles_json}."
PROMPT_TASK="You should provide sentiment score(-1.0 to 1.0) and sentiment_label(positive/neutral/negative) to the topic, regarding articles, summary and key events on the topic in articles." 
PROMPT_OUTPUT="You should provide your answer in json without markdown, like this:"
PROMPT_EXAMPLE_OUTPUT="""
{{
    "sentiment_score": -1.0 to 1.0,
    "sentiment_label": "positive" / "neutral" / "negative",
    "summary": "Short summary on the topic",
    "key_events": ["event 1", "event 2", ...]
}}
"""
ANALYSIS_PROMPT = f"{PROMPT_ROLE}\n{PROMPT_TOPICS}\n{PROMPT_DATA_INPUT}\n{PROMPT_TASK}\n{PROMPT_OUTPUT}\n{PROMPT_EXAMPLE_OUTPUT}"

# Service Exceprion class for LLM
class LLMAnalysisError(Exception):
    pass

# service function to add articles into ai agent promt
def _build_prompt(topic:str, articles:list[dict]) ->str:
    articles=articles[:15]
    articles_json = [
        {
            "title": article.get("title", ""),
            "description":(article.get("description") or""),
        }
        for article in articles
    ]
    return ANALYSIS_PROMPT.format(topic=topic, articles_json=articles_json)

# Service function to clean ai agent response and parse it to dict
def _parse_llm_response(raw_text:str)->dict:
    # Remowe markdown code blocks if present
    cleaned=re.sub(r"```json|```","",raw_text).strip()

    # Finding first JSON-object limits (if recieved more)
    start = cleaned.find("{")
    end = cleaned.find("}")+1

    # Exception: no JSON objects found
    if start ==-1 or end ==0:
        raise LLMAnalysisError(f"No JSON object found in LLM response: {raw_text}")

    # Cutting cleaned res to 1st JSON object
    json_str=cleaned[start:end]
    return json.loads(json_str)

# Service function to call groq
async def _call_groq(prompt:str) ->str:
    # Create groq client
    async with AsyncGroq(api_key=stngs.GROQ_API_KEY) as client:

    # Calling groq api with prompt
        response = await client.chat.completions.create(model=stngs.GROQ_MODEL, 
                                                        messages=[{"role":"user", "content":prompt}],
                                                        max_tokens=2048,
                                                        temperature=0.2)
        return response.choices[0].message.content 

# Service function to call openrouter
async def _call_openrouter(prompt:str)->str:
    # Creating openrouter request
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {stngs.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    body= {
        "model": stngs.OPENROUTER_MODEL,
        "messages": [{"role":"user", "content":prompt}]
    }

# Sending request
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers,
                                     json=body)
    data = response.json()
    return data["choices"][0]["message"]["content"]

# Main service funnction to orchestrate process
async def analyze_articles(topic:str, articles:list[dict])->dict:
    # Building prompt for llm 
    prompt = _build_prompt(topic=topic, articles=articles)
    call_provider={"groq":_call_groq, "openrouter":_call_openrouter}

    # Trying to get data from some of LLMs
    try:
        provider = "groq"
        raw = await call_provider[provider](prompt)
    except Exception:
        try:
            provider = "openrouter"
            raw = await call_provider[provider](prompt)
        except Exception as e:
            raise LLMAnalysisError(f"Both providers failed: {e}")
    
    parsed= _parse_llm_response(raw)
    result=dict(parsed)
    result["ai_provider_used"] = provider
    result["raw_response"] = parsed
    return result
