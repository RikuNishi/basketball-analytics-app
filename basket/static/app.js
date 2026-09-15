"use strict";
const $ = id => document.getElementById(id);
const state = {session:null,frames:[],predictions:{},selected:null,filter:"all",busy:false,setup:{},region:"rim",image:null};
const video = $("video");
const labels = {made:"成功",missed:"失敗",unknown:"判定不能"};
const icons = {made:"✓",missed:"×",unknown:"−"};
const edges = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[24,26],[26,28]];
const pad = value => String(value).padStart(2,"0");
const formatTime = value => `${pad(Math.floor((value||0)/60))}:${pad(Math.floor((value||0)%60))}`;
const preciseTime = value => `${formatTime(value)}.${String(Math.round((value%1)*100)).padStart(2,"0")}`;
const fileUrl = name => `/api/sessions/${state.session.id}/files/${name}`;
const apiUrl = suffix => `/api/sessions/${state.session.id}${suffix}`;
let toastTimer;
function toast(message){const dialog=document.querySelector("dialog[open]");if(dialog){let error=dialog.querySelector(".dialog-error");if(!error){error=document.createElement("p");error.className="dialog-error";error.setAttribute("role","alert");(dialog.querySelector(".dialog-actions")||dialog.lastElementChild).before(error);}error.textContent=message;error.scrollIntoView({block:"nearest"});return;}$("toast").textContent=message;$("toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").hidden=true,4500);}
async function api(url,options={}){const response=await fetch(url,options);if(!response.ok){let message=`リクエストに失敗しました (${response.status})`;try{const data=await response.json();message=typeof data.detail==="string"?data.detail:JSON.stringify(data.detail);}catch{}throw new Error(message);}return response.json();}
function jsonOptions(method,body){return {method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)};}
function notify(message,progress){const box=$("notice");box.replaceChildren(document.createTextNode(message));box.hidden=!message;if(progress!==undefined){const bar=document.createElement("progress");bar.max=1;bar.value=progress;box.append(bar);}}
function action(fn){return async(...args)=>{try{await fn(...args);}catch(error){toast(error.message);}};}
function nearestFrame(t){let low=0,high=state.frames.length-1;while(low<high){const mid=Math.floor((low+high+1)/2);if(state.frames[mid].t<=t)low=mid;else high=mid-1;}return state.frames[low];}
function shot(){return state.session?.shots.find(s=>s.id===state.selected);}
function setBusy(value){state.busy=value;for(const id of ["upload-button","settings","export-button","edit-shot","nav-sessions"]){$(id).disabled=value||(!state.session&&["settings","export-button","edit-shot"].includes(id));}}

async function loadSession(id){
  video.pause();state.session=await api(`/api/sessions/${id}`);state.frames=[];state.predictions={};state.selected=null;state.filter="all";
  $("shot-filter").value="all";switchPanel("shots");
  const s=state.session;$("session-name").textContent=s.is_demo?"フリースロー":s.name;$("demo-badge").hidden=!s.is_demo;
  const date=new Date(s.created_at).toLocaleDateString("ja-JP",{year:"numeric",month:"2-digit",day:"2-digit"});
  $("session-meta").textContent=`${date}  ·  ${s.video.width} × ${s.video.height} / ${s.video.fps.toFixed(0)} fps  ·  ${formatTime(s.video.duration_s)}`;
  $("session-date").textContent=`${date} · ${formatTime(s.video.duration_s)}`;
  $("timeline").max=s.video.duration_s;$("video-stage").style.aspectRatio=`${s.video.width}/${s.video.height}`;
  $("overlay").width=s.video.width;$("overlay").height=s.video.height;
  $("video-tag").textContent="合成映像";$("video-tag").hidden=!s.is_demo;
  $("data-note").textContent=s.is_demo?"デモの映像・数値は合成データです。":"2D計測 · 成否は自動推定を目視で確認してください。";
  $("empty-video").hidden=s.status==="ready";
  if(s.status==="ready"){
    state.frames=await api(`/api/sessions/${id}/frames`);state.predictions=await api(`/api/sessions/${id}/predictions`);
    video.src=fileUrl("preview.mp4")+`?v=${s.revision}`;video.load();
    state.selected=s.shots.find(x=>!x.deleted)?.id??s.shots[0]?.id??null;
    notify("");
    $("video-quality").textContent=`骨格取得 ${s.quality.pose_coverage}% · ボール検出 ${s.quality.ball_coverage}%`;
  }else{
    video.removeAttribute("src");video.load();video.poster=fileUrl("thumbnail.jpg");
    notify("リングと人物を指定して、解析を始めてください。");
    $("video-quality").textContent="解析前";
  }
  renderStats();renderShots();renderDetail();drawCharts();drawOverlay(0);updatePlayer();setBusy(state.busy);
}
function renderStats(){const s=state.session.summary;for(const key of ["attempts","made","missed","unknown"]){$(key).textContent=s[key];}$("rate").replaceChildren(document.createTextNode(s.percentage===null?"—":String(s.percentage)));if(s.percentage!==null){const unit=document.createElement("small");unit.textContent="%";$("rate").append(unit);}$("denominator").textContent=`判定済み ${s.denominator} 本が対象`;
  $("shot-count").textContent=s.attempts;
}
function renderShots(){
  const list=$("shot-list"),scrollLeft=list.scrollLeft;list.replaceChildren();const shots=state.session.shots.filter(s=>state.filter==="deleted"?s.deleted:!s.deleted&&(state.filter==="all"||s.outcome===state.filter));
  if(!shots.length){const empty=document.createElement("p");empty.className="empty-list";empty.textContent=state.session.status!=="ready"?"解析後にシュートが表示されます。":"該当するシュートはありません。";list.append(empty);return;}
  for(const s of shots){const button=document.createElement("button");button.className=`shot-row ${state.selected===s.id?"selected":""}`;button.setAttribute("aria-label",`シュート ${s.id} ${labels[s.outcome]} ${preciseTime(s.release_s)}`);
    button.setAttribute("aria-pressed",String(state.selected===s.id));button.title=s.reviewed?"確認済み":"";
    const number=document.createElement("span");number.className="shot-number";number.textContent=pad(s.id);
    const title=document.createElement("span");title.className="shot-title";title.textContent=preciseTime(s.release_s);
    const result=document.createElement("span");result.className=`outcome ${s.outcome}`;result.textContent=`${icons[s.outcome]} ${s.deleted?"除外":labels[s.outcome]}`;button.append(number,title,result);button.onclick=()=>selectShot(s.id);list.append(button);
  }
  list.scrollLeft=scrollLeft;
}
function selectShot(id){video.pause();state.selected=id;const s=shot();if(s&&video.src){video.currentTime=Math.max(0,s.release_s-.4);}renderShots();renderDetail();drawCharts();}
function renderDetail(){const s=shot();$("selected-detail").hidden=!s;$("comparison-shot").textContent=s?`シュート ${pad(s.id)}`:"シュート未選択";if(!s)return;$("detail-name").textContent=`シュート ${pad(s.id)}`;$("detail-release").textContent=`リリース ${s.release_s.toFixed(2)} 秒`;
  const frame=nearestFrame(s.release_s),a=frame?.angles||{};for(const [id,key] of [["elbow-value","elbow_deg"],["knee-value","knee_deg"],["trunk-value","trunk_deg"]]){$(id).textContent=a[key]===null||a[key]===undefined?"—":`${Math.round(a[key])}°`;}
  $("shot-reason").textContent=s.reviewed?`確認済み${s.note?` · ${s.note}`:""}`:s.reason;
}
function drawOverlay(t){
  const canvas=$("overlay"),ctx=canvas.getContext("2d");ctx.clearRect(0,0,canvas.width,canvas.height);if(!state.frames.length)return;
  const frame=nearestFrame(t);if(!frame||Math.abs(frame.t-t)>.15)return;const scale=canvas.width/960;ctx.lineWidth=2*scale;
  if($("toggle-rim").checked){const r=state.session.config.rim;ctx.strokeStyle="#f0f3b7";ctx.setLineDash([5*scale,4*scale]);ctx.strokeRect(r.x*canvas.width,r.y*canvas.height,r.w*canvas.width,r.h*canvas.height);ctx.setLineDash([]);}
  if($("toggle-ball").checked){const first=Math.max(0,frame.index-Math.ceil(state.session.video.fps*2));for(let i=first+1;i<=frame.index;i++){const a=state.frames[i-1],b=state.frames[i];if(!a.ball||!b.ball||b.t-a.t>state.session.config.max_gap_s)continue;const predicted=a.ball.source!=="detected"||b.ball.source!=="detected";ctx.strokeStyle=predicted?"#d8ded1":"#f3c86f";ctx.setLineDash(predicted?[4*scale,5*scale]:[]);ctx.globalAlpha=.35+.65*(i-first)/Math.max(1,frame.index-first);ctx.beginPath();ctx.moveTo(a.ball.x,a.ball.y);ctx.lineTo(b.ball.x,b.ball.y);ctx.stroke();}ctx.setLineDash([]);ctx.globalAlpha=1;
    if(frame.ball){ctx.strokeStyle=frame.ball.source==="detected"?"#f9d684":"#d8ded1";ctx.beginPath();ctx.arc(frame.ball.x,frame.ball.y,frame.ball.radius+5*scale,0,Math.PI*2);ctx.stroke();}}
  const forecast=state.predictions[frame.index];
  if($("toggle-prediction").checked&&forecast?.length){
    ctx.strokeStyle="#0789c7";ctx.lineWidth=4*scale;ctx.setLineDash([7*scale,5*scale]);ctx.beginPath();
    forecast.forEach((p,i)=>ctx[i?"lineTo":"moveTo"](...p));ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle="#0789c7";ctx.font=`${14*scale}px sans-serif`;ctx.fillText("PREDICTED / 2D",12*scale,canvas.height-16*scale);
  }
  if($("toggle-pose").checked&&frame.pose){ctx.strokeStyle="#d7f3b8";ctx.fillStyle="#f6ffeb";for(const [a,b] of edges){if(frame.pose[a]?.[2]<.5||frame.pose[b]?.[2]<.5)continue;ctx.beginPath();ctx.moveTo(...frame.pose[a].slice(0,2));ctx.lineTo(...frame.pose[b].slice(0,2));ctx.stroke();}for(const p of frame.pose){if(p[2]<.5)continue;ctx.beginPath();ctx.arc(p[0],p[1],3*scale,0,Math.PI*2);ctx.fill();}}
  const active=state.session.shots.find(s=>!s.deleted&&s.start_s<=t&&s.end_s>=t);$("shot-overlay").hidden=!active;if(active){$("shot-overlay").querySelector("strong").textContent=pad(active.id);$("shot-overlay").querySelector(".shot-status").textContent=`${icons[active.outcome]} ${labels[active.outcome]}`;}
}
function updatePlayer(){const t=video.currentTime||0;$("timeline").value=t;$("time").textContent=`${formatTime(t)} / ${formatTime(state.session?.video.duration_s)}`;$("play").textContent=video.paused?"▶":"Ⅱ";$("play").setAttribute("aria-label",video.paused?"再生":"一時停止");const active=state.session?.shots.find(s=>!s.deleted&&s.start_s<=t&&s.end_s>=t);if(active&&active.id!==state.selected){state.selected=active.id;renderShots();renderDetail();drawCharts();}drawOverlay(t);}
function drawCharts(){if(!$("panel-compare").hidden){drawAngles();drawTrajectories();}}
function drawAngles(){
  const c=$("angle-chart"),ctx=c.getContext("2d"),w=c.width,h=c.height;ctx.clearRect(0,0,w,h);
  const key=$("angle-select").value,lo=key==="trunk_deg"?-45:0,hi=key==="trunk_deg"?45:180;
  const X=t=>50+(t+.6)/1.8*(w-72),Y=a=>h-37-(a-lo)/(hi-lo)*(h-65);
  ctx.font="12px Segoe UI";ctx.fillStyle="#747984";ctx.strokeStyle="#e8e9ed";ctx.lineWidth=1;
  for(let v=lo;v<=hi;v+=(hi-lo)/3){ctx.beginPath();ctx.moveTo(44,Y(v));ctx.lineTo(w-15,Y(v));ctx.stroke();ctx.fillText(`${v}°`,9,Y(v)+4);}
  for(const t of [-.5,0,.5,1]){ctx.fillText(`${t===0?"0":t.toFixed(1)} s`,X(t)-13,h-13);}
  ctx.setLineDash([5,5]);ctx.strokeStyle="#c7cbd6";ctx.beginPath();ctx.moveTo(X(0),18);ctx.lineTo(X(0),h-34);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle="#747984";ctx.fillText("リリース",X(0)+6,16);
  for(const s of [...(state.session?.shots||[])].sort((a,b)=>(a.id===state.selected)-(b.id===state.selected))){if(s.deleted||(!$("compare").checked&&s.id!==state.selected))continue;ctx.strokeStyle=s.id===state.selected?"#3c54ce":"#d9dde9";ctx.lineWidth=s.id===state.selected?2.5:1.6;ctx.beginPath();let previous=null;
    for(const f of state.frames){const t=f.t-s.release_s;if(t<-.6||t>1.2)continue;const value=f.angles?.[key];if(value===null||value===undefined){previous=null;continue;}if(!previous||f.t-previous.t>.12)ctx.moveTo(X(t),Y(value));else ctx.lineTo(X(t),Y(value));previous=f;}ctx.stroke();}
  if(!state.frames.length){ctx.fillStyle="#9ca991";ctx.fillText("解析後に角度を表示します",140,105);}
}
let trajectoryCache = new WeakMap();
function trajectoryFor(s){
  const key = `${s.release_s}:${s.end_s}`;
  let cached = trajectoryCache.get(s);
  if(!cached || cached.key!==key){cached={key,...Trajectory.build(state.frames,s,state.session.config.max_gap_s)};trajectoryCache.set(s,cached);}
  return cached;
}
function drawTrajectories(){
  const c=$("trajectory-chart"),ctx=c.getContext("2d"),w=c.width,h=c.height;
  ctx.clearRect(0,0,w,h);
  const paths=(state.session?.shots||[]).filter(s=>!s.deleted&&($("compare").checked||s.id===state.selected))
    .map(s=>({s,...trajectoryFor(s)})).filter(p=>p.origin);
  const all=paths.flatMap(p=>[...p.points,...($("smooth-trajectory").checked?p.curves.flat():[])].map(q=>({x:q.x-p.origin.x,y:q.y-p.origin.y})));
  let minX=0,maxX=100,minY=-80,maxY=20;
  for(const p of all){minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);}
  const scale=Math.min((w-65)/(maxX-minX),(h-58)/(maxY-minY));
  const X=x=>40+(x-minX)*scale,Y=y=>20+(y-minY)*scale;
  ctx.strokeStyle="#e8e9ed";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(30,Y(0));ctx.lineTo(w-14,Y(0));ctx.moveTo(X(0),15);ctx.lineTo(X(0),h-20);ctx.stroke();
  ctx.font="12px Segoe UI";ctx.fillStyle="#747984";ctx.fillText("0",X(0)-12,Y(0)+15);
  for(const p of paths.sort((a,b)=>(a.s.id===state.selected)-(b.s.id===state.selected))){
    const selected=p.s.id===state.selected,color=selected?"#3c54ce":"#b9c0d7";
    ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=selected?2.5:1.4;
    if($("smooth-trajectory").checked)for(const curve of p.curves){ctx.beginPath();curve.forEach((q,i)=>ctx[i?"lineTo":"moveTo"](X(q.x-p.origin.x),Y(q.y-p.origin.y)));ctx.stroke();}
    ctx.globalAlpha=selected?.65:.4;
    for(const q of p.points){ctx.beginPath();ctx.arc(X(q.x-p.origin.x),Y(q.y-p.origin.y),selected?2:1.5,0,Math.PI*2);ctx.fill();}
    ctx.globalAlpha=1;
    const last=p.points.at(-1);if(last)ctx.fillText(pad(p.s.id),Math.min(w-22,X(last.x-p.origin.x)+5),Math.max(12,Y(last.y-p.origin.y)));
  }
  const active=paths.find(p=>p.s.id===state.selected);
  $("trajectory-note").textContent=!active?"リリース付近の実測点が不足しています。":!active.curves.length?"実測点が少ないため、近似線は表示できません。":"リリース直後の実測位置を揃えて表示";
}


$("play").onclick=action(async()=>{if(!state.frames.length)return;if(video.paused)await video.play();else video.pause();});
video.addEventListener("timeupdate",updatePlayer);video.addEventListener("pause",updatePlayer);video.addEventListener("play",updatePlayer);video.addEventListener("loadeddata",()=>{if(shot())video.currentTime=Math.max(0,shot().release_s-.25);updatePlayer();});
video.addEventListener("error",()=>{if(video.getAttribute("src"))toast("動画を再生できません。ページを再読み込みしてください。");});
if("requestVideoFrameCallback" in video){function frameCallback(){updatePlayer();video.requestVideoFrameCallback(frameCallback);}video.requestVideoFrameCallback(frameCallback);}
$("timeline").oninput=()=>{if(state.frames.length)video.currentTime=Number($("timeline").value);updatePlayer();};
for(const [id,direction] of [["prev-frame",-1],["next-frame",1]])$(id).onclick=()=>{if(!state.frames.length)return;video.pause();const frame=nearestFrame(video.currentTime+.0001);const target=state.frames[Math.max(0,Math.min(state.frames.length-1,frame.index+direction))];video.currentTime=target.t;updatePlayer();};
$("speed").onchange=()=>video.playbackRate=Number($("speed").value);
for(const id of ["toggle-pose","toggle-ball","toggle-rim","toggle-prediction"])$(id).onchange=updatePlayer;
$("smooth-trajectory").onchange=drawTrajectories;
$("angle-select").onchange=drawAngles;$("compare").onchange=drawCharts;
$("shot-filter").onchange=()=>{state.filter=$("shot-filter").value;renderShots();};
function switchPanel(name){for(const key of ["shots","compare"]){const active=key===name;$("tab-"+key).setAttribute("aria-selected",String(active));$("tab-"+key).tabIndex=active?0:-1;$("panel-"+key).hidden=!active;}drawCharts();}
for(const name of ["shots","compare"]){$("tab-"+name).onclick=()=>switchPanel(name);$("tab-"+name).onkeydown=event=>{if(["ArrowLeft","ArrowRight","Home","End"].includes(event.key)){event.preventDefault();const target=event.key==="Home"?"shots":event.key==="End"?"compare":name==="shots"?"compare":"shots";switchPanel(target);$("tab-"+target).focus();}};}
$("review-unknown").onclick=()=>{if(!state.session)return;switchPanel("shots");state.filter="unknown";$("shot-filter").value="unknown";renderShots();$("shot-filter").focus({preventScroll:true});};
$("display-button").onclick=()=>{const open=$("display-options").hidden;$("display-options").hidden=!open;$("display-button").setAttribute("aria-expanded",String(open));};
function showDialog(id){video.pause();document.querySelectorAll("dialog[open]").forEach(d=>d.close());document.querySelectorAll(".dialog-error").forEach(e=>e.remove());$(id).showModal();}
document.querySelectorAll(".close-dialog").forEach(button=>button.onclick=()=>button.closest("dialog").close());
$("guide").onclick=()=>showDialog("guide-dialog");$("nav-analysis").onclick=()=>{switchPanel("shots");window.scrollTo({top:0,behavior:"smooth"});};
$("nav-sessions").onclick=action(async()=>{const sessions=await api("/api/sessions");const list=$("sessions-list");list.replaceChildren();for(const s of sessions){const button=document.createElement("button");button.className="session-choice";const text=document.createElement("span"),name=document.createElement("strong"),meta=document.createElement("small");name.textContent=s.name;meta.textContent=`${s.is_demo?"合成デモ · ":""}${s.status==="ready"?`${s.summary.attempts} 本のシュート`:"解析前"} · ${formatTime(s.video.duration_s)}`;text.append(name,meta);button.append(text,document.createTextNode("↗"));button.onclick=action(async()=>{$("sessions-dialog").close();await loadSession(s.id);});list.append(button);}showDialog("sessions-dialog");});
$("upload-button").onclick=()=>$("upload").click();
$("upload").onchange=action(async()=>{const file=$("upload").files[0];if(!file)return;setBusy(true);notify("動画を読み込み中…",0);try{const data=new FormData();data.append("file",file);const s=await api("/api/sessions",{method:"POST",body:data});await loadSession(s.id);await openSetup();}finally{setBusy(false);$("upload").value="";}});
async function openSetup(){video.pause();state.setup=structuredClone(state.session.config||{rim:null,person:null,handedness:"right",threshold:.35,max_gap_s:.12});state.region="rim";$("auto-person").checked=!state.setup.person;$("handedness").value=state.setup.handedness;$("threshold").value=state.setup.threshold;$("setup-canvas").width=state.session.video.width;$("setup-canvas").height=state.session.video.height;
  state.image=new Image();await new Promise((resolve,reject)=>{state.image.onload=resolve;state.image.onerror=()=>reject(new Error("設定用の画像を読み込めません"));state.image.src=fileUrl("thumbnail.jpg");});
  const health=await api("/api/health");const ready=health.vision_installed&&health.pose_model_ready;
  $("model-status").textContent=state.session.is_demo?"デモの設定は確認用です。実際の練習動画を読み込むと解析できます。":!ready?"解析環境の準備が必要です。PowerShellで .\\setup.ps1 -Vision を実行してください。":state.session.status==="ready"?"再解析すると、このセッションの自動判定と修正結果を更新します。":"初回はRF-DETRの重みを取得します。解析中はこの画面で進捗を確認できます。";
  $("setup-zoom").value="1";$("setup-canvas").style.width="100%";panMode=false;$("setup-pan").setAttribute("aria-pressed","false");$("setup-canvas").style.cursor="crosshair";
  $("start-analysis").disabled=state.session.is_demo||!ready;showDialog("setup-dialog");drawSetup();}
$("auto-person").onchange=()=>{if($("auto-person").checked){state.setup.person=null;state.region="rim";}drawSetup();};
$("settings").onclick=action(openSetup);
$("setup-shortcut").onclick=action(openSetup);
$("setup-zoom").onchange=()=>{$("setup-canvas").style.width=Number($("setup-zoom").value)*100+"%";};
$("setup-pan").onclick=()=>{panMode=!panMode;$("setup-pan").setAttribute("aria-pressed",String(panMode));$("setup-canvas").style.cursor=panMode?"grab":"crosshair";};
function drawSetup(){const c=$("setup-canvas"),ctx=c.getContext("2d");ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(state.image,0,0,c.width,c.height);for(const key of ["person","rim"]){const r=state.setup[key];if(!r)continue;ctx.strokeStyle=key==="rim"?"#f2bc4a":"#8dc783";ctx.fillStyle=key==="rim"?"#f2bc4a25":"#8dc78320";ctx.lineWidth=Math.max(2,c.width/300);ctx.strokeRect(r.x*c.width,r.y*c.height,r.w*c.width,r.h*c.height);ctx.fillRect(r.x*c.width,r.y*c.height,r.w*c.width,r.h*c.height);ctx.font=`${Math.max(12,c.width/55)}px Segoe UI`;ctx.fillStyle=ctx.strokeStyle;ctx.fillText(key==="rim"?"RIM":"PLAYER",r.x*c.width+4,Math.max(20,r.y*c.height-7));}
  document.querySelectorAll("[data-region]").forEach(b=>{b.classList.toggle("active",b.dataset.region===state.region);b.hidden=b.dataset.region==="person"&&$("auto-person").checked;});$("region-status").textContent=`リング: ${state.setup.rim?"指定済み":"未指定"}  /  人物: ${$("auto-person").checked?"自動検出":state.setup.person?"指定済み":"未指定"}`;}
document.querySelectorAll("[data-region]").forEach(button=>button.onclick=()=>{state.region=button.dataset.region;drawSetup();});
let dragStart=null,priorRegion=null,panMode=false,panStart=null,drawMoved=false;
function position(event){const r=$("setup-canvas").getBoundingClientRect();return {x:Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))};}
$("setup-canvas").onpointerdown=event=>{event.target.setPointerCapture(event.pointerId);if(panMode){const viewport=event.target.parentElement;panStart={x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};return;}drawMoved=false;dragStart=position(event);priorRegion=state.setup[state.region];};
$("setup-canvas").onpointermove=event=>{if(panStart){event.target.parentElement.scrollLeft=panStart.left+panStart.x-event.clientX;event.target.parentElement.scrollTop=panStart.top+panStart.y-event.clientY;return;}if(!dragStart)return;drawMoved=true;const p=position(event);state.setup[state.region]={x:Math.min(dragStart.x,p.x),y:Math.min(dragStart.y,p.y),w:Math.abs(p.x-dragStart.x),h:Math.abs(p.y-dragStart.y)};drawSetup();};
$("setup-canvas").onpointerup=()=>{panStart=null;if(!dragStart)return;const r=state.setup[state.region];if(!drawMoved||!r||r.w<.005||r.h<.005){state.setup[state.region]=priorRegion;toast("範囲をドラッグで囲んでください。");}dragStart=null;drawSetup();};
$("setup-canvas").onpointercancel=()=>{panStart=null;if(dragStart){state.setup[state.region]=priorRegion;dragStart=null;drawSetup();}};
$("setup-form").onsubmit=action(async event=>{event.preventDefault();if(!state.setup.rim||(!$("auto-person").checked&&!state.setup.person))throw new Error("リングと人物の範囲を指定してください");state.setup.handedness=$("handedness").value;state.setup.threshold=Number($("threshold").value);const job=await api(apiUrl("/analyze"),jsonOptions("POST",state.setup));$("setup-dialog").close();await watchJob(job);});
async function watchJob(job,download=false){setBusy(true);try{for(;;){const current=await api(`/api/jobs/${job.id}`);notify(current.message,current.progress);if(current.status==="failed")throw new Error(current.message);if(current.status==="complete"){await loadSession(current.session_id);if(download)downloadUrl(fileUrl("annotated.mp4"),"basket-annotated.mp4");else toast("解析が完了しました。シュート一覧から結果を確認できます。");return;}await new Promise(resolve=>setTimeout(resolve,1200));}}finally{setBusy(false);}}
$("edit-shot").onclick=()=>{video.pause();const s=shot();if(!s)return;$("edit-title").textContent=`シュート ${pad(s.id)} を確認`;$("edit-outcome").value=s.outcome;$("edit-release").value=s.release_s.toFixed(3);$("edit-release").step="any";$("edit-release").min=s.start_s;$("edit-release").max=s.end_s;$("edit-note").value=s.note||"";$("edit-deleted").checked=s.deleted;$("release-window").textContent=`推定範囲 ${s.release_window_s.map(v=>v.toFixed(3)).join(" 〜 ")} 秒。保存時に最も近いフレームへ合わせます。`;showDialog("edit-dialog");};
$("use-current").onclick=()=>$("edit-release").value=video.currentTime.toFixed(3);
$("edit-form").onsubmit=action(async event=>{event.preventDefault();const s=shot();state.session=await api(apiUrl(`/shots/${s.id}`),jsonOptions("PATCH",{outcome:$("edit-outcome").value,release_s:Number($("edit-release").value),deleted:$("edit-deleted").checked,note:$("edit-note").value}));state.predictions=await api(apiUrl("/predictions"));$("edit-dialog").close();renderStats();renderShots();renderDetail();drawCharts();updatePlayer();toast("修正を保存しました。動画出力にも反映されます。");});
$("export-button").onclick=()=>showDialog("menu-dialog");
function downloadUrl(url,name){const a=document.createElement("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();$("menu-dialog").close();}
$("export-csv").onclick=()=>downloadUrl(apiUrl("/shots.csv"),"shots.csv");
$("export-json").onclick=()=>{if(!state.frames.length){toast("先に動画を解析してください。");return;}downloadUrl(fileUrl("frames.json"),"frames.json");};
$("export-mp4").onclick=action(async()=>{if(!state.frames.length)throw new Error("先に動画を解析してください");$("menu-dialog").close();const job=await api(apiUrl("/render"),{method:"POST"});await watchJob(job,true);});
$("recompute").onclick=action(async()=>{const result=await api(apiUrl("/recompute"),{method:"POST"});downloadUrl(result.url,"proposals.json");toast("自動判定を再計算しました。手動修正は保持されています。");});
setBusy(true);
action(async()=>{try{const sessions=await api("/api/sessions");if(!sessions.length){notify("動画を追加してください。");return;}await loadSession(sessions.find(s=>!s.is_demo)?.id||sessions[0].id);}finally{setBusy(false);}})();
