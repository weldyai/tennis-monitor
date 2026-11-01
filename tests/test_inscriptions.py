import os
import sys

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "test")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import scraper


def cdata(txt):
    return f"<![CDATA[{txt}]]>"


def prop3(txt):
    return f'<PROP NUM="3">{txt}</PROP>'


def test_empty_inputs():
    assert scraper._parse_inscriptions([]) == ""
    assert scraper._parse_inscriptions([""]) == ""
    assert scraper._parse_inscriptions(["<X>rien</X>"]) == ""


def test_category_cdata_extracted_and_html_stripped():
    body = cdata("<b>12 inscrits</b> en <i>Simple Messieurs</i> - champ. A")
    out = scraper._parse_inscriptions([body])
    assert out == "  • 12 inscrits en Simple Messieurs - champ. A"


def test_cdata_without_match_ignored():
    body = cdata("Règlement du tournoi") + cdata("3 inscrits champ")
    assert scraper._parse_inscriptions([body]) == "  • 3 inscrits champ"


def test_entities_unescaped():
    body = cdata("5 inscrits &amp; qualifiés champ")
    assert scraper._parse_inscriptions([body]) == "  • 5 inscrits & qualifiés champ"


def test_categories_deduped_and_order_preserved_across_bodies():
    b1 = cdata("2 inscrits champ B") + cdata("9 inscrits champ A")
    b2 = cdata("2 inscrits champ B") + cdata("1 inscrit champ C")
    out = scraper._parse_inscriptions([b1, b2])
    assert out.split("\n") == [
        "  • 2 inscrits champ B",
        "  • 9 inscrits champ A",
        "  • 1 inscrit champ C",
    ]


def test_total_participants_fallback():
    body = prop3("Open (24 participants / 32)")
    assert scraper._parse_inscriptions([body]) == "  • 24 inscrits / 32 places"


def test_total_teams_fallback():
    body = prop3("Interclubs (8 équipes participantes /12)")
    assert scraper._parse_inscriptions([body]) == "  • 8 équipes / 12 max"


def test_categories_take_priority_over_total():
    body = cdata("4 inscrits champ") + prop3("(24 participants / 32)")
    assert scraper._parse_inscriptions([body]) == "  • 4 inscrits champ"


def test_total_only_from_first_body_with_match():
    b1 = prop3("(10 participants / 16)")
    b2 = prop3("(99 participants / 99)")
    assert scraper._parse_inscriptions([b1, b2]) == "  • 10 inscrits / 16 places"


def test_prop_without_pattern_ignored():
    assert scraper._parse_inscriptions([prop3("rien à voir")]) == ""
