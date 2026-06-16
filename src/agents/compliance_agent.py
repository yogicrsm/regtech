import os
import json
import ollama
from dotenv import load_dotenv

# Import the hybrid search tool
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.hybrid_search import search_regulations

load_dotenv()

# ========================================================
# ⚙️ LOCAL-FIRST CONFIGURATION
# Switch 'provider' to 'gemini' later when ready for cloud.
# ========================================================
AGENT_CONFIG = {
    "routing": {
        "classification_tier": {
            "provider": "ollama",
            "model": "llama3.2",
            "temperature": 0.1
        },
        "generation_tier": {
            "provider": "ollama",  # Switched from gemini to ollama for air-gapped dev
            "model": "llama3.2",   # Using the same local model for reasoning
            "temperature": 0.2
        }
    },
    "security": {
        "redact_pii": True
    }
}

class LocalComplianceAgent:
    def __init__(self, config: dict):
        self.config = config

    def _local_classify_and_redact(self, transaction: dict) -> dict:
        """TIER 1: Pre-processes transaction to extract keywords and scrub entities."""
        print(f"🔒 TIER 1: Running Local Redaction via {self.config['routing']['classification_tier']['model']}...")
        
        prompt = f"""
        Analyze this transaction payload.
        1. Replace the 'sender' and 'recipient_entity' values with '[REDACTED_ENTITY]' for privacy protection.
        2. Identify the single most important compliance keyword (e.g., 'KYC', 'Bonds', 'Capital', 'Liquidity').
        
        Return ONLY a JSON object exactly like this:
        {{
            "redacted_txn": {{...}},
            "search_keyword": "extracted_keyword"
        }}

        Payload: {json.dumps(transaction)}
        """
        
        try:
            response = ollama.chat(
                model=self.config['routing']['classification_tier']['model'],
                messages=[{'role': 'user', 'content': prompt}],
                format='json'
            )
            return json.loads(response['message']['content'])
        except Exception as e:
            print(f"⚠️ Local classification step failed: {e}")
            return {"redacted_txn": transaction, "search_keyword": "KYC"}

    def _local_generate_report(self, redacted_txn: dict, regulations: list) -> str:
        """TIER 2: Executes full regulatory analysis locally without outbound internet calls."""
        print(f"🧠 TIER 2: Running Local Compliance Synthesis via {self.config['routing']['generation_tier']['model']}...")
        
        prompt = f"""
        You are an expert financial compliance officer. Review this transaction against the regulatory context provided.
        You must return a compliance report strictly structured as a JSON object matching this schema:
        {{
            "transaction_status": "APPROVED" or "HOLD" or "REJECTED",
            "risk_rating": "LOW" or "MEDIUM" or "HIGH" or "CRITICAL",
            "applicable_regulations": ["list of document IDs"],
            "citations": ["exact textual quotes from the regulation context used to back your choice"],
            "required_actions": ["concrete steps the compliance desk must execute next"],
            "reasoning": "summary of the legal or regulatory logic applied"
        }}

        TRANSACTION PAYLOAD:
        {json.dumps(redacted_txn, indent=2)}
        
        REGULATORY CONTEXT FETCHED FROM VECTOR DATABASE:
        {json.dumps(regulations, indent=2)}
        """
        
        try:
            response = ollama.chat(
                model=self.config['routing']['generation_tier']['model'],
                messages=[{'role': 'user', 'content': prompt}],
                format='json'
            )
            return response['message']['content']
        except Exception as e:
            return json.dumps({"error": f"Local generation tier failed to compile report: {str(e)}"})

    def screen_transaction(self, transaction: dict) -> dict:
        # 1. Redaction
        prep_data = self._local_classify_and_redact(transaction)
        redacted_txn = prep_data.get("redacted_txn", transaction)
        keyword = prep_data.get("search_keyword", "KYC")
        
        # 2. ENHANCED RETRIEVAL (The "Context-Aware" fix)
        semantic_query = f"""
        Regulatory review for {transaction.get('instrument_type')}.
        Jurisdiction: {transaction.get('recipient_jurisdiction')}
        KYC Status: {transaction.get('kyc_verified')}
        Amount: {transaction.get('amount_usd')}
        """
        context = search_regulations(semantic_query=semantic_query, keyword=keyword, top_k=5)
        
        # 3. Screening (Returning JSON dict instead of string)
        screening_raw = self._local_generate_report(redacted_txn, context)
        screening_result = json.loads(screening_raw)
        
        # Return all components for the QA node to use
        return {
            "redacted_txn": redacted_txn,
            "context": context,
            "screening_result": screening_result
        }

if __name__ == "__main__":
    sample_transaction = {
        "transaction_id": "TXN-99482-XB",
        "date": "2024-05-15",
        "amount_usd": 2000000,
        "sender": "John Doe Wealth Management",
        "recipient_entity": "ShadowCorp Offshore Ltd",
        "recipient_jurisdiction": "High-Risk FATF Listed Jurisdiction",
        "kyc_verified": False,
        "instrument_type": "Cross-border wire transfer"
    }
    
    agent = LocalComplianceAgent(config=AGENT_CONFIG)
    assessment = agent.screen_transaction(sample_transaction)
    
    print("\n📊 --- FINAL LOCAL COMPLIANCE REPORT ---")
    try:
        parsed_report = json.loads(assessment)
        print(json.dumps(parsed_report, indent=2))
    except Exception:
        print(assessment)