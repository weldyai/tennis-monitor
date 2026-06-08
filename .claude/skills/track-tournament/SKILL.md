---
name: track-tournament
description: Ajouter un tournoi au tracking dans state.json (convocation + inscriptions)
---
# Track Tournament

## Step 1: Trouver la clé du tournoi
```bash
python3 -c "
import json
with open('state.json') as f:
    s = json.load(f)
for sid, meta in s.get('id_map_meta', {}).items():
    print(sid, meta['nom'], meta['debut'])
print('---')
print('Déjà trackés:', list(s.get('tracked', {}).keys()))
"
```

## Step 2: Injecter dans tracked
```python
import json, hashlib
with open('state.json') as f:
    s = json.load(f)

# Remplir avec les vraies valeurs du tournoi
nom = "TOURNOI X"
club = "CLUB"
debut = "JJ-MM-AAAA"
fin = "JJ-MM-AAAA"
inscription_avant = "JJ-MM-AAAA"

key = f"{nom}|{debut}|{club}"
sid = hashlib.md5(key.encode()).hexdigest()[:8]
meta = {"nom": nom, "ville": "", "club": club, "debut": debut, "fin": fin, "inscription_avant": inscription_avant}

s.setdefault("id_map", {})[sid] = key
s.setdefault("id_map_meta", {})[sid] = meta
s.setdefault("tracked", {})[key] = {**meta, "last_inscriptions": "", "convocation_notified": False}

with open('state.json', 'w') as f:
    json.dump(s, f, indent=2, ensure_ascii=False)
print("Tracké:", key)
```

## Step 3: Committer et pusher
```bash
git add state.json
git commit -m "track: add <nom>"
git pull --rebase && git push
```
