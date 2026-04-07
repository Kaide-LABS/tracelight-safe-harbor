# **ADJACENT IDEAS: TRACELIGHT EXPANSION WORKFLOWS**

# **Classification: Post-Demo "Menu" for Head of Sales**

# **Status: Passed Anti-Replication & Ego Check Filters**

## **IDEA 1: "THE VACUUM" — Data Room Ingestion Pipeline**

### **Pain Point Solved: Pre-Model Data Extraction from Unstructured Sources**

**The Problem:**  
When a Private Equity fund enters a deal process, the sell-side advisor opens a  
Virtual Data Room (VDR) containing 200-500 unstructured documents: audited  
financial statements (PDFs), management accounts (scanned Excel printouts),  
lease schedules (PDF tables), customer concentration reports, and capital  
expenditure logs. The analyst's first job — before they even open Excel — is to  
manually read these documents and TYPE the raw numbers into the input cells  
of their LBO or DCF template. This "PDF-to-cell" transcription phase takes  
2-5 full analyst-days per deal, is brutally error-prone, and is the \#1 source  
of "garbage in, garbage out" downstream model errors.  
Tracelight makes you superhuman INSIDE Excel. But it cannot help you if the  
numbers you're typing into Excel are wrong in the first place. The Vacuum  
solves the mile of friction that exists BEFORE the analyst ever touches  
Tracelight's core product.  
**Why This Passes the Ego Check:**

* Tracelight's shipped "image upload and understanding" feature operates  
  WITHIN the Excel add-in context — the user pastes a screenshot into the  
  chat. The Vacuum is fundamentally different: it's a standalone bulk  
  ingestion pipeline that processes an entire data room (hundreds of PDFs)  
  and outputs structured, validated data mapped to a model template's input  
  schema. This is industrial-scale document processing, not in-chat image  
  comprehension.  
* Tracelight's core IP is the DAG engine that reasons over Excel formulas.  
  The Vacuum operates entirely upstream — it feeds clean data INTO input  
  cells. It never touches formulas, dependencies, or model logic. It is a  
  pure pre-core sidecar.  
* No announced or shipped Tracelight feature addresses bulk PDF/data room  
  ingestion.

**Why This Is Lethal for the Sales Pitch:**  
Peter Fuller describes the "80/2 rule" — AI compresses the effort needed to  
reach 80% of the answer. The Vacuum \+ Tracelight Core together compress the  
ENTIRE modeling lifecycle: documents arrive → data extracted automatically →  
model built by Tracelight → analyst reviews and refines. The pitch to an MD  
is: "Your analysts currently spend Monday-Wednesday reading PDFs and typing  
numbers. Thursday building the model. Friday presenting. With Vacuum \+  
Tracelight, they start Thursday's work on Monday morning."

### **Technical Pipeline**

**DATA IN:**  
A ZIP archive or folder of PDF/scanned documents from a Virtual Data Room.  
Typical contents: audited financial statements (Income Statement, Balance  
Sheet, Cash Flow), management accounts, debt schedules, CapEx logs, and  
customer/revenue breakdowns. Additionally, the analyst's empty model  
template (.xlsx) defining what input cells need to be populated.  
**AGENT ROUTING:**  
Agent 1: Document Triage Agent (Gemini 2.0 Flash — Google Vertex AI)  
├─ Ingests all PDFs from the data room archive  
├─ Classifies each document by type (audited financials, mgmt accounts,  
│ debt schedule, CapEx log, lease schedule, other/irrelevant)  
├─ Identifies the temporal period covered by each document  
├─ Outputs a Document Manifest: ordered list of documents with types,  
│ page ranges containing financial tables, and extraction priority  
│  
│ WHY GEMINI: Massive context window handles hundreds of pages.  
│ Classification is a comprehension task, not a generation task.  
│ Fast and cheap for bulk triage.  
│  
Agent 2: Table Extraction Agent (GPT-4o Vision — OpenAI API)  
├─ Receives prioritized pages from the Document Manifest  
├─ For each page containing a financial table:  
│ ├─ Extracts tabular data into structured JSON  
│ ├─ Maps each extracted value to a financial line item  
│ │ (Revenue, COGS, EBITDA, Total Debt, CapEx, etc.)  
│ ├─ Handles messy real-world formatting: merged cells,  
│ │ footnotes, parenthetical negatives, currency symbols,  
│ │ “(in thousands)” / “(in millions)” scale indicators  
│ └─ Flags low-confidence extractions for human review  
│  
│ WHY GPT-4o VISION: Best-in-class multimodal accuracy for  
│ scanned/PDF table extraction. Structured Outputs mode ensures  
│ JSON schema compliance.  
│  
Agent 3: Cross-Document Reconciliation Engine (Python — No LLM)  
├─ Receives all extracted JSON payloads  
├─ Hardcoded rules:  
│ ├─ If the same line item (e.g., FY2023 Revenue) appears in  
│ │ multiple documents, assert they match within 1% tolerance  
│ ├─ If they DON’T match, flag the discrepancy and identify  
│ │ the likely source of truth (audited \> management accounts  
│ │ \> investor presentation, by document-type hierarchy)  
│ ├─ Validate inter-statement linkages across documents:  
│ │ P\&L Net Income must match CF starting Net Income  
│ └─ Output a Reconciliation Report with match/mismatch status  
│  
│ WHY PURE PYTHON: This is a trust anchor. No hallucination.  
│ Hardcoded hierarchy and algebraic assertions only.  
│  
Agent 4: Template Mapper (GPT-4o Structured Outputs — OpenAI API)  
├─ Receives reconciled financial data \+ the analyst’s empty  
│ model template schema (parsed by openpyxl)  
├─ Maps each reconciled data point to the correct input cell  
│ in the analyst’s specific template  
├─ Handles naming mismatches: the data room PDF might say  
│ “Net Sales” while the template header says “Revenue”  
├─ Outputs a Cell Mapping payload:  
│ { “sheet”: “P\&L”, “cell”: “C7”, “value”: 142500000,  
│ “source\_doc”: “FY2023\_Audited\_FS.pdf”, “page”: 12,  
│ “confidence”: 0.97 }  
└─ Excel Writer (openpyxl) populates the template  
**DATA OUT:**  
A fully populated .xlsx model template with every input cell filled from  
data room documents \+ a Provenance Report linking each cell value back to  
the exact PDF page and table it was extracted from (page number, bounding  
box coordinates). The analyst can click any cell and see: "This value came  
from Page 12 of FY2023\_Audited\_FS.pdf, Table 2, Row 'Net Revenue'."

## **IDEA 2: "THE JURY" — Cross-Analyst Model Consensus Engine**

### **Pain Point Solved: Assumption Divergence Detection Across Independent Models**

**The Problem:**  
In competitive PE deal processes and large M\&A mandates, it is standard  
practice for 2-4 analysts to independently build financial models of the  
same target company. The Managing Director or Partner then manually  
compares these models to understand where assumptions diverge — one  
analyst projects 12% revenue growth, another projects 8%; one assumes  
3.5x entry multiple, another assumes 4.2x. This "assumption  
reconciliation" meeting is one of the most high-value activities in the  
deal process, because it surfaces the investment's most debatable  
variables and forces the team to justify their reasoning.  
Currently, this comparison is done manually: the MD opens 3-4 Excel files  
side by side and eyeballs the differences. For complex LBO models with  
hundreds of assumptions, this is exhausting and error-prone. Critical  
divergences get missed. Bad assumptions survive unchallenged.  
**Why This Passes the Ego Check:**

* Tracelight's Spreadsheet Compare feature compares TWO VERSIONS of the  
  SAME spreadsheet — it's a version-diff tool. It answers: "What changed  
  between v1 and v2 of THIS model?" The Jury is fundamentally different:  
  it compares N DIFFERENT models of the SAME company built by DIFFERENT  
  analysts with DIFFERENT template structures, DIFFERENT naming conventions,  
  and DIFFERENT assumption architectures. This is cross-model semantic  
  analysis, not intra-model version diffing.  
* The Jury operates entirely post-core. It ingests finished .xlsx outputs  
  from Tracelight (or any other source). It never modifies the models,  
  never touches the DAG engine, and never interferes with model-building  
  workflows. It's a read-only analytical layer that sits on top of  
  completed work.  
* No announced or shipped Tracelight feature addresses cross-analyst  
  assumption comparison or consensus building.

**Why This Is Lethal for the Sales Pitch:**  
Peter wrote: "Deals are like babies. There's one born every minute, but  
each one is a miracle. A million things have to go right to close a deal."  
One of the things that must go right is the investment committee agreeing  
on assumptions. The Jury compresses the assumption reconciliation meeting  
from a 3-hour manual slog into a 5-minute review of a pre-built consensus  
dashboard. For a PE fund doing 50 deals/year, this saves \~150 hours of  
MD time annually — at MD billing rates, that's a massive ROI.

### **Technical Pipeline**

**DATA IN:**  
2-5 completed .xlsx financial models of the same target company, each  
built by a different analyst (potentially using different template  
structures, different sheet naming, different row ordering). Optionally,  
a "target entity identifier" (company name, ticker, or CIK) to help  
the system confirm all models refer to the same entity.  
**AGENT ROUTING:**  
Agent 1: Model Normalization Agent (Gemini 2.0 Flash — Google Vertex AI)  
├─ For each uploaded model:  
│ ├─ Parses the full workbook structure (openpyxl)  
│ ├─ Identifies the model type (LBO, DCF, 3-Statement, Merger)  
│ ├─ Maps every input assumption to a canonical taxonomy:  
│ │ e.g., “Rev Growth Y1” / “Revenue CAGR 2025” / “Top-line  
│ │ growth rate” all map to → REVENUE\_GROWTH\_RATE\_FY2025  
│ ├─ Extracts all key assumptions into a standardized JSON:  
│ │ { “analyst”: “Analyst\_A”,  
│ │ “assumptions”: {  
│ │ “REVENUE\_GROWTH\_RATE\_FY2025”: 0.12,  
│ │ “ENTRY\_MULTIPLE\_EV\_EBITDA”: 4.2,  
│ │ “EXIT\_MULTIPLE\_EV\_EBITDA”: 5.0,  
│ │ “SENIOR\_DEBT\_RATE”: 0.065,  
│ │ …  
│ │ },  
│ │ “outputs”: {  
│ │ “IRR”: 0.234,  
│ │ “MOIC”: 2.8,  
│ │ “EQUITY\_VALUE”: 485000000  
│ │ }  
│ │ }  
│ └─ Handles structural differences: Analyst A might have  
│ revenue on Sheet 1 Row 15; Analyst B on Sheet 3 Row 42\.  
│ The agent resolves this semantically, not positionally.  
│  
│ WHY GEMINI: Semantic comprehension across diverse structures.  
│ Long context handles full multi-sheet workbooks. Fast.  
│  
Agent 2: Divergence Detection Engine (Python — No LLM)  
├─ Receives normalized assumption JSONs from all analysts  
├─ For each canonical assumption key:  
│ ├─ Calculates: mean, median, std deviation, min, max, range  
│ ├─ Flags HIGH DIVERGENCE assumptions where the coefficient  
│ │ of variation exceeds a configurable threshold (default: 15%)  
│ ├─ Ranks all assumptions by divergence magnitude  
│ └─ Identifies the single assumption with the highest  
│ sensitivity to the output IRR (via a finite-difference  
│ approximation: perturb each assumption ±1%, measure IRR  
│ delta, rank by absolute sensitivity)  
│  
│ WHY PURE PYTHON: Statistical calculations must be exact.  
│ No LLM stochasticity in the divergence math.  
│  
Agent 3: Consensus Narrative Agent (GPT-4o — OpenAI API)  
├─ Receives the ranked divergence report \+ sensitivity analysis  
├─ Generates a structured Investment Committee briefing:  
│ ├─ “TOP 5 ASSUMPTION DIVERGENCES” — ranked list with each  
│ │ analyst’s value, the consensus range, and a plain-English  
│ │ explanation of why this divergence matters  
│ ├─ “HIGHEST-SENSITIVITY VARIABLE” — the single assumption  
│ │ that most affects the deal’s IRR, with a recommendation  
│ │ for which analyst’s estimate to interrogate first  
│ ├─ “CONSENSUS OUTPUT RANGE” — the IRR/MOIC range implied  
│ │ by the spread of assumptions across all analysts  
│ └─ Tone: neutral, analytical, no advocacy for any position  
│  
│ WHY GPT-4o: Best at producing structured, professional  
│ financial narrative. Structured Outputs ensures all required  
│ sections are present.  
**DATA OUT:**  
A Consensus Dashboard (React component) showing:

1. A ranked table of all assumptions sorted by divergence magnitude, with  
   each analyst's value displayed as a dot on a horizontal range bar.  
2. A sensitivity tornado chart showing which assumptions have the highest  
   impact on IRR.  
3. A downloadable PDF "Consensus Briefing" summarizing the top divergences  
   and recommended discussion points for the IC meeting.  
4. A "What-If" toggle: select any analyst's full assumption set and  
   instantly see the implied IRR/MOIC, allowing the MD to flip between  
   worldviews in real-time.

## **ANTI-REPLICATION COMPLIANCE MATRIX**

| Idea | Tracelight Core IP | Overlap? | Justification |
| :---- | :---- | :---- | :---- |
| The Vacuum | DAG engine, formula generation, model building, error checking, precedent tracing, Plan Mode, Change Reviews, web search, Style Guides | NONE | Operates entirely pre-core. Extracts data from PDFs into input cells. Never touches formulas, model logic, or the DAG. |
| The Jury | DAG engine, formula generation, Spreadsheet Compare (version diff), model building, spreadsheet-to-webpage | NONE | Operates entirely post-core on finished models. Read-only analysis. Spreadsheet Compare is version-diffing (v1 vs v2 of same model); The Jury is cross-analyst semantic comparison (N different models of same company). Fundamentally different operations. |

## **EGO CHECK COMPLIANCE**

| Idea | Could Their Engineers Be Building This? | Risk Level |
| :---- | :---- | :---- |
| The Vacuum | No. Their product starts when data is already in Excel. Bulk PDF/data room ingestion is a separate product category (competitors: Alkymi, Scribe, Heron Data). No signals from any founder post or product update suggest this is on their roadmap. | LOW |
| The Jury | No. Their comparison feature is a 1:1 version diff. Cross-analyst consensus analysis with sensitivity ranking and narrative generation is a distinct analytical workflow. No signals from any founder post suggest multi-model comparison is planned. | LOW |

