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
    from bs4 import BeautifulSoup

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
                print("Site indisponible (503) — on réessaie au prochain run.")
                browser.close()
                return None

            page.wait_for_timeout(5000)
            html = page.content()
        finally:
            browser.close()

    # Sauvegarder le HTML pour debug (visible dans les artifacts GitHub)
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    soup = BeautifulSoup(html, "html.parser")
    return _parse_tournaments(soup)


def _parse_tournaments(soup) -> list[dict]:
    from bs4 import BeautifulSoup
    import re

    tournaments = []

    # Dans WebDev (PCSOFT), le tableau principal a un id commençant par 'ctz'
    # Les lignes de données ont des ids comme 'A7_ligne_0', 'WD_ligne_A7_0', ou des classes spécifiques
    # Stratégie: chercher la table dont les headers contiennent TOURNOI + DÉBUT + VILLE

    all_tables = soup.find_all("table")
    header_table = None
    col_indices = {}

    for table in all_tables:
        # Chercher une ligne qui contient les colonnes TOURNOI, DÉBUT, VILLE
        header_row = table.find("tr", id=lambda x: x and "TITRES" in x)
        if not header_row:
            # Chercher dans les premières lignes
            rows = table.find_all("tr", limit=3)
            for row in rows:
                texts = [td.get_text(strip=True) for td in row.find_all("td")]
                if "TOURNOI" in texts and "VILLE" in texts:
                    header_row = row
                    break

        if header_row:
            headers = [td.get_text(strip=True) for td in header_row.find_all("td")]
            if "TOURNOI" in headers:
                header_table = table
                col_indices = {h: i for i, h in enumerate(headers) if h}
                break

    if not header_table:
        print("Table de tournois non trouvée dans le HTML rendu.")
        return []

    # Les lignes de données: dans WebDev, elles ont souvent un id avec un numéro
    data_rows = header_table.find_all("tr", id=re.compile(r"A\d+_\d+|ligne"))
    if not data_rows:
        # Fallback: toutes les lignes après l'en-tête
        all_rows = header_table.find_all("tr")
        header_idx = all_rows.index(header_row) if header_row in all_rows else 0
        data_rows = all_rows[header_idx + 1:]

    date_months = re.compile(r"janv|févr|mars|avr|mai|juin|juil|août|sept|oct|nov|déc|\d{2}/\d{2}", re.I)

    for row in data_rows:
        cells = row.find_all("td")
        texts = [c.get_text(strip=True) for c in cells]
        if not texts:
            continue

        def get_col(name, fallback_idx):
            idx = col_indices.get(name, fallback_idx)
            return texts[idx] if idx < len(texts) else ""

        nom = get_col("TOURNOI", 3)
        club = get_col("CLUB", 4)
        debut = get_col("DÉBUT", 5)
        fin = get_col("FIN", 6)
        ville = get_col("VILLE", 7)
        inscr = get_col("INSCR. avant", 8)

        # Garder uniquement les vraies lignes de tournoi
        if (nom and len(nom) > 5
                and not nom.startswith("id_")
                and not nom.startswith("TOURNOI")
                and (date_months.search(debut) or date_months.search(fin))):
            tournaments.append({
                "nom": nom, "club": club, "debut": debut,
                "fin": fin, "ville": ville, "inscription_avant": inscr,
            })

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
