import sqlite3

DB_PATH = "medregulator.sqlite"

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Device History Records (DHR)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS device_history_records (
        lot_number TEXT PRIMARY KEY,
        device_model TEXT NOT NULL,
        udi_di TEXT NOT NULL,
        assembly_line TEXT NOT NULL,
        critical_component TEXT NOT NULL,
        supplier_name TEXT NOT NULL,
        sterilization_batch TEXT NOT NULL,
        release_date TEXT NOT NULL
    )
    """)

    # 2. Historical Non-Conformances & CAPAs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_capas (
        capa_id TEXT PRIMARY KEY,
        component_name TEXT NOT NULL,
        failure_mode TEXT NOT NULL,
        root_cause TEXT NOT NULL,
        iso_clause TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)

    # 3. Immutable Audit Trail Table (21 CFR Part 11 style)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_trail (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        complaint_id TEXT NOT NULL,
        reviewer_id TEXT NOT NULL,
        action_taken TEXT NOT NULL,
        record_hash TEXT NOT NULL,
        payload_snapshot TEXT NOT NULL
    )
    """)

    # Enforce immutability via SQLite triggers
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_audit_update
    BEFORE UPDATE ON audit_trail
    BEGIN
        SELECT RAISE(ABORT, 'Compliance Violation: Audit trail records are immutable.');
    END;
    """)
    cur.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
    BEFORE DELETE ON audit_trail
    BEGIN
        SELECT RAISE(ABORT, 'Compliance Violation: Audit trail records cannot be deleted.');
    END;
    """)

    # Insert Synthetic DHR Rows
    dhr_rows = [
        ("LOT-2026-8841", "CardioFlow Infusion Pump v3", "(01)00840123456789", "Line-A2", "Silicone Check Valve", "MedPolymer Corp", "STER-991", "2026-08-14"),
        ("LOT-2026-9012", "NeuroSense Telemetry Patch", "(01)00840987654321", "Line-C1", "Hydrogel Adhesive Electrode", "BioStick Labs", "STER-104", "2026-09-02"),
        ("LOT-2026-9155", "CardioFlow Infusion Pump v3", "(01)00840123456789", "Line-A2", "Optical Occlusion Sensor", "OptiMedics Inc", "STER-112", "2026-10-11"),
    ]
    cur.executemany("INSERT OR REPLACE INTO device_history_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)", dhr_rows)

    # Insert Historical CAPA Rows
    capa_rows = [
        ("CAPA-2025-041", "Silicone Check Valve", "Backflow occlusion alarm during high-viscosity infusion", "Supplier curing temperature drift caused valve durometer hardening", "ISO 13485:2016 Clause 8.5.2 / Clause 7.4.1", "Closed - Verified"),
        ("CAPA-2026-009", "Hydrogel Adhesive Electrode", "Premature edge lifting after 24h wear", "Batch humidity exposure prior to foil pouch sealing", "ISO 13485:2016 Clause 8.5.2 / Clause 7.5.1", "Closed - Verified"),
    ]
    cur.executemany("INSERT OR REPLACE INTO historical_capas VALUES (?, ?, ?, ?, ?, ?)", capa_rows)

    conn.commit()
    conn.close()
    print(f"Database seeded successfully at {DB_PATH}")

if __name__ == "__main__":
    seed()