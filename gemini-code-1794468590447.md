# MedRegulator AI — FDA QMSR & ISO 13485 CAPA Triage Engine

An end-to-end Forward Deployed Engineering (FDE) proof-of-concept that automates medical device nonconformance triage, queries Device History Records (DHR) via a **Model Context Protocol (MCP)** server, and drafts traceable 5-Why CAPA reports using a deterministic **LangGraph** state machine.

## Architecture

```mermaid
graph TD
    A[Incoming Quality Event / Complaint] --> B[Pydantic QMSR Schema Validator]
    B --> C{LangGraph Node 1: Classify Trigger}
    C -->|Actual Nonconformance| D[Corrective Action - ISO 13485:8.5.2]
    C -->|Proactive Trend| E[Preventive Action - ISO 13485:8.5.3]
    D & E --> F[LangGraph Node 2: MCP DHR & CAPA Lookup]
    F --> G[LangGraph Node 3: 5-Why Root Cause Synthesizer]
    G --> H{LangGraph Node 4: Citation & DHR Guardrail}
    H -->|Pass| I[QA Engineer Sign-Off UI]
    H -->|Fail / Missing Lot| J[Blocked: Manual QA Investigation]
    I -->|Electronic Signature| K[(Immutable SHA-256 Audit Trail)]