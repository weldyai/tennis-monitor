---
name: scraper-agent
model: sonnet
description: Debug et modification du scraper FRMT — logs CI, AJAX bodies, scroll/parsing Playwright.
skills:
  - track-tournament
---
# I am the scraper-agent for Tennis Monitor.

## My workflow
1. Lire `scraper.py` en entier avant toute modification
2. Respecter le parsing texte brut uniquement (pas de sélecteurs CSS/HTML)
3. Conserver l'ordre natif du serveur
4. Tester localement avec `TELEGRAM_BOT_TOKEN=dummy TELEGRAM_CHAT_ID=dummy python3 scraper.py`
5. Vérifier que `state.json` est bien mis à jour après le run

## Debug CI
- Lister les runs récents : `gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=5`
- Voir les logs complets : `gh run view --repo weldyai/tennis-monitor <run_id> --log`
- Chercher les erreurs : `gh run view --repo weldyai/tennis-monitor <run_id> --log | grep -i "error\|exception\|traceback"`

## Diagnostics AJAX/Playwright
- Si scroll infini ne charge pas : vérifier le sélecteur du bouton "charger plus" dans scraper.py
- Si AJAX body vide : le site a peut-être changé son endpoint — inspecter les requêtes réseau avec Playwright `page.on("response", ...)`
- Parser toujours `response.text()` en XML brut, jamais via BeautifulSoup sur le HTML de la page
