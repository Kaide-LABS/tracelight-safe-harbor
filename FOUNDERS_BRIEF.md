# FOUNDER'S BRIEFING DOCUMENT
## Target: Tracelight (tracelight.ai)
## Prepared for: Isaac (Head of Sales / Co-Founder)
## Classification: Internal Only — Pre-Demo Prep

---

# SECTION 1: THE DEMO IN LAYMAN'S TERMS (The "Bar Pitch")

## The Problem We're Solving

Tracelight makes an AI engine that helps financial analysts build complex Excel models — think leveraged buyouts, DCF valuations, the stuff that private equity firms and McKinsey consultants live in. They just raised $3.6M, they're signing 5 of the top 10 global consultancies, and they're growing fast.

But they have one brutal bottleneck: **their biggest prospects can't actually try the product.**

Why? Because these are banks and PE firms. They have strict InfoSec rules. They cannot upload real financial data — actual deal numbers, revenue figures, debt schedules — into any third-party AI tool during an evaluation. That's MNPI (Material Non-Public Information). Uploading it would be a compliance violation. So when the Tracelight sales team says "try our product on your own model," the prospect says: "Love to. InfoSec says we need 3 months of security review before we can upload anything."

Three months. To try a product. That's the bottleneck killing their sales velocity.

## What We Built

**Safe-Harbor:** A tool that generates fake-but-mathematically-perfect financial data and stuffs it into the prospect's own empty Excel template — instantly. No real data needed. No InfoSec approval needed. The prospect can test Tracelight's core product in 30 seconds instead of 3 months.

**Shield-Wall:** An internal tool for Tracelight's own sales team that auto-answers the massive vendor security questionnaires that enterprise clients send during procurement. Instead of someone spending 10 hours copy-pasting from policy docs, our AI reads the questionnaire, queries their actual infrastructure for evidence, and drafts every answer in minutes.

## The Magic Moment (What They'll See On Screen)

### Safe-Harbor Demo:
The prospect uploads an empty LBO shell — just headers, no numbers. In real-time, they watch:

1. **Schema Scan** — A terminal feed lights up showing the AI mapping every sheet: "Income Statement → 23 columns... Balance Sheet → 31 columns... Debt Schedule → 12 columns..."
2. **Data Waterfall** — Numbers cascade into every cell, row by row. Each cell flashes amber as it's written, then green as it passes mathematical validation.
3. **The Verdict** — A full-screen badge: "SYNTHETIC MODEL VERIFIED. Balance Sheet Balanced. Cash Flow Reconciled. Debt Schedule Amortized. Zero Sensitive Data." Two buttons: Download, or Start Testing in Tracelight.

The prospect just went from "InfoSec needs 3 months" to "I'm testing the product right now" in 30 seconds. With a model that feels completely real but contains zero sensitive data.

### Shield-Wall Demo:
The ops team uploads a 30-question vendor security assessment. They watch a terminal feed as the AI parses questions, queries live infrastructure telemetry, pulls policy citations, and drafts evidence-backed answers. Then a drift alert pops up in red: "CRITICAL: Policy claims MFA is required for all users, but telemetry shows Bob doesn't have MFA." The tool didn't just answer the questionnaire — it caught a real compliance gap before the client did.

---

# SECTION 2: THE DEMO IN DEEP TECHNICAL TERMS (The "CTO Shield")

## Architecture Overview

We built two decoupled multi-agent sidecar architectures that interface with Tracelight's core product exclusively at the data boundaries — never touching their proprietary DAG (Directed Acyclic Graph) engine that parses Excel formulas into topological dependency graphs.

### Safe-Harbor: Agent Routing & Data Flow

```
Empty .xlsx Template
     │
     ▼
ORCHESTRATOR (FastAPI + WebSocket, real-time event streaming)
     │
     ├──► AGENT 1: Schema Extraction (Gemini 2.0 Flash, Google Vertex AI)
     │    Parses openpyxl JSON: sheet names, headers, cell positions,
     │    formula patterns, inter-sheet references (P&L→CF→BS linkage).
     │    Classifies model type (LBO/DCF/3-Statement), detects temporal
     │    structure (FY2020-FY2025), infers industry sector.
     │    Output: Typed TemplateSchema (Pydantic, 15 nested models)
     │    Fallback: GPT-4o via OpenAI after 2 Gemini failures.
     │
     ├──► AGENT 2: Synthetic Generation (GPT-4o Structured Outputs, OpenAI)
     │    Receives TemplateSchema. Generates synthetic financial data via
     │    response_format=SyntheticPayload (strict JSON schema enforcement).
     │    Temperature 0.3 for controlled variation. Industry-aware constraints.
     │    Output: SyntheticPayload with cell-level values mapped to exact refs.
     │
     ├──► AGENT 3: Deterministic Validation (Pure Python — NOT an LLM)
     │    6 hardcoded algebraic rules, zero tolerance:
     │    ├─ Balance Sheet Identity: Assets == Liabilities + Equity
     │    ├─ Cash Flow Reconciliation: Ending == Beginning + Net Change
     │    ├─ Net Income Linkage: P&L NI == CF NI
     │    ├─ Margin Bounds: Gross [0,1], EBITDA [-0.5,0.8], Net [-1,0.5]
     │    ├─ Depreciation: Cumulative D&A <= Cumulative CapEx + Opening PP&E
     │    └─ Debt Schedule: Ending = Beginning + Drawdowns - Repayments
     │    On failure: calculates exact delta, plugs Cash or Retained Earnings.
     │    On structural violation: signals retry to Agent 2 (max 3 loops).
     │
     └──► EXCEL WRITER (openpyxl — NOT an LLM)
          Writes validated values into input cells only. Never overwrites formulas.
          Output: .xlsx with working formulas + synthetic inputs.
```

### Shield-Wall: Agent Routing & Data Flow

```
Vendor Security Questionnaire (.xlsx/.csv/.pdf/.docx)
     │
     ▼
ORCHESTRATOR (FastAPI + WebSocket)
     │
     ├──► AGENT 1: Questionnaire Parser (Gemini 2.0 Flash)
     │    Classifies each question into 12 security categories.
     │    Normalizes ambiguous language. Flags telemetry vs. policy needs.
     │    Fallback: GPT-4o after 2 Gemini failures.
     │
     ├──► PARALLEL EXECUTION:
     │    ├─ AGENT 2: Telemetry Agent (GPT-4o + function calling)
     │    │  Generates infrastructure queries via tool_choice="auto".
     │    │  Executes against mock/real AWS adapter (CloudTrail, IAM, KMS, SGs).
     │    │  Semaphore-bounded: max 10 concurrent queries.
     │    │
     │    └─ AGENT 3: Policy Agent (text-embedding-3-small + ChromaDB RAG)
     │       Embeds query, searches chunked SOC 2 / policy docs via cosine
     │       similarity. Returns top-K citations with relevance scores.
     │
     ├──► AGENT 4: Synthesis Agent (GPT-4o Structured Outputs)
     │    Merges telemetry evidence + policy citations per question.
     │    Outputs DraftAnswer with confidence level and evidence grounding.
     │
     └──► AGENT 5: Drift Detector (Pure Python — NOT an LLM)
          5 independent telemetry-vs-policy checks:
          Encryption, MFA, Logging, Network, Generic.
          Serializes raw_result via json.dumps() for pattern matching.
          Deduplicates alerts per question_id.
          Output: DriftAlert[] with severity + remediation recommendation.
```

### The Three "We Are Not an API Wrapper" Soundbites

Isaac — memorize these. Drop them if anyone asks "so you just call GPT-4?":

**Soundbite 1 — The Deterministic Trust Anchor:**
> "The validation layer is not an LLM. It's a hardcoded Python rules engine enforcing six algebraic accounting identities with zero tolerance. If GPT-4o generates a number that breaks double-entry bookkeeping — say, Assets don't equal Liabilities plus Equity — the engine calculates the exact delta, adjusts a designated plug account like Cash or Retained Earnings, and force-corrects the payload. The system is physically incapable of outputting a balance sheet that doesn't balance. That's not prompt engineering. That's a deterministic constraint solver sitting on top of a stochastic generator."

**Soundbite 2 — The Drift Detection Engine:**
> "Shield-Wall doesn't just answer questionnaires — it performs an autonomous internal audit. After the synthesis agent drafts each answer, a pure-Python drift detector independently cross-references the live infrastructure telemetry against the written policy documents using five hardcoded pattern-matching checks. If your SOC 2 report says 'MFA is required for all users' but your IAM config shows Bob doesn't have MFA, the system flags a CRITICAL drift alert — before the client's security team finds it. That's not AI answering questions. That's AI catching compliance violations you didn't know you had."

**Soundbite 3 — The Multi-Provider Agent Routing:**
> "We route each agent to the optimal model for its task, not a single LLM. Schema extraction goes to Gemini 2.0 Flash because it has the longest context window for parsing full multi-sheet workbooks at a tenth of the cost. Synthetic generation goes to GPT-4o Structured Outputs because it has the best JSON schema compliance for financial data. Policy search uses text-embedding-3-small with ChromaDB for cosine similarity retrieval. And the validation and drift detection layers use zero LLM — pure Python with hardcoded algebraic assertions. Every agent has a fallback path: if Gemini fails twice, schema extraction automatically reroutes to GPT-4o. The system self-heals across provider boundaries."

---

# SECTION 3: COMPANY INTELLIGENCE (The Psychological Hook)

## Why We Built This — The Strategic Thesis

Tracelight's core IP is a **DAG (Directed Acyclic Graph) engine** that parses Excel spreadsheets into systems of equations with topological dependencies. Instead of treating a spreadsheet as flat text, their AI reasons over causal relationships between cells. This is what makes them different from every ChatGPT-with-Excel wrapper. It's why Jane Street's former engineer (their CTO) built it this way — he thinks in deterministic systems and formal verification, not in probabilistic generation.

**We do not touch this engine. At all.** Everything we built operates as a "sidecar" — a decoupled module that interfaces with their product only at the input/output boundaries:

- **Safe-Harbor** operates **pre-core**: it populates the input cells of an empty template, then hands the completed file to Tracelight's DAG engine. It never touches formulas, dependencies, or model logic.
- **Shield-Wall** operates **in parallel**: it's an internal ops tool for Tracelight's own team. It has nothing to do with the product their customers use.

This is the **Anti-Replication Principle**. We explicitly killed our third proposal (an IC Memo Synthesizer) because Tracelight had just shipped "spreadsheets to beautiful webpages" two weeks before our analysis — building that would have been stepping on their roadmap and would have destroyed our credibility instantly.

## The Founding Team — Who Isaac Is Really Pitching To

### Peter Fuller (CEO) — The McKinsey Pragmatist
- **Background:** McKinsey Engagement Manager, QuantumBlack, Oxford
- **What he cares about:** ROI, sales cycle compression, "does this move revenue?"
- **Trigger phrase:** He literally told his LinkedIn audience: *"Invest in a testing set-up. Create non-sensitive test data for use cases you care about."* Safe-Harbor is the automation of his own advice. Lead with this.
- **Warning:** He hates "workslop" — sloppy AI output. He wrote an entire manifesto about Microsoft Copilot generating catastrophically wrong financial models. If the demo produces a single unbalanced balance sheet, we're dead. That's why the deterministic validator exists.

### Aleksander Misztal (CTO) — The Jane Street Formalist
- **Background:** Jane Street (OCaml, deterministic systems), Nethermind (Zero-Knowledge cryptography), Cambridge CS
- **What he cares about:** Architectural elegance, mathematical proofs, deterministic guarantees
- **Trigger phrase:** He describes Tracelight as "coding agents" — not "AI assistants." Speak in agent terminology.
- **Why the Audit Trail exists:** He will click "View Audit Trail." He will inspect the JSON. He will check if the validation rules actually ran. The audit trail in Safe-Harbor was built specifically for this person. If it's not there, he won't trust the system.
- **Fun fact:** He runs 100-mile ultramarathons. He won't be impressed by flashy demos that collapse under pressure. He'll want to upload weird edge-case templates and see if it breaks.

### Janek Zimoch (CPO) — The 11x Growth Engineer
- **Background:** 3rd engineer at 11x.ai (scaled $100K to $1M ARR), Standard Chartered quant, Cambridge ML
- **What he cares about:** Frictionless UX, zero-prompt interfaces, "does the user have to think?"
- **Trigger phrase:** He built multi-agent orchestration at 11x. He'll immediately spot if our agent routing is cargo-culted vs. genuinely necessary. He knows what real multi-agent pipelines look like.
- **Warning:** Pathologically detail-oriented. Peter says he keeps a precise watering schedule for office plants and sends 2 AM messages about marginal prompt gains. A single unhandled error state or sloppy loading screen will lose him.

---

# SECTION 4: THE ADJACENT MENU (The Hook for the Next Call)

These are the two additional architectures we've fully designed but not yet built. Isaac — tease these at the very end of the demo video. The goal is to make them want a second call.

---

### IDEA 1: "The Vacuum" — Data Room Ingestion Pipeline

**Isaac's script:**

> "We also have a fully designed architecture called The Vacuum that solves the other end of the modeling lifecycle — the part before the analyst even opens Excel. Right now, when a PE fund enters a deal, an analyst spends 2-5 days manually reading 200 PDFs in a data room and typing numbers into their model. The Vacuum takes a ZIP archive of data room documents, runs them through a Gemini-powered Document Triage Agent that classifies each PDF by type and identifies the financial tables, then a GPT-4o Vision Table Extraction Agent pulls every number into structured JSON with exact cell mappings. A hardcoded Python Reconciliation Engine cross-validates the same line item across multiple documents — if the audited financials say FY2023 Revenue is $142M but the management accounts say $145M, it flags the discrepancy and ranks the audited figure as source of truth. Finally, a Template Mapper writes every validated number into the analyst's empty model template with a full provenance trail — click any cell, see exactly which PDF page the number came from. The analyst starts Thursday's work on Monday morning."

---

### IDEA 2: "The Jury" — Cross-Analyst Model Consensus Engine

**Isaac's script:**

> "The second architecture is called The Jury, and it solves a problem that every MD at a PE fund deals with: when 3-4 analysts independently build LBO models of the same target company, someone has to manually compare all of them to find where the assumptions diverge — one analyst projects 12% revenue growth, another projects 8%, and the difference swings the IRR by 500 basis points. The Jury takes N different completed Excel models, runs each through a Gemini-powered Normalization Agent that semantically maps every assumption to a canonical taxonomy regardless of template structure or naming conventions, then a pure-Python Divergence Engine calculates the statistical spread and runs finite-difference sensitivity analysis to identify which single assumption has the highest impact on the deal's IRR. GPT-4o then generates a structured Consensus Briefing ranking the top 5 assumption divergences with plain-English explanations. The output is a dashboard where the MD can toggle between each analyst's worldview and instantly see the implied returns. The 3-hour assumption reconciliation meeting compresses to a 5-minute review."

---

*End of Founder's Briefing. Good hunting, Isaac.*
