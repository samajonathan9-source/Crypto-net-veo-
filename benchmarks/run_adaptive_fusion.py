"""Fusion adaptative vs statique sur UNSW-NB15.

Compare :
1. meilleur canal unique global (statique)
2. oracle (meilleur canal par famille — borne supérieure)
3. fusion adaptative (routeur à centroïdes appris sur calibration)

Le routeur apprend les centroïdes topologiques par famille sur un split,
puis route chaque fenêtre de test vers son canal optimal. C'est l'argument
central du papier SMI : un IDS qui sait quand utiliser quelle compétence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from cyber.adaptive_fusion import AdaptiveFamilyFusion
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

CHANNELS = ["classical", "psig", "pr", "edge", "entropie", "frustration", "cumul_drift"]
TOPO_KEYS = ["psig", "pr", "edge", "entropie", "frustration", "cumul_drift"]

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


def score_windows(X, cats, detectors, kz):
    starts = range(0, len(X) - WINDOW, STRIDE)
    scores = {k: [] for k in CHANNELS}
    labels, purities = [], []
    for s in starts:
        win = X[s : s + WINDOW]
        corr = window_correlation(win)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        scores["classical"].append(max(float(np.max(d.score(win))) for d in detectors.values()))
        scores["psig"].append(topo["psig_seuille"])
        scores["pr"].append(spec["pr"])
        scores["edge"].append(topo["edge"])
        scores["entropie"].append(topo["entropie"])
        scores["frustration"].append(triad_frustration(corr))
        scores["cumul_drift"].append(kzr["cumul_drift"])
        wl = cats[s : s + WINDOW]
        labs, counts = np.unique(wl, return_counts=True)
        b = counts.argmax()
        labels.append(labs[b])
        purities.append(counts[b] / WINDOW)
    return {k: np.array(v) for k, v in scores.items()}, np.array(labels), np.array(purities)


def topo_vector(scores, i):
    return np.array([scores[k][i] for k in TOPO_KEYS])


def main() -> None:
    t0 = time.time()
    X_tr, cats_tr, y_tr = load_split("UNSW_NB15_training-set.csv", fit_scaler=True)
    X_te, cats_te, y_te = load_split("UNSW_NB15_testing-set.csv")

    X_normal = X_tr[y_tr == 0]
    detectors = {
        "IF": IsolationForestDetector().fit(X_normal),
        "OC-SVM": OneClassSVMDetector().fit(X_normal),
        "PCA-AE": PCAAutoencoderDetector().fit(X_normal),
    }
    ref = window_correlation(X_normal[:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref)

    scores, win_labels, purity = score_windows(X_te, cats_te, detectors, kz)
    usable = purity >= 0.5
    idx = np.where(usable)[0]
    normal_idx = np.array([i for i in idx if win_labels[i] == "Normal"])
    rng = np.random.default_rng(7)
    rng.shuffle(normal_idx)
    n_cal = int(0.6 * len(normal_idx))
    cal_idx, eval_idx = normal_idx[:n_cal], normal_idx[n_cal:]

    # seuils par canal à FPR 2% sur calibration
    thr = {c: float(np.percentile(scores[c][cal_idx], 98)) for c in CHANNELS}

    # --- rappels par famille (pour oracle + apprentissage table) ---
    families = sorted(set(win_labels[idx]) - {"Normal"})
    recalls = {}
    for fam in families:
        fi = np.array([i for i in idx if win_labels[i] == fam])
        if len(fi) < 3:
            continue
        recalls[fam] = {c: float(np.mean(scores[c][fi] >= thr[c])) for c in CHANNELS}

    # oracle : meilleur canal par famille
    oracle_recall = []
    for fam, r in recalls.items():
        best = max(r, key=r.get)
        oracle_recall.append(r[best])
    oracle = float(np.mean(oracle_recall))

    # statique : meilleur canal unique global
    static = {c: float(np.mean([recalls[f][c] for f in recalls])) for c in CHANNELS}
    static_best = max(static, key=static.get)

    # --- fusion adaptative : routeur à centroïdes appris sur CALIBRATION ---
    cal_set = np.array(list(cal_idx) + [i for i in idx if win_labels[i] != "Normal"])
    # on n'utilise que les fenêtres de calibration + attaques pour apprendre les centroïdes
    fusion = AdaptiveFamilyFusion()
    topo_cal = np.array([topo_vector(scores, i) for i in cal_set])
    fam_cal = np.array([win_labels[i] for i in cal_set])
    fusion.fit(topo_cal, fam_cal)
    fusion.learn_channel_map(recalls)

    # évaluation sur eval_idx (normal) : FPR adaptatif
    fp = 0
    for i in eval_idx:
        r = fusion.route(topo_vector(scores, i), {c: scores[c][i] for c in CHANNELS})
        if r["score"] >= thr[r["channel"]]:
            fp += 1
    adaptive_fpr = fp / max(len(eval_idx), 1)

    # rappel adaptatif par famille
    adaptive_recall = {}
    for fam in recalls:
        fi = np.array([i for i in idx if win_labels[i] == fam])
        hit = 0
        for i in fi:
            r = fusion.route(topo_vector(scores, i), {c: scores[c][i] for c in CHANNELS})
            if r["score"] >= thr[r["channel"]]:
                hit += 1
        adaptive_recall[fam] = hit / len(fi)
    adaptive = float(np.mean(list(adaptive_recall.values())))

    print("== Résultat UNSW-NB15 (fusion adaptative) ==")
    print(f"oracle (meilleur canal/famille)  : {oracle:.3f}")
    print(f"statique (meilleur canal global: {static_best}) : {static[static_best]:.3f}")
    print(f"adaptatif (routeur centroïdes)   : {adaptive:.3f}  (FPR {adaptive_fpr:.3f})")
    print("\nrappel par famille (adaptatif) :")
    for fam, r in adaptive_recall.items():
        print(f"  {fam:14s} {r:.2f}")

    out = {
        "oracle": round(oracle, 3),
        "static": round(static[static_best], 3),
        "static_channel": static_best,
        "adaptive": round(adaptive, 3),
        "adaptive_fpr": round(adaptive_fpr, 3),
        "per_family": {k: round(v, 3) for k, v in adaptive_recall.items()},
        "channel_map": fusion.channel_map,
        "runtime_s": round(time.time() - t0, 1),
    }
    p = ROOT / "artifacts" / "adaptive_fusion.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"\n-> {p} ({out['runtime_s']}s)")


if __name__ == "__main__":
    main()
