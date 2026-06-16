# ADR-003: Guardrail Implementation Approach

**Status:** Accepted  
**Date:** June 2026  
**Deciders:** AI Architect

---

## Context

A compliance assistant making incorrect or hallucinated regulatory assertions poses serious business and legal risk. Key failure modes:
1. **Hallucinated thresholds** — LLM invents a capital ratio or transaction limit not in the retrieved context
2. **Fabricated citations** — LLM cites a document that was not retrieved (or does not exist)
3. **PII leakage** — customer names or account numbers flow through to stored compliance reports
4. **False confidence** — LLM provides a definitive answer when the evidence is sparse or ambiguous

We need guardrails that are: (a) implementable with open-source tools only, (b) production-fast (no >500ms overhead), and (c) auditable (the guardrail decision itself must be logged).

---

## Decision

**Implement a layered in-pipeline guardrail stack with no external dependency.**

### Layer 1: PII Redaction (Pre-Processing)
- **What:** Llama 3.2 scrubs PII (names, account IDs) from the raw transaction before any other agent sees it
- **Where:** `pii_redactor` node — first node in every pipeline
- **Why first:** All downstream agents receive only the redacted payload. Even if a downstream LLM generates incorrect output, no PII is embedded in the compliance assessment.

### Layer 2: Evidence Score Threshold (Retrieval Quality Gate)
- **What:** If the average cosine similarity of retrieved chunks is below 0.60, the pipeline aborts the LLM reasoning step and returns a conservative default (`risk_level: MED`, `reason: "Insufficient evidence"`)
- **Where:** `screening_node` — after retrieval, before LLM call
- **Why:** A low similarity score means the query has no good match in the knowledge base. Proceeding with weak context is more dangerous than admitting uncertainty.

### Layer 3: Deterministic Citation Cross-Check (Output Validation)
- **What:** The QA node extracts citation IDs from the LLM's output and cross-references them against the set of actually retrieved chunk IDs. Any citation not in the retrieved set is flagged as fabricated.
- **Where:** `qa_node` — deterministic check before LLM faithfulness judge
- **Why:** Pure string matching. Fast, deterministic, zero additional LLM calls. Catches the most common hallucination pattern (inventing a plausible-sounding document reference).

### Layer 4: LLM Faithfulness Judge (Semantic Grounding Check)
- **What:** A second Llama 3.2 call with a strict auditor prompt checks whether every claim in the screening result is explicitly supported by the retrieved context chunks. Returns `{faithful: bool, feedback: str}`.
- **Where:** `qa_node` — after the citation check
- **Why:** Catches subtler hallucinations where the model rephrases or extrapolates beyond what the context says (e.g., inventing a specific threshold the document merely references in passing). LLM-as-judge adds ~200ms but provides semantic depth that string matching cannot.

### Layer 5: Structured Output Enforcement
- **What:** Ollama's `format='json'` parameter forces the model to produce valid JSON. All prompts include an explicit output schema. `call_llm` in `llm_client.py` raises on `json.JSONDecodeError` rather than silently passing malformed output.
- **Where:** Every LLM call via `llm_client.py`

---

## Alternatives Considered

### Option A: Nvidia NeMo Guardrails
- **Pros:** Purpose-built for LLM guardrails, declarative Colang syntax, supports hallucination detection and topic restriction
- **Cons:** Requires a separate NeMo service (additional operational footprint), adds ~300-500ms latency per call, overkill for structured JSON outputs where schema validation is the primary guard
- **Why rejected:** Operational overhead and latency cost not justified when structured prompts + in-pipeline checks achieve equivalent protection for our use case.

### Option B: Guardrails.ai
- **Pros:** Python library, output validation via Pydantic schemas
- **Cons:** Not in our approved dependency list, adds complexity, doesn't address the citation hallucination problem specifically
- **Why rejected:** Our custom citation cross-check and LLM judge provide equivalent schema validation with lower coupling.

### Option C: No guardrails (trust the LLM)
- **Why rejected:** Unacceptable for a regulated compliance application. Audit requirements mandate that every AI-assisted decision is traceable and verifiable. A hallucinated capital ratio that triggers a false "ALLOW" on a prohibited transaction is a regulatory breach.

### Option D: Rule-based keyword blocklist
- **Pros:** Fast, deterministic
- **Cons:** Cannot detect semantic hallucination (e.g., correct keywords but wrong numbers). Cannot verify that a threshold cited by the LLM actually appears in the source document.
- **Why rejected:** Insufficient detection capability; complements but does not replace semantic checks.

---

## Consequences

**Positive:**
- Multi-layer defence — a hallucination that passes Layer 2 is likely caught by Layer 3 or 4
- Every guardrail decision is logged as a Langfuse observation with trace_id — fully auditable
- No external dependency — all guardrails run locally, consistent with data residency requirements
- Guardrail failures produce a conservative outcome (HOLD rather than ALLOW) — safe-by-default

**Negative:**
- LLM faithfulness judge adds ~200ms per screening call (acceptable for compliance workflows, not for real-time trading)
- False positives possible — the faithfulness judge may flag valid answers if the context is dense and the LLM rephrases naturally. Tuning the threshold may be required post-deployment.
- PII redaction via LLM is probabilistic — it may miss structured PII formats (e.g., encoded account numbers). Supplement with a deterministic regex scrubber for production.

**Monitoring:** Track the rate of `faithful=false` verdicts in Langfuse. If it exceeds 5% over a rolling week, investigate whether retrieval quality has degraded (re-run eval suite) or whether the LLM needs updated prompts.
