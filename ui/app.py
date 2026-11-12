import os
from datetime import datetime, timezone
import requests
import streamlit as st

try:
    API_URL = st.secrets["API_URL"].rstrip("/")
except Exception:
    API_URL = os.getenv("API_URL", "https://medregulator-ai-poc.onrender.com").rstrip("/")

st.set_page_config(page_title="MedRegulator AI | QMSR CAPA Triage", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
.hero-banner { background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f766e 100%); color: #f8fafc; padding: 1.4rem 1.8rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); margin-bottom: 1.2rem; }
.hero-banner h2 { margin: 0; font-size: 1.65rem; font-weight: 700; color: #ffffff; }
.hero-banner p { margin: 0.35rem 0 0 0; color: #cbd5e1; font-size: 0.95rem; }
.pill-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; }
.pill { background: rgba(255,255,255,0.12); color: #e2e8f0; padding: 0.2rem 0.65rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
.why-card { background: #f8fafc; border-left: 4px solid #0f766e; padding: 0.65rem 0.9rem; margin-bottom: 0.5rem; border-radius: 6px; color: #0f172a; font-size: 0.92rem; }
.hash-box { font-family: monospace; background: #0f172a; color: #38bdf8; padding: 0.6rem 0.85rem; border-radius: 6px; font-size: 0.82rem; word-break: break-all; }
</style>
""", unsafe_allow_html=True)

SCENARIOS = {
    "Sterile Barrier Peel (LOT-2026-8841)": {"complaint_id": "CMP-2026-0412", "lot_number": "LOT-2026-8841", "source_channel": "Hospital Post-Market Surveillance", "description": "During pre-operative setup, the Tyvek pouch seal on the cardiac catheter delivery system peeled open with incomplete fusion along the distal edge, compromising sterile barrier integrity prior to patient contact."},
    "Sensor Drift - Telemetry Out of Spec (LOT-2026-9104)": {"complaint_id": "CMP-2026-0519", "lot_number": "LOT-2026-9104", "source_channel": "Field Service & Calibration Log", "description": "Intraoperative pressure transducer exhibited a +12 mmHg zero-point drift after 20 minutes of continuous operation, triggering repeated audible alarms during catheterization."},
    "Custom Complaint / Deviation": {"complaint_id": "CMP-2026-0900", "lot_number": "LOT-2026-8841", "source_channel": "Clinical Feedback Portal", "description": ""},
}

def build_md(cid, lot, rev, inc, res, sig):
    d = res["draft_capa"]
    dhr = res.get("dhr_context") or {}
    dhr_lines = [f"| {k} | {v} |" for k, v in dhr.items()] if dhr else ["| Status | No matching DHR record found |"]
    decision = sig.get("decision", "PENDING_QAREVIEW") if sig else "PENDING_QAREVIEW"
    ts = sig.get("timestamp", "Pending Sign-Off") if sig else "Pending Sign-Off"
    sha = sig.get("sha256_hash", "Unsigned Draft") if sig else "Unsigned Draft"
    return "\n".join([
        f"# FDA QMSR / ISO 13485:2016 CAPA Investigation Report ({cid})",
        f"**Lot Number:** `{lot}` | **Source:** {inc.get('source_channel', '')} | **Classification:** `{d.get('action_classification', '')}`",
        f"**FDA MDR Reportable (21 CFR 803):** `{d.get('mdr_reportable_flag', '')}` | **Confidence:** `{d.get('confidence_score', '')}`",
        "", "## 1. Event Description", inc.get("description", ""),
        "", "## 2. Device History Record (DHR) Traceability", "| Field | Value |", "|---|---|", *dhr_lines,
        "", "## 3. 5-Why Root Cause Analysis", *[f"- {step}" for step in d.get("five_why_analysis", [])],
        "", "## 4. Regulatory & ISO Citations", *[f"- `{cite}`" for cite in d.get("iso_citations", [])],
        "", "## 5. Containment & CAPA Action Plan", d.get("containment_and_action_plan", ""),
        "", "## 6. 21 CFR Part 11 Electronic Sign-Off & Audit Record",
        f"- **QA Reviewer:** `{rev}`", f"- **Disposition:** `{decision}`", f"- **Timestamp (UTC):** `{ts}`", f"- **SHA-256 Hash:** `{sha}`",
    ])
st.markdown("""
<div class="hero-banner">
    <h2>MedAgentQMSR | CAPA &amp; PMS Triage Command Center</h2>
    <p>Automated Device History Record (DHR) Traceability, 5-Why Root Cause Synthesis &amp; 21 CFR Part 11 Electronic Sign-Off</p>
    <div class="pill-row">
        <span class="pill">FDA 21 CFR Part 820 (QMSR)</span>
        <span class="pill">ISO 13485:2016 Clause 8.5</span>
        <span class="pill">21 CFR Part 11 SHA-256 Audit</span>
        <span class="pill">LangGraph Agentic Workflow</span>
    </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("QA Reviewer Session")
    reviewer = st.text_input("Reviewer ID (21 CFR Part 11)", value="QA-LEAD-MIHIR")
    scenario_name = st.selectbox("Load Sample Complaint Scenario", list(SCENARIOS.keys()))
    st.divider()
    st.subheader("Backend Connectivity")
    try:
        health_res = requests.get(f"{API_URL}/audit-logs", timeout=8)
        st.success(f"API Online | {len(health_res.json())} Audit Records") if health_res.ok else st.warning(f"API Responded {health_res.status_code}")
    except Exception:
        st.info("Backend waking up (Render free tier cold start takes ~30s).")
    st.caption(f"Endpoint: `{API_URL}`")

selected = SCENARIOS[scenario_name]
tab1, tab2 = st.tabs(["1. CAPA Triage & QA Disposition", "2. Immutable Audit Trail (21 CFR Part 11)"])

with tab1:
    left, right = st.columns([1, 1.35], gap="large")
    with left:
        st.subheader("Post-Market Complaint Intake")
        with st.container(border=True):
            c1, c2 = st.columns(2)
            complaint_id = c1.text_input("Complaint / Deviation ID", value=selected["complaint_id"])
            lot_number = c2.text_input("Affected Device Lot / UDI", value=selected["lot_number"])
            source_channel = st.text_input("Source Channel", value=selected["source_channel"])
            description = st.text_area("Clinical / Quality Event Description", value=selected["description"], height=150)
            run_btn = st.button("Run Agentic CAPA Triage", type="primary", use_container_width=True)
        if run_btn:
            if not description.strip():
                st.warning("Please enter an event description before running triage.")
            else:
                payload = {"complaint_id": complaint_id, "lot_number": lot_number, "source_channel": source_channel, "description": description}
                with st.spinner("Executing LangGraph Triage..."):
                    try:
                        res = requests.post(f"{API_URL}/triage", json=payload, timeout=60)
                        if res.ok:
                            st.session_state["triage_result"] = res.json()
                            st.session_state["triage_incident"] = payload
                            st.session_state.pop("signoff_result", None)
                        else:
                            st.error(f"Triage Error ({res.status_code}): {res.text}")
                    except Exception as exc:
                        st.error(f"Connection Error: {exc}")
    with right:
        st.subheader("Regulatory Dossier & QA Sign-Off")
        result = st.session_state.get("triage_result")
        incident = st.session_state.get("triage_incident", {})
        if not result:
            st.info("Select a scenario or enter a complaint on the left, then click Run Agentic CAPA Triage.")
        else:
            draft = result["draft_capa"]
            dhr = result.get("dhr_context") or {}
            m1, m2, m3 = st.columns(3)
            m1.metric("Action Classification", draft.get("action_classification", "N/A"))
            m2.metric("FDA MDR (21 CFR 803)", "REPORTABLE" if draft.get("mdr_reportable_flag", False) else "NON-REPORTABLE")
            conf = draft.get("confidence_score", 0.0)
            m3.metric("Traceability Confidence", f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf))
            for flag in result.get("compliance_flags", []):
                st.warning(f"Guardrail Alert: {flag}")
            w_dhr, w_why, w_plan = st.tabs(["DHR Traceability", "5-Why Root Cause", "CAPA Action Plan"])
            with w_dhr:
                st.table([{"DHR Field": k, "Value": str(v)} for k, v in dhr.items()]) if dhr else st.warning("No matching DHR record found.")
            with w_why:
                for item in draft.get("five_why_analysis", []):
                    st.markdown(f"<div class='why-card'>{item}</div>", unsafe_allow_html=True)
                st.markdown("**Regulatory Citations:** " + " , ".join(f"`{c}`" for c in draft.get("iso_citations", [])))
            with w_plan:
                st.info(draft.get("containment_and_action_plan", ""))
            st.divider()
            st.markdown("### 21 CFR Part 11 Electronic Sign-Off")
            c_app, c_rej = st.columns(2)
            if c_app.button("Approve & Sync to QMS", type="primary", use_container_width=True):
                sig = requests.post(f"{API_URL}/signoff", json={"complaint_id": incident.get("complaint_id", complaint_id), "reviewer_id": reviewer, "decision": "APPROVED_SYNC_QMS", "capa_payload": draft}, timeout=30).json()
                sig["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                sig["decision"] = "APPROVED_SYNC_QMS"
                st.session_state["signoff_result"] = sig
            if c_rej.button("Reject for Manual Rework", use_container_width=True):
                sig = requests.post(f"{API_URL}/signoff", json={"complaint_id": incident.get("complaint_id", complaint_id), "reviewer_id": reviewer, "decision": "REJECTED_MANUAL_REWORK", "capa_payload": draft}, timeout=30).json()
                sig["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                sig["decision"] = "REJECTED_MANUAL_REWORK"
                st.session_state["signoff_result"] = sig
            sig_res = st.session_state.get("signoff_result")
            if sig_res:
                st.success(f"Electronic Sign-Off Verified | Decision: {sig_res['decision']} | UTC: {sig_res.get('timestamp', '')}")
                st.markdown(f"<div class='hash-box'>SHA-256 Audit Hash: {sig_res.get('sha256_hash', '')}</div>", unsafe_allow_html=True)
            cid, lot = incident.get("complaint_id", complaint_id), incident.get("lot_number", lot_number)
            st.download_button("Download Signed QMSR CAPA Report (.md)", build_md(cid, lot, reviewer, incident, result, sig_res), file_name=f"CAPA_{cid}_{lot}.md", mime="text/markdown", use_container_width=True)

with tab2:
    h1, h2 = st.columns([4, 1])
    h1.subheader("21 CFR Part 11 Immutable Audit Trail")
    if h2.button("Refresh Audit Logs", use_container_width=True):
        st.rerun()
    try:
        logs_res = requests.get(f"{API_URL}/audit-logs", timeout=20)
        if logs_res.ok:
            data = logs_res.json()
            st.dataframe(data, use_container_width=True, hide_index=True) if data else st.info("No signed CAPA records logged yet.")
        else:
            st.error(f"Audit Log Error ({logs_res.status_code}): {logs_res.text}")
    except Exception as exc:
        st.error(f"Could not reach backend audit logs: {exc}")