"""Détecteurs classiques — Couche 2 du pipeline RATISS-Cyber.

Quatre familles représentatives de l'état de l'art NIDS :
- IsolationForest : anomalie non supervisée (rapide, scalable)
- OneClassSVM : anomalie non supervisée (haute dimension)
- RandomForest : supervisé (robuste, interprétable)
- PCAAutoencoder : erreur de reconstruction (proxy léger des LSTM-AE)

Interface commune : fit(X_normal_ou_X, y=None) / score(X) -> score d'anomalie
(plus haut = plus anormal), pour la fusion ultérieure avec la couche topo.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.svm import OneClassSVM


class IsolationForestDetector:
    name = "IsolationForest"

    def __init__(self, **kw):
        self.model = IsolationForest(
            n_estimators=200, contamination="auto", random_state=42, n_jobs=-1, **kw
        )

    def fit(self, X: np.ndarray, y: np.ndarray | None = None):
        self.model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(X)  # plus haut = plus anormal


class OneClassSVMDetector:
    name = "OneClassSVM"

    def __init__(self, **kw):
        self.model = OneClassSVM(nu=0.05, kernel="rbf", gamma="scale", **kw)

    def fit(self, X: np.ndarray, y: np.ndarray | None = None):
        self.model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(X)


class RandomForestDetector:
    name = "RandomForest"

    def __init__(self, **kw):
        self.model = RandomForestClassifier(
            n_estimators=200, random_state=42, n_jobs=-1, **kw
        )

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.model.fit(X, y)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]


class PCAAutoencoderDetector:
    """Erreur de reconstruction PCA — même famille que les autoencodeurs :

    un modèle apprend la variété normale ; ce qui se reconstruit mal est
    anormal. Proxy CPU-léger du LSTM-AE pour le benchmark de Phase 1.
    """

    name = "PCA-Autoencoder"

    def __init__(self, n_components: float = 0.95):
        self.n_components = n_components
        self.model = PCA(n_components=n_components, random_state=42)

    def fit(self, X: np.ndarray, y: np.ndarray | None = None):
        self.model.fit(X)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        z = self.model.transform(X)
        x_hat = self.model.inverse_transform(z)
        return np.mean((X - x_hat) ** 2, axis=1)


ALL_DETECTORS = [
    IsolationForestDetector,
    OneClassSVMDetector,
    RandomForestDetector,
    PCAAutoencoderDetector,
]
