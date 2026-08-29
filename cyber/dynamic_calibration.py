"""Calibration dynamique du seuil — les seuils suivent la distribution.

Problème : un seuil percentile fixe sur tout le passé devient obsolète si la
distribution des scores dérive (Fold 4). Solution : recalibrer le
percentile sur une fenêtre glissante des scores récents, de sorte que le
FPR est maintenu même quand le régime change.

Garantie : on ne recalibre QUE sur les scores observés (pas de fuite de
label) ; le seuil suit la distribution sans jamais la dépasser.
"""

from __future__ import annotations

from collections import deque

import numpy as np


class OnlineFPSCalibrator:
    """Ajuste le seuil d'un canal pour un FPR cible sur fenêtre glissante.

    target_fpr : FPR visé (défaut 0.02). window : taille du buffer de
    scores normaux (défaut 200). Le seuil est le percentile (1-fpr) du
    buffer — il monte si les scores montent, descend s'ils redescendent.
    """

    def __init__(self, target_fpr: float = 0.02, window: int = 200):
        self.target_fpr = target_fpr
        self.buffer: deque = deque(maxlen=window)
        self._consec_norm = 0

    def update_normal(self, score: float) -> None:
        """Alimente le buffer avec un score normal (appelé sur trafic sain)."""
        self.buffer.append(score)

    def threshold(self) -> float:
        """Seuil courant = percentile (1-fpr) du buffer récent."""
        if len(self.buffer) < 20:
            return 0.0
        return float(np.percentile(self.buffer, 100 * (1 - self.target_fpr)))

    def is_alert(self, score: float) -> bool:
        """Alerte si le score dépasse le seuil courant."""
        return score > self.threshold()
