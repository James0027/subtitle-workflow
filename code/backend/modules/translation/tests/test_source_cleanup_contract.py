"""Task A strict evidence boundary tests; no network or production data."""
import copy
import pytest
from code.backend.modules.translation.source_cleanup import validate_cleanup_structure,get_cleanup_prompts

REFS=[{'chunk_id':'c1','text':'我叫小明。','offset_ms':10000,'duration_ms':1000}]
def valid():
 return {'speakers':[{'speaker_id':'s1','character_ref':'小明','evidence_refs':['c1']}], 'utterances':[{'unit_id':'u1','text':'我叫小明。','source_spans':[{'chunk_id':'c1','original_text':'我叫小明。','start_ms':0,'end_ms':1000}],'speaker_id':'s1','character_ref':'小明','start_ms':10000,'end_ms':11000}], 'operations':[], 'issues':[]}

def test_valid_evidence_and_explicit_self_identification():
 assert validate_cleanup_structure(valid(),{'c1'},REFS).speakers[0].character_ref=='小明'

@pytest.mark.parametrize('case',['extra','confirmed','fake_audio','fake_text','local_time','master_time','unknown_speaker','invented_role','operation_ref','issue_ref','type'])
def test_invalid_output_rejected(case):
 output=valid();unit=output['utterances'][0]
 if case=='extra': output['publish_approved']=True
 if case=='confirmed': unit['status']='CONFIRMED'
 if case=='fake_audio': output['speakers'][0]['evidence_refs']=['c999']
 if case=='fake_text': unit['source_spans'][0]['original_text']='我是老板。'
 if case=='local_time': unit['source_spans'][0]['end_ms']=1001
 if case=='master_time': unit['end_ms']=99999
 if case=='unknown_speaker': unit['speaker_id']='s999'
 if case=='invented_role': output['speakers'][0]['character_ref']='老板';unit['character_ref']='老板'
 if case=='operation_ref': output['operations']=[{'op':'split','detail':'test','unit_id':'u999'}]
 if case=='issue_ref': output['issues']=[{'detail':'test','chunk_ids':['c999']}]
 if case=='type': unit['start_ms']='10000'
 with pytest.raises(ValueError): validate_cleanup_structure(output,{'c1'},REFS)
