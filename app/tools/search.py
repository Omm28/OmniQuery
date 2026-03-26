import httpx
from app.config import (
    TAVILY_API_KEY,
    SEARCH_MAX_RESULTS,
)
from app.logger import logger


def _search_tavily(query: str) -> str:
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": SEARCH_MAX_RESULTS,
        "include_answer": True,
    }

    logger.info("Tavily search | query=%r | max_results=%d", query, SEARCH_MAX_RESULTS)
    response = httpx.post(url, json=payload, timeout=15)
    response.raise_for_status()
    data = response.json()

    parts: list[str] = []

    if data.get("answer"):
        parts.append(f"Summary: {data['answer']}")

    for i, result in enumerate(data.get("results", []), start=1):
        title   = result.get("title", "")
        snippet = result.get("content", "")
        url_    = result.get("url", "")
        parts.append(f"[{i}] {title}\n{snippet}\nSource: {url_}")

    return "\n\n".join(parts) if parts else "No results found."


def web_search(query: str) -> str:
    try:
        return _search_tavily(query)
    except httpx.HTTPStatusError as exc:
        logger.error("Search HTTP error %d: %s", exc.response.status_code, exc)
        raise RuntimeError(f"Search API returned {exc.response.status_code}") from exc
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        raise RuntimeError(f"Search failed: {exc}") from exc
