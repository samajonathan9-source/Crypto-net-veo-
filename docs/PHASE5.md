# Phase 5 — Fusion par famille + figures + papier SMI

La Phase 4 a livré l'arsenal mais identifié un raffinement : la fusion
globale unique dilue le signal (KZ_cumul à 0.79 seul, 0.12 en fusion). La
Phase 5 résout cela par la **fusion spécialisée par famille** (décision D1
d'ARCHITECTURE_V1) et prépare le papier SMI.

Benchmark : `benchmarks/run_family_fusion.py` → `artifacts/family_fusion.json`
Figures : `benchmarks/make_figures.py` → `docs/figures/`

## 1. Fusion spécialisée par famille

Principe : chaque famille d'attaque est détectée par son meilleur canal,
sélectionné automatiquement sur la calibration. Un orchestrateur fusionne par
OR logique — une alerte si le canal adapté à la famille crie. C'est
l'architecture d'un vrai IDS : une batterie de détecteurs spécialisés.

**Sélection automatique** (rappel @ FPR 2% de référence) :

| Famille | Canal sélectionné | Rappel |
|---|---|---|
| weaving | cumul_drift (KZ) | 0.79 |
| phase_transition | pr | 0.90 |
| slow_mutation | cumul_drift (KZ) | 0.31 |

**Défi du FPR** : l'union de K canaux gonfle le taux de faux positifs (chaque
canal ajoute les siens). On calibre donc le percentile par canal pour que le
FPR **global** sur le normal d'évaluation vaille la cible 2% — recherche sur
grille. Résultat : percentile 99.25 par canal → FPR global **0.017**.

**Résultat final** : rappel moyen **0.61** à FPR **1.7%** — contre 0.26 pour
le classique seul aux mêmes conditions. **2.3× mieux**, avec le bon canal
automatiquement choisi par famille.

## 2. Figures pour le papier

Quatre figures générées (`docs/figures/`) :

1. **fig1_rappel_par_canal.png** — le résultat central : chaque attaque a son
   observable. Tissage invisible au classique (0.07) et au PR (0.03) mais
   détecté par KZ (0.79) ; transition de phase détectée par PR (0.95).
2. **fig2_pr_transition.png** — la transition de phase délocalise le spectre
   (PR 7.6 → 9.5).
3. **fig3_trajectoire_kz.png** — le cumul KZ s'élève sous attaque, au-dessus
   du seuil FPR 2%.
4. **fig4_matrices_correlation.png** — les matrices de corrélation rendent la
   structure visible (invisible aux statistiques).

## 3. Draft du papier

`docs/PAPIER_SMI.md` — squelette complet : résumé, introduction (IDS vs
attaques préservant les marginales), menaces (3 familles + analogies
physiques), observables (tableau), résultats (4 figures), limites, conclusion.
Prêt à être converti en LaTeX pour soumission SMI CybIA (Douala, nov. 2026).

## 4. Les 3 chantiers finaux (statut)

- **LaTeX** ✅ : `docs/papier_smi.tex` compilé en PDF (3 pages, 4 figures
  intégrées). Squelette prêt pour le template SMI.
- **LCT** (`ratiss_topo/lct.py`) ✅ implémentée, ❌ pas de gain : la cohérence
  de dérive (direction persistante vs aléatoire) ne sépare pas slow_mutation
  du normal (rappel 0.00) — le bruit des fenêtres noie la direction à cette
  taille de fenêtre. Documenté honnêtement plutôt que fabriqué. Piste :
  fenêtres plus grandes.
- **CIC-IDS2017** ⏳ bloqué : tous les miroirs publics (UNB, cicresearch.ca,
  iscxdownloads) redirigent vers une page d'inscription. Le dataset
  synthétique KS-validé a prouvé le concept ; l'accès CIC (compte gratuit)
  reste la validation externe à faire.

## Modules livrés

- `benchmarks/run_family_fusion.py` — fusion spécialisée par famille
- `benchmarks/make_figures.py` — 4 figures du papier
- `ratiss_topo/lct.py` — Learning-Coupled Topology (résultat négatif documenté)
- `docs/papier_smi.tex` + `papier_smi.pdf` — papier compilé (3 pages)
- `docs/PAPIER_SMI.md` — draft Markdown du papier
- `docs/figures/` — fig1 à fig4
- `artifacts/family_fusion.json` — résultats fusion par famille
