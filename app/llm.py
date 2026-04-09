
import time
import requests

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.logger import logger

OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
REQUEST_TIMEOUT = 60  

def generateResponse(prompt: str) -> str:

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    logger.debug("Ollama request | url=%s | model=%s | prompt_len=%d",
                 OLLAMA_GENERATE_URL, OLLAMA_MODEL, len(prompt))

    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running (`ollama serve`)."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"Ollama request timed out after {REQUEST_TIMEOUT}s."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error: {exc}") from exc

    data = resp.json()
    text = data.get("response", "")
    logger.debug("Ollama response | response_len=%d", len(text))
    return text.strip()

def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    retries: int = 3,
) -> str:

    prompt = f"{system_prompt}\n\n{user_message}" if system_prompt else user_message

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            logger.debug(
                "LLM call | model=%s | attempt=%d/%d",
                OLLAMA_MODEL, attempt, retries,
            )
            return generateResponse(prompt)

        except RuntimeError as exc:
            last_error = exc
            if attempt < retries:
                wait = 2 ** attempt  
                logger.warning(
                    "LLM attempt %d/%d failed: %s. Retrying in %.0fs…",
                    attempt, retries, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error("LLM attempt %d/%d failed: %s", attempt, retries, exc)

    raise RuntimeError(f"LLM failed after {retries} retries: {last_error}") from last_error
