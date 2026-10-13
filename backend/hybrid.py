"""V0.5 Hybrid orchestration; no OpenAI / paid provider integrations.

Browser UI authenticates with the existing studio cookie. Desktop Agent uses a
separate long random token in X-Film-Agent-Token, checked by PasswordGate and
also in each agent route. Agent never receives the website login password.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import DATA, connect
from .render import get_ffmpeg

router = APIRouter(prefix='/api/hybrid', tags=['Hybrid local AI'])
KINDS = {'image': {'.jpg', '.jpeg', '.png', '.webp'},
         'video': {'.mp4'}, 'voice': {'.mp3', '.wav'}}
LIMITS = {'image': 12*1024*1024, 'video': 70*1024*1024, 'voice': 15*1024*1024}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def json_text(v):
    return json.dumps(v, ensure_ascii=False)


def init_hybrid():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS hybrid_tasks(
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
            state TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '{}', output TEXT,
            message TEXT NOT NULL DEFAULT '', error TEXT
        );
        CREATE TABLE IF NOT EXISTS hybrid_agent_status(
            id TEXT PRIMARY KEY, seen TEXT NOT NULL, model TEXT NOT NULL DEFAULT ''
        );
        ''')


def project(pid):
    from .main import read_project
    return read_project(pid)


def folder(pid):
    from .main import project_dir
    return project_dir(pid)


def task_by_id(tid):
    with connect() as c:
        row=c.execute('SELECT * FROM hybrid_tasks WHERE id=?', (tid,)).fetchone()
    if not row: raise HTTPException(404, 'Không tìm thấy tác vụ Hybrid')
    task=dict(row)
    task['details']=json.loads(task['details'])
    task['output']=json.loads(task['output']) if task['output'] else None
    return task


def agent_authorized(request: Request):
    token=os.getenv('AI_FILM_AGENT_TOKEN','')
    supplied=request.headers.get('X-Film-Agent-Token','')
    if len(token) < 32 or not hmac.compare_digest(token, supplied):
        raise HTTPException(401,'Desktop Agent chưa ghép nối hoặc token không hợp lệ')


def check_shot(pid, sid):
    p=project(pid)
    if not re.fullmatch(r'SC\d{3,4}',sid):
        raise HTTPException(422,'Mã shot không hợp lệ')
    if sid not in {x['id'] for x in p['shots']}:
        raise HTTPException(404,'Shot không thuộc dự án')
    return p


def asset_file(pid,sid,kind):
    if kind not in KINDS: raise HTTPException(422,'Loại tài nguyên không hợp lệ')
    d=folder(pid)/'hybrid'/kind
    for ext in sorted(KINDS[kind]):
        path=d/(sid+ext)
        if path.is_file():return path
    return None


def assets_for(pid,shots):
    out=[]
    for shot in shots:
        sid=shot['id']; item={'id':sid}
        for kind in KINDS:
            p=asset_file(pid,sid,kind)
            item[kind]=('/media/'+p.relative_to(DATA).as_posix()) if p else None
        out.append(item)
    return out


def put_task(pid,kind,details):
    with connect() as c:
        active=c.execute("SELECT id FROM hybrid_tasks WHERE project_id=? AND state IN ('queued','running')",(pid,)).fetchone()
        if active:raise HTTPException(409,'Dự án đang có tác vụ Hybrid chưa hoàn thành')
        tid='hy_'+uuid.uuid4().hex[:15]
        now=timestamp()
        c.execute('INSERT INTO hybrid_tasks(id,project_id,kind,state,created,updated,details,message) VALUES(?,?,?,?,?,?,?,?)',
                  (tid,pid,kind,'queued',now,now,json_text(details),'Đang chờ Desktop Agent kết nối'))
    return task_by_id(tid)


@router.get('/status')
def status():
    with connect() as c:
        row=c.execute("SELECT seen,model FROM hybrid_agent_status WHERE id='desktop'").fetchone()
    online=False
    if row:
        try: online=(datetime.now(timezone.utc)-datetime.fromisoformat(row['seen'])).total_seconds()<40
        except ValueError:pass
    return {'version':'0.5.0','mode':'hybrid-local','openai_enabled':False,
            'agent_pairing_configured':len(os.getenv('AI_FILM_AGENT_TOKEN',''))>=32,
            'agent_online':online,'agent_last_seen':row['seen'] if row else None,
            'ollama_model':row['model'] if row else None,
            'note':'Ollama cục bộ: phân cảnh thật khi Desktop Agent trực tuyến. Chrome: chuyển giao thủ công trên website được phép. FFmpeg: dựng thật khi có asset.'}


@router.get('/projects/{project_id}/tasks')
def list_tasks(project_id:str):
    project(project_id)
    with connect() as c:
        rows=c.execute('SELECT id FROM hybrid_tasks WHERE project_id=? ORDER BY created DESC LIMIT 15',(project_id,)).fetchall()
    return [task_by_id(r['id']) for r in rows]


@router.post('/projects/{project_id}/director',status_code=202)
def enqueue_director(project_id:str):
    p=project(project_id)
    if len(p['story'].strip())<10:raise HTTPException(422,'Hãy nhập kịch bản hoàn chỉnh trước')
    return put_task(project_id,'director',{
        'story_sha256':hashlib.sha256(p['story'].encode()).hexdigest(),
        'minutes':p['minutes'], 'shots':len(p['shots'])
    })


class RenderInput(BaseModel):
    seconds:int=Field(default=30,ge=4,le=120)


@router.post('/projects/{project_id}/render',status_code=202)
def enqueue_render(project_id:str,payload:RenderInput):
    p=project(project_id)
    if p.get('script_status')!='approved':
        raise HTTPException(409,'Hãy duyệt phân cảnh AI Director trước khi dựng phim thật')
    return put_task(project_id,'render',{'seconds':payload.seconds})


@router.get('/projects/{project_id}/assets')
def get_assets(project_id:str):
    p=project(project_id)
    return {'shots':assets_for(project_id,p['shots']),
            'output':('/media/'+(folder(project_id)/'final_hybrid.mp4').relative_to(DATA).as_posix())
              if (folder(project_id)/'final_hybrid.mp4').exists() else None,
            'subtitles':('/media/'+(folder(project_id)/'final_hybrid.srt').relative_to(DATA).as_posix())
              if (folder(project_id)/'final_hybrid.srt').exists() else None,
            'backup':'/api/projects/'+project_id+'/backup'}


def validate_media(path:Path,kind:str):
    if kind=='image':
        try:
            from PIL import Image
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                if im.width*im.height>32000000:raise ValueError('image too large')
        except Exception as exc:
            raise HTTPException(422,'File không phải ảnh hợp lệ') from exc
        return
    try:
        ex=get_ffmpeg()
        ffprobe=shutil.which('ffprobe')
        if not ffprobe:
            # imageio-ffmpeg may not ship ffprobe; rely on the FFmpeg decoder.
            args=[ex,'-v','error','-i',str(path),'-f','null','-']
            p=subprocess.run(args,capture_output=True,timeout=45)
            if p.returncode:raise ValueError('decoder rejected media')
        else:
            p=subprocess.run([ffprobe,'-v','error','-show_entries','stream=codec_type','-of','csv=p=0',str(path)],
                             capture_output=True,text=True,timeout=25)
            if p.returncode:raise ValueError('ffprobe rejected media')
            got=p.stdout.splitlines()
            if ('video' if kind=='video' else 'audio') not in got:
                raise ValueError('missing stream')
    except (ValueError,subprocess.TimeoutExpired) as exc:
        raise HTTPException(422,'File âm thanh/video không đọc được hoặc thiếu stream phù hợp') from exc


async def save_stream_upload(file:UploadFile,dest:Path,max_bytes:int):
    dest.parent.mkdir(parents=True,exist_ok=True)
    seen=0
    try:
        with dest.open('wb') as f:
            while True:
                chunk=await file.read(1024*1024)
                if not chunk:break
                seen+=len(chunk)
                if seen>max_bytes: raise HTTPException(413,'File quá lớn cho Render Free; hãy thử đoạn ngắn hơn')
                f.write(chunk)
        if seen==0:raise HTTPException(422,'File trống')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post('/projects/{project_id}/shots/{shot_id}/assets/{kind}')
async def upload_asset(project_id:str,shot_id:str,kind:str,file:UploadFile=File(...)):
    check_shot(project_id,shot_id)
    if kind not in KINDS:raise HTTPException(422,'Loại file không được hỗ trợ')
    ext=Path(file.filename or '').suffix.lower()
    if ext not in KINDS[kind]:raise HTTPException(422,'Định dạng file không khớp loại đã chọn')
    d=folder(project_id)/'hybrid'/kind
    temp=d/(shot_id+'_upload_'+uuid.uuid4().hex[:10]+ext)
    await save_stream_upload(file,temp,LIMITS[kind])
    try:
        validate_media(temp,kind)
        for old_ext in KINDS[kind]:
            (d/(shot_id+old_ext)).unlink(missing_ok=True)
        dest=d/(shot_id+ext)
        temp.replace(dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return {'ok':True,'id':shot_id,'kind':kind,'url':'/media/'+dest.relative_to(DATA).as_posix()}


@router.get('/agent/next')
def agent_next(request:Request,model:str=''):
    agent_authorized(request)
    init_hybrid()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO hybrid_agent_status(id,seen,model) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET seen=excluded.seen,model=excluded.model',
                  ('desktop',timestamp(),model[:100]))
        # Resume a previously claimed running task after a crash/restart.
        row=c.execute("SELECT id FROM hybrid_tasks WHERE state='running' ORDER BY created LIMIT 1").fetchone()
        if row is None:
            row=c.execute("SELECT id FROM hybrid_tasks WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row:c.execute('UPDATE hybrid_tasks SET state=?,updated=?,message=? WHERE id=?',
                             ('running',timestamp(),'Desktop Agent đang xử lý',row['id']))
    if not row:return {'task':None}
    t=task_by_id(row['id'])
    p=project(t['project_id'])
    return {'task':{'id':t['id'],'kind':t['kind'],'project_id':t['project_id'],
                    'details':t['details'],'story':p['story'] if t['kind']=='director' else None,
                    'title':p['title'],'minutes':p['minutes'],'characters':p['characters'],
                    'shots':p['shots'] if t['kind']=='render' else None,
                    'assets':assets_for(t['project_id'],p['shots']) if t['kind']=='render' else None}}


class DirectorResult(BaseModel):
    characters:list[dict]=Field(default_factory=list,max_length=20)
    locations:list[str]=Field(default_factory=list,max_length=30)
    shots:list[dict]=Field(min_length=1,max_length=160)


@router.post('/agent/tasks/{task_id}/complete-director')
def director_complete(task_id:str, payload:DirectorResult,request:Request):
    agent_authorized(request)
    t=task_by_id(task_id)
    if t['kind']!='director' or t['state'] not in ('running','queued'):
        raise HTTPException(409,'Tác vụ không còn nhận kết quả đạo diễn')
    p=project(t['project_id'])
    if t['details']['story_sha256'] != hashlib.sha256(p['story'].encode()).hexdigest() or t['details']['minutes']!=p['minutes']:
        raise HTTPException(409,'Kịch bản thay đổi trong khi chạy; không ghi đè dữ liệu')
    # Preserve complete duration and deterministic shot ids. Never trust an arbitrary path or URL from Ollama.
    expected=len(p['shots'])
    if len(payload.shots)!=expected:raise HTTPException(422,f'Cần {expected} phân cảnh, AI trả {len(payload.shots)}')
    cast=[];ids=set(); names=set()
    for ix,c in enumerate(payload.characters):
        name=str(c.get('name','')).strip()[:90]
        if not name or name.casefold() in names:continue
        names.add(name.casefold())
        raw_id=re.sub('[^A-Z0-9_]','_',str(c.get('id','') or name).upper())[:45].strip('_')
        cid=raw_id if raw_id.startswith('CAST_') else 'CAST_'+raw_id
        if cid in ids:cid=f'{cid[:42]}_{ix}'
        ids.add(cid)
        cast.append({'id':cid,'name':name,'role':str(c.get('role',''))[:160],
                     'costume':str(c.get('costume',''))[:300], 'voice':str(c.get('voice',''))[:240]})
    if not cast:cast=[{k:c.get(k,'') for k in ('id','name','role','costume','voice')} for c in p['characters']]
    valid_ids={x['id'] for x in cast}
    shots=[];total=0
    for i,raw in enumerate(payload.shots):
        if not isinstance(raw,dict):raise HTTPException(422,'Shot không hợp lệ')
        expected_id=f'SC{i+1:03d}'
        if raw.get('id')!=expected_id:raise HTTPException(422,f'Shot ID phải là {expected_id}')
        duration=p['shots'][i]['duration_seconds']
        action=str(raw.get('action','')).strip()[:1200]
        if not action:raise HTTPException(422,f'{expected_id} thiếu hành động')
        dialogue=str(raw.get('dialogue','')).strip()[:1500]
        speaker=raw.get('speaker') if raw.get('speaker') in valid_ids else None
        chars=[v for v in raw.get('characters',[]) if v in valid_ids][:10] if isinstance(raw.get('characters'),list) else []
        if speaker and speaker not in chars:chars.append(speaker)
        shot={'id':expected_id,'index':i+1,'start_second':total,'duration_seconds':duration,
            'title':str(raw.get('title','Phân cảnh'))[:140], 'action':action,
            'location':str(raw.get('location','Theo kịch bản'))[:200],
            'camera':str(raw.get('camera','medium shot'))[:150],
            'dialogue':dialogue,'speaker':speaker,'characters':chars,
            'image_prompt':str(raw.get('image_prompt',''))[:3500],
            'video_prompt':str(raw.get('video_prompt',''))[:3500],
            'status':'director_draft',
            'notes':'Phân cảnh do Ollama đề xuất. Giữ nguyên kịch bản gốc; kiểm tra lời thoại và duyệt trước khi tạo hình.'}
        if not shot['image_prompt'] or not shot['video_prompt']:
            raise HTTPException(422,f'{expected_id} thiếu prompt hình/video')
        shots.append(shot);total+=duration
    if total!=p['minutes']*60:raise HTTPException(422,'Sai thời lượng tổng')
    from .main import replace_ai_cast, now
    # Preserve character portraits by matching names inside the existing helper.
    if cast:replace_ai_cast(t['project_id'],cast)
    with connect() as c:
        c.execute('UPDATE projects SET shots=?,script_status=?,status=?,updated=?,final_video=NULL WHERE id=?',
                  (json_text(shots),'director_draft','script_review',now(),t['project_id']))
        c.execute('UPDATE hybrid_tasks SET state=?,updated=?,message=?,output=? WHERE id=?',
                  ('complete',timestamp(),'Hoàn tất phân cảnh, đang chờ bạn duyệt',json_text({'shot_count':len(shots)}),task_id))
    d=folder(t['project_id'])
    (d/'shots.json').write_text(json.dumps(shots,ensure_ascii=False,indent=2),encoding='utf-8')
    (d/'director_outline.json').write_text(json.dumps({'characters':cast,'locations':payload.locations,'provider':'Ollama local'},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'ok':True,'shot_count':len(shots),'script_status':'director_draft'}


class TaskFailure(BaseModel):
    message:str=Field(min_length=1,max_length=700)


@router.post('/agent/tasks/{task_id}/fail')
def task_fail(task_id:str,payload:TaskFailure,request:Request):
    agent_authorized(request)
    t=task_by_id(task_id)
    if t['state'] not in ('queued','running'):raise HTTPException(409,'Tác vụ đã hoàn tất')
    with connect() as c:
        c.execute('UPDATE hybrid_tasks SET state=?,error=?,message=?,updated=? WHERE id=?',
                  ('failed',payload.message,'Thất bại (dữ liệu cũ được giữ nguyên)',timestamp(),task_id))
    return {'ok':True}


@router.get('/agent/assets/{project_id}/{shot_id}/{kind}')
def agent_get_asset(project_id:str,shot_id:str,kind:str,request:Request):
    agent_authorized(request)
    check_shot(project_id,shot_id)
    p=asset_file(project_id,shot_id,kind)
    if not p:raise HTTPException(404,'Không có tệp cho shot')
    return FileResponse(p)


@router.post('/agent/tasks/{task_id}/complete-render')
async def render_complete(task_id:str,request:Request,video:UploadFile=File(...),subtitles:UploadFile=File(...)):
    agent_authorized(request)
    t=task_by_id(task_id)
    if t['kind']!='render' or t['state'] not in ('queued','running'):raise HTTPException(409,'Tác vụ render không hợp lệ')
    if Path(video.filename or '').suffix.lower()!='.mp4' or Path(subtitles.filename or '').suffix.lower()!='.srt':
        raise HTTPException(422,'Đầu ra yêu cầu MP4 và SRT')
    dest=folder(t['project_id'])
    mp4_tmp=dest/('_upload_'+task_id+'.mp4')
    srt_tmp=dest/('_upload_'+task_id+'.srt')
    try:
        await save_stream_upload(video,mp4_tmp,160*1024*1024)
        await save_stream_upload(subtitles,srt_tmp,1*1024*1024)
        validate_media(mp4_tmp,'video')
        if '-->' not in srt_tmp.read_text(encoding='utf-8-sig',errors='replace') and srt_tmp.stat().st_size>0:
            raise HTTPException(422,'Phụ đề SRT không hợp lệ')
        mp4_tmp.replace(dest/'final_hybrid.mp4')
        srt_tmp.replace(dest/'final_hybrid.srt')
    except Exception:
        mp4_tmp.unlink(missing_ok=True);srt_tmp.unlink(missing_ok=True)
        raise
    from .main import now
    url='/media/'+(dest/'final_hybrid.mp4').relative_to(DATA).as_posix()
    with connect() as c:
        c.execute('UPDATE projects SET final_video=?,status=?,updated=? WHERE id=?',
                  (url,'hybrid_ready',now(),t['project_id']))
        c.execute('UPDATE hybrid_tasks SET state=?,updated=?,message=?,output=? WHERE id=?',
                  ('complete',timestamp(),'Đã dựng MP4 + SRT thật',json_text({'video':url}),task_id))
    return {'ok':True,'video_url':url}

class TaskProgress(BaseModel):
    message:str=Field(min_length=1,max_length=230)

@router.post('/agent/tasks/{task_id}/progress')
def task_progress(task_id:str,payload:TaskProgress,request:Request):
    agent_authorized(request)
    t=task_by_id(task_id)
    if t['state']!='running':raise HTTPException(409,'Tác vụ không chạy')
    with connect() as c:
        c.execute('UPDATE hybrid_tasks SET message=?,updated=? WHERE id=?',
                  (payload.message,timestamp(),task_id))
    return {'ok':True}
