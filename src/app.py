import streamlit as st
import json
import time
import logging

# Force Streamlit to output logs to your terminal
logging.basicConfig(level=logging.INFO, format='%(message)s')

from agents.orchestrator import run_compliance_pipeline

st.set_page_config(page_title="FinServ RegTech Agent", page_icon="🏦", layout="wide")

st.title("🏦 Sovereign RegTech Compliance Pipeline")
st.markdown("""
This platform uses a **Deterministic State Machine** and **Local Llama 3.2** to screen cross-border transactions. 
It ensures 100% data residency (Tier 1 PII Redaction) and MRM-compliant auditability.
""")

default_txn = {
    "txn_id": "TXN-9981",
    "amount": 2000000,
    "currency": "USD",
    "originator_name": "John Doe", 
    "originator_account": "C-1023", 
    "beneficiary_country": "IR",
    "purpose": "consultancy"
}

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 Incoming Transaction")
    st.caption("Edit the JSON payload below to test different scenarios.")
    txn_input = st.text_area("Transaction Payload (JSON)", value=json.dumps(default_txn, indent=2), height=300)
    
    run_button = st.button("🚀 Run Agentic Pipeline", type="primary", use_container_width=True)

with col2:
    st.subheader("📊 Output & Audit Trail")
    
    if run_button:
        try:
            transaction = json.loads(txn_input)
            
            with st.spinner("Agents are analyzing the transaction... (Check terminal for live graph transitions)"):
                final_state = run_compliance_pipeline(transaction)
            
            st.success("✅ Pipeline Execution Complete")
            
            st.markdown("### 📋 Final Compliance Report")
            report = final_state.get("report", {})
            
            # --- THIS IS THE NEW LINE THAT PRINTS TO YOUR TERMINAL ---
            logging.info(f"\n✅ PIPELINE COMPLETE. FINAL REPORT:\n{json.dumps(report, indent=2)}\n")
            # ---------------------------------------------------------

            decision = report.get("final_decision", "UNKNOWN")
            if decision == "BLOCK":
                st.error(f"**Decision:** {decision}")
            elif decision == "HOLD":
                st.warning(f"**Decision:** {decision}")
            else:
                st.success(f"**Decision:** {decision}")
                
            st.write(f"**Executive Summary:** {report.get('executive_summary', 'N/A')}")
            st.write(f"**Required Actions:** {report.get('required_actions', 'N/A')}")
            
            with st.expander("🕵️ View Tier 1 Redacted Payload (Sent to Reasoning Agents)"):
                st.json(final_state.get("redacted_txn", {}))
                
            with st.expander("👤 View Extracted Customer Profile (From SQL DB)"):
                st.json(final_state.get("customer_profile", {}))

        except json.JSONDecodeError:
            st.error("Invalid JSON input. Please check your transaction payload.")
        except Exception as e:
            st.error(f"Pipeline Error: {str(e)}")
    else:
        st.info("Awaiting transaction submission...")
