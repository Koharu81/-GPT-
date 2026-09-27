import os
import re
from typing import Any
from xml.etree import ElementTree as ET
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Mirae AI API", version="3.0.0", description="OpenAI-compatible free-to-use Mirae AI gateway")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "openai/gpt-oss-120b:groq")
if HF_MODEL.startswith("Qwen/Qwen2.5-7B-Instruct"):
    HF_MODEL = "openai/gpt-oss-120b:groq"
API_KEY = os.getenv("MIRAE_API_KEY", "")
NEWS_RSS = "https://news.google.com/rss/search"
HF_URL = "https://router.huggingface.co/v1/chat/completions"

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    history: list[Message] = Field(default_factory=list)
    personality: str = "balanced"
    instructions: str = ""
    web_search: bool = True
    temperature: float = Field(default=0.7, ge=0.2, le=1.2)
    max_tokens: int = Field(default=700, ge=64, le=1600)

class OpenAIMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str | None = None
    messages: list[OpenAIMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=700, ge=1, le=1600)
    stream: bool = False

def language_of(text: str) -> str:
    ko = len(re.findall(r"[가-힣]", text))
    ja = len(re.findall(r"[ぁ-ゖァ-ヺ]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    if ko >= ja and ko >= en:
        return "ko"
    if ja >= ko and ja >= en:
        return "ja"
    return "en"

async def web_search(query: str) -> list[dict[str, str]]:
    params = {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    headers = {"User-Agent": "Mozilla/5.0 MiraeAI/3.0"}
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        response = await client.get(NEWS_RSS, params=params, headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    results = []
    for item in root.findall(".//item")[:8]:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or ""
        description = item.findtext("description") or ""
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description).strip()
        results.append({"title": title.strip(), "url": link.strip(), "snippet": description[:500], "published": pub})
    return results

def build_system(req: ChatRequest, lang: str, sources: list[dict[str, str]]) -> str:
    language_rule = {
        "ko": "한국어로 답하세요. 일본어와 중국어를 임의로 섞지 마세요.",
        "ja": "日本語で答えてください。韓国語や中国語を勝手に混ぜないでください。",
        "en": "Answer in natural English. Do not insert Korean, Japanese, or Chinese unless requested.",
    }[lang]
    source_text = ""
    if sources:
        source_text = "\n현재 웹 검색 결과:\n" + "\n".join(
            f"- {s['title']} | {s['published']} | {s['url']} | {s['snippet']}" for s in sources
        )
    return f"""You are Mirae AI, a general-purpose generative AI assistant.
{language_rule}
The current date is 2026-09-27. When the user asks for latest, today, current, or recent information, use supplied web results and explicitly say when evidence is incomplete.
Do not claim that web search is unavailable when search results are supplied.
Generate a fresh answer from the user's actual request and conversation context. Never use a canned refusal for real-time questions.
Do not invent facts or citations. Keep the answer concise unless detail is requested.
Personality: {req.personality[:80]}
User instructions: {req.instructions[:4000] or "none"}
{source_text}"""

def require_api_key(authorization: str | None) -> None:
    if API_KEY:
        expected = f"Bearer {API_KEY}"
        if authorization != expected:
            raise HTTPException(401, "Invalid or missing API key.")

@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "model": HF_MODEL, "web_search": True, "api": "openai-compatible", "app_token_limit": "none"}

@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(authorization)
    return {"object": "list", "data": [{"id": "mirae-free", "object": "model", "owned_by": "mirae", "permission": []}]}

async def generate(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
    if not HF_TOKEN:
        raise HTTPException(503, "HF_TOKEN is not configured on the API server.")
    payload = {"model": HF_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False}
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(HF_URL, headers=headers, json=payload)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, f"Upstream model request failed: {response.text[:700]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, "The model provider returned an unexpected response.") from exc

@app.post("/chat")
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(authorization)
    lang = language_of(req.message)
    sources = []
    if req.web_search:
        try:
            sources = await web_search(req.message)
        except Exception:
            sources = []
    messages = [{"role": "system", "content": build_system(req, lang, sources)}]
    for item in req.history[-12:]:
        if item.role in {"user", "assistant"} and item.content.strip():
            messages.append({"role": item.role, "content": item.content[:5000]})
    messages.append({"role": "user", "content": req.message})
    reply = await generate(messages, req.temperature, req.max_tokens)
    return {"reply": reply, "model": HF_MODEL, "language": lang, "sources": sources}

@app.post("/v1/chat/completions")
async def openai_chat(req: OpenAIChatRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(authorization)
    if not req.messages:
        raise HTTPException(400, "messages must not be empty.")
    raw = [{"role": m.role, "content": m.content} for m in req.messages]
    last_user = next((m["content"] for m in reversed(raw) if m["role"] == "user"), "")
    lang = language_of(last_user)
    sources = []
    if last_user:
        try:
            sources = await web_search(last_user)
        except Exception:
            sources = []
    system = {"role": "system", "content": build_system(ChatRequest(message=last_user or "Hello"), lang, sources)}
    prompt_messages = [system] + [m for m in raw if m["role"] in {"system", "user", "assistant"}]
    reply = await generate(prompt_messages, req.temperature, req.max_tokens)
    return {
        "id": "mirae-chat",
        "object": "chat.completion",
        "created": 0,
        "model": req.model or "mirae-free",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "sources": sources,
    }

@app.get("/docs-info")
async def docs_info() -> dict[str, Any]:
    return {
        "name": "Mirae AI API",
        "version": "3.0.0",
        "base": "/",
        "endpoints": ["/health", "/v1/models", "/v1/chat/completions", "/chat"],
        "app_token_limit": "none",
        "note": "No application-level usage cap is enforced. The upstream inference provider can still impose quotas, rate limits, or availability limits.",
    }
