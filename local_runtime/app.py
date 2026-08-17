"""Mirae AI Studio local runtime. No external inference API is used."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
DB_PATH = DATA_DIR / "mirae.db"
DATA_DIR.mkdir(exist_ok=True)
ARTIFACT_DIR.mkdir(exist_ok=True)
app = FastAPI(title="Mirae AI Studio Local", version="0.2.0")
sessions: dict[str, int] = {}
job: dict[str, object] = {"status": "idle", "progress": 0, "current_step": 0, "steps": 0, "loss": None, "note": "학습을 시작하면 진행 상황이 여기에 표시됩니다."}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pairs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'mixed', source TEXT NOT NULL DEFAULT 'manual', status TEXT NOT NULL DEFAULT 'approved', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, prefix TEXT NOT NULL, key_hash TEXT UNIQUE NOT NULL, state TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, last_used_at TEXT, revoked_at TEXT);
        CREATE TABLE IF NOT EXISTS usage_logs (id INTEGER PRIMARY KEY, api_key_id INTEGER NOT NULL, user_id INTEGER NOT NULL, endpoint TEXT NOT NULL, status_code INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS training_runs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, status TEXT NOT NULL, requested_steps INTEGER NOT NULL, current_step INTEGER NOT NULL DEFAULT 0, progress INTEGER NOT NULL DEFAULT 0, loss REAL, note TEXT, created_at TEXT NOT NULL, completed_at TEXT);
        CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT, model_version TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_versions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, version TEXT NOT NULL, label TEXT NOT NULL, dataset_records INTEGER NOT NULL, requested_steps INTEGER NOT NULL, parameter_count INTEGER NOT NULL, train_loss REAL, validation_loss REAL, artifact_path TEXT, is_active INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        """)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def setup_required() -> bool:
    with db() as connection:
        return connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"] == 0


def current_user(request: Request) -> sqlite3.Row:
    token = request.cookies.get("mirae_session")
    user_id = sessions.get(token or "")
    if not user_id:
        raise HTTPException(401, "로그인이 필요합니다.")
    with db() as connection:
        user = connection.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(401, "세션이 만료되었습니다.")
    return user


def approved_pairs(user_id: int) -> list[sqlite3.Row]:
    with db() as connection:
        return connection.execute("SELECT prompt, response FROM pairs WHERE user_id = ? AND status = 'approved'", (user_id,)).fetchall()


def active_model_version(user_id: int) -> str:
    with db() as connection:
        row = connection.execute("SELECT version FROM model_versions WHERE user_id=? ORDER BY is_active DESC, id DESC LIMIT 1", (user_id,)).fetchone()
    return row["version"] if row else "starter-v1"


def record_chat_history(user_id: int, message: str, reply: str, mode: str) -> None:
    version = active_model_version(user_id)
    with db() as connection:
        connection.execute("INSERT INTO chat_history (user_id, role, content, model_version, created_at) VALUES (?, 'user', ?, ?, ?)", (user_id, message, version, now()))
        connection.execute("INSERT INTO chat_history (user_id, role, content, mode, model_version, created_at) VALUES (?, 'assistant', ?, ?, ?, ?)", (user_id, reply, mode, version, now()))


def seed_bundled_versions(user_id: int) -> None:
    versions_root = ARTIFACT_DIR / "versions"
    if not versions_root.exists(): return
    with db() as connection:
        if connection.execute("SELECT COUNT(*) AS count FROM model_versions WHERE user_id=?", (user_id,)).fetchone()["count"]: return
        for index, folder in enumerate(sorted(path for path in versions_root.iterdir() if path.is_dir()), start=1):
            metadata_path = folder / "last_run.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            history = metadata.get("history", [])
            last = history[-1] if history else {}
            connection.execute("INSERT INTO model_versions (user_id, version, label, dataset_records, requested_steps, parameter_count, train_loss, validation_loss, artifact_path, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, folder.name, f"번들 직접 학습 모델 {folder.name}", 30 if folder.name.endswith("v1") else 105, int(metadata.get("training_arguments", {}).get("steps", 0)), int(metadata.get("parameter_count", metadata.get("parameters", 0))), last.get("train_loss"), last.get("validation_loss"), str(folder / "checkpoints" / "latest.pt"), 1 if index == len(list(versions_root.iterdir())) else 0, now()))


def tokens(text: str) -> set[str]:
    return {part.lower() for part in re.findall(r"[A-Za-z0-9가-힣]{2,}", text)}


def fallback_reply(message: str, pairs: list[sqlite3.Row]) -> str:
    query = tokens(message)
    best, score = None, 0
    for pair in pairs:
        value = len(query & tokens(pair["prompt"]))
        if value > score:
            best, score = pair, value
    if best and score:
        return best["response"]
    return "아직은 당신이 직접 만든 대화 쌍에서 배우는 작은 AI예요. 비슷한 장면을 학습 데이터에 더해 주시면 더 자연스러운 답을 드릴 수 있어요.\n\nI am still learning from the conversation pairs you create. Add a related example and train me again."


def model_reply(message: str, pairs: list[sqlite3.Row], artifact_dir: Optional[Path] = None) -> tuple[str, str]:
    # The first compact model is still experimental. When the user's question
    # matches approved teaching data, return that verified local answer first.
    if any(tokens(message) & tokens(pair["prompt"]) for pair in pairs):
        return fallback_reply(message, pairs), "local-data"
    artifact_root = artifact_dir or ARTIFACT_DIR
    checkpoint = artifact_root / "checkpoints" / "latest.pt"
    tokenizer_dir = artifact_root / "tokenizer"
    if not checkpoint.exists() or not tokenizer_dir.exists():
        return fallback_reply(message, pairs), "local-data"
    try:
        import torch
        from model.config import ModelConfig
        from model.model import DecoderOnlyTransformer
        from model.tokenizer import CharacterTokenizer
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        payload = torch.load(checkpoint, map_location=device, weights_only=False)
        tokenizer = CharacterTokenizer.load(tokenizer_dir)
        model = DecoderOnlyTransformer(ModelConfig(**payload["model_config"])).to(device)
        model.load_state_dict(payload["model_state"]); model.eval()
        prefix = f"사용자: {message}\n어시스턴트: "
        inputs = torch.tensor([tokenizer.encode(prefix, add_bos=True)], dtype=torch.long, device=device)
        output = model.generate(inputs, max_new_tokens=120, temperature=0.55, top_k=12, eos_id=tokenizer.eos_id)[0].tolist()
        answer = tokenizer.decode(output[len(inputs[0]):]).strip()
        if len(answer) >= 3 and "어시스턴트:" not in answer and "사용자:" not in answer:
            return answer, "trained-small-model"
    except Exception:
        pass
    return fallback_reply(message, pairs), "local-data"


class SetupInput(BaseModel): username: str = Field(min_length=2, max_length=40); password: str = Field(min_length=8, max_length=200)
class LoginInput(SetupInput): pass
class PairInput(BaseModel): prompt: str = Field(min_length=1, max_length=8000); response: str = Field(min_length=1, max_length=8000); language: str = "mixed"; status: str = "approved"
class ChatInput(BaseModel): message: str = Field(min_length=1, max_length=4000)
class KeyInput(BaseModel): name: str = Field(min_length=2, max_length=80)
class TrainInput(BaseModel): steps: int = Field(default=1000, ge=100, le=20000)
class ModelPromptInput(BaseModel): left: int; right: int; message: str = Field(min_length=1, max_length=4000)


@app.get("/api/me")
def me(request: Request):
    if setup_required(): return {"setupRequired": True, "user": None}
    try:
        user = current_user(request); return {"setupRequired": False, "user": dict(user)}
    except HTTPException:
        return {"setupRequired": False, "user": None}


@app.post("/api/setup")
def setup(input: SetupInput, response: Response):
    if not setup_required(): raise HTTPException(409, "초기 관리자는 이미 설정되었습니다.")
    salt = secrets.token_hex(16)
    with db() as connection:
        cursor = connection.execute("INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, 'admin', ?)", (input.username, hash_password(input.password, salt), salt, now()))
        user_id = cursor.lastrowid
    seed_bundled_versions(user_id)
    token = secrets.token_urlsafe(32); sessions[token] = user_id; response.set_cookie("mirae_session", token, httponly=True, samesite="lax")
    return {"ok": True}


@app.post("/api/login")
def login(input: LoginInput, response: Response):
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE username = ?", (input.username,)).fetchone()
    if not user or not secrets.compare_digest(user["password_hash"], hash_password(input.password, user["salt"])):
        raise HTTPException(401, "사용자 이름 또는 비밀번호가 올바르지 않습니다.")
    token = secrets.token_urlsafe(32); sessions[token] = user["id"]; response.set_cookie("mirae_session", token, httponly=True, samesite="lax")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    sessions.pop(request.cookies.get("mirae_session", ""), None); response.delete_cookie("mirae_session"); return {"ok": True}


@app.get("/api/pairs")
def list_pairs(user=Depends(current_user)):
    with db() as connection: rows = connection.execute("SELECT * FROM pairs WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/pairs")
def create_pair(input: PairInput, user=Depends(current_user)):
    with db() as connection: connection.execute("INSERT INTO pairs (user_id, prompt, response, language, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user["id"], input.prompt.strip(), input.response.strip(), input.language, input.status, now(), now()))
    return {"ok": True}


@app.put("/api/pairs/{pair_id}")
def update_pair(pair_id: int, input: PairInput, user=Depends(current_user)):
    with db() as connection:
        cursor = connection.execute("UPDATE pairs SET prompt=?, response=?, language=?, status=?, updated_at=? WHERE id=? AND user_id=?", (input.prompt.strip(), input.response.strip(), input.language, input.status, now(), pair_id, user["id"]))
    if not cursor.rowcount: raise HTTPException(404, "학습 데이터를 찾을 수 없습니다.")
    return {"ok": True}


@app.delete("/api/pairs/{pair_id}")
def delete_pair(pair_id: int, user=Depends(current_user)):
    with db() as connection: cursor = connection.execute("DELETE FROM pairs WHERE id=? AND user_id=?", (pair_id, user["id"]))
    if not cursor.rowcount: raise HTTPException(404, "학습 데이터를 찾을 수 없습니다.")
    return {"ok": True}


@app.get("/api/pairs/export")
def export_pairs(user=Depends(current_user)):
    records = [{"id": f"mirae-{index}", "source": "local-studio", "messages": [{"role": "user", "text": row["prompt"]}, {"role": "assistant", "text": row["response"]}]} for index, row in enumerate(approved_pairs(user["id"]), 1)]
    return {"filename": "mirae-training-pairs.jsonl", "jsonl": "\n".join(json.dumps(record, ensure_ascii=False) for record in records)}


@app.post("/api/pairs/import-starter")
def import_starter_pairs(user=Depends(current_user)):
    source_path = ROOT / "starter_dialogues.jsonl"
    records = [json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    inserted = 0
    with db() as connection:
        existing = connection.execute("SELECT COUNT(*) AS count FROM pairs WHERE user_id=? AND source='starter'", (user["id"],)).fetchone()["count"]
        if existing:
            return {"inserted": 0, "note": "스타터 대화는 이미 가져왔습니다."}
        for record in records:
            messages = record["messages"]
            connection.execute("INSERT INTO pairs (user_id, prompt, response, language, source, status, created_at, updated_at) VALUES (?, ?, ?, 'mixed', 'starter', 'approved', ?, ?)", (user["id"], messages[0]["text"], messages[1]["text"], now(), now()))
            inserted += 1
    return {"inserted": inserted, "note": "자체 작성 스타터 대화를 추가했습니다."}


@app.post("/api/suggest")
def suggest(input: ChatInput, user=Depends(current_user)):
    return {"suggestions": [{"prompt": input.message, "response": "그 이야기를 꺼내 준 것만으로도 중요한 시작이에요. 지금 마음을 한 문장 더 들려주실래요?"}, {"prompt": f"Could you respond with care? {input.message}", "response": "Thank you for sharing that. We can take one small step at a time, in Korean, English, or both."}]}


@app.post("/api/chat")
def chat(input: ChatInput, user=Depends(current_user)):
    reply, mode = model_reply(input.message, approved_pairs(user["id"])); record_chat_history(user["id"], input.message, reply, mode); return {"reply": reply, "mode": mode, "model_version": active_model_version(user["id"])}


@app.get("/api/history")
def history(query: str = "", user=Depends(current_user)):
    phrase = f"%{query.strip()}%"
    with db() as connection:
        if query.strip(): rows = connection.execute("SELECT * FROM chat_history WHERE user_id=? AND content LIKE ? ORDER BY id DESC LIMIT 80", (user["id"], phrase)).fetchall()
        else: rows = connection.execute("SELECT * FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 80", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/history/{history_id}/reuse")
def reuse_history(history_id: int, user=Depends(current_user)):
    with db() as connection:
        selected = connection.execute("SELECT * FROM chat_history WHERE id=? AND user_id=?", (history_id, user["id"])).fetchone()
        if not selected: raise HTTPException(404, "대화 기록을 찾을 수 없습니다.")
        if selected["role"] == "user": counterpart = connection.execute("SELECT * FROM chat_history WHERE user_id=? AND role='assistant' AND id>? ORDER BY id ASC LIMIT 1", (user["id"], history_id)).fetchone()
        else: counterpart = connection.execute("SELECT * FROM chat_history WHERE user_id=? AND role='user' AND id<? ORDER BY id DESC LIMIT 1", (user["id"], history_id)).fetchone()
        if not counterpart: raise HTTPException(400, "짝이 되는 대화 응답을 찾을 수 없습니다.")
        prompt = selected["content"] if selected["role"] == "user" else counterpart["content"]
        response = selected["content"] if selected["role"] == "assistant" else counterpart["content"]
        connection.execute("INSERT INTO pairs (user_id, prompt, response, language, source, status, created_at, updated_at) VALUES (?, ?, ?, 'mixed', 'history-reuse', 'draft', ?, ?)", (user["id"], prompt, response, now(), now()))
    return {"prompt": prompt, "response": response, "note": "대화 기록을 검토용 학습 초안으로 가져왔습니다."}


@app.get("/api/keys")
def list_keys(user=Depends(current_user)):
    with db() as connection: rows = connection.execute("SELECT id, name, prefix, state, created_at, last_used_at FROM api_keys WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/keys")
def create_key(input: KeyInput, user=Depends(current_user)):
    key = f"mirae_{secrets.token_urlsafe(30)}"
    with db() as connection: connection.execute("INSERT INTO api_keys (user_id, name, prefix, key_hash, created_at) VALUES (?, ?, ?, ?, ?)", (user["id"], input.name, key[:18], hash_key(key), now()))
    return {"key": key}


@app.delete("/api/keys/{key_id}")
def revoke_key(key_id: int, user=Depends(current_user)):
    with db() as connection: cursor = connection.execute("UPDATE api_keys SET state='revoked', revoked_at=? WHERE id=? AND user_id=?", (now(), key_id, user["id"]))
    if not cursor.rowcount: raise HTTPException(404, "API 키를 찾을 수 없습니다.")
    return {"ok": True}


def authenticate_api_key(authorization: Optional[str], x_api_key: Optional[str]) -> sqlite3.Row:
    raw = x_api_key or (authorization.split(" ", 1)[1].strip() if authorization and authorization.lower().startswith("bearer ") else "")
    if not raw: raise HTTPException(401, "API key is required.")
    with db() as connection: record = connection.execute("SELECT * FROM api_keys WHERE key_hash=? AND state='active'", (hash_key(raw),)).fetchone()
    if not record: raise HTTPException(401, "Invalid or revoked API key.")
    return record


@app.post("/api/v1/chat/completions")
def external_chat(input: ChatInput, authorization: Optional[str] = Header(default=None), x_api_key: Optional[str] = Header(default=None)):
    record = authenticate_api_key(authorization, x_api_key); reply, mode = model_reply(input.message, approved_pairs(record["user_id"]))
    record_chat_history(record["user_id"], input.message, reply, mode)
    with db() as connection:
        connection.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (now(), record["id"]))
        connection.execute("INSERT INTO usage_logs (api_key_id, user_id, endpoint, status_code, created_at) VALUES (?, ?, ?, 200, ?)", (record["id"], record["user_id"], "/api/v1/chat/completions", now()))
    return {"object": "chat.completion", "model": active_model_version(record["user_id"]), "mode": mode, "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}}]}


def write_training_jsonl(user_id: int) -> Path:
    records = [{"id": f"local-{index}", "source": "mirae-local", "messages": [{"role": "user", "text": row["prompt"]}, {"role": "assistant", "text": row["response"]}]} for index, row in enumerate(approved_pairs(user_id), 1)]
    path = DATA_DIR / "training_pairs.jsonl"; path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8"); return path


def update_run(run_id: int, *, status: str, current_step: int, progress: int, loss: Optional[float], note: str, completed: bool = False) -> None:
    with db() as connection:
        connection.execute("UPDATE training_runs SET status=?, current_step=?, progress=?, loss=?, note=?, completed_at=? WHERE id=?", (status, current_step, progress, loss, note, now() if completed else None, run_id))


def register_model_version(user_id: int, steps: int) -> None:
    metadata_path = ARTIFACT_DIR / "last_run.json"
    if not metadata_path.exists(): return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    history = metadata.get("history", [])
    last = history[-1] if history else {}
    with db() as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM model_versions WHERE user_id=?", (user_id,)).fetchone()["count"]
        connection.execute("UPDATE model_versions SET is_active=0 WHERE user_id=?", (user_id,))
        connection.execute("INSERT INTO model_versions (user_id, version, label, dataset_records, requested_steps, parameter_count, train_loss, validation_loss, artifact_path, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)", (user_id, f"mirae-v{count + 1}", f"직접 학습 모델 v{count + 1}", len(approved_pairs(user_id)), steps, int(metadata.get("parameter_count", metadata.get("parameters", 0))), last.get("train_loss"), last.get("validation_loss"), str(ARTIFACT_DIR / "checkpoints" / "latest.pt"), now()))


def read_training_output(process: subprocess.Popen[str], steps: int, run_id: int, user_id: int) -> None:
    global job
    for line in process.stdout or []:
        match = re.search(r"step=\s*(\d+).*train_loss=([0-9.]+)", line)
        if match:
            current = int(match.group(1)); progress = min(100, int(current / steps * 100)); loss = float(match.group(2)); job.update({"status": "running", "current_step": current, "steps": steps, "progress": progress, "loss": loss, "note": "소형 Transformer가 당신의 JSONL 데이터를 학습하고 있습니다.", "history": [*job.get("history", []), {"step": current, "loss": loss}]}); update_run(run_id, status="running", current_step=current, progress=progress, loss=loss, note=str(job["note"]))
    process.wait()
    final_status = "completed" if process.returncode == 0 else "failed"; final_note = "학습이 완료되었습니다. 대화 패널에서 새 모델을 확인해 보세요." if process.returncode == 0 else "학습이 중단되었습니다. Python 및 PyTorch 설치 상태를 확인하세요."; job.update({"status": final_status, "progress": 100 if process.returncode == 0 else job["progress"], "note": final_note}); update_run(run_id, status=final_status, current_step=int(job["current_step"]), progress=int(job["progress"]), loss=job["loss"], note=final_note, completed=True)
    if process.returncode == 0: register_model_version(user_id, steps)


@app.post("/api/train")
def train(input: TrainInput, user=Depends(current_user)):
    global job
    if job["status"] == "running": raise HTTPException(409, "이미 학습이 진행 중입니다.")
    path = write_training_jsonl(user["id"])
    if len(approved_pairs(user["id"])) < 2: raise HTTPException(400, "학습을 시작하려면 승인된 대화 쌍이 2개 이상 필요합니다.")
    command = [sys.executable, "-m", "model.train", "--data", str(path), "--output-dir", str(ARTIFACT_DIR), "--steps", str(input.steps), "--batch-size", "4", "--eval-interval", str(max(25, input.steps // 10)), "--eval-batches", "4", "--max-seq-len", "128", "--d-model", "128", "--n-heads", "4", "--n-layers", "3"]
    with db() as connection:
        run_id = connection.execute("INSERT INTO training_runs (user_id, status, requested_steps, note, created_at) VALUES (?, 'running', ?, ?, ?)", (user["id"], input.steps, "학습 프로세스를 시작했습니다.", now())).lastrowid
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    job = {"run_id": run_id, "status": "running", "progress": 0, "current_step": 0, "steps": input.steps, "loss": None, "note": "학습 프로세스를 시작했습니다.", "history": []}
    threading.Thread(target=read_training_output, args=(process, input.steps, run_id, user["id"]), daemon=True).start()
    return job


@app.get("/api/train/status")
def train_status(user=Depends(current_user)):
    with db() as connection:
        runs = connection.execute("SELECT * FROM training_runs WHERE user_id=? ORDER BY id DESC LIMIT 10", (user["id"],)).fetchall()
    payload = dict(job)
    payload["runs"] = [dict(run) for run in runs]
    return payload


@app.get("/api/models")
def models(user=Depends(current_user)):
    with db() as connection: rows = connection.execute("SELECT * FROM model_versions WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/models/compare")
def compare_models(left: int, right: int, user=Depends(current_user)):
    with db() as connection: rows = connection.execute("SELECT * FROM model_versions WHERE user_id=? AND id IN (?, ?)", (user["id"], left, right)).fetchall()
    records = {row["id"]: dict(row) for row in rows}
    if left not in records or right not in records: raise HTTPException(404, "비교할 모델 버전을 찾을 수 없습니다.")
    a, b = records[left], records[right]
    return {"left": a, "right": b, "deltas": {"dataset_records": b["dataset_records"] - a["dataset_records"], "requested_steps": b["requested_steps"] - a["requested_steps"], "train_loss": (b["train_loss"] or 0) - (a["train_loss"] or 0), "validation_loss": (b["validation_loss"] or 0) - (a["validation_loss"] or 0)}}


@app.post("/api/models/respond")
def compare_model_responses(input: ModelPromptInput, user=Depends(current_user)):
    with db() as connection: rows = connection.execute("SELECT * FROM model_versions WHERE user_id=? AND id IN (?, ?)", (user["id"], input.left, input.right)).fetchall()
    versions = {row["id"]: row for row in rows}
    if input.left not in versions or input.right not in versions: raise HTTPException(404, "비교할 모델 버전을 찾을 수 없습니다.")
    pairs = approved_pairs(user["id"])
    def answer(version: sqlite3.Row):
        checkpoint = Path(version["artifact_path"]) if version["artifact_path"] else ARTIFACT_DIR / "checkpoints" / "latest.pt"
        reply, mode = model_reply(input.message, pairs, checkpoint.parent.parent)
        return {"version": version["version"], "reply": reply, "mode": mode}
    return {"left": answer(versions[input.left]), "right": answer(versions[input.right])}


@app.get("/api/admin")
def admin(user=Depends(current_user)):
    if user["role"] != "admin": raise HTTPException(403, "관리자 전용입니다.")
    with db() as connection:
        users = connection.execute("SELECT id, username, role, created_at FROM users ORDER BY id DESC").fetchall(); keys = connection.execute("SELECT COUNT(*) AS count FROM api_keys WHERE state='active'").fetchone()["count"]; usage = connection.execute("SELECT COUNT(*) AS count FROM usage_logs").fetchone()["count"]
    return {"users": [dict(row) for row in users], "user_count": len(users), "active_key_count": keys, "request_count": usage}


HTML = """<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Mirae AI Studio</title><style>
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 10%,#0d7274 0,#100722 43%,#260a4c 100%);color:#f7f5ff;font-family:Arial,'Malgun Gothic',sans-serif;min-height:100vh}.wrap{max-width:1180px;margin:auto;padding:28px}.brand{font-size:12px;letter-spacing:.22em;color:#9ef6e9;font-weight:bold}.hero{min-height:82vh;display:flex;flex-direction:column;justify-content:center}.hero h1{font-size:clamp(60px,11vw,145px);line-height:.83;letter-spacing:-.08em;margin:24px 0}.mint{color:#8ff0e1}.sub{max-width:430px;line-height:1.65;color:#d8d1ee}.button{border:0;border-radius:999px;background:#9ff1e3;color:#142421;padding:13px 20px;font-weight:bold;cursor:pointer}.button.ghost{background:#ffffff12;color:white;border:1px solid #ffffff22}.grid{display:grid;grid-template-columns:250px 1fr;gap:22px}.nav,.panel{background:#ffffff0d;border:1px solid #ffffff1c;border-radius:22px;backdrop-filter:blur(16px)}.nav{padding:14px;height:max-content}.nav button{display:block;width:100%;text-align:left;background:transparent;color:#ddd5f6;border:0;padding:12px;border-radius:12px;cursor:pointer}.nav button:hover,.nav button.active{background:#a3f3e51c;color:#a9f8ec}.panel{padding:22px}.view{display:none}.view.active{display:block}.row{display:flex;gap:10px;align-items:center;justify-content:space-between}.stack{display:grid;gap:11px}input,textarea{width:100%;border:1px solid #ffffff22;background:#09031566;color:white;border-radius:12px;padding:12px;font:inherit}textarea{min-height:100px}.item{padding:14px;border-top:1px solid #ffffff15}.muted{color:#c5bddb;font-size:13px;line-height:1.6}.chat{min-height:400px;max-height:58vh;overflow:auto;padding:10px 0}.msg{max-width:80%;padding:12px;border-radius:16px;margin:10px 0;white-space:pre-wrap}.msg.user{margin-left:auto;background:#9ff1e3;color:#102522}.msg.assistant{background:#ffffff12}.pill{display:inline-block;border-radius:999px;background:#9ff1e31a;color:#a9f8ec;padding:5px 9px;font-size:12px}pre{white-space:pre-wrap;background:#05020e88;padding:14px;border-radius:14px;color:#b6fff5;overflow:auto}.notice{padding:12px;border-radius:12px;background:#ffffff0f}.hide{display:none}@media(max-width:760px){.grid{grid-template-columns:1fr}.nav{display:flex;overflow:auto}.nav button{white-space:nowrap}.hero h1{font-size:70px}.wrap{padding:18px}}
</style></head><body><main id='app' class='wrap'></main><script>
const app=document.querySelector('#app');let me=null,editing=null;const call=async(p,o={})=>{let r=await fetch(p,{headers:{'Content-Type':'application/json',...(o.headers||{})},...o});let d=await r.json();if(!r.ok)throw Error(d.detail||d.error||'요청에 실패했습니다.');return d};const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function boot(){let state=await call('/api/me');if(state.setupRequired)return auth(true);if(!state.user)return auth(false);me=state.user;studio()}function auth(setup){app.innerHTML=`<section class='hero'><p class='brand'>MIRAE AI STUDIO · LOCAL</p><h1>당신의 언어로,<br><span class='mint'>지능을 빚어내다.</span></h1><div class='panel' style='max-width:440px'><h2>${setup?'첫 관리자 만들기':'스튜디오 로그인'}</h2><p class='muted'>모든 데이터와 API 키는 이 PC의 SQLite 데이터베이스에만 저장됩니다.</p><div class='stack'><input id='user' placeholder='사용자 이름'><input id='pass' type='password' placeholder='비밀번호 (8자 이상)'><button class='button' id='auth'>${setup?'스튜디오 시작':'로그인'}</button></div></div></section>`;document.querySelector('#auth').onclick=async()=>{try{await call(setup?'/api/setup':'/api/login',{method:'POST',body:JSON.stringify({username:user.value,password:pass.value})});boot()}catch(e){alert(e.message)}}}
function layout(content,active='chat'){app.innerHTML=`<div class='row'><div><p class='brand'>MIRAE AI STUDIO · LOCAL</p><h2>당신의 개인 AI 작업실</h2></div><button class='button ghost' id='logout'>로그아웃</button></div><div class='grid'><nav class='nav'>${[['chat','대화'],['history','대화 기록'],['data','학습 데이터'],['train','학습 관찰'],['models','모델 버전'],['keys','API 키'],['admin','관리자']].map(x=>`<button class='${active===x[0]?'active':''}' data-v='${x[0]}'>${x[1]}</button>`).join('')}</nav><section class='panel'>${content}</section></div>`;document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>view(b.dataset.v));logout.onclick=async()=>{await call('/api/logout',{method:'POST'});boot()}}
async function studio(){view('chat')}async function view(v){if(v==='chat')return chat();if(v==='history')return history();if(v==='data')return data();if(v==='train')return train();if(v==='models')return models();if(v==='keys')return keys();if(v==='admin')return admin()}
async function chat(){layout(`<p class='brand'>CONVERSATION GARDEN</p><h1>오늘, 내 AI에게<br>무엇을 가르칠까요?</h1><div id='messages' class='chat'><div class='notice muted'>한국어와 English를 섞어 편하게 이야기해 보세요. 학습된 모델이 없으면 승인한 대화 데이터 기반으로 답합니다.</div></div><div class='row'><input id='message' placeholder='Korean, English, or both...'><button class='button' id='send'>보내기</button></div>`,'chat');send.onclick=async()=>{let text=message.value.trim();if(!text)return;messages.insertAdjacentHTML('beforeend',`<div class='msg user'>${esc(text)}</div>`);message.value='';try{let d=await call('/api/chat',{method:'POST',body:JSON.stringify({message:text})});messages.insertAdjacentHTML('beforeend',`<div class='msg assistant'>${esc(d.reply)}<div class='muted'>${d.mode}</div></div>`);messages.scrollTop=messages.scrollHeight}catch(e){alert(e.message)}};message.onkeydown=e=>{if(e.key==='Enter')send.click()}}
async function history(){let render=rows=>rows.map(r=>`<article class='item'><span class='pill'>${r.role==='user'?'나':'AI'}</span><p>${esc(r.content)}</p><small class='muted'>${r.model_version||'starter-v1'} · ${r.mode||'conversation'}</small>${r.role==='user'?`<button class='button ghost' data-reuse='${r.id}'>학습 초안으로 재사용</button>`:''}</article>`).join('')||'<p class="muted">저장된 대화가 없습니다.</p>';let rows=await call('/api/history');layout(`<p class='brand'>MEMORY TRACE</p><h1>대화의 흔적을<br>다시 찾아보세요.</h1><div class='row'><input id='historyquery' placeholder='대화 속 단어 검색'><button class='button' id='historysearch'>검색</button></div><div id='historylist'>${render(rows)}</div>`,'history');let wire=()=>document.querySelectorAll('[data-reuse]').forEach(b=>b.onclick=async()=>{try{let d=await call('/api/history/'+b.dataset.reuse+'/reuse',{method:'POST'});alert(d.note)}catch(e){alert(e.message)}});wire();historysearch.onclick=async()=>{let found=await call('/api/history?query='+encodeURIComponent(historyquery.value));historylist.innerHTML=render(found);wire()}}
async function models(){let versions=await call('/api/models');layout(`<p class='brand'>MODEL ATLAS</p><h1>성장한 모델을<br>나란히 살펴보세요.</h1><div class='grid' style='grid-template-columns:1fr 1fr'><div><h3>저장된 모델</h3>${versions.map(v=>`<article class='item'><b>${esc(v.label)}</b><p class='muted'>${v.version} · ${v.dataset_records} pairs · ${v.requested_steps} steps<br>train ${v.train_loss??'—'} / validation ${v.validation_loss??'—'}</p></article>`).join('')||'<p class="muted">학습을 완료하면 모델 버전이 기록됩니다.</p>'}</div><div><h3>버전 비교</h3>${versions.length>1?`<select id='leftmodel'>${versions.map(v=>`<option value='${v.id}'>${esc(v.label)}</option>`).join('')}</select><select id='rightmodel'>${versions.map(v=>`<option value='${v.id}'>${esc(v.label)}</option>`).join('')}</select><input id='compareprompt' placeholder='두 모델에 보낼 같은 질문'><button class='button' id='comparemodels'>성능·응답 비교</button><div id='comparison' class='notice'></div>`:'<p class="muted">두 개 이상의 버전이 필요합니다.</p>'}</div></div>`,'models');if(versions.length>1){leftmodel.value=versions[1].id;rightmodel.value=versions[0].id;comparemodels.onclick=async()=>{let d=await call('/api/models/compare?left='+leftmodel.value+'&right='+rightmodel.value);let text=`<b>${esc(d.left.label)} → ${esc(d.right.label)}</b><p class='muted'>데이터 +${d.deltas.dataset_records} · 스텝 +${d.deltas.requested_steps}<br>학습 손실 ${d.deltas.train_loss.toFixed(4)} · 검증 손실 ${d.deltas.validation_loss.toFixed(4)}</p>`;if(compareprompt.value.trim()){let r=await call('/api/models/respond',{method:'POST',body:JSON.stringify({left:Number(leftmodel.value),right:Number(rightmodel.value),message:compareprompt.value})});text+=`<hr><b>${r.left.version}</b><p>${esc(r.left.reply)}</p><b>${r.right.version}</b><p>${esc(r.right.reply)}</p>`}comparison.innerHTML=text}}}
async function data(){let pairs=await call('/api/pairs');layout(`<p class='brand'>MEMORY ATELIER</p><h1>AI의 기억을<br>당신의 언어로 만드세요.</h1><div class='grid' style='grid-template-columns:1fr 1fr'><div class='stack'><input id='prompt' placeholder='사용자 문장'><textarea id='response' placeholder='어시스턴트 문장'></textarea><div><button class='button' id='save'>${editing?'수정 저장':'대화 쌍 저장'}</button> <button class='button ghost' id='export'>JSONL 내보내기</button> <button class='button ghost' id='starter'>스타터 30쌍</button></div></div><div><input id='seed' placeholder='로컬 초안 주제'><button class='button ghost' id='suggest' style='margin-top:10px'>공감형 초안 제안</button><div id='suggestions' class='stack' style='margin-top:10px'></div></div></div><h3>저장된 기억 <span class='pill'>${pairs.length} pairs</span></h3><div>${pairs.map(p=>`<article class='item'><b>${esc(p.prompt)}</b><p class='muted'>${esc(p.response)}</p><button class='button ghost' data-edit='${p.id}'>수정</button> <button class='button ghost' data-del='${p.id}'>삭제</button></article>`).join('')||'<p class="muted">첫 대화 쌍을 만들어 보세요.</p>'}</div>`,'data');if(editing){prompt.value=editing.prompt;response.value=editing.response}save.onclick=async()=>{let body={prompt:prompt.value,response:response.value};try{await call(editing?'/api/pairs/'+editing.id:'/api/pairs',{method:editing?'PUT':'POST',body:JSON.stringify(body)});editing=null;data()}catch(e){alert(e.message)}};export.onclick=async()=>{let d=await call('/api/pairs/export');let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([d.jsonl],{type:'application/x-ndjson'}));a.download=d.filename;a.click()};starter.onclick=async()=>{try{let d=await call('/api/pairs/import-starter',{method:'POST'});alert(d.note);data()}catch(e){alert(e.message)}};suggest.onclick=async()=>{let d=await call('/api/suggest',{method:'POST',body:JSON.stringify({message:seed.value})});suggestions.innerHTML=d.suggestions.map(s=>`<button class='notice' data-s='${encodeURIComponent(JSON.stringify(s))}'>${esc(s.prompt)}<br><span class='muted'>${esc(s.response)}</span></button>`).join('');document.querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{let s=JSON.parse(decodeURIComponent(b.dataset.s));prompt.value=s.prompt;response.value=s.response})};document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>{editing=pairs.find(p=>p.id==b.dataset.edit);data()});document.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{if(confirm('삭제할까요?')){await call('/api/pairs/'+b.dataset.del,{method:'DELETE'});data()}})}
async function train(){let status=await call('/api/train/status');layout(`<p class='brand'>GROWTH OBSERVATORY</p><h1>작은 신호를 모아<br>AI를 키웁니다.</h1><div class='notice'><span class='pill'>${status.status}</span><h3>${status.current_step||0} / ${status.steps||0} steps · ${status.progress||0}%</h3><p class='muted'>손실값: ${status.loss??'측정 대기'}<br>${status.note}</p></div><div id='chart' class='notice' style='margin-top:12px'><b>손실 곡선</b><p class='muted'>학습을 시작하면 실제 로그가 여기에 나타납니다.</p></div><div class='row'><input id='steps' type='number' value='1000'><button class='button' id='start'>로컬 학습 시작</button></div><p class='muted'>학습은 이 PC의 PyTorch에서 실행되며, 브라우저를 닫아도 로컬 서버가 켜진 동안 계속됩니다.</p>`,'train');let history=status.history||[];if(history.length>1){let values=history.map(x=>x.loss),min=Math.min(...values),max=Math.max(...values),points=history.map((x,i)=>`${i/(history.length-1)*300},${80-(x.loss-min)/Math.max(.0001,max-min)*65}`).join(' ');chart.innerHTML=`<b>손실 곡선</b><svg viewBox='0 0 300 90' width='100%' height='100' aria-label='학습 손실 차트'><polyline points='${points}' fill='none' stroke='#9ff1e3' stroke-width='3'/></svg><p class='muted'>최신 손실값 ${values.at(-1).toFixed(4)}</p>`};start.onclick=async()=>{try{await call('/api/train',{method:'POST',body:JSON.stringify({steps:Number(steps.value)})});setTimeout(train,500)}catch(e){alert(e.message)}};if(status.status==='running')setTimeout(train,1500)}
async function keys(){let list=await call('/api/keys');layout(`<p class='brand'>PRIVATE GATEWAY</p><h1>당신의 AI를<br>안전하게 연결하세요.</h1><div class='row'><input id='keyname' placeholder='예: Unity prototype'><button class='button' id='create'>새 API 키</button></div><div id='newkey'></div><pre>curl -X POST http://127.0.0.1:8000/api/v1/chat/completions \\
 -H "Authorization: Bearer YOUR_MIRAE_API_KEY" \\
 -H "Content-Type: application/json" \\
 -d '{"message":"안녕하세요. Hello!"}'</pre>${list.map(k=>`<article class='item'><b>${esc(k.name)}</b><p class='muted'>${esc(k.prefix)}•••• · ${k.state}</p>${k.state==='active'?`<button class='button ghost' data-revoke='${k.id}'>폐기</button>`:''}</article>`).join('')||'<p class="muted">아직 발급한 키가 없습니다.</p>'}`,'keys');create.onclick=async()=>{try{let d=await call('/api/keys',{method:'POST',body:JSON.stringify({name:keyname.value})});newkey.innerHTML=`<div class='notice'><b>지금 한 번만 보이는 키입니다.</b><pre>${esc(d.key)}</pre></div>`;setTimeout(keys,50)}catch(e){alert(e.message)}};document.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=async()=>{await call('/api/keys/'+b.dataset.revoke,{method:'DELETE'});keys()})}
async function admin(){let d=await call('/api/admin');layout(`<p class='brand'>STUDIO STEWARDSHIP</p><h1>전체 스튜디오의<br>온도를 살핍니다.</h1><div class='grid' style='grid-template-columns:repeat(3,1fr)'><div class='notice'>사용자<br><b>${d.user_count}</b></div><div class='notice'>활성 API 키<br><b>${d.active_key_count}</b></div><div class='notice'>API 요청<br><b>${d.request_count}</b></div></div><h3>사용자</h3>${d.users.map(u=>`<article class='item'><b>${esc(u.username)}</b> <span class='pill'>${u.role}</span></article>`).join('')}`,'admin')}boot();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home(): return HTML


init_db()
