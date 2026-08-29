"""Sonde topologique — test préliminaire du contraste P_sig normal/attaque.

Hypothèse transdisciplinaire : une fenêtre de trafic réseau a une structure
de corrélation entre features, comme un cristal a une structure de corrélation
entre sites. Une attaque = une transition de phase du graphe de corrélation.

Protocole :
- fenêtres de `window` connexions consécutives (par catégorie)
- features numériques de base (stabilité topologique, pas de one-hot sparse)
- matrice de corrélation de la fenêtre -> métrique couplée RATISS
- contraste : distribution des scores normal vs chaque type d'attaque
"""

from __future__ import annotations

import numpy as np

from ratiss_topo.robust_metrics import coupled_metric

# features numériques continues — les taux et compteurs portent la structure
PROBE_FEATURES = [
    "duration", "src_bytes", "dst_bytes", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_serror_rate", "dst_host_rerror_rate",
]


def window_correlation(X: np.ndarray) -> np.ndarray:
    """Corrélation d'une fenêtre, régularisée (fenêtres courtes = matrices
    mal conditionnées ; un léger shrinkage stabilise sans casser la structure)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.corrcoef(X.T)
    c = np.nan_to_num(c, nan=0.0)
    return 0.95 * c + 0.05 * np.eye(c.shape[0])


def topo_scores_by_category(
    X: np.ndarray,
    categories: np.ndarray,
    window: int = 30,
    n_windows: int = 40,
    seed: int = 42,
) -> dict[str, list[dict]]:
    """Score topologique de fenêtres tirées dans chaque catégorie de trafic."""
    rng = np.random.default_rng(seed)
    out: dict[str, list[dict]] = {}
    for cat in sorted(set(categories)):
        pool = X[categories == cat]
        if len(pool) < window:
            continue
        scores = []
        for _ in range(n_windows):
            start = int(rng.integers(0, len(pool) - window))
            corr = window_correlation(pool[start : start + window])
            scores.append(coupled_metric(corr))
        out[cat] = scores
    return out


def summarize(scores_by_cat: dict[str, list[dict]]) -> dict:
    """Moyenne/écart-type par catégorie + contraste vs normal."""
    summary = {}
    for cat, scores in scores_by_cat.items():
        arr = {k: [s[k] for s in scores] for k in scores[0]}
        summary[cat] = {
            k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
            for k, v in arr.items()
        }
    if "normal" in summary:
        ref = summary["normal"]["score"]["mean"]
        for cat in summary:
            summary[cat]["contrast_vs_normal"] = (
                summary[cat]["score"]["mean"] - ref
            )
    return summary
