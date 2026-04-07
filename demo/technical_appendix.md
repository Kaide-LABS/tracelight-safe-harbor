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
