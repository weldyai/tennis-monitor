import scraper


def row(nom, club, debut, fin, ville, insc):
    return (
        f"<COLONNE>{nom}</COLONNE><COLONNE>{club}</COLONNE>"
        f"<COLONNE>{debut}</COLONNE><COLONNE>{fin}</COLONNE>"
        f"<COLONNE>{ville}</COLONNE><COLONNE>{insc}</COLONNE>"
    )


def test_same_name_different_edition_kept():
    """Régression : dédup par nom seul écrasait les nouvelles éditions."""
    raw = row("Open Rabat", "RTC", "01-03-2026", "05-03-2026", "Rabat", "20-02-2026") + \
          row("Open Rabat", "RTC", "01-03-2027", "05-03-2027", "Rabat", "20-02-2027")
    ts = scraper._parse_tournaments_raw(raw)
    assert [t["debut"] for t in ts] == ["01-03-2026", "01-03-2027"]
    assert len({scraper.make_key(t) for t in ts}) == 2


def test_same_name_different_club_kept():
    raw = row("Open", "A", "01-03-2026", "05-03-2026", "Rabat", "20-02-2026") + \
          row("Open", "B", "01-03-2026", "05-03-2026", "Fès", "20-02-2026")
    assert len(scraper._parse_tournaments_raw(raw)) == 2


def test_exact_duplicate_removed_and_order_preserved():
    a = row("Zeta", "C1", "01-03-2026", "05-03-2026", "Rabat", "20-02-2026")
    b = row("Alpha", "C2", "02-03-2026", "06-03-2026", "Fès", "21-02-2026")
    ts = scraper._parse_tournaments_raw(a + b + a)
    assert [t["nom"] for t in ts] == ["Zeta", "Alpha"]  # pas de tri client


def test_make_key_format():
    t = {"nom": "N", "debut": "01-03-2026", "club": "C"}
    assert scraper.make_key(t) == "N|01-03-2026|C"
