"""Real PCM/FFmpeg slicing, isolated DB; no network."""
import hashlib,json,wave
from pathlib import Path
import pytest
from code.backend.shared.tools.media import MediaTool
from code.backend.modules.asr_alignment.recovery import repair_tiny_tail,reusable_results
from code.backend.modules.asr_alignment.handler import get_prompts
from code.backend.modules.asr_alignment.contract import ChunkTranscriptionResult

@pytest.mark.parametrize('duration_ms',[150000,150001,150200])
def test_short_tail_preserves_every_pcm_frame(tmp_path,monkeypatch,duration_ms):
    tool=MediaTool();monkeypatch.setattr(tool,'measure_audio_quality',lambda path,**kw:{})
    audio=tmp_path/'original.wav';rate=8000
    frames=b'\x00\x00'*(duration_ms*rate//1000-8)+b'\xff\x1f'*8
    with wave.open(str(audio),'wb') as out: out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes(frames)
    rows=tool.slice_audio_fixed(audio,tmp_path/'chunks',end_ms=duration_ms)
    assert len(rows)==15
    assert rows[-1]['end_ms']==duration_ms
    decoded=b''
    for row in rows:
        with wave.open(row['file_path'],'rb') as w: decoded+=w.readframes(w.getnframes())
    assert decoded==frames  # includes non-silent final samples, not just timestamps


def test_pcm_repair_and_exact_input_reuse(tmp_path,isolated_test_env):
    rate=8000;rows=[]
    for i,frames in enumerate([b'\x01\x00'*80000,b'\xff\x1f'*8]):
        path=tmp_path/f'{i}.wav'
        with wave.open(str(path),'wb') as out: out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes(frames)
        duration=10000 if i==0 else 1
        rows.append(dict(task_id='SIMULATED',chunk_id=f'old{i}',offset_ms=i*10000,start_ms=i*10000,end_ms=i*10000+duration,duration_ms=duration,checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),file_path=str(path)))
    fixed,report=repair_tiny_tail(rows,tmp_path/'repair',lambda p:{})
    assert len(fixed)==1 and fixed[0]['duration_ms']==10001 and report['preserved_end_ms']==10001
    with wave.open(fixed[0]['file_path'],'rb') as w: assert w.getnframes()==80008
    system,user=get_prompts('zh-CN',10)
    input_hash=hashlib.sha256((rows[0]['checksum_sha256']+system+user).encode()).hexdigest()
    partial=ChunkTranscriptionResult(chunk_id='old0',offset_ms=0,duration_ms=10000,text='SIMULATED',input_hash=input_hash,prompt_params={'model_id':'SIMULATED','source_language':'zh-CN','temperature':0.0,'schema_version':'v1_fixed_pilot'})
    database=isolated_test_env['db']
    with database.transaction() as c:
        c.execute("INSERT INTO runs(run_id,task_id,task_revision,trace_id,authorization_ref,permission_check_ref,module,input_refs,input_revision,idempotency_key,attempt_no,attempts,run_status,context_manifest,manifest_hash,steps,started_at,usage,controls,output_refs,failure,created_at,created_by) VALUES ('SIMULATED_RUN','SIMULATED',5,'t','a','p','asr_alignment',?,5,'i',1,'[]','FAILED',?,'h','[]','SIMULATED','{}','{}','[]',?,'SIMULATED','SIMULATED')",(json.dumps([{'chunk_id':'old0','hash':rows[0]['checksum_sha256']}]),json.dumps({'model':'SIMULATED'}),json.dumps({'partial_results':[partial.model_dump()]})))
        task={'task_id':'SIMULATED','task_revision':5}
        assert len(reusable_results(c,task,rows,'SIMULATED','zh-CN'))==1
        assert not reusable_results(c,task,fixed,'SIMULATED','zh-CN') # merged bytes differ
        assert not reusable_results(c,task,rows,'OTHER_MODEL','zh-CN')
        assert not reusable_results(c,{**task,'task_revision':6},rows,'SIMULATED','zh-CN')
        Path(rows[0]['file_path']).write_bytes(b'changed')
        assert not reusable_results(c,task,rows,'SIMULATED','zh-CN')
