# Tâche 1.4 — Architecture de couplage RATISS-Cyber v1

## Principe fondateur

> Les algorithmes classiques voient les **symptômes**.
> RATISS voit la **structure**.
> La fusion voit **les deux** — et chaque alerte est prouvée.

## Schéma v1 (validé par les résultats Phase 1)

```
RATISS-Cyber v1
│
├── ENTRÉE : flux réseau (Phase 1 : NSL-KDD / Phase 3 : PCAP via Zeek, dpkt)
│
├── FENÊTRAGE : fenêtres glissantes de N connexions (N=30 validé en sonde)
│   │
│   ├── BRANCHE A — CLASSIQUE (symptômes)
│   │   ├── Isolation Forest      → score_IF     (fort sur DoS/Probe)
│   │   ├── PCA-Autoencoder       → score_AE     (reconstruction)
│   │   └── One-Class SVM         → score_SVM    (meilleur F1 Phase 1)
│   │
│   ├── BRANCHE B — TOPOLOGIE RATISS (structure)
│   │   ├── matrice de corrélation fenêtre (16 features, shrinkage 0.95)
│   │   ├── Vietoris-Rips GF(2)   → P_sig(H1)    (ratiss_topo/topology.py)
│   │   ├── corrélation extrême   → edge         (ratiss_topo/robust_metrics.py)
│   │   └── entropie corrélation  → entropie     (désordre)
│   │   → score_topo = P_sig + edge − 0.1·entropie
│   │   (CONTRASTE MAXIMAL sur R2L : +66% P_sig — là où A est aveugle)
│   │
│   └── FUSION (décision)
│       ├── score_final = w_A·score_classique + w_B·score_topo
│       ├── poids par FAMILLE d'attaque (grid search Phase 2)
│       │   — la sonde montre que le signe du contraste topo dépend
│       │     de la famille : fusion globale unique insuffisante
│       ├── seuil adaptatif (les AUC > 0.93 avec F1 < 0.87 prouvent
│       │   que les seuils fixes sont le maillon faible)
│       └── preuve SHA-256 de la fenêtre + scores → auditabilité
│
└── SORTIE : alerte + score + preuve vérifiable
```

## Décisions d'architecture issues de la Phase 1

| # | Décision | Justification mesurée |
|---|---|---|
| D1 | **Fusion pondérée par famille**, pas globale | Le contraste topo est +0.015 (R2L) mais −0.10 (DoS/Probe) : un poids unique diluerait le signal |
| D2 | **Seuils adaptatifs** | AUC 0.93-0.96 vs F1 0.76-0.86 : les scores classiques sont bons, les seuils fixes sont mauvais |
| D3 | **P_sig = signal R2L prioritaire** | +66% là où RF=5.8% : c'est le différenciateur n°1 du pitch SMI |
| D4 | Fenêtre N=30, 16 features numériques | Validé par la sonde ; le one-hot sparse casse les corrélations |
| D5 | Moteur Vietoris-Rips **réutilisé tel quel** | `ratiss_topo/topology.py` est le même code GF(2) que l'écosystème RATISS — zéro réécriture, auditabilité héritée |
| D6 | OC-SVM dans la branche A | Meilleur F1 du benchmark (0.862) |

## Couches reportées (Phases 2-4)

- **Couche 1 (capture PCAP)** : Zeek/dpkt — Phase 3 avec CIC-IDS2017
- **Couche 4 (KTN:Li)** : tissage, régénération, hystérésis APT — Phase 4
  (modules déjà disponibles dans l'écosystème : experiment_hysteresis,
  experiment_decoherence du repo Travaux)
- **LSTM-AE réel** : Phase 3 (PCA-AE en proxy pour l'instant)
- **Dashboard Streamlit + API FastAPI** : Phase 3 (pattern déjà éprouvé
  dans ratiss-Skynet/api/server.py)

## Modules du repo (état après Phase 1)

```
Crypto-net-veo-/
├── ratiss_topo/          # moteur topologique RATISS (greffé de Travaux)
│   ├── topology.py       # Vietoris-Rips GF(2), P_sig — INCHANGÉ
│   └── robust_metrics.py # métrique couplée (adaptée réseau : extremal_weight)
├── cyber/
│   ├── datasets.py       # chargeur NSL-KDD (binaire + multiclasse)
│   ├── classical_detectors.py  # IF, OC-SVM, RF, PCA-AE (interface commune)
│   └── topo_probe.py     # sonde topologique fenêtrée
├── benchmarks/
│   ├── run_nsl_kdd.py    # benchmark classique
│   └── run_topo_probe.py # sonde topo + rappel par catégorie
├── artifacts/            # résultats JSON (reproductibles, seed 42)
├── data/                 # NSL-KDD
└── docs/                 # DATASETS, BENCHMARK_PHASE1, GAP_ANALYSIS, ce fichier
```
