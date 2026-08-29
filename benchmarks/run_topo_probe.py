"""Lance la sonde topologique + l'analyse des lacunes par catégorie.

1. Rappel des détecteurs classiques PAR catégorie d'attaque (où ratent-ils ?)
2. Contraste topologique P_sig normal vs attaques (RATISS voit-il la structure ?)

Sortie : artifacts/topo_probe.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.preprocessing import StandardScaler

from cyber.topo_probe import PROBE_FEATURES, topo_scores_by_category, summarize

ROOT = Path(__file__).resolve().parent.parent


def load_multiclass() -> dict:
    import pandas as pd

    from cyber.datasets import load_nsl_kdd

    data = load_nsl_kdd(
        ROOT / "data/KDDTrain+.txt", ROOT / "data/KDDTest+.txt", binary=False
    )
    return data


def per_category_recall(data: dict) -> dict:
    """Rappel du meilleur classique (RF supervisé) par catégorie d'attaque."""
    from cyber.classical_detectors import RandomForestDetector

    rng = np.random.default_rng(42)
    idx = rng.choice(len(data["X_train"]), 40_000, replace=False)
    X_train, y_train = data["X_train"][idx], data["y_train"][idx]
    idx = rng.choice(len(data["X_test"]), 10_000, replace=False)
    X_test, y_test = data["X_test"][idx], data["y_test"][idx]

    scaler = StandardScaler().fit(X_train)
    y_train_bin = (y_train != "normal").astype(int)
    det = RandomForestDetector().fit(scaler.transform(X_train), y_train_bin)
    scores = det.score(scaler.transform(X_test))
    y_pred = (scores >= 0.5).astype(int)

    out = {}
    for cat in sorted(set(y_test)):
        mask = y_test == cat
        if cat == "normal":
            out[cat] = {"n": int(mask.sum()),
                        "taux_rejet_correct": float((y_pred[mask] == 0).mean())}
        else:
            out[cat] = {"n": int(mask.sum()),
                        "rappel": float(y_pred[mask].mean())}
    return out


def main() -> None:
    data = load_multiclass()

    print("== Rappel par catégorie (RandomForest) ==")
    recalls = per_category_recall(data)
    for cat, m in recalls.items():
        print(f"  {cat:8s} n={m['n']:5d}  {m}")

    print("\n== Sonde topologique ==")
    feat_idx = [data["feature_names"].index(f) for f in PROBE_FEATURES]
    rng = np.random.default_rng(42)
    idx = rng.choice(len(data["X_test"]), 10_000, replace=False)
    X = data["X_test"][idx][:, feat_idx]
    cats = data["y_test"][idx]

    scores = topo_scores_by_category(X, cats, window=30, n_windows=40)
    summary = summarize(scores)
    for cat, m in summary.items():
        print(f"  {cat:8s} score={m['score']['mean']:7.3f} ± {m['score']['std']:.3f}"
              f"  psig={m['psig_seuille']['mean']:.3f}"
              f"  contraste={m.get('contrast_vs_normal', 0):+.3f}")

    out = {
        "protocol": "fenêtres de 30 connexions, 40 fenêtres/catégorie, seed 42, "
                    "16 features numériques, métrique couplée RATISS",
        "per_category_recall_rf": recalls,
        "topo_summary": summary,
    }
    out_path = ROOT / "artifacts/topo_probe.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n-> {out_path}")


if __name__ == "__main__":
    main()
