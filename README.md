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
First chunk the 6 source documents (RBI, MiFID II, ESMA, Basel III), then embed and upload to the vector store:

Bash
python src/parsers/rule_based_chunker.py
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

## 🧪 Running the Evaluation Suite

```bash
python src/evaluation/run_evals.py
```

Runs 20 QA pairs across Basel III, MiFID II, and RBI KYC regulations and scores 4 metrics using an LLM-as-judge. Results are saved to `data/evaluation/reports/`.

## 📊 Sample Outputs

### Regulatory Q&A (Tab 1)

```json
{
  "answer": "Under Basel III, banks must maintain a minimum CET1 capital ratio of 4.5% of risk-weighted assets. Including the capital conservation buffer of 2.5%, the effective minimum rises to 7%.",
  "citations": ["basel_iii_framework / Chunk 12", "basel_iii_framework / Chunk 15"],
  "source_documents": ["basel_iii_framework"],
  "confidence": "HIGH",
  "coverage_note": "Evidence fully supports the answer. Both thresholds explicitly stated in retrieved context."
}
```

### Transaction Screening (Tab 2)

```json
{
  "final_decision": "BLOCK",
  "risk_level": "HIGH",
  "executive_summary": "Transaction to a non-KYC verified counterparty in a sanctioned jurisdiction. Multiple regulatory obligations triggered.",
  "regulatory_basis": ["RBI KYC Master Direction 2016 — Section 16 (EDD)", "Basel III Large Exposures — Article 395"],
  "required_actions": ["File STR with FIU-IND within 7 days", "Escalate to Compliance Officer", "Do not tip off counterparty"],
  "citations": ["rbi_kyc_2016 / Chunk 8", "basel_iii_framework / Chunk 34"]
}
```

### Evaluation Report Summary

```
=== FINAL EVALUATION REPORT ===
Total Test Cases     : 20
Avg Faithfulness     : 4.10 / 5.0
Avg Relevance        : 3.90 / 5.0
Avg Context Precision: 0.7200
Avg Context Recall   : 0.6800
Failures (<3/5)      : 1
Detailed report saved to data/evaluation/reports/eval_run_20260616_120000.json
```
