"""Fenêtrage temporel réel — Phase 2 RATISS-Cyber.

La sonde de Phase 1 tirait des fenêtres aléatoires par catégorie. Ici, les
fenêtres sont GLISSANTES et ORDONNÉES, comme en production : le flux arrive,
on regarde les N dernières connexions, on avance.

Label d'une fenêtre : la catégorie dominante de ses connexions (pureté
mesurée ; les fenêtres mixtes sont marquées pour l'évaluation honnête).
"""

from __future__ import annotations

import numpy as np


def sliding_windows(
    X: np.ndarray,
    categories: np.ndarray,
    window: int = 30,
    stride: int = 10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fenêtres glissantes sur le flux ordonné.

    Retourne (starts, labels, purities) : indices de début, catégorie
    dominante, pureté (fraction de la catégorie dominante).
    """
    starts, labels, purities = [], [], []
    for s in range(0, len(X) - window + 1, stride):
        cats = categories[s : s + window]
        values, counts = np.unique(cats, return_counts=True)
        k = int(np.argmax(counts))
        starts.append(s)
        labels.append(values[k])
        purities.append(float(counts[k] / window))
    return np.array(starts), np.array(labels), np.array(purities)


def ordered_stream(
    X: np.ndarray,
    categories: np.ndarray,
    scenario: dict[str, int] | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Construit un flux ordonné réaliste : du trafic normal entrecoupé
    d'épisodes d'attaque (comme un vrai réseau).

    scenario : {catégorie: nombre d'épisodes}. Chaque épisode = un bloc
    contigu de connexions de cette catégorie inséré dans le flux normal.
    Défaut : journée type avec rafales DoS, scans Probe, sessions R2L lentes.
    """
    rng = np.random.default_rng(seed)
    if scenario is None:
        scenario = {"DoS": 6, "Probe": 6, "R2L": 8, "U2R": 2}

    normal = X[categories == "normal"]
    rng.shuffle(normal)

    # budget : 70% normal, 30% attaques (sur-représenté vs production,
    # pour avoir assez de fenêtres d'attaque à évaluer)
    # Épisodes COURTS et DILUÉS : une attaque furtive ne crie pas, elle
    # se fond dans le flux (rappel classique Phase 1 : R2L 5.8%)
    episode_len = {"DoS": 80, "Probe": 60, "R2L": 75, "U2R": 40}
    stream_X, stream_c = [], []

    n_attack = sum(
        min(episode_len.get(c, 100), int((categories == c).sum())) * n
        for c, n in scenario.items()
    )
    n_normal = min(len(normal), int(n_attack * 70 / 30))
    normal = normal[:n_normal]

    # découpe le normal en segments entre lesquels insérer les épisodes
    episodes = []
    for cat, n in scenario.items():
        pool = X[categories == cat]
        rng.shuffle(pool)
        ep_len = min(episode_len.get(cat, 100), len(pool))
        for i in range(n):
            if len(pool) < ep_len:
                break
            episodes.append((pool[:ep_len], cat))
            pool = pool[ep_len:]
    rng.shuffle(episodes)

    seg_len = n_normal // (len(episodes) + 1)
    pos = 0
    for ep_X, ep_cat in episodes:
        seg = normal[pos : pos + seg_len]
        stream_X.append(seg)
        stream_c.extend(["normal"] * len(seg))
        stream_X.append(ep_X)
        stream_c.extend([ep_cat] * len(ep_X))
        pos += seg_len
    seg = normal[pos:]
    stream_X.append(seg)
    stream_c.extend(["normal"] * len(seg))

    return np.vstack(stream_X), np.array(stream_c)
