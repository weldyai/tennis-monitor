---
name: check
description: Déclenche un run GitHub Actions monitor.yml et watch le résultat
---
# /check — Déclencher un run CI

```bash
gh workflow run monitor.yml --repo weldyai/tennis-monitor
```

Puis watch le run :
```bash
gh run watch --repo weldyai/tennis-monitor $(gh run list --repo weldyai/tennis-monitor --workflow=monitor.yml --limit=1 --json databaseId --jq '.[0].databaseId')
```

Affiche les logs en direct. Le run dure ~2-3 minutes.
