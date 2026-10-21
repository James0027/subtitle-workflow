"""Resume audit: isolated SQLite and zero cloud requests; not product code."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
os.environ['SUBTITLE_TEST_MODE'] = '1'
import config.settings as settings
settings.DB_PATH = HERE / 'isolated-import.db'
settings.GEMINI_API_KEY = ''
settings.GEMINI_EXTERNAL_OUTBOUND_AUTHORIZED = False
settings.GEMINI_BUDGET_AUTHORIZED = False

import httpx
def deny_cloud(*args, **kwargs):
    raise AssertionError('Cloud requests forbidden in resume audit')
httpx.HTTPTransport.handle_request = deny_cloud

import pytest
class AuditPaths:
    @pytest.fixture
    def tmp_path(self, request):
        path = HERE / 'isolated-tests' / request.node.name
        path.mkdir(parents=True, exist_ok=True)
        return path
code = pytest.main(['-q', 'code/backend/modules/culture_check/tests/test_culture_check.py',
                    '--junitxml', str(HERE / 'pytest-results.xml')], plugins=[AuditPaths()])

from fastapi import FastAPI
from fastapi.testclient import TestClient
from code.backend.modules.culture_check.contract import CultureCheckRequest
from code.backend.modules.culture_check.validator import validate_and_process_culture_issues
from code.backend.modules.culture_check.registry import default_registry
from code.backend.modules.culture_check.router import router

request = CultureCheckRequest(task_ref='AUDIT-NONEXISTENT-TASK', task_revision=999,
    arbitrary_extra='should fail', units=[dict(unit_id='u1',source_text='测试',target_text='prueba')])
raw = dict(unit_id='u1', category='legal_platform', trigger_spans=[dict(target_span='prueba')],
    severity_proposal='P0', impact_level=3, occurrence_likelihood=3, remediation_difficulty=3,
    confidence=dict(raw_score=.99,basis='uncalibrated'), evidence_status='sufficient',
    rule_refs=['R-MX-CINEMA-01'],case_refs=['FAKE-CASE'],evidence_refs=['FAKE-EVIDENCE'],
    explanation='测试虚构证据',suggested_action='block_release')
processed = validate_and_process_culture_issues(request,[raw],['u1'],[],
    default_registry.retrieve_applicable_rules('MX',only_active=True),set())
app = FastAPI()
app.include_router(router)
with TestClient(app) as client:
    response = client.post('/api/v1/culture/check',json=request.model_dump())
result = dict(historical_tests_exit_code=int(code),cloud_calls=0,
    unknown_input_field_accepted=True,
    fabricated_evidence_p0_retained=processed[0].severity_proposal=='P0',
    fabricated_case_reference_accepted=processed[0].case_refs==['FAKE-CASE'],
    unauthenticated_nonexistent_task_check_status=response.status_code,
    test_mode=True, production_route_mounted=False,
    history_reconstructed_from_disk=True,
    new_gemini_dispatch='not accepted: host approval policy never; precondition pending')
(HERE/'audit-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
