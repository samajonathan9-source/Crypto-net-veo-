# Tâche 1.1 — Datasets publics de cybersécurité

## Tableau comparatif

| Dataset | Taille | Features | Attaques | Forces | Limites | Rôle dans RATISS-Cyber |
|---|---|---|---|---|---|---|
| **NSL-KDD** | 125 973 train / 22 544 test | 41 (4 catég.) | DoS, Probe, R2L, U2R | Standard de la littérature, test+ contient 17 attaques **inédites** (test de généralisation réel) | Ancien (1999 corrigé 2009), trafic synthétique, pas de PCAP | **Benchmark Phase 1** — comparaison avec la littérature |
| **CIC-IDS2017** | 2.5M flows, 5 jours | 80 (CICFlowMeter) | Brute Force, DDoS, Botnet, Infiltration, Web, Heartbleed | Réaliste (PCAP + flows), étiqueté, moderne | Déséquilibre massif, quelques bugs d'étiquetage connus | **Validation principale** (objectif F1 > 0.90) |
| **UNSW-NB15** | 2.5M records | 49 | 9 catégories (Fuzzers, Backdoor, Shellcode...) | Moderne, mix synthétique/réel, PCAP dispo | Biais de synthèse | Validation croisée |
| **CSE-CIC-IDS2018** | 16M flows | 80 | 7 scénarios, infra réelle (AWS) | Le plus réaliste à grande échelle | Très lourd (~440 Go PCAP) | Optionnel, si temps |

## Décision Phase 1

**NSL-KDD d'abord** : petit, standard, et son test+ avec attaques inédites est
un détecteur naturel de sur-apprentissage — exactement le terrain où la
topologie (structurelle, non supervisée) peut prouver sa valeur ajoutée face
aux méthodes supervisées qui échouent sur l'inconnu.

**CIC-IDS2017 ensuite** (Phase 3) : c'est le dataset de la démo SMI — réaliste,
moderne, avec PCAP pour la couche capture (Zeek/dpkt).

## Accès

- NSL-KDD : `data/KDDTrain+.txt`, `data/KDDTest+.txt` (dans ce repo, source
  github.com/defcom17/NSL_KDD)
- CIC-IDS2017 : https://www.unb.ca/cic/datasets/ids-2017.html (inscription)
- UNSW-NB15 : https://research.unsw.edu.au/projects/unsw-nb15-dataset

## Trafic synthétique RATISS (à générer en Phase 3)

Le 4e dataset sera **généré** : attaques topologiques spécifiques (tissage
lent, mutation de structure à signature statistique constante) — les cas que
les classiques ratent *par construction*. C'est le dataset qui prouvera
l'avantage unique de RATISS-Cyber.
