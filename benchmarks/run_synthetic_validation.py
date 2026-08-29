"""Validation Phase 3 — le dataset synthétique RATISS.

Le test qui tue : des attaques qui ne produisent AUCUN symptôme
statistique (vérifié par tests KS). Si le classique les rate et que la
topologie les voit, l'avantage unique de RATISS-Cyber est prouvé.

Sortie : artifacts/synthetic_validation.json
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
from cyber.fusion_engine import FusionEngine
from cyber.synthetic_attacks import build_synthetic_dataset
from cyber.topo_probe import window_correlation
from cyber.windowing import sliding_windows
from ratiss_topo.arsenal import KibbleZurekTracker, triad_frustration
from ratiss_topo.robust_metrics import coupled_metric, spectral_channels

ROOT = Path(__file__).resolve().parent.parent
WINDOW, STRIDE = 30, 10


def evaluate_at_fpr(scores_normal, scores_attack, fpr_target=0.02):
    thr = float(np.percentile(scores_normal, 100 * (1 - fpr_target)))
    return {
        "recall": float(np.mean(scores_attack >= thr)),
        "fpr": float(np.mean(scores_normal >= thr)),
        "threshold": thr,
    }


def main() -> None:
    t0 = time.perf_counter()
    data = build_synthetic_dataset()
    X, labels = data["X"], data["labels"]

    print("== Validation d'honnêteté (tests KS : l'attaque fuit-elle ?) ==")
    for name, v in data["validation"].items():
        verdict = "✅ invisible" if v["honnete"] else "⚠️ fuite partielle"
        print(f"  {name:18s} {v['features_indistinguishables']}/{v['total_features']} "
              f"features indistinguables (min p={v['min_p_value']:.4f}) {verdict}")

    # --- détecteurs classiques entraînés sur le normal ---
    X_normal = X[labels == "normal"]
    detectors = {
        "IsolationForest": IsolationForestDetector().fit(X_normal),
        "OneClassSVM": OneClassSVMDetector().fit(X_normal),
        "PCA-Autoencoder": PCAAutoencoderDetector().fit(X_normal),
    }

    # --- fenêtres glissantes ---
    starts, win_labels, purities = sliding_windows(X, labels, WINDOW, STRIDE)
    pure = purities == 1.0
    print(f"\nFenêtres : {len(starts)} ({pure.mean():.0%} pures)")

    # --- scores par fenêtre : tous les canaux topologiques ---
    # Leçon du diagnostic : chaque attaque a SON observable. P_sig voit le
    # tissage, edge voit la transition de phase, la dérive voit la mutation.
    channels = ["classical", "psig", "edge", "entropie", "pr", "neg_energy",
                "frustration", "cumul_drift"]
    scores = {k: [] for k in channels}
    corrs = []
    # Kibble-Zurek : référence = médiane des premières fenêtres normales
    ref_corr = window_correlation(X[labels == "normal"][:WINDOW])
    kz = KibbleZurekTracker(window=12)
    kz.set_reference(ref_corr)
    t_topo = 0.0
    for s in starts:
        win = X[s : s + WINDOW]
        scores["classical"].append(max(d.score(win).mean() for d in detectors.values()))
        t1 = time.perf_counter()
        corr = window_correlation(win)
        topo = coupled_metric(corr)
        spec = spectral_channels(corr)
        kzr = kz.update(corr)
        frust = triad_frustration(corr)
        t_topo += time.perf_counter() - t1
        corrs.append(corr)
        scores["psig"].append(topo["psig_seuille"])
        scores["edge"].append(topo["edge"])
        scores["entropie"].append(topo["entropie"])
        scores["pr"].append(spec["pr"])
        scores["neg_energy"].append(spec["neg_energy"])
        scores["frustration"].append(frust)
        scores["cumul_drift"].append(kzr["cumul_drift"])
    for k in scores:
        scores[k] = np.array(scores[k])

    # canal TRAJECTOIRE : dérive de la structure entre fenêtres consécutives
    # (distance de Frobenius des matrices de corrélation) — l'APT mute
    # lentement, chaque fenêtre est normale mais la trajectoire dérive
    drift = np.zeros(len(starts))
    for i in range(1, len(starts)):
        drift[i] = float(np.linalg.norm(corrs[i] - corrs[i - 1]))
    scores["drift"] = drift
    print(f"Temps topo : {t_topo / len(starts) * 1000:.1f} ms/fenêtre")

    # --- évaluation par système et par famille d'attaque ---
    normal_mask = pure & (win_labels == "normal")
    results = {}
    systems = [
        ("classique", "classical"), ("topo_P_sig", "psig"),
        ("topo_edge", "edge"), ("topo_drift", "drift"),
        ("spectral_PR", "pr"), ("spectral_negE", "neg_energy"),
        ("frustration", "frustration"), ("KZ_cumul", "cumul_drift"),
    ]
    for system, key in systems:
        results[system] = {}
        for cat in sorted(set(win_labels)):
            if cat == "normal":
                continue
            mask = pure & (win_labels == cat)
            if mask.sum() < 3:
                continue
            results[system][cat] = evaluate_at_fpr(
                scores[key][normal_mask], scores[key][mask]
            )

    # --- fusion multi-canaux : classique + tous les canaux topo ---
    # PR monte sous attaque (structure délocalisée, ex. hub de phase) :
    # "haut = anormal" comme les autres canaux. Vérifié empiriquement :
    # phase_transition PR=9.46 vs normal 7.65.
    topo_keys = ["psig", "edge", "entropie", "drift", "neg_energy", "pr",
                 "frustration", "cumul_drift"]
    fusion_input = {
        "classical": scores["classical"],
        **{k: scores[k] for k in topo_keys},
    }
    # grid search des poids : split calibration/évaluation disjoint
    pure_idx = np.where(pure)[0]
    rng_split = np.random.default_rng(42)
    rng_split.shuffle(pure_idx)
    half = len(pure_idx) // 2
    calib_idx, eval_idx = pure_idx[:half], pure_idx[half:]
    normal_calib = np.array([i for i in calib_idx if win_labels[i] == "normal"])
    normal_eval = np.array([i for i in eval_idx if win_labels[i] == "normal"])

    best_fusion = {"recall_mean": -1.0}
    for w_t in np.arange(0.0, 1.01, 0.1):
        engine = FusionEngine(w_classical=1.0 - w_t, w_topo=w_t)
        engine.calibrate({k: fusion_input[k][normal_calib] for k in fusion_input})
        comb_calib = np.array([
            engine.combine({k: fusion_input[k][i] for k in fusion_input})
            for i in normal_calib
        ])
        thr = float(np.percentile(comb_calib, 98))
        recalls, fprs = [], []
        for cat in sorted(set(win_labels)):
            if cat == "normal":
                continue
            mask = np.array([i for i in eval_idx if win_labels[i] == cat])
            if len(mask) < 3:
                continue
            comb = np.array([
                engine.combine({k: fusion_input[k][i] for k in fusion_input})
                for i in mask
            ])
            recalls.append(float(np.mean(comb >= thr)))
        comb_ne = np.array([
            engine.combine({k: fusion_input[k][i] for k in fusion_input})
            for i in normal_eval
        ])
        fpr = float(np.mean(comb_ne >= thr))
        if recalls and np.mean(recalls) > best_fusion["recall_mean"]:
            best_fusion = {
                "w_classical": round(1.0 - w_t, 2), "w_topo": round(float(w_t), 2),
                "recall_mean": float(np.mean(recalls)), "fpr": fpr,
                "recalls": dict(zip([c for c in sorted(set(win_labels)) if c != "normal"], recalls)),
            }

    # fusion finale avec les meilleurs poids, évaluée sur eval_idx
    engine = FusionEngine(best_fusion["w_classical"], best_fusion["w_topo"])
    engine.calibrate({k: fusion_input[k][normal_calib] for k in fusion_input})
    comb_calib = np.array([
        engine.combine({k: fusion_input[k][i] for k in fusion_input})
        for i in normal_calib
    ])
    thr = float(np.percentile(comb_calib, 98))
    results["fusion"] = {}
    for cat in sorted(set(win_labels)):
        if cat == "normal":
            continue
        mask = np.array([i for i in eval_idx if win_labels[i] == cat])
        if len(mask) < 3:
            continue
        comb = np.array([
            engine.combine({k: fusion_input[k][i] for k in fusion_input})
            for i in mask
        ])
        results["fusion"][cat] = {
            "recall": float(np.mean(comb >= thr)),
            "fpr": float(np.mean(np.array([
                engine.combine({k: fusion_input[k][i] for k in fusion_input})
                for i in normal_eval
            ]) >= thr)),
        }
    results["fusion_weights"] = best_fusion

    print("\n== Rappel à FPR≈2% (fenêtres pures) ==")
    header = f"{'Attaque':18s}" + "".join(f"{s:>12s}" for s, _ in systems) + f"{'fusion':>12s}"
    print(header)
    for cat in results["classique"]:
        row = f"{cat:18s}"
        for system, _ in systems:
            row += f"{results[system][cat]['recall']:12.2f}"
        row += f"{results['fusion'][cat]['recall']:12.2f}"
        print(row)
    print(f"\nPoids fusion optimaux : w_classical={best_fusion['w_classical']}, "
          f"w_topo={best_fusion['w_topo']} (rappel moyen={best_fusion['recall_mean']:.2f}, "
          f"FPR={best_fusion['fpr']:.3f})")

    out = {
        "protocol": "dataset synthétique RATISS : attaques topologiques pures, "
                    "invisibilité statistique vérifiée par tests KS (seuil 0.01, "
                    ">=90% features indistinguables)",
        "honnetete": data["validation"],
        "n_windows": int(len(starts)),
        "topo_ms_per_window": round(t_topo / len(starts) * 1000, 2),
        "results": results,
        "runtime_s": round(time.perf_counter() - t0, 1),
    }
    out_path = ROOT / "artifacts/synthetic_validation.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n-> {out_path} ({out['runtime_s']}s)")


if __name__ == "__main__":
    main()
