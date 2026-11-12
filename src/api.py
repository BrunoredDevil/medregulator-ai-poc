from seed_db import seed
seed()

import os
import json
import hashlib
import sqlite3
from fastapi import FastAPI
from src.schemas import IncidentInput, SignOffRequest
from src.agent_graph import triage_graph

DB_PATH = os.getenv("DB_PATH", "medregulator.sqlite")
app = FastAPI(title="MedRegulator AI - QMSR CAPA Engine", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "framework": "FDA QMSR / ISO 13485:2016"}

@app.post("/triage")
def run_triage(incident: IncidentInput):
    initial_state = {
        "incident": incident.model_dump(),
        "dhr_context": {},
        "historical_matches": [],
        "draft_capa": {},
        "guardrail_passed": False,
        "status_label": "",
    }
    return triage_graph.invoke(initial_state)

@app.post("/signoff")
def sign_off_capa(req: SignOffRequest):
    payload_str = json.dumps(req.capa_payload, sort_keys=True)
    record_hash = hashlib.sha256(payload_str.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audit_trail (complaint_id, reviewer_id, action_taken, record_hash, payload_snapshot)
        VALUES (?, ?, ?, ?, ?)
        """,
        (req.complaint_id, req.reviewer_id, req.decision, record_hash, payload_str),
    )
    conn.commit()
    conn.close()
    return {"status": "Recorded in immutable audit trail", "sha256_hash": record_hash}

@app.get("/audit-logs")
def get_audit_logs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT audit_id, timestamp, complaint_id, reviewer_id, action_taken, record_hash FROM audit_trail ORDER BY audit_id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
@app.get("/")
def health_check():
    return {"status": "online", "service": "MedRegulator AI QMSR API", "docs": "/docs"}
