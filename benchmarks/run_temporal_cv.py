"""Validation croisée temporelle — crédibilité statistique de la fusion.

La fiche AGI (Condition 9) et les reviewers SMI exigent que le résultat ne
dépende pas d'un split chanceux. On évalue la fusion adaptative par
TimeSeriesSplit (5 folds) sur le flux UNSW-NB15 : chaque fold entraîne le
routeur à centroïdes sur le passé, évalue sur le futur. On rapporte la
moyenne ± écart-type du rappel — le résultat est robuste si la variance
est faible.
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
N_FOLDS = 5

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


def topo_of(corr, kz):
    topo = coupled_metric(corr)
    spec = spectral_channels(corr)
    kzr = kz.update(corr)
    return {
        "psig": topo["psig_seuille"], "pr": spec["pr"], "edge": topo["edge"],
        "entropie": topo["entropie"], "frustration": triad_frustration(corr),
        "cumul_drift": kzr["cumul_drift"],
    }


def main() -> None:
    t0 = time.time()
    X_tr, _, y_tr = load_split("UNSW_NB15_training-set.csv", fit_scaler=True)
    X_te, cats_te, y_te = load_split("UNSW_NB15_testing-set.csv")

    X_normal = X_tr[y_tr == 0]
    detectors = {
        "IF": IsolationForestDetector().fit(X_normal),
        "OC-SVM": OneClassSVMDetector().fit(X_normal),
        "PCA-AE": PCAAutoencoderDetector().fit(X_normal),
    }

    # score toutes les fenêtres du test (label dominant, pureté)
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(window_correlation(X_normal[:WINDOW]))
    S = {k: [] for k in CHANNELS}
    labels = np.array([])
    labs_list, pur_list = [], []
    for s in range(0, len(X_te) - WINDOW, STRIDE):
        win = X_te[s : s + WINDOW]
        corr = window_correlation(win)
        topo = topo_of(corr, kz)
        S["classical"].append(max(float(np.max(d.score(win))) for d in detectors.values()))
        for k in TOPO_KEYS:
            S[k].append(topo[k])
        wl = cats_te[s : s + WINDOW]
        l, c = np.unique(wl, return_counts=True)
        b = c.argmax()
        labs_list.append(l[b]); pur_list.append(c[b] / WINDOW)
    S = {k: np.array(v) for k, v in S.items()}
    labels = np.array(labs_list)
    pure = np.array(pur_list) >= 0.5
    idx_all = np.where(pure)[0]

    print(f"fenêtres utilisables : {len(idx_all)}")
    families = sorted(set(labels[idx_all]) - {"Normal"})

    # CV temporelle : découper le flux de fenêtres en N_FOLDS blocs
    fold_results = []
    for fold in range(N_FOLDS):
        # split temporel : train = fenêtres normales jusqu'à fold, test = bloc fold+1
        n = len(idx_all)
        cut = int((fold + 1) * n / (N_FOLDS + 1))
        train_idx = idx_all[:cut]
        test_idx = idx_all[cut:]
        normal_train = np.array([i for i in train_idx if labels[i] == "Normal"])
        normal_test = np.array([i for i in test_idx if labels[i] == "Normal"])
        if len(normal_train) < 5 or len(normal_test) < 5:
            continue
        rng = np.random.default_rng(fold)
        rng.shuffle(normal_train)
        cal_n = normal_train[: int(0.7 * len(normal_train))]
        thr = {c: float(np.percentile(S[c][cal_n], 98)) for c in CHANNELS}

        # apprendre le centroïde par famille sur train
        fusion = AdaptiveFamilyFusion()
        topo_tr = np.array([[S[k][i] for k in TOPO_KEYS] for i in train_idx])
        fam_tr = np.array([labels[i] for i in train_idx])
        fusion.fit(topo_tr, fam_tr)
        # table de routage sur train
        rec_tr = {}
        for fam in families:
            fi = np.array([i for i in train_idx if labels[i] == fam])
            if len(fi) >= 3:
                rec_tr[fam] = {c: float(np.mean(S[c][fi] >= thr[c])) for c in CHANNELS}
        fusion.learn_channel_map(rec_tr)

        # évaluer sur test
        recalls = []
        for fam in families:
            fi = np.array([i for i in test_idx if labels[i] == fam])
            if len(fi) < 3:
                continue
            hit = sum(
                fusion.route([S[k][i] for k in TOPO_KEYS], {c: S[c][i] for c in CHANNELS})["score"]
                >= thr[fusion.route([S[k][i] for k in TOPO_KEYS], {c: S[c][i] for c in CHANNELS})["channel"]]
                for i in fi
            )
            recalls.append(hit / len(fi))
        if recalls:
            fold_results.append(float(np.mean(recalls)))
        print(f"fold {fold + 1}: rappel moyen={fold_results[-1]:.3f}" if recalls else f"fold {fold + 1}: sauté")

    mean_r, std_r = float(np.mean(fold_results)), float(np.std(fold_results))
    print(f"\nRappel fusion adaptative (CV temporelle {len(fold_results)} folds) : "
          f"{mean_r:.3f} ± {std_r:.3f}")

    out = {
        "n_folds": len(fold_results),
        "mean_recall": round(mean_r, 3),
        "std_recall": round(std_r, 3),
        "per_fold": [round(r, 3) for r in fold_results],
        "runtime_s": round(time.time() - t0, 1),
    }
    p = ROOT / "artifacts" / "temporal_cv.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"-> {p} ({out['runtime_s']}s)")


if __name__ == "__main__":
    main()
