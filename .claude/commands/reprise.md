---
description: Reprendre où on s'est arrêté (inclut les PR et comptes rendus des sessions cloud)
---
1. `git fetch origin`, puis `gh pr list --repo weldyai/tennis-monitor --state open` et pour chaque PR `gh pr diff <n> --repo weldyai/tennis-monitor --name-only` (signaler tout fichier touché par 2 PR).
2. Lire `memory/reprise.md`, puis les comptes rendus cloud : `memory/sessions/*.md` sur `origin/main` et sur chaque branche `origin/claude/*` (`git show origin/claude/<x>:memory/sessions/<fichier>`).
3. Répondre en 5 lignes : PR ouvertes (numéro, titre, mergeable ?), fait, en cours, prochaine action.
4. Après merge d'une PR : intégrer son compte rendu dans `reprise.md` (sur le Mac uniquement), puis proposer de supprimer le fichier de `memory/sessions/`.
