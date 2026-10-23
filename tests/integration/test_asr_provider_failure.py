"""No cloud access: verify quota metadata and one-call stop with isolated fixture storage."""
import json
from pathlib import Path
import httpx

from code.backend.modules.asr_alignment.contract import ASRStatusResponse
from code.backend.modules.asr_alignment.handler import GeminiProviderError
from tests.integration.test_asr_api import test_asr_slice_and_listen_back_flow as prepare_audio


def test_quota_stops_and_commits_failure(auth_client, sample_video, monkeypatch, isolated_test_env):
    prepare_audio(auth_client, sample_video)
    database = isolated_test_env['db']
    with database.transaction() as conn:
        task_id = conn.execute('SELECT task_id FROM tasks LIMIT 1').fetchone()[0]
        source = dict(conn.execute('SELECT * FROM asr_chunks ORDER BY created_at DESC LIMIT 1').fetchone())
        source['chunk_id'] += '_second'
        source['chunk_index'] = 1
        conn.execute(f"INSERT INTO asr_chunks ({','.join(source)}) VALUES ({','.join('?' for _ in source)})", tuple(source.values()))
    # Seed a visibly simulated candidate in the isolated DB, then prove failure preserves it.
    assert auth_client.post(f'/api/v1/tasks/{task_id}/asr/transcribe', json={'simulate': True}).status_code == 200
    before = auth_client.get(f'/api/v1/tasks/{task_id}/asr/candidates').json()['candidates']
    monkeypatch.setattr('code.backend.main.check_cloud_authorization', lambda: ASRStatusResponse(
        model_id='SIMULATED', has_api_key=True, external_outbound_authorized=True,
        budget_authorized=True, allowed_in_pilot=True))
    calls = []
    def quota(**kwargs):
        calls.append(kwargs['chunk_id'])
        raise GeminiProviderError(429, 'RESOURCE_EXHAUSTED', 'SIMULATED daily limit', '53694s')
    monkeypatch.setattr('code.backend.main.transcribe_chunk_gemini', quota)
    response = auth_client.post(f'/api/v1/tasks/{task_id}/asr/transcribe', json={})
    assert response.status_code == 429
    detail = response.json()['detail']
    assert len(calls) == detail['attempted_count'] == 1
    assert len(detail['unattempted_chunk_ids']) == 1
    assert detail['retry_delay'] == '53694s' and '额度不足' in detail['message']
    assert auth_client.get(f'/api/v1/tasks/{task_id}/asr/candidates').json()['candidates'] == before
    with database.transaction() as conn:
        run = dict(conn.execute('SELECT * FROM runs WHERE run_id=?', (detail['run_id'],)).fetchone())
    assert run['run_status'] == 'FAILED'
    assert json.loads(run['failure'])['failed_chunks'][0]['error']['provider_error'] == 'RESOURCE_EXHAUSTED'


def test_adapter_preserves_safe_retry_info(monkeypatch, tmp_path):
    import code.backend.modules.asr_alignment.handler as handler
    monkeypatch.setattr(handler, 'GEMINI_API_KEY', 'SIMULATED-SECRET')
    monkeypatch.setattr(handler, 'check_cloud_authorization', lambda: ASRStatusResponse(
        model_id='SIMULATED', has_api_key=True, external_outbound_authorized=True,
        budget_authorized=True, allowed_in_pilot=True))
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            return httpx.Response(429, json={'error': {'status': 'RESOURCE_EXHAUSTED',
                'message': 'Limit exceeded SIMULATED-SECRET',
                'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '53694s'}]}})
    monkeypatch.setattr(handler.httpx, 'Client', FakeClient)
    audio = tmp_path / 'SIMULATED.wav'
    audio.write_bytes(b'local fake transport fixture')
    try:
        handler.transcribe_chunk_gemini(audio, 'test', 0, 1000)
        assert False, 'Expected provider failure'
    except GeminiProviderError as error:
        assert error.http_status == 429 and error.retry_delay == '53694s'
        assert error.global_failure and 'SIMULATED-SECRET' not in json.dumps(error.safe_detail())


def test_process_shared_minimum_spacing(monkeypatch):
    import code.backend.modules.asr_alignment.handler as handler
    clock = [100.0]
    sleeps, starts = [], []
    monkeypatch.setattr(handler, '_last_request_started', None)
    monkeypatch.setattr(handler.time, 'monotonic', lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(handler.time, 'sleep', sleep)
    class FakeClient:
        def post(self, *args, **kwargs):
            starts.append(clock[0])
    for _ in range(2):
        handler._post_gemini_serial(FakeClient(), 'SIMULATED', {}, {})
    assert sleeps == [4.5] and starts[1] - starts[0] >= 4.5
