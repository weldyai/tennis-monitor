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
    from html import unescape

    DATE_RE = re.compile(r"\d{2}[/-]\d{2}[/-]\d{4}")

    # Les données réelles sont dans le payload XML encodé en \x dans le JS,
    # pas dans les divs A7_*_* (partiellement rendus). On parse le XML directement.
    raw_html = str(soup)

    def decode_hex(s: str) -> str:
        result = []
        i = 0
        while i < len(s):
            if s[i:i+2] == r"\x" and i + 4 <= len(s):
                try:
                    result.append(chr(int(s[i+2:i+4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            result.append(s[i])
            i += 1
        return "".join(result)

    decoded = decode_hex(raw_html)

    # Chercher directement les blocs: <COLONNE>TOURNOI...</COLONNE> suivis de club, dates, ville
    # Le CDATA dans CORPS contient des <COLONNE> qui cassent un split naïf — on cherche
    # le pattern après la fin du CDATA (</COLONNE> juste avant le nom du tournoi)
    pattern = re.compile(
        r"<COLONNE>([^<]*TOURNOI[^<]{0,150})</COLONNE>"   # nom
        r"<COLONNE>([^<]*)</COLONNE>"                      # club
        r"(?:<COLONNE[^/]*/?>)*"                           # colonnes vides optionnelles
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"         # debut
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"         # fin
        r"<COLONNE>([^<]+)</COLONNE>"                      # ville
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>",        # inscription_avant
        re.DOTALL,
    )

    tournaments = []
    seen = set()

    for m in pattern.finditer(decoded):
        nom = unescape(m.group(1).strip())
        if nom in seen:
            continue
        seen.add(nom)
        tournaments.append({
            "nom": nom,
            "club": unescape(m.group(2).strip()),
            "debut": m.group(3),
            "fin": m.group(4),
            "ville": unescape(m.group(5).strip()),
            "inscription_avant": m.group(6),
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
