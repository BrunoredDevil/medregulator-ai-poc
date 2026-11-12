import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="MedRegulator AI | QMSR CAPA Triage", layout="wide")
st.title("MedRegulator AI — FDA QMSR & ISO 13485 CAPA Triage")
st.caption("Automated Device History Record (DHR) Traceability, 5-Why Synthesis & 21 CFR Part 11 Audit Logging")

tab1, tab2 = st.tabs(["1. Incident Triage & QA Sign-Off", "2. Immutable Audit Trail"])

with tab1:
    col1, col2 = st.columns([1, 1.3])

    with col1:
        st.subheader("Incoming Quality Event")
        complaint_id = st.text_input("Complaint / Deviation ID", value="PMS-2026-0419")
        lot_number = st.selectbox("Affected Device Lot Number", ["LOT-2026-8841", "LOT-2026-9012", "LOT-2026-9155", "LOT-INVALID-999"])
        source_channel = st.selectbox("Trigger Source", ["Post-Market Complaint", "Line Inspection Failure", "Statistical Trend Alert"])
        patient_harm = st.checkbox("Potential Patient Harm / Serious Injury Reported (MDR Flag)")
        description = st.text_area(
            "Event Description",
            value="Hospital reported upstream occlusion alarm and reverse fluid backflow during infusion setup on CardioFlow unit.",
            height=110,
        )

        if st.button("Run Agentic Triage", type="primary"):
            res = requests.post(
                f"{API_URL}/triage",
                json={
                    "complaint_id": complaint_id,
                    "lot_number": lot_number,
                    "source_channel": source_channel,
                    "description": description,
                    "patient_harm_reported": patient_harm,
                },
            )
            st.session_state["triage_result"] = res.json()

    with col2:
        st.subheader("AI-Drafted CAPA & Compliance Guardrails")
        result = st.session_state.get("triage_result")
        if result:
            if result["guardrail_passed"]:
                st.success(f"Status: {result['status_label']} (Confidence: {result['draft_capa']['confidence_score']})")
            else:
                st.error(f"Status: {result['status_label']} (Confidence: {result['draft_capa']['confidence_score']})")

            with st.expander("Retrieved DHR & UDI Traceability (via MCP)", expanded=True):
                st.json(result["dhr_context"] or {"warning": "No DHR record matched"})

            draft = result["draft_capa"]
            st.markdown(f"**Classification:** `{draft['action_classification']}` | **MDR Reportable:** `{draft['mdr_reportable_flag']}`")
            st.markdown("**5-Why Root Cause Analysis:**")
            for step in draft["five_why_analysis"]:
                st.markdown(f"- {step}")

            st.markdown("**ISO 13485 / QMSR Citations:**")
            for cite in draft["iso_citations"]:
                st.code(cite)

            st.markdown(f"**Containment & Action Plan:** {draft['containment_and_action_plan']}")

            st.divider()
            reviewer = st.text_input("Electronic Signature (QA Engineer ID)", value="qa_lead_m.kene")
            c_approve, c_reject = st.columns(2)
            if c_approve.button("Approve & Sync to QMS", use_container_width=True):
                sig = requests.post(
                    f"{API_URL}/signoff",
                    json={"complaint_id": complaint_id, "reviewer_id": reviewer, "decision": "APPROVED_SYNC_QMS", "capa_payload": draft},
                ).json()
                st.toast(f"Signed & Hashed: {sig['sha256_hash'][:16]}...")
            if c_reject.button("Reject for Manual Rework", use_container_width=True):
                sig = requests.post(
                    f"{API_URL}/signoff",
                    json={"complaint_id": complaint_id, "reviewer_id": reviewer, "decision": "REJECTED_MANUAL_REWORK", "capa_payload": draft},
                ).json()
                st.toast("Logged rejection in audit trail.")

with tab2:
    st.subheader("Immutable Quality System Audit Log")
    if st.button("Refresh Logs"):
        st.rerun()
    logs = requests.get(f"{API_URL}/audit-logs").json()
    st.dataframe(logs, use_container_width=True)