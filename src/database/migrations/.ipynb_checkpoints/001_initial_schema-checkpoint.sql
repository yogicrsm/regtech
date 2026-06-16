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
    metadata_payload JSONB NOT NULL, -- To store payment rails, currency codes, category tags
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
    embedding vector(384), -- Adjusted to 384 dimensions for our local lightweight testing model
    validity_period tstzrange NOT NULL, -- Handled natively via Postgres Timestamp with Time Zone Range
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create an optimized index for Bitemporal Pre-Filtering + Vector Similarity
CREATE INDEX IF NOT EXISTS idx_chunks_temporal_vector 
ON regulation_chunks 
USING gist (validity_period, embedding gist_vector_ops);