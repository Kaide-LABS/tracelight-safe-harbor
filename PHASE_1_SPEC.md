# PHASE 1 TECHNICAL SPECIFICATION
## Safe-Harbor Synthetic Financial Data Fabric
### File-by-File, Function-by-Function Blueprint for Execution Agent

---

## 0. ENVIRONMENT & DEPENDENCIES

### Python Version
```
Python 3.12+
```

### `requirements.txt`
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
python-multipart==0.0.18
websockets==14.*
openpyxl==3.1.*
pandas==2.2.*
numpy==2.1.*
pydantic==2.10.*
openai==1.66.*
google-genai==1.14.*
python-dotenv==1.0.*
aiofiles==24.*
```

### `.env` (template — never committed)
```
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
SAFE_HARBOR_MAX_FILE_SIZE_MB=25
SAFE_HARBOR_MAX_RETRIES=3
SAFE_HARBOR_GENERATION_TIMEOUT_S=60
```

### Frontend
```
Node 20+
React 18
Vite 6
Tailwind CSS 3.4
```

---

## 1. DIRECTORY STRUCTURE (exact)

```
safe-harbor/
├── backend/
│   ├── main.py
│   ├── orchestrator.py
│   ├── config.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── schema_extractor.py
│   │   ├── synthetic_gen.py
│   │   └── validator.py
│   ├── excel_io/
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   └── writer.py
│   └── models/
│       ├── __init__.py
│       └── schemas.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── UploadZone.jsx
│       │   ├── SchemaTerminal.jsx
│       │   ├── DataWaterfall.jsx
│       │   ├── VerdictBadge.jsx
│       │   └── AuditTrail.jsx
│       └── hooks/
│           └── useWebSocket.js
├── templates/
│   ├── lbo_template.xlsx
│   ├── dcf_template.xlsx
│   └── three_statement_template.xlsx
├── tests/
│   ├── test_parser.py
│   ├── test_validator.py
│   ├── test_schema_extractor.py
│   ├── test_synthetic_gen.py
│   └── test_orchestrator.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 2. PYDANTIC SCHEMAS — `backend/models/schemas.py`

Every data contract in the system. All agents read/write these models. No ad-hoc dicts.

### 2.1 `ColumnSchema`

```python
class ColumnSchema(BaseModel):
    header: str                          # e.g. "Revenue", "Senior Debt Tranche A"
    data_type: Literal[
        "currency_USD", "currency_EUR", "currency_GBP",
        "percentage", "ratio", "integer", "date", "text"
    ]
    temporal_range: str | None = None    # e.g. "FY2020-FY2025"
    periods: list[str] = []             # e.g. ["FY2020","FY2021",...,"FY2025"]
    is_input: bool                       # True = empty cell to fill; False = formula cell, skip
    cell_references: list[str] = []     # e.g. ["B5","C5","D5","E5","F5","G5"]
    sheet_name: str
    constraints: "ColumnConstraints"
```

### 2.2 `ColumnConstraints`

```python
class ColumnConstraints(BaseModel):
    min_value: float | None = None
    max_value: float | None = None
    growth_rate_range: tuple[float, float] | None = None  # e.g. (-0.1, 0.3)
    must_be_positive: bool = False
    must_be_negative: bool = False
    sum_equals: str | None = None        # ref to another column header it must equal
```

### 2.3 `InterSheetReference`

```python
class InterSheetReference(BaseModel):
    source_sheet: str
    source_column: str
    target_sheet: str
    target_column: str
    relationship: Literal["equals", "feeds_into", "delta"]
```

### 2.4 `TemplateSchema` — Output of Schema Extraction Agent

```python
class TemplateSchema(BaseModel):
    model_type: Literal["LBO", "DCF", "3-statement", "unknown"]
    industry: str                        # e.g. "Healthcare SaaS"
    currency: str                        # e.g. "USD"
    sheets: list["SheetSchema"]
    inter_sheet_refs: list[InterSheetReference]
    total_input_cells: int
```

### 2.5 `SheetSchema`

```python
class SheetSchema(BaseModel):
    name: str                            # Excel sheet name
    columns: list[ColumnSchema]
```

### 2.6 `CellValue`

```python
class CellValue(BaseModel):
    sheet_name: str
    cell_ref: str                        # e.g. "B5"
    header: str
    period: str                          # e.g. "FY2022"
    value: float | int | str
```

### 2.7 `SyntheticPayload` — Output of Synthetic Generation Agent

```python
class SyntheticPayload(BaseModel):
    model_type: str
    industry: str
    currency: str
    cells: list[CellValue]
    generation_metadata: "GenerationMetadata"
```

### 2.8 `GenerationMetadata`

```python
class GenerationMetadata(BaseModel):
    model_used: str                      # "gpt-4o"
    temperature: float
    token_usage: "TokenUsage"
    generation_time_ms: int
```

### 2.9 `TokenUsage`

```python
class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

### 2.10 `ValidationRuleResult`

```python
class ValidationRuleResult(BaseModel):
    rule_name: str                       # e.g. "balance_sheet_identity"
    period: str                          # e.g. "FY2022"
    passed: bool
    expected: float | None = None
    actual: float | None = None
    delta: float | None = None
    adjustment_applied: "PlugAdjustment | None" = None
```

### 2.11 `PlugAdjustment`

```python
class PlugAdjustment(BaseModel):
    target_cell: str                     # e.g. "Cash"
    target_sheet: str
    period: str
    original_value: float
    adjusted_value: float
    delta: float
    reason: str                          # e.g. "BS imbalance: Assets - (Liab + Eq) = +142000"
```

### 2.12 `ValidationResult` — Output of Validation Agent

```python
class ValidationResult(BaseModel):
    status: Literal["PASSED", "PASSED_WITH_PLUGS", "FAILED"]
    rules: list[ValidationRuleResult]
    adjustments: list[PlugAdjustment]
    needs_regeneration: list[str]        # column headers that need retry
    validated_payload: SyntheticPayload | None  # payload after plug adjustments
    validation_timestamp: str            # ISO-8601
```

### 2.13 `AuditLogEntry`

```python
class AuditLogEntry(BaseModel):
    timestamp: str                       # ISO-8601
    phase: Literal["upload", "parse", "schema_extract", "generate", "validate", "write"]
    agent: str | None = None
    detail: str
    data: dict | None = None             # arbitrary JSON for the audit trail
```

### 2.14 `JobState`

```python
class JobState(BaseModel):
    job_id: str                          # UUID
    status: Literal["pending", "parsing", "extracting_schema", "generating", "validating", "writing", "complete", "error"]
    template_schema: TemplateSchema | None = None
    synthetic_payload: SyntheticPayload | None = None
    validation_result: ValidationResult | None = None
    audit_log: list[AuditLogEntry] = []
    output_file_path: str | None = None
    error_message: str | None = None
    retry_count: int = 0
```

### 2.15 `WSEvent` — WebSocket event sent to frontend

```python
class WSEvent(BaseModel):
    job_id: str
    phase: str
    event_type: Literal["progress", "cell_update", "validation", "complete", "error"]
    detail: str
    data: dict | None = None
```

---

## 3. CONFIGURATION — `backend/config.py`

### Purpose
Centralized config loaded from `.env` via `python-dotenv`. No scattered env reads.

### Exports

```python
class Settings(BaseModel):
    openai_api_key: str
    google_cloud_project: str
    google_cloud_location: str           # default "us-central1"
    max_file_size_mb: int                # default 25
    max_retries: int                     # default 3
    generation_timeout_s: int            # default 60
    gpt4o_model: str                     # default "gpt-4o"
    gemini_model: str                    # default "gemini-2.0-flash"
    generation_temperature: float        # default 0.3

def get_settings() -> Settings:
    """Load from .env, return frozen Settings instance."""
```

---

## 4. EXCEL PARSER — `backend/excel_io/parser.py`

### Purpose
Read an uploaded `.xlsx` with openpyxl. Extract structure, detect input cells vs formula cells, capture inter-sheet references.

### Dependencies
- `openpyxl` (load_workbook with `data_only=False` to preserve formulas)

### Functions

#### `parse_template(file_path: str) -> dict`

**Input:** Path to uploaded `.xlsx` on disk.

**Logic:**
1. `wb = openpyxl.load_workbook(file_path, data_only=False)` — preserves formulas.
2. For each `ws` in `wb.worksheets`:
   - Read row 1 as headers (skip empty columns).
   - For each column with a header:
     - Scan cells in rows 2..N.
     - If `cell.value` is `None` or empty string → `is_input = True`.
     - If `cell.value` is a string starting with `=` → `is_input = False` (formula cell).
     - Collect all `cell_references` for input cells (e.g. `"B5"` from `cell.coordinate`).
   - Detect temporal headers by regex: match `FY\d{4}`, `CY\d{4}`, `\d{4}E`, `\d{4}A`, or pure year integers.
3. Extract named ranges via `wb.defined_names.definedName` — iterate the `DefinedNameList`, call `.attr_text` to get the sheet/cell references.
4. Detect inter-sheet references:
   - For every formula cell, parse the string for patterns like `'Sheet Name'!CellRef` or `SheetName!CellRef`.
   - Use regex: `r"'?([^'!]+)'?!([A-Z]+\d+)"`.
   - Build a list of `{"source_sheet": current_sheet, "source_cell": cell_ref, "target_sheet": matched_sheet, "target_cell": matched_cell}`.
5. Detect if file contains data in input cells (non-empty, non-formula). If more than 5% of input cells have values, raise `TemplateNotEmptyError`.

**Output:** A `dict` matching the shape needed by the Schema Extraction Agent:
```python
{
    "file_name": str,
    "sheets": [
        {
            "name": str,
            "headers": [{"column_letter": str, "header": str, "row": int}],
            "input_cells": [{"ref": str, "column_header": str}],
            "formula_cells": [{"ref": str, "formula": str, "column_header": str}],
            "temporal_headers": [str],  # detected year/period values
        }
    ],
    "named_ranges": [{"name": str, "sheet": str, "cell_range": str}],
    "inter_sheet_refs": [{"source_sheet": str, "source_cell": str, "target_sheet": str, "target_cell": str}],
    "total_input_cells": int
}
```

**Error Handling:**
- `openpyxl.utils.exceptions.InvalidFileException` → raise `InvalidTemplateError("Corrupt or unsupported Excel file")`.
- File size > `settings.max_file_size_mb` → raise `FileTooLargeError`.

---

## 5. EXCEL WRITER — `backend/excel_io/writer.py`

### Purpose
Write validated synthetic values back into the original template's input cells. Never overwrite formulas.

### Functions

#### `write_synthetic_data(template_path: str, payload: SyntheticPayload, output_path: str) -> str`

**Input:**
- `template_path`: original uploaded `.xlsx`.
- `payload`: the `SyntheticPayload` (post-validation, with plug adjustments applied).
- `output_path`: destination path for the populated `.xlsx`.

**Logic:**
1. `wb = openpyxl.load_workbook(template_path)` — loads with formulas intact.
2. For each `cell_value` in `payload.cells`:
   - `ws = wb[cell_value.sheet_name]`
   - `ws[cell_value.cell_ref] = cell_value.value`
   - **Guard:** Before writing, verify the existing cell is empty or non-formula. If it contains a formula (starts with `=`), skip and log a warning. Never overwrite formulas.
3. `wb.save(output_path)`
4. Return `output_path`.

**Output:** Path to the populated `.xlsx`.

---

## 6. SCHEMA EXTRACTION AGENT — `backend/agents/schema_extractor.py`

### Purpose
Send the parsed template structure to Gemini 2.0 Flash. Receive back a classified, typed `TemplateSchema`.

### Dependencies
- `google-genai` SDK (`from google import genai; from google.genai import types`)

### Functions

#### `async extract_schema(parsed_template: dict, settings: Settings) -> TemplateSchema`

**Input:** The `dict` output from `parser.parse_template()`.

**Logic:**
1. Initialize client:
   ```python
   client = genai.Client(
       vertexai=True,
       project=settings.google_cloud_project,
       location=settings.google_cloud_location,
   )
   ```
2. Build the system prompt (verbatim):
   ```
   You are a financial model analyst specializing in LBO, DCF, and 3-statement models.

   Given the following Excel template structure (JSON), perform these tasks:
   1. Classify each column header by its financial data type: currency_USD, currency_EUR, currency_GBP, percentage, ratio, integer, date, or text.
   2. Identify the temporal range (e.g., FY2020-FY2025) for each column with time-series data.
   3. Detect inter-sheet dependencies from the formula references provided.
   4. Classify the overall model type as LBO, DCF, 3-statement, or unknown.
   5. Infer the likely industry sector from any contextual clues in the headers or sheet names. If no clues, default to "General Corporate".
   6. Set realistic constraints for each input column:
      - Revenue: growth_rate_range of (-0.10, 0.30), must_be_positive=True
      - COGS/OpEx: must_be_positive=True
      - Margins: min 0.0, max 1.0
      - Debt tranches: must_be_positive=True
      - Interest rates: min 0.0, max 0.25

   Output ONLY valid JSON conforming exactly to this schema (no markdown, no commentary):
   ```
   Then append the JSON Schema derived from `TemplateSchema.model_json_schema()`.

3. Call Gemini:
   ```python
   response = client.models.generate_content(
       model=settings.gemini_model,  # "gemini-2.0-flash"
       contents=f"{system_prompt}\n\nTemplate Structure:\n{json.dumps(parsed_template)}",
       config=types.GenerateContentConfig(
           temperature=0.1,
           top_p=0.9,
       ),
   )
   ```
4. Parse `response.text` → strip any markdown fences → `json.loads()` → validate with `TemplateSchema.model_validate()`.
5. Populate the `cell_references` and `periods` fields on each `ColumnSchema` from the original `parsed_template` data (Gemini classifies the types; the cell refs come from the parser).

**Fallback:**
- If Gemini returns malformed JSON: retry up to 2 times.
- If still failing after 2 retries: fall back to GPT-4o via OpenAI with the same prompt.
  ```python
  client = OpenAI(api_key=settings.openai_api_key)
  completion = client.chat.completions.parse(
      model=settings.gpt4o_model,
      messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(parsed_template)}],
      response_format=TemplateSchema,
  )
  return completion.choices[0].message.parsed
  ```

**Output:** `TemplateSchema` instance.

---

## 7. SYNTHETIC GENERATION AGENT — `backend/agents/synthetic_gen.py`

### Purpose
Generate realistic synthetic financial data conforming to the extracted schema using GPT-4o Structured Outputs.

### Dependencies
- `openai` SDK (`from openai import OpenAI`)

### Functions

#### `async generate_synthetic_data(schema: TemplateSchema, settings: Settings, retry_instructions: str | None = None) -> SyntheticPayload`

**Input:**
- `schema`: the `TemplateSchema` from the extraction agent.
- `retry_instructions`: optional string describing which line items to regenerate and why (from validation failures).

**Logic:**
1. Initialize client:
   ```python
   client = OpenAI(api_key=settings.openai_api_key)
   ```
2. Build the system prompt:
   ```
   You are a financial data generator for institutional-grade synthetic models.

   Generate realistic synthetic data for a {schema.model_type} model in the {schema.industry} sector ({schema.currency}).

   RULES:
   - All numbers must be internally consistent. Revenue must show realistic growth patterns.
   - Cost ratios must be industry-appropriate.
   - Debt schedules must amortize correctly.
   - DO NOT generate random numbers. Generate numbers that tell a coherent business story.
   - Respect ALL constraints specified per column.
   - For time-series data, ensure year-over-year transitions are smooth and realistic.
   - Base revenue should be between $50M and $500M for LBO/DCF models.
   - EBITDA margins should be between 10% and 40% depending on industry.
   - Interest rates on debt tranches should be between 4% and 12%.
   ```
   If `retry_instructions` is provided, append:
   ```
   CRITICAL CORRECTION: The previous generation failed validation.
   {retry_instructions}
   Regenerate ONLY the specified line items while keeping all other values identical.
   ```
3. Build the user prompt: serialize the `schema` to JSON including all columns, constraints, periods, and cell references.
4. Define the Pydantic response model for structured output. Use `SyntheticPayload` directly:
   ```python
   completion = client.chat.completions.parse(
       model=settings.gpt4o_model,
       messages=[
           {"role": "system", "content": system_prompt},
           {"role": "user", "content": json.dumps(schema.model_dump())},
       ],
       response_format=SyntheticPayload,
       temperature=settings.generation_temperature,  # 0.3
   )

   result = completion.choices[0].message.parsed
   ```
5. Populate `generation_metadata` with token usage from `completion.usage`.

**Output:** `SyntheticPayload` instance.

**Note on Structured Outputs:** The OpenAI SDK's `client.chat.completions.parse()` method accepts a Pydantic `BaseModel` class as `response_format`. It automatically converts it to a strict JSON schema, sends `response_format: {type: "json_schema", json_schema: {schema: ..., name: "SyntheticPayload", strict: true}}`, and the parsed result is available at `completion.choices[0].message.parsed`. If `.parsed` is `None`, the model did not comply — treat as a generation failure and retry.

---

## 8. DETERMINISTIC VALIDATION AGENT — `backend/agents/validator.py`

### Purpose
Pure Python rules engine. No LLM. Enforces double-entry accounting and inter-statement integrity. This is the trust anchor of the entire system.

### Dependencies
- `pandas`, `numpy` (for vectorized math)
- `datetime` (for timestamps)

### Class: `DeterministicValidator`

#### Constructor

```python
def __init__(self, schema: TemplateSchema):
    self.schema = schema
    # Pre-build lookup tables:
    # self._columns_by_sheet: dict[str, dict[str, ColumnSchema]]
    # self._inter_sheet_map: dict[tuple[str,str], InterSheetReference]
```

#### Method: `validate(payload: SyntheticPayload) -> ValidationResult`

**Logic:**
1. Convert `payload.cells` into a pandas DataFrame keyed by `(sheet_name, header, period)` for fast lookup.
2. Run all 6 rules. Collect results into `list[ValidationRuleResult]`.
3. Apply plug adjustments for any failures.
4. Return `ValidationResult`.

#### Rule Implementations (all private methods)

##### `_rule_balance_sheet_identity(df) -> list[ValidationRuleResult]`
For each period in the Balance Sheet:
```
Total Assets == Total Liabilities + Total Equity
```
- Tolerance: `0.00` (exact match after rounding to 2 decimal places).
- Look up values by matching `header` containing "Total Assets", "Total Liabilities", "Total Equity" (case-insensitive fuzzy match, but prefer exact header from schema).
- On failure: calculate `delta = Total_Assets - (Total_Liabilities + Total_Equity)`. Create `PlugAdjustment` targeting "Cash" or "Cash & Cash Equivalents" on the Balance Sheet. Adjusted value = original + delta.

##### `_rule_cash_flow_reconciliation(df) -> list[ValidationRuleResult]`
For each period in the Cash Flow Statement:
```
Ending Cash == Beginning Cash + Net Change in Cash
```
- `Beginning_Cash` for period N = `Ending_Cash` for period N-1 (for the first period, Beginning Cash is an input or 0).
- On failure: adjust "Other Cash Flow Items" or "Other Operating Activities" by the delta.

##### `_rule_net_income_linkage(df) -> list[ValidationRuleResult]`
```
Income Statement: Net Income == Cash Flow Statement: Net Income
```
AND
```
delta(Retained Earnings) across periods == Net Income - Dividends (if dividends column exists)
```
- On failure: adjust the Cash Flow Statement's Net Income to match the P&L.

##### `_rule_margin_bounds(df) -> list[ValidationRuleResult]`
For each period:
```
Gross Margin = (Revenue - COGS) / Revenue → must be in [0, 1]
EBITDA Margin = EBITDA / Revenue → must be in [-0.5, 0.8]
Net Margin = Net Income / Revenue → must be in [-1.0, 0.5]
```
- Use constraints from `schema` if available; otherwise use the defaults above.
- On failure for margins: this is a structural issue. Set `needs_regeneration` for the offending line item (e.g. "COGS" if Gross Margin is negative). Do NOT plug — signal retry to GPT-4o.

##### `_rule_depreciation_constraint(df) -> list[ValidationRuleResult]`
```
Cumulative Depreciation <= Cumulative CapEx + Opening PP&E
```
- Across all periods.
- On failure: cap Depreciation at the allowed maximum and log the adjustment.

##### `_rule_debt_schedule_integrity(df) -> list[ValidationRuleResult]`
For each debt tranche, for each period:
```
Ending Debt = Beginning Debt + Drawdowns - Repayments
```
- On failure: adjust Repayments to force the identity.

#### Method: `_apply_plug_adjustments(payload, adjustments) -> SyntheticPayload`
Returns a new `SyntheticPayload` with the adjusted cell values. The original payload is not mutated.

#### Method: `_build_retry_instructions(results) -> str | None`
If any rule has `needs_regeneration` items, builds a human-readable string describing what to fix. Returns `None` if no retry needed.

---

## 9. ORCHESTRATOR — `backend/orchestrator.py`

### Purpose
Coordinates the full pipeline: Parse → Schema Extract → Generate → Validate → Write. Streams progress to the frontend via WebSocket.

### Dependencies
- All agents, parser, writer
- `asyncio`, `uuid`, `json`

### Class: `PipelineOrchestrator`

#### Constructor

```python
def __init__(self, settings: Settings):
    self.settings = settings
    self.jobs: dict[str, JobState] = {}  # in-memory job store
```

#### Method: `async run_pipeline(job_id: str, file_path: str, ws_callback: Callable[[WSEvent], Awaitable[None]])`

**Logic (sequential — each step depends on the previous):**

1. **Parse Phase**
   - `self._update_status(job_id, "parsing")`
   - `await ws_callback(WSEvent(job_id=job_id, phase="parse", event_type="progress", detail="Parsing Excel template..."))`
   - `parsed = parse_template(file_path)` — synchronous, wrap in `asyncio.to_thread()`.
   - `await ws_callback(WSEvent(..., detail=f"Found {parsed['total_input_cells']} input cells across {len(parsed['sheets'])} sheets"))`
   - For each sheet: `await ws_callback(WSEvent(..., event_type="progress", detail=f"[MAP] {sheet['name']} → {len(sheet['input_cells'])} input cells"))`

2. **Schema Extraction Phase**
   - `self._update_status(job_id, "extracting_schema")`
   - `await ws_callback(WSEvent(..., phase="schema_extract", detail="Schema extraction starting..."))`
   - `schema = await extract_schema(parsed, self.settings)`
   - `self.jobs[job_id].template_schema = schema`
   - `await ws_callback(WSEvent(..., detail=f"[TYPE] Model classified as: {schema.model_type}"))`
   - For each inter-sheet ref: `await ws_callback(WSEvent(..., detail=f"[LINK] {ref.source_sheet}.{ref.source_column} → {ref.target_sheet}.{ref.target_column} ✓"))`

3. **Generation Phase**
   - `self._update_status(job_id, "generating")`
   - `retry_instructions = None`
   - Loop up to `settings.max_retries` times:
     - `payload = await generate_synthetic_data(schema, self.settings, retry_instructions)`
     - `self.jobs[job_id].synthetic_payload = payload`
     - Stream cell updates to frontend:
       ```python
       for cell in payload.cells:
           await ws_callback(WSEvent(
               ..., phase="generate", event_type="cell_update",
               detail=f"{cell.sheet_name}.{cell.header} [{cell.period}] = {cell.value}",
               data={"sheet": cell.sheet_name, "cell_ref": cell.cell_ref, "value": cell.value}
           ))
       ```

4. **Validation Phase**
   - `self._update_status(job_id, "validating")`
   - `validator = DeterministicValidator(schema)`
   - `result = validator.validate(payload)`
   - `self.jobs[job_id].validation_result = result`
   - For each passed rule: `await ws_callback(WSEvent(..., phase="validate", event_type="validation", detail=f"✓ {rule.rule_name} ({rule.period})"))`
   - For each plug adjustment: `await ws_callback(WSEvent(..., detail=f"⚡ Adjusted {adj.target_cell} by {adj.delta:+,.0f} to force {adj.reason}"))`
   - If `result.status == "FAILED"` and `retry_count < max_retries`:
     - `retry_instructions = validator._build_retry_instructions(result.rules)`
     - `self.jobs[job_id].retry_count += 1`
     - `await ws_callback(WSEvent(..., detail=f"Retrying generation (attempt {retry_count+1})..."))`
     - Go back to step 3.
   - If `result.status == "FAILED"` and retries exhausted: set error, send error event, return.
   - Use `result.validated_payload` (the plug-adjusted version) going forward.

5. **Write Phase**
   - `self._update_status(job_id, "writing")`
   - `output_path = f"/tmp/safe_harbor/{job_id}/output.xlsx"`
   - `await asyncio.to_thread(write_synthetic_data, file_path, result.validated_payload, output_path)`
   - `self.jobs[job_id].output_file_path = output_path`

6. **Complete**
   - `self._update_status(job_id, "complete")`
   - Send final `WSEvent` with `event_type="complete"` including full validation summary and audit log in `data`.

**Timeout:** Wrap the entire pipeline in `asyncio.wait_for(..., timeout=settings.generation_timeout_s)`. On timeout, set status to "error" and send error event.

---

## 10. FASTAPI APPLICATION — `backend/main.py`

### Endpoints

#### `POST /api/upload`

**Request:** `UploadFile` (multipart form-data, field name: `file`).

**Logic:**
1. Validate file extension is `.xlsx` or `.xlsm`.
2. Validate file size <= `settings.max_file_size_mb`.
3. Generate `job_id = str(uuid.uuid4())`.
4. Save uploaded file to `/tmp/safe_harbor/{job_id}/template.xlsx`.
5. Initialize `JobState` in `orchestrator.jobs`.
6. Return `{"job_id": job_id}` (HTTP 202 Accepted).

**Response Schema:**
```json
{"job_id": "uuid-string"}
```

#### `WebSocket /ws/{job_id}`

**Logic:**
1. Accept WebSocket connection.
2. Verify `job_id` exists in `orchestrator.jobs`.
3. Define `ws_callback` that serializes `WSEvent` to JSON and sends over WebSocket.
4. `await orchestrator.run_pipeline(job_id, file_path, ws_callback)`.
5. On pipeline completion, the WebSocket remains open until the client disconnects.

**Event format (sent as JSON text frames):**
```json
{
    "job_id": "...",
    "phase": "validate",
    "event_type": "validation",
    "detail": "✓ Balance Sheet Balanced (FY2022)",
    "data": null
}
```

#### `GET /api/download/{job_id}`

**Logic:**
1. Look up `job_id` in `orchestrator.jobs`.
2. If status != "complete", return HTTP 404 with `{"error": "Job not complete"}`.
3. Return `FileResponse(job.output_file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="safe_harbor_model.xlsx")`.

#### `GET /api/audit/{job_id}`

**Logic:**
1. Return the full `JobState` serialized as JSON (includes `audit_log`, `template_schema`, `validation_result`).
2. If status == "pending", return HTTP 404.

#### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Startup

```python
@app.on_event("startup")
async def startup():
    os.makedirs("/tmp/safe_harbor", exist_ok=True)
```

---

## 11. FRONTEND COMPONENTS

### 11.1 `src/hooks/useWebSocket.js`

**Purpose:** Custom React hook managing WebSocket connection lifecycle and event routing.

**Interface:**
```javascript
const { events, phase, isConnected, lastEvent } = useWebSocket(jobId);
// events: WSEvent[] — full ordered event log
// phase: string — current pipeline phase
// isConnected: boolean
// lastEvent: WSEvent | null
```

**Logic:**
- On `jobId` change: open WebSocket to `ws://localhost:8000/ws/{jobId}`.
- On message: `JSON.parse` → append to `events` state array, update `phase` and `lastEvent`.
- On close/error: set `isConnected = false`.
- Cleanup on unmount.

### 11.2 `src/components/UploadZone.jsx`

**Props:** `onJobCreated(jobId: string)`

**UI:**
- Full-width drag-and-drop zone with dashed border.
- Text: "Drop your empty model template here"
- Subtext: "Strip all sensitive data first. Keep headers, formulas, and structure."
- Supported formats badge: `.xlsx`, `.xlsm`
- File size limit display: "Max 25MB"
- Three sample template buttons below the drop zone: "LBO Template", "DCF Template", "3-Statement Template" — clicking these sends a pre-built template from `/templates/`.
- On drop/select: `POST /api/upload` with the file as `FormData`. On success, call `onJobCreated(response.job_id)`.
- Error states:
  - File too large → red text.
  - Wrong format → red text.
  - Backend returns `TemplateNotEmptyError` → "This file contains data in input cells. Please upload an empty template."

### 11.3 `src/components/SchemaTerminal.jsx`

**Props:** `events: WSEvent[]` (filtered to `phase === "parse" || phase === "schema_extract"`)

**UI:**
- Dark terminal aesthetic (monospace font, dark bg `#0D1117`, green text `#4ADE80`).
- Each event rendered as a line with prefix:
  ```
  [SCAN] Detecting sheets... 4 found
  [MAP]  Income Statement → 23 columns mapped
  [LINK] P&L.Net_Income → CF.Net_Income ✓
  [TYPE] Model classified as: Leveraged Buyout
  ```
- Auto-scroll to bottom on new events.
- Animated cursor blinking at the end.

### 11.4 `src/components/DataWaterfall.jsx`

**Props:** `events: WSEvent[]` (filtered to `event_type === "cell_update" || event_type === "validation"`)

**UI:**
- Excel-like grid layout. Columns = periods (FY2020..FY2025), rows = line items (Revenue, COGS, etc.), grouped by sheet tabs.
- Cells start empty (dark gray).
- On `cell_update` event: the corresponding cell transitions:
  - Empty → AMBER flash (200ms) → show the value → GREEN flash (150ms) → settle to white text on dark bg.
- On `validation` event with adjustment: the affected cell flashes YELLOW with a tooltip showing the adjustment reason.
- Bottom ticker bar scrolling validation messages:
  ```
  ✓ Balance Sheet Balanced (Year 1) ... ✓ Cash Flow Reconciled (Year 1) ...
  ```
- Sheet tabs at the top to switch between visible sheets.

### 11.5 `src/components/VerdictBadge.jsx`

**Props:** `validationResult: ValidationResult, templateSchema: TemplateSchema`

**UI:**
- Full-screen overlay modal with centered badge.
- Large green checkmark icon.
- Title: "SYNTHETIC MODEL VERIFIED"
- Checklist:
  ```
  ✓ Balance Sheet Balanced (all N years)
  ✓ Cash Flow Reconciled (all N years)
  ✓ Debt Schedule Amortized Correctly
  ✓ Margins Within Industry Bounds
  ✓ Zero Sensitive Data
  ```
- Metadata block: Model Type, Industry, Time Horizon, Input Cells populated, Validation rules passed.
- Two CTAs:
  - "Download .xlsx" → `GET /api/download/{jobId}`.
  - "START TESTING IN TRACELIGHT" → primary green button (links to Tracelight's core product).
- If `status === "PASSED_WITH_PLUGS"`: show an amber info bar: "N adjustments were made to ensure mathematical integrity. See audit trail for details."

### 11.6 `src/components/AuditTrail.jsx`

**Props:** `jobId: string`

**UI:**
- Expandable panel (collapsed by default, button text: "View Audit Trail").
- On expand: `GET /api/audit/{jobId}` → display:
  - **Schema** section: collapsible JSON tree of the `TemplateSchema`.
  - **Generated Values** section: table of all synthetic values with constraint bounds shown.
  - **Validation Rules** section: table — rule name, period, passed/failed, expected, actual, delta.
  - **Plug Adjustments** section: table — cell, period, original value, adjusted value, delta, reason.
  - **Timing** section: timestamp for each phase, total pipeline duration.
  - **Cost** section: model, tokens used, estimated cost per the PRD cost table.

### 11.7 `src/App.jsx`

**State Machine:**
```
UPLOAD → SCHEMA_TERMINAL → DATA_WATERFALL → VERDICT → (audit trail accessible from verdict)
```

**Logic:**
1. Show `<UploadZone>`. On `onJobCreated(jobId)`: set `jobId` state, transition to SCHEMA_TERMINAL.
2. Connect `useWebSocket(jobId)`. Route events to `<SchemaTerminal>`.
3. When `phase` transitions to `"generating"`: transition to DATA_WATERFALL view, render `<DataWaterfall>`.
4. When `event_type === "complete"`: transition to VERDICT, render `<VerdictBadge>`.
5. `<AuditTrail>` available from VERDICT screen.

### Tailwind Config

```javascript
// tailwind.config.js
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'harbor-bg': '#0D1117',
        'harbor-surface': '#161B22',
        'harbor-border': '#30363D',
        'harbor-text': '#E6EDF3',
        'harbor-green': '#4ADE80',
        'harbor-amber': '#FBBF24',
        'harbor-red': '#F87171',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
```

---

## 12. SAMPLE TEMPLATES

Three pre-built `.xlsx` files must be created in the `templates/` directory. These are for prospects who don't have their own template handy.

### `lbo_template.xlsx`
Sheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.
- Income Statement columns: Revenue, COGS, Gross Profit (formula), SG&A, EBITDA (formula), D&A, EBIT (formula), Interest Expense (formula from Debt Schedule), EBT (formula), Tax, Net Income (formula). Periods: FY2020-FY2030.
- Balance Sheet: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets (formula), PP&E Net, Goodwill, Other Non-Current Assets, Total Assets (formula), Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities (formula), Senior Debt, Mezzanine Debt, Total Liabilities (formula), Common Equity, Retained Earnings, Total Equity (formula), Total Liabilities & Equity (formula). Periods: FY2020-FY2030.
- Cash Flow: Net Income, D&A, Changes in Working Capital, Operating CF (formula), CapEx, Investing CF (formula), Debt Drawdowns, Debt Repayments, Dividends, Financing CF (formula), Net Change in Cash (formula), Beginning Cash, Ending Cash (formula). Periods: FY2020-FY2030.
- Debt Schedule: For each tranche (Senior, Mezzanine): Beginning Balance, Drawdowns, Repayments, Ending Balance (formula), Interest Rate, Interest Expense (formula). Periods: FY2020-FY2030.
- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.

All input cells empty. All formula cells contain correct Excel formulas with inter-sheet references.

### `dcf_template.xlsx`
Sheets: Revenue Build, Income Statement, Free Cash Flow, DCF Valuation.
- Simplified version: Revenue Build feeds IS, IS feeds FCF, FCF feeds DCF.
- DCF sheet: WACC, Terminal Growth Rate, Terminal Value (formula), PV of FCFs (formula), Enterprise Value (formula).

### `three_statement_template.xlsx`
Sheets: Income Statement, Balance Sheet, Cash Flow Statement.
- Standard 3-statement model with full inter-statement linkages.
- No debt schedule or returns analysis.

---

## 13. TESTS — Required Coverage

### `tests/test_parser.py`
- Test: parses `lbo_template.xlsx` correctly. Assert sheet count, header count, input cell count, formula detection, inter-sheet ref count.
- Test: raises `TemplateNotEmptyError` when file has data in input cells.
- Test: raises `InvalidTemplateError` for corrupt file.

### `tests/test_validator.py`
- Test: balanced BS passes `_rule_balance_sheet_identity`.
- Test: unbalanced BS triggers plug adjustment to Cash, result status is `PASSED_WITH_PLUGS`.
- Test: broken CF reconciliation triggers adjustment.
- Test: margin violation (negative gross margin) returns `needs_regeneration` for COGS.
- Test: depreciation exceeding CapEx + PP&E triggers cap.
- Test: debt schedule mismatch triggers repayment adjustment.

### `tests/test_schema_extractor.py`
- Test: mock Gemini response → verify `TemplateSchema` output parses correctly.
- Test: malformed Gemini response → verify retry logic fires.
- Test: fallback to GPT-4o after 2 Gemini failures.

### `tests/test_synthetic_gen.py`
- Test: mock GPT-4o structured output → verify `SyntheticPayload` parses.
- Test: verify retry with `retry_instructions` modifies the prompt.

### `tests/test_orchestrator.py`
- Test: full pipeline with mocked agents → verify all WebSocket events fire in correct order.
- Test: validation failure → verify retry loop executes up to `max_retries`.
- Test: timeout → verify error state.

---

## 14. DOCKERFILE

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY templates/ ./templates/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 15. BUILD ORDER & DEPENDENCY CHAIN

```
Step 1: schemas.py (no deps — pure Pydantic models)
Step 2: config.py (depends on: pydantic, python-dotenv)
Step 3: parser.py + writer.py (depends on: schemas.py, openpyxl)
Step 4: validator.py (depends on: schemas.py, pandas, numpy)
Step 5: schema_extractor.py (depends on: schemas.py, config.py, google-genai)
Step 6: synthetic_gen.py (depends on: schemas.py, config.py, openai)
Step 7: orchestrator.py (depends on: all agents, parser, writer, schemas.py)
Step 8: main.py (depends on: orchestrator.py, config.py)
Step 9: Frontend components (depends on: backend API being functional)
Step 10: Integration tests (depends on: everything)
```

Steps 3 and 4 can be built in parallel. Steps 5 and 6 can be built in parallel.

---

## 16. CRITICAL BOUNDARIES — WHAT THIS SPEC DOES NOT COVER

- **Phase 2 (Shield-Wall InfoSec Responder):** Not in scope. Do not build.
- **Phase 3 (IC Memo Synthesizer):** Killed. Do not build.
- **Deployment CI/CD:** Not in scope. Manual deploy to Cloud Run.
- **Authentication/Authorization:** Not in scope for the demo. No auth on endpoints.
- **Database:** No database. All state is in-memory (`orchestrator.jobs` dict). Acceptable for a demo.
- **Rate limiting:** Not in scope. Single-user demo.
- **Production error monitoring:** Not in scope.
- **The Tracelight core DAG engine:** NEVER touch this. Safe-Harbor operates purely upstream.

---

*End of Phase 1 Technical Specification.*
