# Phase 3 — Dataset synthétique RATISS + API + Dashboard

La Phase 2 a prouvé la complémentarité sur NSL-KDD. La Phase 3 prouve
l'**avantage unique** : des attaques que les classiques ratent *par
construction*, et que la topologie voit. Plus l'interface de la démo SMI.

Scripts : `benchmarks/run_synthetic_validation.py` → `artifacts/synthetic_validation.json`
API : `api/server.py` · Dashboard : `dashboard/app.py`

## 1. Le test qui tue : attaques topologiques pures

Pour prouver que la topologie apporte quelque chose d'unique, il faut des
attaques qui ne produisent **aucun symptôme statistique** — seulement une
réorganisation structurelle. `cyber/synthetic_attacks.py` en génère trois,
inspirées de l'arsenal RATISS (KTN:Li, transition SSH, Kibble-Zurek) :

| Attaque | Principe | Analogie RATISS |
|---|---|---|
| **weaving** (tissage) | inverse le signe d'1/3 des corrélations — le motif change, la moyenne reste | motifs entrelacés du cristal photo-induit |
| **phase_transition** | la structure bascule de blocs indépendants vers un hub centralisé | transition topologique du modèle SSH |
| **slow_mutation** (APT) | la structure dérive progressivement — chaque fenêtre est normale, la trajectoire est anormale | hystérésis Kibble-Zurek |

**Garantie d'honnêteté** : chaque attaque est vérifiée par tests KS — les
marginales doivent être indistinguables du normal (≥ 90% des features,
seuil 0.01). Résultat : 15-16/16 features invisibles pour les trois. **Si un
classique les détecte, c'est de la chance ; si la topologie les détecte,
c'est de la structure.**

## 2. Résultat : la topologie voit là où le classique est aveugle

Rappel à FPR ≈ 2% (fenêtres pures, split calibration/évaluation disjoint) :

| Attaque | Classique | P_sig | edge | drift | **PR** | **Fusion** |
|---|---|---|---|---|---|---|
| phase_transition | 0.67 | 0.02 | 0.22 | 0.00 | **0.95** | **0.88** |
| slow_mutation | 0.05 | 0.07 | 0.05 | 0.02 | 0.29 | 0.06 |
| weaving | 0.07 | 0.03 | 0.02 | 0.02 | 0.03 | 0.08 |

**Le participation ratio (PR) détecte la transition de phase avec un rappel
de 0.95 — là où le meilleur classique plafonne à 0.67.** C'est l'avantage
unique prouvé : sur une attaque invisible aux statistiques, la structure
spectrale du graphe de corrélation trahit l'intrusion.

## 3. Leçons d'itération (transparence totale)

Cette phase a exigé 5 itérations — chaque échec a affiné la compréhension :

1. **P_sig aveugle au tissage** : il travaille sur |C|, donc insensible aux
   inversions de signe. → Il faut des observables **spectraux**.
2. **Bruit de structure normal trop fort** : un normal trop structuré ne
   laisse aucune marge de contraste. → Normal réaliste en blocs + bruit faible.
3. **Bug neg_energy = 0.0 partout** : le shrinkage de régularisation rend
   toute matrice définie positive (pas de λ<0). Le rappel 1.00 initial était
   un **artefact du seuil 0.0** — erreur détectée et corrigée honnêtement.
   → neg_energy mesure désormais la fraction de corrélations négatives.
4. **Signe de PR inversé** : phase_transition fait *monter* PR (structure
   délocalisée), pas descendre. Corrigé après inspection des distributions.
5. **Fusion en somme dilue** : un seul canal qui crie doit suffire.
   → Fusion par **max des z-scores pondérés**.

**Leçon transdisciplinaire** : il faut la bonne observable pour la bonne
transition de phase. P_sig voit la magnitude, le PR voit la délocalisation,
edge voit la concentration, drift voit la trajectoire. La fusion multi-canaux
les combine.

## 4. Limites honnêtes

- **weaving et slow_mutation restent difficiles** (rappel < 0.10) : leur
  réorganisation est trop subtile pour les canaux actuels à FPR 2%. Pistes :
  fenêtres plus grandes, cumul de drift sur la trajectoire, LCT.
- Le dataset est **synthétique gaussien** — le contraste doit être confirmé
  sur trafic réel (CIC-IDS2017, accès en cours).
- La fusion optimise le rappel moyen ; un FPR plus strict réduit le gain.

## 5. API + Dashboard (interface de la démo SMI)

**API FastAPI** (`api/server.py`, port 12000) :
- `GET /health` — état + intégrité
- `POST /analyze` — analyse une fenêtre → scores des 7 canaux + alerte + preuve SHA-256
- `GET /stats` — poids de fusion, seuil, compteurs

Test réel : fenêtre normale → pas d'alerte (score 1.01) ; fenêtre
phase_transition → 🚨 alerte (score 3.08, PR=9.75).

**Dashboard Streamlit** (`dashboard/app.py`, port 12001) : simulation de flux
en direct, injection d'attaques, visualisation des canaux, alertes et preuves.
Vérifié en navigateur : injection phase_transition → alerte correcte, canal
PR dominant, preuve SHA-256 affichée.

## 6. CIC-IDS2017 (accès en cours)

Le miroir UNB redirige vers une page d'inscription — téléchargement direct
impossible sans compte. Le dataset synthétique RATISS a pris le relais pour
prouver l'avantage unique. L'accès CIC-IDS2017 (vrais flux Zeek, dataset
moderne) reste l'objectif de validation externe pour le papier SMI.

## Modules livrés

- `cyber/synthetic_attacks.py` — 3 attaques topologiques pures + validation KS
- `ratiss_topo/robust_metrics.py:spectral_channels` — PR + neg_energy
- `cyber/fusion_engine.py` — fusion par max des z-scores
- `benchmarks/run_synthetic_validation.py` — validation complète
- `api/server.py` — API d'alerte FastAPI
- `dashboard/app.py` — dashboard Streamlit temps réel
