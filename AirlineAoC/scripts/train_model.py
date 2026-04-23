"""
AOG Predictive Maintenance — ML Model Training Script
Trains two complementary models:
  1. Isolation Forest  — anomaly detection (unsupervised, finds degraded states)
  2. Random Forest     — failure classification (supervised, predicts failure mode + subsystem)

Usage:
    python train_model.py --data ../data --output ../models

Requirements: pip install pandas numpy scikit-learn joblib tqdm
"""

import argparse
import json
import os
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)

SUBSYSTEMS = ["APU", "ENGINE", "LANDING_GEAR", "AVIONICS", "BLEED"]

# Features per subsystem used by the supervised classifier
FEATURE_MAP = {
    "APU": [
        "apu_egt_c", "apu_oil_psi", "apu_vibration_g",
        "apu_rpm_pct", "apu_oil_temp_c", "apu_bleed_psi",
    ],
    "ENGINE": [
        "eng1_egt_c", "eng1_n1_pct", "eng1_n2_pct",
        "eng1_vib_n1_ips", "eng1_oil_psi", "eng1_oil_temp_c",
        "eng1_egt_margin_c",
    ],
    "LANDING_GEAR": [
        "hyd_sys_psi", "brake_temp_c",
        "eng1_oil_psi",  # proxy when LG-specific missing
    ],
    "AVIONICS": [
        "dc_bus_28v", "pitot_heat_amp",
        "fcc_temp_c", "arinc_errors_sec", "bite_fault_count",
    ],
    "BLEED": [
        "bleed_duct_psi", "precooler_temp_c", "precooler_dp_psi",
    ],
}

# Global features always included
GLOBAL_FEATURES = ["sensor_quality_flags"]


def load_telemetry(data_dir, preview=True):
    fname = "sensor_telemetry_preview.csv" if preview else "sensor_telemetry.csv"
    path = os.path.join(data_dir, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found at {path}.\n"
            f"Run: python generate_data.py {'--preview' if preview else ''}"
        )
    print(f"  Loading {fname}...")
    df = pd.read_csv(path, parse_dates=["ts"])
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def load_labels(data_dir):
    path = os.path.join(data_dir, "failure_labels.csv")
    return pd.read_csv(path, parse_dates=["degradation_onset_at", "failure_confirmed_at",
                                          "label_window_start", "label_window_end"])


def engineer_features(df, subsystem):
    """Add rolling statistics and derived features for a given subsystem."""
    feats = FEATURE_MAP.get(subsystem, []) + GLOBAL_FEATURES
    cols_present = [c for c in feats if c in df.columns]

    df = df.sort_values(["aircraft_id", "ts"]).copy()

    for col in cols_present:
        if col == "sensor_quality_flags":
            continue
        # 1-hour rolling mean and std (60 min × 1 sample/min)
        df[f"{col}_roll60_mean"] = (
            df.groupby("aircraft_id")[col]
            .transform(lambda x: x.rolling(60, min_periods=1).mean())
        )
        df[f"{col}_roll60_std"] = (
            df.groupby("aircraft_id")[col]
            .transform(lambda x: x.rolling(60, min_periods=1).std().fillna(0))
        )
        # 6-hour trend slope proxy (difference from 6h ago)
        df[f"{col}_delta360"] = (
            df.groupby("aircraft_id")[col]
            .transform(lambda x: x.diff(360).fillna(0))
        )

    return df


def build_training_set(tel_df, label_df, subsystem):
    """
    Create a labeled dataset for the supervised classifier.
    Label windows from failure_labels are marked with state.
    All other rows are NORMAL.
    """
    sub_labels = label_df[label_df["subsystem"] == subsystem].copy()
    if sub_labels.empty:
        print(f"  No labels found for {subsystem}, skipping supervised training.")
        return None, None

    # Engineer features
    tel_df = engineer_features(tel_df, subsystem)

    feat_cols = (
        FEATURE_MAP.get(subsystem, []) +
        GLOBAL_FEATURES +
        [c for c in tel_df.columns if any(
            c.startswith(b) for b in FEATURE_MAP.get(subsystem, [])
            if "_roll" in c or "_delta" in c
        )]
    )
    feat_cols = list(dict.fromkeys([c for c in feat_cols if c in tel_df.columns]))

    # Assign labels
    tel_df["label"] = "NORMAL"
    for _, row in sub_labels.iterrows():
        mask = (
            (tel_df["aircraft_id"] == row["aircraft_id"]) &
            (tel_df["ts"] >= row["label_window_start"]) &
            (tel_df["ts"] <= row["label_window_end"])
        )
        tel_df.loc[mask, "label"] = row["state"]

    # Downsample NORMAL to balance classes (5:1 ratio)
    normal = tel_df[tel_df["label"] == "NORMAL"].sample(
        n=min(len(tel_df[tel_df["label"] != "NORMAL"]) * 5, 50000),
        random_state=SEED
    )
    anomaly = tel_df[tel_df["label"] != "NORMAL"]
    balanced = pd.concat([normal, anomaly]).sample(frac=1, random_state=SEED)

    X = balanced[feat_cols].fillna(method="ffill").fillna(0)
    y = balanced["label"]

    return X, y


def train_isolation_forest(tel_df, subsystem, output_dir):
    """Train unsupervised anomaly detector on NORMAL data only."""
    print(f"\n  [Isolation Forest] {subsystem}")

    feats = FEATURE_MAP.get(subsystem, []) + GLOBAL_FEATURES
    cols = [c for c in feats if c in tel_df.columns]

    normal_data = tel_df[tel_df["sensor_quality_flags"] == 0][cols].dropna()
    if len(normal_data) < 100:
        print(f"  Not enough clean data for {subsystem}, skipping.")
        return None

    # Sample up to 50k rows for speed
    sample = normal_data.sample(n=min(len(normal_data), 50000), random_state=SEED)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(sample)

    model = IsolationForest(
        n_estimators=100,
        contamination=0.05,   # expect ~5% anomalies in data
        max_samples="auto",
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # Save model + scaler together
    bundle = {"model": model, "scaler": scaler, "features": cols,
              "subsystem": subsystem, "model_type": "IsolationForest"}
    path = os.path.join(output_dir, f"iforest_{subsystem.lower()}.joblib")
    joblib.dump(bundle, path)
    print(f"  Saved → {path}")
    return bundle


def train_random_forest(X, y, subsystem, output_dir):
    """Train supervised failure classifier."""
    print(f"\n  [Random Forest Classifier] {subsystem}")

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y_enc, test_size=0.2, random_state=SEED, stratify=y_enc
    )

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
    )
    clf.fit(X_tr_s, y_tr)

    y_pred = clf.predict(X_te_s)
    print(classification_report(y_te, y_pred, target_names=le.classes_))

    # Feature importance
    importances = pd.Series(clf.feature_importances_, index=X.columns)
    top10 = importances.nlargest(10)
    print(f"  Top features:\n{top10.to_string()}")

    # Compute AUC for binary case
    if len(le.classes_) == 2:
        auc = roc_auc_score(y_te, clf.predict_proba(X_te_s)[:, 1])
        print(f"  ROC-AUC: {auc:.4f}")

    bundle = {
        "model": clf,
        "scaler": scaler,
        "label_encoder": le,
        "features": list(X.columns),
        "subsystem": subsystem,
        "model_type": "RandomForestClassifier",
        "classes": list(le.classes_),
    }
    path = os.path.join(output_dir, f"rf_{subsystem.lower()}.joblib")
    joblib.dump(bundle, path)
    print(f"  Saved → {path}")

    # Save feature importances as JSON for dashboard
    fi_path = os.path.join(output_dir, f"feature_importance_{subsystem.lower()}.json")
    with open(fi_path, "w") as f:
        json.dump(importances.nlargest(20).to_dict(), f, indent=2)

    return bundle


def score_fleet(tel_df, iforest_bundles, rf_bundles, output_dir):
    """Run inference on recent 48-hour window and produce risk scores."""
    print("\n  Scoring fleet (last 48h)...")
    recent = tel_df[tel_df["ts"] >= tel_df["ts"].max() - pd.Timedelta(hours=48)]

    results = []
    for ac_id in recent["aircraft_id"].unique():
        ac_df = recent[recent["aircraft_id"] == ac_id]
        for subsystem in SUBSYSTEMS:
            bundle = iforest_bundles.get(subsystem)
            if bundle is None:
                continue
            cols = bundle["features"]
            X = ac_df[[c for c in cols if c in ac_df.columns]].fillna(0)
            if X.empty:
                continue
            X_s = bundle["scaler"].transform(X[bundle["features"]])
            scores = -bundle["model"].score_samples(X_s)  # higher = more anomalous
            anomaly_rate = float((scores > np.percentile(scores, 90)).mean())

            # Override with RF prediction if available
            rf = rf_bundles.get(subsystem)
            if rf:
                rf_feats = [c for c in rf["features"] if c in ac_df.columns]
                Xrf = ac_df[rf_feats].fillna(method="ffill").fillna(0)
                if not Xrf.empty:
                    Xrf_s = rf["scaler"].transform(Xrf)
                    proba = rf["model"].predict_proba(Xrf_s)
                    failure_idx = list(rf["label_encoder"].classes_).index("FAILURE") \
                        if "FAILURE" in rf["label_encoder"].classes_ else -1
                    if failure_idx >= 0:
                        anomaly_rate = float(proba[:, failure_idx].max())

            risk_cat = ("CRITICAL" if anomaly_rate > 0.8 else
                        "HIGH"     if anomaly_rate > 0.6 else
                        "MODERATE" if anomaly_rate > 0.35 else "LOW")
            results.append({
                "aircraft_id": ac_id,
                "subsystem": subsystem,
                "risk_score": round(anomaly_rate, 4),
                "risk_category": risk_cat,
            })

    out = pd.DataFrame(results)
    path = os.path.join(output_dir, "fleet_risk_scores.csv")
    out.to_csv(path, index=False)
    print(f"  Fleet risk scores saved → {path}")
    return out


def main():
    parser = argparse.ArgumentParser(description="AOG ML Model Trainer")
    parser.add_argument("--data",    default="../data",   help="Path to data directory")
    parser.add_argument("--output",  default="../models", help="Path to save model files")
    parser.add_argument("--preview", action="store_true", help="Use 30-day preview dataset")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print("\n🤖  AOG ML Model Trainer")
    print(f"   Data: {args.data} | Models: {args.output}\n")

    tel_df = load_telemetry(args.data, preview=args.preview)
    lbl_df = load_labels(args.data)

    iforest_bundles = {}
    rf_bundles = {}

    for subsystem in SUBSYSTEMS:
        print(f"\n{'='*50}")
        print(f"  Subsystem: {subsystem}")

        # 1. Isolation Forest (unsupervised)
        bundle = train_isolation_forest(tel_df, subsystem, args.output)
        if bundle:
            iforest_bundles[subsystem] = bundle

        # 2. Random Forest (supervised)
        X, y = build_training_set(tel_df, lbl_df, subsystem)
        if X is not None and len(X) > 50:
            rb = train_random_forest(X, y, subsystem, args.output)
            if rb:
                rf_bundles[subsystem] = rb

    # 3. Score fleet
    score_fleet(tel_df, iforest_bundles, rf_bundles, args.output)

    print("\n🎉  Training complete!")
    print(f"   Models saved to: {os.path.abspath(args.output)}")
    print(f"   Run with --preview flag for quick training on 30-day dataset.\n")


if __name__ == "__main__":
    main()
