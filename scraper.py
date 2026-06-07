import hashlib
import json
import os
import re
import sys
import requests
from datetime import datetime, date, timezone

URL = "https://info.frmt.ma/FRMT_LIVE_WB27"
STATE_FILE = "state.json"
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


def make_key(t: dict) -> str:
    return f"{t['nom']}|{t['debut']}|{t['club']}"


def short_id(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()[:8]


def parse_date(d: str) -> date | None:
    try:
        j, m, y = d.split("-")
        return date(int(y), int(m), int(j))
    except Exception:
        return None


def is_open(t: dict) -> bool:
    d = parse_date(t["inscription_avant"])
    return d is not None and d >= date.today()


# ─── Telegram API ────────────────────────────────────────────────────────────

def _tg(method: str, **kwargs) -> dict:
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=kwargs,
        timeout=10,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} error: {data.get('description', data)}")
    return data


def send_telegram(message: str, reply_markup: dict | None = None) -> int:
    """Returns message_id."""
    params = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = reply_markup
    data = _tg("sendMessage", **params)
    return data["result"]["message_id"]


def edit_message_reply_markup(message_id: int, reply_markup: dict | None = None):
    _tg("editMessageReplyMarkup",
        chat_id=CHAT_ID,
        message_id=message_id,
        reply_markup=reply_markup or {})


def answer_callback(callback_query_id: str, text: str = ""):
    _tg("answerCallbackQuery", callback_query_id=callback_query_id, text=text)


def poll_updates(offset: int) -> list[dict]:
    try:
        data = _tg("getUpdates", offset=offset, timeout=0)
        return data.get("result", [])
    except RuntimeError as e:
        if "Conflict" in str(e):
            print("getUpdates conflict — ignoré ce run.")
            return []
        raise


# ─── State ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"known": [], "tracked": {}, "id_map": {}, "telegram_offset": 0}
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state: dict):
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ─── Parsing ─────────────────────────────────────────────────────────────────

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
    tournaments, seen = [], set()
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


def _parse_inscriptions(ajax_bodies: list[str]) -> str:
    from html import unescape
    categories, total_info = [], ""
    for body in ajax_bodies:
        cdatas = re.findall(r'<!\[CDATA\[(.*?)\]\]>', body, re.DOTALL)
        for cdata in cdatas:
            clean = re.sub(r'<[^>]+>', '', cdata).strip()
            if re.search(r'inscrits?.*champ', clean, re.I):
                entry = unescape(clean)
                if entry not in categories:
                    categories.append(entry)
        if not total_info:
            for prop in re.findall(r'<PROP NUM="3">(.*?)</PROP>', body, re.DOTALL):
                m = re.search(r'\((\d+)\s+participants?\s*/\s*(\d+)\)', prop)
                if m:
                    total_info = f"{m.group(1)} inscrits / {m.group(2)} places"
                m2 = re.search(r'\((\d+)\s+équipes?\s+participantes?\s*/(\d+)\)', prop)
                if m2:
                    total_info = f"{m2.group(1)} équipes / {m2.group(2)} max"
    if categories:
        return "\n".join(f"  • {c}" for c in categories)
    if total_info:
        return f"  • {total_info}"
    return ""


def _check_convocation(ajax_bodies: list[str]) -> bool:
    """Returns True if convocation is published (no longer pending)."""
    for body in ajax_bodies:
        if "ultérieurement" in body or "ulterieurement" in body.lower():
            return False
        # Convocation disponible = lien PDF ou contenu spécifique
        if re.search(r'convoc.*\.pdf|télécharger.*convoc|Convocation.*disponible', body, re.I):
            return True
    return False


# ─── Scraping ────────────────────────────────────────────────────────────────

def _make_browser_session():
    """Returns (playwright, browser, page, ajax_all, ajax_current, set_target)."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_extra_http_headers({
        "Accept-Language": "fr-FR,fr;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })

    ajax_all: list[str] = []
    ajax_current: list[str] = []
    _collecting = [False]

    def on_response(resp):
        try:
            if "PAGE_ACCUEIL" in resp.url and "WD_ACTION_=IMAGE" not in resp.url:
                body = resp.body()
                if len(body) > 100:
                    decoded = body.decode("utf-8", errors="replace")
                    ajax_all.append(decoded)
                    if _collecting[0]:
                        ajax_current.append(decoded)
        except Exception:
            pass

    page.on("response", on_response)

    def set_collecting(active: bool):
        _collecting[0] = active
        if active:
            ajax_current.clear()

    return pw, browser, page, ajax_all, ajax_current, set_collecting


def fetch_tournament_list() -> list[dict] | None:
    pw, browser, page, ajax_all, _, _ = _make_browser_session()
    try:
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        if resp and resp.status == 503:
            return None
        page.wait_for_timeout(6000)
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
        combined = "\n".join(ajax_all) + "\n" + html
        return _parse_tournaments_raw(combined)
    finally:
        browser.close()
        pw.stop()


def fetch_detail(nom: str, tabs: list[str]) -> dict[str, str | bool]:
    """
    Opens browser, loads main page, clicks on `nom`, then each tab in `tabs`.
    tabs: list of tab labels to click, e.g. ["Inscriptions", "Convocations"]
    Returns dict: tab_label -> parsed result
    """
    pw, browser, page, _, ajax_current, set_collecting = _make_browser_session()
    results: dict[str, str | bool] = {}
    try:
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        if resp and resp.status == 503:
            return results
        page.wait_for_timeout(5000)
        page.mouse.move(640, 200)
        for _ in range(15):
            page.mouse.wheel(0, -500)
            page.wait_for_timeout(150)
        page.wait_for_timeout(2000)

        target = page.get_by_text(nom, exact=False).first
        target.click(timeout=5000)
        page.wait_for_timeout(1500)

        for tab_label in tabs:
            tab = page.query_selector(f'text={tab_label}')
            if not tab:
                continue
            set_collecting(True)
            tab.click()
            page.wait_for_timeout(3000)
            set_collecting(False)
            bodies = list(ajax_current)

            if tab_label == "Inscriptions":
                results["inscriptions"] = _parse_inscriptions(bodies)
            elif tab_label == "Convocations":
                results["convocation"] = _check_convocation(bodies)
    except Exception as e:
        print(f"  fetch_detail({nom}): {e}")
    finally:
        browser.close()
        pw.stop()
    return results


# ─── Tracking logic ──────────────────────────────────────────────────────────

def process_callbacks(state: dict) -> bool:
    """
    Poll Telegram for messages starting with /track or /untrack.
    Supports: /track <nom_partiel>  and  /untrack <nom_partiel>
    Returns True if state was modified.
    """
    offset = state.get("telegram_offset", 0)
    updates = poll_updates(offset)
    if not updates:
        return False

    modified = False
    id_map = state.get("id_map", {})
    id_map_meta = state.get("id_map_meta", {})

    for upd in updates:
        offset = max(offset, upd["update_id"] + 1)
        msg = upd.get("message") or upd.get("channel_post")
        cb = upd.get("callback_query")

        # Support commandes texte /track et /untrack
        text = ""
        if msg:
            text = msg.get("text", "")
        elif cb:
            # Ancien système inline — gérer noop silencieusement
            try:
                answer_callback(cb["id"])
            except Exception:
                pass
            continue

        if not text.startswith("/track") and not text.startswith("/untrack"):
            continue

        parts = text.split(None, 1)
        cmd = parts[0].lower()
        query = parts[1].strip().upper() if len(parts) > 1 else ""

        # Chercher le tournoi dans id_map_meta
        match_key = None
        match_meta = None
        for sid, meta in id_map_meta.items():
            if query and query in meta.get("nom", "").upper():
                match_key = id_map.get(sid)
                match_meta = meta
                break

        if cmd == "/track":
            if not query:
                send_telegram("Usage: /track <nom_partiel>\nEx: /track STCO")
            elif not match_key:
                send_telegram(f"❌ Tournoi '{query}' non trouvé dans la liste courante.")
            elif match_key in state.get("tracked", {}):
                send_telegram(f"✅ {match_meta['nom']} est déjà suivi.")
            else:
                state.setdefault("tracked", {})[match_key] = {
                    "nom": match_meta["nom"],
                    "ville": match_meta.get("ville", ""),
                    "club": match_meta.get("club", ""),
                    "debut": match_meta.get("debut", ""),
                    "fin": match_meta.get("fin", ""),
                    "inscription_avant": match_meta.get("inscription_avant", ""),
                    "last_inscriptions": "",
                    "convocation_notified": False,
                }
                send_telegram(f"🔔 Tracking activé : {match_meta['nom']}")
                print(f"Tracking: {match_key}")
                modified = True

        elif cmd == "/untrack":
            if not query:
                send_telegram("Usage: /untrack <nom_partiel>")
            elif match_key and match_key in state.get("tracked", {}):
                del state["tracked"][match_key]
                send_telegram(f"🔕 Tracking désactivé : {match_meta['nom']}")
                modified = True
            else:
                send_telegram(f"❌ Tournoi '{query}' non trouvé dans les tournois suivis.")

    state["telegram_offset"] = offset
    return modified


def check_tracked_tournaments(state: dict) -> bool:
    """
    For each tracked tournament: check inscriptions diff + convocation.
    Sends notifications for changes. Returns True if state was modified.
    """
    tracked = state.get("tracked", {})
    if not tracked:
        return False

    today = date.today()
    modified = False
    keys_to_remove = []

    for key, info in tracked.items():
        fin = parse_date(info.get("fin", ""))
        if fin and fin < today:
            keys_to_remove.append(key)
            continue

        nom = info["nom"]
        print(f"Checking tracked: {nom}")
        tabs = ["Inscriptions"]
        if not info.get("convocation_notified"):
            tabs.append("Convocations")

        detail = fetch_detail(nom, tabs)

        # Inscriptions diff
        new_inscr = detail.get("inscriptions", "")
        if new_inscr and new_inscr != info.get("last_inscriptions", ""):
            prev = info.get("last_inscriptions", "")
            msg = (
                f"📊 <b>Mise à jour inscriptions</b>\n\n"
                f"<b>{nom}</b>\n"
                f"📍 {info.get('ville')} — {info.get('club')}\n"
                f"📅 Du {info.get('debut')} au {info.get('fin')}\n\n"
                f"{new_inscr}\n\n"
                f"👉 <a href=\"{URL}\">Voir le tableau</a>"
            )
            if prev:
                msg = msg.replace("Mise à jour inscriptions", "🔄 Changement inscriptions")
            send_telegram(msg)
            info["last_inscriptions"] = new_inscr
            modified = True

        # Convocation
        if not info.get("convocation_notified") and detail.get("convocation") is True:
            msg = (
                f"📋 <b>Convocation disponible !</b>\n\n"
                f"<b>{nom}</b>\n"
                f"📍 {info.get('ville')} — {info.get('club')}\n"
                f"📅 Du {info.get('debut')} au {info.get('fin')}\n\n"
                f"👉 <a href=\"{URL}\">Voir la convocation</a>"
            )
            send_telegram(msg)
            info["convocation_notified"] = True
            modified = True

    for key in keys_to_remove:
        print(f"Tournoi terminé, stop tracking: {key}")
        del tracked[key]
        modified = True

    return modified


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    import time

    state = load_state()

    # 1. Traiter les callbacks Telegram (boutons Suivre/Passer)
    cb_modified = process_callbacks(state)

    # 2. Récupérer la liste des tournois
    tournaments = fetch_tournament_list()

    if tournaments is None:
        print("Site indisponible — état non modifié.")
        if cb_modified:
            save_state(state)
        sys.exit(0)

    if len(tournaments) < 10:
        print(f"Seulement {len(tournaments)} tournois — retry dans 10s...")
        time.sleep(10)
        tournaments = fetch_tournament_list()
        if not tournaments:
            if cb_modified:
                save_state(state)
            sys.exit(0)

    known = set(state.get("known", []))
    new_ones = [t for t in tournaments if make_key(t) not in known]
    new_ones.sort(key=lambda t: 0 if is_open(t) else 1)

    # 3. Notifier les nouveaux tournois avec boutons Suivre/Passer
    for t in new_ones:
        key = make_key(t)
        sid = short_id(key)
        voyant = "🟢" if is_open(t) else "🔴"

        # Inscriptions si tournoi ouvert
        inscr_block = ""
        if is_open(t):
            detail = fetch_detail(t["nom"], ["Inscriptions"])
            inscr_block = detail.get("inscriptions", "")

        inscr_section = f"\n📊 Inscriptions :\n{inscr_block}\n" if inscr_block else "\n"

        msg = (
            f"🎾 <b>Nouveau tournoi FRMT !</b> {voyant}\n\n"
            f"<b>{t['nom']}</b>\n"
            f"📍 {t['ville']} — {t['club']}\n"
            f"📅 Du {t['debut']} au {t['fin']}\n"
            f"⏰ Inscription avant : {t['inscription_avant']}"
            f"{inscr_section}"
            f"👉 <a href=\"{URL}\">Voir le tableau</a>\n\n"
            f"<i>Pour suivre : /track {t['nom'].split()[-1] if t['nom'].split() else t['club']}</i>"
        )

        msg_id = send_telegram(msg)
        print(f"Notifié : {t['nom']} (msg_id={msg_id})")

        # Stocker le mapping sid → key + meta pour traiter le callback plus tard
        state.setdefault("id_map", {})[sid] = key
        state.setdefault("id_map_meta", {})[sid] = {
            "nom": t["nom"], "ville": t["ville"], "club": t["club"],
            "debut": t["debut"], "fin": t["fin"],
            "inscription_avant": t["inscription_avant"],
        }

    state["known"] = list(known | {make_key(t) for t in tournaments})

    # 4. Vérifier les tournois trackés (inscriptions + convocations)
    track_modified = check_tracked_tournaments(state)

    save_state(state)
    print(f"{len(tournaments)} tournois, {len(new_ones)} nouveau(x).")


if __name__ == "__main__":
    main()
