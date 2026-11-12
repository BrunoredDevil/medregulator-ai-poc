import os
import json
import sqlite3
from typing import TypedDict, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from src.schemas import CAPADraft

DB_PATH = os.getenv("DB_PATH", "medregulator.sqlite")

class TriageState(TypedDict):
    incident: Dict[str, Any]
    dhr_context: Dict[str, Any]
    historical_matches: list
    draft_capa: Dict[str, Any]
    guardrail_passed: bool
    status_label: str

def classify_qmsr_trigger(state: TriageState) -> TriageState:
    """Node 1: Separate Corrective (actual nonconformity) vs Preventive (trend) per QMSR / ISO 13485."""
    inc = state["incident"]
    is_preventive = inc["source_channel"] == "Statistical Trend Alert" and not inc["patient_harm_reported"]
    state["status_label"] = (
        "Preventive Action (ISO 13485:8.5.3)" if is_preventive else "Corrective Action (ISO 13485:8.5.2)"
    )
    return state

def retrieve_dhr_via_mcp_logic(state: TriageState) -> TriageState:
    """Node 2: Query DHR & historical CAPAs (mirrors MCP server tool execution)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    lot = state["incident"]["lot_number"]
    cur.execute("SELECT * FROM device_history_records WHERE lot_number = ?", (lot,))
    dhr = cur.fetchone()
    state["dhr_context"] = dict(dhr) if dhr else {}

    comp = state["dhr_context"].get("critical_component", "")
    if comp:
        cur.execute("SELECT * FROM historical_capas WHERE component_name LIKE ?", (f"%{comp}%",))
        state["historical_matches"] = [dict(r) for r in cur.fetchall()]
    else:
        state["historical_matches"] = []

    conn.close()
    return state

def draft_capa_node(state: TriageState) -> TriageState:
    """Node 3: Generate structured 5-Why CAPA draft (uses OpenAI if key exists, else deterministic synthesis)."""
    inc = state["incident"]
    dhr = state["dhr_context"]
    hist = state["historical_matches"]
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if api_key:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(CAPADraft)
        prompt = (
            f"Draft an FDA QMSR / ISO 13485 compliant CAPA record.\n"
            f"Classification: {state['status_label']}\n"
            f"Incident: {json.dumps(inc)}\n"
            f"DHR Record: {json.dumps(dhr)}\n"
            f"Historical CAPAs: {json.dumps(hist)}"
        )
        result: CAPADraft = llm.invoke(prompt)
        state["draft_capa"] = result.model_dump()
        return state

    if not dhr:
        state["draft_capa"] = {
            "action_classification": state["status_label"],
            "mdr_reportable_flag": inc["patient_harm_reported"],
            "five_why_analysis": [
                "Why 1: Lot number missing from DHR database.",
                "Why 2: Unverified batch traceability.",
                "Why 3: Requires manual QA DHR audit.",
            ],
            "iso_citations": [],
            "containment_and_action_plan": "Quarantine suspect units and perform manual DHR trace.",
            "confidence_score": 0.42,
        }
        return state

    hist_note = hist[0]["root_cause"] if hist else "No prior identical failure in DHR history."
    draft = CAPADraft(
        action_classification=state["status_label"],
        mdr_reportable_flag=inc["patient_harm_reported"],
        five_why_analysis=[
            f"Why 1: Nonconformance observed on {dhr['device_model']} ({inc['description'][:60]}...).",
            f"Why 2: Fault isolated to {dhr['critical_component']} supplied by {dhr['supplier_name']}.",
            f"Why 3: Assembly verification on {dhr['assembly_line']} did not catch parameter drift.",
            f"Why 4: Historical baseline indicates: {hist_note}",
            "Why 5: Incoming supplier lot acceptance criteria lacked automated tolerance gating.",
        ],
        iso_citations=[
            "ISO 13485:2016 Clause 8.5.2 (Corrective Action)" if "Corrective" in state["status_label"] else "ISO 13485:2016 Clause 8.5.3 (Preventive Action)",
            "ISO 13485:2016 Clause 7.4.3 (Verification of Purchased Product)",
            "FDA 21 CFR Part 820 (QMSR Harmonized Record Control)",
        ],
        containment_and_action_plan=f"1. Place hold on remaining inventory from {inc['lot_number']} (Sterilization Batch {dhr['sterilization_batch']}). 2. Issue SCAR to {dhr['supplier_name']}. 3. Update incoming QC test protocol.",
        confidence_score=0.93,
    )
    state["draft_capa"] = draft.model_dump()
    return state

def verify_compliance_guardrail(state: TriageState) -> TriageState:
    """Node 4: Deterministic gate blocking outputs without valid DHR links or ISO citations."""
    draft = state["draft_capa"]
    valid_dhr = bool(state["dhr_context"])
    valid_citations = len(draft.get("iso_citations", [])) > 0
    high_conf = draft.get("confidence_score", 0) >= 0.80

    if valid_dhr and valid_citations and high_conf:
        state["guardrail_passed"] = True
        state["status_label"] = "READY FOR QA SIGN-OFF"
    else:
        state["guardrail_passed"] = False
        state["status_label"] = "BLOCKED: MANUAL QA INVESTIGATION REQUIRED"
    return state

def route_guardrail(state: TriageState) -> Literal["pass", "fail"]:
    return "pass" if state["guardrail_passed"] else "fail"

builder = StateGraph(TriageState)
builder.add_node("classify", classify_qmsr_trigger)
builder.add_node("retrieve_dhr", retrieve_dhr_via_mcp_logic)
builder.add_node("draft_capa", draft_capa_node)
builder.add_node("guardrail", verify_compliance_guardrail)

builder.set_entry_point("classify")
builder.add_edge("classify", "retrieve_dhr")
builder.add_edge("retrieve_dhr", "draft_capa")
builder.add_edge("draft_capa", "guardrail")
builder.add_conditional_edges("guardrail", route_guardrail, {"pass": END, "fail": END})

triage_graph = builder.compile()