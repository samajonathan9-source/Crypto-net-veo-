# 🛡️ RATISS-Cyber IDS — Dashboard web

Interface React/Vite (shadcn/ui + Tailwind) avec les métriques **réelles**
du pipeline RATISS-Cyber.

## Design

Sombre premium, layout deux colonnes (registre des canaux + live feed), orbite
animée. Testé desktop + mobile.

## Sections

- **Hero** : "Intrusion, vue par la structure" — intrusion émerge des
  transitions de phase, détectée par l'arsenal topologique.
- **4 métriques réelles** : rappel adaptatif (33.9%), KZ sur Generic (51%),
  CV temporelle (34.2%), fenêtres UNSW (5 487).
- **Canaux topologiques** : KZ_cumul, PR, frustration, edge, entropie —
  chacun avec meilleur canal, preuve SHA-256, score de rappel.
- **Live feed** : fusion validée, KZ sur Generic, CV temporelle.
- **Scan IDS** : bouton animé — retourne un résumé des résultats réels.

## Données connectées

Les valeurs proviennent du pipeline (UNSW-NB15) :
- `run_adaptive_fusion.py` → `artifacts/adaptive_fusion.json`
- `run_temporal_cv.py` → `artifacts/temporal_cv.json`
- `run_unsw_validation.py` → `artifacts/unsw_validation.json`

## Build

```bash
npm install --legacy-peer-deps
npx vite build # -> dist/public/
npx vite preview --port 12003
```

Structure : shadcn/ui + Tailwind (tokens CSS).

## Développement local

```bash
pnpm install
pnpm dev
```

Le dashboard est construit avec React, Vite, TypeScript, TailwindCSS et Lucide icons. Il fonctionne avec des données de démonstration côté client et ne contient aucune clé secrète.
