import os
import time
from collections import defaultdict, deque

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

app = FastAPI(title="UmeshAI API", version="1.0.0")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"

# Basic per-IP rate limit: up to 20 requests per rolling minute.
_requests_by_ip = defaultdict(deque)
RATE_LIMIT = 20
WINDOW_SECONDS = 60


class ChatRequest(BaseModel):
    messages: list[dict] = Field(min_length=1, max_length=60)


@app.get("/")
def health():
    return {"status": "ok", "service": "UmeshAI API"}


@app.post("/chat")
def chat(payload: ChatRequest, request: Request):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Server API key is not configured.")

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = _requests_by_ip[client_ip]

    while recent and now - recent[0] > WINDOW_SECONDS:
        recent.popleft()

    if len(recent) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait.")

    recent.append(now)

    # Accept only standard chat roles and text content.
    safe_messages = []
    for item in payload.messages:
        role = item.get("role")
        content = item.get("content")
        if role not in ("system", "user", "assistant") or not isinstance(content, str):
            raise HTTPException(status_code=400, detail="Invalid chat message.")
        safe_messages.append({"role": role, "content": content[:12000]})

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": safe_messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            timeout=55,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="AI provider connection failed.")

    if response.status_code != 200:
        # Do not forward provider response text, which can contain internal details.
        raise HTTPException(status_code=502, detail="AI provider returned an error.")

    try:
        answer = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Invalid AI provider response.")

    return {"answer": answer}
