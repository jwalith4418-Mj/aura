from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class StartSessionRequest(BaseModel):
    domain: str


class ObserveRequest(BaseModel):
    evidence: Dict[str, Any]


class AnswerDiagnosticRequest(BaseModel):
    question_id: str
    option_index: int


class MarkRecoveredRequest(BaseModel):
    passed: bool
    original_problem_id: Optional[str] = None
    note: str = ""


class TransferVerifyRequest(BaseModel):
    passed: bool
    transfer_problem_id: str
    original_problem_id: str
    structurally_different: bool = False
    note: str = ""


class TeachRequest(BaseModel):
    target: str
