import httpx
from langchain_core.tools import tool

from app.config import (
    TAVILY_API_KEY,
    SEARCH_MAX_RESULTS,
    SEARCH_RECENCY_DAYS,
)
from app.logger import logger

_RECENCY_KEYWORDS = frozenset({
    "today", "yesterday", "tonight", "last night", "this morning",
    "latest", "recent", "now", "live", "score", "result", "match",
    "news", "update", "current", "breaking", "just", "week",
    "ipl", "nba", "nfl", "premier league", "cricket", "football",
    "stock", "price", "weather",
})

def _is_time_sensitive(query: str) -> bool:
    lowered = query.lower()
    return any(kw in lowered for kw in _RECENCY_KEYWORDS)

def _search_tavily(query: str) -> str:
    url = "https://api.tavily.com/search"
    time_sensitive = _is_time_sensitive(query)
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced" if time_sensitive else "basic",
        "max_results": SEARCH_MAX_RESULTS,
        "include_answer": True,
    }
    if time_sensitive:
        payload["days"] = SEARCH_RECENCY_DAYS

    logger.info(
        "Tavily search | query=%r | max_results=%d | time_sensitive=%s | days=%s",
        query, SEARCH_MAX_RESULTS, time_sensitive,
        SEARCH_RECENCY_DAYS if time_sensitive else "N/A",
    )
    response = httpx.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()

    parts: list[str] = []

    if data.get("answer"):
        parts.append(f"Summary: {data['answer']}")

    for i, result in enumerate(data.get("results", []), start=1):
        title       = result.get("title", "")
        snippet     = result.get("content", "")
        url_        = result.get("url", "")
        published   = result.get("published_date", "")
        date_tag    = f" [{published}]" if published else ""
        parts.append(f"[{i}] {title}{date_tag}\n{snippet}\nSource: {url_}")

    return "\n\n".join(parts) if parts else "No results found."

@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information on any topic.

    Use this tool when the query asks about recent or real-time information
    (news, prices, weather, sports scores, current events, or anything where
    being out-of-date would give a wrong answer).

    For time-sensitive queries (sports results, news, live events), this tool
    automatically restricts results to recent content only.

    Args:
        query: The search query string.

    Returns:
        A formatted string of search results with titles, snippets, source URLs,
        and publication dates where available.
    """
    try:
        return _search_tavily(query)
    except httpx.HTTPStatusError as exc:
        logger.error("Search HTTP error %d: %s", exc.response.status_code, exc)
        raise RuntimeError(f"Search API returned {exc.response.status_code}") from exc
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        raise RuntimeError(f"Search failed: {exc}") from exc
