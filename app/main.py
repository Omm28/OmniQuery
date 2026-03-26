
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.schemas import QueryRequest, QueryResponse, HealthResponse, Conversation, Message
from app.graph import agent_graph
from app.logger import logger
from app.middleware.profanity_filter import ProfanityFilterMiddleware
from app.database import create_table, save_conversation, get_conversations, get_messages_by_conversation
from typing import List
import uuid

_BASE_DIR    = Path(__file__).resolve().parent.parent   
_FRONTEND    = _BASE_DIR / "frontend"
_STATIC_DIR  = _FRONTEND / "static"
_INDEX_HTML  = _FRONTEND / "index.html"



app = FastAPI(
    title="Web Search Agent",
    description=(
        "A LangGraph-powered agent that decides whether to answer a query "
        "from its own knowledge or search the web for up-to-date information."
    ),
    version="1.0.0",
    docs_url="/docs",       
    redoc_url="/redoc",     
)

app.add_middleware(ProfanityFilterMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    logger.info("Static files mounted from %s", _STATIC_DIR)


@app.on_event("startup")
def startup_event():
    create_table()


@app.get("/", tags=["Frontend"])
async def root():
    if _INDEX_HTML.exists():
        return FileResponse(str(_INDEX_HTML))
    return {"status": "ok", "message": "Web Search Agent API is running. See /docs for API documentation."}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(status="ok")

@app.get("/history", response_model=List[Conversation], tags=["History"])
async def history(limit: int = 10):
    try:
        data = get_conversations(limit)
        return data
    except Exception as exc:
        logger.error("Failed to fetch history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@app.get("/history/{conversation_id}", response_model=List[Message], tags=["History"])
async def get_conversation(conversation_id: str):
    try:
        data = get_messages_by_conversation(conversation_id)
        if not data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return data
    except Exception as exc:
        logger.error("Failed to fetch conversation: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")

@app.post("/ask", response_model=QueryResponse, tags=["Agent"])
async def ask(request: QueryRequest) -> QueryResponse:
    query = request.query
    logger.info("POST /ask | query=%r", query)
    conversation_id = request.conversation_id or str(uuid.uuid4())
    try:
        final_state: dict = agent_graph.invoke({"query": query})
    except Exception as exc:
        logger.error("Graph execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    answer   = final_state.get("answer", "I could not generate an answer.")
    decision = final_state.get("decision", "SEARCH")

    source = final_state.get("source")

    if not source:
        source = "llm" if decision == "ANSWER" else "web_search"

    try:
        save_conversation(conversation_id, query, answer, source)
    except Exception as db_error:
        logger.error("DB save failed: %s", db_error)


    logger.info("POST /ask | source=%s | answer length=%d", source, len(answer))
    return QueryResponse(
        answer=answer,
        source=source,
        conversation_id=conversation_id
    )
