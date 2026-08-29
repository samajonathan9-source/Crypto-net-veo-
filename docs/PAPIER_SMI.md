# RATISS-Cyber : Détection d'intrusion par topologie des transitions de phase

**Résumé.** Les détecteurs d'intrusion classiques analysent les *symptômes*
statistiques du trafic — distributions, volumes, fréquences. Nous montrons
qu'une classe d'attaques furtives, que nous construisons pour être
*statistiquement invisibles* (tests de Kolmogorov-Smirnov : ≥ 90% des
features indistinguables du normal), échappe à ces détecteurs mais trahit sa
présence par la *structure* de ses corrélations. En adaptant l'arsenal de la
physique des transitions de phase topologiques (homologie persistante,
participation ratio spectral, mécanisme de Kibble-Zurek, frustration de
triades), nous construisons une batterie d'observables structurelles. Sur un
dataset synthétique contrôlé, chaque attaque est détectée par son observable
propre : le participation ratio détecte la transition de phase (rappel 0.95
vs 0.67 classique), le cumul de Kibble-Zurek détecte le tissage (0.79 vs
0.07). Une fusion spécialisée par famille atteint un rappel moyen de 0.61 à
1.7% de faux positifs — 2.3× le classique seul. Chaque alerte embarque une
preuve SHA-256 vérifiable. *Article en préparation pour SMI CybIA, Douala,
novembre 2026.*

## 1. Introduction

Les systèmes de détection d'intrusion (IDS) modernes reposent sur des
signatures statistiques du trafic. Or un attaquant sophistiqué peut
*préserver les marginales* — les distributions de chaque feature — tout en
réorganisant la *structure* des dépendances entre features. C'est le principe
des attaques par tissage, transition de phase et mutation lente que nous
formalisons. Notre hypothèse : ces réorganisations sont des **transitions de
phase** au sens physique, détectables par les outils de la matière condensée
topologique.

## 2. Menaces : attaques statistiquement invisibles

Trois familles d'attaques, garanties invisibles par tests KS (Tableau 1) :

- **Tissage** : inversion du signe d'un tiers des corrélations — le motif
  change, la moyenne reste (analogie : cristal photo-induit KTN:Li).
- **Transition de phase** : bascule d'une structure en blocs indépendants
  vers un hub centralisé (analogie : modèle SSH).
- **Mutation lente (APT)** : dérive progressive — chaque fenêtre est normale,
  la trajectoire est anormale (analogie : Kibble-Zurek).

## 3. Observables topologiques

| Observable | Mesure | Source physique |
|---|---|---|
| P_sig | boucles de corrélation (homologie H1) | persistance Vietoris-Rips |
| PR | délocalisation spectrale | participation ratio |
| KZ cumul | dérive directionnelle vs référence | mécanisme de Kibble-Zurek |
| Frustration | triangles frustrés (signes) | verre de spin / KTN:Li |
| Edge | concentration des corrélations extrêmes | poids extrémal |

## 4. Résultats

**Figure 1** (fig1_rappel_par_canal.png) : chaque attaque a son observable.
Le classique plafonne ; la topologie voit la structure.

**Figure 2** (fig2_pr_transition.png) : la transition de phase délocalise le
spectre — le PR monte de 7.6 à 9.5.

**Figure 3** (fig3_trajectoire_kz.png) : le cumul de Kibble-Zurek s'élève
sous attaque — la structure s'éloigne du normal.

**Figure 4** (fig4_matrices_correlation.png) : les matrices de corrélation
rendent la structure visible.

Fusion spécialisée par famille : rappel moyen 0.61, FPR 1.7%.

## 5. Limites et travaux futurs

KZ_cumul détecte les campagnes groupées (pas les attaques isolées) ; la
mutation lente reste la plus difficile (0.28) ; validation sur trafic réel
(CIC-IDS2017) en cours ; LCT pour l'adaptation continue.

## 6. Validation sur trafic réel (UNSW-NB15)

Le concept est validé sur UNSW-NB15 (partitions officielles, 175k/87k, 9
familles) : le KZ cumul détecte les Generic à 0.51 vs 0.02 classique. La
fusion adaptative (routeur à centroïdes) atteint 0.339 ≈ borne oracle 0.328,
1.94× la statique. Validation croisée temporelle 5-fold : 0.342 ± 0.227 —
robuste en moyenne, variable selon régime (analyse honnête du Fold 4).

## 7. Limites et travaux futurs

L'écart-type élevé (0.227) reflète les ruptures de régime : la détection de
dérive + recalibration aide (Fold 4 +88%). La mutation lente reste difficile
(fenêtres plus grandes). Calibration dynamique en production, mémoire
procédurale pour les campagnes.

## 8. Conclusion

La cybersécurité gagne à regarder le trafic comme un système physique : les
intrusions furtives sont des transitions de phase, et l'arsenal de la matière
condensée topologique les rend visibles — sur trafic réel comme en synthétique.

---

*Code et données reproductibles : github.com/samajonathan9-source/Crypto-net-veo-*
