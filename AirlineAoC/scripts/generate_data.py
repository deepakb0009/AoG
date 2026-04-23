"""
AOG Predictive Maintenance System — Synthetic Data Generator
Agent 3: Data Engineer
Generates 2 years of realistic sensor telemetry for a 10-aircraft fleet.

Usage:
    python generate_data.py              # Full 2-year dataset
    python generate_data.py --preview    # 30-day preview only
    python generate_data.py --days 90    # Custom duration

Requirements: pip install pandas numpy tqdm
"""

import argparse
import math
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from tqdm import tqdm

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Output directory ──────────────────────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Fleet definition ──────────────────────────────────────────────────────────
FLEET = [
    {"id": "AC001", "reg": "N20001", "series": "A320-214", "engine": "CFM56-5B4",
     "age_yrs": 8.1,  "base_cycles": 7412,  "base_fh": 24850.2},
    {"id": "AC002", "reg": "N20002", "series": "A319-111", "engine": "CFM56-5B5",
     "age_yrs": 12.8, "base_cycles": 13847, "base_fh": 41230.5},
    {"id": "AC003", "reg": "N20003", "series": "A321-231", "engine": "V2533-A5",
     "age_yrs": 5.4,  "base_cycles": 5123,  "base_fh": 17640.8},
    {"id": "AC004", "reg": "N20004", "series": "A320-232", "engine": "V2527-A5",
     "age_yrs": 6.9,  "base_cycles": 6891,  "base_fh": 21340.1},
    {"id": "AC005", "reg": "N20005", "series": "A319-132", "engine": "CFM56-5B6",
     "age_yrs": 14.6, "base_cycles": 17234, "base_fh": 52180.3},
    {"id": "AC006", "reg": "N20006", "series": "A320-214", "engine": "CFM56-5B4",
     "age_yrs": 4.3,  "base_cycles": 3921,  "base_fh": 12480.6},
    {"id": "AC007", "reg": "N20007", "series": "A321-211", "engine": "CFM56-5B3",
     "age_yrs": 9.8,  "base_cycles": 8765,  "base_fh": 28920.4},
    {"id": "AC008", "reg": "N20008", "series": "A320-214", "engine": "CFM56-5B4",
     "age_yrs": 5.1,  "base_cycles": 4932,  "base_fh": 15330.7},
    {"id": "AC009", "reg": "N20009", "series": "A319-115", "engine": "CFM56-5B7",
     "age_yrs": 13.4, "base_cycles": 15612, "base_fh": 47550.9},
    {"id": "AC010", "reg": "N20010", "series": "A321-231", "engine": "V2533-A5",
     "age_yrs": 1.9,  "base_cycles": 2341,  "base_fh": 7820.2},
]

# ── Failure schedule: (aircraft_id, subsystem, failure_day_offset, severity) ─
# These are injected failures — what ML models should learn to predict
FAILURE_SCHEDULE = [
    ("AC001", "APU",          45,  "HIGH"),
    ("AC001", "APU",          310, "CRITICAL"),
    ("AC002", "ENGINE",       90,  "HIGH"),
    ("AC002", "BLEED",        450, "MEDIUM"),
    ("AC003", "LANDING_GEAR", 10,  "CRITICAL"),   # AOG at day 10
    ("AC003", "ENGINE",       280, "HIGH"),
    ("AC004", "AVIONICS",     130, "MEDIUM"),
    ("AC004", "APU",          520, "HIGH"),
    ("AC005", "ENGINE",       60,  "CRITICAL"),   # Oldest aircraft
    ("AC005", "LANDING_GEAR", 220, "HIGH"),
    ("AC005", "BLEED",        480, "MEDIUM"),
    ("AC006", "AVIONICS",     200, "LOW"),
    ("AC007", "APU",          170, "HIGH"),
    ("AC007", "LANDING_GEAR", 400, "MEDIUM"),
    ("AC008", "BLEED",        240, "HIGH"),
    ("AC009", "ENGINE",       100, "CRITICAL"),
    ("AC009", "APU",          360, "MEDIUM"),
    ("AC010", "AVIONICS",     500, "LOW"),
]

# ── Sensor normal ranges ──────────────────────────────────────────────────────
NORMALS = {
    "apu_egt_c":        (555, 12),
    "apu_oil_psi":      (60,  2.5),
    "apu_vibration_g":  (0.45, 0.08),
    "apu_rpm_pct":      (99.5, 0.3),
    "apu_oil_temp_c":   (100, 5),
    "apu_bleed_psi":    (42,  1.5),
    "hyd_sys_psi":      (3000, 25),
    "brake_temp_c":     (120, 30),
    "eng_egt_c":        (740, 20),
    "eng_n1_pct":       (92,  1.5),
    "eng_n2_pct":       (96,  1.0),
    "eng_vib_ips":      (0.35, 0.08),
    "eng_oil_psi":      (70,  3),
    "eng_oil_temp_c":   (100, 8),
    "dc_bus_v":         (28.5, 0.3),
    "pitot_amp":        (10,  0.5),
    "fcc_temp_c":       (55,  4),
    "arinc_errors":     (0.1, 0.2),
    "bleed_psi":        (42,  1.5),
    "precooler_temp_c": (200, 8),
    "precooler_dp":     (2.2, 0.3),
}


def add_noise(value, std_pct=0.01, drift=0.0, spike_prob=0.002):
    """Add Gaussian noise, slow drift, and occasional spikes."""
    noisy = value + np.random.normal(0, abs(value) * std_pct) + drift
    if random.random() < spike_prob:
        noisy += value * random.choice([-1, 1]) * random.uniform(0.05, 0.15)
    return round(noisy, 3)


def degrade(value, target, progress, direction="toward"):
    """Linearly interpolate value toward failure target."""
    if direction == "toward":
        return value + (target - value) * progress
    return value


def get_failure_progress(day, fail_day, lead_days=4):
    """Return 0.0–1.0 degradation progress in the lead-up window."""
    onset = fail_day - lead_days
    if day < onset:
        return 0.0, "NORMAL"
    elif day < fail_day:
        prog = (day - onset) / lead_days
        state = "PRE_FAILURE" if prog > 0.6 else "DEGRADED"
        return min(prog, 1.0), state
    else:
        return 1.0, "FAILURE"


def generate_flight_cycles(aircraft, start_date, num_days):
    """Generate one flight cycle record per flight day."""
    records = []
    cycle_num = aircraft["base_cycles"]
    fh = aircraft["base_fh"]
    flight_routes = [
        ("KLAX", "KJFK"), ("KJFK", "KORD"), ("KORD", "KATL"),
        ("KATL", "KDFW"), ("KDFW", "KSFO"), ("KSFO", "KDEN"),
        ("KDEN", "KBOS"), ("KBOS", "KMIA"), ("KMIA", "KLAX"),
    ]
    for d in range(num_days):
        date = start_date + timedelta(days=d)
        if d % 7 == 6:  # ~1 maintenance day/week
            continue
        flights_today = random.randint(2, 4)
        for f in range(flights_today):
            route = random.choice(flight_routes)
            block = random.randint(90, 320)
            fh_flight = block / 60.0
            cycle_num += 1
            fh += fh_flight
            records.append({
                "cycle_id": f"{aircraft['id']}-{date.strftime('%Y%m%d')}-{f+1:02d}",
                "aircraft_id": aircraft["id"],
                "flight_number": f"SB{random.randint(100,999)}",
                "departure_airport": route[0],
                "arrival_airport": route[1],
                "departure_time": (date + timedelta(hours=6 + f * 4)).isoformat(),
                "block_time_min": block,
                "flight_time_min": block - random.randint(20, 35),
                "cycle_number": cycle_num,
                "total_fh_at_dep": round(fh, 1),
                "fuel_used_kg": round(fh_flight * 2400 + random.gauss(0, 200), 1),
                "status": "COMPLETED",
            })
    return records


def generate_sensor_rows(aircraft, day, date, failures_today):
    """Generate 1-minute interval sensor rows for one day (ground + flight)."""
    rows = []
    aid = aircraft["id"]
    age_factor = min(aircraft["age_yrs"] / 15.0, 1.0)  # 0–1 aging factor

    # Determine degradation state for each active failure
    fail_states = {}
    for (fac, fsys, fday, fsev) in FAILURE_SCHEDULE:
        if fac != aid:
            continue
        prog, state = get_failure_progress(day, fday, lead_days=4)
        fail_states[fsys] = (prog, state)

    # 24 hours × 60 min = 1440 rows per aircraft per day
    for minute in range(0, 1440, 1):
        ts = date + timedelta(minutes=minute)
        hour = minute // 60

        # Determine flight phase by hour-of-day (simplified schedule)
        if hour < 5:
            phase = "GROUND_APU"
            apu_on = True
            engines_on = False
        elif hour < 6:
            phase = "PRE_FLIGHT"
            apu_on = True
            engines_on = False
        elif hour < 7:
            phase = "TAXI_OUT"
            apu_on = False
            engines_on = True
        elif hour < 8:
            phase = "CLIMB"
            apu_on = False
            engines_on = True
        elif hour < 13:
            phase = "CRUISE"
            apu_on = False
            engines_on = True
        elif hour < 14:
            phase = "DESCENT"
            apu_on = False
            engines_on = True
        elif hour < 15:
            phase = "LANDING"
            apu_on = False
            engines_on = True
        elif hour < 16:
            phase = "TAXI_IN"
            apu_on = False
            engines_on = True
        else:
            phase = "POST_FLIGHT"
            apu_on = True
            engines_on = False

        # Base drift grows slightly with age
        drift_base = age_factor * 0.001

        # ── APU sensors ──────────────────────────────────────────────────────
        apu_prog, apu_state = fail_states.get("APU", (0.0, "NORMAL"))
        apu_egt = add_noise(
            degrade(NORMALS["apu_egt_c"][0], 665, apu_prog),
            drift=drift_base * 50
        ) if apu_on else None
        apu_oil = add_noise(
            degrade(NORMALS["apu_oil_psi"][0], 32, apu_prog),
            drift=-drift_base * 5
        ) if apu_on else None
        apu_vib = add_noise(
            degrade(NORMALS["apu_vibration_g"][0], 2.5, apu_prog),
            std_pct=0.04
        ) if apu_on else None
        apu_rpm  = add_noise(NORMALS["apu_rpm_pct"][0])  if apu_on else None
        apu_otemp = add_noise(
            degrade(NORMALS["apu_oil_temp_c"][0], 158, apu_prog)
        ) if apu_on else None
        apu_bleed = add_noise(NORMALS["apu_bleed_psi"][0]) if apu_on else None

        # ── Landing Gear ─────────────────────────────────────────────────────
        lg_prog, lg_state = fail_states.get("LANDING_GEAR", (0.0, "NORMAL"))
        hyd_psi = add_noise(
            degrade(NORMALS["hyd_sys_psi"][0], 2400, lg_prog),
            drift=-drift_base * 30
        )
        brake_t = add_noise(
            degrade(NORMALS["brake_temp_c"][0], 520, lg_prog)
        ) if phase in ("LANDING", "TAXI_IN") else add_noise(80, std_pct=0.05)

        # ── Engine sensors ───────────────────────────────────────────────────
        eng_prog, eng_state = fail_states.get("ENGINE", (0.0, "NORMAL"))
        if engines_on:
            e1_egt  = add_noise(degrade(NORMALS["eng_egt_c"][0], 945, eng_prog), drift=drift_base * 80)
            e1_n1   = add_noise(NORMALS["eng_n1_pct"][0])
            e1_n2   = add_noise(NORMALS["eng_n2_pct"][0])
            e1_vib  = add_noise(degrade(NORMALS["eng_vib_ips"][0], 3.2, eng_prog), std_pct=0.05)
            e1_opsi = add_noise(degrade(NORMALS["eng_oil_psi"][0], 32, eng_prog))
            e1_otemp = add_noise(degrade(NORMALS["eng_oil_temp_c"][0], 162, eng_prog))
            e1_margin = round(930 - e1_egt, 1)
            e2_egt  = add_noise(NORMALS["eng_egt_c"][0])
            e2_n1   = add_noise(NORMALS["eng_n1_pct"][0])
            e2_vib  = add_noise(NORMALS["eng_vib_ips"][0], std_pct=0.05)
            e2_opsi = add_noise(NORMALS["eng_oil_psi"][0])
            e2_margin = round(930 - e2_egt, 1)
        else:
            e1_egt = e1_n1 = e1_n2 = e1_vib = e1_opsi = e1_otemp = e1_margin = None
            e2_egt = e2_n1 = e2_vib = e2_opsi = e2_margin = None

        # ── Avionics ─────────────────────────────────────────────────────────
        av_prog, av_state = fail_states.get("AVIONICS", (0.0, "NORMAL"))
        dc_bus  = add_noise(degrade(NORMALS["dc_bus_v"][0], 23.5, av_prog))
        pitot   = add_noise(degrade(NORMALS["pitot_amp"][0], 0, av_prog))
        fcc_t   = add_noise(degrade(NORMALS["fcc_temp_c"][0], 92, av_prog))
        arinc_e = round(max(0, add_noise(degrade(NORMALS["arinc_errors"][0], 12, av_prog), std_pct=0.5)), 1)
        bite_ct = int(av_prog * 6)

        # ── Bleed Air ────────────────────────────────────────────────────────
        bl_prog, bl_state = fail_states.get("BLEED", (0.0, "NORMAL"))
        bl_psi  = add_noise(degrade(NORMALS["bleed_psi"][0], 22, bl_prog)) if engines_on else None
        pc_temp = add_noise(degrade(NORMALS["precooler_temp_c"][0], 275, bl_prog)) if engines_on else None
        pc_dp   = add_noise(degrade(NORMALS["precooler_dp"][0], 6.5, bl_prog)) if engines_on else None

        # ── Missing value injection (2–5%) ───────────────────────────────────
        qf = 0
        if random.random() < 0.03:
            apu_egt = None; qf |= 4
        if random.random() < 0.02:
            hyd_psi = add_noise(hyd_psi or 3000, std_pct=0.04); qf |= 1  # drift

        rows.append({
            "aircraft_id":       aid,
            "ts":                ts.isoformat(),
            "flight_phase":      phase,
            "apu_egt_c":         apu_egt,
            "apu_oil_psi":       apu_oil,
            "apu_vibration_g":   apu_vib,
            "apu_rpm_pct":       apu_rpm,
            "apu_oil_temp_c":    apu_otemp,
            "apu_bleed_psi":     apu_bleed,
            "hyd_sys_psi":       hyd_psi,
            "brake_temp_c":      brake_t,
            "eng1_egt_c":        e1_egt,
            "eng1_n1_pct":       e1_n1,
            "eng1_n2_pct":       e1_n2,
            "eng1_vib_n1_ips":   e1_vib,
            "eng1_oil_psi":      e1_opsi,
            "eng1_oil_temp_c":   e1_otemp,
            "eng1_egt_margin_c": e1_margin,
            "eng2_egt_c":        e2_egt,
            "eng2_n1_pct":       e2_n1,
            "eng2_vib_n1_ips":   e2_vib,
            "eng2_oil_psi":      e2_opsi,
            "eng2_egt_margin_c": e2_margin,
            "dc_bus_28v":        dc_bus,
            "pitot_heat_amp":    pitot,
            "fcc_temp_c":        fcc_t,
            "arinc_errors_sec":  arinc_e,
            "bite_fault_count":  bite_ct,
            "bleed_duct_psi":    bl_psi,
            "precooler_temp_c":  pc_temp,
            "precooler_dp_psi":  pc_dp,
            "sensor_quality_flags": qf,
        })
    return rows


def generate_maintenance_logs(failures_per_aircraft):
    """Create maintenance log entries for each scheduled failure event."""
    logs = []
    SUBSYS_ATA = {"APU": "49", "ENGINE": "72", "LANDING_GEAR": "32",
                  "AVIONICS": "34", "BLEED": "36"}
    SUBSYS_DESC = {
        "APU":          "APU unscheduled removal — EGT exceedance trend confirmed",
        "ENGINE":       "Engine shop visit — vibration and EGT margin exceedance",
        "LANDING_GEAR": "Hydraulic actuator seal replacement — pressure decay confirmed",
        "AVIONICS":     "ADIRU / FCC fault isolation and LRU replacement",
        "BLEED":        "Bleed duct inspection and PRSOV valve replacement",
    }
    for (aid, subsys, fail_day, severity) in FAILURE_SCHEDULE:
        fail_date = datetime(2024, 1, 1) + timedelta(days=fail_day)
        log_id = f"MX-{aid}-{fail_date.strftime('%Y%m%d')}-{subsys[:3]}"
        dur = random.uniform(4, 48) if severity == "CRITICAL" else random.uniform(2, 16)
        aog = severity in ("HIGH", "CRITICAL")
        logs.append({
            "log_id":          log_id,
            "aircraft_id":     aid,
            "maintenance_type": "AOG" if aog else "UNSCHEDULED",
            "ata_chapter":     SUBSYS_ATA[subsys],
            "subsystem":       subsys,
            "description":     SUBSYS_DESC[subsys],
            "station":         "KLAX",
            "start_time":      fail_date.isoformat(),
            "end_time":        (fail_date + timedelta(hours=dur)).isoformat(),
            "duration_hours":  round(dur, 2),
            "aog_event":       aog,
            "aog_revenue_loss_usd": round(dur * 45000, 2) if aog else 0,
            "severity":        severity,
            "status":          "COMPLETED",
        })
    return logs


def generate_failure_labels(start_date):
    """Create ML ground-truth labels aligned with failure schedule."""
    labels = []
    ml_splits = ["TRAIN"] * 14 + ["VALIDATE"] * 2 + ["TEST"] * 2
    random.shuffle(ml_splits)
    for i, (aid, subsys, fail_day, severity) in enumerate(FAILURE_SCHEDULE):
        fail_ts = start_date + timedelta(days=fail_day)
        onset_ts = fail_ts - timedelta(hours=random.uniform(48, 120))
        labels.append({
            "label_id":           f"FL-{aid}-{fail_ts.strftime('%Y%m%d')}-{subsys[:3]}",
            "aircraft_id":        aid,
            "maintenance_log_id": f"MX-{aid}-{fail_ts.strftime('%Y%m%d')}-{subsys[:3]}",
            "subsystem":          subsys,
            "severity":           severity,
            "failure_confirmed_at": fail_ts.isoformat(),
            "degradation_onset_at": onset_ts.isoformat(),
            "lead_time_hours":    round((fail_ts - onset_ts).total_seconds() / 3600, 1),
            "label_window_start": (onset_ts - timedelta(hours=48)).isoformat(),
            "label_window_end":   fail_ts.isoformat(),
            "state":              "FAILURE",
            "confidence_pct":     round(random.uniform(88, 99), 1),
            "ml_use":             ml_splits[i % len(ml_splits)],
        })
    return labels


def main():
    parser = argparse.ArgumentParser(description="AOG Synthetic Data Generator")
    parser.add_argument("--preview", action="store_true", help="Generate 30-day preview only")
    parser.add_argument("--days", type=int, default=730, help="Number of days to generate")
    args = parser.parse_args()

    num_days = 30 if args.preview else args.days
    start_date = datetime(2024, 1, 1)
    suffix = "_preview" if args.preview else ""

    print(f"\n🛫  AOG Synthetic Data Generator — Agent 3")
    print(f"   Fleet: {len(FLEET)} aircraft | Duration: {num_days} days")
    print(f"   Start: {start_date.date()} | Rows/aircraft/day: 1440\n")

    # ── Aircraft Metadata ────────────────────────────────────────────────────
    meta_rows = [{
        "aircraft_id": a["id"], "registration": a["reg"],
        "series": a["series"], "engine_type": a["engine"],
        "age_years": a["age_yrs"], "base_flight_hours": a["base_fh"],
        "base_cycles": a["base_cycles"]
    } for a in FLEET]
    pd.DataFrame(meta_rows).to_csv(f"{OUT_DIR}/aircraft_metadata{suffix}.csv", index=False)
    print("✅  aircraft_metadata.csv written")

    # ── Flight Cycles ────────────────────────────────────────────────────────
    all_cycles = []
    for ac in FLEET:
        all_cycles.extend(generate_flight_cycles(ac, start_date, num_days))
    pd.DataFrame(all_cycles).to_csv(f"{OUT_DIR}/flight_cycles{suffix}.csv", index=False)
    print(f"✅  flight_cycles.csv written ({len(all_cycles):,} rows)")

    # ── Maintenance Logs ─────────────────────────────────────────────────────
    mx_rows = generate_maintenance_logs(FAILURE_SCHEDULE)
    if args.preview:
        mx_rows = [r for r in mx_rows if
                   datetime.fromisoformat(r["start_time"]) <= start_date + timedelta(days=30)]
    pd.DataFrame(mx_rows).to_csv(f"{OUT_DIR}/maintenance_logs{suffix}.csv", index=False)
    print(f"✅  maintenance_logs.csv written ({len(mx_rows)} rows)")

    # ── Failure Labels ───────────────────────────────────────────────────────
    lbl_rows = generate_failure_labels(start_date)
    pd.DataFrame(lbl_rows).to_csv(f"{OUT_DIR}/failure_labels{suffix}.csv", index=False)
    print(f"✅  failure_labels.csv written ({len(lbl_rows)} rows)")

    # ── Sensor Telemetry (largest file) ─────────────────────────────────────
    tel_path = f"{OUT_DIR}/sensor_telemetry{suffix}.csv"
    header_written = False
    total_rows = 0

    for ac in FLEET:
        print(f"\n   Generating telemetry for {ac['id']} ({ac['reg']})...")
        ac_rows = []
        fail_days = {fday: (fsys, fsev)
                     for (fac, fsys, fday, fsev) in FAILURE_SCHEDULE if fac == ac["id"]}
        for d in tqdm(range(num_days), unit="day", ncols=70):
            failures_today = fail_days.get(d, None)
            ac_rows.extend(generate_sensor_rows(ac, d, start_date + timedelta(days=d), failures_today))
            # Flush every 10 days to limit RAM usage
            if len(ac_rows) >= 14400:
                df = pd.DataFrame(ac_rows)
                df.to_csv(tel_path, mode="a", header=not header_written, index=False)
                header_written = True
                total_rows += len(df)
                ac_rows = []
        if ac_rows:
            df = pd.DataFrame(ac_rows)
            df.to_csv(tel_path, mode="a", header=not header_written, index=False)
            header_written = True
            total_rows += len(df)

    size_mb = os.path.getsize(tel_path) / (1024 * 1024)
    print(f"\n✅  sensor_telemetry.csv written ({total_rows:,} rows, {size_mb:.1f} MB)")
    print(f"\n🎉  Done! All files saved to: {os.path.abspath(OUT_DIR)}\n")


if __name__ == "__main__":
    main()
