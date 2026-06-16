# ADR-002: Model Hosting Strategy (Self-Hosted vs. API)

**Status:** Accepted  
**Date:** June 2026  
**Deciders:** AI Architect

---

## Context

The compliance assistant requires two types of model inference:
1. **Embedding:** Convert regulatory text and queries into 768-dimensional vectors
2. **Generation:** Reason over retrieved regulatory context to produce structured compliance assessments

FinServ Global processes RBI-regulated transaction data (India), MiFID II-regulated trade data (EU), and Basel III capital calculations. Regulatory frameworks in all three jurisdictions impose data localisation and confidentiality obligations:
- **India (RBI/DPDP Act):** Financial data must be stored and processed within India
- **EU (GDPR/MiFID II):** PII and trade data subject to transfer restrictions outside EEA
- **US (SOX/GLBA):** Audit data must be retained and access-controlled

Sending transaction data or regulatory documents containing customer PII to a US-hosted API (OpenAI, Anthropic, Google) without explicit data processing agreements and sovereign cloud options would violate these obligations.

---

## Decision

**Self-host all model inference using Ollama running locally / on-premises.**

| Model | Purpose | Serving |
|---|---|---|
| `llama3.2` (3B) | Classification, generation, judging | Ollama |
| `nomic-embed-text` | Embedding (768-dim) | Ollama |

Models are pulled once and cached locally. Inference runs on CPU (development) or GPU (production, `g5.2xlarge`). The Ollama REST API is accessible only within the deployment network (no external exposure).

**PII firewall:** The `pii_redactor` node runs Llama 3.2 locally before any downstream processing. Even internal systems (screening, QA) receive only the redacted payload. The original PII stays in the transaction record but never propagates through the LLM chain.

---

## Alternatives Considered

### Option A: OpenAI GPT-4o / Anthropic Claude (US-hosted API)
- **Pros:** Best-in-class reasoning quality, no GPU infrastructure needed, low operational overhead
- **Cons:**
  - Data sent to US servers — directly conflicts with RBI data localisation and GDPR transfer restrictions
  - Requires DPA negotiations with providers and likely sovereign cloud agreements
  - Variable latency and cost (pricing risk at 10K queries/day = ~$18K/month vs ~$3K self-hosted)
  - Model deprecations are outside our control — compliance decisions linked to a model that may be retired
- **Why rejected:** Data sovereignty is non-negotiable. Even with Azure OpenAI in EU regions, RBI's expectation is on-premises or sovereign cloud in India.

### Option B: Dedicated Sovereign Cloud API (Azure Government / AWS GovCloud)
- **Pros:** Managed inference, data residency compliance possible in some jurisdictions
- **Cons:** Coverage gap — Azure OpenAI in India region has limited model availability; no sovereign option for MiFID II in-EEA requirements that also covers India simultaneously; significant cost premium; still a proprietary lock-in risk
- **Why rejected:** Does not simultaneously satisfy all three jurisdictions without a complex multi-region routing setup.

### Option C: Self-hosted Llama 3.1 70B on GPU cluster
- **Pros:** Significantly better reasoning quality than 3B for complex multi-regulation scenarios
- **Cons:** Requires A100/H100 GPU cluster (>$10K/month incremental cost), complex MLOps
- **Why not immediately:** Staged roadmap — start with Llama 3.2 3B (sufficient for JSON-structured tasks with structured prompts), upgrade to 70B when latency budget allows

### Option D: Self-hosted Ollama — Llama 3.2 3B (chosen)
- **Pros:**
  - All data stays in-network — satisfies RBI, GDPR, and audit requirements
  - No API cost — fixed infrastructure cost
  - Deterministic model versioning — pin the model hash, freeze for audit periods
  - Sub-200ms inference on GPU for structured JSON outputs
  - `call_llm` abstraction in `llm_client.py` allows swapping to a larger model with zero code changes
- **Cons:** Lower raw reasoning quality than frontier models; requires GPU infrastructure in production

---

## Consequences

**Positive:**
- Zero data sovereignty risk — no regulated data ever touches an external API
- Pinnable model versions support MRM (Model Risk Management) audit requirements
- Cost predictable — no per-token billing
- `AGENT_CONFIG` in `compliance_agent.py` allows per-agent model selection when a larger local model is available

**Negative:**
- Llama 3.2 3B may produce lower-quality answers for highly ambiguous multi-jurisdiction queries compared to GPT-4o
- GPU infrastructure adds CapEx / cloud cost
- Model updates require internal MLOps process (pull new version, run eval suite, promote)

**Mitigation for quality:** Structured prompts with strict JSON schema + guardrails (faithfulness judge, evidence score threshold) compensate significantly. The evaluation suite (`run_evals.py`) provides objective quality gates before any model update is promoted.

**Future state:** When Llama 3.1 70B or similar is available on a cost-effective GPU instance, route complex cross-regulation queries (multi-jurisdiction transactions) to the larger model while keeping classification and simple Q&A on 3B. The `call_llm` abstraction supports this without agent code changes.
