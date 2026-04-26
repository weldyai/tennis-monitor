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
    import re

    # WebDev (PCSOFT) pattern: données dans des divs id="A7_{row}_{col}"
    # col 3=TOURNOI, 4=CLUB, 7=DÉBUT, 8=FIN, 9=VILLE, 10=INSCR.avant
    COL = {"nom": 3, "club": 4, "debut": 7, "fin": 8, "ville": 9, "inscription_avant": 10}

    DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}|\d{1,2}\s+\w+\s+\d{4}")
    GARBAGE_KEYWORDS = {"id_", "LICENCE", "CLT.", "IDM/F", "Colonne", "Action?", "Excel"}

    def get_cell(row_num, col_num):
        el = soup.find("div", id=f"A7_{row_num}_{col_num}")
        return el.get_text(strip=True) if el else ""

    def is_valid_tournament(t: dict) -> bool:
        nom = t["nom"]
        # Nom : longueur raisonnable, pas de keywords d'UI/header
        if not nom or len(nom) > 200:
            return False
        if any(kw in nom for kw in GARBAGE_KEYWORDS):
            return False
        # Dates : debut et fin doivent ressembler à des dates
        if not DATE_RE.search(t["debut"]) or not DATE_RE.search(t["fin"]):
            return False
        # Ville : non vide, pas trop longue
        if not t["ville"] or len(t["ville"]) > 100:
            return False
        return True

    name_cells = soup.find_all("div", id=re.compile(r"^A7_\d+_3$"))
    tournaments = []

    for cell in name_cells:
        row_num = int(cell["id"].split("_")[1])
        nom = cell.get_text(strip=True)
        if not nom:
            continue
        t = {
            "nom": nom,
            "club": get_cell(row_num, COL["club"]),
            "debut": get_cell(row_num, COL["debut"]),
            "fin": get_cell(row_num, COL["fin"]),
            "ville": get_cell(row_num, COL["ville"]),
            "inscription_avant": get_cell(row_num, COL["inscription_avant"]),
        }
        if is_valid_tournament(t):
            tournaments.append(t)

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
