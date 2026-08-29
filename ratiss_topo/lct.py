"""LCT — Learning-Coupled Topology : adaptation continue de la référence.

Le Kibble-Zurek de Phase 4 fige la référence normale au départ. Mais un APT
lent fait *dériver la référence elle-même* : si le normal évolue (heure du
jour, charge), la référence figée devient obsolete et le cumul monte pour
tout le monde. La LCT apprend la dynamique de la référence :

1. **Référence adaptative** : la référence normale est une moyenne mobile
   exponentielle des structures observées — elle suit le normal qui évolue,
   sans le figer.

2. **Cumul directionnel** : ce qui trahit l'APT n'est pas la distance à la
   référence, mais la *direction persistante* de la dérive. Le normal dérive
   de façon aléatoire (la direction s'annule) ; l'APT dérive de façon
   directionnelle (la direction s'accumule). On mesure la cohérence de la
   dérive : ||somme des deltas|| / somme des ||deltas|| — 0 si aléatoire,
   ~1 si directionnel.

Leçon transdisciplinaire : c'est l'hystérésis adaptative — le système apprend
le chemin normal ET détecte quand la trajectoire s'en écarte de façon
persistante. Le normal a une mémoire courte, l'APT une mémoire longue.
"""

from __future__ import annotations

import numpy as np


class LCTTracker:
    """Learning-Coupled Topology : référence adaptative + cohérence de dérive.

    alpha : vitesse d'adaptation de la référence (0 = figée, 1 = instantanée).
    Une valeur modérée (0.1-0.3) laisse la référence suivre le normal lent
    tout en détectant la dérive directionnelle de l'APT.
    """

    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
        self._ref: np.ndarray | None = None
        self._deltas: list[np.ndarray] = []

    def set_reference(self, corr: np.ndarray) -> None:
        self._ref = corr.copy()
        self._deltas = []

    def update(self, corr: np.ndarray) -> dict:
        if self._ref is None:
            self.set_reference(corr)
            return {"cumul_drift": 0.0, "coherence": 0.0, "distance": 0.0}
        delta = corr - self._ref
        dist = float(np.linalg.norm(delta))
        self._deltas.append(delta)
        if len(self._deltas) > 20:
            self._deltas.pop(0)
        # cohérence de la dérive : ||Σ deltas|| / Σ ||deltas||
        sums = np.array([np.linalg.norm(d) for d in self._deltas])
        tot = float(sums.sum())
        coh = float(np.linalg.norm(np.sum(self._deltas, axis=0)) / tot) if tot > 1e-9 else 0.0
        # adaptation : la référence suit partiellement la nouvelle structure
        self._ref = (1 - self.alpha) * self._ref + self.alpha * corr
        return {"cumul_drift": dist, "coherence": coh, "distance": dist}
