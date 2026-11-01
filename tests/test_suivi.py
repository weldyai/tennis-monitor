from datetime import datetime, timedelta, timezone

import scraper
from test_dedup import row


def test_row_without_inscription_date_is_kept():
    raw = (
        "<COLONNE>Open X</COLONNE><COLONNE>RTC</COLONNE>"
        "<COLONNE>01-03-2026</COLONNE><COLONNE>05-03-2026</COLONNE><COLONNE>Rabat</COLONNE>"
    )
    ts = scraper._parse_tournaments_raw(raw)
    assert [(t["nom"], t["inscription_avant"]) for t in ts] == [("Open X", "")]
    assert scraper._PARSE_META["unparsed"] == []


def test_unparsed_row_is_reported():
    raw = row("Ok", "C", "01-03-2026", "05-03-2026", "Rabat", "20-02-2026") + (
        "<COLONNE>Casse</COLONNE><COLONNE>C</COLONNE>"
        "<COLONNE>02-03-2026</COLONNE><COLONNE>06-03-2026</COLONNE>"
    )
    ts = scraper._parse_tournaments_raw(raw)
    assert [t["nom"] for t in ts] == ["Ok"]
    assert scraper._PARSE_META["unparsed"] == ["Casse"]


def _state_with_meta():
    return {
        "known": [], "tracked": {}, "telegram_offset": 0,
        "id_map": {"abc12345": "T|01-03-2026|C"},
        "id_map_meta": {"abc12345": {"nom": "T", "ville": "V", "club": "C", "debut": "01-03-2026",
                                      "fin": "05-03-2026", "inscription_avant": "20-02-2026",
                                      "message_id": 7}},
    }


def _fake_updates(monkeypatch, data):
    calls = {"answered": [], "edited": []}
    monkeypatch.setattr(scraper, "poll_updates",
                        lambda offset: [{"update_id": 10, "callback_query": {"id": "cq1", "data": data}}])
    monkeypatch.setattr(scraper, "answer_callback", lambda i: calls["answered"].append(i))
    monkeypatch.setattr(scraper, "edit_message_reply_markup",
                        lambda mid, rm=None: calls["edited"].append((mid, rm)))
    return calls


def test_click_suivre_enregistre_le_suivi(monkeypatch):
    calls = _fake_updates(monkeypatch, "track:abc12345")
    state = _state_with_meta()
    assert scraper.process_callbacks(state) is True
    assert list(state["tracked"]) == ["T|01-03-2026|C"]
    assert state["tracked"]["T|01-03-2026|C"]["convocation_notified"] is False
    assert state["telegram_offset"] == 11
    assert calls["answered"] == ["cq1"] and calls["edited"][0][0] == 7


def test_click_suivre_sans_meta_ne_plante_pas(monkeypatch):
    _fake_updates(monkeypatch, "track:inconnu")
    state = _state_with_meta()
    scraper.process_callbacks(state)
    assert state["tracked"] == {} and state["telegram_offset"] == 11


def test_convocation_notifiee_une_seule_fois(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_telegram", lambda m, reply_markup=None: sent.append(m))
    monkeypatch.setattr(scraper, "fetch_detail",
                        lambda nom, tabs: {"inscriptions": "", "convocation": "Convocations" in tabs})
    future = (datetime.now() + timedelta(days=5)).strftime("%d-%m-%Y")
    state = {"tracked": {"K": {"nom": "T", "ville": "V", "club": "C", "debut": future, "fin": future,
                               "last_inscriptions": "", "convocation_notified": False}}}
    assert scraper.check_tracked_tournaments(state) is True
    assert sum("Convocation disponible" in m for m in sent) == 1
    assert state["tracked"]["K"]["convocation_notified"] is True
    scraper.check_tracked_tournaments(state)
    assert sum("Convocation disponible" in m for m in sent) == 1


def test_lag_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_alert_throttled",
                        lambda state, key, msg, cooldown_hours=24: sent.append(key) or True)
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat()
    scraper._check_scrape_lag({"last_scrape_at": recent})
    scraper._check_scrape_lag({})
    assert sent == []
    state = {"last_scrape_at": old}
    scraper._check_scrape_lag(state)
    assert sent == ["cron_lag"] and state["last_scrape_at"] > old
