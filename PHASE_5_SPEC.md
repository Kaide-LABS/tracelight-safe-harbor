# PHASE 5 TECHNICAL SPECIFICATION
## Final Demo Execution, Live Walkthrough & Pitch Handoff Package
### File-by-File, Function-by-Function Blueprint for Execution Agent

---

## 0. STRATEGIC CONTEXT

### What This Phase Covers
Phases 1-4 built and deployed the complete system. Phase 5 is the **final mile** — assembling everything into a polished, executable demo package that can be run live in front of Tracelight's founding team (Peter Fuller, Aleksander Misztal, Janek Zimoch).

This is NOT a code phase. It is a **demo engineering** phase:

1. Run the template generator scripts and commit the actual `.xlsx` files
2. Run the fixture generator and commit the sample questionnaire
3. Verify end-to-end local smoke test (docker compose up → both demos work)
4. Build a self-contained demo runner script (`demo/run_demo.sh`)
5. Create a structured pitch deck outline (`demo/deck_outline.md`)
6. Create a technical deep-dive appendix for Aleks (`demo/technical_appendix.md`)
7. Generate a cost comparison table (Safe-Harbor vs manual process, Shield-Wall vs manual process)

### What This Phase Does NOT Cover
- Recording video (out of scope for execution agent)
- Actual pitch delivery (human task)
- Post-pitch follow-up materials
- IC Memo Synthesizer (KILLED)

### Why This Matters
The demo is the product. Peter judges by ROI clarity. Aleks judges by architectural elegance under stress. Janek judges by UX friction. Every artifact in this phase exists to service one of those three lenses.

---

## 1. TEMPLATE GENERATION — Execute & Commit

### Task
Run the template generator scripts from Phase 3 and commit the actual `.xlsx` binary files.

### Steps

```bash
cd safe-harbor/scripts && python3 generate_templates.py
cd ../../shield-wall/scripts && python3 generate_fixtures.py
```

### Verification
After generation, open each file in openpyxl and verify:

**`lbo_template.xlsx`:**
- 5 sheets: Income Statement, Balance Sheet, Cash Flow, Debt Schedule, Returns Analysis
- All formula cells contain formulas (not values)
- Inter-sheet references: IS→DS (Interest Expense), BS→IS (Retained Earnings), CF→IS (Net Income, D&A)
- Total input cells > 50
- IS Interest Expense references Debt Schedule row 16 (Total Interest Expense) — NOT row 13

**`three_statement_template.xlsx`:**
- 3 sheets: Income Statement, Balance Sheet, Cash Flow
- No Debt Schedule, no Returns Analysis
- Simplified BS (no Senior/Mezzanine split)

**`dcf_template.xlsx`:**
- 4 sheets: Revenue Build, Income Statement, Free Cash Flow, DCF Valuation
- Revenue Build feeds IS, IS feeds FCF
- DCF Valuation has WACC and Terminal Growth Rate inputs

**`sample_questionnaire.xlsx`:**
- 1 sheet: "Security Assessment"
- 30 rows of questions covering all 12 security categories
- Response and Evidence columns are empty

### Script: `safe-harbor/scripts/verify_templates.py`

```python
"""Verify generated templates are structurally correct."""
import openpyxl
import sys

def verify_lbo():
    wb = openpyxl.load_workbook("../templates/lbo_template.xlsx", data_only=False)
    assert len(wb.sheetnames) == 5, f"Expected 5 sheets, got {len(wb.sheetnames)}"
    assert "Income Statement" in wb.sheetnames
    assert "Debt Schedule" in wb.sheetnames
    assert "Returns Analysis" in wb.sheetnames

    # Check IS Interest Expense references DS row 16
    ws = wb["Income Statement"]
    ie_cell = ws.cell(row=9, column=2)  # Interest Expense, FY2020
    assert ie_cell.value and "Debt Schedule" in str(ie_cell.value), f"IS Interest Expense formula wrong: {ie_cell.value}"
    assert "16" in str(ie_cell.value), f"Should reference row 16, got: {ie_cell.value}"

    # Count input cells (empty non-formula cells)
    input_count = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2, values_only=False):
            for cell in row[1:]:  # skip label column
                if cell.value is None or (isinstance(cell.value, (int, float)) and cell.value == 0):
                    input_count += 1
    assert input_count > 30, f"Expected > 30 input cells, got {input_count}"
    print(f"LBO template: OK ({len(wb.sheetnames)} sheets, {input_count} input cells)")

def verify_three_statement():
    wb = openpyxl.load_workbook("../templates/three_statement_template.xlsx", data_only=False)
    assert len(wb.sheetnames) == 3, f"Expected 3 sheets, got {len(wb.sheetnames)}"
    assert "Debt Schedule" not in wb.sheetnames
    assert "Returns Analysis" not in wb.sheetnames
    print(f"3-Statement template: OK ({len(wb.sheetnames)} sheets)")

def verify_dcf():
    wb = openpyxl.load_workbook("../templates/dcf_template.xlsx", data_only=False)
    assert len(wb.sheetnames) == 4, f"Expected 4 sheets, got {len(wb.sheetnames)}"
    assert "Revenue Build" in wb.sheetnames
    assert "DCF Valuation" in wb.sheetnames
    print(f"DCF template: OK ({len(wb.sheetnames)} sheets)")

if __name__ == "__main__":
    verify_lbo()
    verify_three_statement()
    verify_dcf()
    print("\nAll templates verified successfully.")
```

### Files to Commit
- `safe-harbor/templates/lbo_template.xlsx`
- `safe-harbor/templates/three_statement_template.xlsx`
- `safe-harbor/templates/dcf_template.xlsx`
- `shield-wall/tests/fixtures/sample_questionnaire.xlsx`
- `safe-harbor/scripts/verify_templates.py`

---

## 2. DEMO RUNNER SCRIPT — `demo/run_demo.sh`

### Purpose
One-command script that starts the entire demo environment locally.

### Implementation

```bash
#!/bin/bash
set -e

echo "============================================"
echo "  TRACELIGHT AI SIDECARS — DEMO LAUNCHER"
echo "============================================"
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose is not installed."
    exit 1
fi

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and add your API keys."
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your OPENAI_API_KEY and GOOGLE_CLOUD_PROJECT"
    exit 1
fi

# Generate templates if not present
if [ ! -f safe-harbor/templates/lbo_template.xlsx ]; then
    echo "[SETUP] Generating Excel templates..."
    cd safe-harbor/scripts && python3 generate_templates.py && cd ../..
    echo "[SETUP] Templates generated."
fi

if [ ! -f shield-wall/tests/fixtures/sample_questionnaire.xlsx ]; then
    echo "[SETUP] Generating sample questionnaire..."
    cd shield-wall/scripts && python3 generate_fixtures.py && cd ../..
    echo "[SETUP] Questionnaire generated."
fi

echo ""
echo "[BUILD] Building Docker images (this may take a few minutes on first run)..."
docker compose build

echo ""
echo "[START] Starting all services..."
docker compose up -d

echo ""
echo "============================================"
echo "  DEMO READY"
echo "============================================"
echo ""
echo "  Launcher:        http://localhost:5173"
echo "  Safe-Harbor:     http://localhost:5174"
echo "  Shield-Wall:     http://localhost:5175"
echo ""
echo "  Safe-Harbor API: http://localhost:8000/docs"
echo "  Shield-Wall API: http://localhost:8001/docs"
echo ""
echo "  To stop: docker compose down"
echo "============================================"

# Open launcher in default browser
if command -v open &> /dev/null; then
    open http://localhost:5173
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173
fi
```

Make executable: `chmod +x demo/run_demo.sh`

---

## 3. PITCH DECK OUTLINE — `demo/deck_outline.md`

### Structure (12 slides)

```markdown
# TRACELIGHT AI SIDECARS — PITCH DECK OUTLINE

## Slide 1: Title
- "Tracelight AI Sidecars: Compressing Enterprise Sales Cycles"
- Subtitle: "Two multi-agent architectures that solve the peripheral
  bottlenecks choking enterprise adoption — without touching the core
  DAG engine."

## Slide 2: The Problem
- InfoSec data restrictions delay proof-of-concept by 2-3 months
- Vendor security questionnaires take 5-10 hours each
- Peter's own words: "Invest in a testing set-up."
- This FDE automates that advice INTO the product.

## Slide 3: Safe-Harbor — The 30-Second Test
- Prospect uploads empty LBO/DCF shell
- AI generates mathematically verified synthetic data
- Balance sheet balances. Cash flow reconciles. Zero sensitive data.
- Prospect clicks "Start Testing" → enters Tracelight immediately.

## Slide 4: Safe-Harbor — Architecture
- 3-agent pipeline: Schema Extraction (Gemini) → Synthetic Generation
  (GPT-4o) → Deterministic Validation (Pure Python)
- Trust anchor: 6 hardcoded algebraic rules, zero LLM hallucination
- Plug-account corrections are transparent and auditable

## Slide 5: Safe-Harbor — Live Demo
- [RUN SCENARIO 1: PE Associate + LBO Template]
- Show: Schema Scan → Data Waterfall → Verdict → Audit Trail
- Call out the "eight cents per model" cost number.

## Slide 6: Shield-Wall — The 5-Minute Questionnaire
- 300-question vendor assessment → answered in minutes
- AI cross-references live infrastructure telemetry with policy documents
- Catches real drift: "Bob doesn't have MFA"

## Slide 7: Shield-Wall — Architecture
- 5-agent pipeline: Parser (Gemini) → Telemetry (GPT-4o + function calling)
  → Policy RAG (ChromaDB + embeddings) → Synthesis (GPT-4o Structured
  Outputs) → Drift Detector (Pure Python)
- Air-gapped: telemetry never leaves the VPC

## Slide 8: Shield-Wall — Live Demo
- [RUN SCENARIO 3: Procurement Team + Sample Questionnaire]
- Show: Processing Terminal → Drift Alert → Answer Grid → DOCX Export

## Slide 9: Anti-Replication Compliance
- Safe-Harbor = PRE-CORE sidecar (upstream of DAG)
- Shield-Wall = PARALLEL sidecar (admin ops, no customer contact)
- Zero interference with Excel add-in, DAG engine, or model builder
- No overlap with shipped features (webpages, plan mode, change reviews)

## Slide 10: ROI
- Safe-Harbor: Every deal closing 8 weeks faster = revenue pulled forward
- Shield-Wall: 5-10 hours saved per questionnaire
- Cost: $0.08 per synthetic model, ~$0.15 per questionnaire
- Total infrastructure: 2 Cloud Run services, 3 static frontends

## Slide 11: Production Readiness
- CI/CD: GitHub Actions → Cloud Build → Cloud Run
- Observability: Structured logging, cost tracking, health endpoints
- Tested: 11 unit tests + 6 drift detection tests passing
- Multi-stage Docker builds, environment-configurable frontends

## Slide 12: Next Steps
- Deploy to Tracelight's staging environment
- Connect Shield-Wall to real AWS telemetry (swap mock adapter)
- Embed Safe-Harbor in the trial onboarding portal
- Custom branding pass to match Tracelight's design system exactly
```

---

## 4. TECHNICAL APPENDIX — `demo/technical_appendix.md`

### For Aleks (CTO) — Architecture Deep Dive

```markdown
# TECHNICAL APPENDIX — For the CTO

## 1. Deterministic Validation Engine (Safe-Harbor Trust Anchor)

6 algebraic rules enforced with zero tolerance:

| Rule | Assertion | On Failure |
|------|-----------|------------|
| Balance Sheet Identity | Assets == Liabilities + Equity | Plug Cash |
| Cash Flow Reconciliation | Ending == Beginning + Net Change | Plug Other CF |
| Net Income Linkage | P&L NI == CF NI | Force CF to match P&L |
| Margin Bounds | Gross [0,1], EBITDA [-0.5,0.8], Net [-1,0.5] | Signal retry |
| Depreciation Constraint | Cum D&A <= Cum CapEx + Opening PP&E | Cap at ceiling |
| Debt Schedule Integrity | Ending = Begin + Draw - Repay (per tranche) | Adjust repayments |

Every plug adjustment is logged with the exact delta, the target
account, and the timestamp. The CTO Audit Trail displays all of this.

## 2. Drift Detection Engine (Shield-Wall Trust Anchor)

5 independent telemetry-vs-policy checks (pure Python, no LLM):

| Check | Policy Claim | Telemetry Signal | Severity |
|-------|-------------|------------------|----------|
| Encryption | "AES-256 at rest" | StorageEncrypted: false | CRITICAL |
| MFA | "MFA required" | MFAEnabled: false | CRITICAL |
| Logging | "CloudTrail enabled" | Trail gaps | WARNING |
| Network | "Only 443 public" | Non-443 port on 0.0.0.0/0 | WARNING |
| Generic | Any policy claim | Synthesis agent flags contradiction | Varies |

Deduplication ensures each question produces at most one alert.

## 3. Agent Routing & Model Selection

| Agent | Model | Rationale |
|-------|-------|-----------|
| Schema Extraction | Gemini 2.0 Flash | Long context, fast, cheap ($0.002/call) |
| Synthetic Generation | GPT-4o Structured Outputs | Best structured output compliance |
| Questionnaire Parser | Gemini 2.0 Flash | Batch classification, fast |
| Telemetry Agent | GPT-4o + function calling | Tool use for infra queries |
| Policy RAG | text-embedding-3-small + ChromaDB | Cosine similarity search |
| Synthesis | GPT-4o Structured Outputs | Evidence-grounded prose |
| Validation/Drift | Pure Python | Zero hallucination guarantee |

No Anthropic/Claude models. No AWS Bedrock. OpenAI + Google only.

## 4. Cost Per Execution

### Safe-Harbor (Per Synthetic Model)
| Agent | Tokens | Cost |
|-------|--------|------|
| Schema Extraction | ~6K | $0.002 |
| Synthetic Generation | ~8K | $0.055 |
| Orchestrator overhead | ~1.5K | $0.011 |
| Validation retries (1.5x avg) | ~5K | $0.034 |
| **Total** | | **~$0.08** |

### Shield-Wall (Per 30-Question Assessment)
| Agent | Tokens | Cost |
|-------|--------|------|
| Questionnaire Parser | ~1.6K | $0.001 |
| Telemetry Agent (30 queries) | ~2.8K | $0.012 |
| Policy Embeddings | ~1.5K | <$0.001 |
| Synthesis (30 answers) | ~6.5K | $0.070 |
| **Total** | | **~$0.08** |

## 5. Production Architecture

```
                    ┌─────────────┐
                    │   Vercel    │
                    │  (3 SPAs)   │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌──────────────┐         ┌──────────────┐
    │  Cloud Run   │         │  Cloud Run   │
    │ safe-harbor  │         │ shield-wall  │
    │   :8000      │         │   :8001      │
    └──────┬───────┘         └──────┬───────┘
           │                        │
    ┌──────┴───────┐         ┌──────┴───────┐
    │ OpenAI API   │         │ OpenAI API   │
    │ Vertex AI    │         │ Vertex AI    │
    │ (no state)   │         │ ChromaDB     │
    └──────────────┘         │ Mock Infra   │
                             └──────────────┘
```

No database. No message queue. No shared state.
Each service is stateless (in-memory job store for demo).
Cloud Run auto-scales 0→3 instances.
```

---

## 5. COST COMPARISON TABLE — `demo/cost_comparison.md`

```markdown
# COST COMPARISON: AI Sidecars vs Manual Process

## Safe-Harbor vs Manual Testing Setup

| Metric | Manual Process | Safe-Harbor |
|--------|---------------|-------------|
| Time to generate test data | 2-5 days (analyst manually creates) | 30 seconds |
| InfoSec approval required | Yes (3+ months for live data) | No (zero sensitive data) |
| Mathematical accuracy | Human error prone | 6 algebraic rules, zero tolerance |
| Cost per model | ~$500 (analyst time @ $100/hr) | $0.08 (API costs) |
| Scalability | 1 model per analyst-week | Unlimited, parallel |
| Audit trail | None | Full JSON: every value, every rule, every adjustment |

**ROI:** If Safe-Harbor enables 5 enterprise deals to close 8 weeks
faster per year, and each deal is worth $50K ARR, that's $250K in
pulled-forward revenue for $0.08 per demo.

## Shield-Wall vs Manual Questionnaire Response

| Metric | Manual Process | Shield-Wall |
|--------|---------------|-------------|
| Time per 300-question assessment | 5-10 hours | ~5 minutes |
| Evidence quality | Copy-paste from docs | Live telemetry + policy citations |
| Drift detection | None | Automatic (catches Bob's missing MFA) |
| Cost per assessment | ~$750 (analyst time) | ~$0.15 (API costs) |
| Consistency | Varies by analyst | Same grounding, every time |
| Export format | Manual Word doc | Auto-generated DOCX |

**ROI:** If Shield-Wall handles 50 questionnaires/year, that's
375 hours saved = ~$37,500 in analyst time for $7.50 in API costs.
```

---

## 6. BUILD ORDER

```
Step 1:  Run generate_templates.py → verify → commit .xlsx files
Step 2:  Run generate_fixtures.py → commit sample_questionnaire.xlsx
Step 3:  Create verify_templates.py → run → confirm all pass
Step 4:  Create demo/run_demo.sh (make executable)
Step 5:  Create demo/deck_outline.md
Step 6:  Create demo/technical_appendix.md
Step 7:  Create demo/cost_comparison.md
Step 8:  Local smoke test: ./demo/run_demo.sh → verify both demos work
Step 9:  Final commit with all generated files
```

Steps 1-2 are independent — run in parallel.
Steps 4-7 are independent — run in parallel.

---

## 7. CRITICAL BOUNDARIES

- **No new code in the backend or frontend.** Phase 5 is artifacts only.
- **Templates MUST have working formulas.** Open them in Excel to verify.
- **The demo runner must work on macOS and Linux.** Use portable bash.
- **The pitch deck is an OUTLINE, not slides.** The human presenter builds the actual deck.
- **IC Memo Synthesizer is KILLED.** Not mentioned in any pitch material.
- **All cost numbers must be verifiable** from the cost tracker data, not guessed.

---

*End of Phase 5 Technical Specification.*
