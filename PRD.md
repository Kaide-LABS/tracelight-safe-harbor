# TRACELIGHT FDE — MASTER PRD
## Red-Team Audit & Final Architecture

---

# TASK 1: THE SOURCE CHECK

## Critical Intelligence Extracted from Source Material

### Peter Fuller (CEO) — What Gemini Got Right
- InfoSec friction is real. Peter explicitly posts: "Invest in a testing set-up. Create non-sensitive test data for use cases you care about." This validates the Safe-Harbor concept directionally.
- Enterprise sales cycle compression is his #1 operational obsession. Multiple posts confirm this.
- He hates "workslop" — AI that produces bad output. He wrote an entire manifesto about it. Any demo that produces sloppy, unverifiable output will be dead on arrival.
- He values SOC 2 Type 2 (they already have it) and frames security as a competitive moat, not a burden.

### Peter Fuller — What Gemini Missed (RED FLAGS)
1. **Tracelight already turns spreadsheets into shareable webpages.** Peter posted *two weeks ago*: "From today, Tracelight turns your spreadsheets into beautiful, shareable webpages." The IC Memo Synthesizer proposal is building something they are actively shipping. This is a kill shot to that proposal.
2. **Plan Mode already exists.** Tracelight now co-develops detailed plans with users before executing. This means the "zero-prompt" framing in the proposals is addressing a problem they've already solved.
3. **Spreadsheet Compare already exists.** They launched a diff tool for comparing two versions of spreadsheets. The proposals don't acknowledge any of these recent product launches.
4. **Change Reviews already exist.** They built a review interface for validating every AI-made change. The "workslop" concern isn't just philosophical — they've already shipped the product answer.
5. **The real macro threat is OpenAI entering financial modeling.** Peter wrote an entire post about it. The proposals don't address competitive moat building at all. OpenAI is curating financial modeling training data. This is the existential risk.
6. **The "Copilot workslop" scandal.** Peter references a viral Copilot screenshot showing catastrophic errors in financial models. The proposals mention "workslop" only in passing but should have weaponized this as social proof for why deterministic validation matters.

### Aleksander Misztal (CTO) — What Gemini Got Right
- Jane Street background correctly mapped to determinism, functional safety, and performance engineering.
- ZK-crypto background at Nethermind correctly mapped to privacy-preservation and formal verification preferences.
- He's quiet. Mostly reposts Peter's content. He "thinks in beautiful systems" (Peter's words). Proposals must be architecturally elegant, not just feature-rich.

### Aleksander Misztal — What Gemini Missed
1. **He ran 100-mile ultramarathons.** This isn't trivia — it maps to extreme patience and endurance mindset. He won't be impressed by flashy demos that collapse under pressure. The demo must be stress-testable.
2. **The Sigma Squared Society fellowship** signals he's networked in the elite founder ecosystem. He'll pattern-match proposals against what other top-tier startups are doing.
3. **His "About" section says "coding agents."** Not "AI assistant," not "copilot" — *coding agents*. He frames Tracelight as an autonomous agent that writes code (formulas). The proposals should speak in agent terminology, not assistant terminology.

### Janek Zimoch (CPO) — What Gemini Got Right
- 11x.ai scaling experience correctly identified. He built multi-agent outbound pipelines.
- Cambridge ML background correctly mapped.
- Standard Chartered quant background correctly identified.

### Janek Zimoch — What Gemini Missed
1. **He was the 3rd engineer at 11x.ai and scaled it from $100k to $1M ARR.** This means he's seen hypergrowth before and knows what product decisions drive ARR. He'll evaluate proposals through a "does this move the revenue needle?" lens, not a "is this technically interesting?" lens.
2. **He maintains a precise watering schedule for office plants and sends 2 AM messages about marginal prompt gains.** (Peter's words.) He is pathologically detail-oriented. Any demo with sloppy edge cases or unhandled states will lose him instantly.
3. **He built the personalization module at 11x.** This is directly relevant — he knows multi-agent orchestration from the inside. He'll immediately spot if the agent routing is cargo-culted versus genuinely necessary.

### Macro/Operational Threats Gemini Failed to Exploit
- **JP Morgan reducing junior analysts by a third.** Peter wrote about this. The "human + AI" augmentation narrative is a massive wedge for selling Safe-Harbor to enterprise.
- **Consulting market growing 7% in 2026 (FT forecast).** This is a tailwind. More consulting spend = more Excel models = more Tracelight demand = more need for frictionless onboarding.
- **The "80/2 rule."** Peter coined this — AI compresses the 80/20 rule. Deep Research can do in 5 minutes what took him 2 weeks at McKinsey. This reframes the value prop: Safe-Harbor isn't just about testing, it's about demonstrating the "80/2" moment to prospects.

---

# TASK 2: THE EGO CHECK

## Proposal 1: Safe-Harbor Synthetic Financial Data Fabric
**VERDICT: PASSES. Clean pre-core sidecar.**
- Generates synthetic data to populate empty model templates.
- Does NOT touch the DAG engine, formula generation, or model-building logic.
- Operates purely upstream — fills the input, then hands off to core.
- No overlap with any shipped or announced Tracelight feature.

## Proposal 2: QuantumBlack-Grade IC Memo Synthesizer
**VERDICT: KILLED. Fatally close to core IP.**
- Tracelight *already ships* the ability to turn spreadsheets into "beautiful, shareable webpages" (Peter, 2 weeks ago).
- The "State Observer Agent" that reads finalized DAG nodes is literally interfacing with their proprietary graph engine. Their engineers are building this natively.
- Peter announced they're "adding chat and native citation to the underlying Excel" in the coming days. This IS the IC Memo Synthesizer, built by their own team.
- Pitching this would trigger an immediate "we're already building this" response and destroy credibility.
- **KILL IT.**

## Proposal 3: Shield-Wall Autonomous InfoSec Responder
**VERDICT: PASSES WITH CAVEATS.**
- Air-gapped, internal-only tool. Does not touch core IP.
- BUT: Tracelight is already SOC 2 Type 2 certified and is signing 5 of the top 10 consultancies. The questionnaire bottleneck may not be as severe as the proposal assumes.
- The real bottleneck Peter describes is the *client's* internal approval process, not Tracelight's ability to answer questionnaires. Peter's advice is aimed at the *buyer* ("Invest in a testing set-up").
- Still useful but lower-impact than Safe-Harbor. It's an ops efficiency tool, not a revenue accelerator.
- **SURVIVES but is the weaker candidate.**

---

# TASK 3: THE 5-PILLAR AUDIT

## Surviving Candidates: Safe-Harbor vs. Shield-Wall

### Pillar 1: Does it solve a REAL bottleneck?

| | Safe-Harbor | Shield-Wall |
|---|---|---|
| Evidence | Peter explicitly says "Invest in a testing set-up" with non-sensitive data. This is his #1 piece of advice for accelerating procurement. | They're already SOC 2 Type 2 certified. Already closing tier-1 firms. Questionnaire speed is a nice-to-have, not a blocker. |
| **Score** | **10/10** | **5/10** |

### Pillar 2: Is the UI in a native environment?

| | Safe-Harbor | Shield-Wall |
|---|---|---|
| Native? | Embedded in the Tracelight trial onboarding flow. The prospect never leaves the Tracelight ecosystem. | Internal ops tool for the sales/legal team. Doesn't face the customer. |
| **Score** | **9/10** | **7/10** |

### Pillar 3: Is there a clear "Magic Moment"?

| | Safe-Harbor | Shield-Wall |
|---|---|---|
| Magic Moment | Prospect uploads an empty LBO shell → watches synthetic data waterfall into the grid → sees a green "Mathematically Verified" badge → immediately starts testing Tracelight's core features. This is the "80/2 moment" Peter describes. | Sales team uploads a 300-question vendor assessment → watches it auto-populate. Satisfying but not customer-facing. |
| **Score** | **10/10** | **6/10** |

### Pillar 4: Does it feature self-healing/resilient architecture?

| | Safe-Harbor | Shield-Wall |
|---|---|---|
| Self-Healing | Deterministic Validation Agent catches GAN errors and force-corrects via plug accounts. System literally cannot output a broken balance sheet. | Drift detection (telemetry vs. policy contradiction) is a genuine self-healing mechanism. |
| **Score** | **9/10** | **8/10** |

### Pillar 5: Clear ROI / Business Case?

| | Safe-Harbor | Shield-Wall |
|---|---|---|
| ROI | Directly compresses enterprise sales cycle by eliminating the #1 blocker Peter identifies. Every deal that closes 2 months faster is revenue pulled forward. | Saves the sales team 5-10 hours per questionnaire. Useful but not transformative. |
| **Score** | **10/10** | **5/10** |

### TOTAL SCORES
- **Safe-Harbor: 48/50** — Dominant winner.
- **Shield-Wall: 31/50** — Useful internal tool, not a demo centerpiece.

---

# TASK 4: THE FINAL VERDICT

## Winner: The Safe-Harbor Synthetic Financial Data Fabric

### Refined Architecture — Critical Changes from Gemini's Proposal

**Problem 1: The GAN/Diffusion model is over-engineered for a 72-hour sprint.**
Training or fine-tuning a Tabular GAN (CTGAN, FairFinGAN) requires significant data curation, compute, and iteration. This is a multi-week ML project, not a demo feature.

**Fix:** Replace the GAN with GPT-4o Structured Outputs. GPT-4o can generate realistic financial time-series data when given a strict JSON schema and industry-specific constraints. The deterministic validation layer catches any statistical outliers. This is buildable in hours, not weeks.

**Problem 2: Gemini's proposal uses Claude/AWS Bedrock. The SOP restricts routing to OpenAI/Google.**
The entire agent routing must be remapped.

**Fix:** 
- Schema Extraction Agent → **Gemini 2.0 Flash** (Google Vertex AI). Long context window is ideal for ingesting full Excel template structures. Fast. Cheap.
- Synthetic Generation Agent → **GPT-4o Structured Outputs** (OpenAI). Best-in-class for producing validated JSON conforming to a strict schema. Temperature 0.3 for controlled variation.
- Deterministic Validation Agent → **Pure Python (Pandas/NumPy).** Not an LLM. Hardcoded algebraic assertions. This is the trust anchor of the entire system.
- Orchestrator → **GPT-4o** (OpenAI). Manages the pipeline, handles retries, formats final output.

**Problem 3: The "magic moment" needs to be weaponized harder.**
The current proposal describes a "data generation terminal." This is too generic. It needs to feel like the prospect is watching an AI analyst build their model in real-time.

**Fix:** The UI should show a three-phase animation: (1) Schema Scan — visual DAG of the empty template's structure, nodes lighting up as the agent maps them. (2) Data Waterfall — numbers cascading into cells, row by row, with each cell briefly flashing green as it passes validation. (3) The Verdict — a full-screen badge: "✓ BALANCE SHEET BALANCED. ✓ CASH FLOW RECONCILED. ✓ READY FOR TESTING." Then the prospect clicks one button and enters Tracelight's core product with a fully populated model.

---

# TASK 5: THE MASTER PRD

```markdown
# ═══════════════════════════════════════════════════════════
# MASTER PRD: SAFE-HARBOR SYNTHETIC FINANCIAL DATA FABRIC
# Target: Tracelight (tracelight.ai)
# Classification: Pre-Core Sidecar Architecture
# Sprint Window: 72 Hours
# ═══════════════════════════════════════════════════════════

## 1. THE FDE THESIS

### How This Hits the 5-Pillar Standard

PILLAR 1 — REAL BOTTLENECK:
Tracelight's CEO publicly states that InfoSec data restrictions are the
#1 blocker to enterprise sales velocity. His exact advice to prospects:
"Invest in a testing set-up. Create non-sensitive test data for use cases
you care about." Safe-Harbor automates this advice INTO the product.
Instead of telling prospects to solve their own testing problem, Tracelight
solves it for them in 30 seconds.

PILLAR 2 — NATIVE ENVIRONMENT:
The Safe-Harbor engine is embedded directly in Tracelight's trial
onboarding portal. The prospect never leaves the ecosystem. The UI
matches Tracelight's existing design language (React + Tailwind). It
feels like a native feature, not a bolted-on demo.

PILLAR 3 — MAGIC MOMENT:
The prospect uploads an empty LBO/DCF shell template (headers only,
all sensitive data stripped). In under 30 seconds, they watch synthetic
financial data cascade into every cell — revenue tranches, debt
schedules, depreciation — while a live validation ticker confirms
mathematical integrity. The balance sheet balances. The cash flow
reconciles. They click "Start Testing" and enter Tracelight's core
product with a model that FEELS real but contains zero sensitive data.

PILLAR 4 — SELF-HEALING:
The Deterministic Validation Agent is a hardcoded Python rules engine.
It enforces: Assets = Liabilities + Equity (zero tolerance). EBITDA
margins bounded by industry standard deviations. Depreciation <=
CapEx. If GPT-4o generates a number that breaks a constraint, the
Validation Agent calculates the exact delta and adjusts a designated
plug account (Cash or Retained Earnings) to force equilibrium. The
system CANNOT output a broken model.

PILLAR 5 — CLEAR ROI:
Every enterprise deal that closes 8 weeks faster because the prospect
could test immediately = revenue pulled forward by 2 months. For a
startup at Tracelight's stage (post-seed, signing tier-1 institutions),
this directly impacts runway, ARR growth, and Series A positioning.

---

## 2. SYSTEM ARCHITECTURE & AGENT ROUTING

### Data Flow (End-to-End)

```
[PROSPECT ACTION]
     │
     ▼
┌─────────────────────────┐
│ 1. UPLOAD EMPTY TEMPLATE │ ← Excel file with headers only,
│    (LBO/DCF/3-Statement) │   all sensitive data stripped
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR (GPT-4o, OpenAI API)            │
│    - Receives the .xlsx file                    │
│    - Dispatches agents in sequence              │
│    - Manages retries on validation failure      │
│    - Max 3 retry loops before human escalation  │
└───────────┬─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 3. SCHEMA EXTRACTION AGENT (Gemini 2.0 Flash)   │
│    via Google Vertex AI                          │
│                                                  │
│    INPUT:  Raw .xlsx bytes (openpyxl parsed to   │
│            JSON: sheet names, headers, cell      │
│            positions, formula patterns,          │
│            named ranges)                         │
│                                                  │
│    PROCESS:                                      │
│    - Maps every column header to a financial     │
│      data type (revenue, COGS, EBITDA, debt      │
│      tranche, CapEx, depreciation, etc.)         │
│    - Identifies temporal structure (e.g.,         │
│      FY2020-FY2025 historicals, FY2026-FY2030    │
│      projections)                                │
│    - Detects inter-sheet references (e.g.,       │
│      P&L feeds into CF, CF feeds into BS)        │
│    - Identifies formula patterns to understand   │
│      which cells are inputs vs. calculated       │
│                                                  │
│    OUTPUT: Strict JSON schema:                   │
│    {                                             │
│      "model_type": "LBO" | "DCF" | "3-stmt",    │
│      "sheets": [                                 │
│        {                                         │
│          "name": "Income Statement",             │
│          "columns": [                            │
│            {                                     │
│              "header": "Revenue",                │
│              "data_type": "currency_USD",        │
│              "temporal_range": "FY2020-FY2025",  │
│              "is_input": true,                   │
│              "constraints": {                    │
│                "min": 0,                         │
│                "growth_rate_range": [-0.1, 0.3]  │
│              }                                   │
│            }                                     │
│          ],                                      │
│          "inter_sheet_refs": [                    │
│            "Net Income → CF.Net_Income",         │
│            "Total Assets → BS.Total_Assets"      │
│          ]                                       │
│        }                                         │
│      ],                                          │
│      "industry": "Healthcare SaaS",              │
│      "currency": "USD"                           │
│    }                                             │
│                                                  │
│    WHY GEMINI: Long context window handles full  │
│    workbook structures. Fast inference. Cheap.    │
│    Schema extraction is a comprehension task,    │
│    not a generation task — Gemini excels here.   │
└───────────┬─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 4. SYNTHETIC GENERATION AGENT (GPT-4o)           │
│    via OpenAI API — Structured Outputs mode       │
│                                                   │
│    INPUT:  JSON schema from Step 3                │
│                                                   │
│    SYSTEM PROMPT CONSTRAINTS:                     │
│    - Temperature: 0.3 (controlled variation)      │
│    - "You are a financial data generator.          │
│      Generate realistic synthetic data for a      │
│      {model_type} model in the {industry}         │
│      sector. All numbers must be internally       │
│      consistent. Revenue must show realistic      │
│      growth patterns. Cost ratios must be         │
│      industry-appropriate. Debt schedules must    │
│      amortize correctly. DO NOT generate random   │
│      numbers. Generate numbers that tell a        │
│      coherent business story."                    │
│    - response_format enforces the exact JSON      │
│      schema output                                │
│                                                   │
│    OUTPUT: Populated JSON matching the schema     │
│    with synthetic values for every input cell.    │
│                                                   │
│    WHY GPT-4o: Best-in-class structured output    │
│    compliance. Temperature control allows         │
│    realistic variation without chaos. Financial   │
│    training data means it understands what a      │
│    "realistic" SaaS revenue curve looks like.     │
└───────────┬───────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 5. DETERMINISTIC VALIDATION AGENT                │
│    Pure Python — NOT an LLM                      │
│                                                  │
│    INPUT:  Populated JSON from Step 4            │
│                                                  │
│    HARDCODED RULES (zero tolerance):             │
│                                                  │
│    RULE 1 — Balance Sheet Identity:              │
│      assert Total_Assets ==                      │
│             Total_Liabilities + Total_Equity     │
│      Tolerance: 0.00 (exact match)               │
│                                                  │
│    RULE 2 — Cash Flow Reconciliation:            │
│      assert Ending_Cash ==                       │
│             Beginning_Cash + Net_CF              │
│      For each period.                            │
│                                                  │
│    RULE 3 — Net Income Linkage:                  │
│      assert PL.Net_Income == CF.Net_Income       │
│      assert PL.Net_Income feeds into             │
│             BS.Retained_Earnings_Delta           │
│                                                  │
│    RULE 4 — Margin Bounds:                       │
│      assert 0 < Gross_Margin < 1                 │
│      assert EBITDA_Margin within [-0.5, 0.8]     │
│      (industry-adjusted bounds from schema)       │
│                                                  │
│    RULE 5 — Depreciation Constraint:             │
│      assert cumulative Depreciation <=           │
│             cumulative CapEx + Opening_PP&E      │
│                                                  │
│    RULE 6 — Debt Schedule Integrity:             │
│      assert Ending_Debt ==                       │
│             Beginning_Debt + Drawdowns           │
│             - Repayments                         │
│      For each tranche, each period.              │
│                                                  │
│    ON FAILURE:                                   │
│    - Calculate exact delta                       │
│    - Adjust designated plug account:             │
│      * For BS imbalance → adjust Cash            │
│      * For CF mismatch → adjust Other_CF_Items   │
│      * For margin violation → regenerate that    │
│        line item (retry to GPT-4o, max 3x)       │
│    - Log every adjustment for the audit trail    │
│                                                  │
│    OUTPUT: Validated JSON + Audit Log            │
│    {                                             │
│      "status": "PASSED" | "PASSED_WITH_PLUGS",   │
│      "adjustments": [...],                       │
│      "validation_timestamp": "ISO-8601"          │
│    }                                             │
└───────────┬─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 6. EXCEL WRITER (openpyxl)                       │
│    Pure Python — NOT an LLM                      │
│                                                  │
│    - Takes validated JSON + original template    │
│    - Writes synthetic values into the exact      │
│      cells mapped by the Schema Agent            │
│    - Preserves all formulas, formatting,         │
│      named ranges, and sheet structure           │
│    - Outputs a complete .xlsx ready for upload   │
│      to Tracelight's core product                │
└───────────┬─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────┐
│ 7. DELIVERY TO PROSPECT                          │
│    - Populated .xlsx available for download      │
│    - OR injected directly into Tracelight's      │
│      trial environment via API                   │
│    - Prospect clicks "Start Testing" →           │
│      enters core Tracelight product with a       │
│      fully populated, mathematically verified    │
│      model containing ZERO sensitive data        │
└─────────────────────────────────────────────────┘
```

### Agent Routing Summary Table

| Agent | Model | Provider | Why This Model |
|-------|-------|----------|----------------|
| Orchestrator | GPT-4o | OpenAI | Reliable function-calling, manages retry logic |
| Schema Extraction | Gemini 2.0 Flash | Google Vertex AI | Long context for full workbook parsing, fast, cheap |
| Synthetic Generation | GPT-4o (Structured Outputs) | OpenAI | Best structured output compliance, financial data understanding |
| Deterministic Validation | Python (Pandas/NumPy) | N/A — No LLM | Trust anchor. Hardcoded rules. Zero hallucination risk. |
| Excel Writer | Python (openpyxl) | N/A — No LLM | Deterministic file manipulation. |

### Model Restriction Compliance
- OpenAI: GPT-4o (Orchestrator + Synthetic Generation)
- Google: Gemini 2.0 Flash (Schema Extraction)
- No Anthropic/Claude models used.
- No AWS Bedrock dependency.

---

## 3. THE "NATIVE ENVIRONMENT" UI SPEC

### Design Principles
- Embedded within Tracelight's existing trial onboarding portal.
- React + Tailwind CSS. Must match Tracelight's existing design system
  (dark UI, clean typography, green accent for success states).
- No separate app. No new URL. The prospect stays inside Tracelight.

### Screen 1: Template Upload
- Full-width drop zone: "Drop your empty model template here"
- Subtext: "Strip all sensitive data first. Keep headers, formulas,
  and structure. We'll do the rest."
- Supported formats badge: .xlsx, .xlsm
- "Or choose a sample template" → pre-built LBO, DCF, 3-Statement
  templates for prospects who don't have one handy.
- File size limit: 25MB
- Error state: "This file contains data in input cells. Please upload
  an empty template with headers only."

### Screen 2: Schema Analysis (The "Detective" Phase)
- Split-screen layout:
  - LEFT: Miniature Excel grid preview showing the uploaded template
    structure with empty cells highlighted.
  - RIGHT: Live terminal feed showing the Schema Agent's work:
    ```
    [SCAN] Detecting sheets... 4 found
    [MAP]  Income Statement → 23 columns mapped
    [MAP]  Balance Sheet → 31 columns mapped  
    [MAP]  Cash Flow → 18 columns mapped
    [MAP]  Debt Schedule → 12 columns mapped
    [LINK] P&L.Net_Income → CF.Net_Income ✓
    [LINK] CF.Ending_Cash → BS.Cash ✓
    [TYPE] Model classified as: Leveraged Buyout
    [DONE] Schema extraction complete. 84 input cells identified.
    ```
  - Animated DAG visualization: Nodes for each sheet, edges for
    inter-sheet references, pulsing as they're discovered.
  - Duration: ~5-8 seconds.

### Screen 3: Data Generation (The "Waterfall" Phase)
- Full-width Excel-like grid view.
- Numbers cascade into cells row by row, sheet by sheet.
- Each cell briefly flashes AMBER as it's written, then GREEN as the
  Validation Agent confirms it.
- Bottom ticker: "Generating 5-year historicals for Healthcare SaaS..."
- Real-time validation badges appearing as constraints pass:
  ```
  ✓ Balance Sheet Balanced (Year 1)
  ✓ Balance Sheet Balanced (Year 2)
  ✓ Cash Flow Reconciled (Year 1)
  ✓ Debt Schedule Verified
  ...
  ```
- If a plug adjustment occurs, show it transparently:
  ```
  ⚡ Adjusted Cash by +$142K to force BS equilibrium (Year 3)
  ```
  This BUILDS trust. It shows the system is honest about corrections,
  not hiding them.
- Duration: ~15-25 seconds.

### Screen 4: The Verdict (The "Magic Moment")
- Full-screen modal with large badge:
  ```
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓  SYNTHETIC MODEL VERIFIED
  
  ✓  Balance Sheet Balanced (all 5 years)
  ✓  Cash Flow Reconciled (all 5 years)
  ✓  Debt Schedule Amortized Correctly
  ✓  Margins Within Industry Bounds
  ✓  Zero Sensitive Data
  
  Model Type:    Leveraged Buyout
  Industry:      Healthcare SaaS
  Time Horizon:  FY2020 – FY2030
  Input Cells:   84 populated
  Validation:    6/6 rules passed
  
  [Download .xlsx]     [▶ START TESTING IN TRACELIGHT]
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ```
- The "START TESTING" button is the primary CTA. It loads the populated
  model directly into Tracelight's core Excel add-in environment.
- The prospect is now using Tracelight's real product with a model
  that feels real but triggers zero InfoSec concerns.

### Screen 5: Audit Trail (For the CTO)
- Expandable panel showing:
  - Full JSON schema extracted in Step 3
  - Every synthetic value generated with its constraint bounds
  - Every validation rule result
  - Every plug adjustment with the exact delta
  - Timestamps for each agent's execution
  - Model/token usage breakdown
- This is built specifically for Aleksander. He will click this.
  If it's not there, he won't trust the system.

---

## 4. PHASE 1 EXECUTION SPEC

### Prerequisites
```
Runtime:     Python 3.12+
Framework:   FastAPI (async)
Frontend:    React 18 + Vite + Tailwind CSS
Deployment:  Google Cloud Run (backend), Netlify (frontend)
API Keys:    OpenAI API key, Google Vertex AI credentials
Libraries:   openpyxl, pandas, numpy, pydantic, uvicorn
```

### Directory Structure
```
safe-harbor/
├── backend/
│   ├── main.py                  # FastAPI app + WebSocket endpoint
│   ├── orchestrator.py          # GPT-4o orchestration logic
│   ├── agents/
│   │   ├── schema_extractor.py  # Gemini 2.0 Flash agent
│   │   ├── synthetic_gen.py     # GPT-4o Structured Outputs agent
│   │   └── validator.py         # Pure Python validation engine
│   ├── excel_io/
│   │   ├── parser.py            # openpyxl template reader
│   │   └── writer.py            # openpyxl synthetic data writer
│   ├── models/
│   │   └── schemas.py           # Pydantic models for all data contracts
│   └── config.py                # API keys, model configs, constraints
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── UploadZone.jsx
│   │   │   ├── SchemaTerminal.jsx
│   │   │   ├── DataWaterfall.jsx
│   │   │   ├── VerdictBadge.jsx
│   │   │   └── AuditTrail.jsx
│   │   └── hooks/
│   │       └── useWebSocket.js
│   └── tailwind.config.js
├── templates/                   # Pre-built sample templates
│   ├── lbo_template.xlsx
│   ├── dcf_template.xlsx
│   └── three_statement_template.xlsx
├── Dockerfile
└── README.md
```

### Step-by-Step Build Order

STEP 1 — Data Contracts (Hour 0-2)
- Define Pydantic models in schemas.py:
  - TemplateSchema: the JSON output of the Schema Extraction Agent
  - SyntheticPayload: the JSON output of the Synthetic Generation Agent
  - ValidationResult: the output of the Validation Agent
  - AuditLogEntry: timestamps, adjustments, rule results
- These are the single source of truth. Every agent reads/writes
  these models. No ad-hoc JSON.

STEP 2 — Excel Parser (Hour 2-6)
- Build parser.py using openpyxl:
  - Read all sheet names, headers, cell positions
  - Detect formula cells vs. input cells (formula cells start with "=")
  - Extract named ranges
  - Detect inter-sheet references by parsing formula strings
  - Output a JSON representation of the template structure
- Build writer.py:
  - Accept validated SyntheticPayload + original template path
  - Write values into input cells only (never overwrite formulas)
  - Save as new .xlsx file
- TEST: Upload a sample LBO template, verify parser extracts all
  headers correctly, verify writer can populate and save.

STEP 3 — Deterministic Validation Agent (Hour 6-12)
- Build validator.py as a pure Python class:
  - Method: validate(payload: SyntheticPayload) → ValidationResult
  - Implement all 6 hardcoded rules (see architecture above)
  - Implement plug-account adjustment logic
  - Implement retry signal (returns which line items need regeneration)
- TEST: Feed it deliberately broken data (BS doesn't balance,
  negative margins, depreciation > CapEx). Verify it catches every
  violation and produces correct plug adjustments.
- This is the trust anchor. It must be bulletproof before proceeding.

STEP 4 — Schema Extraction Agent (Hour 12-18)
- Build schema_extractor.py:
  - Takes parsed Excel JSON from parser.py
  - Sends to Gemini 2.0 Flash via Vertex AI
  - System prompt: "You are a financial model analyst. Given the
    following Excel template structure, classify each column by its
    financial data type, identify temporal ranges, detect inter-sheet
    dependencies, and classify the model type. Output strict JSON
    conforming to the TemplateSchema."
  - Parse response into TemplateSchema Pydantic model
- Fallback: If Gemini fails or returns malformed JSON, retry 2x.
  If still failing, fall back to GPT-4o for schema extraction.
- TEST: Run against LBO, DCF, and 3-Statement templates. Verify
  correct classification of every column.

STEP 5 — Synthetic Generation Agent (Hour 18-26)
- Build synthetic_gen.py:
  - Takes TemplateSchema from Step 4
  - Sends to GPT-4o with Structured Outputs mode
  - response_format enforces SyntheticPayload schema
  - System prompt includes industry-specific constraints from schema
  - Temperature: 0.3
- Chain: Generate → Validate → If validation fails, send failure
  details back to GPT-4o with instruction to regenerate specific
  line items → Re-validate → Max 3 loops
- TEST: Generate synthetic data for each template type. Verify
  the Validation Agent passes on first or second attempt.

STEP 6 — Orchestrator (Hour 26-32)
- Build orchestrator.py:
  - Receives uploaded .xlsx via FastAPI endpoint
  - Executes pipeline: Parse → Schema Extract → Generate → Validate → Write
  - WebSocket connection to frontend for real-time progress updates
  - Sends structured events: {"phase": "schema", "detail": "Mapping Income Statement..."}
  - Error handling: timeout after 60 seconds, graceful degradation
- Build main.py:
  - POST /api/upload — receives .xlsx, returns job_id
  - WS /ws/{job_id} — streams progress events to frontend
  - GET /api/download/{job_id} — returns populated .xlsx

STEP 7 — Frontend (Hour 32-48)
- Build React components in order:
  1. UploadZone.jsx — drag-and-drop with sample template buttons
  2. SchemaTerminal.jsx — terminal-style feed consuming WS events
  3. DataWaterfall.jsx — grid visualization with cell-by-cell animation
  4. VerdictBadge.jsx — full-screen validation summary
  5. AuditTrail.jsx — expandable JSON inspector for the CTO
- useWebSocket.js hook manages the WS connection and event routing
- Tailwind config matches Tracelight's dark UI aesthetic

STEP 8 — Integration & Polish (Hour 48-60)
- End-to-end testing with all three template types
- Error state handling (corrupt files, empty files, files with data)
- Loading states and animations
- Mobile responsiveness (prospects may demo on tablets)
- Cost tracking: log API costs per generation for the demo

STEP 9 — Demo Prep (Hour 60-72)
- Record a 90-second demo video of the full flow
- Prepare three pre-loaded scenarios:
  1. PE Associate uploads empty LBO shell → instant testing
  2. Consulting Analyst uploads empty 3-Statement → instant testing
  3. Asset Manager uploads empty DCF → instant testing
- Prepare the "Peter pitch": "Your prospects tell you InfoSec needs
  3 months. With Safe-Harbor, they test in 30 seconds. Zero sensitive
  data. Mathematically verified. Your sales cycle just got 8 weeks
  shorter."
- Prepare the "Aleks deep-dive": Full audit trail walkthrough showing
  every validation rule, every plug adjustment, every JSON payload.
- Prepare the "Janek product angle": Show how Safe-Harbor eliminates
  user friction — no prompting, no configuration, just upload and go.

### API Cost Estimate (Per Generation)
| Agent | Model | Est. Tokens | Est. Cost |
|-------|-------|-------------|-----------|
| Schema Extraction | Gemini 2.0 Flash | ~4,000 in / ~2,000 out | ~$0.002 |
| Synthetic Generation | GPT-4o | ~3,000 in / ~5,000 out | ~$0.04 |
| Orchestrator overhead | GPT-4o | ~1,000 in / ~500 out | ~$0.01 |
| Validation retries (avg 1.5x) | GPT-4o | ~2,000 in / ~3,000 out | ~$0.03 |
| **TOTAL PER GENERATION** | | | **~$0.08** |

This is the kill number. When Peter asks "how much does this cost?",
the answer is "eight cents per synthetic model." That's the closer.
```

---

## APPENDIX: PROPOSALS KILLED & WHY

### KILLED: IC Memo Synthesizer
- Tracelight already ships spreadsheet-to-webpage conversion (2 weeks ago).
- The "State Observer Agent" touches the proprietary DAG engine — core IP violation.
- Peter announced adding "chat and native citation to underlying Excel" — they're building this natively.
- Pitching this would signal ignorance of their product roadmap and destroy credibility.

### DEMOTED: Shield-Wall InfoSec Responder
- Tracelight is already SOC 2 Type 2 certified.
- Already closing 5 of top 10 consultancies. Questionnaire speed is not the binding constraint.
- Peter's advice about procurement friction is directed at the BUYER's internal process, not Tracelight's ability to respond.
- Useful as a Phase 2 internal ops tool, not a demo centerpiece.

---

*End of Master PRD.*
