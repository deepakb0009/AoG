"""
AOG Predictive Maintenance System — FastAPI Backend
Agent 2: Systems Architect

Serves all REST endpoints defined in docs/api_spec.md
Reads from JSON data files (prototype) — swap with real DB in production.

Usage:
    pip install fastapi uvicorn
    uvicorn main:app --reload --port 8000

Docs: http://localhost:8000/docs
"""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AOG Predictive Maintenance API",
    description="Predict critical component failures before they occur.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ── Data loaders ──────────────────────────────────────────────────────────────
def load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    with open(path) as f:
        return json.load(f)


def get_fleet():
    return load_json("aircraft_metadata.json")

def get_predictions():
    return load_json("predictions.json")

def get_sensor_summary():
    return load_json("sensor_summary.json")

def get_kpis():
    return load_json("kpis.json")

def get_maintenance():
    return load_json("maintenance_alerts.json")


# ── Pydantic models ───────────────────────────────────────────────────────────
class AcknowledgeRequest(BaseModel):
    acknowledged_by: str
    notes: Optional[str] = None

class TelemetryReading(BaseModel):
    ts: str
    flight_phase: str
    cycle_id: Optional[str] = None
    apu_egt_c: Optional[float] = None
    eng1_egt_c: Optional[float] = None
    eng1_n1_pct: Optional[float] = None
    hyd_sys_psi: Optional[float] = None

class TelemetryBatch(BaseModel):
    aircraft_id: str
    source: str = "MANUAL"
    readings: list[TelemetryReading]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"service": "AOG Predictive Maintenance API", "version": "1.0.0",
            "status": "operational", "docs": "/docs"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# 1. Fleet Status
@app.get("/api/fleet/status", tags=["Fleet"])
def fleet_status():
    fleet = get_fleet()
    preds = get_predictions()
    sensors = get_sensor_summary()

    # Build risk lookup from predictions
    risk_lookup: dict = {}
    for alert in preds["alerts"]:
        aid = alert["aircraft_id"]
        if aid not in risk_lookup or alert["risk_score"] > risk_lookup[aid]["risk_score"]:
            risk_lookup[aid] = alert

    enriched = []
    for ac in fleet["aircraft"]:
        aid = ac["aircraft_id"]
        snap = sensors["sensor_snapshots"].get(aid, {})
        top = risk_lookup.get(aid, {})
        enriched.append({
            **ac,
            "max_risk_score":   top.get("risk_score", 0.0),
            "risk_category":    top.get("risk_category", "LOW"),
            "critical_alerts":  sum(1 for a in preds["alerts"] if a["aircraft_id"] == aid and a["risk_category"] == "CRITICAL"),
            "high_alerts":      sum(1 for a in preds["alerts"] if a["aircraft_id"] == aid and a["risk_category"] == "HIGH"),
            "flight_phase":     snap.get("flight_phase", "UNKNOWN"),
        })

    return {
        "generated_at":  datetime.utcnow().isoformat(),
        "fleet_size":    fleet["fleet_size"],
        "operational":   sum(1 for a in fleet["aircraft"] if a["status"] == "OPERATIONAL"),
        "aog":           sum(1 for a in fleet["aircraft"] if a["status"] == "AOG"),
        "maintenance":   sum(1 for a in fleet["aircraft"] if a["status"] == "MAINTENANCE"),
        "aircraft":      enriched,
    }


# 2. Aircraft Detail
@app.get("/api/aircraft/{aircraft_id}", tags=["Aircraft"])
def aircraft_detail(aircraft_id: str):
    fleet = get_fleet()
    ac = next((a for a in fleet["aircraft"] if a["aircraft_id"] == aircraft_id), None)
    if not ac:
        raise HTTPException(status_code=404, detail=f"Aircraft {aircraft_id} not found")

    sensors = get_sensor_summary()
    snap = sensors["sensor_snapshots"].get(aircraft_id, {})
    return {**ac, "sensor_snapshot": snap}


# 3. Sensor telemetry snapshot (last 24h summary from JSON)
@app.get("/api/aircraft/{aircraft_id}/sensors", tags=["Sensors"])
def aircraft_sensors(
    aircraft_id: str,
    subsystem: Optional[str] = Query(None, description="APU|ENGINE|LANDING_GEAR|AVIONICS|BLEED"),
):
    sensors = get_sensor_summary()
    snap = sensors["sensor_snapshots"].get(aircraft_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"No sensor data for {aircraft_id}")

    result = snap
    if subsystem:
        subsys_data = snap.get("subsystems", {}).get(subsystem.upper())
        if not subsys_data:
            raise HTTPException(status_code=404, detail=f"Subsystem {subsystem} not found")
        result = {"aircraft_id": aircraft_id, "subsystem": subsystem, **subsys_data}

    return result


# 4. Predictions for one aircraft
@app.get("/api/aircraft/{aircraft_id}/predictions", tags=["Predictions"])
def aircraft_predictions(aircraft_id: str):
    preds = get_predictions()
    alerts = [a for a in preds["alerts"] if a["aircraft_id"] == aircraft_id]
    return {
        "aircraft_id":   aircraft_id,
        "predicted_at":  preds["generated_at"],
        "model_version": "rf-v2.4.1+iforest-v1.2.0",
        "predictions":   alerts,
    }


# 5. Fleet-wide maintenance alerts
@app.get("/api/maintenance/alerts", tags=["Maintenance"])
def maintenance_alerts(
    severity: Optional[str] = Query(None),
    subsystem: Optional[str] = Query(None),
    acknowledged: bool = Query(False),
    limit: int = Query(50, le=200),
):
    preds = get_predictions()
    alerts = preds["alerts"]

    if severity:
        alerts = [a for a in alerts if a["risk_category"] == severity.upper()]
    if subsystem:
        alerts = [a for a in alerts if a["subsystem"] == subsystem.upper()]
    if not acknowledged:
        alerts = [a for a in alerts if not a.get("acknowledged", False)]

    return {"total": len(alerts), "alerts": alerts[:limit]}


# 6. Acknowledge alert
@app.post("/api/maintenance/alerts/{prediction_id}/acknowledge", tags=["Maintenance"])
def acknowledge_alert(prediction_id: str, body: AcknowledgeRequest):
    # In production: update DB record
    return {
        "status": "acknowledged",
        "prediction_id": prediction_id,
        "acknowledged_by": body.acknowledged_by,
        "acknowledged_at": datetime.utcnow().isoformat(),
    }


# 7. Ingest telemetry
@app.post("/api/telemetry/ingest", tags=["Telemetry"])
def ingest_telemetry(batch: TelemetryBatch):
    # In production: write to TimescaleDB / InfluxDB
    return {
        "accepted": len(batch.readings),
        "rejected": 0,
        "batch_id": f"BATCH-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "quality_warnings": [],
    }


# 8. KPI metrics
@app.get("/api/kpis", tags=["KPIs"])
def kpis(period: str = Query("365d", regex="^(30d|90d|365d|ytd)$")):
    data = get_kpis()
    return {**data, "period": period}


# 9. Export dataset (returns file if available, else instructions)
@app.get("/api/export/dataset", tags=["Export"])
def export_dataset(
    table: str = Query("sensor_telemetry"),
    format: str = Query("csv", regex="^(csv|json)$"),
):
    fname = f"{table}_preview.csv" if table == "sensor_telemetry" else f"{table}.csv"
    fpath = os.path.join(DATA_DIR, fname)
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="text/csv",
                            headers={"Content-Disposition": f"attachment; filename={fname}"})
    return JSONResponse(status_code=202, content={
        "message": f"Dataset '{table}' not yet generated.",
        "instructions": "Run: python scripts/generate_data.py --preview",
        "expected_path": fpath,
    })


# 10. Flight cycles
@app.get("/api/aircraft/{aircraft_id}/cycles", tags=["Aircraft"])
def flight_cycles(aircraft_id: str, limit: int = Query(20, le=100)):
    # Return mock recent cycles
    return {
        "aircraft_id": aircraft_id,
        "cycles": [
            {
                "cycle_id": f"{aircraft_id}-20260424-{i:02d}",
                "flight_number": f"SB{400+i}",
                "departure_airport": ["KLAX","KJFK","KORD","KATL","KDFW"][i % 5],
                "arrival_airport":   ["KJFK","KORD","KATL","KDFW","KSFO"][i % 5],
                "departure_time": f"2026-04-{23-i:02d}T{6+i*2:02d}:00:00Z",
                "block_time_min": 180 + i * 12,
                "status": "COMPLETED",
            }
            for i in range(min(limit, 10))
        ],
    }
