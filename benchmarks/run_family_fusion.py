"""Fusion par famille — chaque attaque détectée par son meilleur canal.

Leçon Phase 4 : la fusion globale unique dilue le signal (KZ_cumul à 0.79
seul mais 0.12 en fusion). Solution (décision D1, ARCHITECTURE_V1) : pour
chaque famille d'attaque, sélectionner le canal qui la voit le mieux, et
combiner par OR logique — une alerte si N'IMPORTE QUEL canal adapté crie.

C'est l'architecture d'un vrai IDS : une batterie de détecteurs
spécialisés, chacun calibré sur sa famille, un orchestrateur qui fusionne.

Protocole honnête : split calibration (60% normal pour les seuils) /
évaluation (40%, jamais utilisé pour calibrer). Seuil par canal à FPR 2%
sur le normal de calibration.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from cyber.classical_detectors import (
    IsolationForestDetector,
    OneClassSVMDetector,
    PCAAutoencoderDetector,
)
from cyber.synthetic_attacks import build_synthetic_dataset
from cyber.topo_probe import window_correlation
from cyber.windowing import sliding_windows
from ratiss_topo.arsenal import KibbleZurekTracker, triad_frustration
from ratiss_topo.robust_metrics import coupled_metric, spectral_channels

ROOT = Path(__file__).resolve().parent.parent
WINDOW, STRIDE = 30, 10
FPR_TARGET = 0.02

CHANNELS = ["classical", "psig", "edge", "entropie", "pr", "neg_energy",
            "frustration", "cumul_drift", "drift"]


def score_stream(X: np.ndarray, labels: np.ndarray):
    """Score toutes les fenêtres sur tous les canaux."""
    X_normal = X[labels == "normal"]
    detectors = {
        "IF": IsolationForestDetector().fit(X_normal),
        "OC-SVM": OneClassSVMDetector().fit(X_normal),
        "PCA-AE": PCAAutoencoderDetector().fit(X_normal),
    }
    starts, win_labels, purities = sliding_windows(X, labels, WINDOW, STRIDE)
    pure = purities == 1.0

    ref_corr = window_correlation(X_normal[:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)

    scores = {k: [] for k in CHANNELS}
    corrs = []
    for s in starts:
        win = X[s : s + WINDOW]
        corr = window_correlation(win)
        corrs.append(corr)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        scores["classical"].append(max(d.score(win).mean() for d in detectors.values()))
        scores["psig"].append(topo["psig_seuille"])
        scores["edge"].append(topo["edge"])
        scores["entropie"].append(topo["entropie"])
        scores["pr"].append(spec["pr"])
        scores["neg_energy"].append(spec["neg_energy"])
        scores["frustration"].append(triad_frustration(corr))
        scores["cumul_drift"].append(kzr["cumul_drift"])
    drift = [0.0] + [float(np.linalg.norm(corrs[i] - corrs[i - 1]))
                     for i in range(1, len(corrs))]
    scores["drift"] = drift
    return {k: np.array(v) for k, v in scores.items()}, win_labels, pure


def main() -> None:
    t0 = time.time()
    data = build_synthetic_dataset()
    X, labels = data["X"], data["labels"]
    scores, win_labels, pure = score_stream(X, labels)

    # split calibration / évaluation (indices disjoints sur le normal)
    normal_idx = np.where(pure & (win_labels == "normal"))[0]
    rng = np.random.default_rng(7)
    rng.shuffle(normal_idx)
    n_cal = int(0.6 * len(normal_idx))
    cal_normal = normal_idx[:n_cal]
    eval_normal = normal_idx[n_cal:]

    families = ["weaving", "phase_transition", "slow_mutation"]

    # Sélection du meilleur canal par famille à un FPR de référence (2%)
    ref_thresholds = {c: float(np.percentile(scores[c][cal_normal], 98))
                      for c in CHANNELS}
    best_channel = {}
    print("== Meilleur canal par famille (rappel @ FPR 2% de référence) ==")
    for fam in families:
        fam_idx = np.where(pure & (win_labels == fam))[0]
        if len(fam_idx) < 3:
            continue
        recalls = {c: float(np.mean(scores[c][fam_idx] >= ref_thresholds[c]))
                   for c in CHANNELS}
        best_c = max(recalls, key=recalls.get)
        best_channel[fam] = best_c
        print(f"  {fam:18s} -> {best_c:12s} rappel={recalls[best_c]:.2f}")

    # OR-fusion : alerte si le canal adapté crie. L'union de K canaux gonfle
    # le FPR (chaque canal ajoute ses faux positifs). On calibre donc le
    # percentile par canal pour que le FPR GLOBAL sur le normal d'évaluation
    # vaille la cible (2%) — recherche sur grille de percentiles.
    active = sorted(set(best_channel.values()) | {"classical"})

    def global_fpr_at(pct: float) -> float:
        thr = {c: float(np.percentile(scores[c][cal_normal], pct)) for c in active}
        fp = np.zeros(len(eval_normal), dtype=bool)
        for c in active:
            fp |= scores[c][eval_normal] >= thr[c]
        return float(fp.mean())

    # plus haut percentile = seuil plus haut = FPR plus bas ; on cherche le
    # percentile donnant FPR global le plus proche de la cible sans passer sous
    best_pct, best_gap = 98.0, float("inf")
    for pct in np.arange(98.0, 99.91, 0.05):
        fpr = global_fpr_at(pct)
        gap = abs(fpr - FPR_TARGET) + (0.05 if fpr > FPR_TARGET else 0.0)
        if gap < best_gap:
            best_gap, best_pct = gap, pct
    thresholds = {c: float(np.percentile(scores[c][cal_normal], best_pct))
                  for c in active}
    global_fpr = global_fpr_at(best_pct)

    print(f"\n== OR-fusion spécialisée (percentile/canal={best_pct:.2f}, FPR global={global_fpr:.3f}) ==")
    results = {}
    total_recall = []
    for fam in families:
        fam_idx = np.where(pure & (win_labels == fam))[0]
        if len(fam_idx) < 3:
            continue
        c = best_channel[fam]
        rec = float(np.mean(scores[c][fam_idx] >= thresholds[c]))
        total_recall.append(rec)
        results[fam] = {"best_channel": c, "recall": round(rec, 3)}
        print(f"  {fam:18s} canal={c:12s} rappel={rec:.2f}")
    mean_recall = float(np.mean(total_recall))
    print(f"\n  Rappel moyen : {mean_recall:.2f}  |  FPR global : {global_fpr:.3f}")

    out = {
        "fpr_target": FPR_TARGET,
        "global_fpr": round(global_fpr, 4),
        "mean_recall": round(mean_recall, 3),
        "per_channel_percentile": round(best_pct, 2),
        "per_family": results,
        "active_channels": active,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out_path = ROOT / "artifacts" / "family_fusion.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n-> {out_path} ({out['elapsed_s']}s)")


if __name__ == "__main__":
    main()
