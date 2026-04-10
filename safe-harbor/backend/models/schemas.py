from typing import Literal, Optional, List
from pydantic import BaseModel, Field

class ColumnConstraints(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    growth_rate_range: Optional[List[float]] = None  # [min, max] e.g. [-0.1, 0.3]
    must_be_positive: bool = False
    must_be_negative: bool = False
    sum_equals: Optional[str] = None

class ColumnSchema(BaseModel):
    header: str
    data_type: Literal[
        "currency_USD", "currency_EUR", "currency_GBP",
        "percentage", "ratio", "integer", "date", "text"
    ]
    temporal_range: Optional[str] = None
    periods: List[str] = Field(default_factory=list)
    is_input: bool
    cell_references: List[str] = Field(default_factory=list)
    sheet_name: str
    constraints: ColumnConstraints

class InterSheetReference(BaseModel):
    source_sheet: str
    source_column: str
    target_sheet: str
    target_column: str
    relationship: Literal["equals", "feeds_into", "delta"]

class SheetSchema(BaseModel):
    name: str
    columns: List[ColumnSchema]

class TemplateSchema(BaseModel):
    model_type: Literal["LBO", "DCF", "3-statement", "unknown"]
    industry: str
    currency: str
    sheets: List[SheetSchema]
    inter_sheet_refs: List[InterSheetReference]
    total_input_cells: int

class CellValue(BaseModel):
    sheet_name: str
    cell_ref: str
    header: str
    period: str
    value: float | int | str

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class GenerationMetadata(BaseModel):
    model_used: str
    temperature: float
    token_usage: TokenUsage
    generation_time_ms: int

class SyntheticPayload(BaseModel):
    model_type: str
    industry: str
    currency: str
    cells: List[CellValue]
    generation_metadata: GenerationMetadata

class PlugAdjustment(BaseModel):
    target_cell: str
    target_sheet: str
    period: str
    original_value: float
    adjusted_value: float
    delta: float
    reason: str

class ValidationRuleResult(BaseModel):
    rule_name: str
    period: str
    passed: bool
    expected: Optional[float] = None
    actual: Optional[float] = None
    delta: Optional[float] = None
    adjustment_applied: Optional[PlugAdjustment] = None

class ValidationResult(BaseModel):
    status: Literal["PASSED", "PASSED_WITH_PLUGS", "FAILED"]
    rules: List[ValidationRuleResult]
    adjustments: List[PlugAdjustment]
    needs_regeneration: List[str]
    validated_payload: Optional[SyntheticPayload] = None
    validation_timestamp: str

class AuditLogEntry(BaseModel):
    timestamp: str
    phase: Literal["upload", "parse", "schema_extract", "generate", "validate", "write"]
    agent: Optional[str] = None
    detail: str
    data: Optional[dict] = None

class JobState(BaseModel):
    job_id: str
    status: Literal["pending", "parsing", "extracting_schema", "generating", "validating", "writing", "complete", "error"]
    template_schema: Optional[TemplateSchema] = None
    synthetic_payload: Optional[SyntheticPayload] = None
    validation_result: Optional[ValidationResult] = None
    audit_log: List[AuditLogEntry] = Field(default_factory=list)
    cost_entries: List[dict] = Field(default_factory=list)
    output_file_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    parsed_template: Optional[dict] = None

class WSEvent(BaseModel):
    job_id: str
    phase: str
    event_type: Literal["progress", "cell_update", "validation", "complete", "error"]
    detail: str
    data: Optional[dict] = None
