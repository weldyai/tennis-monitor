# Reprise — Tennis Monitor
## État (01/11/2026)
En production : GitHub Actions `weldyai/tennis-monitor`. Crons décalés (monitor `11,41`, callbacks `3-58/5`) mais GitHub les retarde encore de 3 à 8 h. 11 tournois sur le site (parsing 11/11), 1 suivi : TCR GRADE 3 (31-10-2026), clic « Suivre » validé en réel le 01/11. Goal « remettre à plat » en cours : `memory/goal.md`.

## Repères
- Vérifier la santé : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5` (ou `/check`).
- Ne jamais éditer `state.json` à la main : skill `track-tournament`.
- Bug passé corrigé : déduplication par nom seul qui masquait les nouvelles éditions de tournois récurrents (voir mémoire globale `tennis_monitor.md`).

## Fait le 01/11 (sessions cloud iPhone → PR #1, #2)
- **PR #1 durcissement `scraper.py`** : alerte `parse_empty` + `exit(1)` si 0 tournoi parsé (site indisponible au retry = `exit(0)`, pas d'alerte) ; alerte `detail_missing` si tournoi/onglet introuvable (24 h) ; `_check_convocation` resserré (PDF associé à « convoc », body « ultérieurement » ignoré sans masquer les suivants).
- **PR #2 tests** : `tests/test_dedup.py` (4 tests, `pytest` dans `requirements.txt`) sur la déduplication (même nom + édition/club différent conservé, doublon exact retiré, ordre serveur préservé).
- **`monitor.yml`** : commit du state avec `if: !cancelled()` + retry du push (5 essais).
- **PR #4 (CI)** : `checkout`, `setup-python`, `upload-artifact` en v7 (monitor + process-callbacks) ; run CI réel vert, avertissement Node 20 disparu. `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` devenu superflu (à retirer). **PR #5** : `tests/test_inscriptions.py` (10 tests `_parse_inscriptions`). 27 tests au total.
- **Protocole sessions cloud** (voir CLAUDE.md) : une session cloud écrit dans `memory/sessions/<date>-<sujet>.md`, jamais dans `reprise.md`.

## Fait le 01/11 (goal « remettre à plat », PR #6 mergée)
- Cause racine « Suivre sans effet » / « tournois ratés » : retard des crons GitHub (dépôt public, pas lié au plan gratuit), pas un bug de code. Bot OK, pas de webhook, 0 update en attente.
- PR #6 : `_check_convocation` (PDF hors règlement dans l'onglet Convocations = publié), parsing tolérant + alerte `parse_gap`, alerte `cron_lag`, alertes avec cause + correction, concurrency partagée monitor/callbacks, crons hors :00/:30. 35 tests verts, run CI vert.
- Test final : clic « Suivre » traité après déclenchement manuel de `process-callbacks.yml`.

## Prochaine action
- Déclencheur externe cron-job.org → `workflow_dispatch` (callbacks 5 min, monitor 11,41) : Brahim crée un token GitHub fine-grained (repo tennis-monitor, Actions read/write) ; login Google bloqué dans l'onglet piloté, à faire dans son Chrome. Puis vérifier avec `gh run list` des runs `workflow_dispatch` à cadence.
- Convocation non validable en réel tant qu'aucune n'est publiée ; `detail_missing` à surveiller.
- Retirer `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` de `monitor.yml` (via PR). Clore le goal quand le déclencheur externe est vérifié.
