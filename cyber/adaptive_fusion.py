"""Fusion adaptative par famille — le routeur qui choisit le bon observable.

La leçon centrale du projet : chaque famille d'attaque a son observable
topologique (Generic→KZ_cumul, weaving→KZ, phase_transition→PR...). La fusion
statique dilue ce signal. La fusion adaptative, elle, apprend à router :

1. EXTRAIRE les features topologiques d'une fenêtre (6 observables).
2. CLASSIFIER la famille la plus probable (petit RandomForest interprétable).
3. ROUTER vers le canal qui voit le mieux cette famille.

L'architecture est EXPLICITE (pas une boîte noire) : le routage est une
table lisible, apprise sur les meilleurs canaux par famille. C'est un IDS
qui sait quand utiliser quelle compétence — la généralité réelle.

Protocole honnête : le routeur est entraîné sur un split de calibration,
évalué sur un split disjoint.
"""

from __future__ import annotations

import numpy as np


class AdaptiveFamilyFusion:
    """Route la fenêtre vers le canal optimal selon sa famille prédite.

    topo_features : les N observables extraits par fenêtre (ex. psig, pr,
    edge, entropie, frustration, cumul_drift).
    channel_map : table famille préférée -> canal (apprise ou fournie).
    """

    def __init__(self, channel_map: dict[str, str] | None = None):
        # routage explicite et interprétable (mis à jour après calibration)
        self.channel_map = channel_map or {
            "Generic": "cumul_drift",
            "Normal": "classical",
        }
        self._centroids: dict[str, np.ndarray] = {}
        self._families: list[str] = []

    def fit(self, topo_features: np.ndarray, family_labels: np.ndarray) -> None:
        """Apprend le centroïde topologique de chaque famille.

        Un classifieur à centroïdes (nearest-centroid) est choisi pour
        l'interprétabilité : on route vers la famille dont la signature
        topologique moyenne est la plus proche. Pas de boîte noire."""
        self._families = sorted(set(family_labels))
        for fam in self._families:
            mask = family_labels == fam
            self._centroids[fam] = topo_features[mask].mean(axis=0)

    def _standardize(self, topo_features: np.ndarray) -> np.ndarray:
        feats = np.asarray(topo_features, dtype=float)
        return feats

    def predict_family(self, topo_features: np.ndarray) -> str:
        """Famille prédite = centroïde topologique le plus proche."""
        if not self._centroids:
            return "Normal"
        f = self._standardize(topo_features)
        dists = {fam: float(np.linalg.norm(f - c)) for fam, c in self._centroids.items()}
        return min(dists, key=dists.get)

    def route(self, topo_features: np.ndarray, scores: dict[str, float]) -> dict:
        """Route une fenêtre : prédit la famille, retourne le canal à croire
        et le score fusionné (le score du canal routé)."""
        family = self.predict_family(topo_features)
        channel = self.channel_map.get(family, "classical")
        return {
            "family": family,
            "channel": channel,
            "score": float(scores.get(channel, 0.0)),
        }

    def learn_channel_map(self, recalls: dict[str, dict[str, float]]) -> None:
        """Apprend la table de routage à partir des rappels mesurés par
        famille et par canal (le meilleur canal devient la route)."""
        for fam, per_channel in recalls.items():
            if per_channel:
                self.channel_map[fam] = max(per_channel, key=per_channel.get)
