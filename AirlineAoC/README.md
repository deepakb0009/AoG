# AeroSentinel — AOG Predictive Maintenance System

> **KPI Targets:** 25–40% AOG reduction · 20–30% unscheduled MX reduction · 15–25% downtime reduction · 5–10% fleet availability increase

## Quick Start

### 1. View the Dashboard
```bash
cd /path/to/AirlineAoC
python3 -m http.server 8080
# Open: http://localhost:8080
```

### 2. Run the FastAPI Backend
```bash
pip install fastapi uvicorn
cd backend
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 3. Generate the Synthetic Dataset (Agent 3)
```bash
pip install pandas numpy tqdm
cd scripts

# 30-day preview (~50 MB, fast)
python generate_data.py --preview

# Full 2-year dataset (~1.5 GB)
python generate_data.py
```

### 4. Train ML Models (Agent 3 + scikit-learn)
```bash
pip install scikit-learn joblib
cd scripts

# Train on 30-day preview (fast)
python train_model.py --preview

# Train on full dataset
python train_model.py
```

---

## Project Structure

```
AirlineAoC/
├── index.html                    # Dashboard SPA entry point
├── css/styles.css                # Glassmorphism dark theme
├── js/
│   ├── app.js                    # SPA router, clock, ticker
│   ├── charts.js                 # Reusable Chart.js wrappers
│   ├── fleet.js                  # Fleet Overview page
│   ├── aircraft.js               # Aircraft Detail page
│   ├── predictions.js            # Prediction Engine page
│   └── maintenance.js            # Maintenance Planner page
├── data/
│   ├── aircraft_metadata.json    # 10-aircraft fleet registry
│   ├── sensor_summary.json       # 24h sensor snapshots (all aircraft)
│   ├── predictions.json          # ML risk predictions (8 active alerts)
│   ├── maintenance_alerts.json   # Upcoming + completed maintenance
│   └── kpis.json                 # KPI metrics with monthly trends
├── backend/
│   └── main.py                   # FastAPI REST backend (10 endpoints)
├── scripts/
│   ├── generate_data.py          # Synthetic data generator (Agent 3)
│   └── train_model.py            # ML model trainer (Isolation Forest + RF)
├── docs/
│   ├── domain_specialist_report.md  # Agent 1 subsystem analysis
│   ├── schema_ddl.sql               # Agent 2 full DB schema DDL
│   └── api_spec.md                  # Agent 2 REST API specification
└── README.md
```

---

## Agent Deliverables

| Agent | Role | Output |
|---|---|---|
| **Agent 1** | Domain Specialist | `docs/domain_specialist_report.md` — Top 5 subsystems, failure modes, sensors |
| **Agent 2** | Systems Architect | `docs/schema_ddl.sql` + `docs/api_spec.md` + `backend/main.py` |
| **Agent 3** | Data Engineer | `scripts/generate_data.py` + `scripts/train_model.py` |
| **Agent 4** | Orchestrator | Full-stack dashboard (`index.html` + `css/` + `js/`) |

---

## Synthetic Dataset Specification

| Parameter | Value |
|---|---|
| Fleet | 10 aircraft (A319/A320/A321 mix, SkyBridge Airlines) |
| Duration | 24 months (Jan 2024 – Dec 2025) |
| Sensor rate | 1 min intervals (1440 rows/aircraft/day) |
| Total rows | ~10.5M (sensor_telemetry) |
| Failure events | 18 injected failures across 5 subsystems |
| Noise model | Gaussian drift + spikes + 2–5% missing values |
| ML labels | NORMAL / DEGRADED / PRE_FAILURE / FAILURE |
| Train/Val/Test | 70% / 15% / 15% split |

---

## ML Models

| Model | Type | Use Case |
|---|---|---|
| **Isolation Forest** | Unsupervised anomaly detection | Detects abnormal sensor patterns without labels |
| **Random Forest** | Supervised multi-class classifier | Predicts failure state: NORMAL/DEGRADED/PRE_FAILURE/FAILURE |

One model pair (IF + RF) is trained **per subsystem** (APU, Engine, Landing Gear, Avionics, Bleed).

---

## Database Schema Tables

| Table | Description |
|---|---|
| `aircraft_metadata` | Master fleet registry |
| `sensor_telemetry` | Time-series sensor readings (partitioned) |
| `flight_cycles` | Per-flight statistics |
| `maintenance_logs` | Historical/scheduled maintenance |
| `failure_labels` | ML ground-truth labels |
| `prediction_results` | ML model output store |

---

## API Endpoints (FastAPI)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fleet/status` | Fleet health overview |
| GET | `/api/aircraft/{id}` | Aircraft detail |
| GET | `/api/aircraft/{id}/sensors` | Sensor telemetry |
| GET | `/api/aircraft/{id}/predictions` | ML predictions |
| GET | `/api/maintenance/alerts` | Active alerts |
| POST | `/api/maintenance/alerts/{id}/acknowledge` | Acknowledge alert |
| POST | `/api/telemetry/ingest` | Ingest sensor batch |
| GET | `/api/kpis` | KPI metrics |
| GET | `/api/export/dataset` | Download CSV |
| GET | `/api/aircraft/{id}/cycles` | Flight cycles |

---

## Standards & References

- ATA iSpec 2200 — chapter numbering
- MSG-3 — maintenance task analysis methodology
- MIL-HDBK-217F — MTBF/reliability standards
- FAA AC 120-17A — maintenance reliability program
