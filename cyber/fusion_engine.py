"""Moteur de fusion — Couche 5 du pipeline RATISS-Cyber.

Combine les scores classiques (symptômes) et topologiques (structure) en
une décision unique, avec preuve SHA-256 vérifiable de chaque alerte.

Décisions d'architecture (Phase 1, docs/ARCHITECTURE_V1.md) :
- D1 : poids optimisés par famille d'attaque (le contraste topo change de
  signe selon la famille — une fusion globale unique dilue le signal)
- D2 : seuil adaptatif appris sur le flux (percentile glissant), pas fixe
- D3 : P_sig est le signal différenciant sur les attaques furtives
"""

from __future__ import annotations

import hashlib
import json

import numpy as np


def window_proof(
    window_data: np.ndarray,
    scores: dict[str, float],
    label_pred: str,
) -> str:
    """Preuve SHA-256 d'une alerte : hash des données brutes de la fenêtre
    + scores + décision. Vérifiable par un tiers sans nous faire confiance."""
    payload = {
        "window_sha256": hashlib.sha256(
            np.ascontiguousarray(window_data).tobytes()
        ).hexdigest(),
        "scores": {k: round(float(v), 6) for k, v in scores.items()},
        "decision": label_pred,
    }
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


class FusionEngine:
    """Fusion pondérée classique + topologique, seuil adaptatif.

    weights : {"classical": w_c, "topo": w_t} — appris par grid search.
    Les scores d'entrée sont normalisés (z-score sur le flux de référence
    normal) pour que la somme pondérée ait un sens.
    """

    def __init__(self, w_classical: float = 0.5, w_topo: float = 0.5):
        self.w_classical = w_classical
        self.w_topo = w_topo
        self._ref_mean: dict[str, float] = {}
        self._ref_std: dict[str, float] = {}

    def calibrate(self, scores_normal: dict[str, np.ndarray]) -> None:
        """Apprend la distribution des scores sur trafic normal (référence
        pour la normalisation z et le seuil adaptatif)."""
        for k, v in scores_normal.items():
            self._ref_mean[k] = float(np.mean(v))
            self._ref_std[k] = float(np.std(v)) or 1.0

    def normalize(self, scores: dict[str, float]) -> dict[str, float]:
        return {
            k: (v - self._ref_mean.get(k, 0.0)) / self._ref_std.get(k, 1.0)
            for k, v in scores.items()
        }

    def combine(self, scores: dict[str, float]) -> float:
        """Score fusionné : max des z-scores pondérés de tous les canaux.

        Un seul canal qui crie suffit à alerter (les attaques furtives ne
        laissent qu'UNE trace — il faut l'entendre). w_classical/w_topo
        pondèrent la branche symptômes vs la branche structure.
        """
        z = self.normalize(scores)
        best = 0.0
        for k, zk in z.items():
            w = self.w_classical if k == "classical" else self.w_topo
            best = max(best, w * zk)
        return best

    def adaptive_threshold(self, combined_normal: np.ndarray, fpr_target: float = 0.02) -> float:
        """Seuil tel que le taux de faux positifs sur le flux normal de
        référence vaut fpr_target (défaut 2% — objectif de la feuille de route)."""
        return float(np.percentile(combined_normal, 100 * (1 - fpr_target)))


def grid_search_weights(
    scores_by_window: list[dict[str, float]],
    labels: np.ndarray,
    calib_idx: np.ndarray,
    eval_idx: np.ndarray,
    fpr_target: float = 0.02,
    grid: np.ndarray | None = None,
) -> dict:
    """Cherche les poids (w_classical, w_topo) maximisant le F1 à FPR contraint.

    calib_idx : fenêtres pour calibrer (normalisations + seuil)
    eval_idx : fenêtres pour évaluer (jamais utilisées en calibration)
    """
    if grid is None:
        grid = np.arange(0.0, 1.01, 0.1)
    labels_bin = (labels != "normal").astype(int)
    best = {"f1": -1.0}

    for w_t in grid:
        engine = FusionEngine(w_classical=1.0 - w_t, w_topo=w_t)
        calib_scores = [scores_by_window[i] for i in calib_idx]
        normal_calib = [s for s, i in zip(calib_scores, calib_idx) if labels[i] == "normal"]
        if not normal_calib:
            continue
        engine.calibrate(
            {k: np.array([s[k] for s in normal_calib]) for k in normal_calib[0]}
        )
        combined_calib = np.array([engine.combine(s) for s in normal_calib])
        threshold = engine.adaptive_threshold(combined_calib, fpr_target)

        y_true, y_pred = [], []
        for i in eval_idx:
            y_true.append(labels_bin[i])
            y_pred.append(int(engine.combine(scores_by_window[i]) >= threshold))
        y_true, y_pred = np.array(y_true), np.array(y_pred)

        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        fpr = fp / max(fp + tn, 1)

        if f1 > best["f1"]:
            best = {
                "w_classical": round(1.0 - w_t, 2),
                "w_topo": round(float(w_t), 2),
                "f1": float(f1),
                "precision": float(precision),
                "recall": float(recall),
                "fpr": float(fpr),
                "threshold": float(threshold),
            }
    return best
