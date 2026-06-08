# Patterns Validés — Tennis Monitor

## Scraping FRMT
- Le site utilise AJAX + scroll infini → Playwright obligatoire
- Parser le texte brut uniquement — la structure HTML change sans prévenir
- Conserver l'ordre natif du serveur (ne pas re-trier côté client)

## Notifications Telegram
- Format validé : nom en gras, 📍 ville — club, 📅 dates, ⏰ inscription, 👉 lien
- Voyant 🟢 = inscriptions ouvertes, 🔴 = fermées (basé sur date inscription_avant)
- Envoyer une notif par tournoi, pas tout en un seul message

## State
- `state.json["known"]` = set de clés de déduplication (format: "NOM|date_debut|club")
- Ne jamais interpréter l'ordre des clés dans `known` comme un ordre chronologique

## CI/CD
- GitHub Actions, cron toutes les 30 minutes (0,30 * * * *)
- Quota GitHub Actions free : ~2250 min/mois avec cette fréquence (dans les limites)
- TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans les secrets GitHub du repo

## Scroll AJAX FRMT
- Scroll bidirectionnel requis : scroll bas pour déclencher le chargement, puis scroll haut pour réinitialiser le trigger
- Ne pas utiliser `page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` seul — combiner avec scroll vers le haut intermédiaire

## Telegram getUpdates
- Utiliser `timeout=0` pour getUpdates (long polling désactivé, réponse immédiate)
- Ne pas utiliser de webhook sur un script CI — getUpdates suffit pour lire les commandes entrantes

## Git state.json
- Toujours `git pull --rebase origin main` avant de committer state.json
- En cas de conflit sur state.json : garder la version locale (elle est plus récente)
