# Tennis Monitor

## Context
Scraper Python qui surveille les tournois FRMT (Fédération Royale Marocaine de Tennis) toutes les 30 minutes via GitHub Actions. Scraping Playwright (AJAX scroll sur app WebDev/PCSOFT), parsing XML brut, notifications Telegram par tournoi. Permet de tracker des tournois individuels et d'être notifié quand la convocation est disponible.

## Stack
- Backend: Python 3.12 + Playwright (scraping JS/AJAX) + BeautifulSoup
- CI: GitHub Actions cron `0,30 * * * *` toutes les 30 min (repo weldyai/tennis-monitor)
- Notifications: Telegram Bot API (getUpdates polling, timeout=0, pas de webhook)
- State: `state.json` commité après chaque run

## Hard Rules
- Ne jamais modifier `state.json` manuellement — passer par le skill `track-tournament`
- Respecter l'ordre natif des données serveur (ne pas trier côté client)
- Parser le texte brut uniquement — ne pas supposer la structure HTML (elle change)
- `state.json["known"]` = clés de déduplication, pas ordonnées chronologiquement
- Toujours `git pull --rebase` avant de pusher state.json
- Ne jamais committer sans confirmation explicite (exception : session cloud, voir ci-dessous, uniquement sur une branche `claude/*`)
- Ne pas ajouter de dépendances sans mettre à jour `requirements.txt`

## Sessions cloud (iPhone / claude.ai/code) — zéro conflit
- Partir de `origin/main` à jour : `git fetch origin && git switch -c claude/<sujet> origin/main`.
- Ne JAMAIS modifier `memory/reprise.md`, `state.json` ni `.github/workflows/*` (main les modifie en continu). Seul le Mac met à jour `reprise.md`.
- Compte rendu de la session : créer UN fichier neuf `memory/sessions/AAAA-MM-JJ-<sujet>.md` (fait, en cours, prochaine action, points à valider). Un fichier unique par branche = jamais de conflit.
- Avant d'ouvrir/mettre à jour la PR : `git fetch origin && git rebase origin/main`, puis `git push --force-with-lease`.
- Une PR = un sujet, fichiers distincts des autres PR ouvertes (vérifier avec `gh pr list` + `gh pr diff --name-only`). Si recouvrement : le signaler dans la PR, ne pas fusionner.
- Commits autorisés uniquement sur `claude/*`, jamais de push sur `main`.

## Tool Instructions
- Déclencher un run CI : `gh workflow run monitor.yml --repo weldyai/tennis-monitor`
- Watch les logs : `gh run watch --repo weldyai/tennis-monitor <run_id>`
- Lister les derniers runs : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5`
- Voir les logs d'un run : `gh run view --repo weldyai/tennis-monitor <run_id> --log`
- Commandes disponibles : `/reprise` (état + PR cloud), `/check` pour déclencher + watch en un seul appel

## Agent Routing
- Debug scraping (AJAX, scroll, parsing) → `scraper-agent`
- Tracker un nouveau tournoi → skill `track-tournament`
- Déclencher un run manuel → `/check`
- Tâches complexes multi-étapes → `orchestrator`

## Output Rules
- Langue: français
- Réponses: max 5 lignes sauf si la tâche exige plus
- Pas d'introduction, pas de récapitulatif en fin
