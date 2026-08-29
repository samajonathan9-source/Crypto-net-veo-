"""Pipeline Phase 2 — fenêtres temporelles réelles + fusion + preuves.

1. Flux ordonné : trafic normal entrecoupé d'épisodes d'attaque (windowing.py)
2. Fenêtres glissantes (N=30, stride=10)
3. Par fenêtre : scores classiques (IF, OC-SVM, PCA-AE) + score topo RATISS
4. Test statistique : bootstrap du contraste P_sig (R2L vs normal)
5. Grid search des poids de fusion à FPR contraint (2%)
6. Comparaison honnête : classique seul vs topo seule vs fusion
7. Preuves SHA-256 des alertes

Sortie : artifacts/phase2_pipeline.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from sklearn.preprocessing import StandardScaler

from cyber.classical_detectors import (
    IsolationForestDetector,
    OneClassSVMDetector,
    PCAAutoencoderDetector,
)
from cyber.datasets import load_nsl_kdd
from cyber.fusion_engine import FusionEngine, grid_search_weights, window_proof
from cyber.topo_probe import PROBE_FEATURES, window_correlation
from cyber.windowing import ordered_stream, sliding_windows
from ratiss_topo.robust_metrics import coupled_metric

ROOT = Path(__file__).resolve().parent.parent
WINDOW, STRIDE = 30, 10


def bootstrap_contrast(
    scores_a: np.ndarray, scores_b: np.ndarray, n_boot: int = 2000, seed: int = 42
) -> dict:
    """Test bootstrap : le contraste moyen(a) - moyen(b) est-il > 0 ?

    Retourne le contraste observé, l'IC 95% et la p-value (fraction des
    rééchantillonnages où le contraste <= 0).
    """
    rng = np.random.default_rng(seed)
    observed = float(np.mean(scores_a) - np.mean(scores_b))
    boots = np.empty(n_boot)
    for i in range(n_boot):
        a = rng.choice(scores_a, len(scores_a), replace=True)
        b = rng.choice(scores_b, len(scores_b), replace=True)
        boots[i] = np.mean(a) - np.mean(b)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p_value = float(np.mean(boots <= 0))
    return {
        "contrast": observed,
        "ci95": [float(lo), float(hi)],
        "p_value": p_value,
        "significant": bool(p_value < 0.05),
    }


def main() -> None:
    t_start = time.perf_counter()
    data = load_nsl_kdd(
        ROOT / "data/KDDTrain+.txt", ROOT / "data/KDDTest+.txt", binary=False
    )
    feat_idx = [data["feature_names"].index(f) for f in PROBE_FEATURES]

    # --- flux ordonné (test uniquement : jamais vu à l'entraînement) ---
    rng = np.random.default_rng(42)
    idx = rng.choice(len(data["X_test"]), 15_000, replace=False)
    X_raw = data["X_test"][idx][:, feat_idx]
    cats_raw = data["y_test"][idx]
    X_stream, cats_stream = ordered_stream(X_raw, cats_raw, seed=42)
    print(f"Flux : {len(X_stream)} connexions "
          f"({dict(zip(*np.unique(cats_stream, return_counts=True)))})")

    # --- scaler + détecteurs classiques (entraînés sur trafic normal train) ---
    idx = rng.choice(len(data["X_train"]), 40_000, replace=False)
    X_train = data["X_train"][idx][:, feat_idx]
    y_train = data["y_train"][idx]
    scaler = StandardScaler().fit(X_train)
    X_normal_train = scaler.transform(X_train[y_train == "normal"])

    detectors = [
        IsolationForestDetector().fit(X_normal_train),
        OneClassSVMDetector().fit(X_normal_train),
        PCAAutoencoderDetector().fit(X_normal_train),
    ]

    # --- fenêtres glissantes + scores ---
    starts, labels, purities = sliding_windows(X_stream, cats_stream, WINDOW, STRIDE)
    print(f"Fenêtres : {len(starts)} (pur = {(purities == 1.0).mean():.0%})")

    X_stream_s = scaler.transform(X_stream)
    per_window_scores: list[dict[str, float]] = []
    t_topo_total = 0.0
    for s in starts:
        win = X_stream_s[s : s + WINDOW]
        scores_c = [d.score(win).mean() for d in detectors]
        t0 = time.perf_counter()
        topo = coupled_metric(window_correlation(win))
        t_topo_total += time.perf_counter() - t0
        per_window_scores.append({
            "classical": float(max(scores_c)),
            "topo": float(topo["psig_seuille"]),  # P_sig nu : signe stable
            "psig": float(topo["psig_seuille"]),
        })
    print(f"Temps topo : {t_topo_total / len(starts) * 1000:.1f} ms/fenêtre")

    # --- test statistique : contraste P_sig R2L vs normal (fenêtres pures) ---
    pure = purities == 1.0
    psig = np.array([s["psig"] for s in per_window_scores])
    stats = {}
    for cat in sorted(set(labels)):
        mask = pure & (labels == cat)
        if mask.sum() < 5 or cat == "normal":
            continue
        stats[cat] = bootstrap_contrast(
            psig[mask], psig[pure & (labels == "normal")]
        )
        sig = "✅ significatif" if stats[cat]["significant"] else "❌"
        print(f"Contraste P_sig {cat:6s} vs normal : "
              f"{stats[cat]['contrast']:+.4f} IC95={stats[cat]['ci95']} "
              f"p={stats[cat]['p_value']:.4f} {sig}")

    # --- split calibration/évaluation (fenêtres pures, disjointes) ---
    pure_idx = np.where(pure)[0]
    rng.shuffle(pure_idx)
    half = len(pure_idx) // 2
    calib_idx, eval_idx = pure_idx[:half], pure_idx[half:]

    # --- baselines : classique seul, topo seule ---
    def eval_single(key: str) -> dict:
        engine = FusionEngine(w_classical=1.0, w_topo=0.0)
        normal_calib = [per_window_scores[i] for i in calib_idx if labels[i] == "normal"]
        ref = np.array([s[key] for s in normal_calib])
        thr = float(np.percentile(ref, 98))
        y_true = (labels[eval_idx] != "normal").astype(int)
        y_pred = np.array([
            per_window_scores[i][key] >= thr for i in eval_idx
        ]).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        return {
            "f1": float(2 * prec * rec / max(prec + rec, 1e-12)),
            "recall": float(rec), "precision": float(prec),
            "fpr": float(fp / max(fp + tn, 1)),
        }

    baseline_classical = eval_single("classical")
    baseline_topo = eval_single("topo")
    print(f"\nClassique seul : F1={baseline_classical['f1']:.3f} "
          f"rappel={baseline_classical['recall']:.3f} FPR={baseline_classical['fpr']:.3f}")
    print(f"Topo seule     : F1={baseline_topo['f1']:.3f} "
          f"rappel={baseline_topo['recall']:.3f} FPR={baseline_topo['fpr']:.3f}")

    # --- fusion : grid search global ---
    best = grid_search_weights(
        per_window_scores, labels, calib_idx, eval_idx, fpr_target=0.02
    )
    print(f"Fusion         : F1={best['f1']:.3f} rappel={best['recall']:.3f} "
          f"FPR={best['fpr']:.3f} (w_classical={best['w_classical']}, "
          f"w_topo={best['w_topo']})")

    # --- rappel par famille : classique seul vs fusion ---
    engine = FusionEngine(best["w_classical"], best["w_topo"])
    normal_calib = [per_window_scores[i] for i in calib_idx if labels[i] == "normal"]
    engine.calibrate(
        {k: np.array([s[k] for s in normal_calib]) for k in normal_calib[0]}
    )
    combined_calib = np.array([engine.combine(s) for s in normal_calib])
    thr = engine.adaptive_threshold(combined_calib, 0.02)

    ref_c = np.array([s["classical"] for s in normal_calib])
    thr_c = float(np.percentile(ref_c, 98))
    per_family = {}
    for cat in sorted(set(labels)):
        mask = eval_idx[labels[eval_idx] == cat]
        if len(mask) < 3 or cat == "normal":
            continue
        rec_c = float(np.mean([per_window_scores[i]["classical"] >= thr_c for i in mask]))
        rec_f = float(np.mean([engine.combine(per_window_scores[i]) >= thr for i in mask]))
        per_family[cat] = {"n": int(len(mask)), "recall_classical": rec_c,
                           "recall_fusion": rec_f}
        print(f"  {cat:6s} n={len(mask):3d}  rappel classique={rec_c:.2f} "
              f"fusion={rec_f:.2f}")

    # --- preuves SHA-256 des 5 premières alertes fusion ---
    proofs = []
    n_proofs = 0
    for i in eval_idx:
        combined = engine.combine(per_window_scores[i])
        if combined >= thr and n_proofs < 5:
            proofs.append({
                "window_start": int(starts[i]),
                "true_label": str(labels[i]),
                "combined_score": round(combined, 4),
                "proof_sha256": window_proof(
                    X_stream_s[starts[i] : starts[i] + WINDOW],
                    per_window_scores[i], "ALERTE",
                ),
            })
            n_proofs += 1

    out = {
        "protocol": {
            "flux": "15K connexions KDDTest+, épisodes d'attaque insérés (seed 42)",
            "window": WINDOW, "stride": STRIDE,
            "features": PROBE_FEATURES,
            "split": "calibration/évaluation disjoints sur fenêtres pures",
            "fpr_target": 0.02,
        },
        "stream_composition": dict(
            zip(*[a.tolist() for a in np.unique(cats_stream, return_counts=True)])
        ),
        "n_windows": int(len(starts)),
        "topo_ms_per_window": round(t_topo_total / len(starts) * 1000, 2),
        "bootstrap_psig_vs_normal": stats,
        "baseline_classical": baseline_classical,
        "baseline_topo": baseline_topo,
        "fusion_best": best,
        "per_family_recall": per_family,
        "alert_proofs": proofs,
        "runtime_s": round(time.perf_counter() - t_start, 1),
    }
    out_path = ROOT / "artifacts/phase2_pipeline.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n-> {out_path} ({out['runtime_s']}s)")


if __name__ == "__main__":
    main()
