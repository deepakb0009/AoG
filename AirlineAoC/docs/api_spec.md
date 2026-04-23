# AOG Predictive Maintenance System — API Specification
# Agent 2: Systems Architect
# Version: 1.0.0 | Format: OpenAPI 3.0-style (Markdown)

---

## Base URL
```
https://api.aog-predict.skybridge.com/v1
```

---

## Authentication
All endpoints require Bearer token authentication:
```
Authorization: Bearer <JWT_TOKEN>
```

---

## Endpoints

### 1. Fleet Status
**GET** `/api/fleet/status`

Returns real-time health overview for all fleet aircraft.

**Response 200:**
```json
{
  "generated_at": "2026-04-24T00:00:00Z",
  "fleet_size": 10,
  "operational": 7,
  "aog": 1,
  "maintenance": 2,
  "aircraft": [
    {
      "aircraft_id": "AC001",
      "registration": "N20001",
      "series": "A320-214",
      "status": "OPERATIONAL",
      "base_airport": "KLAX",
      "total_fh": 24850.2,
      "total_cycles": 7412,
      "max_risk_score": 0.31,
      "risk_category": "MODERATE",
      "critical_alerts": 0,
      "high_alerts": 1,
      "aog_last_30d": 0
    }
  ]
}
```

---

### 2. Aircraft Detail
**GET** `/api/aircraft/{aircraft_id}`

Full aircraft profile with latest sensor snapshot.

**Path Parameters:** `aircraft_id` (string, e.g. `AC001`)

**Response 200:**
```json
{
  "aircraft_id": "AC001",
  "registration": "N20001",
  "series": "A320-214",
  "engine_type": "CFM56-5B4",
  "msn": "4521",
  "delivery_date": "2016-03-14",
  "total_flight_hours": 24850.2,
  "total_cycles": 7412,
  "status": "OPERATIONAL",
  "last_sensor_snapshot": {
    "ts": "2026-04-24T00:00:00Z",
    "flight_phase": "GROUND_APU",
    "apu_egt_c": 568.2,
    "eng1_egt_c": null,
    "hyd_sys_psi": 3012.5
  }
}
```

---

### 3. Sensor Telemetry (Time-Series)
**GET** `/api/aircraft/{aircraft_id}/sensors`

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `from` | ISO8601 datetime | now - 24h | Start timestamp |
| `to` | ISO8601 datetime | now | End timestamp |
| `subsystem` | string | all | Filter: `APU`,`ENGINE`,`LANDING_GEAR`,`AVIONICS`,`BLEED` |
| `resample` | string | `1min` | Downsample interval: `1s`,`1min`,`5min`,`1h` |
| `quality` | boolean | false | Include quality flags |

**Response 200:**
```json
{
  "aircraft_id": "AC001",
  "from": "2026-04-23T00:00:00Z",
  "to": "2026-04-24T00:00:00Z",
  "sample_count": 1440,
  "resample": "1min",
  "sensors": {
    "apu_egt_c":       [{ "ts": "...", "v": 568.2, "qf": 0 }],
    "apu_oil_psi":     [{ "ts": "...", "v": 61.4,  "qf": 0 }],
    "eng1_egt_c":      [{ "ts": "...", "v": 742.1, "qf": 0 }],
    "eng1_vib_n1_ips": [{ "ts": "...", "v": 0.42,  "qf": 0 }]
  }
}
```

---

### 4. Failure Predictions
**GET** `/api/aircraft/{aircraft_id}/predictions`

Latest ML predictions per subsystem.

**Response 200:**
```json
{
  "aircraft_id": "AC001",
  "predicted_at": "2026-04-24T00:00:00Z",
  "model_version": "rf-v2.4.1",
  "predictions": [
    {
      "subsystem": "APU",
      "risk_score": 0.71,
      "risk_category": "HIGH",
      "predicted_failure_mode": "EGT Exceedance - Oil System Degradation",
      "predicted_ttf_hours": 62.4,
      "ttf_ci_lower": 38.0,
      "ttf_ci_upper": 89.2,
      "recommended_action": "Schedule APU oil sample and borescope within 48 hours",
      "top_features": [
        { "feature": "apu_egt_24h_trend", "importance": 0.42 },
        { "feature": "apu_oil_psi_rolling_min", "importance": 0.31 },
        { "feature": "apu_vibration_spectral_800hz", "importance": 0.18 }
      ]
    }
  ]
}
```

---

### 5. Fleet-Wide Maintenance Alerts
**GET** `/api/maintenance/alerts`

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `severity` | string | all | `LOW`,`MODERATE`,`HIGH`,`CRITICAL` |
| `subsystem` | string | all | Subsystem filter |
| `limit` | integer | 50 | Max results |
| `acknowledged` | boolean | false | Include acknowledged alerts |

**Response 200:**
```json
{
  "total": 8,
  "alerts": [
    {
      "aircraft_id": "AC003",
      "registration": "N20003",
      "subsystem": "LANDING_GEAR",
      "risk_category": "CRITICAL",
      "risk_score": 0.91,
      "predicted_failure_mode": "Hydraulic actuator seal leak",
      "recommended_action": "Ground aircraft — hydraulic inspection required",
      "predicted_ttf_hours": 4.2,
      "predicted_at": "2026-04-24T00:00:00Z",
      "acknowledged": false
    }
  ]
}
```

---

### 6. Acknowledge Alert
**POST** `/api/maintenance/alerts/{prediction_id}/acknowledge`

**Request Body:**
```json
{
  "acknowledged_by": "tech_id_42",
  "notes": "Scheduled for inspection at KORD gate B12 at 06:00"
}
```

**Response 200:**
```json
{ "status": "acknowledged", "prediction_id": "PRED-AC003-20260424-LG" }
```

---

### 7. Ingest Telemetry (Batch)
**POST** `/api/telemetry/ingest`

Bulk sensor data ingestion endpoint (ACARS/FOQA feed).

**Request Body:**
```json
{
  "aircraft_id": "AC001",
  "source": "ACARS",
  "readings": [
    {
      "ts": "2026-04-24T00:01:00Z",
      "flight_phase": "CRUISE",
      "cycle_id": "AC001-20260424-001",
      "apu_running": false,
      "eng1_egt_c": 742.5,
      "eng1_n1_pct": 92.3,
      "eng2_egt_c": 738.1,
      "hyd_sys_psi": 3021.0
    }
  ]
}
```

**Response 202:**
```json
{
  "accepted": 1,
  "rejected": 0,
  "batch_id": "BATCH-20260424-0042",
  "quality_warnings": []
}
```

---

### 8. KPI Metrics
**GET** `/api/kpis`

**Query Parameters:** `period` = `30d` | `90d` | `365d` | `ytd`

**Response 200:**
```json
{
  "period": "365d",
  "kpis": {
    "aog_reduction_pct": { "value": 28.4, "target": 32.5, "trend": "UP", "status": "ON_TRACK" },
    "unscheduled_mx_reduction_pct": { "value": 22.1, "target": 25.0, "trend": "UP", "status": "ON_TRACK" },
    "downtime_reduction_pct": { "value": 18.7, "target": 20.0, "trend": "STABLE", "status": "AT_RISK" },
    "fleet_availability_pct": { "value": 94.3, "target": 97.0, "trend": "UP", "status": "ON_TRACK" },
    "aog_events_ytd": 14,
    "aog_events_prev_year": 19,
    "avg_aog_duration_hrs": 6.8,
    "revenue_protected_usd": 1240000
  }
}
```

---

### 9. Export Dataset
**GET** `/api/export/dataset`

**Query Parameters:**

| Param | Type | Description |
|---|---|---|
| `table` | string | `sensor_telemetry`,`maintenance_logs`,`flight_cycles`,`failure_labels`,`aircraft_metadata` |
| `format` | string | `csv` or `json` |
| `from` | ISO8601 | Start date |
| `to` | ISO8601 | End date |
| `aircraft_id` | string | Filter by aircraft (optional) |

**Response 200:** Binary file download with headers:
```
Content-Type: text/csv
Content-Disposition: attachment; filename="sensor_telemetry_2024-01-01_2025-12-31.csv"
```

---

### 10. Flight Cycles
**GET** `/api/aircraft/{aircraft_id}/cycles`

**Query Parameters:** `limit` (default 50), `from`, `to`

**Response 200:**
```json
{
  "aircraft_id": "AC001",
  "cycles": [
    {
      "cycle_id": "AC001-20260424-001",
      "flight_number": "SB101",
      "departure_airport": "KLAX",
      "arrival_airport": "KJFK",
      "departure_time": "2026-04-24T06:00:00Z",
      "block_time_min": 318,
      "fuel_used_kg": 14820,
      "status": "COMPLETED"
    }
  ]
}
```

---

## Error Responses

| Code | Meaning |
|---|---|
| 400 | Bad Request — missing/invalid parameters |
| 401 | Unauthorized — invalid or expired token |
| 404 | Not Found — aircraft_id or resource not found |
| 422 | Unprocessable Entity — validation error |
| 429 | Too Many Requests — rate limit exceeded (500 req/min) |
| 500 | Internal Server Error |

**Error Body:**
```json
{
  "error": "AIRCRAFT_NOT_FOUND",
  "message": "Aircraft AC999 does not exist in the fleet registry",
  "timestamp": "2026-04-24T00:00:00Z"
}
```

---

*Agent 2: Systems Architect — API Specification v1.0.0*
