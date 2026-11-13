"""Slides of the final oral for the Comex of Crocs France (T13).

    python slides/build_slides.py            # writes the .pptx, then the PDF and PNG previews
    python slides/build_slides.py --no-pdf   # the .pptx only

Every figure is read in data/gold/exports/ and in the `decision` and `slides` sections of
config/hypotheses.yaml: none is written in this file. A value that cannot be read is shown as
« À COMPLÉTER » in red and listed at the end of the run. Every figure shown is also written to
slides/controle_chiffres.csv, with the file and the row it comes from, for the check against
the dashboard.

The colours, the font and the logo are those of the Power BI dashboard (T11), read in its
theme file. The deck follows the format asked by the teacher: a title that states the message,
1 to 3 KPI cards with a signed gap, one chart, a dashed frame on the part of the chart that
carries the message, an insight with the key figures in bold. No slide before the decision
slide shows a verdict.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTS = REPO_ROOT / "data" / "gold" / "exports"
CONFIG = REPO_ROOT / "config" / "hypotheses.yaml"
README = REPO_ROOT / "README.md"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PIPELINE = REPO_ROOT / "docs" / "equipe" / "REGLES_COMMUNES.md"
RESOURCES = (
    REPO_ROOT / "dashboard" / "dashboard_crocs.Report" / "StaticResources" / "RegisteredResources"
)
THEME = RESOURCES / "CrocsTheme.json"
OUT_DIR = REPO_ROOT / "slides"
DECK_NAME = "Crocs_Expansion_Allemagne_Comex"
# Screenshot of the dashboard page « Où s'implanter » filtered on Dortmund, taken by hand in
# Power BI: the slide shows the generated text in its place while the file is missing.
CAPTURE_DORTMUND = OUT_DIR / "assets" / "capture_ou_s_implanter_dortmund.png"

TARGET, REFERENCE = "DE", "FR"
MISSING = "À COMPLÉTER"
NBSP = "\u00a0"
MINUS = "\u2212"

# Destatis licence, word for word (README 3.3, mentions obligatoires).
DESTATIS = (
    "Population : © Statistisches Bundesamt (Destatis), 2025, reproduction autorisée avec "
    "mention de la source"
)
# Labels of the six criteria of the grid (README 4.2), in the words of the team (13/11/2026),
# keyed by the start of the KPI name in kpi_guide / kpi_summary.
CRITERIA = (
    ("Croissance du secteur", "Croissance du marché", "Le marché croît-il ?"),
    ("Indice prix relatif", "Indice de prix HT", "Le prix est-il aligné ?"),
    ("Marge brute post-taxe", "Marge après taxes", "La marge tient-elle ?"),
    ("% du catalogue éligible", "Catalogue vendable", "Le catalogue est-il vendable ?"),
    ("Coût d'occupation", "Loyer ÷ CA, scénario central", "Le loyer est-il soutenable ?"),
    ("Payback", "Remboursement, scénario pessimiste", "L'investissement revient-il vite ?"),
)

# The five sections of the oral (TACHES.md, « L'oral »): label of the progress bar, speaker.
SECTIONS = ("Entreprise", "Données", "KPIs", "Analyse", "Décision")
# Words no slide may show before the decision slide (teacher, 13/11/2026).
FORBIDDEN_BEFORE_DECISION = re.compile(r"\b(no-)?go\b|recommandation|verdict", re.IGNORECASE)
DECISION_SLIDE = 9
MAX_RUNNING_WORDS = 30

# Slide geometry, in inches: 16:9.
WIDTH, HEIGHT = 13.333, 7.5
MARGIN = 0.45
CONTENT_TOP, CONTENT_BOTTOM = 1.62, 6.02
CARD_W = 4.2
CHART_X = MARGIN + CARD_W + 0.35
CHART_W = WIDTH - MARGIN - CHART_X

# Sizes (teacher's brief): titles >= 28 pt, text >= 16 pt, key figures >= 40 pt. The footer
# and the progress bar are discreet on purpose.
TITLE_PT, TEXT_PT, FIGURE_PT, SMALL_PT = 28, 16, 40, 10


# --------------------------------------------------------------------------------------
# Theme of the dashboard
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    green: RGBColor
    dark: RGBColor
    grey: RGBColor
    light: RGBColor
    pale_green: RGBColor
    border: RGBColor
    font: str
    font_bold: str
    missing: RGBColor = RGBColor(0xC0, 0x00, 0x00)  # « À COMPLÉTER » only
    white: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)


def rgb(code: str) -> RGBColor:
    return RGBColor.from_string(code.lstrip("#").upper())


def load_theme(path: Path = THEME) -> Theme:
    """Colours and fonts of the Power BI theme (CrocsTheme.json, T11)."""
    theme = json.loads(path.read_text(encoding="utf-8"))
    border = theme["visualStyles"]["*"]["*"]["border"][0]["color"]["solid"]["color"]
    return Theme(
        green=rgb(theme["good"]),
        dark=rgb(theme["foreground"]),
        grey=rgb(theme["foregroundNeutralSecondary"]),
        light=rgb(theme["backgroundNeutral"]),
        pale_green=rgb(theme["backgroundLight"]),
        border=rgb(border),
        font=theme["textClasses"]["label"]["fontFace"],
        font_bold=theme["textClasses"]["title"]["fontFace"],
    )


def find_logo() -> Path | None:
    """The logo file of the dashboard, used as it is."""
    logos = sorted(RESOURCES.glob("*logo*.png"))
    return logos[0] if logos else None


# --------------------------------------------------------------------------------------
# French number format
# --------------------------------------------------------------------------------------
def fr(value: float, decimals: int = 2, sign: bool = False) -> str:
    """3.894 -> '3,89'; 565010 -> '565 010'; sign=True -> '+5,78' or '−0,06'."""
    text = f"{abs(value):,.{decimals}f}".replace(",", NBSP).replace(".", ",")
    if sign:
        return ("+" if value > 0 else MINUS if value < 0 else "") + text
    return (MINUS if value < 0 else "") + text


def points(value: float) -> str:
    """French plural: 'pt' below 2, 'pts' from 2 on."""
    return "pts" if abs(value) >= 2 else "pt"


# --------------------------------------------------------------------------------------
# Data, with the control list
# --------------------------------------------------------------------------------------
class Data:
    """The exports and the config, read once; every figure shown is recorded."""

    def __init__(self, exports: Path = EXPORTS, config: Path = CONFIG):
        self.exports = exports
        self.config = yaml.safe_load(config.read_text(encoding="utf-8"))
        self._frames: dict[str, pd.DataFrame | None] = {}
        self.controls: list[dict] = []
        self.missing: list[str] = []
        self.slide = 0

    def frame(self, name: str) -> pd.DataFrame | None:
        if name not in self._frames:
            path = self.exports / f"{name}.csv"
            self._frames[name] = pd.read_csv(path, encoding="utf-8") if path.exists() else None
        return self._frames[name]

    def kpi(self, name: str, country: str = TARGET) -> float | None:
        kpis = self.frame("kpi_summary")
        if kpis is None:
            return None
        rows = kpis[(kpis["kpi"] == name) & (kpis["pays"] == country)]
        if rows.empty or pd.isna(rows["valeur"].iloc[0]):
            return None
        return float(rows["valeur"].iloc[0])

    def unit(self, name: str, country: str = TARGET) -> str:
        """Unit of a KPI in kpi_summary, kept on one line."""
        kpis = self.frame("kpi_summary")
        rows = kpis[(kpis["kpi"] == name) & (kpis["pays"] == country)] if kpis is not None else []
        return str(rows["unite"].iloc[0]).replace(" ", NBSP) if len(rows) else MISSING

    def year(self) -> str:
        """Reference year of the KPIs (config, section kpi)."""
        return str(self.config["kpi"]["annee_reference"])

    def collected(self) -> str:
        """Day of the crocs.fr / crocs.de survey, in crocs_produits ('12/11/2026')."""
        products = self.frame("crocs_produits")
        if products is None:
            return MISSING
        year, month, day = str(products["date_collecte"].max()).split("-")
        return f"{day}/{month}/{year}"

    def guide_period(self, name: str) -> str:
        """The « période » of a KPI in kpi_guide, without its leading « réel : »."""
        guide = self.frame("kpi_guide")
        rows = guide[guide["nom"] == name] if guide is not None else []
        if not len(rows):
            return MISSING
        period = str(rows["perimetre"].iloc[0]).split("période : ", 1)[-1]
        return period.removeprefix("réel : ")

    def company(self, column: str) -> float | None:
        """A figure of Crocs France (entreprise_france.csv), reference year."""
        company = self.frame("entreprise_france")
        if company is None or column not in company:
            return None
        rows = company[company["annee"].astype(str) == self.year()]
        return None if rows.empty or pd.isna(rows[column].iloc[0]) else float(rows[column].iloc[0])

    def guide_date(self, name: str, full: bool = False) -> str:
        """Year (or full date) of the survey of a real KPI, in the perimeter of kpi_guide."""
        guide = self.frame("kpi_guide")
        rows = guide[guide["nom"] == name] if guide is not None else []
        found = (
            re.search(r"\d\d/\d\d/(\d{4})", str(rows["perimetre"].iloc[0])) if len(rows) else None
        )
        return (found.group(0) if full else found.group(1)) if found else MISSING

    def population_date(self) -> str:
        density = self.frame("densite_concurrentielle")
        if density is None:
            return MISSING
        year, month, day = str(density["date_reference_population"].max()).split("-")
        return f"{day}/{month}/{year}"

    def track(self, label: str, shown: str, source: str) -> str:
        """Record a figure of the slide being built; return it as shown."""
        self.controls.append(
            {"slide": self.slide, "libelle": label, "valeur_affichee": shown, "source": source}
        )
        return shown

    def lack(self, what: str) -> str:
        self.missing.append(f"slide {self.slide} : {what}")
        self.controls.append(
            {"slide": self.slide, "libelle": what, "valeur_affichee": MISSING, "source": "absent"}
        )
        return MISSING

    def write_controls(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["slide", "libelle", "valeur_affichee", "source"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(self.controls)


def kpi_source(name: str, country: str = TARGET) -> str:
    return f"kpi_summary.csv : {name} ({country})"


# --------------------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------------------
@dataclass
class Variation:
    text: str
    favourable: bool | None  # None: no colour judgement (neutral grey)


def signed_gap(
    value: float, reference: float, unit: str, versus: str, higher_is_better: bool
) -> Variation:
    """'▲ +5,78 pts vs France': green when favourable, dark grey otherwise."""
    gap = round(value - reference, 2)
    arrow = "▲" if gap > 0 else "▼" if gap < 0 else "="
    if unit == "pt":
        unit = points(gap)
    decimals = 0 if unit in ("km",) else 2
    text = f"{arrow} {fr(gap, decimals, sign=True)} {unit} vs {versus}".replace("  ", " ")
    favourable = None if gap == 0 else (gap > 0) == higher_is_better
    return Variation(text, favourable)


class Deck:
    def __init__(self, data: Data, theme: Theme, logo: Path | None):
        self.data, self.theme, self.logo = data, theme, logo
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(WIDTH), Inches(HEIGHT)
        self.slide = None

    # -- primitives ------------------------------------------------------------------
    def notes(self, text: str) -> None:
        self.slide.notes_slide.notes_text_frame.text = text

    def new_slide(self, number: int, section: int | None, notes: str = ""):
        self.data.slide = number
        self.slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        background = self.slide.background.fill
        background.solid()
        background.fore_color.rgb = self.theme.white
        self.slide.notes_slide.notes_text_frame.text = notes
        add_fade(self.slide)
        self.progress(section)
        if number > 1 and self.logo:
            self.picture(self.logo, MARGIN, 0.22, height=0.62)
        return self.slide

    def text(
        self,
        x,
        y,
        w,
        h,
        content: str,
        size: float = TEXT_PT,
        color: RGBColor | None = None,
        bold: bool = False,
        align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.TOP,
        role: str = "texte",
        italic: bool = False,
    ):
        """A text box. '**x**' is bold; a line break starts a new paragraph. `role` names the
        shape: titre, insight and courant are running text, counted against the 30 words."""
        box = self.slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        box.name = role
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = anchor
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(frame, side, Inches(0.02))
        for index, line in enumerate(content.split("\n")):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.alignment = align
            for part_index, part in enumerate(re.split(r"\*\*", line)):
                if not part:
                    continue
                run = paragraph.add_run()
                run.text = part
                strong = bold or part_index % 2 == 1
                run.font.name = self.theme.font_bold if strong else self.theme.font
                run.font.bold = False
                run.font.italic = italic
                run.font.size = Pt(size)
                shown = color or self.theme.dark
                if part == MISSING or MISSING in part:
                    shown = self.theme.missing
                run.font.color.rgb = shown
        return box

    def rect(self, x, y, w, h, fill=None, line=None, dash=False, rounded=False, width=1.0):
        shape = self.slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h),
        )
        if rounded:
            shape.adjustments[0] = 0.08
        if fill is None:
            shape.fill.background()
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill
        if line is None:
            shape.line.fill.background()
        else:
            shape.line.color.rgb = line
            shape.line.width = Pt(width)
            if dash:
                shape.line.dash_style = 4  # MSO_LINE_DASH_STYLE.DASH
        shape.shadow.inherit = False
        shape.text_frame.text = ""
        return shape

    def line(self, x1, y1, x2, y2, color, width=1.5, arrow=False):
        connector = self.slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
        )
        connector.line.color.rgb = color
        connector.line.width = Pt(width)
        if arrow:
            end = etree.SubElement(connector.line._get_or_add_ln(), qn("a:tailEnd"))
            end.set("type", "triangle")
        return connector

    def picture(self, path: Path, x, y, height):
        return self.slide.shapes.add_picture(str(path), Inches(x), Inches(y), height=Inches(height))

    # -- chrome ------------------------------------------------------------------------
    def progress(self, section: int | None):
        """Five segments at the top right; the current section in green."""
        width, gap, top = 1.22, 0.06, 0.3
        x0 = WIDTH - MARGIN - len(SECTIONS) * width - (len(SECTIONS) - 1) * gap
        for index, label in enumerate(SECTIONS, start=1):
            x = x0 + (index - 1) * (width + gap)
            current = index == section
            self.rect(x, top, width, 0.07, fill=self.theme.green if current else self.theme.light)
            self.text(
                x,
                top + 0.1,
                width,
                0.25,
                f"{index}. {label}",
                size=SMALL_PT,
                color=self.theme.dark if current else self.theme.grey,
                bold=current,
                role="progression",
            )

    def title(self, text: str):
        self.text(
            MARGIN, 0.9, WIDTH - 2 * MARGIN, 0.6, text, size=TITLE_PT, bold=True, role="titre"
        )

    def footer(self, sources: str, simulated: bool):
        mention = (
            " · Données simulées : ordres de grandeur, pas des chiffres de Crocs."
            if simulated
            else ""
        )
        self.text(
            MARGIN,
            6.94,
            WIDTH - 2 * MARGIN - 0.8,
            0.5,
            f"Sources : {sources}{mention}",
            size=SMALL_PT,
            color=self.theme.grey,
            role="pied",
        )
        self.text(
            WIDTH - MARGIN - 0.7,
            7.02,
            0.7,
            0.3,
            f"{self.data.slide} / {len(SLIDES)}",
            size=SMALL_PT,
            color=self.theme.grey,
            align=PP_ALIGN.RIGHT,
            role="pied",
        )

    def insight(self, text: str, y: float = 6.15):
        self.text(MARGIN, y, WIDTH - 2 * MARGIN, 0.75, text, size=TEXT_PT + 1, role="insight")

    def card(self, x, y, w, h, label, value, variation: Variation | None, badge: str | None):
        """KPI card of the teacher's example: badge, precise label (2 lines at most), big
        value, signed gap."""
        theme = self.theme
        self.rect(x, y, w, h, fill=theme.white, line=theme.border, rounded=True, width=1.25)
        top = y + 0.14
        if badge:
            real = badge == "Réel"
            self.rect(
                x + 0.18,
                top,
                0.95,
                0.3,
                fill=theme.pale_green if real else theme.light,
                rounded=True,
            )
            self.text(
                x + 0.18,
                top,
                0.95,
                0.3,
                badge,
                size=SMALL_PT + 2,
                color=theme.dark,
                bold=True,
                align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE,
                role="badge",
            )
            top += 0.36
        self.text(x + 0.18, top, w - 0.36, 0.58, label, color=theme.grey, role="carte")
        missing = value == MISSING
        self.text(
            x + 0.18,
            y + h - 1.08,
            w - 0.3,
            0.66,
            value,
            size=18 if missing else FIGURE_PT,
            bold=True,
            anchor=MSO_ANCHOR.BOTTOM,
            role="carte",
        )
        if variation:
            colour = (
                theme.green
                if variation.favourable
                else theme.dark if variation.favourable is False else theme.grey
            )
            self.text(
                x + 0.18,
                y + h - 0.42,
                w - 0.3,
                0.34,
                variation.text,
                bold=True,
                color=colour,
                role="carte",
            )

    def frame_label(self, x, y, w, h, label: str | None = None, label_above: bool = True):
        """The dashed frame on the part of the chart that carries the message."""
        self.rect(x, y, w, h, line=self.theme.green, dash=True, width=2.25)
        if label:
            ly = y - 0.4 if label_above else y + h + 0.04
            self.text(x, ly, w, 0.36, label, bold=True, color=self.theme.green, role="graphique")

    def chart_title(self, text: str, x=CHART_X, y=CONTENT_TOP, w=CHART_W):
        self.text(x, y, w, 0.36, text, bold=True, role="graphique")


def add_fade(slide) -> None:
    """Fade transition, the only one used (python-pptx has no API for transitions)."""
    transition = etree.fromstring(
        '<p:transition xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'spd="med"><p:fade/></p:transition>'
    )
    anchor = slide._element.find(qn("p:clrMapOvr"))
    if anchor is None:
        anchor = slide._element.find(qn("p:cSld"))
    anchor.addnext(transition)


def criterion_of(name: str):
    """The (prefix, label, question) of CRITERIA a KPI name belongs to, or None."""
    return next((c for c in CRITERIA if name.startswith(c[0])), None)


def thresholds(d: Data) -> list[tuple[str, str, str, str]]:
    """(axis, label, threshold, question) of each criterion, threshold read in kpi_guide."""
    guide = d.frame("kpi_guide")
    if guide is None:
        return []
    rows = []
    for prefix, label, question in CRITERIA:
        match = guide[guide["nom"].str.startswith(prefix) & guide["seuil"].notna()]
        if match.empty:
            rows.append(("", label, d.lack(f"seuil {label}"), question))
            continue
        rule = str(match["seuil"].iloc[0]).split(" (README", 1)[0]
        rule = re.sub(r"(\d)\.(\d)", r"\1,\2", rule)
        d.track(f"Seuil {label}", rule, "kpi_guide.csv : colonne seuil")
        rows.append((match["axe"].iloc[0], label, rule, question))
    return rows


def results(d: Data) -> list[tuple[str, str, str, str]]:
    """(label, threshold, value in Germany, verdict) of each criterion: the slide 9 table."""
    kpis = d.frame("kpi_summary")
    cases = d.frame("business_case")
    horizon = int(cases["horizon_annees"].iloc[0]) if cases is not None else None
    rules = {label: rule for _, label, rule, _ in thresholds(d)}
    origin = {"REEL": "réel", "SIMULE": "simulé", "MIXTE": "mixte"}
    rows = []
    for prefix, label, _ in CRITERIA:
        match = kpis[
            (kpis["pays"] == TARGET) & kpis["kpi"].str.startswith(prefix) & kpis["seuil"].notna()
        ]
        values, verdicts = [], []
        for row in match.itertuples():
            unit = row.unite or ""
            if pd.isna(row.valeur):
                shown = f"non atteint en {horizon} ans" if horizon else MISSING
            else:
                decimals = 1 if unit == "mois" else 2
                shown = f"{fr(row.valeur, decimals)} {'' if unit == 'indice' else unit}".strip()
            part = row.kpi.split(" : ", 1)[1].lower() if " : " in row.kpi else ""
            values.append((f"{shown} {part}".strip(), origin.get(row.origine_donnees, "")))
            verdicts.append(row.statut_go)
            missing = " : vide = non atteint" if pd.isna(row.valeur) else ""
            d.track(f"{label} {part}".strip(), shown, kpi_source(row.kpi) + missing)
        shown_values = {value.split(" centre")[0] for value, _ in values}
        if len(values) > 1 and len(shown_values) == 1:  # same result in both formats
            values = [(f"{shown_values.pop()}, deux formats", values[0][1])]
        origins = {tag for _, tag in values}
        text = " ; ".join(value for value, _ in values)
        values = [f"{text} ({origins.pop()})" if len(origins) == 1 else text] if values else []
        if prefix == "Croissance du secteur":
            real = kpis[(kpis["pays"] == TARGET) & kpis["kpi"].str.startswith("Croissance des dép")]
            if not real.empty:
                value = fr(real["valeur"].iloc[0])
                values.append(f"{value} % réel (Eurostat, toutes chaussures)")
                d.track("Croissance Eurostat DE", f"{value} %", kpi_source(real["kpi"].iloc[0]))
        verdict = " / ".join(dict.fromkeys(verdicts)) if verdicts else MISSING
        rows.append((label, rules.get(label, MISSING), " ; ".join(values) or MISSING, verdict))
    return rows


# --------------------------------------------------------------------------------------
# Readers of the README and of the CI (architecture slide)
# --------------------------------------------------------------------------------------
def pipeline_state(path: Path = PIPELINE) -> tuple[int, int, int, int]:
    """(tables, simulated, real, relations) of the gold warehouse, read in « État du
    pipeline » (REGLES_COMMUNES.md, row « 3. Gold »), kept up to date at each merge."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 3. Gold"):
            found = re.search(
                r"(\d+) tables \((\d+) simulées, (\d+) réelles\).*?(\d+) relations", line
            )
            if found:
                return tuple(int(value) for value in found.groups())
    raise ValueError("ligne « 3. Gold » introuvable dans l'état du pipeline")


def readme_relations(path: Path = README) -> list[tuple[str, str]]:
    """(parent, child) of each relation of the constellation diagram, README 3.2."""
    block = path.read_text(encoding="utf-8").split("erDiagram", 1)[1].split("```", 1)[0]
    return re.findall(r"^\s*(\w+)\s+\S+\s+(\w+)\s*:", block, flags=re.MULTILINE)


def readme_period(path: Path = README) -> str:
    """The period of the study, in the title of the README ("2027-2029")."""
    first = path.read_text(encoding="utf-8").splitlines()[0]
    found = re.search(r"\d{4}-\d{4}", first)
    return found.group(0) if found else MISSING


def readme_team(path: Path = README) -> list[str]:
    """First names of the team table of the README."""
    text = path.read_text(encoding="utf-8").split("## Équipe", 1)[1].split("\n---", 1)[0]
    rows = re.findall(r"^\|\s*([^|]+?)\s*\|", text, flags=re.MULTILINE)
    return [row.split()[0] for row in rows if row not in ("Membre",) and not row.startswith("-")]


def ci_systems(path: Path = CI) -> list[str]:
    match = re.search(r"os:\s*\[([^\]]+)\]", path.read_text(encoding="utf-8"))
    names = {"ubuntu": "Linux", "windows": "Windows", "macos": "macOS"}
    return [names.get(os.strip().split("-")[0], os.strip()) for os in match.group(1).split(",")]


# --------------------------------------------------------------------------------------
# The ten slides
# --------------------------------------------------------------------------------------
def slide_1(deck: Deck) -> None:
    d, t = deck.data, deck.theme
    deck.new_slide(1, 1)
    if deck.logo:
        deck.picture(deck.logo, MARGIN, 0.85, height=1.9)
    deck.text(
        3.3,
        1.05,
        WIDTH - 3.3 - MARGIN,
        1.5,
        "Faut-il ouvrir un réseau Crocs en propre en Allemagne ?",
        size=36,
        bold=True,
        anchor=MSO_ANCHOR.MIDDLE,
        role="titre",
    )
    deck.text(
        3.3,
        2.55,
        WIDTH - 3.3 - MARGIN,
        0.4,
        f"Comex Crocs France · {readme_period()}",
        color=t.grey,
        role="courant",
    )
    year, source = d.year(), "entreprise_france.csv"
    total, opened = d.company("nb_magasins_total"), d.company("nb_magasins_ouverts")
    revenue, online = d.company("ca_ttc_eur"), d.company("part_ecommerce_ca_ht_pct")
    sku = d.company("nb_sku")
    cards = [
        (
            f"Magasins France · ouverts / total · {year}",
            (
                d.track("Magasins ouverts / total", f"{fr(opened, 0)} / {fr(total, 0)}", source)
                if total is not None and opened is not None
                else d.lack("magasins France (entreprise_france.csv)")
            ),
        ),
        (
            f"CA France · TTC · {year}",
            (
                d.track("CA France TTC", f"{fr(revenue / 1e6, 1)} M€", f"{source} : ca_ttc_eur")
                if revenue is not None
                else d.lack("CA France TTC (entreprise_france.csv)")
            ),
        ),
        (
            f"E-commerce · part du CA HT · France · {year}",
            (
                d.track(
                    "Part e-commerce", f"{fr(online)} %", f"{source} : part_ecommerce_ca_ht_pct"
                )
                if online is not None
                else d.lack("part e-commerce (entreprise_france.csv)")
            ),
        ),
        (
            f"SKU · catalogue France · {year}",
            (
                d.track("SKU", fr(sku, 0), f"{source} : nb_sku")
                if sku is not None
                else d.lack("nombre de SKU (entreprise_france.csv)")
            ),
        ),
    ]
    width = (WIDTH - 2 * MARGIN - 0.2 * (len(cards) - 1)) / len(cards)
    for index, (label, value) in enumerate(cards):
        deck.card(MARGIN + index * (width + 0.2), 3.3, width, 2.25, label, value, None, "Simulé")
    share = d.kpi("Part de marché Crocs")
    share_fr = d.kpi("Part de marché Crocs", REFERENCE)
    if share is not None and share_fr is not None:
        d.track("Part de marché Crocs DE", f"{fr(share)} %", kpi_source("Part de marché Crocs"))
        d.track(
            "Part de marché Crocs FR (référence)",
            f"{fr(share_fr)} %",
            kpi_source("Part de marché Crocs", REFERENCE),
        )
        gap = signed_gap(share, share_fr, "pt", "France", True).text.split(" ", 1)[1]
        deck.insight(
            f"Via des revendeurs, Crocs pèse déjà **{fr(share)} %** du segment allemand "
            f"(**{gap}**).",
            y=5.75,
        )
    else:
        deck.insight(d.lack("part de marché Crocs DE / FR"), y=5.75)
    deck.text(
        MARGIN,
        6.5,
        WIDTH - 2 * MARGIN,
        0.4,
        f"{', '.join(readme_team())} · Projet pédagogique, Eugenia School. Scénario fictif.",
        size=SMALL_PT + 3,
        color=t.grey,
        role="pied",
    )
    deck.notes(
        "Aurélie, 1 min. Bonjour. Crocs France exploite un réseau de magasins en propre et "
        "vend en ligne sur crocs.fr. En Allemagne, la marque est déjà présente, mais "
        "seulement chez des revendeurs. La question que nous pose le Comex est simple : "
        f"faut-il ouvrir un réseau Crocs en propre en Allemagne sur {readme_period()} ? "
        "Précision importante : le scénario est fictif et assumé, les données internes de "
        "Crocs sont simulées et signalées comme telles sur chaque slide. Nous sommes cinq, et "
        "chacun présente la partie qu'il a construite. Mehdi commence par les données."
    )
    deck.footer(
        f"entreprise_france ({year}) ; kpi_summary (part de marché {year}, segment casual "
        "moulé & sandales, en valeur TTC)",
        True,
    )


def slide_2(deck: Deck) -> None:
    d = deck.data
    tables, simulated, real, relations = pipeline_state()
    systems = ci_systems()
    deck.new_slide(
        2,
        2,
        notes=(
            "Mehdi, 45 s. Toutes les données passent par la même chaîne : les sources réelles "
            "et le générateur simulé alimentent la couche bronze, brute et datée ; la couche "
            "silver nettoie et type ; la couche gold est un entrepôt DuckDB de "
            f"{tables} tables, {simulated} simulées et {real} réelles, reliées par {relations} "
            "clés étrangères. Le modèle est une constellation : plusieurs étoiles, chacune une "
            "table de faits entourée de ses dimensions, qui partagent le temps, le pays et le "
            "hub ; deux dimensions se rattachent à une autre, ce sont les branches en flocon. "
            "Une seule commande, make all, reconstruit tout, et la CI rejoue les tests à "
            f"chaque push sous {' et '.join(systems)}."
        ),
    )
    deck.title("Un entrepôt testé, reproductible en une commande")
    deck.card(
        MARGIN,
        CONTENT_TOP,
        CARD_W,
        2.1,
        "Tables de l'entrepôt gold · DuckDB · modèle en constellation",
        d.track("Tables de l'entrepôt", fr(tables, 0), "REGLES_COMMUNES.md : État du pipeline"),
        Variation(f"{simulated} simulées · {real} réelles", None),
        None,
    )
    d.track(
        "Tables simulées / réelles",
        f"{simulated} / {real}",
        "REGLES_COMMUNES.md : État du pipeline",
    )
    deck.card(
        MARGIN,
        CONTENT_TOP + 2.25,
        CARD_W,
        2.1,
        "Relations entre tables · clés étrangères de l'entrepôt",
        d.track("Relations", fr(relations, 0), "REGLES_COMMUNES.md : État du pipeline"),
        Variation(f"CI : {' et '.join(systems)}", None),
        None,
    )
    draw_constellation(deck)
    deck.insight("Des **étoiles** partagent leurs dimensions ; deux branches en **flocon**.")
    deck.footer(
        "docs/equipe/REGLES_COMMUNES.md (état du pipeline) ; README 3.1-3.2 ; "
        ".github/workflows/ci.yml ; Makefile",
        False,
    )


# Words for the tables of the diagram (README 3.2); a table missing here keeps its name.
TABLE_LABELS = {
    "dim_temps": "Temps",
    "dim_produit": "Produit",
    "dim_pays": "Pays",
    "dim_concurrent": "Concurrent",
    "dim_zone_chalandise": "Zone de chalandise",
    "dim_magasin": "Magasin",
    "dim_hub_logistique": "Hub logistique",
    "fact_ventes_france": "Ventes France",
}


def draw_constellation(deck: Deck) -> None:
    """The star / snowflake model of README 3.2, simplified: the facts grouped by the
    dimension they hang on, every dimension, and the two snowflake branches framed."""
    d, t = deck.data, deck.theme
    relations = readme_relations()
    facts_of = {}
    for parent, child in relations:
        if child.startswith("fact_"):
            facts_of.setdefault(parent, set()).add(child)
    flakes = [(p, c) for p, c in relations if p.startswith("dim_") and c.startswith("dim_")]
    by_country = facts_of.get("dim_pays", set())
    by_zone = facts_of.get("dim_zone_chalandise", set())
    sales = {f for f in facts_of.get("dim_magasin", set())}
    facts = {c for _, c in relations if c.startswith("fact_")}
    d.track("Tables de faits (README 3.2)", fr(len(facts), 0), "README.md, section 3.2 (erDiagram)")
    deck.chart_title("Modèle en constellation (README 3.2) · vert : faits · gris : dimensions")
    x0 = CHART_X
    boxes = {
        # dimensions, top row and bottom row
        "dim_temps": (x0, 2.25, 1.55),
        "dim_pays": (x0 + 2.95, 2.25, 1.3),
        "dim_zone_chalandise": (x0 + 5.6, 2.25, 2.25),
        "dim_produit": (x0, 4.85, 1.4),
        "dim_magasin": (x0 + 1.6, 4.85, 1.45),
        "dim_hub_logistique": (x0 + 3.45, 4.85, 2.0),
        "dim_concurrent": (x0 + 5.95, 4.85, 1.9),
    }
    facts_boxes = {
        "ventes": (x0, 3.5, 2.05, TABLE_LABELS.get(next(iter(sales), ""), "Ventes")),
        "pays": (x0 + 2.45, 3.5, 2.6, f"{len(by_country)} faits par pays"),
        "zone": (x0 + 5.35, 3.5, 2.5, f"{len(by_zone)} faits par zone"),
    }
    d.track("Faits par pays / par zone", f"{len(by_country)} / {len(by_zone)}", "README.md, 3.2")
    height = 0.55

    def centre(box, top=True, fact=False):
        x, y, w = box[:3]
        h = 0.75 if fact else height
        return x + w / 2, (y if top else y + h)

    links = [
        ("ventes", "dim_temps"),
        ("ventes", "dim_produit"),
        ("ventes", "dim_magasin"),
        ("pays", "dim_pays"),
        ("pays", "dim_temps"),
        ("pays", "dim_concurrent"),
        ("zone", "dim_zone_chalandise"),
        ("zone", "dim_hub_logistique"),
        ("zone", "dim_concurrent"),
    ]
    for fact, dim in links:
        fx, fy_top = centre(facts_boxes[fact], top=True, fact=True)
        _, fy_bottom = centre(facts_boxes[fact], top=False, fact=True)
        dx, dy_top = centre(boxes[dim], top=True)
        _, dy_bottom = centre(boxes[dim], top=False)
        if dy_top < fy_top:  # dimension above the fact
            deck.line(fx, fy_top, dx, dy_bottom, t.grey, width=1.25)
        else:
            deck.line(fx, fy_bottom, dx, dy_top, t.grey, width=1.25)
    for parent, child in flakes:  # snowflake: a dimension hanging on another
        if parent in boxes and child in boxes:
            (px, py, pw), (cx, _, cw) = boxes[parent], boxes[child]
            left, right = sorted([(px, pw), (cx, cw)])
            deck.line(left[0] + left[1], py + height / 2, right[0], py + height / 2, t.green, 2)
    for key, (x, y, w, label) in facts_boxes.items():
        deck.rect(x, y, w, 0.75, fill=t.green, rounded=True)
        deck.text(
            x,
            y,
            w,
            0.75,
            label,
            size=TEXT_PT,
            bold=True,
            color=t.white,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
    for key, (x, y, w) in boxes.items():
        deck.rect(x, y, w, height, fill=t.light, rounded=True)
        deck.text(
            x,
            y,
            w,
            height,
            TABLE_LABELS.get(key, key),
            size=TEXT_PT,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
    for parent, child in flakes:
        if parent in boxes and child in boxes:
            (px, py, pw), (cx, _, cw) = boxes[parent], boxes[child]
            x1, x2 = min(px, cx), max(px + pw, cx + cw)
            deck.frame_label(
                x1 - 0.08,
                py - 0.08,
                x2 - x1 + 0.16,
                height + 0.16,
                "flocon",
                label_above=False,
            )


def slide_3(deck: Deck) -> None:
    d, t = deck.data, deck.theme
    real = d.kpi("Distance moyenne au hub le plus proche")
    simulated = d.kpi("Distance moyenne au hub le plus proche (comparaison, jeu simulé)")
    deck.new_slide(
        3,
        2,
        notes=(
            "Mehdi, 45 s. Pour chaque axe, nous avons cherché une source réelle et ouverte : "
            "Eurostat pour le marché, les sites crocs.fr et crocs.de pour les prix et le "
            "catalogue, OpenStreetMap, Destatis et OSRM pour les villes et les distances, TARIC "
            "pour les droits. Ce qui reste interne à Crocs, ventes et coûts, est simulé et "
            "étiqueté. Quand les deux existent, nous les comparons : la distance moyenne au hub "
            "est quasiment la même dans le réel et dans le simulé. Les licences des sources "
            "ouvertes sont citées en bas de la slide."
        ),
    )
    deck.title("Chaque axe a sa source réelle ou simulée, étiquetée")
    if real is not None and simulated is not None:
        value = d.track(
            "Distance moyenne au hub DE (réel)",
            f"{fr(real, 0)} km",
            kpi_source("Distance moyenne au hub le plus proche"),
        )
        d.track(
            "Distance moyenne au hub DE (simulé)",
            f"{fr(simulated, 0)} km",
            kpi_source("Distance moyenne au hub le plus proche (comparaison, jeu simulé)"),
        )
        variation = signed_gap(
            round(real), round(simulated), "km", f"simulé ({fr(simulated, 0)} km)", False
        )
        variation.favourable = None
    else:
        value, variation = d.lack("distance moyenne au hub, réel et simulé"), None
    deck.card(
        MARGIN,
        CONTENT_TOP + 0.55,
        CARD_W,
        2.3,
        "Distance au hub · Allemagne · calcul OSRM du "
        f"{d.guide_date('Distance moyenne au hub le plus proche', full=True)}",
        value,
        variation,
        "Réel",
    )
    deck.frame_label(
        MARGIN - 0.1, CONTENT_TOP + 0.45, CARD_W + 0.2, 2.5, "Le réel confirme le simulé"
    )
    # Axes of README 2.3, Réseau and Logistique shown together as in the five sections of the oral.
    rows = [
        ("Axe", "Source réelle", "Simulé"),
        ("Marché", "Eurostat : dépenses en chaussures", "segment, parts"),
        ("Prix", "crocs.fr / crocs.de : prix", "marge, coûts"),
        ("Réseau & logistique", "OSM, Destatis, OSRM, TARIC", "loyers, hubs"),
        ("Assortiment", "crocs.fr / crocs.de : catalogue", "pénétration"),
        ("Rentabilité", "aucune (données internes)", "ventes, coûts"),
    ]
    deck.chart_title("Origine des données, par axe")
    widths = (2.35, 3.75, CHART_W - 6.1)
    top = CONTENT_TOP + 0.5
    for r, row in enumerate(rows):
        x = CHART_X
        y = top + r * 0.6
        fill = t.green if r == 0 else (t.white if r % 2 else t.pale_green)
        deck.rect(CHART_X, y, CHART_W, 0.6, fill=fill)
        for c, cell in enumerate(row):
            deck.text(
                x + 0.1,
                y,
                widths[c] - 0.15,
                0.6,
                cell,
                size=TEXT_PT,
                bold=(r == 0 or c == 0),
                anchor=MSO_ANCHOR.MIDDLE,
                role="graphique",
            )
            x += widths[c]
    deck.insight(
        "Ce qui est interne à Crocs est **simulé et étiqueté** ; "
        "tout le reste vient de **sources ouvertes**."
    )
    deck.footer(
        "© contributeurs OpenStreetMap (ODbL) · "
        f"{DESTATIS} · itinéraires OSRM · Eurostat · TARIC · crocs.fr, crocs.de "
        f"({d.collected()})",
        True,
    )


def slide_4(deck: Deck) -> None:
    d, t = deck.data, deck.theme
    guide = d.frame("kpi_guide")
    deck.new_slide(
        4,
        3,
        notes=(
            "Alexis, 2 min. Chaque KPI répond à une question de décision. Le marché : est-il en "
            "croissance ? Le prix : pouvons-nous vendre au même niveau qu'en France et garder "
            "notre marge ? L'assortiment : le catalogue français est-il vendable ? La "
            "rentabilité : un magasin couvre-t-il ses coûts et rembourse-t-il son "
            "investissement assez vite ? Réseau et logistique éclairent le choix des villes. "
            "Point essentiel : ces seuils ont été fixés avant toute analyse, et nous ne les "
            "avons pas modifiés après avoir vu les résultats. Le coût d'occupation est jugé sur "
            "le scénario central, le payback sur le scénario pessimiste, le plus prudent."
        ),
    )
    if guide is None:
        deck.title("Des seuils fixés avant l'analyse")
        deck.text(MARGIN, 3, 6, 0.5, d.lack("kpi_guide.csv"), role="courant")
        deck.footer("kpi_guide.csv", False)
        return
    grid = thresholds(d)
    deck.title(f"{fr(len(grid), 0)} seuils fixés avant l'analyse")
    header = ("Axe", "Critère", "Seuil", "Décision éclairée")
    widths = (1.9, 4.6, 2.2, WIDTH - 2 * MARGIN - 8.7)
    top, height = CONTENT_TOP + 0.05, 0.6
    rows = [header] + grid
    for r, row in enumerate(rows):
        y = top + r * height
        fill = t.green if r == 0 else (t.white if r % 2 else t.pale_green)
        deck.rect(MARGIN, y, WIDTH - 2 * MARGIN, height, fill=fill)
        x = MARGIN
        for c, cell in enumerate(row):
            deck.text(
                x + 0.1,
                y,
                widths[c] - 0.15,
                height,
                cell,
                size=TEXT_PT,
                bold=(r == 0 or c == 2),
                anchor=MSO_ANCHOR.MIDDLE,
                role="graphique",
            )
            x += widths[c]
    deck.frame_label(
        MARGIN + widths[0] + widths[1] - 0.04,
        top - 0.04,
        widths[2] + 0.08,
        height * len(rows) + 0.08,
    )
    deck.insight("Les seuils sont fixés **avant** l'analyse : on ne les ajuste pas au résultat.")
    deck.footer("README 2.3 et 4.2 ; kpi_guide.csv", False)


def slide_5(deck: Deck) -> None:
    d = deck.data
    name = (
        "Croissance des dépenses des ménages en chaussures (Eurostat, TCAM 2022-2025, toutes "
        "chaussures, en valeur, inflation comprise, données provisoires)"
    )
    tcam, tcam_fr = d.kpi(name), d.kpi(name, REFERENCE)
    index_name = "Indice prix relatif (HT, base pays de référence = 100)"
    price = d.kpi(index_name)
    base = float(re.search(r"= (\d+)\)", index_name).group(1))
    catalogue = d.kpi("% du catalogue éligible")
    vat, vat_fr = d.kpi("TVA standard"), d.kpi("TVA standard", REFERENCE)
    deck.new_slide(5, 4)
    deck.title("Le marché allemand croît, le marché français stagne")
    first, last = d.config["kpi"]["tcam_annee_debut"], d.config["kpi"]["tcam_annee_fin"]
    deck.notes(
        "Jean-Li, 45 s. Premier indicateur, le plus large : le marché. Selon Eurostat, les "
        f"dépenses des ménages allemands en chaussures ont progressé entre {first} et {last}, "
        "quand celles des ménages français ont stagné. Ces chiffres allemands sont "
        "provisoires, et ils couvrent toutes les chaussures, pas seulement notre segment. "
        "Deuxième indicateur, le prix : sur les sites de Crocs, le prix TTC est exactement le "
        "même en France et en Allemagne. L'écart d'indice HT ne vient que de la TVA, plus "
        "basse en Allemagne. Et tout le catalogue français est déjà listé sur crocs.de."
    )
    if tcam is not None and tcam_fr is not None:
        value = d.track("TCAM dépenses chaussures DE", f"{fr(tcam)} %", kpi_source(name))
        d.track(
            "TCAM dépenses chaussures FR (référence)",
            f"{fr(tcam_fr)} %",
            kpi_source(name, REFERENCE),
        )
        variation = signed_gap(tcam, tcam_fr, "pt", "France", True)
    else:
        value, variation = d.lack("TCAM Eurostat DE / FR"), None
    deck.card(
        MARGIN,
        CONTENT_TOP,
        CARD_W,
        2.1,
        f"TCAM {d.config['kpi']['tcam_annee_debut']}-{d.config['kpi']['tcam_annee_fin']} · "
        "dépenses en chaussures · Allemagne · TTC",
        value,
        variation,
        "Réel",
    )
    if price is not None:
        shown = d.track("Indice prix relatif HT DE", fr(price), kpi_source(index_name))
        variation = signed_gap(price, base, "pt", f"France ({fr(base, 0)})", True)
        variation.favourable = None  # a gap of VAT, neither good nor bad
    else:
        shown, variation = d.lack("indice prix relatif HT DE"), None
    deck.card(
        MARGIN,
        CONTENT_TOP + 2.25,
        CARD_W,
        2.1,
        f"Indice prix · HT · Allemagne / France · {d.collected()}",
        shown,
        variation,
        "Réel",
    )
    # Chart: household spending on footwear, index 100 in the first year of the TCAM.
    series = d.frame("eurostat_series")
    start, end = d.config["kpi"]["tcam_annee_debut"], d.config["kpi"]["tcam_annee_fin"]
    deck.chart_title(f"Dépenses des ménages en chaussures · base 100 en {start} · TTC")
    if series is None:
        deck.text(CHART_X, 3, 5, 0.5, d.lack("eurostat_series.csv"), role="graphique")
    else:
        spend = series[series["indicateur"] == "depenses_menages_chaussures_meur"]
        years = sorted(
            set(spend[spend["code_pays"] == TARGET]["annee"])
            & set(spend[spend["code_pays"] == REFERENCE]["annee"])
        )
        years = [y for y in years if y >= start - 4 and y <= end]
        lines = {}
        provisional = {}
        for country in (TARGET, REFERENCE):
            rows = spend[spend["code_pays"] == country].set_index("annee")
            lines[country] = [
                rows.loc[y, "valeur"] / rows.loc[start, "valeur"] * 100 for y in years
            ]
            provisional[country] = [y for y in years if rows.loc[y, "statut_eurostat"] == "p"]
        draw_lines(deck, years, lines, start, end)
        last = {c: lines[c][-1] for c in lines}
        for c in lines:
            d.track(
                f"Indice dépenses chaussures {c} {end} (base {start})",
                fr(last[c], 1),
                "eurostat_series.csv : depenses_menages_chaussures_meur",
            )
    pairs = price_pairs(d)
    words = []
    if pairs:
        same, total = pairs
        words.append(f"Prix TTC identiques (**{fr(same, 0)}/{fr(total, 0)} paires**)")
        d.track(
            "Paires FR/DE au même prix TTC",
            f"{same} / {total}",
            "crocs_produits.csv : paires disponibles sur les deux sites",
        )
    else:
        words.append(f"Prix TTC : {d.lack('paires de prix crocs_produits')}")
    if price is not None and vat is not None and vat_fr is not None:
        words.append(
            f"indice HT **{fr(price)}** dû à la TVA "
            f"(**{fr(vat, 0)} %** vs **{fr(vat_fr, 0)} %**)"
        )
        d.track("TVA DE / FR", f"{fr(vat, 0)} % / {fr(vat_fr, 0)} %", kpi_source("TVA standard"))
    if catalogue is not None:
        words.append(f"catalogue à **{fr(catalogue, 0)} %**")
        d.track(
            "% du catalogue éligible DE",
            f"{fr(catalogue, 0)} %",
            kpi_source("% du catalogue éligible"),
        )
    deck.insight(" ; ".join(words) + ".")
    deck.footer(
        "Eurostat nama_10_cp18 (dépenses, toutes chaussures ; DE provisoire "
        f"{min(provisional.get(TARGET, [start]))}-{end}) ; "
        f"crocs.fr et crocs.de, relevé du {d.collected()}",
        False,
    )


def price_pairs(d: Data) -> tuple[int, int] | None:
    """Pairs (model, colour) on sale on both sites, and how many have the same TTC price."""
    products = d.frame("crocs_produits")
    if products is None:
        return None
    products = products.astype({"code_modele": str, "code_coloris": str})
    on_sale = products[products["disponible"].astype(str).str.lower() == "true"]
    pairs = on_sale[on_sale["site"] == REFERENCE].merge(
        on_sale[on_sale["site"] == TARGET],
        on=["code_modele", "code_coloris"],
        suffixes=("_fr", "_de"),
    )
    return int((pairs["prix_affiche_fr"] == pairs["prix_affiche_de"]).sum()), len(pairs)


def draw_lines(deck: Deck, years: list[int], lines: dict, start: int, end: int) -> None:
    """Line chart drawn with shapes: the same rendering in PowerPoint and in the PDF."""
    t = deck.theme
    left, right = CHART_X + 0.75, CHART_X + CHART_W - 2.15
    top, bottom = CONTENT_TOP + 0.95, CONTENT_BOTTOM - 0.55
    values = [v for serie in lines.values() for v in serie]
    low, high = (int(min(values) // 10) * 10), (int(max(values) // 10) + 1) * 10

    def px(i):
        return left + (right - left) * i / (len(years) - 1)

    def py(v):
        return bottom - (bottom - top) * (v - low) / (high - low)

    for tick in range(low, high + 1, 10):
        deck.line(left, py(tick), right, py(tick), t.light, width=0.75)
        deck.text(
            left - 0.7,
            py(tick) - 0.17,
            0.6,
            0.34,
            str(tick),
            size=TEXT_PT,
            color=t.grey,
            align=PP_ALIGN.RIGHT,
            role="graphique",
        )
    for i, year in enumerate(years):
        deck.text(
            px(i) - 0.4,
            bottom + 0.08,
            0.8,
            0.34,
            str(year),
            size=TEXT_PT,
            color=t.grey,
            align=PP_ALIGN.CENTER,
            role="graphique",
        )
    colours = {TARGET: t.green, REFERENCE: t.dark}
    names = {TARGET: "Allemagne", REFERENCE: "France"}
    for country, serie in lines.items():
        for i in range(1, len(serie)):
            deck.line(px(i - 1), py(serie[i - 1]), px(i), py(serie[i]), colours[country], width=3.5)
        deck.text(
            right + 0.4,
            py(serie[-1]) - 0.2,
            1.75,
            0.4,
            f"{names[country]} {fr(serie[-1], 1)}",
            bold=True,
            color=colours[country],
            role="graphique",
        )
    first = years.index(start)
    deck.frame_label(
        px(first) - 0.3,
        top - 0.15,
        px(len(years) - 1) - px(first) + 0.6,
        bottom - top + 0.6,
        f"TCAM {start}-{end}",
    )


def slide_6(deck: Deck) -> None:
    d, t = deck.data, deck.theme
    cities = d.frame("city_scoring")
    hubs = d.frame("distance_hub")
    deck.new_slide(6, 4)
    if cities is None or hubs is None:
        deck.title("Les villes allemandes, classées")
        deck.text(MARGIN, 3, 6, 0.5, d.lack("city_scoring.csv / distance_hub.csv"), role="courant")
        deck.footer("city_scoring.csv ; distance_hub.csv", True)
        return
    cities = cities.sort_values("rang")
    top = cities[cities["est_prioritaire"].astype(str).str.lower() == "true"]
    hub = hubs["commune_hub_le_plus_proche"].value_counts().index[0]
    deck.title(f"{len(top)} villes se détachent, desservies depuis {hub}")
    density_top, density_all = (
        top["densite_pour_100k_hab"].mean(),
        cities["densite_pour_100k_hab"].mean(),
    )
    deck.card(
        MARGIN,
        CONTENT_TOP,
        CARD_W,
        2.1,
        f"Magasins {d.unit('Densité concurrentielle').replace('pour ', '/ ')} · top {len(top)}, "
        "Allemagne",
        d.track(
            "Densité moyenne top 6",
            fr(density_top),
            "city_scoring.csv : moyenne de densite_pour_100k_hab, est_prioritaire",
        ),
        signed_gap(
            round(density_top, 2),
            round(density_all, 2),
            "",
            f"12 villes ({fr(density_all)})",
            False,
        ),
        "Réel",
    )
    d.track(
        "Densité moyenne 12 villes",
        fr(density_all),
        "city_scoring.csv : moyenne de densite_pour_100k_hab",
    )
    distance_top = hubs[hubs["ville"].isin(top["ville"])]["distance_reelle_km"].mean()
    distance_all = d.kpi("Distance moyenne au hub le plus proche")
    if distance_all is None:
        distance_all = hubs["distance_reelle_km"].mean()
    deck.card(
        MARGIN,
        CONTENT_TOP + 2.25,
        CARD_W,
        2.1,
        f"Distance au hub le plus proche · top {len(top)}, Allemagne · "
        f"OSRM {d.guide_date('Distance moyenne au hub le plus proche')}",
        d.track(
            "Distance moyenne top 6",
            f"{fr(distance_top, 0)} km",
            "distance_hub.csv : moyenne de distance_reelle_km, villes est_prioritaire",
        ),
        signed_gap(
            round(distance_top),
            round(distance_all),
            "km",
            f"12 villes ({fr(distance_all, 0)} km)",
            False,
        ),
        "Réel",
    )
    weights = d.config["city_scoring"]["poids"]
    labels = {"densite_concurrentielle": "densité", "distance_hub": "distance"}
    legend = ", ".join(f"{fr(v, 0)} % {labels.get(k, k)}" for k, v in weights.items())
    deck.chart_title(f"Score /100 des {len(cities)} villes allemandes")
    deck.notes(
        "Jean-Li, 45 s. Une fois le marché posé, où ouvrir ? Nous avons classé les "
        f"{len(cities)} plus grandes villes allemandes sur un score sur 100 : {legend}. Le "
        "potentiel utilise la population officielle Destatis, la densité les magasins de "
        f"chaussures relevés dans OpenStreetMap. {len(top)} villes se détachent. Elles ont "
        f"moins de concurrence que la moyenne des {len(cities)}, et elles sont plus proches de "
        f"notre centre de distribution de {hub}, qui est le hub le plus proche de presque toutes "
        "les villes. C'est aussi la page du dashboard que nous allons montrer en direct."
    )
    left, label_w = CHART_X, 1.55
    bar_left, bar_right = left + label_w, CHART_X + CHART_W - 0.7
    row_h = (CONTENT_BOTTOM - CONTENT_TOP - 0.55) / len(cities)
    y0 = CONTENT_TOP + 0.5
    best = cities["score"].max()
    for i, row in enumerate(cities.itertuples()):
        y = y0 + i * row_h
        prioritaire = row.ville in set(top["ville"])
        deck.text(
            left,
            y,
            label_w - 0.1,
            row_h,
            row.ville,
            size=TEXT_PT,
            align=PP_ALIGN.RIGHT,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
        length = (bar_right - bar_left) * row.score / best
        deck.rect(
            bar_left,
            y + row_h * 0.18,
            length,
            row_h * 0.64,
            fill=t.green if prioritaire else t.light,
        )
        deck.text(
            bar_left + length + 0.08,
            y,
            0.7,
            row_h,
            fr(row.score, 1),
            size=TEXT_PT,
            color=t.dark if prioritaire else t.grey,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
        d.track(f"Score {row.ville}", fr(row.score, 1), "city_scoring.csv : score")
    deck.frame_label(left + 0.1, y0 - 0.01, CHART_W - 0.1, row_h * len(top) + 0.02)
    dordrecht = hubs["commune_hub_le_plus_proche"].value_counts()
    hub, count = dordrecht.index[0], int(dordrecht.iloc[0])
    d.track(
        "Villes dont Dordrecht est le hub le plus proche",
        f"{count} / {len(hubs)}",
        "distance_hub.csv : commune_hub_le_plus_proche",
    )
    deck.insight(
        f"**{hub}** est le hub le plus proche de **{count} villes sur {len(hubs)}** ; "
        f"le top {len(top)} en est à **{fr(distance_top, 0)} km** en moyenne."
    )
    deck.footer(
        "city_scoring (loyers et revenus simulés) ; "
        f"{d.guide_period('Densité concurrentielle')} ; © contributeurs OpenStreetMap (ODbL) ; "
        f"{DESTATIS} ; itinéraires OSRM",
        True,
    )


def slide_7(deck: Deck) -> None:
    d = deck.data
    cases = d.frame("business_case")
    grid = d.frame("sensibilite_payback")
    decision = d.config.get("decision") or {}
    conditions = decision.get("conditions") or {}
    etp, ratio = conditions.get("nb_etp"), conditions.get("ca_m2_min_vs_france")
    deck.new_slide(7, 4)
    deck.title("Le payback dépend de l'effectif et du CA/m²")
    opening = d.config["business_case_allemagne"]["annee_premiere_ouverture"]
    payback_name = "Payback (scénario pessimiste) : Centre commercial"
    horizon = int(cases["horizon_annees"].iloc[0]) if cases is not None else None
    kpis = d.frame("kpi_summary")
    seuil_text = None
    if kpis is not None:
        match = kpis[(kpis["kpi"] == payback_name) & (kpis["pays"] == TARGET)]
        seuil_text = match["seuil"].iloc[0] if not match.empty else None
    seuil = float(re.search(r"(\d+)", seuil_text).group(1)) if seuil_text else None
    if horizon and seuil and d.kpi(payback_name) is None:
        months = horizon * 12
        value = d.track(
            "Payback pessimiste CC",
            f"> {fr(months, 0)} mois",
            kpi_source(payback_name) + " : vide = non atteint ; business_case.csv : horizon_annees",
        )
        variation = Variation(f"non atteint sur {horizon} ans", False)
    else:
        value, variation = d.lack("payback pessimiste et seuil"), None
    deck.card(
        MARGIN,
        CONTENT_TOP,
        CARD_W,
        2.1,
        f"Payback pessimiste · centre commercial · Allemagne {opening}",
        value,
        variation,
        "Simulé",
    )
    occupancy_name = (
        "Coût d'occupation (loyer + charges ÷ CA, scénario central) : Centre commercial"
    )
    occupancy = d.kpi(occupancy_name)
    limit = d.config["go_no_go"]["cout_occupation_max_pct_ca"]
    if occupancy is not None:
        shown = d.track(
            "Coût d'occupation central CC", f"{fr(occupancy)} %", kpi_source(occupancy_name)
        )
        variation = signed_gap(occupancy, limit, "pt", f"seuil {fr(limit, 0)} %", False)
    else:
        shown, variation = d.lack("coût d'occupation central CC"), None
    deck.card(
        MARGIN,
        CONTENT_TOP + 2.25,
        CARD_W,
        2.1,
        f"Coût d'occupation central · % CA HT · Allemagne {opening}",
        shown,
        variation,
        "Simulé",
    )
    deck.chart_title("Payback pessimiste, en mois · centre commercial · Allemagne")
    if grid is None or etp is None or ratio is None:
        deck.text(
            CHART_X,
            3,
            5,
            0.5,
            d.lack("sensibilite_payback.csv ou section decision"),
            role="graphique",
        )
    else:
        shown_cell = draw_heatmap(deck, grid, seuil or 36, etp, ratio)
        if shown_cell is not None:
            d.track(
                "Payback à la condition de la section decision",
                f"{fr(shown_cell, 1)} mois",
                "sensibilite_payback.csv : nb_etp, ratio_ca_m2_vs_france de la section decision",
            )
    gain = round((ratio - 1) * 100) if ratio else None
    cell = None
    if grid is not None and etp is not None and ratio is not None:
        match = grid[
            (grid["nb_etp"].round(2) == round(etp, 2))
            & (grid["ratio_ca_m2_vs_france"].round(2) == round(ratio, 2))
        ]
        cell = float(match["payback_mois"].iloc[0]) if not match.empty else None
    if cell is not None:
        deck.insight(
            f"Avec **{fr(etp, 0)} ETP** et un CA/m² supérieur de **{fr(gain, 0)} %** à la "
            f"France, le payback passe à **{fr(cell, 1)} mois**."
        )
    else:
        deck.insight(d.lack("payback de la condition (sensibilite_payback)"))
    if cell is not None and seuil and horizon:
        deck.notes(
            "Jean-Li, 45 s. Le business case d'un magasin type, en données simulées. Le coût "
            "d'occupation en centre commercial, dans le scénario central, est juste sous le "
            f"seuil de {fr(limit, 0)} %. En revanche, dans le scénario pessimiste, celui sur "
            "lequel nous jugeons le payback, le magasin type, avec l'effectif moyen de la "
            f"France, ne rembourse pas son investissement en {horizon} ans. La grille montre ce "
            "qui le fait basculer : l'effectif et le CA au mètre carré. Avec "
            f"{fr(etp, 0)} ETP et un CA/m² supérieur de {fr(gain, 0)} % à la France, le payback "
            f"passe à {fr(cell, 1)} mois, sous le seuil de {fr(seuil, 0)} mois. Briac va vous "
            "montrer comment l'IA commente ces chiffres."
        )
    deck.footer(
        "business_case, sensibilite_payback "
        "(payback = investissement ÷ résultat annuel, montée en charge incluse)",
        True,
    )


def draw_heatmap(
    deck: Deck, grid: pd.DataFrame, seuil: float, etp: float, ratio: float
) -> float | None:
    """Payback by staff (rows) and CA/m² vs France (columns), with the type store at the
    bottom. Green: at or below the threshold; grey: above it."""
    d, t = deck.data, deck.theme
    shown = d.config["slides"]["sensibilite_affichee"]
    rows = [float(v) for v in shown["nb_etp"]]
    cols = [float(v) for v in shown["ratio_ca_m2_vs_france"]]
    base_case = grid[grid["est_cas_business_case"].astype(str).str.lower() == "true"]
    base_etp = float(base_case["nb_etp"].iloc[0]) if not base_case.empty else None
    if base_etp is not None:
        rows.append(base_etp)
    left, top = CHART_X + 1.95, CONTENT_TOP + 1.2
    cell_w = (CHART_W - 1.95) / len(cols)
    cell_h = (CONTENT_BOTTOM - top) / len(rows)
    deck.text(
        CHART_X,
        CONTENT_TOP + 0.38,
        CHART_W,
        0.34,
        f"Colonnes : CA/m² rapporté à la France · vert : ≤ {fr(seuil, 0)} mois (seuil)",
        size=TEXT_PT,
        color=t.grey,
        role="graphique",
    )
    for j, col in enumerate(cols):
        deck.text(
            left + j * cell_w,
            top - 0.42,
            cell_w,
            0.38,
            f"× {fr(col)}",
            size=TEXT_PT,
            bold=True,
            align=PP_ALIGN.CENTER,
            role="graphique",
        )
    highlighted, frame = None, None
    for i, nb in enumerate(rows):
        label = f"{fr(nb)} ETP" + (" (type)" if base_etp is not None and nb == base_etp else "")
        deck.text(
            CHART_X,
            top + i * cell_h,
            1.9,
            cell_h,
            label,
            size=TEXT_PT,
            bold=True,
            align=PP_ALIGN.RIGHT,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
        for j, col in enumerate(cols):
            match = grid[
                (grid["nb_etp"].round(4) == round(nb, 4))
                & (grid["ratio_ca_m2_vs_france"].round(2) == round(col, 2))
            ]
            value = match["payback_mois"].iloc[0] if not match.empty else None
            if match.empty:
                text, fill, colour = MISSING, t.white, t.missing
                d.lack(f"payback {nb} ETP × {col}")
            elif pd.isna(value):
                text, fill, colour = "> 10 ans", t.light, t.grey
            else:
                ok = value <= seuil
                text, fill, colour = (
                    fr(value, 1),
                    (t.green if ok else t.light),
                    (t.white if ok else t.dark),
                )
            x, y = left + j * cell_w, top + i * cell_h
            deck.rect(x + 0.03, y + 0.03, cell_w - 0.06, cell_h - 0.06, fill=fill)
            deck.text(
                x,
                y,
                cell_w,
                cell_h,
                text,
                size=TEXT_PT,
                bold=True,
                color=colour,
                align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE,
                role="graphique",
            )
            if (
                round(nb, 2) == round(etp, 2)
                and round(col, 2) == round(ratio, 2)
                and value is not None
                and not pd.isna(value)
            ):
                highlighted = float(value)
                frame = (x - 0.05, y - 0.05, cell_w + 0.1, cell_h + 0.1)
    if frame:
        deck.frame_label(*frame)
    return highlighted


def slide_8(deck: Deck) -> None:
    d, t = deck.data, deck.theme
    comments = d.frame("ai_commentary")
    deck.new_slide(
        8,
        4,
        notes=(
            "Briac, 45 s, puis démo. Les commentaires du dashboard sont rédigés par un modèle de "
            "langage, à partir des seules lignes de kpi_summary de la page et du filtre. Ensuite, "
            "le code relit chaque texte : tout nombre absent des données est refusé et le texte "
            "est régénéré. Le garde-fou vérifie les chiffres, pas le raisonnement : la relecture "
            "humaine reste indispensable. Démo : dans le dashboard, page Où s'implanter, "
            "choisissez Berlin puis Dortmund, le commentaire change avec le filtre. Si la démo "
            "échoue, la capture ci-contre montre le commentaire de Dortmund."
        ),
    )
    deck.title("L'IA rédige, le code vérifie chaque chiffre")
    if comments is not None:
        dashboard = comments[~comments["page"].str.startswith("Slide")]
        verified = int(dashboard["verifie"].astype(str).str.lower().eq("true").sum())
        total = len(dashboard)
        value = d.track(
            "Commentaires du dashboard vérifiés",
            f"{verified} / {total}",
            "ai_commentary.csv : verifie, pages du dashboard",
        )
        variation = Variation(
            f"{fr(verified / total * 100, 0)} % des textes affichés", verified == total
        )
    else:
        value, variation = d.lack("ai_commentary.csv"), None
    deck.card(
        MARGIN,
        CONTENT_TOP,
        CARD_W,
        2.1,
        "Commentaires du dashboard aux chiffres vérifiés",
        value,
        variation,
        None,
    )
    steps = ["kpi_summary", "Modèle de langage", "Vérification des chiffres", "Dashboard"]
    deck.chart_title("Du KPI au commentaire affiché")
    step_w, gap = (CHART_W - 3 * 0.35) / 4, 0.35
    y = CONTENT_TOP + 0.5
    for i, step in enumerate(steps):
        x = CHART_X + i * (step_w + gap)
        fill = t.pale_green if i == 2 else t.light
        deck.rect(x, y, step_w, 0.9, fill=fill, rounded=True)
        deck.text(
            x,
            y,
            step_w,
            0.9,
            step,
            size=TEXT_PT,
            bold=True,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            role="graphique",
        )
        if i:
            deck.line(x - gap + 0.03, y + 0.45, x - 0.03, y + 0.45, t.grey, arrow=True)
    check_x = CHART_X + 2 * (step_w + gap)
    deck.frame_label(
        check_x - 0.06,
        y - 0.06,
        step_w + 0.12,
        1.02,
        "Nombre absent : texte refusé",
        label_above=False,
    )
    # The screenshot of the dashboard, with a two-line excerpt of the generated text beside it
    # (Jean-Li, 13/11/2026): the first sentence, the key message.
    box_y = y + 1.55
    box_h = CONTENT_BOTTOM - box_y
    excerpt = None
    if comments is not None:
        row = comments[
            (comments["page"] == "Où s'implanter") & (comments["valeur_filtre"] == "Dortmund")
        ]
        if not row.empty and str(row["verifie"].iloc[0]).lower() == "true":
            candidate = re.split(r"(?<=[.!?])\s", str(row["texte"].iloc[0]).strip())[0]
            if not FORBIDDEN_BEFORE_DECISION.search(candidate):
                excerpt = candidate
    text_x, text_w = CHART_X, CHART_W
    if CAPTURE_DORTMUND.exists():
        picture = deck.picture(CAPTURE_DORTMUND, CHART_X, box_y, height=box_h)
        if picture.width > Inches(CHART_W * 0.62):
            ratio = Inches(CHART_W * 0.62) / picture.width
            picture.width, picture.height = Inches(CHART_W * 0.62), int(picture.height * ratio)
        text_x = CHART_X + picture.width / 914400 + 0.25
        text_w = CHART_X + CHART_W - text_x
    else:
        d.lack("capture du dashboard, page Où s'implanter, Dortmund (slides/assets/)")
    deck.rect(text_x, box_y, text_w, box_h, fill=t.pale_green, line=t.border, rounded=True)
    deck.text(
        text_x + 0.2,
        box_y + 0.12,
        text_w - 0.4,
        0.36,
        "Commentaire IA · Dortmund (extrait)",
        bold=True,
        role="graphique",
    )
    deck.text(
        text_x + 0.2,
        box_y + 0.55,
        text_w - 0.4,
        box_h - 0.65,
        f"« {excerpt} »" if excerpt else d.lack("commentaire Dortmund vérifié, sans verdict"),
        italic=True,
        role="capture",
    )
    deck.insight(
        "Le garde-fou vérifie **les chiffres** ; la relecture humaine reste **indispensable**."
    )
    deck.footer("ai_commentary.csv ; src/ai/commentary.py (garde-fou)", True)


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def decision_case(d: Data) -> tuple[float | None, float | None]:
    """(CA/m² in €, payback in months) of the condition of the decision section."""
    conditions = (d.config.get("decision") or {}).get("conditions") or {}
    grid = d.frame("sensibilite_payback")
    etp, ratio = conditions.get("nb_etp"), conditions.get("ca_m2_min_vs_france")
    if grid is None or etp is None or ratio is None:
        return None, None
    match = grid[
        (grid["nb_etp"].round(2) == round(etp, 2))
        & (grid["ratio_ca_m2_vs_france"].round(2) == round(ratio, 2))
    ]
    if match.empty:
        return None, None
    return float(match["ca_m2_eur"].iloc[0]), float(match["payback_mois"].iloc[0])


def slide_9(deck: Deck) -> None:
    """The decision, revealed here only: the six criteria with their result, then the verdict."""
    d, t = deck.data, deck.theme
    decision = d.config.get("decision") or {}
    deck.new_slide(9, 5)
    deck.title("La recommandation au Comex")
    verdict = decision.get("verdict")
    verdict = (
        d.track("Verdict", verdict, "config/hypotheses.yaml : decision.verdict")
        if verdict
        else d.lack("decision.verdict")
    )
    parts = verdict.split(",", 1)
    content = f"{parts[0]},**{parts[1]}**" if len(parts) == 2 else verdict
    box = deck.text(
        MARGIN, 1.42, WIDTH - 2 * MARGIN, 0.85, content, size=44, color=t.dark, role="verdict"
    )
    runs = box.text_frame.paragraphs[0].runs
    if len(runs) == 2:
        runs[1].font.color.rgb = t.green
    rows = results(d)
    header = ("Critère", "Seuil", "Allemagne", "Verdict")
    widths = (3.3, 1.35, WIDTH - 2 * MARGIN - 6.5, 1.85)
    top, height = 2.3, 0.54
    for r, row in enumerate([header] + rows):
        y = top + r * height
        fill = t.green if r == 0 else (t.white if r % 2 else t.pale_green)
        deck.rect(MARGIN, y, WIDTH - 2 * MARGIN, height, fill=fill)
        x = MARGIN
        for c, cell in enumerate(row):
            colour = t.dark
            if r and c == 3:
                colour = t.green if "NO-GO" not in cell else t.dark
            deck.text(
                x + 0.1,
                y,
                widths[c] - 0.15,
                height,
                cell,
                size=TEXT_PT,
                bold=(r == 0 or c == 3),
                color=colour,
                anchor=MSO_ANCHOR.MIDDLE,
                role="graphique",
            )
            x += widths[c]
    blocking = [row[0] for row in rows if "NO-GO" in row[3]]
    frame_rows = [i for i, row in enumerate(rows, start=1) if "NO-GO" in row[3]]
    if frame_rows:
        first, last = min(frame_rows), max(frame_rows)
        deck.frame_label(
            MARGIN - 0.05,
            top + first * height - 0.04,
            WIDTH - 2 * MARGIN + 0.1,
            (last - first + 1) * height + 0.08,
        )
    deck.insight(
        (
            "Le NO-GO tient à "
            f"**{' et '.join(lower_first(label.split(',')[0]) for label in blocking)}** ; "
            "il se lève sous conditions."
            if blocking
            else "Tous les critères respectent leur seuil."
        ),
        y=6.32,
    )
    deck.notes(
        "Aurélie, 45 s. Voici notre recommandation, que nous n'avons pas affichée avant pour "
        "laisser parler les faits. Sur les six critères fixés à l'avance, le marché, le prix, "
        "la marge et le catalogue respectent leur seuil. Deux critères bloquent : le loyer "
        "rapporté au CA en centre-ville, et surtout le remboursement de l'investissement dans "
        "le scénario pessimiste, non atteint sur l'horizon du modèle. En l'état, notre réponse "
        "est donc non. Mais ce NO-GO peut se lever : c'est l'objet de la slide suivante."
    )
    deck.footer(
        "kpi_summary (Allemagne ; coûts et ventes simulés) ; kpi_guide (seuils, README 4.2) ; "
        "config/hypotheses.yaml (section decision)",
        True,
    )


def slide_10(deck: Deck) -> None:
    """The conditions that lift the NO-GO, the pilot and the next steps."""
    d, t = deck.data, deck.theme
    decision = d.config.get("decision") or {}
    conditions = decision.get("conditions") or {}
    levers = decision.get("leviers_secondaires") or {}
    plan = (d.config.get("slides") or {}).get("pilote") or {}
    cities = d.frame("city_scoring")
    deck.new_slide(10, 5)
    target, payback = decision_case(d)
    etp, ratio = conditions.get("nb_etp"), conditions.get("ca_m2_min_vs_france")
    gain = fr((ratio - 1) * 100, 0) if ratio else MISSING
    deck.title(
        f"Le GO tient à un format allégé : {fr(etp, 0) if etp else MISSING} ETP, "
        f"CA/m² France + {gain} %"
    )
    tiles = [
        ("Format", conditions.get("format") or d.lack("decision.conditions.format")),
        (
            "Effectif",
            (
                f"≈ {fr(etp, 0)} ETP (≤ {fr(conditions['nb_etp_max'])})"
                if etp and conditions.get("nb_etp_max")
                else d.lack("effectif")
            ),
        ),
        (
            "CA/m²",
            (
                f"≥ France + {gain} % · {fr(target, 0)} €/m²\npayback {fr(payback, 1)} mois"
                if ratio and target and payback
                else d.lack("CA/m² cible")
            ),
        ),
        (
            "Villes",
            f"{len(conditions.get('villes') or [])} : " + ", ".join(conditions.get("villes") or []),
        ),
        ("Hub", conditions.get("hub") or d.lack("hub")),
    ]
    if target:
        d.track(
            "CA/m² cible",
            f"{fr(target, 0)} €/m²",
            "sensibilite_payback.csv : ca_m2_eur, condition de la section decision",
        )
    if payback:
        d.track(
            "Payback à la condition",
            f"{fr(payback, 1)} mois",
            "sensibilite_payback.csv : payback_mois",
        )
    widths = [2.05, 2.05, 3.5, 2.85, 1.4]
    x, y = MARGIN, CONTENT_TOP + 0.1
    for (label, value), w in zip(tiles, widths):
        deck.rect(x, y, w, 1.35, fill=t.pale_green, rounded=True)
        deck.text(x + 0.12, y + 0.08, w - 0.24, 0.35, label, color=t.grey, role="carte")
        deck.text(x + 0.12, y + 0.42, w - 0.24, 0.9, value, size=TEXT_PT, bold=True, role="carte")
        x += w + 0.1
    deck.frame_label(MARGIN - 0.06, y - 0.06, sum(widths) + 0.4 + 0.12, 1.47)
    lever = levers.get("preference_vietnam_gain_marge_pts")
    if lever is not None:
        d.track(
            "Levier Vietnam",
            f"+{fr(lever, 1)} pt",
            "config/hypotheses.yaml : decision.leviers_secondaires",
        )
    deck.text(
        MARGIN,
        y + 1.55,
        WIDTH - 2 * MARGIN,
        0.4,
        (
            f"Levier secondaire : préférence Vietnam, **+{fr(lever, 1)} pt** de marge, "
            "insuffisant seul"
            if lever is not None
            else d.lack("levier Vietnam")
        ),
        role="carte",
    )
    # Plan: pilot, then milestones in €/m².
    stores = plan.get("nb_magasins")
    pilot = (
        list(cities.sort_values("rang")["ville"].head(stores))
        if cities is not None and stores
        else []
    )
    steps = [
        f"Pilote : {fr(stores, 0)} magasins\n{', '.join(pilot)}" if pilot else d.lack("pilote")
    ]
    milestones = plan.get("jalons") or []
    others = len(conditions.get("villes") or []) - len(pilot)
    for index, milestone in enumerate(milestones):
        if target:
            amount = target * milestone["pct_ca_m2_cible"] / 100
            then = (
                f" → {others} autres villes" if index == len(milestones) - 1 and others > 0 else ""
            )
            steps.append(
                f"{milestone['mois']} mois : CA/m² ≥ {fr(amount, 0)} €/m²"
                f"\n{milestone['pct_ca_m2_cible']} % de la cible{then}"
            )
            d.track(
                f"Jalon {milestone['mois']} mois",
                f"{fr(amount, 0)} €/m²",
                "slides.pilote.jalons × CA/m² cible (sensibilite_payback)",
            )
    deck.text(MARGIN, y + 2.15, 6, 0.36, "Plan de pilote", bold=True, role="graphique")
    x, sy, w = MARGIN, y + 2.6, (WIDTH - 2 * MARGIN - 0.5 * (len(steps) - 1)) / len(steps)
    for i, step in enumerate(steps):
        deck.rect(x, sy, w, 1.0, fill=t.white, line=t.green, rounded=True, width=1.5)
        deck.text(
            x + 0.1,
            sy,
            w - 0.2,
            1.0,
            step,
            size=TEXT_PT,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            role="carte",
        )
        if i:
            deck.line(x - 0.47, sy + 0.5, x - 0.03, sy + 0.5, t.green, width=2, arrow=True)
        x += w + 0.5
    deck.insight(
        f"Next steps : valider **{fr(etp, 0) if etp else MISSING} ETP** avec les opérations, "
        "prouver l'origine Vietnam, acheter des données de marché.",
        y=6.15,
    )
    if etp and ratio and pilot:
        deck.notes(
            "Aurélie, 45 s. Le NO-GO se lève sous conditions, toutes chiffrées : un format "
            f"{str(conditions.get('format', '')).lower()}, environ {fr(etp, 0)} ETP au lieu de "
            "l'effectif moyen de la France, un CA au mètre carré au moins égal à celui de la "
            f"France plus {gain} %, dans les {len(conditions.get('villes') or [])} villes du "
            f"classement, approvisionnées depuis {conditions.get('hub')}. La préférence "
            "douanière Vietnam aide, sans suffire seule. Nous proposons un pilote de "
            f"{len(pilot)} magasins à {' et '.join(pilot)}, avec deux points d'étape chiffrés "
            "en euros par mètre carré, avant d'ouvrir les autres villes. Merci, nous prenons "
            "vos questions."
        )
    deck.footer(
        "config/hypotheses.yaml (sections decision et slides) ; sensibilite_payback ; "
        "city_scoring ; README 4.4",
        True,
    )


def slide_11(deck: Deck) -> None:
    t = deck.theme
    deck.new_slide(11, None)
    deck.title("Annexe · Limites assumées")
    limits = [
        "Coûts et ventes simulés",
        "Eurostat provisoire, toutes chaussures",
        "Préférence Vietnam à vérifier",
        "Effectif minimal à valider",
        "Scénario fictif",
    ]
    for i, limit in enumerate(limits):
        y = CONTENT_TOP + 0.2 + i * 0.82
        deck.rect(MARGIN, y, 0.12, 0.6, fill=t.green)
        deck.text(
            MARGIN + 0.35,
            y,
            9,
            0.6,
            limit,
            size=TEXT_PT + 4,
            anchor=MSO_ANCHOR.MIDDLE,
            role="courant",
        )
    etp = ((deck.data.config.get("decision") or {}).get("conditions") or {}).get("nb_etp")
    effectif = f"de {fr(etp, 0)} ETP " if etp else ""
    deck.notes(
        "Annexe, pour les questions. Nos limites sont assumées et écrites : les coûts et les "
        "ventes sont simulés, calibrés sur des ordres de grandeur publics ; les données "
        "Eurostat allemandes sont provisoires et couvrent toutes les chaussures, pas notre "
        "segment ; la préférence douanière Vietnam suppose de prouver l'origine des produits ; "
        f"l'effectif minimal {effectif}doit être validé avec les opérations ; enfin, le "
        "scénario est fictif : Crocs possède déjà des boutiques en Allemagne, que nous traitons "
        "comme un indice que le marché existe."
    )
    deck.footer("README 3.4 et 4.4 ; docs/ENSEIGNEMENTS.md", True)


SLIDES = (
    slide_1,
    slide_2,
    slide_3,
    slide_4,
    slide_5,
    slide_6,
    slide_7,
    slide_8,
    slide_9,
    slide_10,
    slide_11,
)


# --------------------------------------------------------------------------------------
# Checks, build, export
# --------------------------------------------------------------------------------------
def slide_texts(prs, roles=None):
    """(slide number, role, text) of every text shape."""
    for number, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                if roles is None or shape.name in roles:
                    yield number, shape.name, shape.text_frame.text


def count_words(text: str) -> int:
    """Words of running text; a number ('100,85', '565 010', '128/128') counts as one."""
    number = r"\d+(?:[\s\u00a0,./]\d+)*"
    return len(re.findall(rf"{number}|[^\W\d_]+(?:['’-][^\W\d_]+)*", text))


def check(prs) -> list[str]:
    """The checks of the brief that the code can make; empty when all pass."""
    problems = []
    for number, role, text in slide_texts(prs):
        if number < DECISION_SLIDE and FORBIDDEN_BEFORE_DECISION.search(text):
            problems.append(
                f"slide {number} : « {FORBIDDEN_BEFORE_DECISION.search(text).group(0)} » "
                "avant la décision"
            )
    words: dict[int, int] = {}
    for number, _, text in slide_texts(prs, roles={"titre", "insight", "courant"}):
        words[number] = words.get(number, 0) + count_words(text)
    for number, count in sorted(words.items()):
        if count > MAX_RUNNING_WORDS:
            problems.append(
                f"slide {number} : {count} mots de texte courant (> {MAX_RUNNING_WORDS})"
            )
    for number, slide in enumerate(prs.slides, start=1):
        notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
        count = len(notes.split())
        if not 60 <= count <= 120:
            problems.append(f"slide {number} : notes de {count} mots (60 à 120)")
    return problems


def build(out_dir: Path = OUT_DIR, data: Data | None = None) -> tuple[Path, Data, list[str]]:
    data = data or Data()
    deck = Deck(data, load_theme(), find_logo())
    for make in SLIDES:
        make(deck)
    properties = deck.prs.core_properties  # replace the library's sample metadata
    properties.title = "Crocs France : ouvrir un réseau en propre en Allemagne ?"
    properties.subject = f"Comex Crocs France · {readme_period()}"
    properties.author = ", ".join(readme_team())
    properties.last_modified_by = ""
    properties.comments = ""
    properties.created = properties.modified = datetime.now().replace(microsecond=0)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{DECK_NAME}.pptx"
    deck.prs.save(path)
    data.write_controls(out_dir / "controle_chiffres.csv")
    return path, data, check(deck.prs)


def soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    windows = Path("C:/Program Files/LibreOffice/program/soffice.exe")
    return found or (str(windows) if windows.exists() else None)


def export_pdf(pptx: Path) -> Path | None:
    """PDF with LibreOffice, then one PNG per slide with pdftoppm, when they are installed."""
    office = soffice()
    if office is None:
        print("LibreOffice introuvable : exporter le PDF depuis PowerPoint (Fichier > Exporter).")
        return None
    subprocess.run(
        [office, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)],
        check=True,
        capture_output=True,
    )
    pdf = pptx.with_suffix(".pdf")
    if shutil.which("pdftoppm"):
        previews = pptx.parent / "apercus"
        previews.mkdir(exist_ok=True)
        for old in previews.glob("slide-*.png"):
            old.unlink()
        subprocess.run(
            ["pdftoppm", "-r", "80", "-png", str(pdf), str(previews / "slide")], check=True
        )
    else:
        print("pdftoppm introuvable : aperçus PNG non générés.")
    return pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Slides de l'oral Comex (T13).")
    parser.add_argument("--no-pdf", action="store_true", help="écrire le .pptx seulement")
    args = parser.parse_args()
    path, data, problems = build()
    print(f"Slides : {path.relative_to(REPO_ROOT)}")
    if not args.no_pdf:
        pdf = export_pdf(path)
        if pdf:
            print(f"PDF : {pdf.relative_to(REPO_ROOT)}")
    print(f"Liste de contrôle : {len(data.controls)} chiffres, slides/controle_chiffres.csv")
    for line in data.missing:
        print(f"À COMPLÉTER, {line}")
    for problem in problems:
        print(f"CONTRÔLE : {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
