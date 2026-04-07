from typing import Literal, Optional, List, Dict
from pydantic import BaseModel, Field

class SecurityQuestion(BaseModel):
    id: int
    category: Literal[
        "access_control", "encryption", "network_security",
        "incident_response", "data_classification", "business_continuity",
        "vendor_management", "physical_security", "compliance",
        "logging_monitoring", "change_management", "other"
    ]
    original_text: str
    normalized_query: str
    requires_telemetry: bool
    requires_policy: bool
    source_row: Optional[int] = None
    source_sheet: Optional[str] = None

class ParsedQuestionnaire(BaseModel):
    source_file: str
    source_format: Literal["xlsx", "csv", "pdf", "docx", "txt"]
    total_questions: int
    questions: List[SecurityQuestion]
    metadata: Optional[dict] = None

class TelemetryEvidence(BaseModel):
    question_id: int
    query_executed: str
    query_type: Literal["athena_sql", "iam_api", "kms_api", "config_api", "mock"]
    raw_result: dict | list
    summary: str
    timestamp: str
    proves: str

class PolicyCitation(BaseModel):
    question_id: int
    policy_document: str
    section: str
    excerpt: str
    relevance_score: float
    chunk_id: str

class DraftAnswer(BaseModel):
    question_id: int
    answer_text: str
    confidence: Literal["high", "medium", "low"]
    evidence_sources: List[Literal["telemetry", "policy", "both", "none"]]
    telemetry_evidence: List[TelemetryEvidence] = Field(default_factory=list)
    policy_citations: List[PolicyCitation] = Field(default_factory=list)
    drift_detected: bool
    drift_detail: Optional[str] = None
    needs_human_review: bool

class DriftAlert(BaseModel):
    question_id: int
    severity: Literal["critical", "warning", "info"]
    policy_states: str
    telemetry_shows: str
    recommendation: str

class QuestionnaireResult(BaseModel):
    total_questions: int
    answered: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    drift_alerts: int
    needs_review: int
    answers: List[DraftAnswer]
    processing_time_ms: int
    export_ready: bool

class ShieldWallAuditEntry(BaseModel):
    timestamp: str
    phase: str
    agent: Optional[str] = None
    detail: str
    data: Optional[dict] = None

class ShieldWallJobState(BaseModel):
    job_id: str
    status: Literal[
        "pending", "parsing", "classifying",
        "querying_telemetry", "querying_policies",
        "synthesizing", "detecting_drift",
        "complete", "error"
    ]
    questionnaire: Optional[ParsedQuestionnaire] = None
    result: Optional[QuestionnaireResult] = None
    drift_alerts: List[DriftAlert] = Field(default_factory=list)
    audit_log: List[ShieldWallAuditEntry] = Field(default_factory=list)
    cost_entries: List[dict] = Field(default_factory=list)
    error_message: Optional[str] = None

class ShieldWallWSEvent(BaseModel):
    job_id: str
    phase: str
    event_type: Literal["progress", "answer_update", "drift_alert", "complete", "error"]
    detail: str
    data: Optional[dict] = None
