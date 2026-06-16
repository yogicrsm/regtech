import os
import psycopg
from psycopg.rows import dict_row

# Hardcoded for local Day 1 sandbox testing environment
# Changed to 5434 to completely clear any Mac host loopback conflicts
DB_CONN_STRING = "host=127.0.0.1 port=5434 dbname=regtech user=postgres password=mysecretpassword"

def get_db_connection():
    """Establishes a connection to the local Postgres container."""
    try:
        conn = psycopg.connect(DB_CONN_STRING, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to Postgres container: {e}")
        raise e

def run_migrations():
    """Reads and executes our initial temporal schema migration script."""
    migration_path = "/Users/ryogeshwaran/workpace/regtech/src/database/migrations/001_initial_schema.sql"
    
    if not os.path.exists(migration_path):
        print(f"⚠️ Migration file not found at {migration_path}")
        return

    print("⚙️ Executing database migrations...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            with open(migration_path, "r") as f:
                sql_script = f.read()
            cursor.execute(sql_script)
        conn.commit()
        print("✅ Database schemas initialized with pgvector and tstzrange extensions.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration execution failed: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    # Test the module independently
    run_migrations()