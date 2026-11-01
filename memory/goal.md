# Goal actif — valider tennis-monitor de bout en bout (hors test final iPhone)

**Statut** : atteint (2026-11-01) — test final iPhone OK (PR #3)

## Critère de fin
Tous verts : (1) pytest sur main ; (2) nouveaux tests locaux de la logique PR #1 (_check_convocation, _run_scrape, alertes) ; (3) workflows YAML valides + simulation locale du retry de push sous course ; (4) parsing réel du site FRMT (lecture seule, sans Telegram) ; (5) un run CI réel vert après les merges ; (6) protocole sessions cloud simulé. Puis demander à Brahim le test final iPhone.

## Périmètre
- Autorisé : lecture, tests locaux, fichiers tests/ en local non commités, clones jetables dans le scratchpad, lecture seule du site FRMT, `gh workflow run monitor.yml` (déclenchement normal documenté dans CLAUDE.md).
- Interdit : commit/push sans accord, envoi Telegram, modification de state.json, modifs hors tests.

## Budget
Itérations illimitées (accordé par Brahim) ; arrêt si même échec 2 fois ou besoin d'élargir le périmètre.

## Vérificateur
Commandes explicites (pytest, yaml, gh run).

## Journal
1. tests/test_hardening.py (13 cas : _check_convocation, _run_scrape 3 scénarios, throttle, detail_missing) + test_dedup : 17 passed.
2. YAML monitor + process-callbacks valides ; simulation course de push : ancien push rejeté, nouveau step OK (rebase + push).
3. Parsing réel FRMT (lecture seule) : 11 tournois = historique count_history (11 constants), 0 nouveau, 11/11 connus.
4. Run CI réel 41312739475 post-merge : success, 11 tournois, Commit updated state success.
5. fetch_detail réel sur 3 tournois : aucun _missing (onglets Inscriptions/Convocations présents) -> risque « Suivi cassé » quotidien non confirmé ; convocation=False partout (aucune publiée, donc regex de publication non validable en réel).
Écart restant : test final iPhone (protocole sessions) ; tests/test_hardening.py non commité.
