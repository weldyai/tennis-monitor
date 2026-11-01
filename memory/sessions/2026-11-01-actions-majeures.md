# 2026-11-01 — Actions GitHub vers dernières versions majeures

## Fait
- checkout v4→v7, setup-python v5→v7, upload-artifact v4→v7 (monitor.yml, process-callbacks.yml).
- Dernières majeures lues via `git ls-remote --tags` (v7 pour les trois).
- Compat ubuntu-latest (24.04) : runtime Node 24 des actions v7, runner GitHub à jour. YAML valide.
- Scraper non touché.

## En cours
- Rien. Vérification réelle = un run CI après merge.

## Prochaine action
- `/check` après merge pour valider un run complet.
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` (monitor.yml) devenu superflu : à retirer plus tard.

## Points à valider
- Exception à la règle « ne pas modifier .github/workflows/* » : demandée explicitement. Risque de conflit si main touche ces fichiers : rebase avant merge.
