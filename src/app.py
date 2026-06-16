import streamlit as st
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

from agents.orchestrator import (
    run_compliance_pipeline,
    run_qa_pipeline,
    run_impact_pipeline,
    run_batch_report_pipeline,
)

st.set_page_config(page_title="FinServ RegTech Agent", page_icon="🏦", layout="wide")

st.title("🏦 Sovereign RegTech Compliance Pipeline")
st.markdown(
    "Local Llama 3.2 + pgvector · 100% data residency · MRM-compliant audit trail"
)

tab_qa, tab_screen, tab_impact, tab_batch = st.tabs([
    "🔍 Regulatory Q&A",
    "🕵️ Transaction Screening",
    "⚖️ Impact Analysis",
    "📊 Batch Report",
])

# ─────────────────────────────────────────────
# Tab 1: Natural-language Regulatory Q&A
# ─────────────────────────────────────────────
with tab_qa:
    st.subheader("Ask a Regulatory Question")
    st.caption(
        "Type a question about Basel III, MiFID II, or RBI guidelines. "
        "The system retrieves relevant regulation chunks and generates a cited answer."
    )

    sample_questions = [
        "What are the Tier 1 capital adequacy requirements under Basel III?",
        "What KYC obligations apply to cross-border payments above $10,000 under RBI guidelines?",
        "What appropriateness assessment is required for complex products under MiFID II?",
    ]
    selected = st.selectbox("Or pick a sample question:", ["(type your own)"] + sample_questions)
    default_q = "" if selected == "(type your own)" else selected
    query = st.text_input("Your question:", value=default_q, placeholder="Enter your regulatory question...")

    if st.button("🔍 Get Answer", type="primary", key="qa_btn"):
        if not query.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Searching regulatory knowledge base..."):
                state = run_qa_pipeline(query)

            answer = state.get("qa_answer", {})
            confidence = answer.get("confidence", "LOW")

            if confidence == "HIGH":
                st.success(f"Confidence: {confidence}")
            elif confidence == "MED":
                st.warning(f"Confidence: {confidence}")
            else:
                st.error(f"Confidence: {confidence}")

            st.markdown("### Answer")
            st.write(answer.get("answer", "No answer generated."))

            citations = answer.get("citations", [])
            if citations:
                st.markdown("### Citations")
                for c in citations:
                    st.markdown(f"- `{c}`")

            if answer.get("coverage_note"):
                st.info(f"Coverage note: {answer['coverage_note']}")

            with st.expander("📚 Retrieved Context Chunks"):
                st.json(answer.get("retrieved_context", []))

# ─────────────────────────────────────────────
# Tab 2: Transaction Screening (existing flow)
# ─────────────────────────────────────────────
with tab_screen:
    st.subheader("Screen a Transaction")
    st.caption(
        "Submit a transaction payload. The pipeline redacts PII, retrieves applicable "
        "regulations via hybrid search + RRF re-ranking, and produces a risk-rated report."
    )

    default_txn = {
        "txn_id": "TXN-9981",
        "amount": 2000000,
        "currency": "USD",
        "originator_name": "John Doe",
        "originator_account": "C-1023",
        "beneficiary_country": "IR",
        "purpose": "consultancy",
    }

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Transaction Payload (JSON)**")
        txn_input = st.text_area(
            "Edit to test different scenarios:",
            value=json.dumps(default_txn, indent=2),
            height=300,
            label_visibility="collapsed",
        )
        run_btn = st.button("🚀 Run Screening Pipeline", type="primary", use_container_width=True, key="screen_btn")

    with col2:
        st.markdown("**Output & Audit Trail**")
        if run_btn:
            try:
                transaction = json.loads(txn_input)
                with st.spinner("Agents analyzing transaction..."):
                    final_state = run_compliance_pipeline(transaction)

                st.success("Pipeline Execution Complete")

                report = final_state.get("report", {})
                logging.info(f"\nFINAL REPORT:\n{json.dumps(report, indent=2)}\n")

                decision = report.get("final_decision", "UNKNOWN")
                if decision == "BLOCK":
                    st.error(f"Decision: **{decision}**")
                elif decision == "HOLD":
                    st.warning(f"Decision: **{decision}**")
                else:
                    st.success(f"Decision: **{decision}**")

                st.write(f"**Executive Summary:** {report.get('executive_summary', 'N/A')}")
                st.write(f"**Required Actions:** {report.get('required_actions', 'N/A')}")

                reg_basis = report.get("regulatory_basis", [])
                if reg_basis:
                    st.markdown("**Regulatory Basis:**")
                    for r in reg_basis:
                        st.markdown(f"- `{r}`")

                with st.expander("🕵️ Tier 1 Redacted Payload"):
                    st.json(final_state.get("redacted_txn", {}))

                with st.expander("👤 Customer Profile (from SQL DB)"):
                    st.json(final_state.get("customer_profile", {}))

                with st.expander("🔎 QA Faithfulness Check"):
                    st.json(final_state.get("qa_result", {}))

                with st.expander("📚 Retrieved Regulation Chunks"):
                    st.json(final_state.get("context", []))

            except json.JSONDecodeError:
                st.error("Invalid JSON. Please check the transaction payload.")
            except Exception as e:
                st.error(f"Pipeline error: {e}")
        else:
            st.info("Awaiting transaction submission...")

# ─────────────────────────────────────────────
# Tab 3: Regulatory Change Impact Analysis
# ─────────────────────────────────────────────
with tab_impact:
    st.subheader("Regulatory Change Impact Analysis")
    st.caption(
        "Paste the text of a new circular or amendment. The agent will cross-reference "
        "it against existing policies and flag which transaction types are affected."
    )

    sample_circular = (
        "RBI Circular: Effective 2024-04-01, all cross-border remittances above USD 500,000 "
        "to counterparties in FATF grey-listed jurisdictions require prior approval from the "
        "Compliance Head and must be reported to the Financial Intelligence Unit within 24 hours."
    )

    circular_text = st.text_area(
        "Paste new circular / amendment text:",
        value=sample_circular,
        height=200,
    )

    if st.button("⚖️ Analyze Impact", type="primary", key="impact_btn"):
        if not circular_text.strip():
            st.warning("Please paste the circular text.")
        else:
            with st.spinner("Cross-referencing against regulatory knowledge base..."):
                state = run_impact_pipeline(circular_text)

            impact = state.get("impact_result", {})

            level = impact.get("impact", "UNKNOWN")
            if level == "MAJOR":
                st.error(f"Impact Level: **{level}**")
            elif level == "MINOR":
                st.warning(f"Impact Level: **{level}**")
            else:
                st.success(f"Impact Level: **{level}**")

            needs_update = impact.get("needs_policy_update", False)
            st.write(f"**Policy Update Required:** {'Yes' if needs_update else 'No'}")

            with st.expander("📚 Related Regulation Chunks Retrieved"):
                st.json(state.get("context", []))

# ─────────────────────────────────────────────
# Tab 4: Batch Compliance Report
# ─────────────────────────────────────────────
with tab_batch:
    st.subheader("Batch Compliance Report")
    st.caption(
        "Submit a JSON array of transactions to generate an aggregated compliance report "
        "suitable for the audit committee."
    )

    default_batch = [
        {
            "txn_id": "TXN-001",
            "amount": 2000000,
            "currency": "USD",
            "originator_account": "C-1023",
            "beneficiary_country": "IR",
            "purpose": "consultancy",
        },
        {
            "txn_id": "TXN-002",
            "amount": 500000,
            "currency": "EUR",
            "originator_account": "C-2045",
            "beneficiary_country": "DE",
            "purpose": "investment",
        },
        {
            "txn_id": "TXN-003",
            "amount": 150000,
            "currency": "INR",
            "originator_account": "C-3012",
            "beneficiary_country": "IN",
            "purpose": "priority_sector_lending",
        },
    ]

    col_a, col_b = st.columns([1, 1])

    with col_a:
        period = st.text_input("Reporting Period:", value="2024-Q2")
        batch_input = st.text_area(
            "Transaction Array (JSON):",
            value=json.dumps(default_batch, indent=2),
            height=350,
        )
        batch_btn = st.button("📊 Generate Report", type="primary", use_container_width=True, key="batch_btn")

    with col_b:
        if batch_btn:
            try:
                transactions = json.loads(batch_input)
                if not isinstance(transactions, list):
                    st.error("Input must be a JSON array of transactions.")
                else:
                    with st.spinner(f"Screening {len(transactions)} transactions..."):
                        state = run_batch_report_pipeline(transactions, period=period)

                    report = state.get("batch_report", {})

                    if "error" in report:
                        st.error(report["error"])
                    else:
                        st.success(f"Report generated for {report.get('total_transactions')} transactions")

                        risk = report.get("risk_summary", {})
                        dec = report.get("decision_summary", {})

                        m1, m2, m3 = st.columns(3)
                        m1.metric("HIGH Risk", risk.get("HIGH", 0))
                        m2.metric("MED Risk", risk.get("MED", 0))
                        m3.metric("LOW Risk", risk.get("LOW", 0))

                        d1, d2, d3 = st.columns(3)
                        d1.metric("BLOCKED", dec.get("BLOCK", 0))
                        d2.metric("HELD", dec.get("HOLD", 0))
                        d3.metric("ALLOWED", dec.get("ALLOW", 0))

                        if report.get("systemic_observations"):
                            st.markdown("**Systemic Observations:**")
                            for obs in report["systemic_observations"]:
                                st.markdown(f"- {obs}")

                        if report.get("required_actions"):
                            st.markdown("**Required Actions:**")
                            for act in report["required_actions"]:
                                st.markdown(f"- {act}")

                        with st.expander("📋 Individual Transaction Results"):
                            st.json(report.get("individual_results", []))

                        with st.expander("📄 Full Report JSON"):
                            st.json(report)

            except json.JSONDecodeError:
                st.error("Invalid JSON. Please check the transaction array.")
            except Exception as e:
                st.error(f"Batch pipeline error: {e}")
        else:
            st.info("Submit a transaction batch to generate the report.")
