"""Calibration dynamique vs fixe sur UNSW-NB15.

On compare un seuil percentile fixe (Phase 5) à une recalibration online
sur fenêtre glissante (OnlineFPSCalibrator). On mesure si le FPR se
stabilise ~2% et si le rappel s'améliore.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from cyber.classical_detectors import IsolationForestDetector
from cyber.dynamic_calibration import OnlineFPSCalibrator
from cyber.topo_probe import window_correlation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "UNSW-NB15"
WINDOW, STRIDE = 30, 15
_SCALER: dict | None = None


def load_split(file: str, fit_scaler: bool = False):
    global _SCALER
    df = pd.read_csv(DATA / file)
    cats = df["attack_cat"].astype(str).values
    y = df["label"].values.astype(int)
    num = df.select_dtypes("number").drop(columns=["label"], errors="ignore")
    X = num.values.astype(float)
    if fit_scaler or _SCALER is None:
        _SCALER = {"mu": X.mean(axis=0),
                    "sd": np.where(X.std(axis=0) == 0, 1.0, X.std(axis=0))}
    X = (X - _SCALER["mu"]) / _SCALER["sd"]
    return X, cats, y


def main() -> None:
    X_tr, _, y_tr = load_split("UNSW_NB15_training-set.csv", fit_scaler=True)
    X_te, cats_te, y_te = load_split("UNSW_NB15_testing-set.csv")
    det = IsolationForestDetector().fit(X_tr[y_tr == 0])

    scores, labels = [], []
    for s in range(0, len(X_te) - WINDOW, STRIDE):
        win = X_te[s : s + WINDOW]
        scores.append(float(np.max(det.score(win))))
        labels.append("Normal" if np.mean(y_te[s : s + WINDOW] == 0) > 0.5 else "attaque")
    scores = np.array(scores)
    labels = np.array(labels)

    # split calibration/eval : normal comme référence online
    cal = scores[labels == "Normal"][:500]
    dyn = OnlineFPSCalibrator(target_fpr=0.02, window=200)
    for s in cal:
        dyn.update_normal(s)
    fixed_thr = float(np.percentile(cal, 98))

    fams = sorted(set(labels) - {"Normal"})
    results = {}
    for fam in fams:
        idx = np.where(labels == fam)[0]
        if len(idx) < 3:
            continue
        rec_fix = float(np.mean(scores[idx] > fixed_thr))
        rec_dyn = float(np.mean(scores[idx] > dyn.threshold()))
        results[fam] = {"fixe": rec_fix, "dynamique": rec_dyn}

    print("== Calibration dynamique vs fixe (rappel par famille) ==")
    for fam, r in results.items():
        print(f"{fam:14s} fixe={r['fixe']:.2f}  dynamique={r['dynamique']:.2f}")
    m_fix = float(np.mean([r['fixe'] for r in results.values()]))
    m_dyn = float(np.mean([r['dynamique'] for r in results.values()]))
    print(f"\nrappel moyen: fixe={m_fix:.3f}  dynamique={m_dyn:.3f}")
    p = ROOT / "artifacts" / "dynamic_calibration.json"
    p.write_text(json.dumps({"fixe": m_fix, "dynamique": m_dyn, "per_family": results}, indent=2))
    print(f"-> {p}")


if __name__ == "__main__":
    main()
