import json
import os
import re
import sys
import requests
from datetime import datetime, timezone

URL = "https://info.frmt.ma/FRMT_LIVE_WB27"
STATE_FILE = "state.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def _decode_hex(s: str) -> str:
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


def _parse_tournaments_raw(raw_text: str) -> list[dict]:
    from html import unescape

    decoded = _decode_hex(raw_text)

    pattern = re.compile(
        r"<COLONNE>([^<]*TOURNOI[^<]{0,150})</COLONNE>"
        r"<COLONNE>([^<]*)</COLONNE>"
        r"(?:<COLONNE[^/]*/?>)*"
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"
        r"<COLONNE>([^<]+)</COLONNE>"
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>",
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


def _parse_inscriptions(ajax_responses: list[str]) -> str:
    """
    Parse AJAX responses after clicking a tournament + Inscriptions tab.
    Returns formatted string with per-category breakdown or total inscribed/capacity.
    """
    from html import unescape

    categories = []
    total_info = ""

    for body in ajax_responses:
        # Per-category breakdown (jeunes): RUPTURE CDATA lines
        cdatas = re.findall(r'<!\[CDATA\[(.*?)\]\]>', body, re.DOTALL)
        for cdata in cdatas:
            clean = re.sub(r'<[^>]+>', '', cdata).strip()
            # Matches: "10 ans : Garçons : 34 inscrits (champ limité à 40 joueurs)"
            if re.search(r'inscrits?.*champ', clean, re.I):
                entry = unescape(clean)
                if entry not in categories:
                    categories.append(entry)

        # Adult total: I3 PROP "(82 participants / 92)"
        if not total_info:
            props = re.findall(r'<PROP NUM="3">(.*?)</PROP>', body, re.DOTALL)
            for prop in props:
                m = re.search(r'\((\d+)\s+participants?\s*/\s*(\d+)\)', prop)
                if m:
                    inscrits, max_places = m.group(1), m.group(2)
                    total_info = f"{inscrits} inscrits / {max_places} places"
                m2 = re.search(r'\((\d+)\s+équipes?\s+participantes?\s*/(\d+)\)', prop)
                if m2:
                    inscrits, max_places = m2.group(1), m2.group(2)
                    total_info = f"{inscrits} équipes / {max_places} max"

    if categories:
        return "\n".join(f"  • {c}" for c in categories)
    if total_info:
        return f"  • {total_info}"
    return ""


def fetch_data(new_names: list[str]) -> tuple[list[dict] | None, dict[str, str]]:
    """
    Fetches tournament list + inscription details for tournaments in new_names.
    Returns (tournaments, inscriptions_map) where inscriptions_map is nom → formatted string.
    """
    from playwright.sync_api import sync_playwright

    ajax_all: list[str] = []
    ajax_current: list[str] = []
    collecting_for: str | None = None

    def on_response(resp):
        try:
            if "PAGE_ACCUEIL" in resp.url and "WD_ACTION_=IMAGE" not in resp.url:
                body = resp.body()
                if len(body) > 100:
                    decoded = body.decode("utf-8", errors="replace")
                    ajax_all.append(decoded)
                    if collecting_for is not None:
                        ajax_current.append(decoded)
        except Exception:
            pass

    inscriptions: dict[str, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "Accept-Language": "fr-FR,fr;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        page.on("response", on_response)

        try:
            resp = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            if resp and resp.status == 503:
                print("Site indisponible (503).")
                return None, {}

            page.wait_for_timeout(6000)

            # Scroll pour charger tous les tournois via AJAX
            page.mouse.move(640, 200)
            for _ in range(5):
                page.mouse.wheel(0, -500)
                page.wait_for_timeout(300)
            page.wait_for_timeout(2000)
            for _ in range(40):
                page.mouse.wheel(0, -500)
                page.wait_for_timeout(150)
            page.wait_for_timeout(2000)
            for _ in range(10):
                page.mouse.wheel(0, 500)
                page.wait_for_timeout(150)
            for _ in range(40):
                page.mouse.wheel(0, -500)
                page.wait_for_timeout(150)
            page.wait_for_timeout(3000)

            html = page.content()

            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(html)

            combined_raw = "\n".join(ajax_all) + "\n" + html
            tournaments = _parse_tournaments_raw(combined_raw)

            # Récupérer les inscriptions pour chaque nouveau tournoi
            for nom in new_names:
                collecting_for = nom
                ajax_current.clear()

                try:
                    target = page.get_by_text(nom, exact=False).first
                    target.click(timeout=5000)
                    page.wait_for_timeout(1500)

                    inscr_tab = page.query_selector('text=Inscriptions')
                    if inscr_tab:
                        inscr_tab.click()
                        page.wait_for_timeout(3000)

                    result = _parse_inscriptions(list(ajax_current))
                    if result:
                        inscriptions[nom] = result
                        print(f"  Inscriptions {nom}: ok")
                except Exception as e:
                    print(f"  Inscriptions {nom}: erreur ({e})")
                finally:
                    collecting_for = None

        finally:
            browser.close()

    return tournaments, inscriptions


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
            f, indent=2, ensure_ascii=False,
        )


def make_key(t: dict) -> str:
    return f"{t['nom']}|{t['debut']}|{t['club']}"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data.get('description', data)}")


def main():
    import time
    from datetime import date

    known = load_state()

    # Premier run sans inscriptions pour identifier les nouveaux rapidement
    tournaments, inscriptions = fetch_data(new_names=[])

    if tournaments is None:
        print("Erreur temporaire — état non modifié.")
        sys.exit(0)

    if len(tournaments) < 10:
        print(f"Seulement {len(tournaments)} tournois — nouvelle tentative dans 10s...")
        time.sleep(10)
        tournaments, _ = fetch_data(new_names=[])
        if not tournaments or len(tournaments) < 10:
            print("Retry insuffisant.")
            sys.exit(0)

    today = datetime.now(timezone.utc).date()

    def parse_date(d: str):
        try:
            j, m, y = d.split("-")
            return (int(y), int(m), int(j))
        except Exception:
            return (9999, 99, 99)

    def is_open(t: dict) -> bool:
        y, m, j = parse_date(t["inscription_avant"])
        try:
            return date(y, m, j) >= today
        except Exception:
            return False

    new_ones = [t for t in tournaments if make_key(t) not in known]
    new_ones.sort(key=lambda t: 0 if is_open(t) else 1)

    # Si nouveaux tournois ouverts → récupérer inscriptions en un seul browser pass
    open_new_names = [t["nom"] for t in new_ones if is_open(t)]
    if open_new_names:
        _, inscriptions = fetch_data(new_names=open_new_names)

    for t in new_ones:
        voyant = "🟢" if is_open(t) else "🔴"
        inscr_block = inscriptions.get(t["nom"], "")
        inscr_section = f"\n📊 Inscriptions :\n{inscr_block}\n" if inscr_block else "\n"

        msg = (
            f"🎾 <b>Nouveau tournoi FRMT !</b> {voyant}\n\n"
            f"<b>{t['nom']}</b>\n"
            f"📍 {t['ville']} — {t['club']}\n"
            f"📅 Du {t['debut']} au {t['fin']}\n"
            f"⏰ Inscription avant : {t['inscription_avant']}"
            f"{inscr_section}"
            f"👉 <a href=\"{URL}\">Voir le tableau</a>"
        )
        send_telegram(msg)
        print(f"Notifié : {t['nom']}")

    updated = known | {make_key(t) for t in tournaments}
    save_state(updated)
    print(f"{len(tournaments)} tournois, {len(new_ones)} nouveau(x).")


if __name__ == "__main__":
    main()
