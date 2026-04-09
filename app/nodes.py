import re
from typing import Literal

from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage

from app.llm_langchain import chat_llm
from app.tools.search import web_search
from app.logger import logger
from datetime import date

AGENT_SYSTEM_PROMPT = """\
You are an AI research assistant with access to external tools.

CURRENT DATE: {today_date}
YESTERDAY'S DATE: {yesterday_date}

Date resolution rules (follow these exactly when constructing search queries):
- "today" or "tonight"            → {today_date}
- "yesterday" or "last night"     → {yesterday_date}
- "this week"                     → week containing {today_date}
Always use the resolved calendar date (e.g. "{yesterday_date}") in your search query — never the word "yesterday" or "last night".

Your job is to provide accurate, clear, and reliable answers.

## SEARCH STRATEGY

You have a `web_search` tool for real-time data. Use it wisely:

1. **CALL THE TOOL for**:
   - News, sports scores, current prices (crypto/stocks).
   - Events occurring around {today_date} or {yesterday_date}.
   - Any fact that changes frequently.

2. **DO NOT CALL THE TOOL for**:
   - Greetings/Small talk ("Hi", "How's it going?").
   - Static facts ("What is TCP/UDP?", "Distance to the moon").
   - Logic, Math, or Code ("Write a python script", "2+2").
   - Summarizing the current conversation.

### Examples:
- User: "Hi there!" -> **No Search**. Response: "Hello! How can I help you today?"
- User: "TCP vs UDP" -> **No Search**. Response: "TCP is connection-oriented, while UDP is..."
- User: "IPL score" -> **Search**. Query: "IPL 2026 match result {today_date}"

---

## RESEARCH GUIDELINES

When researching recent events:
- **Check Dates**: Favor results with recent dates (e.g., `[2026-04-08]`). 
- **Filter Archives**: Ignore results with years like `/2020` or `/2022` in the URL if the event is current.
- **Fail Gracefully**: If no recent results are found, say "I couldn't find a reliable recent update." Do not hallucinate.

---

## RESPONSE STYLE

- **Direct & Concise**: Don't mention your training data or knowledge cutoff.
- **Citations**: For search results, use `[Name](URL)` format in a bulleted list.
- **Accuracy**: Treat search results as the source of truth for current events.

---


"""

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
CONTEXT_MANAGEMENT_PROMPT = """\
## CONTEXT ISOLATION — CURRENT QUERY IS STANDALONE

The user has switched to a new, unrelated topic.

For this query you MUST:
- Treat it as a completely fresh, independent request.
- Do NOT carry over any specific entities from earlier in the conversation
  (e.g. names, teams, scores, dates, locations, products, companies).
- Formulate any tool/search queries using ONLY what the user just asked.
- Do NOT assume that pronouns or ambiguous references in the new query refer
  to anything discussed previously.

If an entity is not explicitly stated in the current query, do not invent or
infer it from prior context.
"""

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "on",
        "at", "for", "by", "with", "about", "and", "or", "but", "if", "that",
        "this", "it", "its", "what", "who", "how", "when", "where", "me",
        "my", "i", "you", "your", "we", "our", "they", "their", "tell",
        "give", "get", "show", "latest", "recent", "new", "now",
    }
)

def _keywords(text: str) -> set[str]:
    """Return a set of meaningful lowercase words from *text*."""
    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}

def _detect_topic_shift(messages: list) -> bool:
    """
    Return True when the current (last) HumanMessage shares very few keywords
    with the immediately preceding HumanMessage.

    Strategy — Overlap coefficient on non-stopword tokens:
        overlap = |A ∩ B| / min(|A|, |B|)

      * >= 0.20  → same topic (no injection needed)
      *  < 0.20  → topic shift detected (inject CONTEXT_MANAGEMENT_PROMPT)

    Uses only human↔human comparison (not against the AI response) so that a
    short new query is never unfairly penalised against a long prior AI answer.

    Only fires when there is at least one prior human turn to compare against.
    """
    human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    if len(human_msgs) < 2:
        return False

    current_kw = _keywords(human_msgs[-1].content)
    prior_kw   = _keywords(human_msgs[-2].content)

    if not current_kw or not prior_kw:
        return False

    intersection = current_kw & prior_kw
    overlap = len(intersection) / min(len(current_kw), len(prior_kw))

    logger.debug(
        "_detect_topic_shift | overlap=%.3f | current=%s | prior=%s",
        overlap,
        sorted(current_kw)[:8],
        sorted(prior_kw)[:8],
    )
    return overlap < 0.20

_tools = [web_search]
_llm_with_tools = chat_llm.bind_tools(_tools)

DIRECT_ANSWER_PROMPT = """\
You are a helpful AI assistant. Answer the user's question directly and concisely
using your own knowledge. Do not mention search tools, web searches, or any inability
to access the internet. Just answer naturally.
"""

ROUTER_PROMPT = """\
You are a classification router. Your ONLY job is to decide if the USER QUERY requires a web search for real-time, current, or recent information (e.g., sports scores, news, weather, stock prices, or recent events).

USER QUERY: "{query}"

Respond with EXACTLY ONE WORD: "YES" if it requires search, or "NO" if it does not. DO NOT answer the query, and DO NOT explain your reasoning.

Examples:
USER QUERY: "hi there" -> NO
USER QUERY: "what is tcp vs udp" -> NO
USER QUERY: "explain what a binary search tree is" -> NO
USER QUERY: "who won the ipl game yesterday" -> YES
USER QUERY: "current price of bitcoin" -> YES
USER QUERY: "Summarize the top news from today." -> YES
"""

def agent_node(state: dict) -> dict:
    messages = list(state["messages"])

    today = date.today()
    from datetime import timedelta
    yesterday = today - timedelta(days=1)
    formatted_prompt = AGENT_SYSTEM_PROMPT.format(
        today_date=today.strftime("%B %d, %Y"),
        yesterday_date=yesterday.strftime("%B %d, %Y"),
    )

    
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=formatted_prompt)] + messages

    # ── Topic-shift detection & context isolation ────────────────────────────
    
    convo_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    if _detect_topic_shift(convo_messages):
        logger.info("agent_node | topic shift detected — injecting CONTEXT_MANAGEMENT_PROMPT")
        
        # Guarantee we inject it safely right before the LAST HumanMessage,
        # avoiding issues if the LLM is in a tool-calling loop.
        human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
        if human_indices:
            last_human_idx = human_indices[-1]
            injection = SystemMessage(content=CONTEXT_MANAGEMENT_PROMPT)
            messages.insert(last_human_idx, injection)
    # ─────────────────────────────────────────────────────────────────────────

    # ── Router: Decide if tools should be enabled ────────────────────────────
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]
    last_human_text = human_messages[-1].content if human_messages else ""

    has_tool_message = isinstance(messages[-1], ToolMessage)

    if has_tool_message:
        llm = _llm_with_tools
    else:
        router_msgs = [
            HumanMessage(content=ROUTER_PROMPT.format(query=last_human_text))
        ]
        router_decision = chat_llm.invoke(router_msgs).content.strip().upper()
        logger.info("agent_node | router=%s | query=%r", router_decision, last_human_text)

        if "YES" in router_decision:
            llm = _llm_with_tools
        else:
            # Swap in the lean, tool-free system prompt so the model
            # doesn't narrate search workflows for simple questions.
            messages = [
                SystemMessage(content=DIRECT_ANSWER_PROMPT)
            ] + [m for m in messages if not isinstance(m, SystemMessage)]
            llm = chat_llm
    # ─────────────────────────────────────────────────────────────────────────

    logger.info("agent_node | invoking LLM | message_count=%d", len(messages))
    response: AIMessage = llm.invoke(messages)
    logger.info(
        "agent_node | tool_calls=%d",
        len(response.tool_calls) if getattr(response, "tool_calls", None) else 0,
    )
    return {"messages": [response]}

def should_continue(state: dict) -> Literal["tools", "__end__"]:
    last_message: AIMessage = state["messages"][-1]
    if last_message.tool_calls:
        logger.debug("should_continue | routing to tools")
        return "tools"
    logger.debug("should_continue | routing to END")
    return "__end__"
