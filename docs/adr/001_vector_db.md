# ADR-001: Vector Database Selection

**Status:** Accepted  
**Date:** June 2026  
**Deciders:** AI Architect

---

## Context

The RAG pipeline requires a vector store to index regulatory document chunks (768-dimensional embeddings from `nomic-embed-text`) and support:
1. Approximate nearest-neighbour (ANN) semantic search
2. Filtering by jurisdiction and time (regulations change — we need bitemporal queries)
3. Keyword co-filtering (ILIKE) for mandatory keyword matches
4. No external network egress — regulated data must not leave the deployment environment

The system must handle ~50,000 chunks initially (5 documents × ~10,000 chunks) and grow to ~500,000 as the regulatory corpus expands.

---

## Decision

**Use PostgreSQL 15 with the `pgvector` extension.**

Schema:
```sql
CREATE TABLE regulation_chunks (
    chunk_id SERIAL PRIMARY KEY,
    jurisdiction VARCHAR(4),
    doc_id VARCHAR(64),
    citation VARCHAR(256),
    raw_text TEXT,
    embedding vector(768),
    validity_period tstzrange,  -- bitemporal: when this regulation was in force
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON regulation_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON regulation_chunks USING gist (validity_period);
```

---

## Alternatives Considered

### Option A: ChromaDB
- **Pros:** Simple Python API, no external dependency, fast for prototyping
- **Cons:** No bitemporal support (we'd need a separate metadata filter layer), no transactional guarantees, not production-hardened at scale, no full-text search integration
- **Why rejected:** Bitemporal queries are a first-class requirement (a regulation may have been amended — we need to know what applied on a given transaction date). ChromaDB has no native `tstzrange` equivalent.

### Option B: Weaviate
- **Pros:** Production-grade, supports hybrid search natively (BM25 + vector), multi-tenancy
- **Cons:** Separate operational footprint (another containerised service), no native bitemporal support without custom schema design, more complex to self-host, larger resource footprint
- **Why rejected:** Adds operational complexity without material benefit over pgvector for our scale. The bitemporal constraint would still require custom logic.

### Option C: Pinecone / Qdrant Cloud
- **Pros:** Fully managed, fast, metadata filtering
- **Cons:** Data leaves the deployment environment — directly violates the data residency requirement for RBI-regulated data
- **Why rejected:** Non-starter for data sovereignty reasons.

### Option D: PostgreSQL + pgvector (chosen)
- **Pros:**
  - Native `tstzrange` gives bitemporal filtering in a single SQL clause (`validity_period @> $date`)
  - ILIKE and full-text search coexist with vector search in the same query
  - HNSW index gives sub-10ms ANN search at our corpus size
  - Single operational database — no additional service to manage
  - Transactional consistency for document updates
  - 100% self-hostable (RDS, CloudSQL, or bare-metal)
- **Cons:** Not purpose-built for vector search; for >10M vectors may require sharding

---

## Consequences

**Positive:**
- Bitemporal queries are handled in native SQL — no bespoke application logic
- Hybrid search (cosine + ILIKE) in a single round-trip to the database
- Existing PostgreSQL operational tooling applies (backups, migrations, monitoring)

**Negative:**
- HNSW index build time increases with corpus size; may need `ivfflat` for >5M vectors
- No native BM25 scoring — we implement keyword density in the application layer (RRF re-ranker)
- pgvector dimensions capped at 2,000 — fine for nomic-embed-text (768-dim) but constrains future model choice if moving to higher-dimensional models

**Migration path:** If corpus exceeds 5M vectors and pgvector ANN latency degrades beyond SLA, migrate the vector index to a dedicated pgvector-compatible sidecar (e.g., Supabase) while keeping the relational metadata in PostgreSQL. The schema is compatible.
