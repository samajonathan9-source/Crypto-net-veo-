"""Métriques topologiques robustes — greffe RATISS pour la cybersécurité.

Adapté de ratiss_photoinduced/robust_metrics.py (Travaux) : les fonctions
physiques SSH sont remplacées par des équivalents génériques de graphe, car
ici la matrice de corrélation vient du trafic réseau, pas d'un cristal KTN:Li.

Le point de greffe transdisciplinaire : psig_from_correlation() accepte
n'importe quelle matrice de corrélation. Cristal ou réseau, la persistance
homologique voit la structure.
"""

from __future__ import annotations

import numpy as np

from ratiss_topo.topology import psig_from_correlation


def psig_thresholded(corr: np.ndarray, seuil: float = 0.05) -> float:
    """P_sig après seuillage : met à zéro les corrélations < seuil (bruit)."""
    c = corr.copy()
    c[np.abs(c) < seuil] = 0.0
    return psig_from_correlation(c)


def correlation_entropy(corr: np.ndarray) -> float:
    """Entropie de la distribution des corrélations.

    H bas = corrélation structurée (topologique) ; H haut = désordre.
    """
    c = np.abs(corr.flatten())
    c = c[c > 1e-12]
    if len(c) == 0:
        return 0.0
    p = c / c.sum()
    return float(-np.sum(p * np.log(p)))


def extremal_weight(corr: np.ndarray) -> float:
    """Généralisation de edge_weight : corrélation entre les deux dimensions
    les plus éloignées (bord-bord du nuage de features).

    Dans le SSH c'était |C_{0,N-1}| (bouts de la chaîne). Ici, les "bords"
    sont les features dont les profils de corrélation sont les plus distants.
    """
    profiles = np.abs(corr)
    delta = profiles[:, None, :] - profiles[None, :, :]
    dist = np.linalg.norm(delta, axis=2)
    i, j = np.unravel_index(np.argmax(dist), dist.shape)
    return float(abs(corr[i, j]))


def coupled_metric(corr: np.ndarray, seuil: float = 0.05) -> dict:
    """Vote combiné P_sig seuillé + corrélation extrême + entropie.

    score = P_sig + edge - 0.1 * entropie  (formule RATISS validée sur QPU).
    """
    psig = psig_thresholded(corr, seuil)
    edge = extremal_weight(corr)
    entropy = correlation_entropy(corr)
    return {
        "psig_seuille": psig,
        "edge": edge,
        "entropie": entropy,
        "score": psig + edge - 0.1 * entropy,
    }
