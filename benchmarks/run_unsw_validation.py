"""Validation réelle UNSW-NB15 — l'arsenal topologique sur vrai trafic.

Le concept a été prouvé sur le synthétique KS-validé (Phases 3-5). UNSW-NB15
apporte le trafic RÉEL : 9 familles d'attaques modernes (Generic, Exploits,
Fuzzers, DoS, Recon, Backdoor, Shellcode, Worms). Protocole :

1. les classiques tant que système de base (IsolationForest, OC-SVM, PCA-AE)
2. les canaux topologiques structurels (P_sig, PR, edge, entropie, KZ cumul)
3. protocole honnête : split calibration (normal de train) / évaluation (test)

La question centrale : la structure spectrale aide-t-elle sur du trafic
réel, ou l'effet n'existe que sur le synthétique ?
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from cyber.classical_detectors import (
    IsolationForestDetector,
    OneClassSVMDetector,
    PCAAutoencoderDetector,
)
from cyber.topo_probe import window_correlation
from ratiss_topo.arsenal import KibbleZurekTracker, triad_frustration
from ratiss_topo.robust_metrics import coupled_metric, spectral_channels

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets" / "UNSW-NB15"
WINDOW, STRIDE = 30, 15
FPR_TARGET = 0.02

CHANNELS = ["classical", "psig", "pr", "edge", "entropie", "frustration", "cumul_drift"]


_SCALER: dict | None = None

def load_split(file: str, fit_scaler: bool = False):
    """Charge train/test. Standardise (z-score) ; le scaler est calibré sur
    le train (fit_scaler=True) et réutilisé pour le test — les échelles UNSW
    sont trop hétérogènes (var 23→1.9e10) pour des corrélations sans cela."""
    global _SCALER
    df = pd.read_csv(DATA / file)
    cats = df["attack_cat"].astype(str).values
    y = df["label"].values.astype(int)
    num = df.select_dtypes("number").drop(columns=["label"], errors="ignore")
    X = num.values.astype(float)
    if fit_scaler or _SCALER is None:
        _SCALER = {"mu": X.mean(axis=0), "sd": np.where(X.std(axis=0) == 0, 1.0, X.std(axis=0))}
    X = (X - _SCALER["mu"]) / _SCALER["sd"]
    return X, cats, y


def score_windows(X, cats, y, detectors, ref_corr, kz):
    """Score toutes les fenêtres sur tous les canaux."""
    starts = range(0, len(X) - WINDOW, STRIDE)
    scores = {k: [] for k in CHANNELS}
    labels, purity = [], []
    for s in starts:
        win = X[s : s + WINDOW]
        corr = window_correlation(win)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        # max (pas mean) sur la fenêtre : une attaque doit dépasser le seuil
        # même entourée de normal — la moyenne dilue le signal
        scores["classical"].append(
            max(float(np.max(d.score(win))) for d in detectors.values())
        )
        scores["psig"].append(topo["psig_seuille"])
        scores["pr"].append(spec["pr"])
        scores["edge"].append(topo["edge"])
        scores["entropie"].append(topo["entropie"])
        scores["frustration"].append(triad_frustration(corr))
        scores["cumul_drift"].append(kzr["cumul_drift"])
        wl = cats[s : s + WINDOW]
        wy = y[s : s + WINDOW]
        # label dominant + sa fraction (pureté)
        labs, counts = np.unique(wl, return_counts=True)
        best = counts.argmax()
        labels.append(labs[best])
        purity.append(float(counts[best]) / WINDOW)
    return {k: np.array(v) for k, v in scores.items()}, np.array(labels), np.array(purity)


def main() -> None:
    t0 = time.time()
    X_tr, cats_tr, y_tr = load_split("UNSW_NB15_training-set.csv", fit_scaler=True)
    X_te, cats_te, y_te = load_split("UNSW_NB15_testing-set.csv")

    # normal de train pour calibrer les classiques + la référence KZ
    X_normal_tr = X_tr[y_tr == 0]
    if len(X_normal_tr) < WINDOW * 5:
        print("pas assez de normal"); return
    detectors = {
        "IF": IsolationForestDetector().fit(X_normal_tr),
        "OC-SVM": OneClassSVMDetector().fit(X_normal_tr),
        "PCA-AE": PCAAutoencoderDetector().fit(X_normal_tr),
    }
    ref_corr = window_correlation(X_normal_tr[:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)

    # score le flux de TEST
    scores, win_labels, purity = score_windows(X_te, cats_te, y_te, detectors, ref_corr, kz)
    # pureté >= 50% : le test set UNSW mélange les attaques, une fenêtre est
    # attribuée à sa famille dominante si elle représente au moins 50%
    pure = purity >= 0.5
    print(f"fenêtres : {len(win_labels)} ({pure.mean():.0%} utilisables)")

    # calibration des seuils sur le normal du test (60%) / évaluation (40%)
    normal_idx = np.where(win_labels == "Normal")[0]
    rng = np.random.default_rng(7)
    rng.shuffle(normal_idx)
    n_cal = int(0.6 * len(normal_idx))
    cal_normal, eval_normal = normal_idx[:n_cal], normal_idx[n_cal:]

    thresholds = {c: float(np.percentile(scores[c][cal_normal], 98)) for c in CHANNELS}

    families = sorted(set(win_labels) - {"Normal"})
    print(f"== Rappel @ FPR 2% par famille (UNSW-NB15, {len(win_labels)} fenêtres) ==")
    header = "Famille".ljust(18) + "".join(c.ljust(12) for c in ["classique", "PR", "KZ_cum"])
    print(header)
    results = {}
    best_recall = []
    for fam in families:
        fam_idx = np.where(pure & (win_labels == fam))[0]
        if len(fam_idx) < 3:
            continue
        recs = {c: float(np.mean(scores[c][fam_idx] >= thresholds[c])) for c in CHANNELS}
        results[fam] = {k: round(v, 3) for k, v in recs.items()}
        best_c = max(recs, key=recs.get)
        best_recall.append(recs[best_c])
        print(fam.ljust(18) + "".join(f"{recs[c]:.2f}".ljust(12) for c in ["classical", "pr", "cumul_drift"])
              + f"| best={best_c}")

    mean_recall = float(np.mean(best_recall)) if best_recall else 0.0
    print(f"\nRappel moyen (meilleur canal par famille) : {mean_recall:.2f}")

    out = {
        "n_windows": int(len(win_labels)),
        "fpr_target": FPR_TARGET,
        "mean_recall": round(mean_recall, 3),
        "per_family": results,
        "runtime_s": round(time.time() - t0, 1),
    }
    p = ROOT / "artifacts" / "unsw_validation.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"-> {p} ({out['runtime_s']}s)")


if __name__ == "__main__":
    main()
