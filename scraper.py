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


def _is_finished(t: dict) -> bool:
    d = parse_date(t.get("fin", ""))
    return d is not None and d < date.today()


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


def send_alert_throttled(state: dict, key: str, message: str, cooldown_hours: int = 24) -> bool:
    """Envoie une alerte Telegram au plus une fois par `cooldown_hours` pour une clé donnée."""
    alerts = state.setdefault("alerts", {})
    now = datetime.now(timezone.utc)
    last = alerts.get(key)
    if last:
        try:
            if (now - datetime.fromisoformat(last)).total_seconds() < cooldown_hours * 3600:
                return False
        except Exception:
            pass
    try:
        send_telegram(message)
    except Exception as e:
        print(f"  alerte '{key}' non envoyée: {e}")
        return False
    alerts[key] = now.isoformat()
    return True


def edit_message_reply_markup(message_id: int, reply_markup: dict | None = None):
    _tg("editMessageReplyMarkup", chat_id=CHAT_ID, message_id=message_id,
        reply_markup=reply_markup or {})


def answer_callback(callback_query_id: str):
    _tg("answerCallbackQuery", callback_query_id=callback_query_id)


def poll_updates(offset: int) -> list[dict]:
    try:
        data = _tg("getUpdates", offset=offset, timeout=0,
                   allowed_updates=["message", "channel_post", "callback_query"])
        return data.get("result", [])
    except RuntimeError as e:
        if "Conflict" in str(e):
            print("getUpdates conflict — ignoré.")
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

_PARSE_META: dict = {"unparsed": []}
_LOOSE_ROW = re.compile(
    r"<COLONNE>([^<]{1,150})</COLONNE>\s*<COLONNE>([^<]*)</COLONNE>"
    r"(?:<COLONNE[^/]*/?>)*\s*<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"
    r"\s*<COLONNE>\d{2}-\d{2}-\d{4}</COLONNE>",
    re.DOTALL,
)


def _find_unparsed(decoded: str, seen: set) -> list[str]:
    """Lignes qui ressemblent à un tournoi (nom, club, deux dates) mais absentes du résultat."""
    from html import unescape
    missed = []
    for m in _LOOSE_ROW.finditer(decoded):
        key = (unescape(m.group(1).strip()), m.group(3), unescape(m.group(2).strip()))
        if (key[0], key[1], key[2]) not in seen and key[0] not in missed:
            missed.append(key[0])
    return missed


def _parse_tournaments_raw(raw_text: str) -> list[dict]:
    from html import unescape
    decoded = _decode_hex(raw_text)
    pattern = re.compile(
        r"<COLONNE>([^<]{1,150})</COLONNE>"
        r"<COLONNE>([^<]*)</COLONNE>"
        r"(?:<COLONNE[^/]*/?>)*"
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"
        r"<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>"
        r"<COLONNE>([^<]*)</COLONNE>"
        r"(?:<COLONNE>(\d{2}-\d{2}-\d{4})</COLONNE>)?",
        re.DOTALL,
    )
    tournaments, seen = [], set()
    for m in pattern.finditer(decoded):
        nom = unescape(m.group(1).strip())
        club = unescape(m.group(2).strip())
        debut = m.group(3)
        # Dédup par (nom, début, club) : un même nom de tournoi revient
        # chaque année avec une nouvelle édition (date différente) — dédupliquer
        # par nom seul écraserait silencieusement les nouvelles éditions.
        dedup_key = (nom, debut, club)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        tournaments.append({
            "nom": nom,
            "club": club,
            "debut": debut,
            "fin": m.group(4),
            "ville": unescape(m.group(5).strip()),
            "inscription_avant": m.group(6) or "",
        })
    _PARSE_META["unparsed"] = _find_unparsed(decoded, seen)
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


_CONVOC_PENDING = re.compile(r"ult[ée]rieurement", re.I)
_CONVOC_PUBLISHED = re.compile(
    r"convoc[^<]{0,200}\.pdf|\.pdf[^<]{0,200}convoc"
    r"|t[ée]l[ée]charger[^<]{0,100}convoc|convocation[^<]{0,100}disponible",
    re.I,
)
_PDF_CONTEXT = re.compile(r"[^<>\"']{0,120}\.pdf", re.I)


def _check_convocation(ajax_bodies: list[str]) -> bool:
    """True si la convocation est publiée. Les bodies viennent du seul onglet Convocations :
    tout PDF y vaut publication, sauf un règlement. Un body « ultérieurement » est ignoré
    sans masquer un body publié qui le suivrait."""
    for body in ajax_bodies:
        if _CONVOC_PENDING.search(body):
            continue
        if _CONVOC_PUBLISHED.search(body):
            return True
        if any("glement" not in m.group(0).lower() for m in _PDF_CONTEXT.finditer(body)):
            return True
    return False


# ─── Scraping ────────────────────────────────────────────────────────────────

def _scroll_all_until_stable(page, ajax_all: list[str], max_rounds: int = 20, stable_needed: int = 3) -> int:
    """Scroll window + inner containers until tournament count stabilizes. Returns final count."""
    _JS_SCROLL = """
        () => {
            window.scrollTo(0, document.body.scrollHeight);
            Array.from(document.querySelectorAll('*'))
                .filter(el => {
                    const s = getComputedStyle(el);
                    return el.scrollHeight > el.clientHeight + 50 &&
                           (s.overflow === 'auto' || s.overflow === 'scroll' ||
                            s.overflowY === 'auto' || s.overflowY === 'scroll');
                })
                .forEach(el => { el.scrollTop = el.scrollHeight; });
        }
    """
    prev_count = 0
    stable_rounds = 0
    for round_num in range(max_rounds):
        for _ in range(30):
            page.mouse.wheel(0, -500)
            page.wait_for_timeout(100)
        try:
            page.evaluate(_JS_SCROLL)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        current_count = len(_parse_tournaments_raw("\n".join(ajax_all)))
        print(f"  scroll round {round_num + 1}: {current_count} tournois")
        if current_count == prev_count:
            stable_rounds += 1
            if stable_rounds >= stable_needed:
                break
        else:
            stable_rounds = 0
            prev_count = current_count
    return prev_count


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
        _scroll_all_until_stable(page, ajax_all)
        page.wait_for_timeout(2000)
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
    pw, browser, page, ajax_all, ajax_current, set_collecting = _make_browser_session()
    results: dict[str, str | bool] = {}
    try:
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        if resp and resp.status == 503:
            return results
        page.wait_for_timeout(5000)
        page.mouse.move(640, 200)

        # Scroll incrémental : le virtual scroll WebDev ne rend dans le DOM
        # que les éléments visibles — on scroll par petits pas et on vérifie
        # après chaque pas si l'élément apparaît dans le DOM.
        target = page.get_by_text(nom, exact=False)
        found = False
        for _ in range(400):
            if target.count() > 0:
                try:
                    target.first.scroll_into_view_if_needed(timeout=3000)
                    target.first.click(timeout=5000)
                    found = True
                    break
                except Exception:
                    pass
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(200)

        if not found:
            print(f"  fetch_detail({nom}): non trouvé après scroll complet")
            results["_missing"] = "tournoi"
            return results
        page.wait_for_timeout(1500)

        for tab_label in tabs:
            tab = page.query_selector(f'text={tab_label}')
            if not tab:
                results["_missing"] = (str(results.get("_missing", "")) + f" {tab_label}").strip()
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
    """Lit les callbacks Telegram (boutons Suivre/Passer). Retourne True si state modifié."""
    offset = state.get("telegram_offset", 0)
    updates = poll_updates(offset)
    if not updates:
        return False

    modified = False
    id_map = state.get("id_map", {})
    id_map_meta = state.get("id_map_meta", {})

    for upd in updates:
        new_offset = upd["update_id"] + 1
        if new_offset > offset:
            offset = new_offset
            modified = True

        cb = upd.get("callback_query")
        if not cb:
            continue

        try:
            answer_callback(cb["id"])
        except Exception:
            pass

        data = cb.get("data", "")

        if data.startswith("track:"):
            sid_cb = data[6:]
            key = id_map.get(sid_cb)
            meta = id_map_meta.get(sid_cb)
            if key and meta and key not in state.get("tracked", {}):
                state.setdefault("tracked", {})[key] = {
                    "nom": meta["nom"], "ville": meta.get("ville", ""),
                    "club": meta.get("club", ""), "debut": meta.get("debut", ""),
                    "fin": meta.get("fin", ""), "inscription_avant": meta.get("inscription_avant", ""),
                    "last_inscriptions": "", "convocation_notified": False,
                }
                print(f"Tracking activé: {key}")
                modified = True
            if meta and meta.get("message_id"):
                try:
                    edit_message_reply_markup(meta["message_id"],
                        {"inline_keyboard": [[{"text": "✅ Suivi", "callback_data": "noop"}]]})
                except Exception:
                    pass

        elif data.startswith("pass:"):
            sid_cb = data[5:]
            meta = id_map_meta.get(sid_cb)
            if meta and meta.get("message_id"):
                try:
                    edit_message_reply_markup(meta["message_id"], {})
                except Exception:
                    pass

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

        # Auto-diagnostic : libellé d'onglet / tournoi introuvable (UI changée)
        if detail.get("_missing"):
            send_alert_throttled(
                state, f"detail_missing:{short_id(key)}",
                f"⚠️ <b>Suivi cassé</b>\n\n<b>{nom}</b> : élément introuvable "
                f"({detail['_missing']}). Le site a peut-être changé de libellés.",
                cooldown_hours=24,
            )
            modified = True

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
    state = load_state()

    # 1. Traiter les callbacks Telegram (boutons Suivre/Passer)
    cb_modified = process_callbacks(state)
    if cb_modified:
        save_state(state)

    if "--callbacks-only" in sys.argv:
        return

    try:
        _run_scrape(state, cb_modified)
    except Exception:
        import traceback
        send_alert_throttled(
            state, "crash",
            f"🚨 <b>Tennis Monitor en panne</b>\n\n<code>{traceback.format_exc()[-1500:]}</code>",
            cooldown_hours=2,
        )
        save_state(state)
        raise


def _check_scrape_lag(state: dict):
    """Auto-diagnostic : écart anormal entre deux scrapes (cron GitHub throttlé)."""
    now = datetime.now(timezone.utc)
    last = state.get("last_scrape_at")
    state["last_scrape_at"] = now.isoformat()
    if not last:
        return
    try:
        gap_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
    except Exception:
        return
    if gap_h >= 2:
        send_alert_throttled(
            state, "cron_lag",
            f"⏱ <b>Scrape en retard</b>\n\n{gap_h:.1f} h depuis le scrape précédent (attendu : 30 min).\n"
            "Cause probable : GitHub retarde les crons sous charge (pire aux minutes :00/:30).\n"
            "Correction : déclencheur externe (cron-job.org → workflow_dispatch) ; "
            "tant que ce n'est pas en place, les nouveaux tournois et les clics 🔔 Suivre sont traités avec ce retard.",
            cooldown_hours=24,
        )


def _run_scrape(state: dict, cb_modified: bool):
    import time

    _check_scrape_lag(state)

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
        if tournaments is None:
            print("Site indisponible au retry — état non modifié.")
            if cb_modified:
                save_state(state)
            sys.exit(0)
        if not tournaments:
            send_alert_throttled(
                state, "parse_empty",
                "🚨 <b>Aucun tournoi parsé</b>\n\nLe site répond mais le parsing renvoie 0 "
                "résultat après retry (structure <code>&lt;COLONNE&gt;</code> changée ?).",
                cooldown_hours=6,
            )
            save_state(state)
            sys.exit(1)

    unparsed = _PARSE_META.get("unparsed") or []
    if unparsed:
        send_alert_throttled(
            state, "parse_gap",
            f"⚠️ <b>{len(unparsed)} ligne(s) du site non parsée(s)</b>\n\n"
            + "\n".join(f"• {n}" for n in unparsed[:10])
            + "\n\nCause probable : colonnes de la ligne changées. Le parsing a déjà été rendu tolérant "
            "sur la fin de ligne ; si l'alerte persiste, la structure <code>&lt;COLONNE&gt;</code> a changé.",
            cooldown_hours=12,
        )

    # Auto-diagnostic : chute anormale du nombre de tournois vs historique récent
    count_history = state.setdefault("count_history", [])
    if len(count_history) >= 5:
        avg = sum(count_history) / len(count_history)
        if avg > 0 and len(tournaments) < avg * 0.6:
            send_alert_throttled(
                state, "count_drop",
                f"⚠️ <b>Anomalie scraping</b>\n\n{len(tournaments)} tournois vus contre "
                f"{avg:.0f} en moyenne récemment.\nCause probable : le site FRMT a retiré des "
                f"tournois passés (normal) ou le scroll/parsing a cassé (alerte parse_gap si des lignes "
                f"sont ignorées).\nCorrection : comparer avec le site ; si le site en montre plus, relancer /check.",
                cooldown_hours=12,
            )
    count_history.append(len(tournaments))
    state["count_history"] = count_history[-20:]

    known = set(state.get("known", []))
    new_ones = [t for t in tournaments if make_key(t) not in known]
    # Ne notifier que les tournois pas encore terminés
    to_notify = [t for t in new_ones if not _is_finished(t)]
    to_notify.sort(key=lambda t: 0 if is_open(t) else 1)

    # Auto-diagnostic : aucun nouveau tournoi détecté depuis trop longtemps —
    # aurait dû alerter dès le début du bug de dédup par nom seul (fix du 2026-08-13).
    if new_ones:
        state["last_new_tournament_at"] = datetime.now(timezone.utc).isoformat()
    else:
        last_new = state.get("last_new_tournament_at")
        if last_new is None:
            state["last_new_tournament_at"] = datetime.now(timezone.utc).isoformat()
        else:
            try:
                days = (datetime.now(timezone.utc) - datetime.fromisoformat(last_new)).days
            except Exception:
                days = 0
            if days >= 15:
                send_alert_throttled(
                    state, "stagnation",
                    f"⚠️ <b>Aucun nouveau tournoi détecté depuis {days} jours</b>\n\n"
                    f"Cause probable : creux de saison, ou scrapes retardés (voir alerte cron_lag), "
                    f"ou parsing cassé (voir alerte parse_gap).\nCorrection : /check puis comparer avec le site.",
                    cooldown_hours=48,
                )

    # 3. Notifier les nouveaux tournois avec boutons Suivre/Passer
    for t in to_notify:
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
            f"👉 <a href=\"{URL}\">Voir le tableau</a>"
        )

        reply_markup = {"inline_keyboard": [[
            {"text": "🔔 Suivre", "callback_data": f"track:{sid}"},
            {"text": "⏭ Passer", "callback_data": f"pass:{sid}"},
        ]]}
        msg_id = send_telegram(msg, reply_markup=reply_markup)
        print(f"Notifié : {t['nom']} (msg_id={msg_id})")

        # Stocker le mapping sid → key + meta (avec message_id pour édition)
        state.setdefault("id_map", {})[sid] = key
        state.setdefault("id_map_meta", {})[sid] = {
            "nom": t["nom"], "ville": t["ville"], "club": t["club"],
            "debut": t["debut"], "fin": t["fin"],
            "inscription_avant": t["inscription_avant"],
            "message_id": msg_id,
        }

    state["known"] = list(known | {make_key(t) for t in tournaments})

    # 4. Vérifier les tournois trackés (inscriptions + convocations)
    track_modified = check_tracked_tournaments(state)

    # Auto-diagnostic : rien n'est suivi alors que des tournois sont ouverts —
    # on ne rate pas un nouveau tournoi, mais on peut rater son suivi si personne
    # ne clique jamais 🔔 Suivre.
    if not state.get("tracked") and any(is_open(t) and not _is_finished(t) for t in tournaments):
        send_alert_throttled(
            state, "tracked_empty",
            "ℹ️ <b>Aucun tournoi suivi</b> alors que des tournois sont ouverts.\n"
            "Clique 🔔 Suivre sur un message pour être notifié des inscriptions/convocation.\n"
            "Si tu as déjà cliqué : le clic est traité au prochain cron (retard possible, voir cron_lag).",
            cooldown_hours=24,
        )

    save_state(state)
    print(f"{len(tournaments)} tournois, {len(to_notify)} notifié(s) ({len(new_ones) - len(to_notify)} terminés ignorés).")


if __name__ == "__main__":
    main()
