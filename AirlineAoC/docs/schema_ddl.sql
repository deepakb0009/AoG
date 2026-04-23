-- =============================================================================
-- AOG PREDICTIVE MAINTENANCE SYSTEM — DATABASE SCHEMA DDL
-- Agent 2: Systems Architect
-- Standards: ATA iSpec 2200, SQL:2016, TimescaleDB-compatible
-- =============================================================================

-- Enable UUID generation
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- Uncomment for PostgreSQL

-- =============================================================================
-- TABLE 1: AIRCRAFT_METADATA
-- Master registry of all fleet aircraft
-- =============================================================================
CREATE TABLE aircraft_metadata (
    aircraft_id         VARCHAR(10)     PRIMARY KEY,          -- e.g. 'AC001'
    registration        VARCHAR(10)     NOT NULL UNIQUE,      -- e.g. 'N20001'
    icao_type           VARCHAR(10)     NOT NULL,             -- e.g. 'A320'
    iata_type           VARCHAR(10)     NOT NULL,             -- e.g. 'A320'
    manufacturer        VARCHAR(50)     NOT NULL DEFAULT 'Airbus',
    series              VARCHAR(20)     NOT NULL,             -- e.g. 'A320-214'
    engine_type         VARCHAR(30)     NOT NULL,             -- e.g. 'CFM56-5B4'
    msn                 VARCHAR(20)     NOT NULL UNIQUE,      -- Manufacturer Serial Number
    delivery_date       DATE            NOT NULL,
    total_flight_hours  DECIMAL(10,1)   NOT NULL DEFAULT 0.0,
    total_cycles        INTEGER         NOT NULL DEFAULT 0,
    fleet_operator      VARCHAR(100)    NOT NULL,
    base_airport        CHAR(4)         NOT NULL,             -- ICAO airport code
    status              VARCHAR(20)     NOT NULL DEFAULT 'OPERATIONAL'
                        CHECK (status IN ('OPERATIONAL','AOG','MAINTENANCE','RETIRED')),
    last_c_check        DATE,
    next_c_check        DATE,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aircraft_status ON aircraft_metadata(status);
CREATE INDEX idx_aircraft_base ON aircraft_metadata(base_airport);

-- =============================================================================
-- TABLE 2: FLIGHT_CYCLES
-- One row per flight (departure to arrival)
-- =============================================================================
CREATE TABLE flight_cycles (
    cycle_id            VARCHAR(20)     PRIMARY KEY,          -- e.g. 'AC001-20240115-001'
    aircraft_id         VARCHAR(10)     NOT NULL REFERENCES aircraft_metadata(aircraft_id),
    flight_number       VARCHAR(10)     NOT NULL,
    departure_airport   CHAR(4)         NOT NULL,
    arrival_airport     CHAR(4)         NOT NULL,
    departure_time      TIMESTAMP       NOT NULL,
    arrival_time        TIMESTAMP,
    block_time_min      INTEGER,                              -- Total block time in minutes
    flight_time_min     INTEGER,                              -- Air time in minutes
    cruise_altitude_ft  INTEGER,
    max_payload_kg      DECIMAL(8,1),
    fuel_used_kg        DECIMAL(8,1),
    takeoff_weight_kg   DECIMAL(8,1),
    landing_weight_kg   DECIMAL(8,1),
    cycle_number        INTEGER         NOT NULL,             -- Cumulative cycle count at departure
    total_fh_at_dep     DECIMAL(10,1)   NOT NULL,             -- Total FH at departure
    apu_hours_flight    DECIMAL(6,2),                         -- APU usage this flight
    max_headwind_kts    INTEGER,
    max_tailwind_kts    INTEGER,
    turbulence_level    VARCHAR(10)
                        CHECK (turbulence_level IN ('NONE','LIGHT','MODERATE','SEVERE')),
    status              VARCHAR(15)     NOT NULL DEFAULT 'COMPLETED'
                        CHECK (status IN ('PLANNED','ACTIVE','COMPLETED','DIVERTED','CANCELLED')),
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fc_aircraft ON flight_cycles(aircraft_id);
CREATE INDEX idx_fc_departure ON flight_cycles(departure_time);
CREATE INDEX idx_fc_aircraft_time ON flight_cycles(aircraft_id, departure_time);

-- =============================================================================
-- TABLE 3: SENSOR_TELEMETRY
-- High-frequency time-series sensor readings
-- Partition by (aircraft_id, month) in production — shown as single table here
-- =============================================================================
CREATE TABLE sensor_telemetry (
    telemetry_id        BIGINT          PRIMARY KEY,          -- Auto-increment
    aircraft_id         VARCHAR(10)     NOT NULL REFERENCES aircraft_metadata(aircraft_id),
    cycle_id            VARCHAR(20)     REFERENCES flight_cycles(cycle_id),
    ts                  TIMESTAMP       NOT NULL,             -- Reading timestamp (UTC)
    flight_phase        VARCHAR(15)     NOT NULL
                        CHECK (flight_phase IN ('PRE_FLIGHT','TAXI_OUT','TAKEOFF','CLIMB',
                                                'CRUISE','DESCENT','APPROACH','LANDING',
                                                'TAXI_IN','POST_FLIGHT','GROUND_APU')),

    -- APU Sensors (ATA 49)
    apu_egt_c           DECIMAL(6,1),   -- APU Exhaust Gas Temp (°C)
    apu_oil_psi         DECIMAL(5,1),   -- APU Oil Pressure (psi)
    apu_vibration_g     DECIMAL(5,3),   -- APU Body Vibration (g)
    apu_rpm_pct         DECIMAL(5,2),   -- APU Speed (% RPM)
    apu_oil_temp_c      DECIMAL(5,1),   -- APU Oil Temp (°C)
    apu_bleed_psi       DECIMAL(5,1),   -- APU Bleed Pressure (psi)
    apu_fuel_flow_kg    DECIMAL(6,1),   -- APU Fuel Flow (kg/hr)
    apu_running         BOOLEAN,        -- APU running flag

    -- Landing Gear Sensors (ATA 32)
    hyd_sys_psi         DECIMAL(6,1),   -- Hydraulic System Pressure (psi)
    brake_temp_ngl_c    DECIMAL(6,1),   -- Nose Gear Left Brake Temp (°C)
    brake_temp_ngr_c    DECIMAL(6,1),   -- Nose Gear Right Brake Temp (°C)
    brake_temp_mll_c    DECIMAL(6,1),   -- Main Left Left Brake Temp (°C)
    brake_temp_mlr_c    DECIMAL(6,1),   -- Main Left Right Brake Temp (°C)
    brake_temp_mrl_c    DECIMAL(6,1),   -- Main Right Left Brake Temp (°C)
    brake_temp_mrr_c    DECIMAL(6,1),   -- Main Right Right Brake Temp (°C)
    lg_nose_pos_mm      DECIMAL(6,1),   -- Nose Gear LVDT Position (mm)
    lg_left_pos_mm      DECIMAL(6,1),   -- Left MLG LVDT Position (mm)
    lg_right_pos_mm     DECIMAL(6,1),   -- Right MLG LVDT Position (mm)
    oleo_stroke_mm      DECIMAL(5,1),   -- Shock absorber stroke (mm)
    hyd_fluid_level_pct DECIMAL(5,1),   -- Hydraulic Fluid Level (%)

    -- Propulsion Sensors — Engine 1 (ATA 70-80)
    eng1_egt_c          DECIMAL(6,1),   -- Engine 1 EGT (°C)
    eng1_n1_pct         DECIMAL(5,2),   -- Engine 1 N1 Speed (%)
    eng1_n2_pct         DECIMAL(5,2),   -- Engine 1 N2 Speed (%)
    eng1_vib_n1_ips     DECIMAL(5,3),   -- Engine 1 N1 Vibration (IPS)
    eng1_vib_n2_ips     DECIMAL(5,3),   -- Engine 1 N2 Vibration (IPS)
    eng1_oil_psi        DECIMAL(5,1),   -- Engine 1 Oil Pressure (psi)
    eng1_oil_temp_c     DECIMAL(5,1),   -- Engine 1 Oil Temp (°C)
    eng1_ff_kg          DECIMAL(7,1),   -- Engine 1 Fuel Flow (kg/hr)
    eng1_egt_margin_c   DECIMAL(6,1),   -- Engine 1 EGT Margin (redline - actual)
    eng1_running        BOOLEAN,

    -- Propulsion Sensors — Engine 2 (ATA 70-80)
    eng2_egt_c          DECIMAL(6,1),
    eng2_n1_pct         DECIMAL(5,2),
    eng2_n2_pct         DECIMAL(5,2),
    eng2_vib_n1_ips     DECIMAL(5,3),
    eng2_vib_n2_ips     DECIMAL(5,3),
    eng2_oil_psi        DECIMAL(5,1),
    eng2_oil_temp_c     DECIMAL(5,1),
    eng2_ff_kg          DECIMAL(7,1),
    eng2_egt_margin_c   DECIMAL(6,1),
    eng2_running        BOOLEAN,

    -- Avionics / FCS Sensors (ATA 22/27/34)
    dc_bus_28v          DECIMAL(5,2),   -- 28V DC Bus Voltage (V)
    pitot_heat_amp      DECIMAL(5,2),   -- Pitot Heater Current (A)
    fcc_temp_c          DECIMAL(5,1),   -- FCC Internal Temp (°C)
    arinc_errors_sec    DECIMAL(5,1),   -- ARINC 429 Bus Errors/sec
    bite_fault_count    SMALLINT,       -- BITE Fault Count (session)

    -- Pneumatic / Bleed Air Sensors (ATA 36)
    bleed_duct_psi      DECIMAL(5,1),   -- Bleed Duct Pressure (psi)
    precooler_temp_c    DECIMAL(6,1),   -- Precooler Outlet Temp (°C)
    precooler_dp_psi    DECIMAL(5,2),   -- Precooler Diff Pressure (psi)
    prsov_pos_deg       DECIMAL(5,1),   -- PRSOV Valve Position (°)
    bleed_flow_lbs      DECIMAL(5,1),   -- Bleed Air Flow (lbs/min)

    -- Data Quality Flags (bitmask: 1=DRIFT, 2=SPIKE, 4=MISSING, 8=FROZEN)
    sensor_quality_flags SMALLINT       NOT NULL DEFAULT 0,

    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tel_aircraft_ts ON sensor_telemetry(aircraft_id, ts);
CREATE INDEX idx_tel_cycle ON sensor_telemetry(cycle_id);
CREATE INDEX idx_tel_ts ON sensor_telemetry(ts);
CREATE INDEX idx_tel_quality ON sensor_telemetry(sensor_quality_flags) WHERE sensor_quality_flags > 0;

-- =============================================================================
-- TABLE 4: MAINTENANCE_LOGS
-- Historical and scheduled maintenance records
-- =============================================================================
CREATE TABLE maintenance_logs (
    log_id              VARCHAR(20)     PRIMARY KEY,          -- e.g. 'MX-AC001-20240220-01'
    aircraft_id         VARCHAR(10)     NOT NULL REFERENCES aircraft_metadata(aircraft_id),
    cycle_id            VARCHAR(20)     REFERENCES flight_cycles(cycle_id),
    maintenance_type    VARCHAR(20)     NOT NULL
                        CHECK (maintenance_type IN ('A_CHECK','B_CHECK','C_CHECK','D_CHECK',
                                                    'OOP','UNSCHEDULED','AOG','LINE','TRANSIT')),
    ata_chapter         VARCHAR(10)     NOT NULL,             -- e.g. '49', '32-10'
    subsystem           VARCHAR(30)     NOT NULL,             -- e.g. 'APU','LANDING_GEAR'
    description         TEXT            NOT NULL,
    work_order          VARCHAR(20),
    station             CHAR(4)         NOT NULL,             -- ICAO airport where work done
    start_time          TIMESTAMP       NOT NULL,
    end_time            TIMESTAMP,
    duration_hours      DECIMAL(6,2),
    technician_id       VARCHAR(20),
    parts_replaced      TEXT,                                 -- JSON array of P/N replaced
    labour_cost_usd     DECIMAL(10,2),
    parts_cost_usd      DECIMAL(10,2),
    aog_event           BOOLEAN         NOT NULL DEFAULT FALSE,
    aog_revenue_loss_usd DECIMAL(10,2),
    fh_at_maintenance   DECIMAL(10,1),
    cycles_at_maintenance INTEGER,
    root_cause          TEXT,
    corrective_action   TEXT,
    deferral_allowed    BOOLEAN         NOT NULL DEFAULT FALSE,
    mel_reference       VARCHAR(20),                          -- MEL item if deferred
    status              VARCHAR(15)     NOT NULL DEFAULT 'COMPLETED'
                        CHECK (status IN ('PLANNED','IN_PROGRESS','COMPLETED','DEFERRED','CANCELLED')),
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mx_aircraft ON maintenance_logs(aircraft_id);
CREATE INDEX idx_mx_start ON maintenance_logs(start_time);
CREATE INDEX idx_mx_aog ON maintenance_logs(aog_event) WHERE aog_event = TRUE;
CREATE INDEX idx_mx_subsystem ON maintenance_logs(subsystem);
CREATE INDEX idx_mx_ata ON maintenance_logs(ata_chapter);

-- =============================================================================
-- TABLE 5: FAILURE_LABELS
-- Ground-truth ML training labels — links sensor windows to failure events
-- =============================================================================
CREATE TABLE failure_labels (
    label_id            VARCHAR(20)     PRIMARY KEY,          -- e.g. 'FL-AC001-20240315-APU'
    aircraft_id         VARCHAR(10)     NOT NULL REFERENCES aircraft_metadata(aircraft_id),
    maintenance_log_id  VARCHAR(20)     NOT NULL REFERENCES maintenance_logs(log_id),
    subsystem           VARCHAR(30)     NOT NULL,
    failure_mode        VARCHAR(100)    NOT NULL,
    ata_chapter         VARCHAR(10)     NOT NULL,
    severity            VARCHAR(10)     NOT NULL
                        CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    failure_confirmed_at TIMESTAMP      NOT NULL,             -- When failure was confirmed/found
    degradation_onset_at TIMESTAMP,                           -- Estimated start of degradation
    lead_time_hours     DECIMAL(6,1),                         -- Hours from onset to confirmation
    label_window_start  TIMESTAMP       NOT NULL,             -- Start of labeled sensor window
    label_window_end    TIMESTAMP       NOT NULL,             -- End of labeled sensor window
    state               VARCHAR(15)     NOT NULL
                        CHECK (state IN ('NORMAL','DEGRADED','PRE_FAILURE','FAILURE')),
    confidence_pct      DECIMAL(5,1)    NOT NULL DEFAULT 95.0, -- Label confidence 0-100%
    primary_sensor      VARCHAR(50),                          -- Most discriminative sensor
    fh_at_onset         DECIMAL(10,1),
    cycles_at_onset     INTEGER,
    ml_use              VARCHAR(10)     NOT NULL DEFAULT 'TRAIN'
                        CHECK (ml_use IN ('TRAIN','VALIDATE','TEST','HOLDOUT')),
    notes               TEXT,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fl_aircraft ON failure_labels(aircraft_id);
CREATE INDEX idx_fl_subsystem ON failure_labels(subsystem);
CREATE INDEX idx_fl_state ON failure_labels(state);
CREATE INDEX idx_fl_window ON failure_labels(label_window_start, label_window_end);
CREATE INDEX idx_fl_ml_use ON failure_labels(ml_use);

-- =============================================================================
-- TABLE 6: PREDICTION_RESULTS (ML Model Output Store)
-- =============================================================================
CREATE TABLE prediction_results (
    prediction_id       VARCHAR(25)     PRIMARY KEY,
    aircraft_id         VARCHAR(10)     NOT NULL REFERENCES aircraft_metadata(aircraft_id),
    subsystem           VARCHAR(30)     NOT NULL,
    predicted_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    risk_score          DECIMAL(5,4)    NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    risk_category       VARCHAR(15)     NOT NULL
                        CHECK (risk_category IN ('LOW','MODERATE','HIGH','CRITICAL')),
    predicted_failure_mode VARCHAR(100),
    predicted_ttf_hours DECIMAL(8,1),                         -- Predicted Time-To-Failure (hrs)
    ttf_lower_ci        DECIMAL(8,1),                         -- 95% CI lower bound
    ttf_upper_ci        DECIMAL(8,1),                         -- 95% CI upper bound
    model_name          VARCHAR(50)     NOT NULL,
    model_version       VARCHAR(20)     NOT NULL,
    feature_window_hrs  INTEGER         NOT NULL DEFAULT 48,   -- Lookback window used
    top_features        TEXT,                                  -- JSON: top contributing features
    recommended_action  VARCHAR(200),
    acknowledged        BOOLEAN         NOT NULL DEFAULT FALSE,
    acknowledged_by     VARCHAR(50),
    acknowledged_at     TIMESTAMP,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pred_aircraft ON prediction_results(aircraft_id);
CREATE INDEX idx_pred_risk ON prediction_results(risk_category);
CREATE INDEX idx_pred_time ON prediction_results(predicted_at);
CREATE INDEX idx_pred_subsystem ON prediction_results(subsystem);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Current Fleet Health Summary
CREATE VIEW v_fleet_health AS
SELECT
    am.aircraft_id,
    am.registration,
    am.series,
    am.status,
    am.base_airport,
    am.total_flight_hours,
    am.total_cycles,
    MAX(pr.predicted_at) AS last_prediction_at,
    MAX(pr.risk_score) AS max_risk_score,
    SUM(CASE WHEN pr.risk_category = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_alerts,
    SUM(CASE WHEN pr.risk_category = 'HIGH' THEN 1 ELSE 0 END) AS high_alerts,
    COUNT(CASE WHEN ml.aog_event = TRUE
               AND ml.start_time >= datetime('now','-30 days')
               THEN 1 END) AS aog_last_30d
FROM aircraft_metadata am
LEFT JOIN prediction_results pr ON am.aircraft_id = pr.aircraft_id
    AND pr.predicted_at >= datetime('now','-24 hours')
LEFT JOIN maintenance_logs ml ON am.aircraft_id = ml.aircraft_id
GROUP BY am.aircraft_id, am.registration, am.series, am.status,
         am.base_airport, am.total_flight_hours, am.total_cycles;

-- AOG KPI Summary
CREATE VIEW v_aog_kpis AS
SELECT
    COUNT(CASE WHEN aog_event = TRUE
               AND start_time >= datetime('now','-365 days') THEN 1 END) AS aog_count_ytd,
    COUNT(CASE WHEN aog_event = TRUE
               AND start_time >= datetime('now','-30 days') THEN 1 END) AS aog_count_30d,
    SUM(CASE WHEN aog_event = TRUE
             AND start_time >= datetime('now','-365 days')
             THEN aog_revenue_loss_usd ELSE 0 END) AS aog_revenue_loss_ytd,
    AVG(CASE WHEN aog_event = TRUE THEN duration_hours END) AS avg_aog_duration_hrs
FROM maintenance_logs;

-- =============================================================================
-- SAMPLE REFERENCE DATA
-- =============================================================================
INSERT INTO aircraft_metadata
  (aircraft_id,registration,icao_type,iata_type,manufacturer,series,engine_type,msn,delivery_date,
   total_flight_hours,total_cycles,fleet_operator,base_airport,status,last_c_check,next_c_check,created_at,updated_at)
VALUES
('AC001','N20001','A320','A320','Airbus','A320-214','CFM56-5B4','4521','2016-03-14',24850.2,7412,'SkyBridge Airlines','KLAX','OPERATIONAL','2024-08-10','2026-08-10',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC002','N20002','A319','A319','Airbus','A319-111','CFM56-5B5','3892','2012-07-22',41230.5,13847,'SkyBridge Airlines','KJFK','OPERATIONAL','2023-11-02','2025-11-02',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC003','N20003','A321','A321','Airbus','A321-231','V2533-A5','5104','2018-11-30',17640.8,5123,'SkyBridge Airlines','KORD','AOG','2024-06-15','2026-06-15',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC004','N20004','A320','A320','Airbus','A320-232','V2527-A5','4788','2017-04-05',21340.1,6891,'SkyBridge Airlines','KLAX','OPERATIONAL','2024-02-20','2026-02-20',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC005','N20005','A319','A319','Airbus','A319-132','CFM56-5B6','3201','2010-09-18',52180.3,17234,'SkyBridge Airlines','KATL','MAINTENANCE','2023-05-12','2025-05-12',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC006','N20006','A320','A320','Airbus','A320-214','CFM56-5B4','5322','2020-01-08',12480.6,3921,'SkyBridge Airlines','KDFW','OPERATIONAL','2025-01-08','2027-01-08',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC007','N20007','A321','A321','Airbus','A321-211','CFM56-5B3','4430','2015-06-25',28920.4,8765,'SkyBridge Airlines','KMIA','OPERATIONAL','2024-04-30','2026-04-30',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC008','N20008','A320','A320','Airbus','A320-214','CFM56-5B4','4901','2019-03-11',15330.7,4932,'SkyBridge Airlines','KSFO','OPERATIONAL','2024-09-22','2026-09-22',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC009','N20009','A319','A319','Airbus','A319-115','CFM56-5B7','2987','2011-12-03',47550.9,15612,'SkyBridge Airlines','KDEN','OPERATIONAL','2023-08-05','2025-08-05',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('AC010','N20010','A321','A321','Airbus','A321-231','V2533-A5','5688','2022-05-17',7820.2,2341,'SkyBridge Airlines','KBOS','OPERATIONAL','2025-05-17','2027-05-17',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
