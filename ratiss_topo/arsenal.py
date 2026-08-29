"""Arsenal RATISS avancé — canaux inspirés de la physique des transitions.

Adaptation cyber de trois concepts de l'arsenal photo-induit :

1. HYSTÉRÉSIS (experiment_hysteresis.py) : un système qui traverse une
   transition "s'en souvient" — l'état au retour diffère de l'état à
   l'aller. En cyber : une fenêtre qui suit une attaque garde une trace
   structurelle. On mesure la mémoire comme la persistance de l'anomalie
   APRÈS le pic (la structure ne revient pas instantanément au normal).

2. KIBBLE-ZUREK (experiment_ramp_speeds.py) : près d'une transition, le
   système "gèle" — la dynamique ralentit puis rate le basculement. En
   cyber : un APT qui mute lentement produit un drift faible MAIS
   persistant et directionnel. On mesure le cumul de drift signé (la
   trajectoire s'éloigne du normal sans revenir) et le gel (variance du
   drift qui s'effondre = figeage près du point critique).

3. TISSAGE KTN (ktn_woven.py) : les motifs entrelacés du cristal. En
   cyber : le weaving inverse des signes de corrélation — la structure
   des TRIANGLES (motifs à 3 features) change même si les paires restent
   proches. On mesure la cohérence des triades (produit des 3 corrélations
   d'un triangle) : un tissage crée des triangles frustrés (produit < 0).
"""

from __future__ import annotations

import numpy as np


def triad_frustration(corr: np.ndarray) -> float:
    """Fraction de triangles frustrés (tissage).

    Un triangle (i,j,k) est frustré si le produit C_ij * C_jk * C_ik < 0 :
    les trois features ne peuvent pas être simultanément alignées. Le
    tissage (inversion de signes) crée de la frustration — comme les
    motifs entrelacés du KTN:Li. Le trafic normal, organisé en blocs
    cohérents, a peu de triangles frustrés.
    """
    d = corr.shape[0]
    n_frustrated = 0
    n_total = 0
    for i in range(d):
        for j in range(i + 1, d):
            for k in range(j + 1, d):
                prod = corr[i, j] * corr[j, k] * corr[i, k]
                n_total += 1
                if prod < -1e-9:
                    n_frustrated += 1
    return n_frustrated / max(n_total, 1)


class HysteresisTracker:
    """Mémoire structurelle du flux (hystérésis dynamique).

    Maintient une trace exponentielle de l'anomalie : quand une fenêtre
    est anormale, la trace monte ; elle redescend lentement (constante de
    temps tau). Une attaque brève laisse une trace qui persiste — le
    système "se souvient" de la transition, comme l'hystérésis du SSH.

    L'APT lent, lui, accumule une trace élevée en permanence : chaque
    fenêtre ajoute un peu d'anomalie, la trace ne redescend jamais.
    """

    def __init__(self, tau: float = 8.0):
        """tau : constante de temps de la mémoire (en nombre de fenêtres)."""
        self.tau = tau
        self.trace = 0.0
        self._baseline_mean = 0.0
        self._baseline_std = 1.0

    def calibrate(self, anomaly_normal: np.ndarray) -> None:
        """Apprend le niveau d'anomalie du trafic normal (référence)."""
        self._baseline_mean = float(np.mean(anomaly_normal))
        self._baseline_std = float(np.std(anomaly_normal)) or 1.0

    def update(self, anomaly: float) -> float:
        """Intègre une nouvelle anomalie et retourne la trace (z-score
        intégré avec oubli exponentiel)."""
        z = (anomaly - self._baseline_mean) / self._baseline_std
        z = max(z, 0.0)  # seule l'anomalie positive alimente la trace
        decay = np.exp(-1.0 / self.tau)
        self.trace = decay * self.trace + (1 - decay) * z
        return float(self.trace)


class KibbleZurekTracker:
    """Détecteur de gel et de dérive directionnelle (Kibble-Zurek).

    Un APT lent produit un drift faible mais persistant et directionnel :
    la structure s'éloigne du normal sans jamais revenir. Deux signaux :

    - cumul directionnel : la somme des drifts signés (projections sur la
      direction d'éloignement du normal). Un bruit aléatoire s'annule ;
      une dérive directionnelle s'accumule.
    - gel : la variance du drift qui s'effondre alors que le cumul monte —
      le système se fige près du point critique (signature Kibble-Zurek).
    """

    def __init__(self, window: int = 12):
        self.window = window
        self._ref_corr: np.ndarray | None = None
        self._drifts: list[float] = []

    def set_reference(self, corr_normal: np.ndarray) -> None:
        """Structure de référence du trafic normal (point de départ)."""
        self._ref_corr = corr_normal.copy()

    def update(self, corr: np.ndarray) -> dict:
        """Intègre une nouvelle matrice de corrélation."""
        if self._ref_corr is None:
            self._ref_corr = corr.copy()
            return {"cumul_drift": 0.0, "gel": 0.0}
        # drift signé : projection de (corr - ref) sur la direction actuelle
        delta = corr - self._ref_corr
        dist = float(np.linalg.norm(delta))
        self._drifts.append(dist)
        if len(self._drifts) > self.window:
            self._drifts.pop(0)
        # cumul : distance totale au point de référence (s'éloigne = APT)
        cumul = dist
        # gel : variance du drift récent qui s'effondre (figeage)
        if len(self._drifts) >= 4:
            var = float(np.var(self._drifts))
            mean = float(np.mean(self._drifts))
            gel = mean / (np.sqrt(var) + 1e-9)  # SNR du drift : haut = dérive régulière
        else:
            gel = 0.0
        return {"cumul_drift": cumul, "gel": float(gel)}
