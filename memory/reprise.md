# Reprise — Tennis Monitor
## État
En production : GitHub Actions `weldyai/tennis-monitor`, cron toutes les 30 min, derniers runs OK (01/11). 120 tournois connus, 1 suivi. Dernier changement : 01/11, PR #1 (durcissement scraper) et #2 (tests dédup) mergées.

## Repères
- Vérifier la santé : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5` (ou `/check`).
- Ne jamais éditer `state.json` à la main : skill `track-tournament`.
- Bug passé corrigé : déduplication par nom seul qui masquait les nouvelles éditions de tournois récurrents (voir mémoire globale `tennis_monitor.md`).

## Fait le 01/11 (sessions cloud iPhone → PR #1, #2)
- **PR #1 durcissement `scraper.py`** : alerte `parse_empty` + `exit(1)` si 0 tournoi parsé (site indisponible au retry = `exit(0)`, pas d'alerte) ; alerte `detail_missing` si tournoi/onglet introuvable (24 h) ; `_check_convocation` resserré (PDF associé à « convoc », body « ultérieurement » ignoré sans masquer les suivants).
- **PR #2 tests** : `tests/test_dedup.py` (4 tests, `pytest` dans `requirements.txt`) sur la déduplication (même nom + édition/club différent conservé, doublon exact retiré, ordre serveur préservé).
- **`monitor.yml`** : commit du state avec `if: !cancelled()` + retry du push (5 essais).
- **Protocole sessions cloud** (voir CLAUDE.md) : une session cloud écrit dans `memory/sessions/<date>-<sujet>.md`, jamais dans `reprise.md`.

## Prochaine action
- Surveiller le 1er run du cron après les merges (retry du push, `!cancelled()`) : `gh run list ... --limit=5`.
- Non vérifié en réel : (a) alerte `detail_missing` possiblement quotidienne si l'onglet « Convocations » n'existe pas avant publication ; (b) `_check_convocation` ne reconnaît plus un `.pdf` sans « convoc » → valider sur un vrai body AJAX.
- `memory/sessions/2026-11-01-*.md` : intégrés ici, à supprimer au prochain commit.
