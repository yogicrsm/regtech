import psycopg

# Your isolated Docker Postgres connection
DB_CONN_STRING = "host=127.0.0.1 port=5434 dbname=regtech user=postgres password=mysecretpassword"

def reset_schema():
    print("🔄 Resetting database schema for Nomic 768-dimension vectors...")
    try:
        # Using autocommit=True so we don't have to manually commit the DDL changes
        with psycopg.connect(DB_CONN_STRING, autocommit=True) as conn:
            with conn.cursor() as cursor:
                
                print("   🗑️  Dropping old 384-dimension table...")
                cursor.execute("DROP TABLE IF EXISTS regulation_chunks CASCADE;")

                print("   🏗️  Creating new table with vector(768)...")
                cursor.execute("""
                    CREATE TABLE regulation_chunks (
                        chunk_id SERIAL PRIMARY KEY,
                        obligation_id VARCHAR(64),
                        jurisdiction VARCHAR(4) NOT NULL,
                        doc_id VARCHAR(64) NOT NULL,
                        citation VARCHAR(256) NOT NULL,
                        raw_text TEXT NOT NULL,
                        embedding vector(768),
                        validity_period tstzrange NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                print("   ⚡ Rebuilding HNSW semantic and GiST temporal indexes...")
                cursor.execute("""
                    CREATE INDEX idx_chunks_embedding_hnsw 
                    ON regulation_chunks 
                    USING hnsw (embedding vector_cosine_ops);
                    
                    CREATE INDEX idx_chunks_temporal_gist 
                    ON regulation_chunks 
                    USING gist (validity_period);
                """)
                
                print("✅ Schema successfully upgraded. Ready for Nomic embeddings.")
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    reset_schema()