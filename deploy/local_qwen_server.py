from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

MODEL_PATH = Path(os.getenv("QWEN_MODEL_PATH", r"C:\Users\L\Downloads\AI\Mirae_AI_Studio_Local\models\Mirae-Qwen2.5-1.5B-Instruct"))
MODEL_NAME = os.getenv("MODEL_NAME", "Mirae-Qwen2.5-1.5B-Instruct")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MAX_NEW_TOKENS = int(os.getenv("QWEN_MAX_NEW_TOKENS", "2048"))

app = FastAPI(title="Mirae Local Qwen Model", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_tokenizer = None
_model = None
_model_lock = threading.Lock()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = MODEL_NAME
    messages: list[Message] = Field(default_factory=list)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2200, ge=1, le=MAX_NEW_TOKENS)
    stream: bool = False


def authorized(authorization: str | None) -> bool:
    if not MODEL_API_KEY:
        return True
    return bool(authorization and authorization == f"Bearer {MODEL_API_KEY}")


def load_model():
    global _tokenizer, _model
    if _model is not None and _tokenizer is not None:
        return _tokenizer, _model
    with _model_lock:
        if _model is not None and _tokenizer is not None:
            return _tokenizer, _model
        if not MODEL_PATH.exists():
            raise RuntimeError(f"Qwen model path does not exist: {MODEL_PATH}")
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers is not installed. Run: pip install -r deploy/local_qwen_requirements.txt") from exc
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True, trust_remote_code=False)
        if torch.cuda.is_available():
            device = torch.device("cuda")
            dtype = torch.float16
        else:
            device = torch.device("cpu")
            dtype = torch.float32
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            local_files_only=True,
            dtype=dtype,
            trust_remote_code=False,
        ).to(device)
        _model.eval()
        return _tokenizer, _model


def make_inputs(messages: list[Message]):
    tokenizer, model = load_model()
    payload = [{"role": m.role, "content": m.content} for m in messages]
    inputs = tokenizer.apply_chat_template(
        payload,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    if hasattr(inputs, "items"):
        return {k: v.to(model.device) for k, v in inputs.items()}
    return {"input_ids": inputs.to(model.device)}


def generation_kwargs(req: ChatRequest) -> dict[str, Any]:
    temperature = max(0.05, float(req.temperature))
    kwargs: dict[str, Any] = {
        "max_new_tokens": min(req.max_tokens, MAX_NEW_TOKENS),
        "pad_token_id": 151643,
        "eos_token_id": 151645,
    }
    if temperature <= 0.05:
        kwargs["do_sample"] = False
    else:
        kwargs.update({"do_sample": True, "temperature": temperature, "top_p": 0.9})
    return kwargs


def generate_text(req: ChatRequest) -> str:
    tokenizer, model = load_model()
    inputs = make_inputs(req.messages)
    with torch.inference_mode():
        output = model.generate(**inputs, **generation_kwargs(req))
    prompt_len = inputs["input_ids"].shape[-1]
    return tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True).strip()


def sse(name: str, data: dict[str, Any]) -> str:
    import json
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_text(req: ChatRequest):
    from transformers import TextIteratorStreamer
    tokenizer, model = load_model()
    inputs = make_inputs(req.messages)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    errors: list[BaseException] = []

    def run():
        try:
            with torch.inference_mode():
                model.generate(**inputs, streamer=streamer, **generation_kwargs(req))
        except BaseException as exc:
            errors.append(exc)
            streamer.end()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    for text in streamer:
        if text:
            yield text
    thread.join(timeout=1)
    if errors:
        raise RuntimeError(str(errors[0]))


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "model_path": str(MODEL_PATH),
        "cuda": torch.cuda.is_available(),
        "loaded": _model is not None,
    }


@app.get("/v1/models")
def models(authorization: str | None = Header(default=None)):
    if not authorized(authorization):
        raise HTTPException(401, "Invalid model API key.")
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "mirae-local"}]}


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest, authorization: str | None = Header(default=None)):
    if not authorized(authorization):
        raise HTTPException(401, "Invalid model API key.")
    if not req.messages:
        raise HTTPException(400, "messages is required.")
    if req.stream:
        def body():
            import json
            created = int(time.time())
            try:
                for piece in stream_text(req):
                    yield "data: " + json.dumps({"id": "mirae-local", "object": "chat.completion.chunk", "created": created, "model": MODEL_NAME, "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}, ensure_ascii=False) + "\n\n"
                yield "data: " + json.dumps({"id": "mirae-local", "object": "chat.completion.chunk", "created": created, "model": MODEL_NAME, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                yield "data: " + json.dumps({"error": {"message": str(exc)}}, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
        return StreamingResponse(body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    reply = generate_text(req)
    return {
        "id": "mirae-local",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
    }
