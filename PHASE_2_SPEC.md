# PHASE 2 TECHNICAL SPECIFICATION
## Shield-Wall Autonomous InfoSec Responder
### File-by-File, Function-by-Function Blueprint for Execution Agent

---

## 0. STRATEGIC CONTEXT

### What This Is
An air-gapped, internal-only multi-agent system that autonomously answers vendor security questionnaires by cross-referencing live infrastructure telemetry with internal compliance policies. It is an ops-efficiency tool for Tracelight's sales/legal team — NOT customer-facing.

### Why It Exists
Enterprise procurement cycles include 100-300 question vendor security assessments. Manually answering these costs 5-10 hours per questionnaire. Tracelight is signing 5 of the top 10 global consultancies — each with their own bespoke questionnaire. Shield-Wall compresses this from days to minutes.

### Anti-Replication Boundary
Shield-Wall operates in the **parallel administrative compliance** lane. It never touches the DAG engine, Excel add-in, or any customer-facing product surface. It is a pure internal tool.

### Model Routing Restriction
Same SOP as Phase 1: OpenAI and Google models only. No Anthropic/Claude, no AWS Bedrock.

| Agent | Model | Provider | Rationale |
|-------|-------|----------|-----------|
| Questionnaire Parser | Gemini 2.0 Flash | Google Vertex AI | Fast, cheap, excellent at structured extraction from messy text |
| Telemetry Agent | GPT-4o | OpenAI | Strong SQL generation for Athena-like queries, function calling |
| Policy Agent (RAG) | GPT-4o | OpenAI | Accurate retrieval-augmented generation over compliance docs |
| Synthesis Agent | GPT-4o (Structured Outputs) | OpenAI | Evidence-backed answer generation with strict JSON schema |
| Drift Detector | Pure Python | N/A | Deterministic comparison — no LLM needed |

### Demo vs Production Architecture
The demo uses a **mock telemetry layer** — a local JSON/SQLite representation of AWS infrastructure state. The architecture is pluggable: swap the mock adapter for real AWS Athena/CloudTrail/IAM queries in production without changing any agent logic.

---

## 1. ENVIRONMENT & DEPENDENCIES

### `requirements.txt` (extends Phase 1 — separate service)
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
python-multipart==0.0.18
websockets==14.*
pydantic==2.10.*
pydantic-settings==2.*
openai==1.66.*
google-genai==1.14.*
python-dotenv==1.0.*
aiofiles==24.*
pandas==2.2.*
numpy==2.1.*
chromadb==0.5.*
openpyxl==3.1.*
python-docx==1.1.*
PyPDF2==3.0.*
tiktoken==0.8.*
```

### `.env` (template)
```
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
SHIELD_WALL_MAX_FILE_SIZE_MB=50
SHIELD_WALL_MAX_QUESTIONS=500
SHIELD_WALL_GENERATION_TIMEOUT_S=300
# Production only (ignored in demo mode):
AWS_REGION=eu-west-1
AWS_ATHENA_DATABASE=cloudtrail_logs
AWS_ATHENA_OUTPUT_BUCKET=s3://shield-wall-athena-results/
DEMO_MODE=true
```

### Frontend
```
Node 20+, React 18, Vite 6, Tailwind CSS 3.4
(Same stack as Phase 1 for consistency)
```

---

## 2. DIRECTORY STRUCTURE

```
shield-wall/
├── backend/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + WebSocket
│   ├── orchestrator.py              # Pipeline coordinator
│   ├── config.py                    # Settings
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── questionnaire_parser.py  # Gemini 2.0 Flash — parse questionnaires
│   │   ├── telemetry_agent.py       # GPT-4o — generate & execute infra queries
│   │   ├── policy_agent.py          # GPT-4o + ChromaDB RAG — search policies
│   │   ├── synthesis_agent.py       # GPT-4o Structured Outputs — draft answers
│   │   └── drift_detector.py        # Pure Python — telemetry vs policy check
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract telemetry adapter interface
│   │   ├── mock_adapter.py          # Demo mode: reads from local JSON/SQLite
│   │   └── aws_adapter.py           # Production: real Athena/CloudTrail/IAM
│   ├── policy_store/
│   │   ├── __init__.py
│   │   ├── indexer.py               # Ingest & chunk policy docs into ChromaDB
│   │   └── retriever.py             # Semantic search over policy chunks
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── excel_parser.py          # Parse .xlsx/.csv questionnaires
│   │   ├── pdf_parser.py            # Parse PDF questionnaires
│   │   └── text_parser.py           # Parse plain text / DOCX questionnaires
│   └── models/
│       ├── __init__.py
│       └── schemas.py               # All Pydantic data contracts
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
│       │   ├── QuestionnaireUpload.jsx
│       │   ├── ProcessingTerminal.jsx
│       │   ├── AnswerGrid.jsx
│       │   ├── DriftAlerts.jsx
│       │   └── ExportPanel.jsx
│       └── hooks/
│           └── useWebSocket.js      # Reuse from Phase 1
├── data/
│   ├── mock_infra/
│   │   ├── cloudtrail_events.json   # Simulated CloudTrail log entries
│   │   ├── iam_policies.json        # Simulated IAM configuration
│   │   ├── kms_keys.json            # Simulated KMS encryption states
│   │   ├── security_groups.json     # Simulated VPC security groups
│   │   └── rds_instances.json       # Simulated RDS config (encryption, backups)
│   └── policies/
│       ├── soc2_type2_report.pdf    # Sample SOC 2 Type 2 document
│       ├── data_classification.md   # Sample data classification policy
│       ├── network_security.md      # Sample network security policy
│       ├── incident_response.md     # Sample IR plan
│       └── access_control.md        # Sample access control policy
├── tests/
│   ├── test_questionnaire_parser.py
│   ├── test_telemetry_agent.py
│   ├── test_policy_agent.py
│   ├── test_synthesis_agent.py
│   ├── test_drift_detector.py
│   └── test_orchestrator.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 3. PYDANTIC SCHEMAS — `backend/models/schemas.py`

### 3.1 `SecurityQuestion`
```python
class SecurityQuestion(BaseModel):
    id: int                                  # Sequential index within the questionnaire
    category: Literal[
        "access_control", "encryption", "network_security",
        "incident_response", "data_classification", "business_continuity",
        "vendor_management", "physical_security", "compliance",
        "logging_monitoring", "change_management", "other"
    ]
    original_text: str                       # Verbatim question text from the questionnaire
    normalized_query: str                    # LLM-cleaned, unambiguous restatement
    requires_telemetry: bool                 # Does this need live infra evidence?
    requires_policy: bool                    # Does this need policy document citation?
    source_row: int | None = None            # Row number in original file (for mapping back)
    source_sheet: str | None = None          # Sheet name if from Excel
```

### 3.2 `ParsedQuestionnaire`
```python
class ParsedQuestionnaire(BaseModel):
    source_file: str
    source_format: Literal["xlsx", "csv", "pdf", "docx", "txt"]
    total_questions: int
    questions: list[SecurityQuestion]
    metadata: dict | None = None             # Client name, date, any header info extracted
```

### 3.3 `TelemetryEvidence`
```python
class TelemetryEvidence(BaseModel):
    question_id: int
    query_executed: str                      # The SQL/API query that was run
    query_type: Literal["athena_sql", "iam_api", "kms_api", "config_api", "mock"]
    raw_result: dict | list                  # Raw query response
    summary: str                             # Human-readable summary of the finding
    timestamp: str                           # ISO-8601 — when the query was executed
    proves: str                              # What this evidence demonstrates
```

### 3.4 `PolicyCitation`
```python
class PolicyCitation(BaseModel):
    question_id: int
    policy_document: str                     # e.g. "SOC 2 Type 2 Report"
    section: str                             # e.g. "CC6.1 — Logical Access Controls"
    excerpt: str                             # Verbatim quote from the policy
    relevance_score: float                   # 0.0 - 1.0 cosine similarity
    chunk_id: str                            # ChromaDB chunk reference
```

### 3.5 `DraftAnswer`
```python
class DraftAnswer(BaseModel):
    question_id: int
    answer_text: str                         # The synthesized response
    confidence: Literal["high", "medium", "low"]
    evidence_sources: list[Literal["telemetry", "policy", "both", "none"]]
    telemetry_evidence: list[TelemetryEvidence]
    policy_citations: list[PolicyCitation]
    drift_detected: bool                     # Telemetry contradicts policy
    drift_detail: str | None = None
    needs_human_review: bool                 # True if confidence=low or drift=true
```

### 3.6 `QuestionnaireResult`
```python
class QuestionnaireResult(BaseModel):
    total_questions: int
    answered: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    drift_alerts: int
    needs_review: int
    answers: list[DraftAnswer]
    processing_time_ms: int
    export_ready: bool
```

### 3.7 `DriftAlert`
```python
class DriftAlert(BaseModel):
    question_id: int
    severity: Literal["critical", "warning", "info"]
    policy_states: str                       # What the policy claims
    telemetry_shows: str                     # What the infrastructure actually shows
    recommendation: str                      # Suggested remediation
```

### 3.8 `ShieldWallJobState`
```python
class ShieldWallJobState(BaseModel):
    job_id: str
    status: Literal[
        "pending", "parsing", "classifying",
        "querying_telemetry", "querying_policies",
        "synthesizing", "detecting_drift",
        "complete", "error"
    ]
    questionnaire: ParsedQuestionnaire | None = None
    result: QuestionnaireResult | None = None
    drift_alerts: list[DriftAlert] = []
    audit_log: list["ShieldWallAuditEntry"] = []
    error_message: str | None = None
```

### 3.9 `ShieldWallAuditEntry`
```python
class ShieldWallAuditEntry(BaseModel):
    timestamp: str
    phase: str
    agent: str | None = None
    detail: str
    data: dict | None = None
```

### 3.10 `ShieldWallWSEvent`
```python
class ShieldWallWSEvent(BaseModel):
    job_id: str
    phase: str
    event_type: Literal["progress", "answer_update", "drift_alert", "complete", "error"]
    detail: str
    data: dict | None = None
```

---

## 4. CONFIGURATION — `backend/config.py`

```python
class ShieldWallSettings(BaseModel):
    openai_api_key: str
    google_cloud_project: str
    google_cloud_location: str               # default "us-central1"
    max_file_size_mb: int                    # default 50
    max_questions: int                       # default 500
    generation_timeout_s: int                # default 300
    gpt4o_model: str                         # default "gpt-4o"
    gemini_model: str                        # default "gemini-2.0-flash"
    demo_mode: bool                          # default True
    # Production AWS settings (ignored when demo_mode=True):
    aws_region: str = "eu-west-1"
    aws_athena_database: str = "cloudtrail_logs"
    aws_athena_output_bucket: str = ""
    # RAG settings:
    chroma_persist_dir: str = "./data/chroma_db"
    policy_chunk_size: int = 512             # tokens per chunk
    policy_chunk_overlap: int = 64
    policy_top_k: int = 5                    # retrieval results per query
```

---

## 5. FILE PARSERS — `backend/parsers/`

### 5.1 `excel_parser.py`

#### `parse_excel_questionnaire(file_path: str) -> list[dict]`

**Logic:**
1. `wb = openpyxl.load_workbook(file_path, data_only=True)`
2. Iterate all sheets. For each sheet:
   - Detect the header row (first row containing keywords like "Question", "Requirement", "Control", "#", "ID").
   - For each subsequent row, extract the question text from the widest/longest text column.
   - Capture the row number and sheet name for mapping back during export.
3. Return a list of `{"text": str, "row": int, "sheet": str}`.

**Edge cases:**
- Multi-cell questions (question spans columns A-D) → concatenate.
- Merged cells → use `ws.merged_cells.ranges` to detect and read the top-left cell.
- Empty rows → skip.

### 5.2 `pdf_parser.py`

#### `parse_pdf_questionnaire(file_path: str) -> list[dict]`

**Logic:**
1. `PyPDF2.PdfReader(file_path)` to extract text from all pages.
2. Concatenate all page text.
3. Split on numbered patterns: `r"(\d{1,3}[\.\)]\s)"` to segment questions.
4. Each segment becomes a question entry.
5. Return `[{"text": str, "page": int}]`.

### 5.3 `text_parser.py`

#### `parse_docx_questionnaire(file_path: str) -> list[dict]`

**Logic:**
1. `python-docx` to read `.docx` paragraphs.
2. Detect numbered lists or bold headers as question boundaries.
3. Return `[{"text": str, "paragraph_index": int}]`.

#### `parse_csv_questionnaire(file_path: str) -> list[dict]`

**Logic:**
1. `pandas.read_csv(file_path)`.
2. Auto-detect the question column (longest average string length).
3. Return `[{"text": str, "row": int}]`.

---

## 6. QUESTIONNAIRE PARSER AGENT — `backend/agents/questionnaire_parser.py`

### Purpose
Takes raw extracted question texts and classifies/normalizes them into structured `SecurityQuestion` objects using Gemini 2.0 Flash.

### Function: `async parse_questionnaire(raw_questions: list[dict], settings: ShieldWallSettings) -> ParsedQuestionnaire`

**Logic:**
1. Initialize Gemini client:
   ```python
   client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
   ```
2. Batch questions in groups of 50 (to stay within context limits).
3. For each batch, send to Gemini with system prompt:
   ```
   You are an information security analyst classifying vendor security questionnaire questions.

   For each question:
   1. Assign a category from: access_control, encryption, network_security,
      incident_response, data_classification, business_continuity,
      vendor_management, physical_security, compliance, logging_monitoring,
      change_management, other.
   2. Rewrite it as a clear, unambiguous normalized query.
   3. Determine if answering requires live infrastructure telemetry (e.g., "Is MFA enforced?" → yes).
   4. Determine if answering requires policy document citation (e.g., "What is your IR plan?" → yes).

   Output JSON array conforming to the SecurityQuestion schema.
   ```
4. Parse response → validate each entry as `SecurityQuestion`.
5. Assign sequential `id` values.
6. Fallback: If Gemini fails after 2 retries, fall back to GPT-4o with same prompt.

**Output:** `ParsedQuestionnaire`.

---

## 7. TELEMETRY AGENT — `backend/agents/telemetry_agent.py`

### Purpose
For each question requiring telemetry, generate and execute an infrastructure query against the telemetry adapter (mock or real AWS).

### Function: `async gather_telemetry(questions: list[SecurityQuestion], adapter: TelemetryAdapter, settings: ShieldWallSettings) -> list[TelemetryEvidence]`

**Logic:**
1. Filter to `questions` where `requires_telemetry == True`.
2. For each question, call GPT-4o with function calling:
   ```python
   completion = client.chat.completions.create(
       model=settings.gpt4o_model,
       messages=[
           {"role": "system", "content": TELEMETRY_SYSTEM_PROMPT},
           {"role": "user", "content": f"Question: {q.normalized_query}\nCategory: {q.category}"},
       ],
       tools=TELEMETRY_TOOLS,
       tool_choice="auto",
   )
   ```
3. `TELEMETRY_TOOLS` defines the available query functions the adapter exposes:
   ```python
   TELEMETRY_TOOLS = [
       {
           "type": "function",
           "function": {
               "name": "query_cloudtrail",
               "description": "Search AWS CloudTrail logs for specific events",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "event_name": {"type": "string", "description": "CloudTrail event name (e.g., ConsoleLogin, CreateUser)"},
                       "time_range_days": {"type": "integer", "description": "Look back N days"},
                       "filter_key": {"type": "string"},
                       "filter_value": {"type": "string"},
                   },
                   "required": ["event_name"]
               }
           }
       },
       {
           "type": "function",
           "function": {
               "name": "query_iam_config",
               "description": "Retrieve IAM configuration: MFA status, password policies, role definitions",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "query_type": {"type": "string", "enum": ["mfa_status", "password_policy", "roles", "users", "access_keys"]},
                   },
                   "required": ["query_type"]
               }
           }
       },
       {
           "type": "function",
           "function": {
               "name": "query_encryption_status",
               "description": "Check KMS encryption status of AWS resources",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "resource_type": {"type": "string", "enum": ["rds", "s3", "ebs", "dynamodb"]},
                   },
                   "required": ["resource_type"]
               }
           }
       },
       {
           "type": "function",
           "function": {
               "name": "query_network_config",
               "description": "Retrieve VPC, security group, and network ACL configurations",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "query_type": {"type": "string", "enum": ["security_groups", "vpc_flow_logs", "nacls", "public_endpoints"]},
                   },
                   "required": ["query_type"]
               }
           }
       }
   ]
   ```
4. When GPT-4o calls a tool, execute via `adapter.execute(function_name, **args)`.
5. Feed the result back to GPT-4o for summarization into `TelemetryEvidence`.
6. Run questions in parallel (up to 10 concurrent via `asyncio.gather`).

**TELEMETRY_SYSTEM_PROMPT:**
```
You are a cloud security engineer with read-only access to AWS infrastructure.
Given a security questionnaire question, determine which infrastructure queries
would provide evidence to answer it. Use the available tools to retrieve live
infrastructure state. Summarize what each result proves.
Do NOT fabricate evidence. If no relevant data is found, say so.
```

---

## 8. TELEMETRY ADAPTERS — `backend/telemetry/`

### 8.1 `base.py` — Abstract Interface

```python
from abc import ABC, abstractmethod

class TelemetryAdapter(ABC):
    @abstractmethod
    async def execute(self, function_name: str, **kwargs) -> dict:
        """Execute a telemetry query and return the raw result."""
        ...
```

### 8.2 `mock_adapter.py` — Demo Mode

#### Class: `MockTelemetryAdapter(TelemetryAdapter)`

**Constructor:** Loads all JSON files from `data/mock_infra/` into memory.

**Method: `async execute(function_name, **kwargs) -> dict`**

Logic by function_name:
- `"query_cloudtrail"`: Filter `cloudtrail_events.json` by `event_name`, `time_range_days`, optional key/value filter. Return matching events.
- `"query_iam_config"`: Return the appropriate section from `iam_policies.json` based on `query_type`.
- `"query_encryption_status"`: Return the resource encryption state from `kms_keys.json` + `rds_instances.json`.
- `"query_network_config"`: Return from `security_groups.json`.

### 8.3 `aws_adapter.py` — Production Mode (Stub)

#### Class: `AWSLiveTelemetryAdapter(TelemetryAdapter)`

**Constructor:** Accepts `boto3.Session`, Athena database config.

**Method: `async execute(function_name, **kwargs) -> dict`**

Executes real AWS API calls:
- `"query_cloudtrail"`: Run Athena SQL against CloudTrail log table.
- `"query_iam_config"`: `iam_client.get_account_authorization_details()`, `get_account_password_policy()`, `list_mfa_devices()`.
- `"query_encryption_status"`: `kms_client.describe_key()`, `rds_client.describe_db_instances()`.
- `"query_network_config"`: `ec2_client.describe_security_groups()`, `describe_vpc_flow_logs()`.

**Note for execution agent:** Implement the full method signatures and docstrings but leave the body as `raise NotImplementedError("Production adapter — requires AWS credentials")`. The mock adapter is what gets demoed.

---

## 9. POLICY STORE — `backend/policy_store/`

### 9.1 `indexer.py` — Ingest Policy Documents

#### Function: `index_policies(policy_dir: str, settings: ShieldWallSettings) -> chromadb.Collection`

**Logic:**
1. Initialize ChromaDB persistent client:
   ```python
   client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
   collection = client.get_or_create_collection("shield_wall_policies", metadata={"hnsw:space": "cosine"})
   ```
2. Scan `policy_dir` for `.pdf`, `.md`, `.txt`, `.docx` files.
3. For each file:
   - Extract text (PDF via PyPDF2, DOCX via python-docx, MD/TXT via direct read).
   - Chunk using tiktoken: `settings.policy_chunk_size` tokens with `settings.policy_chunk_overlap` overlap.
   - For each chunk, generate embedding via OpenAI:
     ```python
     openai_client = OpenAI(api_key=settings.openai_api_key)
     resp = openai_client.embeddings.create(model="text-embedding-3-small", input=chunk_text)
     embedding = resp.data[0].embedding
     ```
   - Add to ChromaDB:
     ```python
     collection.add(
         ids=[chunk_id],
         embeddings=[embedding],
         documents=[chunk_text],
         metadatas=[{"source": filename, "section": section_header, "chunk_index": i}]
     )
     ```
4. Return the collection.

### 9.2 `retriever.py` — Search Policies

#### Function: `async retrieve_policy_citations(query: str, collection: chromadb.Collection, settings: ShieldWallSettings) -> list[PolicyCitation]`

**Logic:**
1. Generate query embedding via OpenAI `text-embedding-3-small`.
2. Search ChromaDB:
   ```python
   results = collection.query(query_embeddings=[query_embedding], n_results=settings.policy_top_k)
   ```
3. Map each result to `PolicyCitation`:
   - `policy_document` from metadata `source`.
   - `section` from metadata `section`.
   - `excerpt` from `documents`.
   - `relevance_score` from `distances` (convert to cosine similarity).
   - `chunk_id` from `ids`.
4. Return list sorted by `relevance_score` descending.

---

## 10. POLICY AGENT — `backend/agents/policy_agent.py`

### Function: `async gather_policy_citations(questions: list[SecurityQuestion], collection: chromadb.Collection, settings: ShieldWallSettings) -> dict[int, list[PolicyCitation]]`

**Logic:**
1. Filter to questions where `requires_policy == True`.
2. For each question, call `retrieve_policy_citations(q.normalized_query, collection, settings)`.
3. Run in parallel (up to 20 concurrent).
4. Return `{question_id: [PolicyCitation, ...]}`.

---

## 11. SYNTHESIS AGENT — `backend/agents/synthesis_agent.py`

### Function: `async synthesize_answers(questions: list[SecurityQuestion], telemetry: dict[int, list[TelemetryEvidence]], citations: dict[int, list[PolicyCitation]], settings: ShieldWallSettings) -> list[DraftAnswer]`

**Logic:**
1. For each question, build a context payload:
   ```python
   context = {
       "question": q.normalized_query,
       "category": q.category,
       "telemetry_evidence": [e.model_dump() for e in telemetry.get(q.id, [])],
       "policy_citations": [c.model_dump() for c in citations.get(q.id, [])],
   }
   ```
2. Call GPT-4o Structured Outputs:
   ```python
   completion = client.chat.completions.parse(
       model=settings.gpt4o_model,
       messages=[
           {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
           {"role": "user", "content": json.dumps(context)},
       ],
       response_format=DraftAnswer,
   )
   answer = completion.choices[0].message.parsed
   ```
3. **SYNTHESIS_SYSTEM_PROMPT:**
   ```
   You are a senior information security analyst drafting responses to a vendor
   security questionnaire. You have access to:
   1. Live infrastructure telemetry evidence (retrieved moments ago)
   2. Internal compliance policy citations (from our SOC 2 Type 2 report and
      security policies)

   RULES:
   - Ground every claim in provided evidence. Quote policy sections verbatim
     where possible.
   - Reference specific telemetry findings with timestamps.
   - If telemetry is unavailable, answer from policy only and set confidence
     to "medium".
   - If neither telemetry nor policy covers the question, set confidence to
     "low" and needs_human_review to true.
   - NEVER fabricate evidence, configurations, or policy language.
   - Write in professional, concise enterprise security prose.
   - Use present tense ("Tracelight enforces..." not "Tracelight will enforce...").
   ```
4. Batch questions in groups of 10 for parallel processing.

---

## 12. DRIFT DETECTOR — `backend/agents/drift_detector.py`

### Purpose
Pure Python. Compares telemetry evidence against policy claims. Flags contradictions.

### Function: `detect_drift(answers: list[DraftAnswer]) -> list[DriftAlert]`

**Logic:**
For each answer where both `telemetry_evidence` and `policy_citations` are non-empty:

1. **Encryption drift:** If policy states "AES-256 encryption at rest for all production databases" but telemetry shows any RDS instance with `StorageEncrypted: false` → `DriftAlert(severity="critical")`.

2. **MFA drift:** If policy states "MFA required for all console access" but telemetry shows IAM users without MFA → `DriftAlert(severity="critical")`.

3. **Logging drift:** If policy states "All API calls are logged via CloudTrail" but telemetry shows CloudTrail not enabled or with gaps → `DriftAlert(severity="warning")`.

4. **Network drift:** If policy states "No public-facing endpoints except the load balancer" but telemetry shows security groups with `0.0.0.0/0` inbound rules on non-443 ports → `DriftAlert(severity="warning")`.

5. **Generic drift:** For all other cases, do a keyword comparison. Extract key assertions from policy citations (e.g., "90-day key rotation") and check if telemetry evidence contains contradicting data. If the answer contains `drift_detected: true` from the synthesis agent, create a drift alert.

**Output:** `list[DriftAlert]`. Also set `answer.drift_detected = True` and `answer.needs_human_review = True` for affected answers.

---

## 13. ORCHESTRATOR — `backend/orchestrator.py`

### Class: `ShieldWallOrchestrator`

#### Constructor
```python
def __init__(self, settings: ShieldWallSettings):
    self.settings = settings
    self.jobs: dict[str, ShieldWallJobState] = {}
    self.adapter = MockTelemetryAdapter() if settings.demo_mode else AWSLiveTelemetryAdapter(...)
    self.policy_collection = None  # initialized on startup
```

#### Method: `async initialize()`
Called on app startup. Indexes policy documents into ChromaDB:
```python
self.policy_collection = index_policies("./data/policies", self.settings)
```

#### Method: `async run_pipeline(job_id, file_path, ws_callback)`

**Sequential flow:**

1. **Parse Phase**
   - Detect file type from extension.
   - Route to appropriate parser (`excel_parser`, `pdf_parser`, `text_parser`).
   - Send progress events: `[PARSE] Detected 247 questions in vendor_assessment.xlsx`

2. **Classification Phase**
   - `questionnaire = await parse_questionnaire(raw_questions, settings)`
   - Send events: `[CLASS] 142 require telemetry, 203 require policy citation, 12 categories detected`

3. **Parallel Evidence Gathering**
   - Execute telemetry and policy queries in parallel:
     ```python
     telemetry_task = gather_telemetry(questions_needing_telemetry, self.adapter, settings)
     policy_task = gather_policy_citations(questions_needing_policy, self.policy_collection, settings)
     telemetry_results, policy_results = await asyncio.gather(telemetry_task, policy_task)
     ```
   - Stream per-question progress events:
     ```
     [TELEM] Q#14 — Querying IAM MFA enforcement... ✓ Evidence retrieved
     [POLICY] Q#14 — Found: SOC 2 CC6.1 "Multi-factor authentication is required..." (0.94 relevance)
     ```

4. **Synthesis Phase**
   - `answers = await synthesize_answers(all_questions, telemetry_results, policy_results, settings)`
   - Stream per-answer events:
     ```
     [SYNTH] Q#14 — Answer drafted (HIGH confidence, telemetry + policy grounded)
     [SYNTH] Q#87 — Answer drafted (LOW confidence, needs human review)
     ```

5. **Drift Detection Phase**
   - `drift_alerts = detect_drift(answers)`
   - For each alert: send `drift_alert` event type:
     ```
     [DRIFT] ⚠ CRITICAL: Q#23 — Policy claims MFA enforced, telemetry shows 2 users without MFA
     ```

6. **Complete**
   - Build `QuestionnaireResult`.
   - Send `complete` event with full result payload.

**Timeout:** `asyncio.wait_for(..., timeout=settings.generation_timeout_s)`.

---

## 14. FASTAPI APPLICATION — `backend/main.py`

### Endpoints

#### `POST /api/upload`
- Accept: `.xlsx`, `.csv`, `.pdf`, `.docx`, `.txt`
- File size limit: `settings.max_file_size_mb`
- Return: `{"job_id": "uuid"}`

#### `WebSocket /ws/{job_id}`
- Streams `ShieldWallWSEvent` as JSON text frames.
- Triggers `orchestrator.run_pipeline(job_id, file_path, ws_callback)`.

#### `GET /api/result/{job_id}`
- Returns full `ShieldWallJobState` as JSON.
- Includes all answers, drift alerts, audit log.

#### `GET /api/export/{job_id}`
- Generates a populated response document:
  - If original was `.xlsx`: write answers back into a new column in the original spreadsheet.
  - If original was `.pdf`/`.docx`: generate a new `.docx` with question-answer pairs.
- Return as `FileResponse`.

#### `POST /api/policies/reindex`
- Triggers re-indexing of policy documents from `data/policies/`.
- Useful after updating policy files.

#### CORS
```python
allow_origins=["http://localhost:5173"]
```

---

## 15. FRONTEND COMPONENTS

### 15.1 `QuestionnaireUpload.jsx`
- Drop zone accepting `.xlsx`, `.csv`, `.pdf`, `.docx`, `.txt`.
- Subtext: "Upload a vendor security questionnaire. We'll answer it in minutes."
- File type badges and size limit display.

### 15.2 `ProcessingTerminal.jsx`
- Dark terminal (same aesthetic as Phase 1 SchemaTerminal).
- Shows parsing, classification, telemetry queries, policy lookups in real-time.
- Color-coded prefixes:
  - `[PARSE]` — white
  - `[CLASS]` — cyan
  - `[TELEM]` — green (queries being executed)
  - `[POLICY]` — blue (citations found)
  - `[SYNTH]` — amber (answers being drafted)
  - `[DRIFT]` — red (contradictions detected)

### 15.3 `AnswerGrid.jsx`
- Table view: columns = `#`, `Category`, `Question (truncated)`, `Answer (truncated)`, `Confidence`, `Sources`, `Review`.
- Confidence badges: HIGH = green, MEDIUM = amber, LOW = red.
- Sources badges: "Telemetry" green pill, "Policy" blue pill.
- "Review" column: checkbox for needs_human_review rows (pre-checked for LOW + drift).
- Click a row to expand full question, full answer, evidence details, and policy citations.
- Filter bar: filter by category, confidence, drift status.

### 15.4 `DriftAlerts.jsx`
- Card layout at the top of the page (above AnswerGrid) when drift is detected.
- Each card: severity icon (red shield = critical, amber triangle = warning), question number, policy claim vs telemetry reality, recommended action.
- Collapsible — defaults to expanded if any CRITICAL alerts exist.

### 15.5 `ExportPanel.jsx`
- Fixed bottom bar (appears after completion).
- Stats: "247 questions answered | 231 high confidence | 3 drift alerts | 13 need review"
- Export button: "Download Completed Questionnaire" → `GET /api/export/{jobId}`.
- "Copy All Answers" button → copies Q&A pairs to clipboard.

### Tailwind Config
Reuse Phase 1 colors, extend with:
```javascript
colors: {
  // ... Phase 1 colors
  'harbor-blue': '#60A5FA',
  'harbor-cyan': '#22D3EE',
}
```

---

## 16. MOCK INFRASTRUCTURE DATA

### `data/mock_infra/cloudtrail_events.json`
50+ simulated events covering:
- `ConsoleLogin` events (with and without MFA)
- `CreateUser`, `DeleteUser`, `AttachUserPolicy`
- `CreateDBInstance`, `ModifyDBInstance`
- `PutBucketEncryption`, `CreateKey`
- `AuthorizeSecurityGroupIngress`
- Each event: `{"eventName": str, "eventTime": ISO-8601, "userIdentity": {...}, "requestParameters": {...}, "responseElements": {...}}`

### `data/mock_infra/iam_policies.json`
- Password policy: `MinimumPasswordLength: 14`, `RequireMFA: true`, `MaxPasswordAge: 90`
- 3 IAM users: 2 with MFA enabled, 1 without (to trigger drift detection)
- 5 IAM roles with attached policies

### `data/mock_infra/kms_keys.json`
- 3 KMS keys: production (AES-256, auto-rotation 365 days), staging, development
- Key policies and grants

### `data/mock_infra/rds_instances.json`
- 2 RDS instances: production (encrypted, Multi-AZ, automated backups 35-day retention), staging (encrypted, single-AZ)

### `data/mock_infra/security_groups.json`
- Production SG: inbound 443 from `0.0.0.0/0`, 5432 from VPC CIDR only
- Staging SG: inbound 443 from `0.0.0.0/0`, 22 from office IP only
- One intentionally misconfigured SG: port 8080 open to `0.0.0.0/0` (to trigger drift)

---

## 17. SAMPLE POLICY DOCUMENTS

### `data/policies/soc2_type2_report.pdf`
A realistic 15-20 page mock SOC 2 Type 2 report covering:
- CC1 (Control Environment) through CC9 (Risk Mitigation)
- Specific control IDs (CC6.1 — Logical Access, CC6.6 — Encryption, CC7.2 — Monitoring)
- Each control: description, test procedure, test result

### `data/policies/data_classification.md`
- 4 tiers: Public, Internal, Confidential, Restricted
- Handling requirements per tier (encryption, access, retention, disposal)

### `data/policies/network_security.md`
- VPC architecture, segmentation, WAF, DDoS mitigation
- Approved ports and protocols
- VPN requirements for remote access

### `data/policies/incident_response.md`
- 6-phase IR plan: Preparation, Identification, Containment, Eradication, Recovery, Lessons Learned
- Escalation matrix, SLAs (P1: 15min, P2: 1hr, P3: 4hr)
- Notification procedures

### `data/policies/access_control.md`
- RBAC model, least privilege, JIT access
- Onboarding/offboarding procedures
- Password policy, MFA requirements
- Quarterly access reviews

---

## 18. TESTS — Required Coverage

### `tests/test_questionnaire_parser.py`
- Test: Excel questionnaire with 50 questions → all parsed and classified.
- Test: PDF with numbered questions → correct segmentation.
- Test: CSV with question column → auto-detection works.
- Test: Empty file → graceful error.
- Test: File exceeding max_questions → truncation with warning.

### `tests/test_telemetry_agent.py`
- Test: MFA question → GPT-4o calls `query_iam_config(query_type="mfa_status")`.
- Test: Encryption question → calls `query_encryption_status(resource_type="rds")`.
- Test: Mock adapter returns expected data for each function.
- Test: Question not requiring telemetry → skipped correctly.

### `tests/test_policy_agent.py`
- Test: Encryption question → retrieves CC6.6 from SOC 2 with relevance > 0.8.
- Test: Index → search round-trip with ChromaDB.
- Test: No relevant policy → returns empty list.

### `tests/test_synthesis_agent.py`
- Test: High-confidence answer (telemetry + policy) → confidence="high".
- Test: Policy-only answer → confidence="medium".
- Test: No evidence → confidence="low", needs_human_review=true.

### `tests/test_drift_detector.py`
- Test: MFA policy states "required" but IAM shows user without MFA → `DriftAlert(severity="critical")`.
- Test: Encryption policy matches telemetry → no drift alert.
- Test: Open security group contradicts network policy → `DriftAlert(severity="warning")`.

### `tests/test_orchestrator.py`
- Test: Full pipeline with mocked agents → all events fire in correct order.
- Test: Timeout → error state.
- Test: Drift alerts surface correctly in final result.

---

## 19. DOCKERFILE

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Port 8001 to avoid collision with Phase 1 (port 8000).

---

## 20. BUILD ORDER & DEPENDENCY CHAIN

```
Step 1:  schemas.py (pure Pydantic models — no deps)
Step 2:  config.py (pydantic-settings, python-dotenv)
Step 3:  File parsers — excel_parser.py, pdf_parser.py, text_parser.py
         (openpyxl, PyPDF2, python-docx, pandas)
Step 4:  Mock infrastructure data — all JSON files in data/mock_infra/
Step 5:  Sample policy documents — all files in data/policies/
Step 6:  Telemetry adapters — base.py, mock_adapter.py, aws_adapter.py (stub)
         (Depends on: Step 4 for test data)
Step 7:  Policy store — indexer.py, retriever.py
         (Depends on: Steps 5, chromadb, openai embeddings)
Step 8:  Questionnaire parser agent
         (Depends on: Steps 1-3, google-genai)
Step 9:  Telemetry agent
         (Depends on: Steps 1, 6, openai)
Step 10: Policy agent
         (Depends on: Steps 1, 7)
Step 11: Synthesis agent
         (Depends on: Steps 1, 9, 10, openai structured outputs)
Step 12: Drift detector
         (Depends on: Steps 1, 11 — pure Python)
Step 13: Orchestrator
         (Depends on: all agents + adapters + store)
Step 14: main.py — FastAPI app
         (Depends on: Step 13)
Step 15: Frontend components
         (Depends on: backend API being functional)
Step 16: Integration tests
         (Depends on: everything)
```

Steps 3, 4, 5 are independent — build in parallel.
Steps 6 and 7 are independent — build in parallel.
Steps 8, 9, 10 are independent — build in parallel.

---

## 21. CRITICAL BOUNDARIES

- **This is an INTERNAL ops tool.** It is not customer-facing. The UI is for Tracelight's own sales/legal team.
- **Anti-replication:** Does not touch the DAG engine, Excel add-in, or any modeling functionality.
- **Demo mode is the default.** Production AWS integration is stubbed. Do not implement real AWS calls beyond the interface signature.
- **No authentication** for the demo. Single-user internal tool.
- **No database** beyond ChromaDB for the policy vector store. Job state is in-memory.
- **The mock data must be realistic enough to demo convincingly.** The mock infra should contain realistic AWS resource configurations including intentional drift for demo impact.
- **Phase 3 (IC Memo Synthesizer) is KILLED.** Do not build. Do not reference.

---

*End of Phase 2 Technical Specification.*
