"""Exact-input partial-result recovery; no fabricated silence or successful outcomes."""
import hashlib
import json
import uuid
import wave
from pathlib import Path
from .contract import ChunkTranscriptionResult
from .handler import get_prompts


def repair_tiny_tail(rows, root, measure):
    if len(rows) < 2 or rows[-1]['duration_ms'] >= 250:
        return rows, None
    previous, tail = rows[-2:]
    if previous['offset_ms'] + previous['duration_ms'] != tail['offset_ms']:
        return rows, None
    new_run = 'srun_repair_' + uuid.uuid4().hex[:8]
    directory = root / rows[0]['task_id'] / new_run
    directory.mkdir(parents=True, exist_ok=True)
    merged = directory / 'merged-tail.wav'
    with wave.open(str(previous['file_path']), 'rb') as first, wave.open(str(tail['file_path']), 'rb') as last:
        if first.getparams()[:3] != last.getparams()[:3] or first.getcomptype() != 'NONE' or last.getcomptype() != 'NONE':
            raise ValueError('末段音频格式不同，无法无损合并，请重新切片')
        data = first.readframes(first.getnframes()) + last.readframes(last.getnframes())
        with wave.open(str(merged), 'wb') as output:
            output.setparams(first.getparams());output.writeframes(data)
    new_rows=[]
    for index, old in enumerate(rows[:-1]):
        row = dict(old);row['slice_run_id']=new_run;row['chunk_id']=f"chk_{new_run}_{index:03d}"
        if index == len(rows)-2:
            row.update(file_path=str(merged),duration_ms=previous['duration_ms']+tail['duration_ms'],end_ms=tail['end_ms'],checksum_sha256=hashlib.sha256(merged.read_bytes()).hexdigest(),quality_stats=json.dumps(measure(merged)))
        new_rows.append(row)
    return new_rows, {'policy':'merge_tail_under_250ms','source_chunk_ids':[previous['chunk_id'],tail['chunk_id']], 'new_slice_run_id':new_run,'preserved_end_ms':tail['end_ms']}


def reusable_results(conn, task, rows, model, language):
    result={}
    for run in conn.execute("SELECT * FROM runs WHERE task_id=? AND task_revision=? AND module='asr_alignment' AND run_status='FAILED' ORDER BY created_at DESC",(task['task_id'],task['task_revision'])):
        manifest=json.loads(run['context_manifest'] or '{}')
        if manifest.get('model') != model or manifest.get('is_simulated',False):
            continue
        refs={r['chunk_id']:r.get('hash') for r in json.loads(run['input_refs'])}
        partial=json.loads(run['failure'] or '{}').get('partial_results',[])
        for raw in partial:
            if raw.get('is_simulated') or not raw.get('input_hash'):
                continue
            params=raw.get('prompt_params') or {}
            if params.get('model_id')!=model or params.get('source_language')!=language or params.get('temperature')!=0.0 or params.get('schema_version')!='v1_fixed_pilot':
                continue
            for row in rows:
                if row['chunk_id'] in result or row['checksum_sha256']!=refs.get(raw['chunk_id']) or row['offset_ms']!=raw['offset_ms'] or row['duration_ms']!=raw['duration_ms']:
                    continue
                actual=hashlib.sha256(Path(row['file_path']).read_bytes()).hexdigest()
                system,user=get_prompts(language,row['duration_ms']/1000)
                input_hash=hashlib.sha256((actual+system+user).encode()).hexdigest()
                if actual != row['checksum_sha256'] or input_hash != raw['input_hash']:
                    continue
                item=ChunkTranscriptionResult.model_validate(raw).model_copy(update={'chunk_id':row['chunk_id']})
                result[row['chunk_id']]={'result':item,'source_run_id':run['run_id'],'source_chunk_id':raw['chunk_id']}
    return result
