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
- Ne jamais committer sans confirmation explicite
- Ne pas ajouter de dépendances sans mettre à jour `requirements.txt`

## Tool Instructions
- Déclencher un run CI : `gh workflow run monitor.yml --repo weldyai/tennis-monitor`
- Watch les logs : `gh run watch --repo weldyai/tennis-monitor <run_id>`
- Lister les derniers runs : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5`
- Voir les logs d'un run : `gh run view --repo weldyai/tennis-monitor <run_id> --log`
- Commande disponible : `/check` pour déclencher + watch en un seul appel

## Agent Routing
- Debug scraping (AJAX, scroll, parsing) → `scraper-agent`
- Tracker un nouveau tournoi → skill `track-tournament`
- Déclencher un run manuel → `/check`
- Tâches complexes multi-étapes → `orchestrator`

## Output Rules
- Langue: français
- Réponses: max 5 lignes sauf si la tâche exige plus
- Pas d'introduction, pas de récapitulatif en fin
