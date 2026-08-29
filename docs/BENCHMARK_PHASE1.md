# Tâche 1.2 — Benchmark des algorithmes classiques (NSL-KDD)

## Protocole (reproductible)

- Train : 40 000 échantillons de KDDTrain+ (seed 42), StandardScaler
- Test : 10 000 échantillons de KDDTest+ — **avec ses attaques inédites**
- Classification binaire normal/attaque
- Seuil : p95 des scores sur trafic normal (non supervisé) / 0.5 (supervisé)
- Script : `benchmarks/run_nsl_kdd.py` → `artifacts/benchmark_nsl_kdd.json`

## Résultats

| Algorithme | Type | Accuracy | F1 | FPR | AUC | Inférence |
|---|---|---|---|---|---|---|
| One-Class SVM | anomalie non sup. | 0.847 | **0.862** | 0.078 | 0.932 | 0.082 ms |
| PCA-Autoencoder | reconstruction | 0.828 | 0.843 | 0.092 | 0.933 | 0.001 ms |
| Isolation Forest | anomalie non sup. | 0.725 | 0.763 | 0.060 | 0.941 | 0.006 ms |
| Random Forest | supervisé | 0.733 | 0.768 | **0.022** | **0.965** | 0.005 ms |

*(PCA-AE = proxy CPU-léger du LSTM-AE : même famille "erreur de
reconstruction". Un vrai LSTM-AE sera ajouté en Phase 3 sur CIC-IDS2017.)*

## Lecture honnête

1. **Personne n'atteint F1 > 0.90 sur KDDTest+** — cohérent avec la
   littérature : le test+ contient 17 types d'attaques absents du train.
   C'est la preuve expérimentale que les méthodes classiques **généralisent
   mal à l'inconnu**.
2. Les AUC (0.93-0.96) sont meilleures que les F1 : les scores sont bons,
   ce sont les **seuils fixes** qui cassent. La fusion topologique devra
   apporter des seuils adaptatifs.
3. Tous passent le critère temps réel (< 100 ms/fenêtre) — la latence ne
   sera pas un problème de couplage.

## Rappel par catégorie (Random Forest, le meilleur FPR)

| Catégorie | n | Rappel | Verdict |
|---|---|---|---|
| DoS | 3 356 | 81.8% | ✅ détecté |
| Probe | 1 076 | 74.5% | ✅ détecté |
| **R2L** | 1 267 | **5.8%** | ❌ **aveugle** |
| **U2R** | 26 | **7.7%** | ❌ **aveugle** |
| normal | 4 275 | 97.8% rejet correct | ✅ |

→ Les classiques ratent **~94% des R2L/U2R** : attaques lentes, furtives,
statistiquement semblables au trafic normal. C'est la lacune exacte que la
couche topologique doit combler (voir `GAP_ANALYSIS.md`).
