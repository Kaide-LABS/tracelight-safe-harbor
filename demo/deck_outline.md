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
