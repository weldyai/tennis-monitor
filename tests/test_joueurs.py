import scraper

PDF = """Les joueuses ci-dessous sont convoquées ultérieurement pour le tirage au sort
BENNANI     ABLA        COC         174
AMDOUY      SARA        OCC         176

36     631 BENOMAR       WALID        OCC    DIM 11H00                       Umpire    0
37     711 KHARCHAFI     ADIL         USM/TCC0
38     675 AMDOUY        SAMY         OCC    DIM 12H15                0
39         Q11                               0                        DIM 16H00
"""


def test_samy_adversaire_et_horaire():
    ms = {m["joueur"]: m for m in scraper._find_player_matches(PDF)}
    assert ms["Samy AMDOUY"]["adversaire"] == "KHARCHAFI ADIL USM/TCC"
    assert ms["Samy AMDOUY"]["horaire"] == "DIM 12H15"


def test_sara_liste_avec_contexte():
    m = {m["joueur"]: m for m in scraper._find_player_matches(PDF)}["Sara AMDOUY"]
    assert m["adversaire"] == "" and "ultérieurement" in m["contexte"]


def test_autres_joueurs_ignores():
    assert scraper._find_player_matches("12 500 DUPONT  JEAN  TCR  SAM 9H00") == []


def test_extract_pdf_urls_gview():
    body = "https://docs.google.com/gview?embedded=true&amp;url=https://info2.frmt.ma/DOCS//1/a.pdf "
    assert scraper._extract_pdf_urls([body]) == ["https://info2.frmt.ma/DOCS//1/a.pdf"]


def test_notif_joueur_une_seule_fois(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_telegram", lambda m, reply_markup=None: sent.append(m))
    monkeypatch.setattr(scraper, "_pdf_to_text", lambda u: PDF)
    monkeypatch.setattr(scraper, "fetch_detail", lambda nom, tabs: {"convocation": True, "convocation_pdfs": ["u.pdf"]})
    st = {"tracked": {"K": {"nom": "T", "ville": "V", "club": "C", "debut": "01-01-2099",
                            "fin": "02-01-2099", "convocation_notified": True}}}
    scraper.check_tracked_tournaments(st)
    scraper.check_tracked_tournaments(st)
    assert sum("🎾" in m for m in sent) == 2


def test_tour_suivant_nom_seul_genre_deduit():
    t = "LANORIA  TQ GRADE 4 DAMES\n 1  300 DUPONT  ANNE  TCR  AMDOUY      SAM 16H30\n"
    m = scraper._find_player_matches(t)[0]
    assert m["joueur"] == "Sara AMDOUY" and m["horaire"] == "SAM 16H30"


def test_cle_stable_si_score_change():
    a = {"joueur": "J", "ligne": "38 A 0", "adversaire": "X", "horaire": "DIM 9H00"}
    b = {**a, "ligne": "38 A 6/1 6/2"}
    assert scraper._match_key("u", a) == scraper._match_key("u", b)


def _lanoria():
    import os
    p = os.path.join(os.path.dirname(__file__), "fixtures", "lanoria_hommes.txt")
    return open(p, encoding="utf-8").read().splitlines()


def _put(line, off, txt):
    line = line.ljust(off + len(txt) + 1)
    return line[:off] + txt + line[off + len(txt):]


def _samy(lines):
    ms = [m for m in scraper._find_player_matches("\n".join(lines)) if m["joueur"] == "Samy AMDOUY"]
    assert len(ms) == 1
    return ms[0]


def _row(lines, needle):
    return next(n for n, l in enumerate(lines) if needle in l)


def test_tableau_reel_premier_tour():
    m = _samy(_lanoria())
    assert (m["statut"], m["horaire"], m["adversaire"]) == ("1er tour", "DIM 12H15", "KHARCHAFI ADIL USM/TCC")


def test_tableau_deuxieme_tour_adversaire_inconnu():
    L = _lanoria(); i = _row(L, "675 AMDOUY")
    L[i] = _put(L[i], 57, "AMDOUY")
    m = _samy(L)
    assert m["statut"] == "2e tour" and m["horaire"] == "DIM 16H00"
    assert m["adversaire"].startswith("vainqueur de Q11 / TIMOUMI HAMZA")


def test_tableau_deuxieme_tour_adversaire_connu():
    L = _lanoria(); i = _row(L, "675 AMDOUY")
    L[i] = _put(L[i], 57, "AMDOUY"); L[i + 2] = _put(L[i + 2], 57, "TIMOUMI")
    m = _samy(L)
    assert m["statut"] == "2e tour" and m["adversaire"].startswith("TIMOUMI HAMZA")


def test_tableau_elimine_au_premier_tour():
    L = _lanoria(); i = _row(L, "675 AMDOUY")
    L[i - 1] = _put(L[i - 1], 57, "KHARCHAFI")
    m = _samy(L)
    assert m["statut"].startswith("Éliminé") and m["adversaire"].startswith("KHARCHAFI")


def test_tableau_troisieme_tour():
    L = _lanoria(); i = _row(L, "675 AMDOUY")
    L[i] = _put(L[i], 57, "AMDOUY"); L[i] = _put(L[i], 73, "AMDOUY")
    assert _samy(L)["statut"] == "3e tour"


def test_notification_changement_tour(monkeypatch):
    sent = []
    monkeypatch.setattr(scraper, "send_telegram", lambda m, reply_markup=None: sent.append(m))
    L = _lanoria(); i = _row(L, "675 AMDOUY")
    versions = ["\n".join(L)]
    L[i] = _put(L[i], 57, "AMDOUY"); versions.append("\n".join(L))
    cur = {"t": versions[0]}
    monkeypatch.setattr(scraper, "_pdf_to_text", lambda u: cur["t"])
    monkeypatch.setattr(scraper, "fetch_detail", lambda nom, tabs: {"convocation": True, "convocation_pdfs": ["u.pdf"]})
    st = {"tracked": {"K": {"nom": "T", "ville": "V", "club": "C", "debut": "01-01-2099",
                            "fin": "02-01-2099", "convocation_notified": True}}}
    scraper.check_tracked_tournaments(st)
    n1 = sum("Samy" in m for m in sent)
    scraper.check_tracked_tournaments(st)
    assert sum("Samy" in m for m in sent) == n1
    cur["t"] = versions[1]
    scraper.check_tracked_tournaments(st)
    assert sum("Samy" in m for m in sent) == n1 + 1
    assert any("2e tour" in m and "DIM 16H00" in m for m in sent)


def _tscm():
    import os
    p = os.path.join(os.path.dirname(__file__), "fixtures", "tscm_dames_qualifs.txt")
    return open(p, encoding="utf-8").read()


def _sara(txt):
    ms = [m for m in scraper._find_player_matches(txt) if m["joueur"] == "Sara AMDOUY"]
    assert len(ms) == 1
    return ms[0]


def test_tscm_reel_sara_eliminee_des_qualifs():
    m = _sara(_tscm())
    assert m["statut"] == "Éliminé(e) des qualifications"
    assert m["adversaire"].startswith("ZERROUR SORAYA")


def test_tscm_reel_sara_prochain_match_sans_marqueur_q():
    import re
    txt = re.sub(r"[ ]+Q[ ]*$", "", _tscm(), flags=re.M)
    m = _sara(txt)
    assert m["statut"] == "2e tour" and m["adversaire"].startswith("ZERROUR SORAYA")
    assert m["horaire"].endswith("11H30")


def test_tscm_reel_notification_eliminee():
    m = _sara(_tscm())
    msg = scraper._format_player_match({"nom": "T", "ville": "V", "club": "C"}, "u", m)
    assert "Éliminé(e) des qualifications" in msg and "ZERROUR" in msg
