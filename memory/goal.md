# Goal actif — remettre à plat Tennis Monitor (tournois ratés, bouton Suivi, notif convocation)

**Statut** : atteint (01/11/2026) — critères 1 à 6 verts ; convocation réelle à valider à la prochaine publication

## Objectif
Tennis Monitor détecte tous les tournois, le bouton « Suivre » Telegram enregistre bien le suivi, et la notification de convocation part quand elle est publiée.

## Critère de fin (tous verts)
1. Cause racine prouvée (logs CI, state.json, code) pour chacun des 3 symptômes : (a) tournois ratés, (b) clic « Suivre » sans effet, (c) pas de notif à la publication de la convocation.
2. Correctifs + tests pytest verts (reproduisent chaque bug avant fix, passent après).
3. Simulation locale bout en bout, Telegram mocké : callback « Suivre » → tournoi dans les suivis ; convocation publiée → notification émise une seule fois.
4. Un run CI réel vert après merge + `process-callbacks` vert.
5. Autodiagnostic : chaque alerte (stagnation, count_drop, tracked_empty, crash) indique cause probable + correction, et auto-répare quand c'est sûr.
6. Test final : Brahim clique « Suivre » sur un vrai tournoi dans Telegram et confirme.

## Périmètre
- Autorisé : lecture code/logs, tests locaux, clones jetables dans le scratchpad, lecture seule du site FRMT, `gh run/workflow`, modifs de `scraper.py`, `tests/`, `.github/workflows/*`, commits + PR sur branche dédiée.
- Interdit : envoi Telegram réel avant le test final, édition manuelle de `state.json` (passer par `track-tournament`), push sur main sans PR, ajout de features hors critère.

## Budget
5 itérations max, checkpoint à l'itération 3.

## Vérificateur
pytest + simulation locale + `gh run view` (logs réels) ; `code-review` sur le diff avant PR.

## Journal
1. Diagnostic : bot OK, pas de webhook, 0 update en attente (run 41317070401). telegram_offset figé depuis le 13/08. Crons GitHub dégradés à 3-8 h (charge GitHub à :00/:30, dépôt public, pas lié au plan gratuit). Scraper ne voit que 11 tournois depuis oct (88 en sept). monitor.yml sans groupe de concurrence (course avec callbacks). Autodiagnostic existant (84d259c) = alertes seules, sans correction.
Pistes : déclencheur externe (cron-job.org -> workflow_dispatch) + minutes décalées ; concurrency sur monitor.yml ; vérifier la liste des tournois vs site réel ; étendre l'autodiagnostic.
2. Site réel = 11 tournois (parsing 11/11, 0 ligne ignorée) -> « tournois ratés » = détection retardée par les crons, pas de perte de parsing. Correctifs (PR claude/fix-suivi) : crons hors :00/:30 + concurrency monitor.yml ; _check_convocation : un PDF (hors règlement) dans l'onglet Convocations vaut publication (la PR #1 avait trop resserré) ; parsing tolérant (inscription_avant optionnel) + alerte parse_gap ; alerte cron_lag ; alertes avec cause + correction. 35 tests verts (clic Suivre, convocation notifiée 1 seule fois, lag). Step DIAG retiré.
Écart restant : merge PR, run CI réel vert, déclencheur externe (cron-job.org, besoin d'un token GitHub de Brahim), test final clic Suivre.
3. Test final OK (clic « Suivre » → TCR GRADE 3 suivi). Déclencheur externe cron-job.org en place, cadence 5/30 min vérifiée sur ~1 h, tous runs verts. Résultat : cause racine = retard des crons GitHub, corrigé par le déclenchement externe + durcissement du scraper (PR #6).
