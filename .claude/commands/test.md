---
name: test
description: Lance le scraper en mode dry-run (sans vrai token Telegram)
---
# Test Scraper

```bash
cd /Users/brahimamdouy/code/apps/tennis-monitor
TELEGRAM_BOT_TOKEN=dummy TELEGRAM_CHAT_ID=dummy python3 scraper.py
```

Vérifie : nombre de tournois, nouveaux détectés, pas d'erreur Python.
