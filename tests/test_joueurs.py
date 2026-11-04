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
