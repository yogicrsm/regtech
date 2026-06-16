import json
import logging
from agents.orchestrator import run_compliance_pipeline

# Setup logging to see the StateGraph transitions
logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    # 1. Define the mock transaction from Scenario 2A
    test_transaction = {
        "txn_id": "TXN-9981",
        "amount": 2000000,
        "currency": "USD",
        "originator_name": "John Doe",  # PII that the Redactor MUST scrub
        "originator_account": "C-1023",
        "beneficiary_country": "IR",    # High-risk jurisdiction
        "purpose": "consultancy"
    }

    print("\n🚀 STARTING AGENTIC COMPLIANCE PIPELINE...")
    print(f"📥 Raw Input: {json.dumps(test_transaction, indent=2)}\n")
    print("-" * 50)

    # 2. Execute the State Machine
    final_state = run_compliance_pipeline(test_transaction)

    print("-" * 50)
    print("✅ PIPELINE EXECUTION COMPLETE.\n")
    
    # 3. Print the auditable results from the final state
    print("🕵️  Redacted Payload (Tier 1 Privacy):")
    print(json.dumps(final_state.get("redacted_txn", {}), indent=2))
    
    print("\n📊 Final Compliance Report:")
    print(json.dumps(final_state.get("report", {}), indent=2))

if __name__ == "__main__":
    main()
