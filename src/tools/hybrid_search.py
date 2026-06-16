import psycopg
import ollama
from datetime import datetime

# Database and Model configs
DB_CONN_STRING = "host=127.0.0.1 port=5434 dbname=regtech user=postgres password=mysecretpassword"
EMBEDDING_MODEL = "nomic-embed-text"

def search_regulations(
    semantic_query: str, 
    transaction_date: str = None, 
    keyword: str = None, 
    top_k: int = 3
) -> list:
    """
    Performs a Hybrid Bitemporal Search against the regulatory database.
    """
    # 1. Default to today if no transaction date is provided
    if not transaction_date:
        transaction_date = datetime.now().strftime("%Y-%m-%d")

    # 2. Convert the natural language query into a vector using local Ollama
    try:
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=semantic_query)
        query_vector = response['embedding']
    except Exception as e:
        print(f"❌ Failed to embed query: {e}")
        return []

    # 3. Execute the Hybrid SQL Search
    try:
        with psycopg.connect(DB_CONN_STRING) as conn:
            with conn.cursor() as cursor:
                
                # The SQL combines Vector Math (<=>), Date Intersection (@>), and Keyword matching (ILIKE)
                sql_query = """
                    SELECT 
                        jurisdiction, 
                        doc_id, 
                        citation, 
                        raw_text,
                        1 - (embedding <=> %s::vector) AS similarity_score
                    FROM regulation_chunks
                    WHERE validity_period @> %s::timestamptz
                """
                
                params = [query_vector, transaction_date]

                # Add Keyword filter if provided
                if keyword:
                    sql_query += " AND raw_text ILIKE %s "
                    params.append(f"%{keyword}%")

                # Order by closest semantic match
                sql_query += " ORDER BY embedding <=> %s::vector LIMIT %s;"
                params.extend([query_vector, top_k])

                cursor.execute(sql_query, tuple(params))
                results = cursor.fetchall()

                # Format the results cleanly
                formatted_results = []
                for row in results:
                    formatted_results.append({
                        "jurisdiction": row[0],
                        "document": row[1],
                        "citation": row[2],
                        "text": row[3],
                        "relevance_score": round(row[4], 4)
                    })
                
                return formatted_results

    except Exception as e:
        print(f"❌ Search execution failed: {e}")
        return []

if __name__ == "__main__":
    # --- Local Sandbox Test ---
    print("🔍 Testing Hybrid Retrieval Engine...\n")
    
    # Let's test one of the exact scenarios from your assignment prompt:
    # "Cross-border payment of $2M to a non-KYC verified entity in a high-risk jurisdiction"
    
    test_query = "What are the rules for cross-border transactions to non-KYC entities in high-risk jurisdictions?"
    test_keyword = "KYC" # Forcing it to ensure the keyword appears
    test_date = "2024-05-15"
    
    print(f"Query: '{test_query}'")
    print(f"Keyword Required: '{test_keyword}'")
    print(f"Transaction Date: {test_date}\n")
    
    results = search_regulations(
        semantic_query=test_query,
        transaction_date=test_date,
        keyword=test_keyword,
        top_k=2
    )
    
    if not results:
        print("⚠️ No results found.")
    else:
        for i, res in enumerate(results, 1):
            print(f"--- Result {i} (Score: {res['relevance_score']}) ---")
            print(f"📜 Doc: {res['document']} | 📍 {res['citation']} | 🌍 {res['jurisdiction']}")
            # Print just the first 200 characters so it doesn't flood the terminal
            print(f"📝 Text: {res['text'][:200]}...\n")