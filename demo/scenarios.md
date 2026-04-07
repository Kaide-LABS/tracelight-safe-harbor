# TRACELIGHT — FDE DEMO SCENARIOS

## Scenario 1: "The PE Associate" (Safe-Harbor)
**Target Profile:** Bain Capital / KKR Private Equity Associate
**The Block:** InfoSec says "no live data for 3 months" to evaluate Tracelight's core LBO modeling workflow.
**The Solution:** Safe-Harbor Synthetic Financial Data Fabric

**Flow:**
1. Open Launcher → click "Launch Safe-Harbor".
2. Click "LBO Template" sample button.
3. Watch Schema Scan (~5s) → Data Waterfall (~20s) → Verdict Badge.
4. Point out the Validation Ticker checking the 6 algebraic rules in real-time.
5. Click "Download .xlsx" → open in Excel to prove the output is a real model with working formulas.
6. Click "View Audit Trail" to show the CTO exactly what happened under the hood (zero LLM hallucinations).

**Peter Pitch:** "Your prospects tell you InfoSec needs 3 months. With Safe-Harbor, they test in 30 seconds. Zero sensitive data. Mathematically verified. Your sales cycle just got 8 weeks shorter."
**Cost Callout:** "Eight cents per synthetic model."

---

## Scenario 2: "The Consulting Analyst" (Safe-Harbor)
**Target Profile:** McKinsey / BCG Analyst
**The Block:** Needs to see Tracelight work with a standard 3-Statement model, not just LBOs.

**Flow:**
1. Same as Scenario 1 but use `three_statement_template.xlsx`.
2. Highlight that there's no debt schedule, purely IS/BS/CF linkage. The agent dynamically adapted without user configuration.

**Janek Pitch:** "No prompting. No configuration. Upload and go. The complexity is in the backend."

---

## Scenario 3: "The Procurement Team" (Shield-Wall)
**Target Profile:** Goldman Sachs Procurement / Internal Ops
**The Block:** 250-question vendor security assessment that takes 10 hours to complete manually.

**Flow:**
1. Open Launcher → click "Launch Shield-Wall".
2. Upload `sample_questionnaire.xlsx` (30 representative questions).
3. Watch Processing Terminal: parsing → classification → parallel evidence gathering → synthesis.
4. Review AnswerGrid: Filter by "Drift".
5. Show the MFA alert: "Policy says MFA is required, but Telemetry shows Bob doesn't have it."
6. Click "Download Completed Questionnaire" to get the `.docx` export.

**Aleks Pitch:** "Air-gapped. Single-tenant. Read-only telemetry. Your infrastructure data never leaves your VPC. And it caught a real drift before you sent the questionnaire out."
