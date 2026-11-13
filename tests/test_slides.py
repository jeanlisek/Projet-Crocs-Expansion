"""Tests of slides/build_slides.py (T13): the checks of the brief that code can make."""

import csv
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

pptx = pytest.importorskip("pptx")
from pptx import Presentation  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_slides", ROOT / "slides" / "build_slides.py")
slides = importlib.util.module_from_spec(SPEC)
sys.modules["build_slides"] = slides  # dataclasses look the module up by name
SPEC.loader.exec_module(slides)

EXEMPT = {"pied", "progression", "badge"}  # discreet on purpose


@pytest.fixture(scope="module")
def deck(tmp_path_factory):
    out = tmp_path_factory.mktemp("slides")
    path, data, problems = slides.build(out)
    return Presentation(str(path)), data, problems, out


def test_ten_slides_pass_the_checks_of_the_brief(deck):
    """No verdict before the decision slide, 30 words of running text at most, notes of 60
    to 120 words."""
    prs, _, problems, _ = deck
    assert len(prs.slides) == 10
    assert problems == []


def test_no_verdict_word_before_the_decision_slide(deck):
    prs = deck[0]
    for number, _, text in slides.slide_texts(prs):
        if number < slides.DECISION_SLIDE:
            assert not slides.FORBIDDEN_BEFORE_DECISION.search(text), (number, text)
    texts = " ".join(text for number, _, text in slides.slide_texts(prs) if number == 9)
    assert slides.FORBIDDEN_BEFORE_DECISION.search(texts)


def test_text_sizes(deck):
    """Titles >= 28 pt, other text >= 16 pt, key figures of the cards >= 40 pt."""
    prs = deck[0]
    for number, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not shape.has_text_frame or shape.name in EXEMPT:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if not run.text.strip():
                        continue
                    size = run.font.size.pt
                    minimum = slides.TITLE_PT if shape.name == "titre" else slides.TEXT_PT
                    assert size >= minimum, (number, shape.name, run.text, size)


def test_every_slide_fades_and_has_speaker_notes(deck):
    prs = deck[0]
    for slide in prs.slides:
        transitions = slide._element.findall(slides.qn("p:transition"))
        assert len(transitions) == 1 and transitions[0][0].tag == slides.qn("p:fade")
        assert slide.has_notes_slide and slide.notes_slide.notes_text_frame.text


def test_every_kpi_figure_matches_kpi_summary(deck):
    """The control list, figure by figure: each figure read in kpi_summary is the value of
    its row, rounded as shown."""
    _, data, _, out = deck
    kpis = pd.read_csv(ROOT / "data" / "gold" / "exports" / "kpi_summary.csv", encoding="utf-8")
    with (out / "controle_chiffres.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    checked = 0
    for row in rows:
        found = re.match(r"kpi_summary\.csv : (.+) \((\w\w)\)$", row["source"])
        if not found:
            continue
        name, country = found.groups()
        match = kpis[(kpis["kpi"] == name) & (kpis["pays"] == country)]
        assert not match.empty, row
        shown = re.search(r"[\u2212-]?\d[\d\u00a0]*(?:,\d+)?", row["valeur_affichee"]).group(0)
        number = float(shown.replace("\u00a0", "").replace(",", ".").replace("\u2212", "-"))
        decimals = len(shown.split(",")[1]) if "," in shown else 0
        assert round(float(match["valeur"].iloc[0]), decimals) == number, row
        checked += 1
    assert checked >= 10


def test_a_missing_export_is_shown_in_red(tmp_path):
    exports = tmp_path / "exports"
    shutil.copytree(ROOT / "data" / "gold" / "exports", exports)
    (exports / "city_scoring.csv").unlink()
    path, data, _ = slides.build(tmp_path / "out", slides.Data(exports=exports))
    assert any(line.startswith("slide 6 : ") for line in data.missing)
    prs = Presentation(str(path))
    red = [
        run
        for shape in prs.slides[5].shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
        if run.text == slides.MISSING
    ]
    assert red and all(run.font.color.rgb == slides.RGBColor(0xC0, 0x00, 0x00) for run in red)


def test_french_number_format():
    nbsp, minus = "\u00a0", "\u2212"
    assert slides.fr(565010, 0) == f"565{nbsp}010"
    assert slides.fr(3.894) == "3,89"
    assert slides.fr(5.78, sign=True) == "+5,78"
    assert slides.fr(-0.06, sign=True) == f"{minus}0,06"
    gap = slides.signed_gap(14.94, 15, "pt", "seuil 15 %", higher_is_better=False)
    assert gap.text == f"▼ {minus}0,06 pt vs seuil 15 %" and gap.favourable
    gap = slides.signed_gap(5.54, -0.24, "pt", "France", higher_is_better=True)
    assert gap.text == "▲ +5,78 pts vs France" and gap.favourable


def test_running_words_count_a_number_as_one_word():
    assert slides.count_words("Prix TTC identiques (128/128 paires) : l'indice HT 100,85.") == 8


def test_readers_of_the_readme_and_the_ci():
    tables, relations, facts, dims = slides.readme_model()
    assert tables == facts + dims and relations > 0
    assert len(slides.readme_team()) == 5
    assert slides.ci_systems() == ["Linux", "Windows"]
