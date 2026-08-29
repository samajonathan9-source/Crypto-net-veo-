# RATISS-Cyber — Détection d'intrusion topologique

**POC RATISS Labs (Cameroun) — Jonathan Evina**
Prototype de NIDS couplant les algorithmes classiques de cybersécurité avec
l'arsenal topologique RATISS (Vietoris-Rips, P_sig, métrique couplée robuste).
Cible : démo SMI CybIA, Douala, novembre 2026.

> Les algorithmes classiques voient les **symptômes**. RATISS voit la
> **structure**. La fusion voit les deux — et chaque alerte est prouvée.

## État : Phase 3 terminée ✅

| Phase | Fichier | Résultat clé |
|---|---|---|
| 1.1 Datasets | `docs/DATASETS.md` | NSL-KDD (benchmark) + CIC-IDS2017 (validation) |
| 1.2 Benchmark classiques | `docs/BENCHMARK_PHASE1.md` | F1 max 0.862 (OC-SVM) — personne > 0.90 sur attaques inédites |
| 1.3 Lacunes | `docs/GAP_ANALYSIS.md` | **R2L : classique 5.8% vs P_sig +66%** — complémentarité prouvée |
| 1.4 Architecture v1 | `docs/ARCHITECTURE_V1.md` | Fusion par famille + seuils adaptatifs + preuve SHA-256 |
| 2. Pipeline complet | `docs/PHASE2.md` | Fusion F1=0.911 > classique 0.899 ; rappel R2L +8% ; P_sig R2L p<0.0001 ✅ |
| **3. Avantage unique + démo** | `docs/PHASE3.md` | **Attaques invisibles aux stats (tests KS ✅) : PR détecte la transition de phase rappel 0.95 vs 0.67 classique ; API + dashboard live** |

## Reproduire

```bash
pip install -r requirements.txt
PYTHONPATH=. python benchmarks/run_nsl_kdd.py              # benchmark classique
PYTHONPATH=. python benchmarks/run_topo_probe.py           # sonde topologique
PYTHONPATH=. python benchmarks/run_phase2_pipeline.py      # pipeline fusion NSL-KDD
PYTHONPATH=. python benchmarks/run_synthetic_validation.py # avantage unique (synthétique)

# API + dashboard
PYTHONPATH=. python -m uvicorn api.server:app --port 12000
PYTHONPATH=. python -m streamlit run dashboard/app.py --server.port 12001
```

## Structure

- `ratiss_topo/` — moteur topologique RATISS (Vietoris-Rips GF(2), métrique couplée, canaux spectraux)
- `cyber/` — datasets, détecteurs classiques, fenêtrage, fusion, attaques synthétiques
- `benchmarks/` — scripts Phase 1, 2 et 3
- `api/` — API d'alerte FastAPI (preuve SHA-256)
- `dashboard/` — dashboard Streamlit temps réel
- `artifacts/` — résultats JSON (seed 42, reproductible)
- `docs/` — livrables Phase 1, 2 et 3

## Feuille de route

Phase 1 ✅ Fondations → Phase 2 ✅ pipeline de couplage → Phase 3 ✅ avantage
unique + démo → Phase 4 : arsenal RATISS complet (KTN:Li, hystérésis APT,
LCT) + validation CIC-IDS2017 → Phase 5 : SMI.
