-- 1. Enable the required enterprise extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Create the Master Regulations/Obligations table
CREATE TABLE IF NOT EXISTS obligations (
    obligation_id VARCHAR(64) PRIMARY KEY,
    parent_doc_id VARCHAR(64) NOT NULL,
    section VARCHAR(128),
    clause VARCHAR(128),
    text_content TEXT NOT NULL,
    metadata_payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create the Chunks & Embeddings table with Temporal Range support
CREATE TABLE IF NOT EXISTS regulation_chunks (
    chunk_id SERIAL PRIMARY KEY,
    obligation_id VARCHAR(64) REFERENCES obligations(obligation_id) ON DELETE CASCADE,
    jurisdiction VARCHAR(4) NOT NULL,
    doc_id VARCHAR(64) NOT NULL,
    citation VARCHAR(256) NOT NULL,
    raw_text TEXT NOT NULL,
    -- 384 dimensions for lightweight local testing models
    embedding vector(384), 
    validity_period tstzrange NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create the Vector Index (Using HNSW for high-speed semantic search)
-- Note: 'vector_cosine_ops' optimizes for cosine similarity
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
ON regulation_chunks 
USING hnsw (embedding vector_cosine_ops);

-- 5. Create the Bitemporal Time-Travel Index (Using GiST for date ranges)
CREATE INDEX IF NOT EXISTS idx_chunks_temporal_gist 
ON regulation_chunks 
USING gist (validity_period)