"""V0.5 integration smoke: no actual Ollama calls, no paid APIs."""
import io
import os
import subprocess
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0,str(root))
os.environ['APP_MODE']='local'
os.environ['AI_FILM_DATA']=str(Path(tempfile.mkdtemp(prefix='v05-api-test-')))
os.environ['AI_FILM_AGENT_TOKEN']='local-agent-token-test-1234567890-abcdefghijkl'

from fastapi.testclient import TestClient
from PIL import Image
from backend.main import app
from backend.render import get_ffmpeg


def run():
    h={'X-Film-Agent-Token':os.environ['AI_FILM_AGENT_TOKEN']}
    with TestClient(app) as c:
        health=c.get('/api/health').json()
        assert health['version']=='0.5.0' and 'OpenAI' not in str(health)
        assert c.get('/').status_code==200 and 'hybrid.js' in c.get('/').text
        assert c.get('/studio').status_code==200
        assert c.get('/api/ai-writer/status').status_code==404
        status=c.get('/api/hybrid/status').json()
        assert status['openai_enabled'] is False
        assert c.get('/api/hybrid/agent/next').status_code==401
        assert c.get('/api/hybrid/agent/next',headers={'X-Film-Agent-Token':'wrong'}).status_code==401
        p=c.post('/api/projects',json={'title':'Phim kiểm thử V0.5','story':'An bước vào nhà. Lan nói: "Chào An!" An nhìn về cửa sổ.','minutes':1})
        assert p.status_code==201,p.text
        pid=p.json()['id']
        raw=c.post(f'/api/hybrid/projects/{pid}/director')
        assert raw.status_code==202,raw.text
        taskid=raw.json()['id']
        job=c.get('/api/hybrid/agent/next',headers=h,params={'model':'test-model'}).json()['task']
        assert job['id']==taskid and job['story'] == p.json()['story']
        bad=c.post('/api/hybrid/agent/tasks/'+taskid+'/complete-director',headers=h,json={'characters':[],'shots':[]})
        assert bad.status_code==422
        shots=[]
        for i in range(8):
            shots.append({'id':f'SC{i+1:03d}','title':f'Cảnh {i+1}', 'action':'An nhìn về cửa sổ',
                'location':'Phòng khách','camera':'medium closeup','characters':['CAST_C01'],
                'speaker':None,'dialogue':'','image_prompt':'Cinematic drama 9:16',
                'video_prompt':'Natural movement'})
        result=c.post('/api/hybrid/agent/tasks/'+taskid+'/complete-director',headers=h,
                      json={'characters':[{'id':'CAST_C01','name':'An','role':'Nhân vật chính'}],
                            'locations':['Phòng khách'],'shots':shots})
        assert result.status_code==200,result.text
        updated=c.get('/api/projects/'+pid).json()
        assert updated['story']==p.json()['story']
        assert len(updated['shots'])==8 and updated['script_status']=='director_draft'
        assert c.post(f'/api/projects/{pid}/approve-script').status_code==200
        png=io.BytesIO();Image.new('RGB',(300,500),(90,120,160)).save(png,format='PNG')
        u=c.post(f'/api/hybrid/projects/{pid}/shots/SC001/assets/image',files={'file':('shot.png',png.getvalue(),'image/png')})
        assert u.status_code==200,u.text
        asset=c.get(f'/api/hybrid/projects/{pid}/assets').json()['shots'][0]
        assert asset['image'].endswith('SC001.png')
        assert c.get(f'/api/hybrid/agent/assets/{pid}/SC001/image',headers=h).status_code==200
        render_job=c.post(f'/api/hybrid/projects/{pid}/render',json={'seconds':8})
        assert render_job.status_code==202,render_job.text
        rt=render_job.json()['id']
        claimed=c.get('/api/hybrid/agent/next',headers=h).json()['task']
        assert claimed['id']==rt and claimed['kind']=='render'
        ff=get_ffmpeg()
        with tempfile.TemporaryDirectory() as td:
            movie=Path(td)/'film.mp4';srt=Path(td)/'film.srt'
            proc=subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=black:s=320x576:r=8',
                                 '-t','1','-pix_fmt','yuv420p','-c:v','libx264',str(movie)],capture_output=True,text=True,timeout=30)
            assert proc.returncode==0,proc.stderr
            srt.write_text('1\n00:00:00,000 --> 00:00:00,800\nChào An!\n',encoding='utf-8')
            ok=c.post('/api/hybrid/agent/tasks/'+rt+'/complete-render',headers=h,
                      files={'video':('film.mp4',movie.read_bytes(),'video/mp4'),
                             'subtitles':('film.srt',srt.read_bytes(),'text/plain')})
            assert ok.status_code==200,ok.text
        status=c.get(f'/api/hybrid/projects/{pid}/assets').json()
        assert status['output'].endswith('final_hybrid.mp4')
        assert c.get(status['output']).status_code==200
        assert c.get(status['subtitles']).status_code==200
        assert c.get(f'/api/projects/{pid}/backup').status_code==200
    print('V0.5 HYBRID PASS: no paid API, token protection, queue, director, approval, image upload, MP4/SRT + backup')


if __name__=='__main__':run()
