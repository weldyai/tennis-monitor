# Reprise — Tennis Monitor
## État
En production : GitHub Actions `weldyai/tennis-monitor`, cron toutes les 30 min, derniers runs OK (26/10). 120 tournois connus, 1 suivi. Dernier commit : 20/08 (fix cron callbacks 5 min).

## Repères
- Vérifier la santé : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5` (ou `/check`).
- Ne jamais éditer `state.json` à la main : skill `track-tournament`.
- Bug passé corrigé : déduplication par nom seul qui masquait les nouvelles éditions de tournois récurrents (voir mémoire globale `tennis_monitor.md`).

## Prochaine action
Aucune en attente.
