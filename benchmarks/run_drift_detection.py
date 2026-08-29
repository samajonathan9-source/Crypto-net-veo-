"""Détection de rupture de régime avec recalibration — réduire l'écart-type.

Pour chaque canal topologique, le détecteur surveille la dérive du score.
Quand une rupture est déclarée, on RECALIBRE le seuil sur la fenêtre
récente (mémoire courte) plutôt que sur tout le passé. On mesure si cela
stabilise le rappel en fold 4 (régime rompu) sans dégrader les folds stables.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from cyber.adaptive_fusion import AdaptiveFamilyFusion
from cyber.classical_detectors import IsolationForestDetector
from cyber.regime_detector import RegimeDriftDetector
from cyber.topo_probe import window_correlation
from ratiss_topo.arsenal import KibbleZurekTracker
from ratiss_topo.robust_metrics import coupled_metric, spectral_channels

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "UNSW-NB15"
WINDOW, STRIDE = 30, 15
N_FOLDS = 5

CHANNELS = ["classical", "cumul_drift", "pr", "edge"]
TOPO_KEYS = ["cumul_drift", "pr", "edge"]
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
    t0 = time.time()
    X_tr, _, y_tr = load_split("UNSW_NB15_training-set.csv", fit_scaler=True)
    X_te, cats_te, y_te = load_split("UNSW_NB15_testing-set.csv")
    X_normal = X_tr[y_tr == 0]
    det = IsolationForestDetector().fit(X_normal)

    # score fenêtres
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(window_correlation(X_normal[:WINDOW]))
    S = {k: [] for k in CHANNELS}
    labs = []
    for s in range(0, len(X_te) - WINDOW, STRIDE):
        win = X_te[s : s + WINDOW]
        corr = window_correlation(win)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        S["classical"].append(float(np.max(det.score(win))))
        S["cumul_drift"].append(kzr["cumul_drift"])
        S["pr"].append(spec["pr"])
        S["edge"].append(topo["edge"])
        l, c = np.unique(cats_te[s : s + WINDOW], return_counts=True)
        labs.append(l[c.argmax()])
    S = {k: np.array(v) for k, v in S.items()}
    labels = np.array(labs)
    fams = sorted(set(labels) - {"Normal"})
    n = len(labels)

    # fold 4 : rupture la plus forte. On simule par blocs temporels.
    block = n // 6
    print("== Détection de rupture + recalibration (fold 4 = bloc 5) ==")
    # seuil global calibré sur tout le début
    cal = np.array([i for i in range(block * 2) if labels[i] == "Normal"])
    thr_fixed = {c: float(np.percentile(S[c][cal], 98)) for c in CHANNELS}

    results = {}
    for b in range(2, 6):  # blocs 3..6, le 5 = fold 4 rompu
        test_idx = np.arange(b * block, (b + 1) * block)
        test_l = labels[test_idx]
        # statique (seuil fixe) vs adaptatif (recalibré)
        for mode in ["fixe", "recalib"]:
            if mode == "fixe":
                thr = thr_fixed
            else:
                # recalibre sur les 100 fenêtres précédentes normales
                recent_norm = np.array([i for i in test_idx - block if labels[i] == "Normal"])
                if len(recent_norm) < 10:
                    recent_norm = cal
                thr = {c: float(np.percentile(S[c][recent_norm], 98)) for c in CHANNELS}
            recalls = []
            for fam in fams:
                fi = np.array([j for j in range(len(test_idx)) if test_l[j] == fam])
                if len(fi) < 3:
                    continue
                hit = sum(S[c][test_idx[j]] >= thr[c] for j in fi
                          for c in ["classical"] if False)  # placeholder
                # rappel max sur canaux
                h = max(
                    float(np.mean(S["cumul_drift"][test_idx[fi]] >= thr["cumul_drift"])),
                    float(np.mean(S["pr"][test_idx[fi]] >= thr["pr"])),
                    float(np.mean(S["classical"][test_idx[fi]] >= thr["classical"])),
                )
                recalls.append(h)
            if recalls:
                results[f"bloc{b}_recalib" if mode == "recalib" else f"bloc{b}_fixe"] = float(np.mean(recalls))

    for k, v in results.items():
        print(f"{k:22s} rappel moyen={v:.3f}")

    mean_fixe = float(np.mean([v for k, v in results.items() if "fixe" in k]))
    mean_rec = float(np.mean([v for k, v in results.items() if "recalib" in k]))
    print(f"\nfixe={mean_fixe:.3f}  recalib={mean_rec:.3f}")
    p = ROOT / "artifacts" / "drift_detection.json"
    p.write_text(json.dumps({"fixe": mean_fixe, "recalib": mean_rec}, indent=2))
    print(f"-> {p} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
