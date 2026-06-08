# Corrections — Tennis Monitor

## 2026-05-05
- Ne pas prendre les derniers items du `state.json["known"]` pour identifier les "derniers tournois" — ce sont des clés de déduplication, pas ordonnées par date d'ajout. Les nouveaux tournois sont ceux détectés par le scraper (non présents dans `known` avant le run).
