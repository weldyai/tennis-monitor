# Reprise — Tennis Monitor
## État
En production : GitHub Actions `weldyai/tennis-monitor`, cron toutes les 30 min, derniers runs OK (26/10). 120 tournois connus, 1 suivi. Dernier commit : 20/08 (fix cron callbacks 5 min).

## Repères
- Vérifier la santé : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5` (ou `/check`).
- Ne jamais éditer `state.json` à la main : skill `track-tournament`.
- Bug passé corrigé : déduplication par nom seul qui masquait les nouvelles éditions de tournois récurrents (voir mémoire globale `tennis_monitor.md`).

## Prochaine action
Aucune en attente.

## 2026-11-01 — Audit durcissement scraper.py (branche `claude/hardening`)
Risques si le site FRMT change, et correctifs :
1. **Regex `<COLONNE>` rigide** → 0 tournoi parsé = sortie silencieuse (`exit(0)`). Fix : alerte Telegram `parse_empty` + `exit(1)` (CI rouge).
2. **Libellés UI en dur** (nom du tournoi, onglets `Inscriptions`/`Convocations`) → `fetch_detail` renvoie `{}` sans bruit, le suivi meurt. Fix : marqueur `_missing` + alerte `detail_missing:<id>` (24 h).
3. **`_check_convocation` trop large** (tout `.pdf` = convocation, `ultérieurement` court-circuite tout). Fix : PDF associé à « convoc » uniquement, body « ultérieurement » ignoré sans masquer les autres.

À faire : valider le fix 3 sur un vrai body AJAX Convocations (non testé en live), puis merge de la PR.
