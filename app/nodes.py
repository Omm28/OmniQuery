from app.state import GraphState
from app.llm import call_llm
from app.tools.search import web_search
from app.logger import logger

# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────────────────

DECISION_SYSTEM_PROMPT = """\
You are a routing assistant for a question-answering system.
Your ONLY job is to decide whether the user's query requires a web search or can be answered from your existing knowledge.

Reply with EXACTLY ONE WORD — no punctuation, no explanation:
  ANSWER   → if the query is about general knowledge, definitions, reasoning, math, coding, historical facts, or a conversation (ex: whats up bro, how are you doing today) that are unlikely to have changed.
  SEARCH   → if the query asks about:
               • Recent or real-time information (news, prices, weather, sports scores)
               • Specific URLs, live data, or unknown entities
               • Anything where being out-of-date would give a wrong answer
               • If the user asks you for current information on something

Think carefully. If you are unsure whether your knowledge is current, output SEARCH.
Output only ANSWER or SEARCH.
"""

ANSWER_SYSTEM_PROMPT = """\
You are a helpful, knowledgeable assistant.
Answer the user's question clearly, concisely, and accurately using your internal knowledge.
If you do not know, say so honestly — do not fabricate information.
"""

SYNTHESIZE_SYSTEM_PROMPT = """\
You are a research assistant.
You have been given a user question and a set of web search results.
Your task is to synthesise a clear, accurate, and helpful answer STRICTLY based on the provided search results.
When citing a source, always include the full URL from the "Source:" field as a markdown hyperlink, e.g. [Site Name](https://example.com).
Never use bare numbered references like [1] or [2] without an accompanying hyperlink.
Do not add information that is not present in the search results.
"""

def decide_node(state: GraphState) -> dict:
    
    query = state["query"]
    logger.info("decide_node | query=%r", query)

    raw_decision = call_llm(
        system_prompt=DECISION_SYSTEM_PROMPT,
        user_message=query,
        temperature=0.0,
        max_tokens=10,
    )

    
    decision = raw_decision.strip().upper().split()[0] if raw_decision.strip() else "SEARCH"

    
    if decision not in ("ANSWER", "SEARCH"):
        logger.warning("Unexpected decision %r — defaulting to SEARCH", decision)
        decision = "SEARCH"

    logger.info("decide_node | decision=%s", decision)
    return {"decision": decision}


def answer_node(state: GraphState) -> dict:
  
    query = state["query"]
    logger.info("answer_node | query=%r", query)

    answer = call_llm(
        system_prompt=ANSWER_SYSTEM_PROMPT,
        user_message=query,
        temperature=0.3,
        max_tokens=1024,
    )

    logger.info("answer_node | answer length=%d chars", len(answer))
    return {"answer": answer}


def search_node(state: GraphState) -> dict:
    
    query = state["query"]
    logger.info("search_node | query=%r", query)

    try:
        results = web_search(query)
        logger.info("search_node | results length=%d chars", len(results))
    except RuntimeError as exc:
       
        logger.error("search_node | search failed: %s", exc)
        results = f"Web search failed: {exc}. Please rely on general knowledge."

    return {"search_results": results}


def synthesize_node(state: GraphState) -> dict:
    
    query          = state["query"]
    search_results = state.get("search_results", "No search results available.")
    logger.info("synthesize_node | query=%r", query)

    user_message = (
        f"User question: {query}\n\n"
        f"Search results:\n{search_results}"
    )

    answer = call_llm(
        system_prompt=SYNTHESIZE_SYSTEM_PROMPT,
        user_message=user_message,
        temperature=0.2,
        max_tokens=1024,
    )

    logger.info("synthesize_node | answer length=%d chars", len(answer))
    return {"answer": answer}
