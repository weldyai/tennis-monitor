import time

import pytest
import scraper


@pytest.mark.parametrize("bodies,expected", [
    ([], False),
    (["Convocations publiées ultérieurement"], False),
    (['<a href="convocation_open.pdf">x</a>'], True),
    (["Télécharger la convocation"], True),
    (["La convocation est disponible"], True),
    (['<a href="reglement.pdf">Règlement</a>'], False),
    (['<a href="liste_joueurs_J1.pdf">Liste</a>'], True),
    (['<a href="reglement.pdf">Règlement</a>', '<a href="tableau.pdf">T</a>'], True),
    (["à venir ultérieurement", '<a href="convoc.pdf">c</a>'], True),
    (["à venir ULTERIEUREMENT", "rien d'utile"], False),
])
def test_check_convocation(bodies, expected):
    assert scraper._check_convocation(bodies) is expected


@pytest.fixture
def run_env(monkeypatch):
    sent = []
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(scraper, "save_state", lambda s: None)
    monkeypatch.setattr(scraper, "send_alert_throttled",
                        lambda state, key, msg, cooldown_hours=24: sent.append(key) or True)

    def run(seq):
        it = iter(seq)
        monkeypatch.setattr(scraper, "fetch_tournament_list", lambda: next(it))
        with pytest.raises(SystemExit) as e:
            scraper._run_scrape({}, False)
        return e.value.code, list(sent)
    return run


def test_site_down_first_call(run_env):
    assert run_env([None]) == (0, [])


def test_site_down_at_retry_no_false_alert(run_env):
    assert run_env([[{"a": 1}], None]) == (0, [])


def test_empty_after_retry_alerts_and_fails(run_env):
    assert run_env([[{"a": 1}], []]) == (1, ["parse_empty"])


def test_alert_throttle(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_telegram", lambda m, reply_markup=None: sent.append(m))
    state = {}
    assert scraper.send_alert_throttled(state, "k", "m", cooldown_hours=6) is True
    assert scraper.send_alert_throttled(state, "k", "m", cooldown_hours=6) is False
    assert len(sent) == 1 and "k" in state["alerts"]


def test_detail_missing_alert_once_per_day(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_telegram", lambda m, reply_markup=None: sent.append(m))
    monkeypatch.setattr(scraper, "fetch_detail", lambda nom, tabs: {"_missing": "Convocations"})
    state = {"tracked": {"Open|01-01-2099|C": {"nom": "Open", "fin": "02-01-2099"}}}
    assert scraper.check_tracked_tournaments(state) is True
    scraper.check_tracked_tournaments(state)
    assert len(sent) == 1 and "Suivi cassé" in sent[0]
