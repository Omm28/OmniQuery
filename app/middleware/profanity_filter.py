import json
import re
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse
from app.middleware.wordlist import BANNED_WORDS


def contains_profanity(text: str) -> bool:
    words = re.split(r"\W+", text.lower())
    return any(w in BANNED_WORDS for w in words)


class ProfanityFilterMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        body = b""

        async def receive_wrapper():
            nonlocal body
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
            return message

        more_body = True
        while more_body:
            message = await receive_wrapper()
            more_body = message.get("more_body", False)

        try:
            data = json.loads(body.decode())
            query = data.get("query", "")
        except:
            query = ""

        if contains_profanity(query):
            response =JSONResponse(
                {
                    "answer": "Hey, let’s keep it clean 😅 Try rephrasing your question.",
                    "source": "moderation"
                    }
            )
            
            await response(scope, receive, send)
            return  # 🔥 THIS MUST STOP EXECUTION

        # ✅ CLEAN → pass request forward
        async def receive_again():
            return {
                "type": "http.request",
                "body": body,
                "more_body": False
            }

        await self.app(scope, receive_again, send)