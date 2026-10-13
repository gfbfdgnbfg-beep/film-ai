"""AI Film Factory V0.5 Windows Desktop Agent.

Uses Ollama for local director and FFmpeg to render user-supplied image/video
assets and optional voice audio. It NEVER signs in to third-party AI sites,
submits to paid APIs, or bypasses provider restrictions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import textwrap
from getpass import getpass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

DEFAULT_SERVER='https://ai-film-factory-studio.onrender.com'
OLLAMA_URL=os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
MODEL=os.getenv('OLLAMA_MODEL','qwen2.5:7b')
BASE=Path(__file__).resolve().parent


def ensure_server(address):
    parsed=urlparse(address)
    if parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
        return address.rstrip('/')
    raise ValueError('Chỉ cho phép HTTPS từ xa hoặc HTTP tới localhost, để bảo vệ Agent Token')


class Remote:
    def __init__(self,server,token):
        self.server=ensure_server(server)
        self.http=httpx.Client(headers={'X-Film-Agent-Token':token},timeout=httpx.Timeout(180,connect=12))

    def get(self,path,params=None):
        r=self.http.get(self.server+path,params=params)
        if r.status_code>=400:raise RuntimeError(f'Server HTTP {r.status_code}: {r.text[:250]}')
        return r

    def post(self,path,payload):
        r=self.http.post(self.server+path,json=payload)
        if r.status_code>=400:raise RuntimeError(f'Server HTTP {r.status_code}: {r.text[:350]}')
        return r.json()

    def progress(self,tid,message):
        self.post('/api/hybrid/agent/tasks/'+tid+'/progress',{'message':message})

    def fail(self,tid,message):
        return self.post('/api/hybrid/agent/tasks/'+tid+'/fail',{'message':str(message)[:650]})

    def send_render(self,tid,mp4:Path,srt:Path):
        with mp4.open('rb') as f, srt.open('rb') as g:
            r=self.http.post(self.server+'/api/hybrid/agent/tasks/'+tid+'/complete-render',
                             files={'video':(mp4.name,f,'video/mp4'), 'subtitles':(srt.name,g,'text/plain')},
                             timeout=httpx.Timeout(600,connect=20))
        if r.status_code>=400: raise RuntimeError('Lỗi upload MP4: '+r.text[:350])
        return r.json()


def ollama_json(prompt,*,num_predict=3200):
    try:
        with httpx.Client(timeout=httpx.Timeout(400,connect=10)) as client:
            r=client.post(OLLAMA_URL+'/api/chat',json={
                'model':MODEL,'stream':False,'format':'json',
                'options':{'temperature':0.25,'num_predict':num_predict},
                'messages':[{'role':'system','content':'Bạn là đạo diễn phim. Luôn trả JSON hợp lệ. Không viết lại, không bịa lời thoại không có trong kịch bản.'},
                            {'role':'user','content':prompt}]})
            r.raise_for_status()
            content=r.json()['message']['content']
        raw=json.loads(content)
        if not isinstance(raw,dict):raise ValueError('Output JSON không phải object')
        return raw
    except httpx.ConnectError as exc:
        raise RuntimeError('Không kết nối Ollama tại '+OLLAMA_URL+'. Hãy mở Ollama và tải mô hình: ollama pull '+MODEL) from exc
    except (ValueError,KeyError,IndexError) as exc:
        raise RuntimeError('Ollama chưa trả JSON hợp lệ; thử lại hoặc thay model') from exc


def _clean(s,n=220):
    return str(s or '').strip()[:n]


def char_id(name):
    text=re.sub(r'[^A-Z0-9]+','_',name.upper()).strip('_')
    return 'CAST_'+(text[:38] or 'NV')


def normalize_text(s):
    return re.sub(r'\s+',' ',str(s)).strip().casefold().strip('“”"\' ')


def analyze_script(task,remote):
    text=task['story'].strip()
    shots_total=(task['minutes']*60+7)//8
    title=task['title']
    tid=task['id']
    remote.progress(tid,'Đang trích xuất nhân vật và bối cảnh với '+MODEL)
    source_cast=task.get('characters') or []
    outline=ollama_json('''Đọc kịch bản GỐC sau. KHÔNG viết lại nội dung.
Trả JSON object có: characters (mảng {name,role,costume,voice}), locations (mảng tên địa điểm), summary (tóm tắt tình tiết). Tối đa 12 nhân vật. Chỉ nhận nhân vật được nhắc trong kịch bản.
Tên phim: '''+title+'\nKỊCH BẢN:\n'+text[:25000],num_predict=2800)
    cast=[]; seen=set()
    for c in (outline.get('characters') or []):
        if not isinstance(c,dict):continue
        name=_clean(c.get('name'),80)
        if not name or name.casefold() in seen:continue
        seen.add(name.casefold())
        # IDs are ASCII: simple stable index, not derived from accents.
        cast.append({'id':f'CAST_C{len(cast)+1:02d}','name':name,
                     'role':_clean(c.get('role'),160),'costume':_clean(c.get('costume'),250),
                     'voice':_clean(c.get('voice'),160)})
    if not cast:
        cast=[{**c,'id':_clean(c.get('id'),50)} for c in source_cast if c.get('name')]
    locations=[_clean(x,140) for x in (outline.get('locations') or []) if isinstance(x,str)][:20]
    past=[]
    for offset in range(0,shots_total,7):
        batch=[{'id':f'SC{i+1:03d}','start_second':i*8,
                'duration_seconds':min(8,task['minutes']*60-i*8)}
               for i in range(offset,min(shots_total,offset+7))]
        remote.progress(tid,f'Ollama đang chia cảnh {offset+1}–{offset+len(batch)} / {shots_total}')
        payload={'full_script':text[:25000], 'film_title':title,
                 'summary':_clean(outline.get('summary'),900),'locations':locations,
                 'characters':cast,'recent_shots':[{k:s.get(k,'') for k in ('title','action')} for s in past[-2:]],
                 'requested_shots':batch}
        instruction='''Bạn là ĐẠO DIỄN, không phải biên kịch. Không thêm nhân vật, tình tiết hoặc lời thoại mới.
Kịch bản người dùng là sự thật duy nhất. Chia diễn biến kịch bản thành CHÍNH XÁC các shot trong requested_shots, giữ thứ tự câu chuyện; mỗi shot phải tương ứng điểm hợp lý trên trục thời gian.
Quyết định location, camera, ánh sáng, hành động, và mô tả tạo ảnh/video. Nếu đoạn gốc không có lời thoại, để dialogue trống.
Nếu có lời thoại: CHỈ ĐƯỢC chép đúng nguyên văn từng câu xuất hiện trong full_script, không tự viết. Gán speaker theo ID characters hoặc null.
Trả JSON object {"shots":[...]}, đúng số lượng; từng shot có keys: id,title,action,location,camera,dialogue,speaker,characters,image_prompt,video_prompt.
image_prompt và video_prompt tiếng Anh mô tả phong cách điện ảnh Việt Nam, ảnh tham chiếu nhân vật, 9:16, no text. characters chứa các ID đã được cung cấp. Không đảo thứ tự và không bỏ shot.
ĐẦU VÀO:\n'''
        out=ollama_json(instruction+json.dumps(payload,ensure_ascii=False),num_predict=6500)
        items=out.get('shots')
        if not isinstance(items,list) or len(items)!=len(batch):
            raise RuntimeError(f'Ollama trả {len(items) if isinstance(items,list) else "sai"} shot, cần {len(batch)} shot nhóm {offset+1}. Storyboard cũ chưa đổi.')
        cast_ids={c['id'] for c in cast}
        for wanted,raw in zip(batch,items):
            if not isinstance(raw,dict):raise RuntimeError('Có shot không hợp lệ')
            if raw.get('id')!=wanted['id']:raise RuntimeError(f'ID shot sai: cần {wanted["id"]}')
            dialogue=_clean(raw.get('dialogue'),1500)
            # Reject invented dialogue; no automatic rewriting of the script.
            if dialogue and normalize_text(dialogue) not in normalize_text(text):
                dialogue=''
            person=raw.get('speaker') if raw.get('speaker') in cast_ids else None
            chars=[x for x in (raw.get('characters') or []) if x in cast_ids]
            action=_clean(raw.get('action'),1200)
            if not action:raise RuntimeError(f'{wanted["id"]}: không có hành động')
            past.append({'id':wanted['id'], 'title':_clean(raw.get('title'),140) or 'Phân cảnh',
                'action':action,'location':_clean(raw.get('location'),200) or 'Theo kịch bản',
                'camera':_clean(raw.get('camera'),150) or 'medium shot',
                'dialogue':dialogue,'speaker':person if dialogue else None,
                'characters':chars,
                'image_prompt':_clean(raw.get('image_prompt'),3500) or 'Cinematic Vietnamese drama, '+action+', portrait 9:16, no text.',
                'video_prompt':_clean(raw.get('video_prompt'),3500) or 'Subtle cinematic motion: '+action})
    return {'characters':cast,'locations':locations,'shots':past}


def ffmpeg_exe():
    path=shutil.which('ffmpeg')
    if path:return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError('Không tìm thấy FFmpeg. Cài ffmpeg vào PATH hoặc pip install imageio-ffmpeg') from exc


def run_ffmpeg(cmd,timeout=250,cwd=None):
    p=subprocess.run([ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y',*map(str,cmd)],
                     capture_output=True,text=True,timeout=timeout,cwd=cwd)
    if p.returncode:
        raise RuntimeError('FFmpeg: '+p.stderr[-650:])


def font(size):
    for name in ('C:/Windows/Fonts/arial.ttf','C:/Windows/Fonts/segoeui.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(name).is_file():return ImageFont.truetype(name,size)
    return ImageFont.load_default()


def placeholder(shot,dest):
    im=Image.new('RGB',(480,854),(15,26,40))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((24,25,456,820),radius=24,outline=(74,105,133),width=2)
    d.text((44,70),'AI FILM FACTORY • V0.5',font=font(18),fill='#9bbed1')
    d.text((44,165),shot['id'],font=font(34),fill='#ffffff')
    y=240
    for text in (shot.get('title',''),shot.get('action','')):
        for line in textwrap.wrap(text, width=29)[:7]:
            d.text((44,y),line,font=font(21),fill='#e0eaf2');y+=32
    d.text((44,770),'Ảnh chờ nhập • chưa có video AI',font=font(16),fill='#9bbed1')
    im.save(dest,'PNG')


def srt_time(secs):
    ms=round(secs*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def render_film(task,remote,workdir):
    tid=task['id'];pid=task['project_id'];seconds=task['details']['seconds']
    remain=seconds;chosen=[]
    for item in task['shots']:
        if remain<=0:break
        take=min(remain,item['duration_seconds']);chosen.append((item,take));remain-=take
    mapping={a['id']:a for a in task['assets']}
    parts=[];subtitle=[];t=0
    (workdir/'shots').mkdir(exist_ok=True)
    for i,(shot,duration) in enumerate(chosen):
        sid=shot['id'];remote.progress(tid,f'FFmpeg: đang dựng {i+1}/{len(chosen)} • {sid}')
        asset=mapping[sid]
        filepaths={}
        for kind in ('video','image','voice'):
            if asset.get(kind):
                ex=Path(urlparse(asset[kind]).path).suffix
                path=workdir/'shots'/(sid+'_'+kind+ex)
                res=remote.get('/api/hybrid/agent/assets/'+pid+'/'+sid+'/'+kind)
                path.write_bytes(res.content)
                filepaths[kind]=path
        image=filepaths.get('image')
        if not filepaths.get('video') and not image:
            image=workdir/'shots'/(sid+'_placeholder.png')
            placeholder(shot,image)
        pure=workdir/'shots'/(sid+'_video.mp4')
        vf='scale=480:854:force_original_aspect_ratio=increase,crop=480:854,setsar=1,fps=24,format=yuv420p'
        if 'video' in filepaths:
            run_ffmpeg(['-stream_loop','-1','-i',filepaths['video'],'-t',duration,'-vf',vf,'-an',
                        '-c:v','libx264','-preset','ultrafast','-crf','26',pure],timeout=200)
        else:
            run_ffmpeg(['-loop','1','-framerate','24','-i',image,'-t',duration,'-vf',vf,'-an',
                        '-c:v','libx264','-preset','ultrafast','-crf','26',pure],timeout=200)
        part=workdir/'shots'/(sid+'_with_sound.mp4')
        if 'voice' in filepaths:
            run_ffmpeg(['-i',pure,'-i',filepaths['voice'],'-filter_complex',
                        f'[1:a]apad,atrim=0:{duration},aresample=44100[a]',
                        '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','96k','-t',duration,part],timeout=120)
        else:
            run_ffmpeg(['-i',pure,'-f','lavfi','-t',duration,'-i',
                        'anullsrc=channel_layout=stereo:sample_rate=44100',
                        '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','96k',
                        '-t',duration,part],timeout=120)
        parts.append(part)
        if shot.get('dialogue'):
            subtitle.extend([str(len(subtitle)//4+1),f'{srt_time(t)} --> {srt_time(t+duration)}',shot['dialogue'],''])
        t+=duration
    srt=workdir/'final_hybrid.srt'
    srt.write_text('\n'.join(subtitle),encoding='utf-8-sig')
    concat=workdir/'files.txt'
    concat.write_text(''.join("file '"+x.resolve().as_posix().replace("'","'\\''")+"'\n" for x in parts),encoding='utf-8')
    merged=workdir/'merged.mp4';output=workdir/'final_hybrid.mp4'
    remote.progress(tid,'Đang ghép cảnh, âm thanh và phụ đề')
    run_ffmpeg(['-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',merged],timeout=240)
    # Burn subtitles into video if FFmpeg includes libass. SRT remains available either way.
    if subtitle:
        try:
            run_ffmpeg(['-i','merged.mp4','-vf',"subtitles=final_hybrid.srt:force_style='FontSize=18,Alignment=2,MarginV=36'",
                        '-c:v','libx264','-preset','fast','-crf','25','-c:a','copy','-movflags','+faststart',
                        'final_hybrid.mp4'],timeout=300,cwd=workdir)
        except Exception:
            # Windows drive paths and some ffmpeg binaries don't include libass.
            shutil.copy2(merged,output)
            print('FFmpeg hiện tại chưa chèn phụ đề vào hình. File SRT vẫn đi kèm.')
    else:shutil.copy2(merged,output)
    return output,srt


def main():
    server=os.getenv('AI_FILM_SERVER','').strip() or input(f'Địa chỉ website [{DEFAULT_SERVER}]: ').strip() or DEFAULT_SERVER
    token=os.getenv('AI_FILM_AGENT_TOKEN','').strip() or getpass('Agent Pairing Token trên Render (nhập ẩn): ').strip()
    if len(token)<32:raise SystemExit('Token cần ít nhất 32 ký tự. Tạo bí mật khác mật khẩu website.')
    client=Remote(server,token)
    print('AI Film Factory V0.5 • Desktop Agent • Ollama '+MODEL)
    print('Kết nối server:',client.server,'| Ollama:',OLLAMA_URL)
    print('Không sử dụng OpenAI, không gọi dịch vụ AI trả phí.')
    running_id=None
    while True:
        try:
            data=client.get('/api/hybrid/agent/next',params={'model':MODEL}).json()
            task=data.get('task')
            if not task:
                time.sleep(6);continue
            if running_id==task['id']:
                time.sleep(6);continue
            running_id=task['id']
            print('Nhận tác vụ',task['id'],task['kind'])
            try:
                if task['kind']=='director':
                    output=analyze_script(task,client)
                    client.post('/api/hybrid/agent/tasks/'+task['id']+'/complete-director',output)
                    print('Đã tạo storyboard. Hãy vào website để duyệt.')
                elif task['kind']=='render':
                    with tempfile.TemporaryDirectory(prefix='film_factory_') as d:
                        mp4,srt=render_film(task,client,Path(d))
                        client.send_render(task['id'],mp4,srt)
                    print('Đã gửi MP4 và SRT về website.')
                else:raise RuntimeError('Loại tác vụ chưa được hỗ trợ: '+task['kind'])
            except Exception as exc:
                print('Lỗi tác vụ:',str(exc))
                try:client.fail(task['id'],str(exc))
                except Exception as e:print('Không cập nhật được lỗi lên server:',e)
            finally:running_id=None
        except KeyboardInterrupt:
            print('\nĐã dừng Agent.');return
        except Exception as exc:
            print('Chưa kết nối:',str(exc));time.sleep(10)


if __name__=='__main__':main()
