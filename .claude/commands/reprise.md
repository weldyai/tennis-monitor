---
description: Reprendre où on s'est arrêté (inclut les PR/branches claude/* du cloud)
---
1. Exécuter `git fetch origin` puis `gh pr list --repo weldyai/tennis-monitor --state open` et `git branch -r --list 'origin/claude/*'`.
2. Lire `memory/reprise.md`.
3. Donner en 5 lignes : PR/branches claude/* ouvertes (numéro, titre), fait, en cours, prochaine action.
