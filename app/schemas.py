from typing import Literal, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question or prompt from the user.",
        examples=["What is the latest news about AI?"],
    )
    conversation_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str = Field(..., description="The final answer to the user's query.")
    source: Literal["llm", "web_search", "moderation"] = Field(
        ...,
        description="Indicates whether the answer came from the LLM directly or from a web search.",
    )
    conversation_id: str = Field(..., description="The ID of the conversation.")


class HealthResponse(BaseModel):
    status: str = "ok"

class Conversation(BaseModel):
    conversation_id: str
    first_query: str
    last_updated: str

class Message(BaseModel):
    query: str
    answer: str
    source: str
    timestamp: str