Agentic RegTech Compliance Pipeline
A robust, local-first, multi-agent regulatory technology (RegTech) system designed to automate financial compliance screening. This system implements a stateful, multi-hop agentic architecture capable of hybrid bitemporal retrieval and strict hallucination prevention via an LLM-based Faithfulness Judge.

🏗️ Architecture Overview
This pipeline operates on a decoupled infrastructure:

Vector DB (Standalone): Dedicated PostgreSQL instance with pgvector for regulatory chunks.

Observability & Customer Data: Docker Compose stack for Langfuse telemetry and the structured Customer database.

Agentic Logic: Python-based state machine powered by local LLMs (Ollama/llama3.2).

Interface: Streamlit application for end-to-end execution.

🛠️ Prerequisites
Python 3.10+

Docker & Docker Compose

Ollama (running locally with llama3.2 and nomic-embed-text models pulled)

🚀 Step-by-Step Setup Guide
Step 1: Initialize the Standalone Vector DB
We isolate the vector database to ensure high-performance semantic retrieval. Run this standalone Docker container to spin up PostgreSQL 16 with the pgvector extension:

Bash
docker run --name regtech-postgres \
  -e POSTGRES_DB=regtech \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=mysecretpassword \
  -p 5432:5432 \
  -d pgvector/pgvector:pg16
Step 2: Run Database Migrations
Initialize the vector schema (creating the regulation_chunks table with vector and bitemporal extensions).

Bash
# Ensure your virtual environment is active
python src/database/connection.py
(Verify the console output confirms the schema creation).

Step 3: Setup Langfuse & Customer DB
Langfuse provides our regulatory audit trails, and the Customer DB handles entity lookups.

Spin up the stack: Use the original docker-compose.yml to start the Langfuse and Customer DB services.

Bash
docker-compose up -d
Generate Telemetry Keys:

Open http://localhost:3000 in your browser.

Create your Organization and Project.

Navigate to settings and generate your Public Key (pk) and Secret Key (sk).

Configure the .env file: Update your Python environment with the generated keys and database connections:

Ini, TOML
LANGFUSE_HOST="http://localhost:3000"
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."

DB_CONN_STRING="host=127.0.0.1 port=5432 dbname=regtech user=postgres password=mysecretpassword"
# Add your Customer DB connection string here if it uses a different port
Step 4: Ingest the Regulatory Knowledge Base
Upload the 5 core regulatory documents (e.g., RBI Guidelines, MiFID II) located in your packs folder into the Vector DB. This step chunks the documents, embeds them using nomic-embed-text, and stores them in Postgres.

Bash
python src/database/vector_uploader.py
(Wait for the success message indicating all chunks are safely stored).

Step 5: Launch the Interface
With the data layer populated and telemetry active, start the Streamlit frontend to interact with the RegTech agents.

Bash
streamlit run src/app.py 
(Adjust the path to your specific Streamlit entry file if different).

✅ End-to-End Verification
To confirm the pipeline is fully runnable:

Submit a test transaction via the Streamlit UI.

Watch the terminal for agent state transitions (Supervisor -> Screening -> QA -> Report).

Open Langfuse (localhost:3000) and verify that a new Compliance_Pipeline trace was generated, capturing the full execution tree and QA faithfulness check.
