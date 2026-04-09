
from langchain_ollama import ChatOllama

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.logger import logger

logger.info("Initialising ChatOllama | base_url=%s | model=%s", OLLAMA_BASE_URL, OLLAMA_MODEL)

chat_llm = ChatOllama(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    temperature=0.2,
)
