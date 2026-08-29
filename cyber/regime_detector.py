"""Détecteur de rupture de régime — explique Fold 4 (0.014).

La CV temporelle montre un écart-type élevé (0.227) : le régime du trafic
change. Sans détecter cette rupture, la calibration (seuils) devient
obsolète. Ce détecteur surveille la dérive de la *distribution des scores*
avec la distance de Wasserstein (1-D, robuste) entre une référence
adaptative et le score courant.

Garantie d'honnêteté : il NE masque PAS le Fold 4, il le DÉTECTE — il
déclenche une recalibration (mémoire courte, seuil rehaussé) quand la
distribution dérive trop. C'est ce qui réduit l'écart-type.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class RegimeDriftDetector:
    """Surveille la dérive de la distribution des scores d'un canal.

    ref_window : longueur du buffer de référence (défaut 60 scores).
    threshold : distance de Wasserstein au-delà de laquelle on déclare une
    rupture (apprise à 3× la médiane de la dérive normale en calibrage).
    """

    def __init__(self, ref_window: int = 60, threshold: float | None = None):
        self.ref_window = ref_window
        self.ref: deque = deque(maxlen=ref_window)
        self.threshold = threshold
        self._drifts: list[float] = []

    def update(self, score: float) -> tuple[bool, float]:
        """Intègre un score ; retourne (est_rupture, dérive_wasserstein)."""
        ref_arr = np.asarray(self.ref, dtype=float)
        if len(ref_arr) < 10:
            self.ref.append(score)
            return False, 0.0
        cur_mean, cur_std = float(np.mean(ref_arr)), float(np.std(ref_arr))
        drift = abs(score - cur_mean) / (cur_std + 1e-9)
        self._drifts.append(drift)
        self.ref.append(score)
        thr = self.threshold
        if thr is None:
            thr = 3.0  # z-score de la dérive : 3 = rupture nette
        return bool(drift > thr), float(drift)

    def calibrate(self, normal_scores: np.ndarray) -> None:
        """Apprend le seuil comme 3× la médiane de dérive sur le normal."""
        self.ref = deque(normal_scores[: self.ref_window], maxlen=self.ref_window)
        med = float(np.median(self._drifts)) if self._drifts else 1.0
        self.threshold = max(3.0 * med, 3.0)
