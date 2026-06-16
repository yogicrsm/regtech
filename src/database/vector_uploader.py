import os
import json
import psycopg
import ollama

DB_CONN_STRING = "host=127.0.0.1 port=5434 dbname=regtech user=postgres password=mysecretpassword"
EMBEDDING_MODEL = "nomic-embed-text" 

def upload_chunks_to_db():
    print(f"🚀 Initializing Fault-Tolerant Upload with {EMBEDDING_MODEL} (768 Dimensions)...")
    json_dir = "/Users/ryogeshwaran/workpace/regtech/data/processed_json"
    
    try:
        conn = psycopg.connect(DB_CONN_STRING)
        cursor = conn.cursor()

        for filename in os.listdir(json_dir):
            if not filename.endswith("_chunks.json"): continue
                
            filepath = os.path.join(json_dir, filename)
            with open(filepath, "r") as f:
                chunks = json.load(f)
                
            print(f"\n📦 Processing {len(chunks)} chunks from {filename}...")
            
            successful = 0
            failed = 0
            
            for chunk in chunks:
                raw_text = chunk["raw_text"]
                
                # Failsafe: Hard truncate at ~25,000 characters to guarantee it fits the 8k token limit
                if len(raw_text) > 25000:
                    raw_text = raw_text[:25000]
                    
                try:
                    # Explicitly tell Ollama to use the maximum context window
                    response = ollama.embeddings(
                        model=EMBEDDING_MODEL, 
                        prompt=raw_text,
                        options={'num_ctx': 8192} 
                    )
                    vector = response['embedding']
                    
                    cursor.execute("""
                        INSERT INTO regulation_chunks 
                        (jurisdiction, doc_id, citation, raw_text, embedding, validity_period)
                        VALUES (%s, %s, %s, %s, %s::vector, %s::tstzrange)
                    """, (
                        chunk["jurisdiction"],
                        chunk["doc_id"],
                        chunk["citation"],
                        chunk["raw_text"],
                        vector,
                        "[2023-01-01, infinity)" 
                    ))
                    successful += 1
                    
                except Exception as e:
                    failed += 1
                    # Log the error but DO NOT crash the script
                    print(f"   ⚠️ Skipping anomalous chunk ({chunk['citation']}): {e}")
                    continue 
            
            print(f"   ↳ ✅ {successful} inserted | ❌ {failed} skipped")
                
        conn.commit()
        print("\n🏆 Success: All valid documents embedded and stored in PostgreSQL.")
        
    except Exception as e:
        print(f"❌ Critical Database failure: {e}")
        if 'conn' in locals(): conn.rollback()
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    upload_chunks_to_db()