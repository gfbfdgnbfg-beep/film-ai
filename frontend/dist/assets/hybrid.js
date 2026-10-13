/* AI Film Factory V0.5 Hybrid Dashboard: no OpenAI, no external CDN, no hardcoded secrets. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const state={tab:'dashboard',pid:localStorage.getItem('film_v05_pid')||'',projects:[],project:null,agent:null,tasks:[],assets:null,shot:null,preview:30,busy:false};
const tabs={dashboard:'Tổng quan',director:'AI Director',assets:'Ảnh · Video · Giọng',output:'Đầu ra',connect:'Kết nối AI'};
async function get(path,options={}){
 const r=await fetch('/api'+path,{credentials:'same-origin',...options});
 let v=await r.json().catch(()=>({}));
 if(!r.ok)throw new Error(v.detail||`HTTP ${r.status}`);
 return v;
}
const post=(path,obj={})=>get(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});
function toast(txt,error=false){$('toast').innerHTML=`<div class="message ${error?'error':''}">${esc(txt)}</div>`;setTimeout(()=>{$('toast').innerHTML=''},5500)}
function statename(s){return ({mock:'Bản nháp quy tắc',edited:'Đã sửa thủ công',director_draft:'AI Director · Chờ duyệt',approved:'Đã duyệt'})[s]||s||'Chưa có'}
function tb(){return `<div class="project-menu"><label for="chooseProject">Dự án hiện tại</label><select id="chooseProject"><option value="">— Chọn phim —</option>${state.projects.map(x=>`<option value="${esc(x.id)}" ${state.pid===x.id?'selected':''}>${esc(x.title)} · ${x.minutes} phút</option>`).join('')}</select>${state.pid?`<a class="btn light" href="/api/projects/${esc(state.pid)}/backup">↓ Sao lưu ZIP</a>`:''}</div>`}
const box=(label,value)=>`<div class="metric"><div class="num">${value}</div><div class="lbl">${label}</div></div>`;
function heading(k,t,d){return `<div class="eyebrow">${esc(k)}</div><h1 class="page-title">${esc(t)}</h1><p class="desc">${d}</p>`}
function dashboard(){const p=state.project,task=state.tasks[0];return `
 <div class="hero"><div class="eyebrow">LOCAL-FIRST · BROWSER-ASSISTED</div><h1>Một kịch bản.<br><span>Một trung tâm sản xuất phim.</span></h1><p>Bạn cung cấp kịch bản và lời thoại. Ollama trên PC đề xuất phân cảnh, bối cảnh, góc máy. FFmpeg dựng các tài nguyên được cung cấp và trả phim MP4 có tiếng Việt/phụ đề về website. Không gọi OpenAI.</p><div class="actions"><span class="chip">Ollama miễn phí</span><span class="chip">Desktop Agent</span><span class="chip">FFmpeg</span><span class="chip">Chuyển giao tab AI có hỗ trợ</span></div></div>
 <div class="grid3 mb16">${box('TỔNG DỰ ÁN',state.projects.length)}${box('SỐ PHÂN CẢNH',p?.shots?.length||0)}${box('DESKTOP AGENT',state.agent?.agent_online?'ONLINE':'OFFLINE')}</div>
 <div class="grid2"> <section class="card"><div class="eyebrow">01 / ĐẦU VÀO</div><h2>Tạo phim từ kịch bản của bạn</h2><label class="field" for="newTitle">Tên phim</label><input type="text" id="newTitle" maxlength="140" value="Cô lao công và bản hợp đồng 50 tỷ"><label class="field" for="newScript">Kịch bản / cốt truyện hoàn chỉnh</label><textarea id="newScript" rows="9" placeholder="Dán toàn bộ kịch bản của bạn vào đây, kể cả lời thoại từng nhân vật..."></textarea><label class="field" for="newMinutes">Thời lượng phim</label><select id="newMinutes">${[1,3,5,8,10,15].map(x=>`<option value="${x}" ${x===8?'selected':''}>${x} phút</option>`).join('')}</select><button class="btn primary full mt16" data-action="create">＋ Tạo dự án</button><p class="tiny">Tạo dự án chưa gọi AI. Storyboard ban đầu chỉ là bản nháp quy tắc.</p></section>
 <section class="card"><div class="eyebrow">02 / CURRENT PROJECT</div><h2>Trạng thái sản xuất</h2>${tb()}${p?`<div class="notice"><strong>${esc(p.title)}</strong><br>${p.minutes} phút · ${p.shots.length} shot · ${statename(p.script_status)}</div><div class="timeline mt16">
 ${[['1','Kịch bản đầu vào','Bạn viết và lưu'],['2','Ollama AI Director','Chia cảnh, bối cảnh, góc máy'],['3','Asset Manager','Nhận ảnh, video và giọng Việt'],['4','FFmpeg Local Render','MP4, âm thanh, SRT']].map(a=>`<div class="step"><span class="number">${a[0]}</span><div><b>${a[1]}</b><small>${a[2]}</small></div></div>`).join('')}</div><div class="actions"><button data-tab="director" class="btn primary">◈ Mở AI Director</button><button data-tab="output" class="btn">▶ Xem đầu ra</button></div>`:'<p class="tiny">Hãy tạo một dự án hoặc chọn phim đã có từ danh sách.</p>'}
 ${task?`<div class="divider"></div><small class="muted">Tác vụ gần nhất</small><p>${esc(task.message)}</p><span class="state ${esc(task.state)}">${esc(task.state)}</span>`:''}</section></div>`}
function director(){const p=state.project;if(!p)return heading('AI DIRECTOR','Chưa có dự án','Hãy tạo hoặc chọn dự án trong mục Tổng quan.')+'<button class="btn" data-tab="dashboard">← Tổng quan</button>';
 const task=state.tasks.find(x=>x.kind==='director');
 return heading('LOCAL OLLAMA / AI DIRECTOR','Phân tích kịch bản & quyết định góc máy','Không viết lại kịch bản của bạn. AI đọc nội dung, đề xuất shot, bối cảnh, góc máy, ánh sáng và prompt hình/video. Kết quả cần được bạn duyệt.')+tb()+`<div class="grid2"><section class="card"><h2>Kịch bản đầu vào</h2><label class="field" for="scriptTitle">Tên phim</label><input id="scriptTitle" type="text" maxlength="140" value="${esc(p.title)}"><label class="field" for="scriptBody">Nội dung do bạn viết</label><textarea rows="13" id="scriptBody">${esc(p.story)}</textarea><label class="field" for="scriptMinutes">Thời lượng</label><select id="scriptMinutes">${[1,3,5,8,10,15].map(x=>`<option value="${x}" ${p.minutes===x?'selected':''}>${x} phút</option>`).join('')}</select><div class="actions"><button class="btn" data-action="saveScript">✓ Lưu kịch bản</button><button class="btn primary" data-action="director">◈ Phân cảnh bằng Ollama</button></div><p class="tiny">Lưu kịch bản trước khi chạy. Nếu đổi thời lượng, bạn cần tạo lại shot quy tắc trước khi yêu cầu Ollama.</p></section>
 <section class="card"><h2>Tác vụ phân cảnh</h2><div class="notice">Đầu vào: <b>kịch bản của bạn</b><br>Đầu ra: <b>shot list + bối cảnh + góc máy + prompt ảnh/video</b><br>Nhà cung cấp: <b>Ollama trên PC</b> — không phí token.</div><div class="divider"></div><h3>Trạng thái</h3>${task?`<div class="task-item"><span class="state ${esc(task.state)}">${esc(task.state)}</span><p>${esc(task.message)}</p>${task.error?`<div class="warning">${esc(task.error)}</div>`:''}<small class="mono">${esc(task.updated)}</small></div>`:'<p>Chưa gửi yêu cầu AI Director.</p>'}<div class="divider"></div><p><b>Storyboard:</b> ${statename(p.script_status)} · ${p.shots.length} shot</p><div class="actions"><button class="btn good" data-action="approve" ${p.script_status!=='director_draft'?'disabled':''}>✓ Duyệt phân cảnh</button><a class="btn" href="/studio">✎ Biên tập chi tiết ↗</a><a class="btn" href="/api/projects/${esc(p.id)}/shots/download">↓ shots.json</a></div><div class="warning">AI có thể hiểu sai cảnh hoặc lời thoại. Kiểm tra storyboard trong trình chỉnh sửa trước khi duyệt; kết quả AI không tự sửa văn bản gốc.</div></section></div>`}
function assets(){const p=state.project;if(!p)return heading('ASSETS','Chưa có dự án','Hãy tạo hoặc chọn phim trước.');
 const shot=p.shots.find(s=>s.id===state.shot)||p.shots[0];if(!shot)return '<p>Chưa có shot</p>';
 const a=(state.assets?.shots||[]).find(x=>x.id===shot.id)||{};
 const upload=(kind,label,accept)=>`<label class="btn file-upload">＋ ${label}<input type="file" data-upload="${kind}" accept="${accept}" aria-label="${label}"></label>`;
 return heading('ASSET MANAGER / 9:16','Chuẩn bị ảnh, video và giọng Việt','Có thể mở một trang AI theo cách thủ công, sao chép prompt và tải kết quả về. Sau đó tải tệp lên shot tương ứng. Kết nối tự thao tác tab của từng dịch vụ sẽ cần adapter hợp lệ riêng.')+tb()+`<div class="shot-layout"><aside class="shot-list">${p.shots.map(s=>{const b=(state.assets?.shots||[]).find(x=>x.id===s.id)||{};return `<button class="shot-row ${shot.id===s.id?'active':''}" data-action="shot" data-sid="${esc(s.id)}"><strong>${esc(s.id)} · ${esc(s.title)}</strong><small>${esc(s.location)} · ${s.duration_seconds}s</small><small>${b.image?'📷 ':''}${b.video?'🎞 ':''}${b.voice?'🎤 ':''}</small></button>`}).join('')}</aside>
 <section class="card"><div class="eyebrow">${esc(shot.id)} / ${shot.duration_seconds} GIÂY</div><h2>${esc(shot.title)}</h2><div class="shot-fields"><div><small>Bối cảnh</small><b>${esc(shot.location)}</b></div><div><small>Góc máy</small><b>${esc(shot.camera)}</b></div><div><small>Hành động</small><b>${esc(shot.action)}</b></div><div><small>Lời thoại</small><b>${esc(shot.dialogue||'Không có lời thoại')}</b></div></div><label class="field">Prompt ảnh (sao chép sang công cụ AI phù hợp)</label><div class="prompt">${esc(shot.image_prompt)}</div><button class="btn light mt16" data-action="copyImage">⧉ Sao chép prompt ảnh</button><label class="field">Prompt tạo video</label><div class="prompt">${esc(shot.video_prompt)}</div><button class="btn light mt16" data-action="copyVideo">⧉ Sao chép prompt video</button><div class="divider"></div><h3>File tài nguyên của shot</h3><div class="actions">${upload('image','Tải ảnh phân cảnh','image/png,image/jpeg,image/webp')}${upload('video','Tải video MP4','video/mp4')}${upload('voice','Tải giọng MP3/WAV','audio/mpeg,audio/wav')}</div><p class="tiny">Video từ website AI phải được tải về hợp lệ và upload thủ công ở V0.5. Giọng Việt có thể được thu âm hoặc tạo bằng công cụ bạn được phép sử dụng.</p><div class="asset-previews mt16">${a.image?`<div><small>ẢNH</small><img src="${esc(a.image)}" alt="Ảnh ${esc(shot.id)}"></div>`:'<div class="placeholder-label">Chưa có ảnh</div>'}${a.video?`<div><small>VIDEO</small><video controls preload="metadata" src="${esc(a.video)}"></video></div>`:'<div class="placeholder-label">Chưa có video</div>'}</div>${a.voice?`<p>🎤 Giọng đọc: <audio controls src="${esc(a.voice)}"></audio></p>`:''}</section></div>`}
function output(){const p=state.project;if(!p)return heading('OUTPUT','Chưa có dự án','Hãy tạo hoặc chọn phim trước.');
 const a=state.assets||{},task=state.tasks.find(x=>x.kind==='render');
 return heading('OUTPUT STUDIO','Xem và tải phim hoàn chỉnh','Dựng các video/ảnh đã tải lên; thêm giọng nói theo shot, tạo SRT tiếng Việt và có thể chèn phụ đề trực tiếp nếu FFmpeg hỗ trợ libass.')+tb()+`<div class="grid2"><section class="card"><h2>Trình xem phim</h2><div class="video-stage">${a.output?`<video controls preload="metadata" src="${esc(a.output)}"></video>`:'<div class="empty-video"><span class="play">▷</span>Chưa có phim hoàn chỉnh<br><small>Đợi Desktop Agent dựng xong MP4</small></div>'}</div><div class="actions">${a.output?`<a class="btn primary" href="${esc(a.output)}" download="ai-film-factory-v05.mp4">↓ Tải MP4</a>`:''}${a.subtitles?`<a class="btn" href="${esc(a.subtitles)}" download="subtitles.srt">↓ Phụ đề SRT</a>`:''}<a class="btn" href="${esc(a.backup||'/api/projects/'+p.id+'/backup')}">↓ Sao lưu toàn bộ ZIP</a></div><p class="tiny">File lưu trên Render Free có thể mất sau khi deploy hoặc restart. Hãy tải MP4/SRT/ZIP về PC ngay sau khi hoàn thành.</p></section>
 <section class="card"><h2>Đưa vào hàng đợi dựng phim</h2><p>Trạng thái storyboard: <strong>${statename(p.script_status)}</strong></p><label class="field" for="renderSeconds">Thời lượng bản thử</label><select id="renderSeconds">${[16,30,60,90,120].map(x=>`<option value="${x}" ${state.preview===x?'selected':''}>${x} giây</option>`).join('')}</select><button class="btn primary full mt16" data-action="render" ${p.script_status==='approved'?'':'disabled'}>▶ FFmpeg dựng video + tiếng + phụ đề</button><p class="tiny">Nếu shot chưa có video: dùng ảnh tĩnh; nếu chưa có ảnh: dùng thẻ mô tả cảnh. Nếu chưa có giọng: đoạn đó im lặng. Đây không phải video AI chuyển động trừ khi bạn đã nhập clip AI thật.</p><div class="divider"></div>${task?`<span class="state ${esc(task.state)}">${esc(task.state)}</span><p>${esc(task.message)}</p>${task.error?`<div class="warning">${esc(task.error)}</div>`:''}`:'<p>Chưa có tác vụ render Hybrid.</p>'}<div class="divider"></div><h3>Nhật ký tác vụ</h3><div class="task-list">${state.tasks.map(x=>`<div class="task-item"><b>${x.kind==='director'?'Ollama Director':'FFmpeg Render'} · ${esc(x.state)}</b><p>${esc(x.message)}</p><small>${esc(x.created)}</small></div>`).join('')||'Chưa có tác vụ'}</div></section></div>`}
function connect(){return heading('CONNECTION HUB','Kết nối và điều phối AI miễn phí','Bản này đã có hàng đợi Ollama và render FFmpeg trên Desktop Agent. Các website AI khác mới ở chế độ mở trang, sao chép prompt, tải file lên khi điều khoản sử dụng cho phép.')+`<div class="grid2">
 <section class="card"><h2>Desktop Agent trên máy Windows</h2><div class="notice">Trạng thái: <b>${state.agent?.agent_online?'Đã kết nối':'Chưa kết nối'}</b><br>Mô hình: <b>${esc(state.agent?.ollama_model||'qwen2.5:7b')}</b><br>Cấu hình token: <b>${state.agent?.agent_pairing_configured?'Đã có trên server':'Chưa cấu hình ở Render'}</b></div><ol class="help"><li>Cài Python 3.11 và Ollama trên Windows.</li><li>Mở PowerShell, chạy <code>ollama pull qwen2.5:7b</code>.</li><li>Giải nén ZIP V0.5, cài thư viện theo <code>requirements.txt</code>.</li><li>Trong Render Environment, đặt <code>AI_FILM_AGENT_TOKEN</code> bằng chuỗi bí mật ngẫu nhiên từ 32 ký tự trở lên.</li><li>Chạy <code>python desktop_agent/agent.py</code>, nhập địa chỉ website và token khi được hỏi.</li><li>Giữ PC bật, rồi nhấn "Phân cảnh bằng Ollama" trên website.</li></ol><div class="warning">Không chụp/gửi Agent Token và không đưa token lên GitHub. Không cần OpenAI API key. Agent kết nối chủ động qua HTTPS, không mở cổng trên router.</div></section>
 <section class="card"><h2>Browser Manager — Bàn giao thủ công</h2><p>Ở V0.5, bạn có thể mở trang AI hợp lệ trong tab mới và sao chép prompt ở mục Ảnh · Video · Giọng. Website chưa tự điều khiển form của các dịch vụ bên ngoài.</p><label class="field" for="externalUrl">Địa chỉ trang AI (HTTPS)</label><input id="externalUrl" type="text" placeholder="https://trang-ai-ban-duoc-phep-su-dung.example"><button class="btn mt16" data-action="openExternal">↗ Mở tab AI</button><div class="divider"></div><h3>Trạng thái các nhà cung cấp</h3><div class="timeline">${[['Ollama Local','Đã tích hợp qua Agent'],['FFmpeg Local','Đã tích hợp qua Agent'],['AI Image trên Chrome','Chưa có adapter tự động'],['AI Video trên Chrome','Chưa có adapter tự động'],['TTS trên Chrome','Nhập tệp thủ công']].map(([n,d],i)=>`<div class="step"><span class="number">${i+1}</span><div><b>${n}</b><small>${d}</small></div></div>`).join('')}</div><p class="tiny">Không vượt CAPTCHA, giới hạn miễn phí, xác thực hoặc điều khoản chống tự động hóa. Chỉ xây adapter cho trang cho phép.</p></section></div>`}
function render(){document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===state.tab));$('breadcrumb').textContent=tabs[state.tab];const b=$('agentBadge');b.textContent=state.agent?.agent_online?'● Desktop Agent đang kết nối':'○ Desktop Agent chưa kết nối';b.className='pill '+(state.agent?.agent_online?'online':'offline');$('view').innerHTML=({dashboard,director,assets,output,connect}[state.tab]||dashboard)();}
async function load(all=true){
 try{
  if(all)state.projects=await get('/projects');
  if(state.pid&&!state.projects.some(x=>x.id===state.pid))state.pid=state.projects[0]?.id||'';
  if(!state.pid&&state.projects.length)state.pid=state.projects[0].id;
  const [agent,project,tasks,assets]=await Promise.all([
   get('/hybrid/status'),state.pid?get('/projects/'+state.pid):Promise.resolve(null),
   state.pid?get('/hybrid/projects/'+state.pid+'/tasks'):Promise.resolve([]),
   state.pid?get('/hybrid/projects/'+state.pid+'/assets'):Promise.resolve(null)]);
  Object.assign(state,{agent,project,tasks,assets});
  if(project&&!project.shots.some(x=>x.id===state.shot))state.shot=project.shots[0]?.id;
  localStorage.setItem('film_v05_pid',state.pid);
  if(all||!document.activeElement||!['TEXTAREA','INPUT','SELECT'].includes(document.activeElement.tagName))render();
  else {const b=$('agentBadge');b.textContent=state.agent?.agent_online?'● Desktop Agent đang kết nối':'○ Desktop Agent chưa kết nối';b.className='pill '+(state.agent?.agent_online?'online':'offline');}
 }catch(e){toast(e.message,true)}
}
function nav(name){state.tab=name;render();window.scrollTo(0,0)}
async function submit(action,elem){
 const p=state.project;const pid=state.pid;
 if(state.busy)return;
 state.busy=true;
 try{
  if(action==='create'){
   let title=$('newTitle').value.trim(),story=$('newScript').value.trim(),minutes=Number($('newMinutes').value);
   if(story.length<10)throw Error('Kịch bản cần ít nhất 10 ký tự');
   const created=await post('/projects',{title,story,minutes});state.pid=created.id;state.shot=null;
   state.tab='director';toast('Đã tạo dự án. Kết nối Agent rồi gửi kịch bản cho Ollama.');
  }else if(action==='saveScript'){
   const title=$('scriptTitle').value.trim(),story=$('scriptBody').value.trim(),minutes=Number($('scriptMinutes').value);
   let regenerate=minutes!==p.minutes;
   if(regenerate&&!confirm('Đổi thời lượng sẽ tạo lại storyboard quy tắc và thay các shot đã chỉnh. Tiếp tục?'))return;
   await get('/projects/'+pid,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,story,minutes,regenerate})});
   toast('Đã lưu kịch bản gốc.');
  }else if(action==='director'){
   if(!confirm('Gửi kịch bản nguyên văn tới Ollama trên PC? Kết quả sẽ thay storyboard sau khi tạo đủ các shot; bản sao lưu nên được tải trước.'))return;
   await post('/hybrid/projects/'+pid+'/director');toast('Đã xếp hàng chờ Desktop Agent.');
  }else if(action==='approve'){
   if(!confirm('Bạn đã kiểm tra các shot, bối cảnh và lời thoại chưa?'))return;
   await post('/projects/'+pid+'/approve-script');toast('Đã duyệt storyboard.');
  }else if(action==='render'){
   const seconds=Number($('renderSeconds').value);state.preview=seconds;
   await post('/hybrid/projects/'+pid+'/render',{seconds});toast('Đã gửi yêu cầu FFmpeg cho Desktop Agent.');
  }else if(action==='shot'){state.shot=elem.dataset.sid;render();return;
  }else if(action==='copyImage'||action==='copyVideo'){
   const s=p.shots.find(x=>x.id===state.shot)||p.shots[0];
   await navigator.clipboard.writeText(action==='copyImage'?s.image_prompt:s.video_prompt);
   toast('Đã sao chép prompt.');return;
  }else if(action==='openExternal'){
   const u=new URL($('externalUrl').value.trim());
   if(u.protocol!=='https:'||!u.hostname.includes('.'))throw Error('Chỉ mở URL HTTPS hợp lệ');
   window.open(u.href,'_blank','noopener,noreferrer');return;
  }
  await load();
 }catch(e){toast(e.message,true)}finally{state.busy=false}
}
document.addEventListener('click',e=>{
 const t=e.target.closest('[data-tab]');if(t){if(t.tagName==='A')return;nav(t.dataset.tab);return;}
 const a=e.target.closest('[data-action]');if(a)submit(a.dataset.action,a);
});
document.addEventListener('change',async e=>{
 if(e.target.id==='chooseProject'){
  state.pid=e.target.value;state.shot=null;localStorage.setItem('film_v05_pid',state.pid);await load();return;
 }
 if(!e.target.dataset.upload)return;
 const f=e.target.files?.[0],kind=e.target.dataset.upload;if(!f||!state.project)return;
 const sid=state.shot;state.busy=true;
 try{
  const form=new FormData();form.append('file',f);
  const r=await fetch(`/api/hybrid/projects/${state.pid}/shots/${sid}/assets/${kind}`,{method:'POST',body:form,credentials:'same-origin'});
  const data=await r.json().catch(()=>({}));if(!r.ok)throw Error(data.detail||`Upload HTTP ${r.status}`);
  toast(`Đã nhận ${kind} cho ${sid}`);await load();
 }catch(err){toast(err.message,true)}finally{state.busy=false}
});
$('logoutLink').addEventListener('click',async e=>{e.preventDefault();await fetch('/auth/logout',{method:'POST',credentials:'same-origin'});location.href='/login'});
load();setInterval(()=>load(false),6500);
})();
