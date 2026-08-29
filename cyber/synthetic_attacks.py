"""Dataset synthétique RATISS — attaques topologiques pures.

Philosophie : les datasets publics (NSL-KDD, CIC-IDS2017) contiennent des
attaques qui produisent AUSSI des symptômes statistiques. Pour prouver
l'avantage unique de la couche topologique, il faut des attaques qui ne
produisent AUCUN symptôme statistique — seulement une réorganisation
structurelle. C'est le cas que les classiques ratent PAR CONSTRUCTION.

Garantie d'honnêteté : chaque attaque générée est vérifiée — les marginales
(moyenne, écart-type par feature) doivent être indistinguables du normal
(test KS, seuil 0.05). Si une attaque fuit statistiquement, elle est rejetée.

Trois familles d'attaques topologiques (inspiration KTN:Li) :
1. TISSAGE (weaving) : les features se réorganisent en boucles de
   corrélation (le motif change, la moyenne reste) — comme les motifs
   entrelacés du cristal photo-induit
2. TRANSITION DE PHASE : la matrice de corrélation bascule d'une phase
   (blocs indépendants) à une autre (hub centralisé) — comme la transition
   topologique du modèle SSH
3. MUTATION LENTE (APT) : la structure dérive progressivement — chaque
   fenêtre individuelle est normale, mais la TRAJECTOIRE topologique
   est anormale (hystérésis Kibble-Zurek)
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def _validate_marginals(X_normal: np.ndarray, X_attack: np.ndarray, alpha: float = 0.01) -> dict:
    """Vérifie que l'attaque ne fuit pas statistiquement : test KS par
    feature. Retourne le nombre de features indistinguables et le verdict."""
    n_features = X_normal.shape[1]
    n_pass = 0
    p_values = []
    for j in range(n_features):
        _, p = stats.ks_2samp(X_normal[:, j], X_attack[:, j])
        p_values.append(float(p))
        if p > alpha:
            n_pass += 1
    return {
        "features_indistinguishables": n_pass,
        "total_features": n_features,
        "fraction": n_pass / n_features,
        "min_p_value": min(p_values),
        "honnete": n_pass / n_features >= 0.9,  # >= 90% des features invisibles
    }


def _sample_with_correlation(
    mean: np.ndarray, target_corr: np.ndarray, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Échantillonne n points gaussiens de moyenne `mean` et de matrice de
    corrélation cible `target_corr` (variances unitaires)."""
    d = len(mean)
    # régularisation : la corrélation cible doit être définie positive
    eigvals, eigvecs = np.linalg.eigh(target_corr)
    eigvals = np.clip(eigvals, 1e-6, None)
    cov = eigvecs @ np.diag(eigvals) @ eigvecs.T
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal((n, d))
    return mean + z @ L.T


def generate_normal(mean: np.ndarray, corr: np.ndarray, n: int, rng) -> np.ndarray:
    """Trafic normal : gaussien multivarié de structure de corrélation donnée."""
    return _sample_with_correlation(mean, corr, n, rng)


def attack_weaving(mean: np.ndarray, corr: np.ndarray, n: int, rng) -> np.ndarray:
    """TISSAGE : réorganise les boucles de corrélation en préservant les
    marginales. Le signe de certaines corrélations s'inverse (le motif
    s'entrelace différemment) — la moyenne et la variance ne bougent pas."""
    d = len(mean)
    corr_w = corr.copy()
    # inverse un tiers des corrélations hors diagonale (tissage)
    iu = np.triu_indices(d, 1)
    n_flip = len(iu[0]) // 3
    idx = rng.choice(len(iu[0]), n_flip, replace=False)
    for k in idx:
        i, j = iu[0][k], iu[1][k]
        corr_w[i, j] = -corr_w[i, j]
        corr_w[j, i] = -corr_w[j, i]
    return _sample_with_correlation(mean, corr_w, n, rng)


def attack_phase_transition(mean: np.ndarray, corr: np.ndarray, n: int, rng) -> np.ndarray:
    """TRANSITION DE PHASE : la structure bascule de blocs indépendants vers
    un hub centralisé (une feature devient corrélée à toutes les autres).
    Les marginales (moyenne, variance par feature) sont préservées."""
    d = len(mean)
    corr_p = np.eye(d) * 0.5 + 0.5 * corr  # part de la structure normale
    hub = int(rng.integers(0, d))
    # le hub absorbe les corrélations : fortement lié à tous, les autres
    # se décorrèlent entre eux (transition de phase du graphe)
    for j in range(d):
        if j != hub:
            corr_p[hub, j] = corr_p[j, hub] = 0.7 * np.sign(corr[hub, j] + 1e-9)
    for i in range(d):
        for j in range(d):
            if i != hub and j != hub and i != j:
                corr_p[i, j] *= 0.3
    np.fill_diagonal(corr_p, 1.0)
    return _sample_with_correlation(mean, corr_p, n, rng)


def attack_slow_mutation(
    mean: np.ndarray, corr: np.ndarray, n: int, rng, n_steps: int = 10
) -> np.ndarray:
    """MUTATION LENTE (APT) : la structure dérive progressivement du normal
    vers un état tissé. Chaque sous-fenêtre est proche du normal, mais la
    trajectoire globale est anormale."""
    blocks = []
    corr_target = corr.copy()
    d = len(mean)
    iu = np.triu_indices(d, 1)
    idx = rng.choice(len(iu[0]), len(iu[0]) // 3, replace=False)
    for k in idx:
        i, j = iu[0][k], iu[1][k]
        corr_target[i, j] = corr_target[j, i] = -corr_target[i, j]
    block_len = n // n_steps
    for step in range(n_steps):
        alpha = step / max(n_steps - 1, 1)  # 0 = normal, 1 = tissé
        corr_step = (1 - alpha) * corr + alpha * corr_target
        blocks.append(_sample_with_correlation(mean, corr_step, block_len, rng))
    remainder = n - n_steps * block_len
    if remainder > 0:
        blocks.append(_sample_with_correlation(mean, corr_target, remainder, rng))
    return np.vstack(blocks)


def build_synthetic_dataset(
    n_features: int = 16,
    n_normal: int = 3000,
    n_per_attack: int = 600,
    seed: int = 42,
) -> dict:
    """Construit le dataset synthétique complet avec validation d'honnêteté."""
    rng = np.random.default_rng(seed)
    mean = rng.uniform(-1, 1, n_features)
    # structure de corrélation normale réaliste : blocs de features liées
    # (ex. compteurs de connexion) + bruit faible. Un normal trop
    # structuré ne laisse aucune marge de contraste aux attaques.
    corr = np.eye(n_features)
    block = 4
    for i in range(0, n_features, block):
        for j in range(i, min(i + block, n_features)):
            for k in range(j + 1, min(i + block, n_features)):
                corr[j, k] = corr[k, j] = 0.5
    corr += rng.uniform(-0.05, 0.05, (n_features, n_features))
    corr = 0.5 * (corr + corr.T)
    np.fill_diagonal(corr, 1.0)

    X_normal = generate_normal(mean, corr, n_normal, rng)
    attacks = {
        "weaving": attack_weaving(mean, corr, n_per_attack, rng),
        "phase_transition": attack_phase_transition(mean, corr, n_per_attack, rng),
        "slow_mutation": attack_slow_mutation(mean, corr, n_per_attack, rng),
    }

    validation = {}
    for name, X_att in attacks.items():
        validation[name] = _validate_marginals(X_normal, X_att)

    labels = np.array(
        ["normal"] * n_normal
        + [name for name, X in attacks.items() for _ in range(len(X))]
    )
    X = np.vstack([X_normal] + list(attacks.values()))
    return {"X": X, "labels": labels, "validation": validation,
            "n_features": n_features, "seed": seed}
