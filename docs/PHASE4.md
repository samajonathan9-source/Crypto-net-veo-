# Phase 4 — Arsenal RATISS complet

La Phase 3 a prouvé l'avantage unique sur la transition de phase (PR 0.95)
mais a laissé weaving et slow_mutation difficiles. La Phase 4 adapte trois
concepts de l'arsenal photo-induit RATISS pour les traiter — et tient la
promesse transdisciplinaire : **la physique des transitions de phase appliquée
à la cybersécurité**.

Module : `ratiss_topo/arsenal.py` · Benchmark : `benchmarks/run_synthetic_validation.py`

## 1. Les trois concepts adaptés

| Concept physique | Source RATISS | Adaptation cyber |
|---|---|---|
| **Hystérésis dynamique** | `experiment_hysteresis.py` — le système "se souvient" de la transition | `HysteresisTracker` : trace exponentielle de l'anomalie — une attaque laisse une trace qui persiste après le pic |
| **Kibble-Zurek** | `experiment_ramp_speeds.py` — gel près du point critique, dérive non-adiabatique | `KibbleZurekTracker` : cumul de drift directionnel (la structure s'éloigne du normal sans revenir) + gel (SNR du drift) |
| **Tissage KTN:Li** | `ktn_woven.py` — motifs entrelacés du cristal | `triad_frustration` : fraction de triangles frustrés (C_ij·C_jk·C_ik < 0) — le tissage inverse des signes et frustre les triades |

## 2. Résultat : chaque attaque a son observable

Rappel à FPR ≈ 2% (fenêtres pures, flux groupé) :

| Attaque | Classique | PR | frustration | **KZ_cumul** | Fusion |
|---|---|---|---|---|---|
| phase_transition | 0.67 | **0.95** | 0.29 | 0.88 | **0.92** |
| **weaving** | 0.07 | 0.03 | 0.09 | **0.79** 🔥 | 0.12 |
| slow_mutation | 0.05 | 0.29 | 0.07 | 0.33 | 0.06 |

**Percée** : le cumul Kibble-Zurek détecte le **weaving à 0.79** — là où le
classique (0.07), P_sig (0.03) et le PR (0.03) sont tous aveugles. C'est le
deuxième avantage unique prouvé : une attaque purement structurelle, invisible
à toutes les statistiques et à la plupart des canaux topologiques, est trahie
par la **dérive de sa structure par rapport à la référence normale**.

## 3. Cartographie des observables (leçon transdisciplinaire)

Chaque transition de phase a sa bonne observable — c'est la leçon centrale :

| Observable | Ce qu'elle mesure | Attaque détectée |
|---|---|---|
| **P_sig** | magnitude des boucles de corrélation (homologie) | R2L sur NSL-KDD (Phase 2) |
| **PR** | délocalisation spectrale (participation) | phase_transition (0.95) |
| **edge** | concentration des corrélations extrêmes | phase_transition (0.22) |
| **frustration** | triangles frustrés (signes) | weaving (faible seul) |
| **KZ_cumul** | dérive directionnelle vs référence | **weaving (0.79)**, phase (0.88) |
| **drift** | trajectoire entre fenêtres | slow_mutation (à amplifier) |

**Il n'y a pas un détecteur topologique, il y a un arsenal.** La fusion
multi-canaux combine leurs forces — mais elle doit être calibrée par famille
(le contraste change de nature selon l'attaque).

## 4. Limites honnêtes (transparence totale)

- **KZ_cumul dépend du regroupement** : sur un flux mélangé (attaques
  dispersées), 0% de fenêtres pures et le cumul ne s'accumule pas. Il détecte
  les **campagnes** d'attaques groupées — réaliste pour un APT qui frappe en
  rafales, pas pour une attaque isolée unique. C'est le domaine de validité.
- **La fusion sous-exploite KZ_cumul sur weaving** (0.12 vs 0.79 seul) : le
  max des z-scores avec calibration sur normal ne hisse pas assez le canal.
  La fusion optimale par famille reste un raffinement (Phase 5).
- **slow_mutation reste le plus dur** (0.33 max) : sa dérive est lente et
  bidirectionnelle, le cumul partiel. Piste : fenêtres plus grandes + LCT.
- **Référence KZ** : le choix de la structure de référence normale influence
  le cumul. Une référence robuste (médiane sur longue période) est nécessaire
  en production.

## 5. API + Dashboard enrichis

**API** (`api/server.py`) : 9 canaux actifs, dont frustration et cumul_drift.
Le tracker KZ maintient la mémoire du flux entre requêtes (mode campagne).

**Dashboard** (`dashboard/app.py`) : mode campagne (séquence de 4 fenêtres),
trajectoire Kibble-Zurek en direct. Vérifié en navigateur : injection weaving
en campagne → 🚨 alerte correcte (score 1.78 ≥ seuil 1.27), cumul_drift ~4.5.

## 6. Vers la Phase 5 (SMI)

L'arsenal est complet. Reste pour le papier et la démo SMI :
- **Fusion par famille** calibrée (chaque attaque → son poids de fusion)
- **Validation CIC-IDS2017** (accès en cours) pour confirmer sur trafic réel
- **LCT** (Learning-Coupled Topology) pour slow_mutation
- **Figures** pour le papier (diagrammes de persistance, trajectoires KZ)

## Modules livrés

- `ratiss_topo/arsenal.py` — HysteresisTracker, KibbleZurekTracker, triad_frustration
- `benchmarks/run_synthetic_validation.py` — 8 canaux évalués
- `api/server.py` — 9 canaux + mémoire KZ
- `dashboard/app.py` — mode campagne + trajectoire KZ
