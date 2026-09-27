const $=s=>document.querySelector(s);
const API="/api";
let user=null;
let profile={name:"",email:"",bio:"",birth_date:null,avatar_url:""};
let settings={theme:"light",personality:"balanced",instructions:"",web_search:true,temperature:.7};
let chats=[],current=[],currentId=null,authMode="login",pendingSignup=null,resendTimer=null;
let currentTitle="새 대화";

function simpleHash(value){
  let h=2166136261;
  const s=String(value??"");
  for(let i=0;i<s.length;i++){
    h^=s.charCodeAt(i);
    h=Math.imul(h,16777619);
  }
  return (h>>>0).toString(16).padStart(8,"0");
}

async function req(path,opt={}){
  const r=await fetch(API+path,{credentials:"include",...opt,headers:{"Content-Type":"application/json",...(opt.headers||{})}});
  const d=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(d.detail||"요청에 실패했습니다.");
  return d;
}
function applyTheme(){
  const t=settings.theme||"light";
  if(t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme:dark)").matches))document.documentElement.dataset.theme="dark";
  else document.documentElement.removeAttribute("data-theme");
  if($("#theme"))$("#theme").value=t;
}
function fillSettings(){
  if($("#web"))$("#web").value=String(!!settings.web_search);
  if($("#personality"))$("#personality").value=settings.personality||"balanced";
  if($("#instructions"))$("#instructions").value=settings.instructions||"";
  if($("#theme"))$("#theme").value=settings.theme||"light";
  applyTheme();
}
async function boot(){
  try{
    const m=await req("/auth/me");user=m.user;
    await Promise.all([loadSettings(),loadProfile(),loadHistory()]);
    setAccountLabel();
  }catch{}
  fillSettings();renderHistory();newChat(false);
}
async function loadSettings(){try{settings=await req("/settings")}catch{}}
async function loadProfile(){if(user)try{applyProfile(await req("/profile"))}catch{}}
async function loadHistory(){
  if(user)try{
    const [rows,convs]=await Promise.all([req("/history"),req("/conversations")]);
    restoreServer(rows,convs);renderHistory();
  }catch{}
}
function setAccountLabel(){
  if($("#accountName"))$("#accountName").textContent=user?(profile.name||user.name):"계정";
  if($("#userInfo"))$("#userInfo").textContent=user?(profile.name||user.name)+" · "+user.email:"로그인하지 않음";
  if($("#accountAvatar"))setAvatar($("#accountAvatar"),profile.name||user?.name||"M",profile.avatar_url||"");
  if($("#accountPageAvatar"))setAvatar($("#accountPageAvatar"),profile.name||user?.name||"M",profile.avatar_url||"");
}
function setAvatar(el,name,url){
  el.textContent="";
  if(url){const img=document.createElement("img");img.src=url;img.alt="";img.referrerPolicy="no-referrer";img.onerror=()=>el.textContent=(name||"M").slice(0,1).toUpperCase();el.appendChild(img)}
  else el.textContent=(name||"M").slice(0,1).toUpperCase();
}
function applyProfile(p){
  profile={...profile,...p};
  if($("#profileName"))$("#profileName").value=p.name||"";
  if($("#profileEmail"))$("#profileEmail").textContent=p.email||"";
  if($("#profileBio"))$("#profileBio").value=p.bio||"";
  if($("#profileBirth"))$("#profileBirth").value=p.birth_date||"";
  if($("#profileAvatarUrl"))$("#profileAvatarUrl").value=p.avatar_url||"";
  if($("#profileAvatar"))setAvatar($("#profileAvatar"),p.name||"M",p.avatar_url||"");
  if($("#accountAvatar"))setAvatar($("#accountAvatar"),p.name||"M",p.avatar_url||"");
  if($("#accountPageAvatar"))setAvatar($("#accountPageAvatar"),p.name||"M",p.avatar_url||"");
  setAccountLabel();
}
function renderEmpty(){
  $("#messages").innerHTML='<section class="hero"><h1>무엇을 도와드릴까요?</h1><p>질문, 학습, 창작, 분석, 번역까지 하나의 대화에서 이어가세요.</p><div class="cards">'+
  '<button class="card" data-q="최신 중요한 소식을 찾아서 정리해줘"><b>최신 정보</b><span>필요할 때만 웹 검색</span></button>'+
  '<button class="card" data-q="새로운 게임 아이디어를 하나 구체적으로 만들어줘"><b>아이디어</b><span>게임과 프로젝트 아이디어 발전</span></button>'+
  '<button class="card" data-q="어려운 개념을 중학생도 이해하게 설명해줘"><b>학습</b><span>복잡한 내용을 쉽게 이해</span></button>'+
  '<button class="card" data-q="자연스러운 한국어 글을 작성해줘"><b>글쓰기</b><span>문장과 콘텐츠를 함께 작성</span></button></div></section>';
  document.querySelectorAll("[data-q]").forEach(x=>x.onclick=()=>ask(x.dataset.q));
}
function normalizeMarkdown(text){
  return String(text||"").split(/(```[\\s\\S]*?```)/g).map((part,i)=>i%2?part:part.replace(/\\([*_#~\[\]])/g,"$1")).join("");
}
function renderMarkdown(text){
  const src=normalizeMarkdown(text);const lines=src.split("\n"),out=[];let i=0;
  const esc=v=>escapeHtml(v);const inline=v=>{let s=esc(v),links=[];s=s.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,(_,label,url)=>{const i=links.push("<a href=\""+url+"\" target=\"_blank\" rel=\"noopener noreferrer nofollow\">"+label+"</a>")-1;return "\u0000L"+i+"\u0000"});s=s.replace(/(https?:\/\/[^\s<]+)/g,'<a href="$1" target="_blank" rel="noopener noreferrer nofollow">$1</a>');s=s.replace(/`([^`\n]+)`/g,"<code>$1</code>");s=s.replace(/(\*\*|__)(.+?)\1/g,"<strong>$2</strong>");s=s.replace(/~~(.+?)~~/g,"<del>$1</del>");s=s.replace(/(^|[^\\w])\*([^*\n]+)\*(?!\*)/g,"$1<em>$2</em>");s=s.replace(/\u0000L(\d+)\u0000/g,(_,i)=>links[Number(i)]);return s};
  while(i<lines.length){const line=lines[i];if(!line.trim()){i++;continue}
    if(/^```/.test(line.trim())){const lang=(line.trim().slice(3).trim()||"text").replace(/[^A-Za-z0-9_+#.-]/g,""),code=[];i++;while(i<lines.length&&!/^```/.test(lines[i].trim())){code.push(lines[i]);i++}if(i<lines.length)i++;out.push("<div class='code-shell'><div class='code-head'><span>"+esc(lang)+"</span><button type='button' class='code-copy'>복사</button></div><pre><code>"+esc(code.join("\n"))+"</code></pre></div>");continue}
    let m=line.match(/^(#{1,6})\s+(.+)$/);if(m){const n=m[1].length;out.push("<h"+n+">"+inline(m[2])+"</h"+n+">");i++;continue}
    if(/^[-*+]\s+/.test(line)){const b=[];while(i<lines.length&&/^[-*+]\s+/.test(lines[i])){b.push(lines[i].replace(/^[-*+]\s+/,""));i++}out.push("<ul>"+b.map(x=>"<li>"+inline(x)+"</li>").join("")+"</ul>");continue}
    if(/^\d+\.\s+/.test(line)){const b=[];while(i<lines.length&&/^\d+\.\s+/.test(lines[i])){b.push(lines[i].replace(/^\d+\.\s+/,""));i++}out.push("<ol>"+b.map(x=>"<li>"+inline(x)+"</li>").join("")+"</ol>");continue}
    if(/^>\s?/.test(line)){const b=[];while(i<lines.length&&/^>\s?/.test(lines[i])){b.push(lines[i].replace(/^>\s?/,""));i++}out.push("<blockquote>"+b.map(inline).join("<br>")+"</blockquote>");continue}
    if(i+1<lines.length&&line.includes("|")&&lines[i+1].includes("|")){const h=line.split("|").slice(1,-1),sep=lines[i+1].split("|").slice(1,-1);if(h.length&&h.length===sep.length&&sep.every(x=>/^\s*:?-{3,}:?\s*$/.test(x))){let html="<div class='md-table-wrap'><table><thead><tr>"+h.map(x=>"<th>"+inline(x.trim())+"</th>").join("")+"</tr></thead><tbody>";i+=2;while(i<lines.length&&lines[i].includes("|")&&lines[i].trim()){const c=lines[i].split("|").slice(1,-1);if(c.length!==h.length)break;html+="<tr>"+c.map(x=>"<td>"+inline(x.trim())+"</td>").join("")+"</tr>";i++}out.push(html+"</tbody></table></div>");continue}}
    const p=[line];i++;while(i<lines.length&&lines[i].trim()&&!/^(#{1,6})\s+/.test(lines[i])&&!/^```/.test(lines[i].trim())&&!/^[-*+]\s+/.test(lines[i])&&!/^\d+\.\s+/.test(lines[i])&&!/^>\s?/.test(lines[i])){p.push(lines[i]);i++}out.push("<p>"+p.map(inline).join("<br>")+"</p>");
  }return out.join("");
}
function addCodeCopy(pre){
  if(pre.querySelector(".code-copy"))return;
  pre.classList.add("code-block");
  const button=document.createElement("button");button.className="code-copy";button.type="button";button.textContent="복사";
  button.onclick=async()=>{try{await navigator.clipboard.writeText(pre.querySelector("code")?.textContent||"");button.textContent="복사됨";setTimeout(()=>button.textContent="복사",1200)}catch{button.textContent="복사 실패"}};
  pre.appendChild(button);
}
function renderBubble(el,text){
  el.innerHTML=renderMarkdown(text);
  el.querySelectorAll(".code-copy").forEach(button=>{button.onclick=async()=>{const code=button.closest(".code-shell")?.querySelector("pre code")?.textContent||button.closest("pre")?.querySelector("code")?.textContent||"";await copyText(code,button)}});
}
function add(role,text,sources=[],feedbackKey=""){
  const e=document.createElement("article");e.className="msg "+role;
  const name=role==="user"?(profile.name||user?.name||"나"):"Mirae";
  e.innerHTML='<div class="msg-id"><div class="avatar"></div><b class="msg-name">'+escapeHtml(name)+'</b></div><div class="wrap"><div class="bubble"></div></div>';
  const avatar=e.querySelector(".avatar");
  if(role==="user")setAvatar(avatar,name,profile.avatar_url||"");else avatar.textContent="M";
  if(role==="assistant")renderBubble(e.querySelector(".bubble"),text);else e.querySelector(".bubble").textContent=text;
  if(role==="assistant"&&sources.length)renderSources(e,sources);
  if(role==="assistant"&&feedbackKey)addMessageActions(e,feedbackKey,text);
  $("#messages").appendChild(e);e.scrollIntoView({behavior:"smooth",block:"end"});return e;
}
async function copyText(text,button){
  try{await navigator.clipboard.writeText(text);button.textContent="복사됨";setTimeout(()=>button.textContent="복사",1200)}catch{button.textContent="복사 실패"}
}
function addMessageActions(e,key,text){
  const wrap=e.querySelector(".wrap");
  const actions=document.createElement("div");actions.className="message-actions";
  const copy=document.createElement("button");copy.className="message-action";copy.textContent="복사";copy.onclick=()=>copyText(text,copy);
  const like=document.createElement("button");like.className="message-action feedback";like.dataset.value="like";like.textContent="좋아요";
  const dislike=document.createElement("button");dislike.className="message-action feedback";dislike.dataset.value="dislike";dislike.textContent="싫어요";
  [like,dislike].forEach(btn=>btn.onclick=async()=>{actions.querySelectorAll(".feedback").forEach(x=>x.classList.remove("selected"));btn.classList.add("selected");if(user)try{await req("/feedback",{method:"PUT",body:JSON.stringify({feedback:btn.dataset.value,message_hash:key,conversation_id:currentId})})}catch{}});
  actions.append(copy,like,dislike);wrap.appendChild(actions);
}
function renderSources(e,sources){
  let box=e.querySelector(".sources");
  if(!box){box=document.createElement("div");box.className="sources";e.querySelector(".wrap").appendChild(box)}
  box.innerHTML="";
  sources.forEach((s,i)=>{const a=document.createElement("a");a.href=s.url;a.target="_blank";a.rel="noopener noreferrer nofollow";a.className="source-card";const host=(()=>{try{return new URL(s.url).hostname.replace(/^www\./,"")}catch{return "source"}})();a.innerHTML="<span class=\"source-index\">"+(i+1)+"</span><span class=\"source-copy\"><b>"+escapeHtml(s.title)+"</b><small>"+escapeHtml(host)+(s.published?" · "+escapeHtml(s.published):"")+"</small></span><span class=\"source-arrow\">↗</span>";box.appendChild(a)});
}
function createAssistant(){
  const e=document.createElement("article");e.className="msg assistant";
  e.innerHTML='<div class="msg-id"><div class="avatar">M</div><b class="msg-name">Mirae</b></div><div class="wrap"><div class="process"><button class="process-toggle" type="button"><span class="process-dot"></span><span class="process-label">질문 분석 중</span><span class="process-chevron">⌄</span></button><div class="process-details"></div></div><div class="bubble"></div></div>';
  const process=e.querySelector(".process"),toggle=e.querySelector(".process-toggle");
  toggle.onclick=()=>{process.classList.toggle("expanded");toggle.querySelector(".process-chevron").textContent=process.classList.contains("expanded")?"⌃":"⌄"};
  $("#messages").appendChild(e);e.scrollIntoView({behavior:"smooth",block:"end"});
  return {e:e,bubble:e.querySelector(".bubble"),process:process,label:e.querySelector(".process-label"),details:e.querySelector(".process-details"),logs:[],raw:""};
}
function addProcessLog(box,label){
  const now=new Date().toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
  if(box.logs[box.logs.length-1]?.label===label)return;
  box.logs.push({label:label,time:now});
  box.details.innerHTML=box.logs.map(x=>`<div class="process-log"><span>${escapeHtml(x.label)}</span><time>${x.time}</time></div>`).join("");
}
function stage(box,label){box.label.textContent=label;box.process.classList.remove("done");addProcessLog(box,label)}
function finish(box){
  box.label.textContent="답변 완료";box.process.classList.add("done");addProcessLog(box,"답변 완료");
  if(!box.e.querySelector(".message-actions"))addMessageActions(box.e,simpleHash(box.raw||box.bubble.textContent),box.raw||box.bubble.textContent);
}
function restoreServer(rows,convs=[]){
  const grouped=[],by={},titles=Object.fromEntries(convs.map(x=>[x.id,x.title]));
  for(const x of rows){
    const id=x.conversation_id||("legacy-"+x.id);
    if(!by[id])by[id]={id:id,title:x.conversation_title||titles[id]||"새 대화",messages:[]};
    by[id].messages.push({role:x.role,content:x.content,sources:x.sources||[],feedback_key:x.role==="assistant"?simpleHash(x.content):""});
  }
  chats=Object.values(by).slice(-100);localStorage.setItem("mirae-local",JSON.stringify(chats));
}
function renderHistory(){
  const h=$("#history");h.innerHTML="";
  [...chats].reverse().forEach(c=>{
    const row=document.createElement("div");row.className="history-row";
    const b=document.createElement("button");b.className="btn history-main";b.textContent=c.title||"새 대화";b.onclick=()=>loadChat(c.id);
    const menu=document.createElement("button");menu.className="history-menu";menu.type="button";menu.textContent="⋯";menu.title="대화 메뉴";
    menu.onclick=e=>{e.stopPropagation();openConversationMenu(row,c)};
    row.append(b,menu);h.appendChild(row);
  });
}
function openConversationMenu(row,c){
  document.querySelectorAll(".conversation-menu").forEach(x=>x.remove());
  const menu=document.createElement("div");menu.className="conversation-menu";
  const rename=document.createElement("button");rename.textContent="이름 변경";rename.onclick=()=>renameConversation(c);
  const del=document.createElement("button");del.textContent="삭제";del.className="delete-menu";del.onclick=()=>deleteConversation(c);
  menu.append(rename,del);row.appendChild(menu);
}
async function renameConversation(c){
  const title=prompt("새 대화 이름",c.title||"새 대화");if(title===null)return;
  const value=title.trim();if(!value)return;
  try{
    if(user)await req("/conversations/"+encodeURIComponent(c.id),{method:"PUT",body:JSON.stringify({title:value})});
    c.title=value;currentTitle=value;renderHistory();saveLocal();if(c.id===currentId)$("#title").textContent=value;
  }catch(e){alert(e.message)}
}
async function deleteConversation(c){
  if(!confirm("이 대화를 삭제할까요? 삭제하면 대화 내용도 함께 삭제됩니다."))return;
  try{
    if(user)await req("/conversations/"+encodeURIComponent(c.id),{method:"DELETE"});
    chats=chats.filter(x=>x.id!==c.id);localStorage.setItem("mirae-local",JSON.stringify(chats));
    if(c.id===currentId)newChat(false);else renderHistory();
  }catch(e){alert(e.message)}
}
function loadChat(id){
  const c=chats.find(x=>x.id===id);if(!c)return;
  currentId=id;currentTitle=c.title||"새 대화";current=c.messages||[];$("#messages").innerHTML="";
  current.forEach(m=>add(m.role,m.content,m.sources||[],m.feedback_key||""));
  $("#title").textContent=currentTitle;closeSidebar();
}
function newChat(save=true){
  if(save&&current.length)saveLocal();
  current=[];currentId=crypto.randomUUID();currentTitle="새 대화";$("#messages").innerHTML="";renderEmpty();$("#title").textContent="새 대화";closeSidebar();
}
function saveLocal(){
  let c=chats.find(x=>x.id===currentId);
  if(!c){c={id:currentId,title:currentTitle||"새 대화",messages:[]};chats.push(c)}
  c.messages=current;c.title=currentTitle||c.title||"새 대화";
  chats=chats.slice(-100);localStorage.setItem("mirae-local",JSON.stringify(chats));renderHistory();
}
function parseSSEBlock(block,box,state){
  let ev="message",data="";
  block.split("\n").forEach(line=>{if(line.startsWith("event:"))ev=line.slice(6).trim();if(line.startsWith("data:"))data+=line.slice(5).trim()});
  if(!data)return;let obj;try{obj=JSON.parse(data)}catch{return}
  if(ev==="stage")stage(box,obj.label||"처리 중");
  else if(ev==="sources"){state.sources=obj.sources||[];if(state.sources.length){addProcessLog(box,"웹 검색 완료 · "+state.sources.length+"개 결과");renderSources(box.e,state.sources)}}
  else if(ev==="conversation"){state.conversation_id=obj.id||"";state.title=obj.title||"새 대화";currentTitle=state.title;const c=chats.find(x=>x.id===state.conversation_id);if(c)c.title=state.title;$("#title").textContent=state.title}
  else if(ev==="delta"){box.raw=(box.raw||"")+(obj.text||"");box.bubble.textContent=box.raw;box.e.scrollIntoView({behavior:"smooth",block:"end"})}
  else if(ev==="done"){state.done=true;if(obj.conversation_id)state.conversation_id=obj.conversation_id;renderBubble(box.bubble,box.raw||"");finish(box)}
  else if(ev==="error")throw Error(obj.message||"생성 중 오류가 발생했습니다.");
}
async function streamAsk(text,box){
  const body={message:text,history:current.slice(0,-1).slice(-12),personality:settings.personality,instructions:settings.instructions,web_search:settings.web_search,temperature:settings.temperature,max_tokens:2600,conversation_id:currentId};
  const r=await fetch(API+"/chat/stream",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if(!r.ok)throw Error("스트리밍 요청에 실패했습니다.");
  const type=r.headers.get("content-type")||"";
  if(!type.includes("text/event-stream")){const d=await r.json();box.raw=d.reply||"";renderBubble(box.bubble,box.raw);if(d.sources?.length)renderSources(box.e,d.sources);finish(box);return d}
  const reader=r.body.getReader(),dec=new TextDecoder();let buffer="",state={sources:[]};
  while(true){
    const v=await reader.read();if(v.done)break;buffer+=dec.decode(v.value,{stream:true});
    const blocks=buffer.split("\n\n");buffer=blocks.pop()||"";blocks.forEach(b=>parseSSEBlock(b,box,state));
  }
  if(buffer.trim())parseSSEBlock(buffer,box,state);
  return {reply:box.raw||"",sources:state.sources,conversation_id:state.conversation_id,title:state.title||currentTitle};
}
async function ask(text){
  text=text.trim();if(!text)return;
  if(!current.length)$("#messages").innerHTML="";
  add("user",text);current.push({role:"user",content:text});$("#title").textContent=currentTitle==="새 대화"?"대화 중":currentTitle;$("#input").value="";$("#send").disabled=true;
  const box=createAssistant();
  try{const d=await streamAsk(text,box);current.push({role:"assistant",content:d.reply,sources:d.sources||[]});saveLocal()}
  catch(e){box.bubble.textContent="오류가 발생했습니다. "+e.message;finish(box);current.pop()}
  finally{$("#send").disabled=false;$("#input").focus()}
}
function openAuth(mode="login"){authMode=mode;pendingSignup=null;renderAuth();$("#authOverlay").classList.remove("hidden");$("#email").focus()}
function closeAuth(){$("#authOverlay").classList.add("hidden")}
function renderAuth(){
  const verify=authMode==="verify",signup=authMode==="signup";
  $("#authTitle").textContent=verify?"이메일 인증":signup?"Mirae 계정 만들기":"Mirae에 로그인";
  $("#authDesc").textContent=verify?"이메일로 받은 6자리 인증 코드를 입력하세요.":signup?"회원가입을 완료하려면 이메일 인증이 필요합니다.":"계정으로 대화 기록과 설정을 동기화하세요.";
  $("#nameField").classList.toggle("hidden",!signup);$("#passwordField").classList.toggle("hidden",verify);$("#codeField").classList.toggle("hidden",!verify);$("#verifyNote").classList.toggle("hidden",!verify);
  $("#authSubmit").textContent=verify?"인증하고 가입 완료":signup?"인증 코드 보내기":"로그인";
  $("#resendCode").classList.toggle("hidden",!verify);$("#authSwitch").classList.toggle("hidden",verify);
  $("#authSwitch").textContent=signup?"이미 계정이 있다면 로그인":"처음이라면 회원가입";$("#authMsg").textContent="";
}
async function finishLogin(d){
  user=d.user;closeAuth();setAccountLabel();await Promise.all([loadSettings(),loadProfile(),loadHistory()]);fillSettings();newChat(false);
}
$("#authSubmit").onclick=async()=>{
  $("#authMsg").textContent="";
  try{
    if(authMode==="signup"){
      pendingSignup={name:$("#name").value.trim(),email:$("#email").value.trim(),password:$("#password").value};
      await req("/auth/signup/request",{method:"POST",body:JSON.stringify(pendingSignup)});
      authMode="verify";$("#email").value=pendingSignup.email;renderAuth();$("#code").focus();startResendTimer();
    }else if(authMode==="verify"){
      const d=await req("/auth/signup/verify",{method:"POST",body:JSON.stringify({email:pendingSignup.email,code:$("#code").value.trim()})});await finishLogin(d);
    }else{
      const d=await req("/auth/login",{method:"POST",body:JSON.stringify({email:$("#email").value.trim(),password:$("#password").value})});await finishLogin(d);
    }
  }catch(e){$("#authMsg").textContent=e.message}
};
$("#authSwitch").onclick=()=>{authMode=authMode==="login"?"signup":"login";pendingSignup=null;renderAuth()};
$("#closeAuth").onclick=closeAuth;
function startResendTimer(){
  clearInterval(resendTimer);let left=60;$("#resendCode").disabled=true;$("#resendCode").textContent="인증 코드 다시 보내기 ("+left+")";
  resendTimer=setInterval(()=>{left--;$("#resendCode").textContent=left?"인증 코드 다시 보내기 ("+left+")":"인증 코드 다시 보내기";if(!left){clearInterval(resendTimer);$("#resendCode").disabled=false}},1000);
}
$("#resendCode").onclick=async()=>{try{await req("/auth/signup/request",{method:"POST",body:JSON.stringify(pendingSignup)});$("#authMsg").textContent="새 인증 코드를 보냈습니다.";startResendTimer()}catch(e){$("#authMsg").textContent=e.message}};
async function saveSettings(){
  settings={theme:$("#theme").value,personality:$("#personality").value,instructions:$("#instructions").value,web_search:$("#web").value==="true",temperature:settings.temperature||.7};
  applyTheme();if(user)try{await req("/settings",{method:"PUT",body:JSON.stringify(settings)})}catch(e){console.error(e)}
}
["theme","personality","instructions","web"].forEach(id=>$("#"+id).onchange=saveSettings);
async function openSettings(page="general"){
  if(!user){openAuth("login");return}
  await Promise.all([loadSettings(),loadProfile()]);fillSettings();setAccountLabel();$("#settingsOverlay").classList.remove("hidden");selectPage(page);
}
function selectPage(page){
  document.querySelectorAll(".nav-btn").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
  document.querySelectorAll(".page").forEach(p=>p.classList.toggle("hidden",p.id!=="page-"+page));
  const b=document.querySelector('.nav-btn[data-page="'+page+'"]');$("#settingTitle").textContent=b?b.textContent:"설정";$("#settingEyebrow").textContent=(b?b.textContent:"설정").toUpperCase();
  if(page==="skills")loadSkills();if(page==="memory")loadMemories();
}
document.querySelectorAll(".nav-btn").forEach(b=>b.onclick=()=>selectPage(b.dataset.page));
$("#closeSettings").onclick=()=>$("#settingsOverlay").classList.add("hidden");
$("#settingsMenu").onclick=()=>openSettings("general");$("#skillsMenu").onclick=()=>openSettings("skills");$("#openKeys").onclick=()=>location.href="/api-keys";$("#openDocs").onclick=()=>location.href="/api-docs";
$("#account").onclick=()=>user?openSettings("profile"):openAuth("login");
$("#saveProfile").onclick=async()=>{
  try{
    const p=await req("/profile",{method:"PUT",body:JSON.stringify({name:$("#profileName").value,bio:$("#profileBio").value,birth_date:$("#profileBirth").value||null,avatar_url:$("#profileAvatarUrl").value})});
    user.name=p.name;setAccountLabel();applyProfile(p);$("#globalStatus").textContent="프로필이 저장되었습니다.";
  }catch(e){alert(e.message)}
};
$("#logout").onclick=async()=>{try{await req("/auth/logout",{method:"POST"})}catch{}user=null;setAccountLabel();$("#settingsOverlay").classList.add("hidden");newChat(false)};
$("#clearLocal").onclick=()=>{localStorage.removeItem("mirae-local");chats=[];newChat(false)};
async function loadMemories(){
  if(!user)return;
  const box=$("#memoryList");box.innerHTML="<div class='muted'>메모리 불러오는 중…</div>";
  try{
    const list=await req("/memories");box.innerHTML="";
    if(!list.length){box.innerHTML="<div class='muted'>저장된 메모리가 없습니다.</div>";return}
    list.forEach(m=>{
      const card=document.createElement("div");card.className="memory-card";
      card.innerHTML='<div class="memory-content">'+escapeHtml(m.content)+'</div><button class="danger memory-delete" type="button">삭제</button>';
      card.querySelector(".memory-delete").onclick=async()=>{try{await req("/memories/"+m.id,{method:"DELETE"});loadMemories()}catch(e){alert(e.message)}};
      box.appendChild(card);
    });
  }catch(e){box.innerHTML='<div class="muted">'+escapeHtml(e.message)+'</div>'}
}
$("#memoryForm").onsubmit=async e=>{
  e.preventDefault();
  const content=$("#memoryContent").value.trim();if(!content)return;
  try{await req("/memories",{method:"POST",body:JSON.stringify({content:content})});$("#memoryContent").value="";loadMemories()}catch(err){alert(err.message)}
};
$("#registerSkillPrompt").onclick=async()=>{
  const prompt=$("#skillPrompt").value.trim();if(!prompt)return;
  const btn=$("#registerSkillPrompt");btn.disabled=true;btn.textContent="스킬 구성 중…";
  try{await req("/skills/from-prompt",{method:"POST",body:JSON.stringify({prompt:prompt})});$("#skillPrompt").value="";btn.textContent="등록 완료";setTimeout(()=>btn.textContent="프롬프트로 등록",1200);loadSkills()}catch(err){alert(err.message);btn.textContent="프롬프트로 등록"}finally{btn.disabled=false}
};
async function loadSkills(){
  if(!user)return;const box=$("#skillList");box.innerHTML="<div class='muted'>스킬 불러오는 중…</div>";
  try{
    const list=await req("/skills");box.innerHTML="";
    if(!list.length){box.innerHTML="<div class='muted'>등록된 스킬이 없습니다.</div>";return}
    list.forEach(s=>{
      const card=document.createElement("div");card.className="skill-card";
      card.innerHTML='<div class="row"><div class="name">'+escapeHtml(s.name)+'</div><span class="muted">'+escapeHtml(s.method)+'</span></div><div class="desc">'+escapeHtml(s.description||"설명 없음")+'</div><div class="url">'+escapeHtml(s.url)+'</div><div class="skill-actions"><button class="outline run">실행</button><button class="danger del">삭제</button></div>';
      card.querySelector(".run").onclick=async()=>{
        const raw=prompt("파라미터 JSON을 입력하세요. 예: {\"city\":\"천안\"}","{}");if(raw===null)return;
        try{const p=JSON.parse(raw);const r=await req("/skills/"+s.id+"/run",{method:"POST",body:JSON.stringify({params:p})});alert("HTTP "+r.result.status+"\n\n"+r.result.body.slice(0,4000))}catch(e){alert(e.message)}
      };
      card.querySelector(".del").onclick=async()=>{if(!confirm("'"+s.name+"' 스킬을 삭제할까요?"))return;try{await req("/skills/"+s.id,{method:"DELETE"});loadSkills()}catch(e){alert(e.message)}};
      box.appendChild(card);
    });
  }catch(e){box.innerHTML="<div class='muted'>"+escapeHtml(e.message)+"</div>"}
}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
$("#skillForm").onsubmit=async e=>{
  e.preventDefault();
  try{
    const names=$("#skillParams").value.split(",").map(x=>x.trim()).filter(Boolean);
    let body=$("#skillBody").value.trim();
    const method=$("#skillMethod").value;
    if(!body&&names.length&&["POST","PUT","PATCH"].includes(method))body=JSON.stringify(Object.fromEntries(names.map(n=>[n,"{{"+n+"}}"])),null,2);
    await req("/skills",{method:"POST",body:JSON.stringify({name:$("#skillName").value,description:$("#skillDescription").value,url:$("#skillUrl").value,method:method,headers:$("#skillHeaders").value,body:body})});
    e.target.reset();$("#skillMethod").value="GET";$("#globalStatus").textContent="스킬이 등록되었습니다. 채팅에서 /skill 이름 {…}으로 실행할 수 있습니다.";loadSkills();
  }catch(err){alert(err.message)}
};
$("#form").onsubmit=e=>{e.preventDefault();ask($("#input").value)};
$("#input").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask(e.target.value)}};
$("#input").oninput=e=>{e.target.style.height="auto";e.target.style.height=Math.min(e.target.scrollHeight,160)+"px"};
$("#newChat").onclick=()=>newChat();$("#mobileNew").onclick=()=>newChat();$("#mobileMenu").onclick=()=>$("#sidebar").classList.toggle("open");
function closeSidebar(){$("#sidebar").classList.remove("open")}
$("#chat").onclick=closeSidebar;
const mq=matchMedia("(prefers-color-scheme:dark)");if(mq.addEventListener)mq.addEventListener("change",()=>{if(settings.theme==="system")applyTheme()});
renderAuth();boot();
