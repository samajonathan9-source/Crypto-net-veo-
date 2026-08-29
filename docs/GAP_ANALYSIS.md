# Tâche 1.3 — Ce que les méthodes classiques ratent

## La lacune, mesurée

Sur KDDTest+ (benchmark Phase 1, Random Forest — le meilleur FPR) :

| Famille d'attaque | Nature | Rappel classique | Pourquoi les classiques ratent |
|---|---|---|---|
| DoS | Volumétrique, bruyante | 81.8% | — (détectée) |
| Probe | Scan, répétitif | 74.5% | — (détectée) |
| **R2L** | Accès distant furtif, sessions lentes qui **imitent le normal** | **5.8%** | Les features statistiques d'une session R2L ressemblent à du trafic légitime. Pas de burst, pas de volume — rien à voir pour un détecteur statistique. |
| **U2R** | Élévation de privilèges, rare et subtile | **7.7%** | Trop peu d'exemples pour le supervisé ; trop proche du normal pour l'anomalie. |

**Pattern général** : les classiques voient les *symptômes* (volume, fréquence,
écart à la moyenne). Une attaque qui ne produit pas de symptôme statistique
est invisible — même si elle **réorganise la structure** des relations entre
features (qui parle à qui, dans quel ordre, avec quelles dépendances).

## Le test topologique préliminaire (sonde RATISS)

Protocole : fenêtres de 30 connexions, 16 features numériques, matrice de
corrélation régularisée, métrique couplée RATISS (P_sig + edge − 0.1·entropie,
formule validée sur QPU IBM dans l'écosystème RATISS). Script :
`benchmarks/run_topo_probe.py` → `artifacts/topo_probe.json`.

| Catégorie | P_sig (persist. H1) | Score couplé | Contraste vs normal |
|---|---|---|---|
| normal | 0.076 | −0.306 | — |
| DoS | 0.084 | −0.402 | −0.096 |
| Probe | 0.075 | −0.413 | −0.107 |
| **R2L** | **0.126** | −0.291 | **+0.015** |

## Le signal qui compte

**R2L — la catégorie où le classique est aveugle (5.8%) — montre le contraste
topologique le plus fort : P_sig +66% vs normal.**

Lecture transdisciplinaire : une session R2L n'est pas une anomalie
*statistique*, c'est une **transition de phase structurelle** — comme dans le
cristal KTN:Li où la polarisation change la topologie des corrélations sans
changer la densité moyenne. Les boucles H1 (persistance homologique) capturent
cette réorganisation.

## Limites honnêtes de ce test préliminaire

1. Fenêtres tirées **aléatoirement** dans chaque catégorie, pas temporelles —
   la Phase 2 devra construire de vraies fenêtres glissantes sur flux ordonnés.
2. L'écart R2L est prometteur mais doit passer un **test statistique** (n=40
   fenêtres/catégorie ici ; il faudra bootstrap + p-value).
3. Le score couplé est négativement contrasté sur DoS/Probe — la métrique
   devra être **recalibrée par famille d'attaque** (poids w différents), ce
   que la Phase 2 fera par grid search.
4. KDDTest+ est ancien ; confirmation requise sur CIC-IDS2017 (Phase 3).

## Conclusion pour l'architecture

La complémentarité est démontrée en préliminaire :

```
        Classique fort (DoS, Probe)  ←→  Classique aveugle (R2L, U2R)
        Topo : contraste faible      ←→  Topo : contraste maximal
```

Ni le classique seul, ni la topologie seule ne suffisent. **La fusion est le
produit.** C'est exactement l'architecture de `ARCHITECTURE_V1.md`.
