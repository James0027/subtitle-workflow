"""Strict model-only response contracts; server status and identities are excluded."""
from typing import List,Literal,Optional
from pydantic import BaseModel,ConfigDict

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class PromptTermHit(StrictModel):
    source_term:str
    required_target:str
    actual_target:str
    term_ref:Optional[str]=None
    matched:bool

class PromptTranslation(StrictModel):
    unit_id:str
    translation:str
    term_hits:List[PromptTermHit]
    brief_source_paraphrase:Optional[str]
    issues:List[str]

class PromptTranslationOutput(StrictModel):
    schema_version:Literal['1.0.0']='1.0.0'
    translations:List[PromptTranslation]

class PromptCheckIssue(StrictModel):
    unit_id:str
    category:Literal['omission','addition','number','negation','entity','relationship','address','context','other']
    severity:Literal['BLOCK','WARN','INFO']
    source_span:Optional[str]=None
    target_span:Optional[str]=None
    detail:str
    suggestion:Optional[str]=None
    uncertainty:Optional[str]=None

class PromptCheckOutput(StrictModel):
    schema_version:Literal['1.0.0']='1.0.0'
    issues:List[PromptCheckIssue]
    qe_status:Optional[Literal['未评估']]=None
