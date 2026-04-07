# PHASE 3 TECHNICAL SPECIFICATION
## Integration, End-to-End Testing, Deployment & Demo Prep
### File-by-File, Function-by-Function Blueprint for Execution Agent

---

## 0. STRATEGIC CONTEXT

### What This Phase Covers
Phase 1 (Safe-Harbor) and Phase 2 (Shield-Wall) are individually built and code-reviewed. Phase 3 brings them together into a **single deployable demo** with:
1. A unified launcher/landing page that routes to either tool
2. End-to-end tests proving each pipeline works with real API calls
3. Sample Excel templates actually created and committed (not just specced)
4. Docker Compose for one-command local startup
5. Deployment config for Google Cloud Run (backend) + Netlify/Vercel (frontend)
6. Three pre-loaded demo scenarios per the PRD's Step 9

### What This Phase Does NOT Cover
- IC Memo Synthesizer (KILLED — do not build)
- Production auth/authz (not needed for demo)
- Production database (in-memory is fine)
- CI/CD pipelines (manual deploy)

---

## 1. DIRECTORY STRUCTURE (additions/changes only)

```
tracelight-safe-harbor/
├── docker-compose.yml              # NEW — orchestrates both services
├── .env.example                    # NEW — unified env template
├── launcher/                       # NEW — unified landing page
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── index.css
├── safe-harbor/
│   ├── templates/                  # POPULATE — actual .xlsx files
│   │   ├── lbo_template.xlsx
│   │   ├── dcf_template.xlsx
│   │   └── three_statement_template.xlsx
│   ├── tests/                      # NEW — E2E and unit tests
│   │   ├── conftest.py
│   │   ├── test_parser.py
│   │   ├── test_validator.py
│   │   ├── test_schema_extractor.py
│   │   ├── test_synthetic_gen.py
│   │   ├── test_orchestrator_e2e.py
│   │   └── fixtures/
│   │       └── sample_lbo.xlsx
│   ├── backend/
│   │   └── (existing — no changes unless bugs found in E2E)
│   └── frontend/
│       └── (existing — minor polish)
├── shield-wall/
│   ├── tests/                      # NEW — E2E and unit tests
│   │   ├── conftest.py
│   │   ├── test_questionnaire_parser.py
│   │   ├── test_telemetry_agent.py
│   │   ├── test_policy_agent.py
│   │   ├── test_synthesis_agent.py
│   │   ├── test_drift_detector.py
│   │   ├── test_orchestrator_e2e.py
│   │   └── fixtures/
│   │       └── sample_questionnaire.xlsx
│   ├── backend/
│   │   └── (existing — no changes unless bugs found in E2E)
│   └── frontend/
│       └── (existing — minor polish)
└── demo/                           # NEW — demo prep materials
    ├── scenarios.md                # The 3 demo scenarios scripted
    └── pitch_notes.md              # Peter/Aleks/Janek pitch angles
```

---

## 2. DOCKER COMPOSE — `docker-compose.yml`

### Purpose
One command (`docker compose up`) starts both backends and all three frontends.

### Spec

```yaml
version: "3.9"

services:
  safe-harbor-backend:
    build:
      context: ./safe-harbor
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./safe-harbor/templates:/app/templates
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 10s
      timeout: 5s
      retries: 3

  shield-wall-backend:
    build:
      context: ./shield-wall
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    env_file:
      - .env
    volumes:
      - ./shield-wall/data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/docs"]
      interval: 10s
      timeout: 5s
      retries: 3

  launcher:
    build:
      context: ./launcher
      dockerfile: Dockerfile
    ports:
      - "5173:5173"
    depends_on:
      - safe-harbor-backend
      - shield-wall-backend

  safe-harbor-frontend:
    build:
      context: ./safe-harbor/frontend
      dockerfile: Dockerfile
    ports:
      - "5174:5174"
    depends_on:
      - safe-harbor-backend

  shield-wall-frontend:
    build:
      context: ./shield-wall/frontend
      dockerfile: Dockerfile
    ports:
      - "5175:5175"
    depends_on:
      - shield-wall-backend
```

### Frontend Dockerfiles (new, one per frontend)

Each frontend gets a minimal Dockerfile:
```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
EXPOSE <PORT>
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "<PORT>"]
```

Ports:
- `5173`: Launcher
- `5174`: Safe-Harbor frontend
- `5175`: Shield-Wall frontend

### `.env.example`

```
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=tracelight-demo
GOOGLE_CLOUD_LOCATION=us-central1
```

---

## 3. UNIFIED LAUNCHER — `launcher/`

### Purpose
A single landing page that routes the user to either Safe-Harbor or Shield-Wall. This is what opens when the demo starts.

### `launcher/src/App.jsx`

**UI:**
- Full-screen dark background (`harbor-bg`).
- Centered logo area: "Tracelight — AI Sidecars" (or company wordmark).
- Two large cards, side by side:

**Card 1: Safe-Harbor**
- Icon: shield with data flowing in
- Title: "Safe-Harbor"
- Subtitle: "Synthetic Financial Data Fabric"
- Description: "Generate mathematically verified synthetic data for empty Excel templates. Zero sensitive data. Instant testing."
- Tag: "PRE-CORE — For Prospects"
- CTA button: "Launch Safe-Harbor" → navigates to `http://localhost:5174`

**Card 2: Shield-Wall**
- Icon: shield with lock
- Title: "Shield-Wall"
- Subtitle: "Autonomous InfoSec Responder"
- Description: "Answer vendor security questionnaires in minutes. AI-powered with live infrastructure evidence."
- Tag: "PARALLEL — Internal Ops"
- CTA button: "Launch Shield-Wall" → navigates to `http://localhost:5175`

- Bottom footer: "Anti-Replication Compliant — Does not touch the core DAG engine"

### Tailwind Config
Same color palette as Phase 1/2 (`harbor-bg`, `harbor-surface`, `harbor-green`, etc.).

### Dependencies
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "vite": "^6.0.0"
  }
}
```

---

## 4. SAMPLE EXCEL TEMPLATES — `safe-harbor/templates/`

These must be **real, functional `.xlsx` files** — not placeholders. The execution agent must create them using `openpyxl`.

### 4.1 Template Generator Script — `safe-harbor/scripts/generate_templates.py`

A standalone Python script that generates the three templates. Run once, commit the output `.xlsx` files.

#### `generate_lbo_template()`

**Sheets and structure:**

**Sheet 1: "Income Statement"**
- Row 1: Headers — `""`, `FY2020`, `FY2021`, `FY2022`, `FY2023`, `FY2024`, `FY2025`
- Column A (row labels): Revenue, COGS, Gross Profit, SG&A, EBITDA, D&A, EBIT, Interest Expense, EBT, Tax, Net Income
- Input cells (empty): Revenue, COGS, SG&A, D&A, Tax (rows 2-6 for each period)
- Formula cells:
  - `Gross Profit = Revenue - COGS`
  - `EBITDA = Gross Profit - SG&A`
  - `EBIT = EBITDA - D&A`
  - `Interest Expense = ='Debt Schedule'!InterestExpense` (inter-sheet ref)
  - `EBT = EBIT - Interest Expense`
  - `Net Income = EBT - Tax`

**Sheet 2: "Balance Sheet"**
- Row labels: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets, PP&E Net, Goodwill, Other Non-Current Assets, Total Assets, Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities, Senior Debt, Mezzanine Debt, Total Liabilities, Common Equity, Retained Earnings, Total Equity, Total Liabilities & Equity
- Input cells: Cash, AR, Inventory, Other CA, PP&E, Goodwill, Other NCA, AP, Accrued, Current Debt, Senior Debt, Mezzanine, Common Equity
- Formula cells:
  - `Total Current Assets = SUM(Cash:Other CA)`
  - `Total Assets = Total CA + PP&E + Goodwill + Other NCA`
  - `Total Current Liabilities = SUM(AP:Current Debt)`
  - `Total Liabilities = Total CL + Senior Debt + Mezzanine`
  - `Retained Earnings` = previous period RE + `='Income Statement'!Net Income` (inter-sheet)
  - `Total Equity = Common Equity + Retained Earnings`
  - `Total L&E = Total Liabilities + Total Equity`

**Sheet 3: "Cash Flow Statement"**
- Row labels: Net Income, D&A, Changes in Working Capital, Operating CF, CapEx, Investing CF, Debt Drawdowns, Debt Repayments, Dividends, Financing CF, Net Change in Cash, Beginning Cash, Ending Cash
- Input cells: Changes in WC, CapEx, Debt Drawdowns, Debt Repayments, Dividends
- Formula cells:
  - `Net Income = ='Income Statement'!Net Income`
  - `D&A = ='Income Statement'!D&A`
  - `Operating CF = Net Income + D&A + Changes in WC`
  - `Investing CF = -CapEx`
  - `Financing CF = Drawdowns - Repayments - Dividends`
  - `Net Change = Operating + Investing + Financing`
  - `Beginning Cash = previous period Ending Cash` (first period = 0)
  - `Ending Cash = Beginning + Net Change`

**Sheet 4: "Debt Schedule"**
- Two tranches: Senior Debt, Mezzanine
- Per tranche: Beginning Balance, Drawdowns, Repayments, Ending Balance, Interest Rate, Interest Expense
- Input cells: Drawdowns, Repayments, Interest Rate (for first period: Beginning Balance)
- Formula cells:
  - `Ending Balance = Beginning + Drawdowns - Repayments`
  - `Interest Expense = Beginning Balance * Interest Rate`
  - `Beginning Balance (period N) = Ending Balance (period N-1)`
- Total Interest Expense row = sum of both tranches (referenced by Income Statement)

**Sheet 5: "Returns Analysis"**
- Single column of summary metrics
- Input cells: Entry EV, Exit Multiple, Equity Invested
- Formula cells:
  - `Exit EV = Exit Multiple * FY2025 EBITDA` (inter-sheet)
  - `Net Debt at Exit = ='Debt Schedule'!Total Ending Debt`
  - `Exit Equity = Exit EV - Net Debt at Exit`
  - `MOIC = Exit Equity / Equity Invested`
  - `IRR` (leave as input — IRR is complex to auto-formula)

**Formatting:**
- Bold headers
- Currency format for money cells (`#,##0`)
- Percentage format for rates and margins (`0.0%`)
- Light gray background on formula rows to visually distinguish inputs from outputs

#### `generate_dcf_template()`

Simplified 4-sheet model:
- Revenue Build (input: revenue by segment, growth rates)
- Income Statement (formulas link to Revenue Build)
- Free Cash Flow (formulas link to IS)
- DCF Valuation (input: WACC, Terminal Growth; formulas: PV of FCFs, Terminal Value, Enterprise Value)

#### `generate_three_statement_template()`

Standard 3-sheet model (IS, BS, CF) with full inter-statement linkages. No debt schedule or returns.

### Build Instructions
```bash
cd safe-harbor/scripts
python generate_templates.py
# Output: safe-harbor/templates/lbo_template.xlsx
#         safe-harbor/templates/dcf_template.xlsx
#         safe-harbor/templates/three_statement_template.xlsx
```

Commit the generated `.xlsx` files.

---

## 5. SAMPLE QUESTIONNAIRE — `shield-wall/tests/fixtures/sample_questionnaire.xlsx`

A real `.xlsx` questionnaire for Shield-Wall E2E testing.

### Structure
- Sheet 1: "Security Assessment"
- Header row: `#`, `Category`, `Question`, `Response`, `Evidence`
- 30 questions covering all 12 spec categories:

| # | Category | Question |
|---|----------|----------|
| 1 | access_control | Does your organization enforce multi-factor authentication for all user accounts? |
| 2 | encryption | Are all production databases encrypted at rest using AES-256 or equivalent? |
| 3 | encryption | Describe your key management practices including rotation schedules. |
| 4 | network_security | Are there any publicly accessible endpoints other than your load balancer? |
| 5 | network_security | Describe your VPC segmentation and network access control strategy. |
| 6 | incident_response | Do you have a documented incident response plan? What are your SLAs? |
| 7 | incident_response | Describe your breach notification procedures and timelines. |
| 8 | logging_monitoring | Are all API calls logged? What is your log retention period? |
| 9 | logging_monitoring | Do you use a SIEM? Describe your monitoring and alerting capabilities. |
| 10 | data_classification | How do you classify data? Describe your data handling tiers. |
| 11 | business_continuity | What is your RTO and RPO for critical systems? |
| 12 | business_continuity | Describe your disaster recovery architecture. |
| 13 | vendor_management | How do you assess and monitor third-party vendor risk? |
| 14 | compliance | Are you SOC 2 Type 2 certified? When was your last audit? |
| 15 | compliance | Do you comply with GDPR? How do you handle data subject requests? |
| 16 | change_management | Describe your change management and deployment process. |
| 17 | physical_security | Where are your data centers located? What physical security controls exist? |
| 18 | access_control | Describe your RBAC model and least-privilege enforcement. |
| 19 | access_control | How do you handle employee onboarding and offboarding access? |
| 20 | encryption | Is data encrypted in transit? What TLS version do you enforce? |
| 21 | network_security | Do you perform regular penetration testing? How often? |
| 22 | logging_monitoring | How do you detect unauthorized access attempts? |
| 23 | incident_response | Have you experienced any security breaches in the last 24 months? |
| 24 | data_classification | How do you handle data deletion and disposal? |
| 25 | compliance | Do you have cyber insurance? What is the coverage? |
| 26 | access_control | Do you enforce password complexity requirements? What are they? |
| 27 | encryption | Describe your backup encryption strategy. |
| 28 | business_continuity | How often do you test your disaster recovery plan? |
| 29 | vendor_management | Do your subprocessors maintain equivalent security certifications? |
| 30 | change_management | How do you manage secrets and API keys in your codebase? |

"Response" and "Evidence" columns are empty (to be filled by Shield-Wall).

Generate with `openpyxl` in a script: `shield-wall/scripts/generate_fixtures.py`.

---

## 6. TESTS — Safe-Harbor

### `safe-harbor/tests/conftest.py`

```python
import pytest
from backend.config import get_settings

@pytest.fixture
def settings():
    return get_settings()

@pytest.fixture
def sample_lbo_path():
    return "templates/lbo_template.xlsx"
```

### `safe-harbor/tests/test_parser.py`
- **test_parse_lbo_template**: Load `lbo_template.xlsx` → verify 5 sheets detected, correct input cell count (>50), formula cells detected, inter-sheet refs found (IS→CF, CF→BS, DS→IS).
- **test_parse_empty_check**: Create a template with data in input cells → verify `TemplateNotEmptyError` raised when >5% populated.
- **test_parse_formula_detection**: Verify cells starting with `=` are classified as formula, not input.
- **test_parse_temporal_headers**: Verify `FY2020`-`FY2025` detected as temporal headers.

### `safe-harbor/tests/test_validator.py`
- **test_bs_balanced**: Feed a `SyntheticPayload` where Assets == L+E → expect `PASSED`.
- **test_bs_imbalanced_plug**: Feed payload where Assets != L+E → expect `PASSED_WITH_PLUGS`, verify Cash adjusted.
- **test_cf_reconciliation**: Feed payload where Ending Cash != Begin + Net → verify plug applied.
- **test_margin_violation**: Feed payload where EBITDA margin > 0.8 → expect `FAILED`, EBITDA in `needs_regeneration`.
- **test_depreciation_cap**: Feed payload where cumulative D&A > CapEx + PP&E → verify cap applied.
- **test_debt_schedule**: Feed payload where Ending Debt != Begin + Draw - Repay → verify repayment adjusted.
- **test_all_rules_pass**: Feed a perfectly valid payload → expect `PASSED`, 0 adjustments.

### `safe-harbor/tests/test_schema_extractor.py`
- **test_gemini_success** (mock): Mock Gemini response with valid JSON → verify `TemplateSchema` parsed correctly with cell_references populated.
- **test_gemini_failure_gpt4o_fallback** (mock): Mock Gemini to raise, mock GPT-4o to succeed → verify fallback works.
- All tests use `unittest.mock.patch` to avoid real API calls.

### `safe-harbor/tests/test_synthetic_gen.py`
- **test_generation_returns_payload** (mock): Mock GPT-4o `chat.completions.parse` → verify `SyntheticPayload` returned with correct structure.
- **test_retry_instructions_appended** (mock): Pass `retry_instructions` → verify prompt includes them.

### `safe-harbor/tests/test_orchestrator_e2e.py`
- **test_full_pipeline_with_mocks**: Mock all agents (schema extractor, synthetic gen). Use real parser and validator with `lbo_template.xlsx`. Verify:
  - All WebSocket events fire in order: parse → schema_extract → generate → validate → write → complete.
  - Output `.xlsx` file exists and is readable.
  - Validation result is PASSED or PASSED_WITH_PLUGS.
- **test_timeout_handling**: Set `generation_timeout_s=0.001` → verify error state.

### Test Runner Command
```bash
cd safe-harbor && python -m pytest tests/ -v --tb=short
```

---

## 7. TESTS — Shield-Wall

### `shield-wall/tests/conftest.py`

```python
import pytest
from backend.config import get_settings
from backend.telemetry.mock_adapter import MockTelemetryAdapter

@pytest.fixture
def settings():
    return get_settings()

@pytest.fixture
def mock_adapter():
    return MockTelemetryAdapter()

@pytest.fixture
def sample_questionnaire_path():
    return "tests/fixtures/sample_questionnaire.xlsx"
```

### `shield-wall/tests/test_questionnaire_parser.py`
- **test_excel_parsing**: Parse `sample_questionnaire.xlsx` → verify 30 questions extracted.
- **test_classification** (mock): Mock Gemini → verify all 30 questions classified with valid categories.
- **test_gemini_failure_gpt4o_fallback** (mock): Mock Gemini to raise, mock GPT-4o → verify fallback.

### `shield-wall/tests/test_telemetry_agent.py`
- **test_mfa_question**: Feed question "Is MFA enforced?" → verify `query_iam_config(query_type="mfa_status")` called on mock adapter.
- **test_encryption_question**: Feed encryption question → verify `query_encryption_status` called.
- **test_mock_adapter_cloudtrail**: Call `mock_adapter.execute("query_cloudtrail", event_name="ConsoleLogin")` → verify returns events.
- **test_mock_adapter_iam**: Call `mock_adapter.execute("query_iam_config", query_type="mfa_status")` → verify returns users including one without MFA.
- **test_concurrency_limit**: Feed 20 questions → verify semaphore limits to 10 concurrent.

### `shield-wall/tests/test_policy_agent.py`
- **test_index_and_search**: Index `data/policies/`, search for "encryption at rest" → verify relevance > 0.5 from soc2 or data_classification doc.
- **test_no_match**: Search for "quantum computing" → verify empty result.

### `shield-wall/tests/test_drift_detector.py`
- **test_mfa_drift**: Create DraftAnswer with policy citing "MFA required" and telemetry showing `"MFAEnabled": false` → verify critical DriftAlert.
- **test_encryption_drift**: Policy says "AES-256", telemetry shows `"StorageEncrypted": false` → critical alert.
- **test_network_drift**: Policy says "only 443 public", telemetry shows port 8080 on 0.0.0.0/0 → warning alert.
- **test_no_drift**: Matching policy and telemetry → no alerts.
- **test_deduplication**: Ensure same question_id doesn't produce duplicate alerts.

### `shield-wall/tests/test_orchestrator_e2e.py`
- **test_full_pipeline_with_mocks**: Mock LLM agents, use real parsers, mock adapter, real policy store. Verify all WS events fire correctly.

### Test Runner Command
```bash
cd shield-wall && python -m pytest tests/ -v --tb=short
```

---

## 8. FRONTEND POLISH

### 8.1 Safe-Harbor Frontend — Vite Config Fix

Update `safe-harbor/frontend/vite.config.js` to proxy `/templates/` to the backend so sample template buttons work:

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/templates': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

Add a static file mount on the backend `main.py`:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/templates", StaticFiles(directory="templates"), name="templates")
```

### 8.2 Shield-Wall Frontend — Vite Config

```javascript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
  },
});
```

### 8.3 Error States (Both Frontends)

Add a global error boundary component `ErrorBanner.jsx` to both frontends:
- If a WebSocket event with `event_type === "error"` is received, display a red banner at the top with the error detail and a "Try Again" button that resets to UPLOAD phase.

### 8.4 Loading Animations

Both `SchemaTerminal.jsx` and `ProcessingTerminal.jsx` should show a subtle pulsing dot animation when waiting for events (already partially implemented — verify the `animate-pulse` class is applied).

---

## 9. SAFE-HARBOR BACKEND — STATIC FILE SERVING

### Add to `safe-harbor/backend/main.py`

```python
from fastapi.staticfiles import StaticFiles

# After app creation, before routes:
app.mount("/templates", StaticFiles(directory="templates"), name="templates")
```

This allows the frontend's sample template buttons to fetch `/templates/lbo_template.xlsx` etc.

---

## 10. DEMO SCENARIOS — `demo/scenarios.md`

### Scenario 1: "The PE Associate" (Safe-Harbor)
**Setup:** PE associate at Bain Capital needs to evaluate Tracelight for their LBO modeling workflow. InfoSec says "no live data for 3 months."

**Flow:**
1. Open Launcher → click "Launch Safe-Harbor"
2. Click "LBO Template" sample button
3. Watch Schema Scan (5s) → Data Waterfall (20s) → Verdict Badge
4. Click "Download .xlsx" → open in Excel → verify numbers are realistic and formulas work
5. Click "View Audit Trail" → show every validation rule passed

**Peter Pitch:** "Your prospects tell you InfoSec needs 3 months. With Safe-Harbor, they test in 30 seconds. Zero sensitive data. Mathematically verified. Your sales cycle just got 8 weeks shorter."

**Cost Callout:** "Eight cents per synthetic model."

### Scenario 2: "The Consulting Analyst" (Safe-Harbor)
**Setup:** McKinsey analyst uploads an empty 3-Statement model.

**Flow:** Same as Scenario 1 but with `three_statement_template.xlsx`. Highlights: No debt schedule complexity, pure IS/BS/CF linkage.

**Janek Pitch:** "No prompting. No configuration. Upload and go. The complexity is in the backend."

### Scenario 3: "The Procurement Team" (Shield-Wall)
**Setup:** Goldman Sachs sent a 250-question vendor security assessment. Tracelight's ops team needs to respond by Friday.

**Flow:**
1. Open Launcher → click "Launch Shield-Wall"
2. Upload `sample_questionnaire.xlsx` (30 questions for demo speed)
3. Watch Processing Terminal: parsing → classification → parallel evidence gathering → synthesis
4. Review AnswerGrid: filter by "Drift" → show the MFA user without MFA
5. Click "Download Completed Questionnaire" → get `.docx`

**Aleks Pitch:** "Air-gapped. Single-tenant. Read-only telemetry. Your infrastructure data never leaves your VPC. And it caught a real drift — Bob doesn't have MFA."

---

## 11. PITCH NOTES — `demo/pitch_notes.md`

### For Peter (CEO) — ROI & Sales Cycle
- Safe-Harbor compresses proof-of-concept from months to minutes
- Cost: $0.08 per synthetic model generation
- Prospect can test immediately without any InfoSec approvals
- Shield-Wall: saves 5-10 hours per vendor assessment response

### For Aleks (CTO) — Architecture & Trust
- Deterministic Validation Agent: zero LLM hallucination in the trust layer
- 6 algebraic rules enforced with zero tolerance
- Plug-account corrections are transparent and auditable
- Shield-Wall: air-gapped, read-only telemetry, drift detection catches real issues
- All agent outputs are structured (Pydantic schemas end-to-end)

### For Janek (CPO) — UX & Product
- Zero-prompt interface: upload and go
- Three-phase magic moment: Schema Scan → Data Waterfall → Verdict
- Every interaction is visual and verifiable
- Shield-Wall: answers in minutes, not days — professional DOCX output

---

## 12. BUILD ORDER & DEPENDENCY CHAIN

```
Step 1:  Template generator script (safe-harbor/scripts/generate_templates.py)
         → generates 3 .xlsx templates → commit the outputs
Step 2:  Sample questionnaire generator (shield-wall/scripts/generate_fixtures.py)
         → generates sample_questionnaire.xlsx → commit
Step 3:  Static file serving on safe-harbor backend (mount /templates)
Step 4:  Vite config updates for both frontends (ports, proxy)
Step 5:  Launcher app (new: launcher/ directory with React + Tailwind)
Step 6:  docker-compose.yml + frontend Dockerfiles
Step 7:  Safe-Harbor tests (test_parser, test_validator, test_schema_extractor,
         test_synthetic_gen, test_orchestrator_e2e)
Step 8:  Shield-Wall tests (test_questionnaire_parser, test_telemetry_agent,
         test_policy_agent, test_drift_detector, test_orchestrator_e2e)
Step 9:  Error boundary components (both frontends)
Step 10: .env.example
Step 11: demo/scenarios.md + demo/pitch_notes.md
Step 12: End-to-end smoke test: `docker compose up`, run both demo scenarios manually
```

Steps 1+2 are independent — run in parallel.
Steps 3+4+5 are independent — run in parallel.
Steps 7+8 are independent — run in parallel.

---

## 13. CRITICAL BOUNDARIES

- **No new agents, no new AI features.** Phase 3 is integration, testing, and polish only.
- **Do not modify agent logic** unless an E2E test reveals a bug. If a bug is found, fix it minimally.
- **Do not add authentication, rate limiting, or database.** This is a demo, not production.
- **Do not build CI/CD.** Deployment is manual.
- **IC Memo Synthesizer is KILLED.** Do not build, do not reference, do not stub.
- **The template `.xlsx` files must contain real Excel formulas with inter-sheet references.** They are the proof that the parser and writer work correctly. If the templates are broken, the entire Safe-Harbor demo fails.

---

*End of Phase 3 Technical Specification.*
