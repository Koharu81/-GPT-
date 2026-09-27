import os, re, json, time, secrets, hashlib, hmac
from typing import Any
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import FastAPI, Header, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

app=FastAPI(title="Mirae AI API",version="4.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["https://gpt-phi-cyan.vercel.app","https://mirae.koharu.live"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
DATABASE_URL=os.getenv("DATABASE_URL","")
HF_TOKEN=os.getenv("HF_TOKEN",""); HF_MODEL=os.getenv("HF_MODEL","openai/gpt-oss-120b:groq")
NEWS_RSS="https://news.google.com/rss/search"; HF_URL="https://router.huggingface.co/v1/chat/completions"
SESSION_DAYS=30

def db():
    if not DATABASE_URL: raise HTTPException(503,"DATABASE_URL is not configured.")
    return psycopg.connect(DATABASE_URL,row_factory=dict_row)

def digest(value:str)->str: return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password:str)->str:
    salt=secrets.token_bytes(16); return "scrypt$"+salt.hex()+"$"+hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
def password_ok(password:str,stored:str)->bool:
    try:
        _,salt,hashed=stored.split("$",2); got=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex(); return hmac.compare_digest(got,hashed)
    except Exception: return False

def session_user(request:Request):
    token=request.cookies.get("mirae_session")
    if not token: return None
    with db() as c:
        row=c.execute("SELECT u.* FROM mirae_sessions s JOIN mirae_users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>now()",[digest(token)]).fetchone()
    return row
class Signup(BaseModel):
    email:str; password:str=Field(min_length=8,max_length=200); name:str=Field(min_length=1,max_length=40)
class Login(BaseModel): email:str; password:str
class ChatMessage(BaseModel): role:str; content:str
class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=12000); history:list[ChatMessage]=Field(default_factory=list); personality:str="balanced"; instructions:str=""; web_search:bool=True; temperature:float=Field(.7,ge=.2,le=1.2); max_tokens:int=Field(700,ge=64,le=1600)
class Settings(BaseModel): theme:str="light"; personality:str="balanced"; instructions:str=""; web_search:bool=True; temperature:float=Field(.7,ge=.2,le=1.2)
class KeyCreate(BaseModel): name:str=Field(min_length=2,max_length=80)

def lang(text):
    counts=[len(re.findall(r"[가-힣]",text)),len(re.findall(r"[ぁ-ゖァ-ヺ]",text)),len(re.findall(r"[A-Za-z]",text))]; return ["ko","ja","en"][counts.index(max(counts))]
async def search_web(q):
    params={"q":q,"hl":"ko","gl":"KR","ceid":"KR:ko"}
    async with httpx.AsyncClient(timeout=8,follow_redirects=True) as x:
        r=await x.get(NEWS_RSS,params=params,headers={"User-Agent":"MiraeAI/4.0"}); r.raise_for_status()
    import xml.etree.ElementTree as ET
    root=ET.fromstring(r.text); out=[]
    for i in root.findall(".//item")[:8]:
        title=i.findtext("title") or ""; link=i.findtext("link") or ""; pub=i.findtext("pubDate") or ""; desc=re.sub(r"<[^>]+>"," ",i.findtext("description") or "")
        out.append({"title":title.strip(),"url":link.strip(),"published":pub,"snippet":" ".join(desc.split())[:500]})
    return out
async def generate(messages,temp,max_tokens):
    if not HF_TOKEN: raise HTTPException(503,"HF_TOKEN is not configured on the API server.")
    async with httpx.AsyncClient(timeout=90) as x:
        r=await x.post(HF_URL,headers={"Authorization":f"Bearer {HF_TOKEN}"},json={"model":HF_MODEL,"messages":messages,"temperature":temp,"max_tokens":max_tokens,"stream":False})
    if r.status_code>=400: raise HTTPException(r.status_code,f"Upstream model request failed: {r.text[:500]}")
    try:return r.json()["choices"][0]["message"]["content"].strip()
    except Exception: raise HTTPException(502,"Invalid model response.")
def system_prompt(req,language,sources):
    rules={"ko":"한국어로 답하세요. 임의로 다른 언어를 섞지 마세요.","ja":"日本語で答えてください。勝手に他の言語を混ぜないでください。","en":"Answer in natural English unless the user requests another language."}
    src="\n웹 검색 결과:\n"+"\n".join(f"- {x['title']} | {x['published']} | {x['url']} | {x['snippet']}" for x in sources) if sources else ""
    return f"""You are Mirae AI, a general-purpose generative AI assistant. Current date: 2026-09-27. {rules[language]}
Use supplied web results for current/latest/recent questions. Do not claim search is unavailable when results exist. Do not invent citations or facts. Personality: {req.personality[:80]}. User instructions: {req.instructions[:4000] or 'none'}.{src}"""

def save_chat(user_id,message,reply,mode,sources):
    with db() as c:
        c.execute("INSERT INTO mirae_chat_history(user_id,role,content,mode,model,sources) VALUES (%s,'user',%s,%s,%s,%s),(%s,'assistant',%s,%s,%s,%s)",[user_id,message,mode,HF_MODEL,json.dumps(sources),user_id,reply,mode,HF_MODEL,json.dumps(sources)]); c.commit()

def set_session(response,user_id):
    token=secrets.token_urlsafe(48); exp=datetime.now(timezone.utc)+timedelta(days=SESSION_DAYS)
    with db() as c: c.execute("INSERT INTO mirae_sessions(user_id,token_hash,expires_at) VALUES (%s,%s,%s)",[user_id,digest(token),exp]); c.commit()
    response.set_cookie("mirae_session",token,max_age=SESSION_DAYS*86400,httponly=True,secure=True,samesite="none",path="/")

@app.get("/health")
async def health(): return {"ok":True,"model":HF_MODEL,"web_search":True,"database":bool(DATABASE_URL),"version":"4.0.0"}

@app.post("/auth/signup")
async def signup(data:Signup,response:Response):
    email=data.email.strip().lower()
    if "@" not in email: raise HTTPException(400,"올바른 이메일을 입력해주세요.")
    with db() as c:
        if c.execute("SELECT id FROM mirae_users WHERE email=%s",[email]).fetchone(): raise HTTPException(409,"이미 가입된 이메일입니다.")
        row=c.execute("INSERT INTO mirae_users(email,password_hash,name) VALUES (%s,%s,%s) RETURNING id,email,name",[email,password_hash(data.password),data.name.strip()]).fetchone()
        c.execute("INSERT INTO mirae_user_settings(user_id) VALUES (%s)",[row["id"]]); c.commit()
    set_session(response,row["id"]); return {"user":row}
@app.post("/auth/login")
async def login(data:Login,response:Response):
    with db() as c: row=c.execute("SELECT * FROM mirae_users WHERE email=%s",[data.email.strip().lower()]).fetchone()
    if not row or not password_ok(data.password,row["password_hash"]): raise HTTPException(401,"이메일 또는 비밀번호가 올바르지 않습니다.")
    with db() as c: c.execute("UPDATE mirae_users SET last_signed_in=now(),updated_at=now() WHERE id=%s",[row["id"]]); c.commit()
    set_session(response,row["id"]); return {"user":{"id":row["id"],"email":row["email"],"name":row["name"]}}
@app.post("/auth/logout")
async def logout(request:Request,response:Response):
    token=request.cookies.get("mirae_session")
    if token:
        with db() as c:c.execute("DELETE FROM mirae_sessions WHERE token_hash=%s",[digest(token)]);c.commit()
    response.delete_cookie("mirae_session",path="/"); return {"ok":True}
@app.get("/auth/me")
async def me(request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    return {"user":{"id":u["id"],"email":u["email"],"name":u["name"]}}
@app.get("/settings")
async def get_settings(request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    with db() as c:
        row=c.execute("SELECT theme,personality,instructions,web_search,temperature FROM mirae_user_settings WHERE user_id=%s",[u["id"]]).fetchone()
    return row or {"theme":"light","personality":"balanced","instructions":"","web_search":True,"temperature":.7}
@app.put("/settings")
async def put_settings(data:Settings,request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    with db() as c:
        c.execute("INSERT INTO mirae_user_settings(user_id,theme,personality,instructions,web_search,temperature) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id) DO UPDATE SET theme=EXCLUDED.theme,personality=EXCLUDED.personality,instructions=EXCLUDED.instructions,web_search=EXCLUDED.web_search,temperature=EXCLUDED.temperature,updated_at=now()",[u["id"],data.theme,data.personality,data.instructions,data.web_search,data.temperature]);c.commit()
    return data.model_dump()
@app.get("/history")
async def history(request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    with db() as c: rows=c.execute("SELECT id,role,content,mode,model,sources,created_at FROM mirae_chat_history WHERE user_id=%s ORDER BY created_at DESC LIMIT 160",[u["id"]]).fetchall()
    return list(reversed(rows))
@app.post("/chat")
async def chat(req:ChatRequest,request:Request,authorization:str|None=Header(default=None)):
    u=session_user(request); sources=[]
    if req.web_search:
        try:sources=await search_web(req.message)
        except Exception:sources=[]
    msgs=[{"role":"system","content":system_prompt(req,lang(req.message),sources)}]
    msgs += [{"role":m.role,"content":m.content[:5000]} for m in req.history[-12:] if m.role in ("user","assistant") and m.content.strip()]
    msgs.append({"role":"user","content":req.message}); reply=await generate(msgs,req.temperature,req.max_tokens)
    if u: save_chat(u["id"],req.message,reply,"web" if sources else "model",sources)
    return {"reply":reply,"model":HF_MODEL,"language":lang(req.message),"sources":sources}

@app.get("/api-keys")
async def list_keys(request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    with db() as c: return c.execute("SELECT id,name,key_prefix,state,last_used_at,revoked_at,created_at FROM mirae_api_keys WHERE user_id=%s ORDER BY created_at DESC",[u["id"]]).fetchall()
@app.post("/api-keys")
async def create_key(data:KeyCreate,request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    raw="mk_"+secrets.token_urlsafe(32); prefix=raw[:10]
    with db() as c:c.execute("INSERT INTO mirae_api_keys(user_id,name,key_prefix,key_hash) VALUES (%s,%s,%s,%s)",[u["id"],data.name,prefix,digest(raw)]);c.commit()
    return {"key":raw,"prefix":prefix,"warning":"이 값은 지금 한 번만 표시됩니다."}
@app.delete("/api-keys/{key_id}")
async def revoke_key(key_id:int,request:Request):
    u=session_user(request)
    if not u: raise HTTPException(401,"로그인이 필요합니다.")
    with db() as c:c.execute("UPDATE mirae_api_keys SET state='revoked',revoked_at=now() WHERE id=%s AND user_id=%s",[key_id,u["id"]]);c.commit()
    return {"ok":True}
@app.post("/v1/chat/completions")
async def openai_chat(req:dict[str,Any],request:Request,authorization:str|None=Header(default=None)):
    key=authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    with db() as c:
        k=c.execute("SELECT * FROM mirae_api_keys WHERE key_hash=%s AND state='active'",[digest(key)]).fetchone() if key else None
    if not k: raise HTTPException(401,"Invalid or missing API key.")
    msgs=req.get("messages") or []; last=next((m.get("content","") for m in reversed(msgs) if m.get("role")=="user"),"")
    sources=[]
    try:sources=await search_web(last)
    except Exception:pass
    prompt=[{"role":"system","content":system_prompt(ChatRequest(message=last),lang(last),sources)}]+[m for m in msgs if m.get("role") in ("system","user","assistant")]
    reply=await generate(prompt,float(req.get("temperature",.7)),min(int(req.get("max_tokens",700)),1600))
    with db() as c:c.execute("UPDATE mirae_api_keys SET last_used_at=now() WHERE id=%s",[k["id"]]);c.commit()
    return {"id":"mirae-chat","object":"chat.completion","created":int(time.time()),"model":req.get("model","mirae-free"),"choices":[{"index":0,"message":{"role":"assistant","content":reply},"finish_reason":"stop"}],"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0},"sources":sources}
@app.get("/v1/models")
async def models(authorization:str|None=Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"API key required.")
    with db() as c:k=c.execute("SELECT id FROM mirae_api_keys WHERE key_hash=%s AND state='active'",[digest(authorization[7:])]).fetchone()
    if not k:raise HTTPException(401,"Invalid API key.")
    return {"object":"list","data":[{"id":"mirae-free","object":"model","owned_by":"mirae"}]}
