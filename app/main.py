
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.schemas import QueryRequest, QueryResponse, HealthResponse, Conversation, Message
from app.graph import agent_graph
from app.logger import logger
from app.middleware.profanity_filter import ProfanityFilterMiddleware
from app.database import create_table, create_users_table, save_conversation, get_conversations, get_messages_by_conversation
from app.auth.routes import router as auth_router
from app.auth.dependencies import get_current_user
from app.auth.jwt import decode_access_token
from app.auth.config import SESSION_SECRET_KEY
from app.anonymizer import anonymize, deanonymize
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

app.add_middleware(ProfanityFilterMiddleware)

app.include_router(auth_router)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    logger.info("Static files mounted from %s", _STATIC_DIR)

@app.on_event("startup")
def startup_event():
    create_table()
    create_users_table()  

_LOGIN_HTML = _FRONTEND / "login.html"

_AUTH_COOKIE = "oq_token"

def _is_authenticated(request: Request) -> bool:
    """Quick cookie check — no DB hit, just verifies the JWT signature."""
    token = request.cookies.get(_AUTH_COOKIE)
    if not token:
        return False
    try:
        decode_access_token(token)
        return True
    except Exception:
        return False

@app.get("/", tags=["Frontend"])
async def root(request: Request):
    """Serve the main app. Unauthenticated users are redirected to /login."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    if _INDEX_HTML.exists():
        return FileResponse(str(_INDEX_HTML))
    return {"status": "ok", "message": "Authenticated. See /docs."}

@app.get("/login", tags=["Frontend"])
async def login_page(request: Request):
    """Serve the login page. Authenticated users are bounced back to /."""
    if _is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    if _LOGIN_HTML.exists():
        return FileResponse(str(_LOGIN_HTML))
    
    return RedirectResponse(url="/auth/login", status_code=302)

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(status="ok")

@app.get("/history", response_model=List[Conversation], tags=["History"])
async def history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = get_conversations(limit, user_id=current_user["id"])
        return data
    except Exception as exc:
        logger.error("Failed to fetch history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@app.get("/history/{conversation_id}", response_model=List[Message], tags=["History"])
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = get_messages_by_conversation(conversation_id, user_id=current_user["id"])
        if not data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch conversation: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")

@app.delete("/history/{conversation_id}", tags=["History"])
async def delete_conversation_route(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        from app.database import delete_conversation
        deleted = delete_conversation(conversation_id, user_id=current_user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found or not owned by user")
        return {"status": "ok", "message": "Conversation deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete conversation: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

@app.post("/ask", response_model=QueryResponse, tags=["Agent"])
async def ask(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
) -> QueryResponse:
    original_query = request.query
    logger.info("POST /ask | query=%r", original_query)
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # ── Anonymize PII before the query reaches the LLM ───────────────────────
    anonymized_query, pii_mapping = anonymize(original_query)
    if pii_mapping:
        logger.info(
            "POST /ask | PII anonymized | %d entities replaced",
            len(pii_mapping),
        )

    # ── Context History (cap to 5 previous exchanges) ────────────────────────
    history_messages = []
    if request.conversation_id:
        try:
            prior_messages = get_messages_by_conversation(
                request.conversation_id, user_id=current_user["id"]
            )
            
            for msg in prior_messages[-5:]:
                history_messages.append(HumanMessage(content=msg["query"]))
                history_messages.append(AIMessage(content=msg["answer"]))
            
            logger.info("POST /ask | loaded %d prior exchanges", len(history_messages) // 2)
        except Exception as e:
            logger.error("Failed to load conversation history: %s", e)

    all_messages = history_messages + [HumanMessage(content=anonymized_query)]

    try:
        final_state: dict = agent_graph.invoke(
            {"messages": all_messages}
        )
    except Exception as exc:
        logger.error("Graph execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    messages = final_state.get("messages", [])
    answer = messages[-1].content if messages else "I could not generate an answer."

    # ── Restore any PII placeholders in the agent's response ─────────────────
    answer = deanonymize(answer, pii_mapping)

    
    used_search = any(isinstance(m, ToolMessage) for m in messages)
    source = "web_search" if used_search else "llm"

    
    try:
        save_conversation(
            conversation_id, original_query, answer, source, user_id=current_user["id"]
        )
    except Exception as db_error:
        logger.error("DB save failed: %s", db_error)

    logger.info("POST /ask | source=%s | answer length=%d", source, len(answer))
    return QueryResponse(
        answer=answer,
        source=source,
        conversation_id=conversation_id
    )
