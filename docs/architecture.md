# FinServ Global — AI-Powered Regulatory Compliance Assistant
## Architecture Document

**Version:** 1.0 | **Date:** June 2026 | **Status:** MVP

---

## 1. Assignment Context

FinServ Global operates across India, EU, and US markets with ~40 compliance officers spending 60%+ of their time manually searching regulatory PDFs. This system reduces that burden by providing:

1. Natural-language Q&A over a versioned regulatory knowledge base (Basel III, MiFID II, RBI)
2. Real-time transaction screening with risk ratings and citations
3. Regulatory change impact analysis
4. Audit-ready batch compliance reports

**Hard constraints:** 100% data residency (no regulated data to external APIs), open-source stack only, full audit traceability.

---

## 2. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Presentation Layer  (Streamlit — 4-tab UI)                    │
│  Q&A │ Transaction Screening │ Impact Analysis │ Batch Report  │
└───────────────────────┬────────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────────┐
│  Orchestration Layer  (Custom State Machine / Multi-Pipeline)  │
│  run_qa_pipeline │ run_compliance_pipeline │ run_batch_report  │
└───────────────────────┬────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌──────────────────┐
│ Agent Nodes   │ │ RAG / Retrieval│ │ Guardrails / QA  │
│ Redactor      │ │ Hybrid Search  │ │ PII Redaction    │
│ Supervisor    │ │ + RRF Reranker │ │ Faithfulness QA  │
│ EDD           │ │               │ │ Evidence Score   │
│ Screening     │ └───────┬───────┘ └──────────────────┘
│ QA Judge      │         │
│ Reporter      │ ┌───────▼───────┐
│ Regulatory QA │ │  Vector DB    │
│ Batch Report  │ │  PostgreSQL   │
│ Impact        │ │  + pgvector   │
└───────────────┘ └───────────────┘
                        │
┌───────────────────────▼────────────────────────────────────────┐
│  Data Layer                                                    │
│  regulation_chunks (pgvector) │ customers.db (SQLite)         │
└───────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────────────┐
│  Observability Layer  (Langfuse — self-hosted)                 │
│  Traces │ Observations │ Token Usage │ Latency                 │
└────────────────────────────────────────────────────────────────┘
```

See also: `diagrams/00_layers.png`, `diagrams/04_agent_topology.png`

---

## 3. RAG Pipeline Design

### 3.1 Document Ingestion Strategy

| Document | Jurisdiction | Format | Doc ID |
|---|---|---|---|
| RBI KYC Master Direction 2016 | IN | PDF | rbi_kyc_2016 |
| RBI Operating Guidelines – Primary Dealers | IN | PDF | rbi_op_guidelines |
| RBI Relief Savings Bonds | IN | PDF | rbi_relief_bonds |
| MiFID II Investor Protection Guide | EU | PDF | mifid_ii_guide |
| Basel III Framework | INTL | PDF | basel_iii_framework |

**Ingestion pipeline:** `src/parsers/rule_based_chunker.py` → `src/database/vector_uploader.py`

Documents are parsed with `pypdf`, chunked, embedded with `nomic-embed-text` via local Ollama, and inserted into PostgreSQL with a `validity_period` tstzrange column to support bitemporal queries.

### 3.2 Chunking Strategy

**Algorithm:** Native Recursive Splitter (implemented in `rule_based_chunker.py`) with:
- **Chunk size:** 3,000 characters
- **Overlap:** 300 characters (10%)
- **Separator hierarchy:** paragraphs (`\n\n`) → lines (`\n`) → sentences (`. `) → words

**Justification:** Regulatory PDFs have structured paragraph boundaries. Starting with `\n\n` respects section boundaries (preserving regulatory context). The 300-character overlap ensures that references to a threshold defined at the end of one chunk are not lost at the start of the next. 3,000 characters fits comfortably within `nomic-embed-text`'s 8,192-token context window while keeping chunks semantically cohesive.

### 3.3 Embedding Model & Vector Database

| Component | Choice | Alternatives Considered | Why |
|---|---|---|---|
| Embedding model | `nomic-embed-text` (768-dim) via Ollama | OpenAI text-embedding-3, BGE-M3 | Local-only, MTEB top-10 open model, 768-dim gives strong semantic coverage with reasonable index size |
| Vector DB | PostgreSQL 15 + pgvector | Chroma, Weaviate, Pinecone | Single-DB simplifies ops, bitemporal support via native `tstzrange`, HNSW index for sub-10ms ANN search |

See ADR-001 for full vector DB trade-off analysis.

### 3.4 Retrieval Strategy — Hybrid Search + RRF Re-ranking

**Stage 1 — Candidate fetch (SQL):**
```sql
SELECT ... FROM regulation_chunks
WHERE validity_period @> $transaction_date::timestamptz
  [AND raw_text ILIKE $keyword]
ORDER BY embedding <=> $query_vector
LIMIT top_k * 3
```
- Cosine similarity via pgvector `<=>` operator over HNSW index
- Bitemporal filter: `validity_period @> date` ensures only regulations in force on the transaction date are returned (eliminates superseded circulars)
- Optional ILIKE keyword filter for hard keyword requirements (e.g., "KYC", "SWIFT")

**Stage 2 — RRF Re-ranking (`src/tools/reranker.py`):**
```
final_score = 0.6 × (1/(k + vector_rank)) + 0.4 × (1/(k + keyword_density_rank))
```
- `keyword_density_rank`: ranks candidates by fraction of query tokens found in `raw_text`
- RRF constant `k=60` prevents high-rank candidates from dominating when the score gap is small
- Re-ranking is performed in Python with no additional model dependency
- Returns top-K with `rerank_score` field for auditability

**Stage 3 — Evidence score guardrail:**
If the average cosine similarity across retrieved chunks is below 0.60, the pipeline returns a LOW-confidence assessment rather than generating a potentially hallucinated answer. This threshold is configurable.

### 3.5 Version Control in the Vector Store

Each chunk has a `validity_period tstzrange` column:
- `[2023-01-01, infinity)` for currently active regulations
- `[2021-01-01, 2023-12-31)` for superseded versions (retained for audit replay)

When a new circular supersedes an existing document, the old chunks are updated with a finite upper bound and new chunks are inserted with the new effective date. This allows the system to answer "what regulation applied on date X?" without re-indexing.

---

## 4. LLM Orchestration Layer

### 4.1 Foundation Model

| Attribute | Choice | Rationale |
|---|---|---|
| Model | Llama 3.2 (3B) via Ollama | 100% local — no data leaves the machine. Sufficient for JSON-structured compliance tasks with well-crafted prompts. |
| Serving | Ollama | Single binary, GPU acceleration if available, REST API compatible |
| Embedding | nomic-embed-text | Separate embedding model optimised for retrieval, avoids using the generative model for embeddings |

See ADR-002 for self-hosted vs. API trade-off analysis.

### 4.2 Multi-Model Routing Strategy

```
Query classification / PII scrubbing → Llama 3.2 (small, fast, local)
Compliance synthesis (screening) → Llama 3.2 (same model, structured JSON prompt)
QA faithfulness judge → Llama 3.2 (structured JSON prompt, binary verdict)
```

**Production extension:** Route complex multi-regulation reasoning to a larger model (e.g., Llama 3.1 70B via Ollama on GPU, or Mistral-Large on a sovereign cloud). The `AGENT_CONFIG` dict in `compliance_agent.py` and the `call_llm` abstraction in `llm_client.py` are designed to support per-agent model selection.

### 4.3 Prompt Engineering Framework

All prompts are externalised as YAML files in `prompts/`:

| File | Agent | Output Schema |
|---|---|---|
| `screening_v1.yaml` | Screening Specialist | `{compliant, risk_level, reason, citations, evidence}` |
| `qa_judge.yaml` | QA/Faithfulness Judge | `{faithful, feedback}` |
| `reporter_v1.yaml` | Report Specialist | `{final_decision, executive_summary, regulatory_basis, required_actions}` |
| `qa_v1.yaml` | Regulatory Q&A | `{answer, citations, source_documents, confidence, coverage_note}` |
| `batch_report_v1.yaml` | Batch Reporter | `{risk_summary, decision_summary, systemic_observations, required_actions}` |

**Key prompt design principles:**
1. **Strict JSON output** (`format='json'` in Ollama API) — parseable, schema-validated
2. **No invention rules** — every prompt explicitly prohibits inventing thresholds or regulations not in context
3. **Chain-of-thought suppressed** — we want structured decisions, not long reasoning chains, to keep latency low
4. **Evidence grounding** — prompts require the model to cite specific context chunks

### 4.4 Guardrails

| Guardrail | Implementation | Location |
|---|---|---|
| PII Redaction | Llama 3.2 scrubs names/IDs before any further processing | `redactor.py` |
| Evidence score threshold | If avg cosine similarity < 0.60, force LOW confidence / HOLD | `screening.py` |
| Citation hallucination check | Cross-references LLM-cited chunk IDs against retrieved chunk set | `qa.py` (qa_node) |
| LLM faithfulness judge | Secondary LLM call verifies claims are in context | `qa.py` |
| JSON parse guard | `json.loads` with fallback + default values | `llm_client.py` |

See ADR-003 for guardrail design trade-offs.

---

## 5. Agentic Workflow Design

### 5.1 State Machine Architecture

The system uses a custom `StateGraph` (not LangGraph/CrewAI) to maintain full control over determinism and auditability. The state is a plain Python dict threaded through each node.

**Transaction Screening Flow:**
```
redact → supervise → [edd →] screen → qa → report
```

| Node | Role | Key Outputs |
|---|---|---|
| `pii_redactor` | Tier 1 privacy: scrubs PII via local LLM | `redacted_txn` |
| `supervisor_router` | Deterministic routing (amount, jurisdiction) | `next_node` |
| `edd_node` | Enhanced Due Diligence flag for HIGH-risk customers | `edd_result` |
| `screening_node` | RAG retrieval + LLM compliance assessment | `screening_result`, `context`, `evidence_score` |
| `qa_node` | Faithfulness validation (deterministic + LLM judge) | `qa_result` |
| `reporting_node` | Final report generation | `report` |

**Additional Pipelines (parallel entry points):**

| Pipeline | Entry Function | Flow |
|---|---|---|
| Q&A | `run_qa_pipeline(query)` | retrieval → `regulatory_qa_node` |
| Impact Analysis | `run_impact_pipeline(text)` | retrieval → `impact_node` |
| Batch Report | `run_batch_report_pipeline(txns)` | loop(screening) → `batch_report_node` |

### 5.2 Tool Definitions

| Tool | ID | Type | Description |
|---|---|---|---|
| `search_regulations` | T02 | pgvector + RRF | Hybrid bitemporal search + re-ranking |
| `get_customer_profile` | T08 | SQLite | KYC/risk lookup by account ID |
| `mcp_search_tool` | — | Adapter | Wraps T02 with error propagation |

### 5.3 Error Handling

- **Retrieval failure:** `mcp_search_tool` raises `RuntimeError` on zero results (no silent fallback)
- **LLM JSON parse failure:** `llm_client.py` raises — caught at node level with default safe values
- **Customer not found:** Returns `UNKNOWN` risk rating, triggers conservative screening path
- **Low evidence score:** `evidence_score < 0.60` bypasses LLM conclusion and returns HOLD

---

## 6. Infrastructure & Non-Functional Requirements

### 6.1 Local Development Stack

```
docker-compose.yml:
  postgres:15 (port 5434)  ← regulation_chunks table with pgvector
  langfuse:2   (port 3000)  ← observability UI
  
ollama (native, port 11434) ← llama3.2 + nomic-embed-text
streamlit (port 8501)        ← compliance UI
```

### 6.2 Production Cloud Architecture (AWS EKS)

```
                    ┌──────────────┐
Internet ──────────►│  API Gateway  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  EKS Cluster  │
                    │  ┌──────────┐│
                    │  │Streamlit ││  (2-4 replicas, HPA on CPU)
                    │  │ Pod      ││
                    │  └──────┬───┘│
                    │         │    │
                    │  ┌──────▼───┐│
                    │  │Agent     ││  (4-8 replicas, HPA on pending requests)
                    │  │Service   ││
                    │  └──────┬───┘│
                    │         │    │
                    │  ┌──────▼───┐│
                    │  │Ollama    ││  (GPU node group, g5.2xlarge)
                    │  │Service   ││  (2 replicas for availability)
                    │  └──────────┘│
                    └──────────────┘
                           │
              ┌────────────┴───────────┐
              │                        │
    ┌─────────▼──────┐      ┌──────────▼──────┐
    │  RDS Postgres  │      │  Self-hosted     │
    │  (pgvector)    │      │  Langfuse on EKS │
    │  Multi-AZ      │      │  (observability) │
    └────────────────┘      └─────────────────┘
```

**Auto-scaling:**
- Streamlit pods: HPA on CPU (target 70%), min 2, max 8
- Agent service: HPA on custom metric (queue depth), min 4, max 16
- Ollama: vertical scaling (larger GPU) preferred over horizontal (model state is large)

**Data Residency:** All components run within the customer's AWS account in a single region (e.g., `ap-south-1` for India-regulated data). No traffic crosses to external LLM APIs. Ollama serves models from local GPU nodes.

### 6.3 Cost Estimate (500 concurrent users, 10K queries/day)

| Component | Instance | Monthly Cost (est.) |
|---|---|---|
| EKS control plane | — | $72 |
| Agent service nodes | 4× m6i.xlarge | $560 |
| Ollama GPU nodes | 2× g5.2xlarge | $1,940 |
| RDS Postgres (pgvector) | db.r6g.large Multi-AZ | $380 |
| Langfuse (EKS) | 2× t3.medium | $60 |
| **Total** | | **~$3,012/month** |

*Comparison: Equivalent Claude API usage at 10K queries/day × ~2K tokens/query = ~$600/day = $18K/month. Self-hosted Llama 3.2 reduces LLM cost by ~6×.*

### 6.4 Security & Compliance

| Control | Implementation |
|---|---|
| Data residency | All model inference on Ollama in-cluster — zero external LLM API calls |
| PII protection | Tier 1 redaction node runs before any regulatory reasoning |
| Encryption at rest | RDS encryption enabled, EBS volumes encrypted |
| Encryption in transit | TLS 1.3 between all services (mTLS within EKS via Istio) |
| Audit logging | Every LLM call logged as Langfuse observation with input/output/trace_id |
| Model access control | Ollama service accessible only within EKS namespace (NetworkPolicy) |
| Secrets management | DB credentials via AWS Secrets Manager, injected as K8s secrets |

### 6.5 Observability

**Langfuse (self-hosted)** captures:
- Trace per compliance pipeline run (linked by `trace_id`)
- Observation per agent node (name, input, output, latency)
- Token usage estimation per LLM call
- Evidence score and retrieval metadata

**Evaluation pipeline** (`src/evaluation/run_evals.py`) measures 4 metrics:
- **Faithfulness** (1-5): LLM-as-judge, is answer grounded in context?
- **Answer Relevance** (1-5): LLM-as-judge, does answer match ground truth?
- **Context Precision** (0-1): fraction of retrieved chunks relevant to the query
- **Context Recall** (0-1): fraction of ground truth claims supported by retrieved context

**Drift detection:** Re-run evaluation weekly. Flag if average faithfulness drops below 3.5 or context precision drops below 0.6 — triggers a re-embedding run (new documents may have shifted the vector space).

---

## 7. Key Design Decisions

See `docs/adr/` for full Architecture Decision Records:
- [ADR-001: Vector Database Selection](adr/001_vector_db.md)
- [ADR-002: Model Hosting Strategy](adr/002_model_hosting.md)
- [ADR-003: Guardrail Implementation](adr/003_guardrails.md)
