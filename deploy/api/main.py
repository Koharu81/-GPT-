import os
import re
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Mirae AI API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct:fastest")
BING_URL = "https://www.bing.com/search"

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
    params = {"q": query, "setlang": "ko-KR", "cc": "kr", "count": "5"}
    headers = {"User-Agent": "Mozilla/5.0 MiraeAI/2.0"}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        response = await client.get(BING_URL, params=params, headers=headers)
        response.raise_for_status()
        html = response.text
    results = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, re.S):
        match = re.search(r'<h2><a href="([^"]+)">(.*?)</a>', block, re.S)
        if not match:
            continue
        url, title = match.groups()
        title = re.sub(r"<.*?>", "", title)
        snippet = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        text = re.sub(r"<.*?>", "", snippet.group(1)) if snippet else ""
        results.append({"title": title.strip(), "url": url.strip(), "snippet": re.sub(r"\s+", " ", text).strip()})
        if len(results) >= 5:
            break
    return results

def build_system(req: ChatRequest, lang: str, sources: list[dict[str, str]]) -> str:
    language_rule = {
        "ko": "한국어로 답하세요. 일본어 한자나 중국어 표현을 임의로 섞지 마세요.",
        "ja": "日本語で答えてください。韓国語や中国語を勝手に混ぜないでください。",
        "en": "Answer in natural English. Do not insert Korean, Japanese, or Chinese unless requested.",
    }[lang]
    source_text = ""
    if sources:
        source_text = "\n웹 검색 결과:\n" + "\n".join(
            f"- {s['title']} | {s['url']} | {s['snippet']}" for s in sources
        )
    personality = req.personality[:80]
    instructions = req.instructions[:4000]
    return f"""You are Mirae AI, a general-purpose generative assistant.
{language_rule}
Generate a fresh answer from the current request and conversation context. Never copy a canned greeting just because the input is short.
Stay tightly relevant to the user's actual request. Do not invent facts when evidence is missing.
Personality: {personality}
User instructions: {instructions or "none"}
If web results are supplied, use them as current context and distinguish sourced facts from your own reasoning.
{source_text}"""

@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "model": HF_MODEL, "web_search": True}

@app.post("/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    if not HF_TOKEN:
        raise HTTPException(503, "HF_TOKEN is not configured on the API server.")
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
    payload = {
        "model": HF_MODEL,
        "messages": messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://router.huggingface.co/v1/chat/completions",
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(response.status_code, f"Hugging Face request failed: {response.text[:500]}")
    data = response.json()
    reply = data["choices"][0]["message"]["content"].strip()
    return {"reply": reply, "model": HF_MODEL, "language": lang, "sources": sources}
