import json
import os
import sys
import requests
from datetime import datetime, timezone

URL = "https://info.frmt.ma/FRMT_LIVE_WB27"
STATE_FILE = "state.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def fetch_tournaments() -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "fr-FR,fr;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

        try:
            resp = page.goto(URL, wait_until="networkidle", timeout=30000)
            if resp and resp.status == 503:
                print(f"Site indisponible (503) — on réessaie au prochain run.")
                browser.close()
                return None  # None = erreur temporaire, pas de mise à jour d'état

            # Attendre que le tableau de tournois soit chargé
            page.wait_for_timeout(4000)

            # Extraire les lignes du tableau principal
            # Dans WebDev, les lignes de données ont des classes ou IDs spécifiques
            # On cherche les lignes qui contiennent nom de tournoi + dates
            tournaments = page.evaluate("""() => {
                const results = [];

                // Chercher toutes les tables et trouver celle des tournois
                // Les tournois ont typiquement: TOURNOI, CLUB, DÉBUT, FIN, VILLE dans les colonnes
                const allRows = document.querySelectorAll('tr');
                let headerRow = null;
                let headerCols = [];

                for (const row of allRows) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    const texts = cells.map(c => c.innerText.trim());

                    // Détecter la ligne d'en-tête
                    if (texts.includes('TOURNOI') && texts.includes('CLUB') && texts.includes('VILLE')) {
                        headerCols = texts;
                        headerRow = row;
                        continue;
                    }

                    // Si on a trouvé l'en-tête, les prochaines lignes non-vides sont des données
                    if (headerRow && cells.length >= 5) {
                        const nom = texts[headerCols.indexOf('TOURNOI')] || texts[3] || '';
                        const club = texts[headerCols.indexOf('CLUB')] || texts[4] || '';
                        const debut = texts[headerCols.indexOf('DÉBUT')] || texts[5] || '';
                        const fin = texts[headerCols.indexOf('FIN')] || texts[6] || '';
                        const ville = texts[headerCols.indexOf('VILLE')] || texts[7] || '';
                        const inscr = texts.find(t => t.includes('Avr') || t.includes('Mai') || t.includes('Jui') || t.includes('Sep') || t.includes('Oct') || t.includes('Nov')) || '';

                        // Filtrer les lignes vides ou parasites
                        if (nom && nom.length > 3 && !nom.startsWith('id_') && debut && debut.match(/\\d/)) {
                            results.push({ nom, club, debut, fin, ville, inscription_avant: inscr });
                        }
                    }
                }

                return results;
            }""")

        finally:
            browser.close()

    return tournaments


def load_state() -> set[str]:
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE) as f:
        data = json.load(f)
    return set(data.get("known", []))


def save_state(known: set[str]):
    with open(STATE_FILE, "w") as f:
        json.dump(
            {"known": list(known), "updated_at": datetime.now(timezone.utc).isoformat()},
            f, indent=2, ensure_ascii=False
        )


def make_key(t: dict) -> str:
    return f"{t['nom']}|{t['debut']}|{t['club']}"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)


def main():
    tournaments = fetch_tournaments()

    if tournaments is None:
        print("Erreur temporaire — état non modifié.")
        sys.exit(0)  # Ne pas faire échouer le workflow

    if not tournaments:
        print("Aucun tournoi détecté — la structure HTML a peut-être changé.")
        # On envoie une alerte une fois si le parsing échoue
        sys.exit(0)

    known = load_state()
    new_ones = [t for t in tournaments if make_key(t) not in known]

    for t in new_ones:
        msg = (
            f"🎾 <b>Nouveau tournoi FRMT !</b>\n\n"
            f"<b>{t['nom']}</b>\n"
            f"📍 {t['ville']} — {t['club']}\n"
            f"📅 Du {t['debut']} au {t['fin']}\n"
            f"⏰ Inscription avant : {t['inscription_avant']}\n\n"
            f"👉 <a href=\"{URL}\">Voir le tableau</a>"
        )
        send_telegram(msg)
        print(f"Notifié : {t['nom']}")

    updated = known | {make_key(t) for t in tournaments}
    save_state(updated)
    print(f"{len(tournaments)} tournois, {len(new_ones)} nouveau(x).")


if __name__ == "__main__":
    main()
