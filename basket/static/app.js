"use strict";
const $ = id => document.getElementById(id);
const state = {session:null,frames:[],selected:null,filter:"all",busy:false,setup:{},region:"rim",image:null};
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
function toast(message){$("toast").textContent=message;$("toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").hidden=true,6500);}
async function api(url,options={}){const response=await fetch(url,options);if(!response.ok){let message=`リクエストに失敗しました (${response.status})`;try{const data=await response.json();message=typeof data.detail==="string"?data.detail:JSON.stringify(data.detail);}catch{}throw new Error(message);}return response.json();}
function jsonOptions(method,body){return {method,headers:{"Content-Type":"application/json"},body:JSON.stringify(body)};}
function notify(message,progress){const box=$("notice");box.replaceChildren(document.createTextNode(message));box.hidden=!message;if(progress!==undefined){const bar=document.createElement("progress");bar.max=1;bar.value=progress;box.append(bar);}}
function action(fn){return async(...args)=>{try{await fn(...args);}catch(error){toast(error.message);}};}
function nearestFrame(t){let low=0,high=state.frames.length-1;while(low<high){const mid=Math.floor((low+high+1)/2);if(state.frames[mid].t<=t)low=mid;else high=mid-1;}return state.frames[low];}
function shot(){return state.session?.shots.find(s=>s.id===state.selected);}
function setBusy(value){state.busy=value;for(const id of ["upload-button","settings","export-button","edit-shot","nav-sessions"]){$(id).disabled=value||(!state.session&&["settings","export-button","edit-shot"].includes(id));}}

async function loadSession(id){
  video.pause();state.session=await api(`/api/sessions/${id}`);state.frames=[];state.selected=null;state.filter="all";
  document.querySelectorAll("[data-filter]").forEach(b=>b.classList.toggle("active",b.dataset.filter==="all"));
  const s=state.session;$("session-name").textContent=s.name;$("demo-badge").hidden=!s.is_demo;
  const date=new Date(s.created_at).toLocaleDateString("ja-JP",{year:"numeric",month:"2-digit",day:"2-digit"});
  $("session-meta").textContent=`${date}  ·  ${s.video.width} × ${s.video.height} / ${s.video.fps.toFixed(0)} fps  ·  ${formatTime(s.video.duration_s)}`;
  $("timeline").max=s.video.duration_s;$("video-stage").style.aspectRatio=`${s.video.width}/${s.video.height}`;
  $("overlay").width=s.video.width;$("overlay").height=s.video.height;
  $("video-tag").textContent=s.is_demo?"SYNTHETIC DEMO · 合成映像":"LOCAL ANALYSIS · 2D";
  $("data-note").textContent=s.is_demo?"デモの映像・数値は合成データです。":"2D計測 · 成否は自動推定を目視で確認してください。";
  $("empty-video").hidden=s.status==="ready";
  if(s.status==="ready"){
    state.frames=await api(`/api/sessions/${id}/frames`);
    video.src=fileUrl("preview.mp4")+`?v=${s.revision}`;video.load();
    state.selected=s.shots.find(x=>!x.deleted)?.id??s.shots[0]?.id??null;
    notify(s.is_demo?"デモセッションを表示しています。映像・骨格・軌跡・成否は合成データです。実際の解析は「練習動画を読み込む」から始められます。":"");
    $("video-quality").textContent=`骨格取得 ${s.quality.pose_coverage}% · ボール検出 ${s.quality.ball_coverage}%`;
  }else{
    video.removeAttribute("src");video.load();video.poster=fileUrl("thumbnail.jpg");
    notify("動画を読み込みました。「撮影設定」でリングと人物の範囲を指定してください。");
    $("video-quality").textContent="解析前";
  }
  renderStats();renderShots();renderDetail();drawCharts();drawOverlay(0);updatePlayer();
}
function renderStats(){const s=state.session.summary;for(const key of ["attempts","made","missed","unknown"]){$(key).textContent=s[key];}$("rate").replaceChildren(document.createTextNode(s.percentage===null?"—":String(s.percentage)));if(s.percentage!==null){const unit=document.createElement("small");unit.textContent="%";$("rate").append(unit);}$("denominator").textContent=`判定済み ${s.denominator} 本が対象`;
  $("rate-ring").style.strokeDashoffset=182.2*(1-(s.percentage||0)/100);$("shot-count").textContent=s.attempts;
}
function renderShots(){
  const list=$("shot-list");list.replaceChildren();const shots=state.session.shots.filter(s=>state.filter==="deleted"?s.deleted:!s.deleted&&(state.filter==="all"||s.outcome===state.filter));
  if(!shots.length){const empty=document.createElement("p");empty.className="empty-list";empty.textContent=state.session.status!=="ready"?"解析後にシュートが表示されます。":"該当するシュートはありません。";list.append(empty);return;}
  for(const s of shots){const button=document.createElement("button");button.className=`shot-row ${state.selected===s.id?"selected":""}`;button.setAttribute("aria-label",`シュート ${s.id} ${labels[s.outcome]} ${preciseTime(s.release_s)}`);
    const number=document.createElement("span");number.className="shot-number";number.textContent=pad(s.id);
    const title=document.createElement("span");title.className="shot-title";title.textContent=`シュート ${pad(s.id)}`;const time=document.createElement("span");time.className="shot-time";time.textContent=`${preciseTime(s.release_s)}${s.reviewed?"  · 確認済み":""}`;title.append(time);
    const result=document.createElement("span");result.className=`outcome ${s.outcome}`;result.textContent=`${icons[s.outcome]} ${s.deleted?"除外":labels[s.outcome]}`;button.append(number,title,result);button.onclick=()=>selectShot(s.id);list.append(button);
  }
}
function selectShot(id){state.selected=id;const s=shot();if(s&&video.src){video.currentTime=Math.max(0,s.release_s-.4);}renderShots();renderDetail();drawCharts();}
function renderDetail(){const s=shot();$("selected-detail").hidden=!s;if(!s)return;$("detail-name").textContent=`SHOT ${pad(s.id)} · リリース時`;
  const frame=nearestFrame(s.release_s),a=frame?.angles||{};for(const [id,key] of [["elbow-value","elbow_deg"],["knee-value","knee_deg"],["trunk-value","trunk_deg"]]){$(id).textContent=a[key]===null||a[key]===undefined?"—":`${Math.round(a[key])}°`;}
  $("shot-reason").textContent=s.reviewed?`確認済み${s.note?` · ${s.note}`:""}`:s.reason;
}
function drawOverlay(t){
  const canvas=$("overlay"),ctx=canvas.getContext("2d");ctx.clearRect(0,0,canvas.width,canvas.height);if(!state.frames.length)return;
  const frame=nearestFrame(t);if(!frame||Math.abs(frame.t-t)>.15)return;const scale=canvas.width/960;ctx.lineWidth=2*scale;
  if($("toggle-rim").checked){const r=state.session.config.rim;ctx.strokeStyle="#f0f3b7";ctx.setLineDash([5*scale,4*scale]);ctx.strokeRect(r.x*canvas.width,r.y*canvas.height,r.w*canvas.width,r.h*canvas.height);ctx.setLineDash([]);}
  if($("toggle-ball").checked){const first=Math.max(0,frame.index-Math.ceil(state.session.video.fps*2));for(let i=first+1;i<=frame.index;i++){const a=state.frames[i-1],b=state.frames[i];if(!a.ball||!b.ball||b.t-a.t>state.session.config.max_gap_s)continue;const predicted=a.ball.source!=="detected"||b.ball.source!=="detected";ctx.strokeStyle=predicted?"#d8ded1":"#f3c86f";ctx.setLineDash(predicted?[4*scale,5*scale]:[]);ctx.globalAlpha=.35+.65*(i-first)/Math.max(1,frame.index-first);ctx.beginPath();ctx.moveTo(a.ball.x,a.ball.y);ctx.lineTo(b.ball.x,b.ball.y);ctx.stroke();}ctx.setLineDash([]);ctx.globalAlpha=1;
    if(frame.ball){ctx.strokeStyle=frame.ball.source==="detected"?"#f9d684":"#d8ded1";ctx.beginPath();ctx.arc(frame.ball.x,frame.ball.y,frame.ball.radius+5*scale,0,Math.PI*2);ctx.stroke();}}
  if($("toggle-pose").checked&&frame.pose){ctx.strokeStyle="#d7f3b8";ctx.fillStyle="#f6ffeb";for(const [a,b] of edges){if(frame.pose[a]?.[2]<.5||frame.pose[b]?.[2]<.5)continue;ctx.beginPath();ctx.moveTo(...frame.pose[a].slice(0,2));ctx.lineTo(...frame.pose[b].slice(0,2));ctx.stroke();}for(const p of frame.pose){if(p[2]<.5)continue;ctx.beginPath();ctx.arc(p[0],p[1],3*scale,0,Math.PI*2);ctx.fill();}}
  const active=state.session.shots.find(s=>!s.deleted&&s.start_s<=t&&s.end_s>=t);$("shot-overlay").hidden=!active;if(active){$("shot-overlay").querySelector("strong").textContent=pad(active.id);$("shot-overlay").querySelector(".shot-status").textContent=`${icons[active.outcome]} ${labels[active.outcome]}`;}
}
function updatePlayer(){const t=video.currentTime||0;$("timeline").value=t;$("time").textContent=`${formatTime(t)} / ${formatTime(state.session?.video.duration_s)}`;$("play").textContent=video.paused?"▶":"Ⅱ";$("play").setAttribute("aria-label",video.paused?"再生":"一時停止");const active=state.session?.shots.find(s=>!s.deleted&&s.start_s<=t&&s.end_s>=t);if(active&&active.id!==state.selected){state.selected=active.id;renderShots();renderDetail();drawCharts();}drawOverlay(t);}
function drawCharts(){drawAngles();drawTrajectories();}
function drawAngles(){
  const c=$("angle-chart"),ctx=c.getContext("2d"),w=c.width,h=c.height;ctx.clearRect(0,0,w,h);
  const key=$("angle-select").value,lo=key==="trunk_deg"?-45:0,hi=key==="trunk_deg"?45:180;
  const X=t=>50+(t+.6)/1.8*(w-72),Y=a=>h-37-(a-lo)/(hi-lo)*(h-65);
  ctx.font="13px Segoe UI";ctx.fillStyle="#a7b09d";ctx.strokeStyle="#edf0e7";ctx.lineWidth=1;
  for(let v=lo;v<=hi;v+=(hi-lo)/3){ctx.beginPath();ctx.moveTo(44,Y(v));ctx.lineTo(w-15,Y(v));ctx.stroke();ctx.fillText(`${v}°`,9,Y(v)+4);}
  for(const t of [-.5,0,.5,1]){ctx.fillText(`${t===0?"0":t.toFixed(1)} s`,X(t)-13,h-13);}
  ctx.setLineDash([5,5]);ctx.strokeStyle="#d4ddc9";ctx.beginPath();ctx.moveTo(X(0),18);ctx.lineTo(X(0),h-34);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle="#9aab87";ctx.fillText("RELEASE",X(0)+6,16);
  for(const s of state.session?.shots||[]){if(s.deleted||(!$("compare").checked&&s.id!==state.selected))continue;ctx.strokeStyle=s.id===state.selected?"#789355":"#dce5d3";ctx.lineWidth=s.id===state.selected?2.8:1.6;ctx.beginPath();let previous=null;
    for(const f of state.frames){const t=f.t-s.release_s;if(t<-.6||t>1.2)continue;const value=f.angles?.[key];if(value===null||value===undefined){previous=null;continue;}if(!previous||f.t-previous.t>.12)ctx.moveTo(X(t),Y(value));else ctx.lineTo(X(t),Y(value));previous=f;}ctx.stroke();}
  if(!state.frames.length){ctx.fillStyle="#9ca991";ctx.fillText("解析後に角度を表示します",140,105);}
}
function drawTrajectories(){
  const c=$("trajectory-chart"),ctx=c.getContext("2d"),w=c.width,h=c.height;ctx.clearRect(0,0,w,h);const paths=[];
  for(const s of state.session?.shots||[]){if(s.deleted)continue;const origin=nearestFrame(s.release_s)?.ball;if(!origin)continue;const points=state.frames.filter(f=>f.t>=s.release_s&&f.t<=Math.min(s.end_s,s.release_s+2.2)).map(f=>f.ball?{x:f.ball.x-origin.x,y:f.ball.y-origin.y,source:f.ball.source,t:f.t}:null);paths.push({s,points});}
  const points=paths.flatMap(p=>p.points).filter(Boolean);const minX=Math.min(0,...points.map(p=>p.x)),maxX=Math.max(100,...points.map(p=>p.x)),minY=Math.min(-80,...points.map(p=>p.y)),maxY=Math.max(20,...points.map(p=>p.y));
  const scale=Math.min((w-65)/(maxX-minX),(h-58)/(maxY-minY));const X=x=>40+(x-minX)*scale,Y=y=>20+(y-minY)*scale;
  ctx.strokeStyle="#e7ecdf";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(30,Y(0));ctx.lineTo(w-14,Y(0));ctx.moveTo(X(0),15);ctx.lineTo(X(0),h-20);ctx.stroke();
  ctx.font="11px Segoe UI";ctx.fillStyle="#a5b197";ctx.fillText("0",X(0)-12,Y(0)+15);ctx.fillText("RELEASE",X(0)+6,Y(0)+15);
  for(const path of paths){const isSelected=path.s.id===state.selected;ctx.strokeStyle=isSelected?"#ba945d":"#dce5d1";ctx.lineWidth=isSelected?2.5:1.4;for(let i=1;i<path.points.length;i++){const a=path.points[i-1],b=path.points[i];if(!a||!b||b.t-a.t>.12)continue;ctx.setLineDash(a.source!=="detected"||b.source!=="detected"?[4,5]:[]);ctx.beginPath();ctx.moveTo(X(a.x),Y(a.y));ctx.lineTo(X(b.x),Y(b.y));ctx.stroke();}}ctx.setLineDash([]);
  ctx.fillStyle="#9cab8c";ctx.beginPath();ctx.arc(X(0),Y(0),3,0,Math.PI*2);ctx.fill();
}

$("play").onclick=action(async()=>{if(!state.frames.length)return;if(video.paused)await video.play();else video.pause();});
video.addEventListener("timeupdate",updatePlayer);video.addEventListener("pause",updatePlayer);video.addEventListener("play",updatePlayer);video.addEventListener("loadeddata",()=>{if(shot())video.currentTime=Math.max(0,shot().release_s-.25);updatePlayer();});
video.addEventListener("error",()=>{if(video.getAttribute("src"))toast("動画を再生できません。ページを再読み込みしてください。");});
if("requestVideoFrameCallback" in video){function frameCallback(){updatePlayer();video.requestVideoFrameCallback(frameCallback);}video.requestVideoFrameCallback(frameCallback);}
$("timeline").oninput=()=>{if(state.frames.length)video.currentTime=Number($("timeline").value);updatePlayer();};
for(const [id,direction] of [["prev-frame",-1],["next-frame",1]])$(id).onclick=()=>{if(!state.frames.length)return;video.pause();const frame=nearestFrame(video.currentTime+.0001);const target=state.frames[Math.max(0,Math.min(state.frames.length-1,frame.index+direction))];video.currentTime=target.t;updatePlayer();};
$("speed").onchange=()=>video.playbackRate=Number($("speed").value);
for(const id of ["toggle-pose","toggle-ball","toggle-rim"])$(id).onchange=updatePlayer;
$("angle-select").onchange=drawAngles;$("compare").onchange=drawAngles;
document.querySelectorAll("[data-filter]").forEach(button=>button.onclick=()=>{state.filter=button.dataset.filter;document.querySelectorAll("[data-filter]").forEach(b=>b.classList.toggle("active",b===button));renderShots();});
document.querySelectorAll(".close-dialog").forEach(button=>button.onclick=()=>button.closest("dialog").close());
$("guide").onclick=()=>$("guide-dialog").showModal();$("nav-analysis").onclick=()=>window.scrollTo({top:0,behavior:"smooth"});
$("nav-sessions").onclick=action(async()=>{const sessions=await api("/api/sessions");const list=$("sessions-list");list.replaceChildren();for(const s of sessions){const button=document.createElement("button");button.className="session-choice";const text=document.createElement("span"),name=document.createElement("strong"),meta=document.createElement("small");name.textContent=s.name;meta.textContent=`${s.is_demo?"合成デモ · ":""}${s.status==="ready"?`${s.summary.attempts} 本のシュート`:"解析前"} · ${formatTime(s.video.duration_s)}`;text.append(name,meta);button.append(text,document.createTextNode("↗"));button.onclick=action(async()=>{$("sessions-dialog").close();await loadSession(s.id);});list.append(button);}$("sessions-dialog").showModal();});
$("upload-button").onclick=()=>$("upload").click();
$("upload").onchange=action(async()=>{const file=$("upload").files[0];if(!file)return;setBusy(true);notify("動画をこのPCのワークスペースに読み込んでいます…",0);try{const data=new FormData();data.append("file",file);const s=await api("/api/sessions",{method:"POST",body:data});await loadSession(s.id);await openSetup();}finally{setBusy(false);$("upload").value="";}});
async function openSetup(){video.pause();state.setup=structuredClone(state.session.config||{rim:null,person:{x:.05,y:.05,w:.9,h:.9},handedness:"right",threshold:.35,max_gap_s:.12});state.region="rim";$("handedness").value=state.setup.handedness;$("threshold").value=state.setup.threshold;$("setup-canvas").width=state.session.video.width;$("setup-canvas").height=state.session.video.height;
  state.image=new Image();await new Promise((resolve,reject)=>{state.image.onload=resolve;state.image.onerror=()=>reject(new Error("設定用の画像を読み込めません"));state.image.src=fileUrl("thumbnail.jpg");});
  const health=await api("/api/health");const ready=health.vision_installed&&health.pose_model_ready;
  $("model-status").textContent=state.session.is_demo?"デモの設定は確認用です。実際の練習動画を読み込むと解析できます。":!ready?"解析環境の準備が必要です。PowerShellで .\\setup.ps1 -Vision を実行してください。":state.session.status==="ready"?"再解析すると、このセッションの自動判定と修正結果を更新します。":"初回はRF-DETRの重みを取得します。解析中はこの画面で進捗を確認できます。";
  $("start-analysis").disabled=state.session.is_demo||!ready;$("setup-dialog").showModal();drawSetup();}
$("settings").onclick=action(openSetup);
function drawSetup(){const c=$("setup-canvas"),ctx=c.getContext("2d");ctx.clearRect(0,0,c.width,c.height);ctx.drawImage(state.image,0,0,c.width,c.height);for(const key of ["person","rim"]){const r=state.setup[key];if(!r)continue;ctx.strokeStyle=key==="rim"?"#f2bc4a":"#8dc783";ctx.fillStyle=key==="rim"?"#f2bc4a25":"#8dc78320";ctx.lineWidth=Math.max(2,c.width/300);ctx.strokeRect(r.x*c.width,r.y*c.height,r.w*c.width,r.h*c.height);ctx.fillRect(r.x*c.width,r.y*c.height,r.w*c.width,r.h*c.height);ctx.font=`${Math.max(12,c.width/55)}px Segoe UI`;ctx.fillStyle=ctx.strokeStyle;ctx.fillText(key==="rim"?"RIM":"PLAYER",r.x*c.width+4,Math.max(20,r.y*c.height-7));}
  document.querySelectorAll("[data-region]").forEach(b=>b.classList.toggle("active",b.dataset.region===state.region));$("region-status").textContent=`リング: ${state.setup.rim?"指定済み":"未指定"}  /  人物: ${state.setup.person?"指定済み（手の動く範囲も確認）":"未指定"}`;}
document.querySelectorAll("[data-region]").forEach(button=>button.onclick=()=>{state.region=button.dataset.region;drawSetup();});
let dragStart=null,priorRegion=null;
function position(event){const r=$("setup-canvas").getBoundingClientRect();return {x:Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))};}
$("setup-canvas").onpointerdown=event=>{dragStart=position(event);priorRegion=state.setup[state.region];event.target.setPointerCapture(event.pointerId);};
$("setup-canvas").onpointermove=event=>{if(!dragStart)return;const p=position(event);state.setup[state.region]={x:Math.min(dragStart.x,p.x),y:Math.min(dragStart.y,p.y),w:Math.abs(p.x-dragStart.x),h:Math.abs(p.y-dragStart.y)};drawSetup();};
$("setup-canvas").onpointerup=()=>{if(!dragStart)return;const r=state.setup[state.region];if(!r||r.w<.005||r.h<.005){state.setup[state.region]=priorRegion;toast("もう少し大きい領域をドラッグしてください。");}dragStart=null;drawSetup();};
$("setup-form").onsubmit=action(async event=>{event.preventDefault();if(!state.setup.rim||!state.setup.person)throw new Error("リングと人物の範囲を指定してください");state.setup.handedness=$("handedness").value;state.setup.threshold=Number($("threshold").value);const job=await api(apiUrl("/analyze"),jsonOptions("POST",state.setup));$("setup-dialog").close();await watchJob(job);});
async function watchJob(job,download=false){setBusy(true);try{for(;;){const current=await api(`/api/jobs/${job.id}`);notify(current.message,current.progress);if(current.status==="failed")throw new Error(current.message);if(current.status==="complete"){await loadSession(current.session_id);if(download)downloadUrl(fileUrl("annotated.mp4"),"basket-annotated.mp4");else toast("解析が完了しました。シュート一覧から結果を確認できます。");return;}await new Promise(resolve=>setTimeout(resolve,1200));}}finally{setBusy(false);}}
$("edit-shot").onclick=()=>{video.pause();const s=shot();if(!s)return;$("edit-title").textContent=`シュート ${pad(s.id)} を確認`;$("edit-outcome").value=s.outcome;$("edit-release").value=s.release_s.toFixed(3);$("edit-release").step="any";$("edit-release").min=s.start_s;$("edit-release").max=s.end_s;$("edit-note").value=s.note||"";$("edit-deleted").checked=s.deleted;$("release-window").textContent=`推定範囲 ${s.release_window_s.map(v=>v.toFixed(3)).join(" 〜 ")} 秒。保存時に最も近いフレームへ合わせます。`;$("edit-dialog").showModal();};
$("use-current").onclick=()=>$("edit-release").value=video.currentTime.toFixed(3);
$("edit-form").onsubmit=action(async event=>{event.preventDefault();const s=shot();state.session=await api(apiUrl(`/shots/${s.id}`),jsonOptions("PATCH",{outcome:$("edit-outcome").value,release_s:Number($("edit-release").value),deleted:$("edit-deleted").checked,note:$("edit-note").value}));$("edit-dialog").close();renderStats();renderShots();renderDetail();drawCharts();updatePlayer();toast("修正を保存しました。動画出力にも反映されます。");});
$("export-button").onclick=()=>$("export-menu").hidden=!$("export-menu").hidden;
document.addEventListener("click",event=>{if(!event.target.closest(".dropdown"))$("export-menu").hidden=true;});
function downloadUrl(url,name){const a=document.createElement("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();$("export-menu").hidden=true;}
$("export-csv").onclick=()=>downloadUrl(apiUrl("/shots.csv"),"shots.csv");
$("export-json").onclick=()=>{if(!state.frames.length){toast("先に動画を解析してください。");return;}downloadUrl(fileUrl("frames.json"),"frames.json");};
$("export-mp4").onclick=action(async()=>{$("export-menu").hidden=true;if(!state.frames.length)throw new Error("先に動画を解析してください");if(state.session.revision===state.session.rendered_revision){downloadUrl(fileUrl("annotated.mp4"),"basket-annotated.mp4");return;}const job=await api(apiUrl("/render"),{method:"POST"});await watchJob(job,true);});
$("recompute").onclick=action(async()=>{const result=await api(apiUrl("/recompute"),{method:"POST"});downloadUrl(result.url,"proposals.json");toast("自動判定を再計算しました。手動修正は保持されています。");});
setBusy(true);
action(async()=>{try{const sessions=await api("/api/sessions");if(!sessions.length){notify("セッションがありません。練習動画を読み込んでください。");return;}await loadSession(sessions.find(s=>!s.is_demo)?.id||"demo");}finally{setBusy(false);}})();
