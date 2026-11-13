"""T9: AI commentary of the dashboard, one text per page and per filter value.

The texts are generated in advance, checked, then written to data/gold/ai_commentary.csv
and loaded into the warehouse, from which `make exports` writes the versioned CSV read by
Power BI. The dashboard shows the row of the active filter (join on page + valeur_filtre):
it never calls the model, so the demo needs neither the network nor a key.

Guard rail (docs/equipe/briac.md): the model only receives the rows of the page and of the
filter concerned. Every number of the generated text must be a number of that input, rounded
or not. The code also checks the length of the text and a list of forbidden phrases
(config/hypotheses.yaml, section `ia`). A failed check triggers a regeneration, at most
`regenerations_max` times, then `verifie = false`.

The dashboard pages only state facts and gaps, to France and to the thresholds: no verdict and
no recommendation (feedback of the teacher, 13/11/2026). The recommendation, which repeats the
team's decision, is a separate text for slide 9 (page "Slide 9 (recommandation)").

Usage:  python -m src.ai.commentary [--warehouse FILE] [--out FILE] [--load-only]
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable, Protocol

import duckdb
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ENV_PATH = REPO_ROOT / ".env"
DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "gold" / "warehouse.duckdb"
DEFAULT_OUT = REPO_ROOT / "data" / "gold" / "ai_commentary.csv"

API_KEY_NAME = "ANTHROPIC_API_KEY"
TABLE = "ai_commentary"
COLUMNS = ["page", "filtre", "valeur_filtre", "texte", "verifie", "date_generation"]

# Page names and filter values are the join keys of the dashboard (docs/equipe/aurelie.md):
# the country filter sits on dim_pays[nom_pays] and the city filter on [ville].
PAGE_SYNTHESIS = "Synthèse Comex"
PAGE_MARKET = "Marché & prix"
PAGE_CITIES = "Où s'implanter"
PAGE_BUSINESS = "Business case"
# Not a page of the dashboard: the text of the recommendation slide (slide 9).
PAGE_SLIDE = "Slide 9 (recommandation)"
DASHBOARD_PAGES = (PAGE_SYNTHESIS, PAGE_MARKET, PAGE_CITIES, PAGE_BUSINESS)
NO_FILTER = "aucun"
ALL_VALUES = "tous"
TARGET_COUNTRY = "DE"
REFERENCE_COUNTRY = "FR"
MARKET_AXES = ("Marché", "Prix")
BUSINESS_AXIS = "Rentabilité"
COMEX_QUESTION = (
    "L'ouverture d'un réseau de magasins Crocs en propre en Allemagne sur 2027-2029 "
    "est-elle réalisable et rentable ?"
)
OVERVIEW_QUESTION = "Que montrent les indicateurs de l'Allemagne, axe par axe ?"

# sql/kpi/kpi_summary.sql: "vide = non atteint dans l'horizon -> NO-GO" for the payback.
MISSING_PAYBACK = "non atteint dans l'horizon"
MISSING_VALUE = "non disponible"
ORIGIN_LABELS = {"SIMULE": "simulées", "REEL": "réelles", "MIXTE": "mixtes"}

# --------------------------------------------------------------------------------------
# Numbers: extraction and check
# --------------------------------------------------------------------------------------
# A thousands separator is a space, a no-break space or a narrow no-break space followed by
# exactly three digits (French typography). Letters, commas and dots before a number mean it
# belongs to something else (an identifier such as Z001, the decimals of another number).
_SEPARATOR = "[   ]"
NUMBER_PATTERN = re.compile(
    rf"(?<![\w,.])(\d{{1,3}}(?:{_SEPARATOR}\d{{3}})+(?:[,.]\d+)?|\d+(?:[,.]\d+)?)(?!\d)"
)
# A scale word right after a number: "1,2 M€", "525 k€", "3 millions". Without one, a number
# is compared at its face value only, so that a stray "1" is never accepted as 1.2 million.
SCALE_PATTERN = re.compile(r"\s*(milliards?|Md|millions?|M|milliers?|mille|k|K)(?![a-zà-ÿ])")
SCALES = {
    "milliard": 1e9,
    "milliards": 1e9,
    "Md": 1e9,
    "million": 1e6,
    "millions": 1e6,
    "M": 1e6,
    "millier": 1e3,
    "milliers": 1e3,
    "mille": 1e3,
    "k": 1e3,
    "K": 1e3,
}


@dataclass(frozen=True)
class Number:
    """A number as written in a text: its value, its decimals and its scale word."""

    text: str
    value: float
    decimals: int
    scale: float = 1.0


def extract_numbers(text: str) -> list[Number]:
    """Every number written in a text, in French or English notation."""
    numbers = []
    for match in NUMBER_PATTERN.finditer(text):
        raw = re.sub(_SEPARATOR, "", match.group(1)).replace(",", ".")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        scale_match = SCALE_PATTERN.match(text, match.end())
        scale = SCALES[scale_match.group(1)] if scale_match else 1.0
        numbers.append(Number(match.group(1), float(raw), decimals, scale))
    return numbers


def is_supported(number: Number, allowed: list[float]) -> bool:
    """True when the number is an allowed value, possibly rounded to its written decimals.

    With a scale word, both readings are tried: "525 k€" for 525098, and "0,603 million"
    for a value given as 0,603 in a column already counted in millions.
    """
    half_unit = 0.5 * 10**-number.decimals + 1e-9
    scales = {1.0, number.scale}
    return any(
        abs(number.value - value / scale) <= half_unit for value in allowed for scale in scales
    )


def unsupported_numbers(text: str, allowed: list[float]) -> list[str]:
    """The numbers of a text that do not come from the allowed values."""
    return [n.text for n in extract_numbers(text) if not is_supported(n, allowed)]


def allowed_values(prompt: str) -> list[float]:
    """The values a text may use: every number of the prompt that was sent to the model."""
    return [n.value * n.scale for n in extract_numbers(prompt)]


# French typography: a no-break space between groups of three digits ("565 010 €"), from
# five digits on, so that a year ("2027") is never split. The no-break space keeps the
# number on one line in the text box of the dashboard.
THOUSANDS = "\u00a0"
_UNGROUPED = re.compile(r"(?<![\d,.])(\d{5,})(?!\d)")


def group_thousands(digits: str) -> str:
    """'565010' -> '565 010' (no-break space); fewer than five digits are left as they are."""
    if len(digits) < 5:
        return digits
    return f"{int(digits):,}".replace(",", THOUSANDS)


def normalize_numbers(text: str) -> str:
    """Write the thousands separator the model left out: '565010 €' -> '565 010 €'."""
    return _UNGROUPED.sub(lambda match: group_thousands(match.group(1)), text)


def count_words(text: str) -> int:
    """Words of a text; a number counts as one word ("565 010" too), a sign alone as none."""
    collapsed = NUMBER_PATTERN.sub("0", text)
    return sum(1 for token in collapsed.split() if re.search(r"\w", token))


# --------------------------------------------------------------------------------------
# Requests: one per page and filter value, built from the rows of that page only
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Request:
    """One text to generate: its join keys, its question and its input rows."""

    page: str
    filtre: str
    valeur_filtre: str
    question: str
    lines: tuple[str, ...]
    template: str = "commentaire.md"
    max_words: int | None = None
    # A sentence of the team added by the code after the text of the model, word for word.
    ending: str | None = None

    @property
    def model_words(self) -> int | None:
        """The limit given to the model: max_words, less the words of the ending."""
        if self.max_words is None:
            return None
        return self.max_words - (count_words(self.ending) if self.ending else 0)


def format_value(value) -> str | None:
    """Display a value as the model reads it: decimal comma, at most three decimals."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return group_thousands(str(int(value)))
        whole, _, decimals = f"{value:.3f}".rstrip("0").partition(".")
        return group_thousands(whole) + ("," + decimals if decimals else "")
    if isinstance(value, int):
        return group_thousands(str(value))
    return str(value)


# Position of a value against its threshold, the dashboard's wording of statut_go: a fact
# (the value is above or below a number), where GO / NO-GO is a verdict.
POSITIONS = {"GO": "seuil respecté", "NO-GO": "seuil non respecté"}
_BOUND = re.compile(r"\s*([≥≤<>])\s*(-?\d+(?:[.,]\d+)?)")


def threshold_bound(seuil: str | None) -> float | None:
    """The number of a one-sided threshold ("≥ 2 %", "≤ 36 mois"); None for a range."""
    match = _BOUND.match(seuil or "")
    return float(match.group(2).replace(",", ".")) if match else None


def gap(value: float, reference: float, unit: str | None) -> str:
    """A difference computed by the code, so that the model never computes one itself."""
    difference = round(value - reference, 2)
    if difference == 0:
        return "aucun écart"
    size = abs(difference)
    unit = unit or ""
    if unit.startswith("%"):
        unit = "point" if size < 2 else "points"
    elif unit == "indice":
        unit = "point d'indice" if size < 2 else "points d'indice"
    side = "au-dessus" if difference > 0 else "au-dessous"
    return f"{format_value(size)} {unit} {side}".replace("  ", " ")


def scenario_stem(kpi: str) -> str:
    """The name of a KPI without its scenario: one stem for central, optimiste, pessimiste."""
    return re.sub(r"scénario \w+", "scénario", kpi)


def country_stem(kpi: str) -> str:
    """The name of a KPI shared by the countries: the provisional mark is not part of it."""
    return kpi.replace(", données provisoires", "")


def scenario_thresholds(kpis: list[dict]) -> dict:
    """(country, stem) -> (threshold, scenario), for the KPIs judged on one scenario only.

    README 4.2 judges the occupancy cost on the central scenario and the payback on the
    pessimistic one: the other scenarios have no threshold of their own. Without this, the
    pessimistic page said "sans seuil fixé" for an occupancy cost of 17,92 % (13/11/2026).
    """
    thresholds = {}
    for row in kpis:
        found = re.search(r"scénario (\w+)", row["kpi"])
        if found and row["seuil"]:
            thresholds[(row["pays"], scenario_stem(row["kpi"]))] = (row["seuil"], found.group(1))
    return thresholds


def render_kpi(
    row: dict,
    verdict: bool = True,
    france: dict | None = None,
    thresholds: dict | None = None,
) -> str:
    """One row of kpi_summary, with every column of the contract.

    verdict=False is the dashboard's reading: the position against the threshold and the gap
    to it, never GO / NO-GO. `france` is the same KPI for France, given with the gap to it;
    `thresholds` comes from scenario_thresholds. Every gap is computed here, in the code.
    """
    raw = row["valeur"]
    value = format_value(raw)
    if value is None:
        value = MISSING_PAYBACK if row["kpi"].startswith("Payback") else MISSING_VALUE
    else:
        unit = row["unite"] or ""
        # A TCAM is a yearly mean rate: "3,89 %" alone reads as a total growth.
        if "TCAM" in row["kpi"] and unit == "%":
            unit = "% par an"
        value = f"{value} {unit}".strip()
    seuil = row["seuil"]
    parts = [f"- {row['kpi']}", f"axe : {row['axe']}", f"valeur : {value}"]
    reference = (thresholds or {}).get((row.get("pays"), scenario_stem(row["kpi"])))
    if seuil:
        parts.append(f"seuil : {seuil}")
    elif reference:
        seuil = reference[0]
        parts.append(f"seuil : {seuil}, jugé sur le scénario {reference[1]}")
    else:
        parts.append("seuil : aucun")
    if verdict:
        parts.append(f"verdict : {row['statut_go']}")
    elif row["statut_go"] in POSITIONS:
        parts.append(f"position : {POSITIONS[row['statut_go']]}")
    bound = threshold_bound(seuil)
    if bound is not None and raw is not None:
        parts.append(f"écart au seuil : {gap(float(raw), bound, row['unite'])}")
    if france is not None and raw is not None and france["valeur"] is not None:
        french = format_value(france["valeur"])
        parts.append(f"France : {french} {france['unite'] or ''}".rstrip())
        gap_france = gap(float(raw), float(france["valeur"]), row["unite"])
        parts.append(f"écart à la France : {gap_france}")
    origin = ORIGIN_LABELS.get(row["origine_donnees"], row["origine_donnees"])
    parts += [f"statut : {row['statut_epistemique']}", f"données : {origin}"]
    return " | ".join(parts)


def render_record(row: dict, skip: tuple[str, ...] = ()) -> tuple[str, ...]:
    """One row of a gold view other than kpi_summary, one line per column."""
    lines = []
    for column, raw in row.items():
        if column in skip:
            continue
        if column == "origine_donnees":
            lines.append(f"- données : {ORIGIN_LABELS.get(raw, raw)}")
            continue
        value = format_value(raw)
        lines.append(f"- {column} : {MISSING_VALUE if value is None else value}")
    return tuple(lines)


def fetch_dicts(con: duckdb.DuckDBPyConnection, query: str, params=()) -> list[dict]:
    result = con.execute(query, params)
    names = [column[0] for column in result.description]
    return [dict(zip(names, values)) for values in result.fetchall()]


DECISION_SECTION = "decision"
DECISION_OPEN = (
    "- décision : non arrêtée par l'équipe ; la grille du README fixe un seuil par critère "
    "mais aucune règle pour combiner les critères"
)


# Words for the keys of the decision section. A bare key was misread: "ca_m2_min_vs_france :
# 1,02" became "un coût au m² d'au moins 1,02 fois le niveau France" (13/11/2026). An unknown
# key is shown as it is.
DECISION_LABELS = {
    "conditions": "conditions du GO",
    "format": "format de magasin",
    "nb_etp": "effectif par magasin, en ETP",
    "nb_etp_max": "effectif maximal par magasin, en ETP",
    "ca_m2_min_vs_france": (
        "chiffre d'affaires par m² (CA/m²) minimal, en multiple du CA/m² de la France au même "
        "format"
    ),
    "villes": "villes retenues",
    "hub": "hub logistique",
    "leviers_secondaires": "leviers secondaires",
    "preference_vietnam_gain_marge_pts": "préférence tarifaire Vietnam, gain de marge en points",
}
# The team's sentence on how the GO will be confirmed: added word for word after the text of
# the slide, never given to the model to rephrase (Jean-Li, 13/11/2026).
CONFIRMATION_KEY = "confirmation_go"


def _decision_value(key: str, value) -> str:
    text = format_value(value) or MISSING_VALUE
    if key.endswith("_vs_france") and isinstance(value, (int, float)):
        text += f" (France + {format_value(round((value - 1) * 100, 2))} %)"
    return text


def _decision_items(prefix: str, value, key: str = "") -> list[str]:
    """Flatten the decision section, whatever its keys, into one line per value."""
    if isinstance(value, dict):
        return [
            line
            for name, item in value.items()
            if name != CONFIRMATION_KEY
            for line in _decision_items(f"{prefix} / {DECISION_LABELS.get(name, name)}", item, name)
        ]
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return [f"- {prefix} : " + " ; ".join(format_value(item) or "" for item in value)]
        return [line for item in value for line in _decision_items(prefix, item, key)]
    return [f"- {prefix} : {_decision_value(key, value)}"]


# README 4.2: the payback criterion is judged on the pessimistic scenario.
PAYBACK_SCENARIO = "pessimiste"
SENSITIVITY_VIEW = "sensibilite_payback"
CONDITION_KEYS = ("format", "nb_etp", "ca_m2_min_vs_france")


def lifting_condition(con: duckdb.DuckDBPyConnection, decision) -> str | None:
    """The team condition that lifts the NO-GO of the payback, with the payback it gives.

    The payback is read in the sensitivity view, on the row of the conditions of the
    decision: a value of the warehouse, which the guard rail accepts, and not the figure of
    a comment of the config, which the model never receives. None without a decision, a
    complete set of conditions or a matching row.
    """
    conditions = decision.get("conditions") if isinstance(decision, dict) else None
    # Another layout of the section (a list, missing keys) gives no condition, never a crash.
    if not isinstance(conditions, dict) or any(conditions.get(k) is None for k in CONDITION_KEYS):
        return None
    objects = con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    if SENSITIVITY_VIEW not in {name for (name,) in objects}:
        return None
    rows = fetch_dicts(
        con,
        f"SELECT * FROM {SENSITIVITY_VIEW} WHERE code_pays = ? AND scenario = ? AND format = ? "
        "AND nb_etp = ? AND abs(ratio_ca_m2_vs_france - ?) < 1e-9",
        (
            TARGET_COUNTRY,
            PAYBACK_SCENARIO,
            conditions["format"],
            conditions["nb_etp"],
            conditions["ca_m2_min_vs_france"],
        ),
    )
    if not rows:
        return None
    row = rows[0]
    gain = format_value(round((row["ratio_ca_m2_vs_france"] - 1) * 100, 2))
    origin = ORIGIN_LABELS.get(row["origine_donnees"], row["origine_donnees"])
    return (
        f"- condition de l'équipe qui lève le NO-GO du payback (section decision, vue "
        f"{SENSITIVITY_VIEW}) : format {row['format']}, {format_value(row['nb_etp'])} ETP, "
        f"CA/m² au moins égal à la France + {gain} % ({format_value(row['ca_m2_eur'])} €/m²), "
        f"payback {format_value(row['payback_mois'])} mois pour un seuil {row['seuil']}, "
        f"verdict {row['statut_go']} | données : {origin}"
    )


def decision_lines(decision) -> tuple[str, ...]:
    """The decision is the team's, read from config/hypotheses.yaml (section `decision`):
    README 4.2 sets one threshold per criterion and no rule to combine them, so the model
    explains the decision and never takes it. No section yet: the decision is said open."""
    if not decision:
        return (DECISION_OPEN,)
    return tuple(_decision_items("décision retenue par l'équipe", decision))


def city_reading(n_cities: int, weights: dict) -> tuple[str, ...]:
    """How to read a line of city_scoring: without it, a note of 0 reads as a zero value.

    Source: section city_scoring of config/hypotheses.yaml (weights and their comments).
    """
    weighting = ", ".join(f"{criterion} {weight}" for criterion, weight in weights.items())
    return (
        f"- lecture des notes : chaque note va de 0 à 100 et classe les {n_cities} villes entre "
        f"elles sur un critère ; 100 = la plus favorable des {n_cities}, 0 = la moins favorable "
        f"des {n_cities}, jamais une valeur nulle",
        # One line per note: "densité moins dense = mieux" alone was read as "forte densité
        # favorable" for Dortmund (note 100, 5,8 shops per 100 000 inhabitants), 12/11/2026.
        "- note_potentiel élevée : le plus fort potentiel de clientèle",
        "- note_loyer élevée : le loyer le plus bas",
        "- note_densite élevée : le moins de magasins de chaussures par habitant, donc la "
        "concurrence la plus faible ; une note de densité élevée signifie une densité faible",
        "- note_distance élevée : la ville la plus proche d'un hub logistique",
        f"- score : moyenne des notes pondérée par {weighting}",
        "- densite_pour_100k_hab : magasins de chaussures pour 100 000 habitants",
    )


def criterion_ranks(city: dict, cities: list[dict]) -> tuple[str, ...]:
    """The rank of the city on each note, 1 being the best of the cities.

    A good overall rank says nothing of each criterion: Dortmund, 2nd, was said to have a
    "potentiel solide" with a note of 6,4 (12/11/2026). The rank on each note is a fact of
    city_scoring that leaves no room for that reading.
    """
    columns = [c for c in city if c.startswith("note_") and city[c] is not None]
    if not columns:
        return ()
    n = len(cities)
    ranks = [
        f"{column} rang {1 + sum((other[column] or 0) > city[column] for other in cities)} sur {n}"
        for column in columns
    ]
    return (f"- rang de la ville sur chaque note (rang 1 = la meilleure) : {' ; '.join(ranks)}",)


# On a Business case page, the two labels are formats of shop: the pessimistic page said
# "dans les deux villes" (13/11/2026).
FORMATS_LINE = (
    "- Centre commercial et Centre-ville désignent les deux formats de magasin comparés "
    "(deux types d'emplacement)"
)
# A team choice, not a fact of the city: a verdict the dashboard does not give.
CITY_SKIPPED = ("est_prioritaire",)


def build_requests(con: duckdb.DuckDBPyConnection, config: dict | None = None) -> list[Request]:
    """Every (page, filter value) of the dashboard, each with the rows it is allowed to see,
    then the text of slide 9.

    `config` is the whole of config/hypotheses.yaml (read from the file when omitted).
    """
    config = config if config is not None else load_config()
    decision = config.get(DECISION_SECTION)
    kpis = fetch_dicts(con, "SELECT * FROM kpi_summary ORDER BY axe, kpi")
    thresholds = scenario_thresholds(kpis)
    france = {country_stem(r["kpi"]): r for r in kpis if r["pays"] == REFERENCE_COUNTRY}

    def facts(row: dict) -> str:
        """The dashboard's reading of a row: gaps to France and to the thresholds."""
        if row["pays"] == REFERENCE_COUNTRY:
            reference = None
        else:
            reference = france.get(country_stem(row["kpi"]))
        return render_kpi(row, verdict=False, france=reference, thresholds=thresholds)

    target = [row for row in kpis if row["pays"] == TARGET_COUNTRY]
    page_words = config["ia"]["commentaire_mots_max"]
    requests = [
        Request(
            page=PAGE_SYNTHESIS,
            filtre=NO_FILTER,
            valeur_filtre=ALL_VALUES,
            question=OVERVIEW_QUESTION,
            lines=tuple(facts(row) for row in target),
            max_words=page_words,
        )
    ]

    countries = fetch_dicts(con, "SELECT code_pays, nom_pays FROM dim_pays ORDER BY nom_pays")
    for country in countries:
        rows = [
            row for row in kpis if row["pays"] == country["code_pays"] and row["axe"] in MARKET_AXES
        ]
        requests.append(
            Request(
                page=PAGE_MARKET,
                filtre="pays",
                valeur_filtre=country["nom_pays"],
                question=f"Que disent le marché et les prix pour : {country['nom_pays']} ?",
                lines=tuple(facts(row) for row in rows),
                max_words=page_words,
            )
        )

    cities = fetch_dicts(con, "SELECT * FROM city_scoring ORDER BY rang")
    reading = city_reading(len(cities), config["city_scoring"]["poids"])
    for city in cities:
        requests.append(
            Request(
                page=PAGE_CITIES,
                filtre="ville",
                valeur_filtre=city["ville"],
                question=f"Quel est l'intérêt de {city['ville']} pour un magasin Crocs ?",
                lines=(
                    *reading,
                    *render_record(city, skip=CITY_SKIPPED),
                    *criterion_ranks(city, cities),
                ),
                max_words=page_words,
            )
        )

    scenarios = [
        row["scenario"]
        for row in fetch_dicts(con, "SELECT DISTINCT scenario FROM business_case ORDER BY 1")
    ]
    business = [row for row in target if row["axe"] == BUSINESS_AXIS]
    for scenario in scenarios:
        # The rows of this scenario, and the ones that do not depend on any (break-even).
        rows = [
            row
            for row in business
            if f"scénario {scenario})" in row["kpi"] or "scénario" not in row["kpi"]
        ]
        requests.append(
            Request(
                page=PAGE_BUSINESS,
                filtre="scenario",
                valeur_filtre=scenario,
                question=f"Que montre le business case allemand dans le scénario {scenario} ?",
                lines=(FORMATS_LINE, *(facts(row) for row in rows)),
                max_words=page_words,
            )
        )

    # Slide 9: the only text with the verdicts and the team's decision.
    verdicts = [row["statut_go"] for row in target]
    condition = lifting_condition(con, decision)
    confirmation = decision.get(CONFIRMATION_KEY) if isinstance(decision, dict) else None
    requests.append(
        Request(
            page=PAGE_SLIDE,
            filtre=NO_FILTER,
            valeur_filtre=ALL_VALUES,
            question=COMEX_QUESTION,
            lines=(
                *(render_kpi(row, thresholds=thresholds) for row in target),
                f"- Verdicts des KPI à seuil : {verdicts.count('GO')} GO, "
                f"{verdicts.count('NO-GO')} NO-GO",
                *decision_lines(decision),
                *((condition,) if condition else ()),
            ),
            template="synthese.md",
            # A slide, not a report: a longer synthesis was cut at max_tokens on 12/11/2026,
            # ending in the middle of a word.
            max_words=config["ia"]["synthese_mots_max"],
            ending=str(confirmation).strip() if confirmation else None,
        )
    )
    return requests


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def user_prompt(request: Request) -> str:
    return read_prompt(request.template).format(
        page=request.page,
        filtre=request.filtre,
        valeur_filtre=request.valeur_filtre,
        question=request.question,
        lignes="\n".join(request.lines) or MISSING_VALUE,
        mots_max=request.model_words,
    )


# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------
class Model(Protocol):
    def generate(self, system: str, user: str) -> str: ...


class TruncatedAnswer(Exception):
    """The model stopped at max_tokens: the text it returned is incomplete."""

    def __init__(self, text: str):
        super().__init__("réponse tronquée au plafond max_tokens")
        self.text = text


class ClaudeModel:
    """Messages API (SDK anthropic 2.x).

    The SDK retries by itself, with a growing wait, on 408, 409, 429 (rate limit) and 5xx
    (anthropic/_base_client.py, _should_retry); a 401 (bad key) or a 400 is raised at once.
    The SDK accepts no sampling parameter (no temperature, top_p, top_k nor seed): two runs
    may word a text differently, never its numbers, which the guard rail checks every time.
    Thinking tokens count toward max_tokens (SDK documentation of `thinking`): left to the
    model, the thinking may use the whole budget and leave an empty or truncated text.
    """

    def __init__(self, api_key: str, settings: dict):
        # Imported here: the tests use a stand-in model and never need the SDK.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, max_retries=settings["tentatives_max"])
        self._settings = settings

    def generate(self, system: str, user: str) -> str:
        options = {}
        if self._settings.get("reflexion"):
            options["thinking"] = {"type": self._settings["reflexion"]}
        response = self._client.messages.create(
            model=self._settings["modele"],
            max_tokens=self._settings["max_tokens"],
            system=system,
            messages=[{"role": "user", "content": user}],
            **options,
        )
        # The answer is a list of content blocks: keep the text ones, in order. Thinking
        # blocks, when there are any, are not part of the answer.
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":
            raise TruncatedAnswer(text)
        return text


class Throttled:
    """Waits between two calls of the wrapped model, as a margin below the rate limits."""

    def __init__(self, model: Model, delay: float, sleep: Callable[[float], None] = time.sleep):
        self._model = model
        self._delay = delay
        self._sleep = sleep
        self._calls = 0

    def generate(self, system: str, user: str) -> str:
        if self._calls:
            self._sleep(self._delay)
        self._calls += 1
        return self._model.generate(system, user)


def _attempt(model: Model, system: str, prompt: str) -> tuple[str, bool]:
    """One generation: (text, truncated)."""
    try:
        return model.generate(system, prompt).strip(), False
    except TruncatedAnswer as answer:
        return answer.text.strip(), True


def forbidden_phrases(text: str, page: str, rules) -> list[str]:
    """The forbidden phrases of a text, as problems: config/hypotheses.yaml, section `ia`,
    key `formulations_interdites`; each rule is a regular expression, case ignored, for every
    page ("toutes") or a list of pages."""
    problems = []
    for rule in rules or ():
        pages = rule.get("pages", "toutes")
        if pages != "toutes" and page not in pages:
            continue
        for match in re.finditer(rule["motif"], text, flags=re.IGNORECASE):
            reason = f" ({rule['raison']})" if rule.get("raison") else ""
            problems.append(f"formulation interdite « {match.group(0)} »{reason}")
    return problems


def _problems(
    text: str, truncated: bool, allowed: list[float], request: Request, rules
) -> list[str]:
    """Why a text cannot be shown as verified; empty when it can.

    An empty text has no number at all and a truncated one may have only right numbers:
    both would pass a check of the numbers alone, so they are rejected first.
    """
    if truncated:
        return ["texte tronqué"]
    if not text:
        return ["texte vide"]
    problems = []
    rejected = unsupported_numbers(text, allowed)
    if rejected:
        problems.append(f"chiffres hors données : {', '.join(rejected)}")
    limit = request.model_words
    if limit is not None and count_words(text) > limit:
        problems.append(f"{count_words(text)} mots pour {limit} au plus")
    return problems + forbidden_phrases(text, request.page, rules)


def comment(
    model: Model, request: Request, rules=(), regenerations: int = 1
) -> tuple[str, bool, str]:
    """Generate one text and check it; regenerate while a check fails, at most
    `regenerations` times: (text, verified, why). The team's ending, if any, is added last."""
    system = read_prompt("systeme.md")
    user = user_prompt(request)
    # Built from the first prompt only: the correction prompt quotes the rejected text,
    # whose numbers must not become allowed by being quoted.
    allowed = allowed_values(user)
    prompt = user
    for attempt in range(1 + regenerations):
        text, truncated = _attempt(model, system, prompt)
        text = normalize_numbers(text)
        problems = _problems(text, truncated, allowed, request, rules)
        if not problems:
            break
        # An empty or truncated text has nothing to correct: the same prompt is sent again.
        prompt = user
        if text and not truncated:
            correction = read_prompt("correction.md").format(
                problemes="\n".join(f"- {problem}" for problem in problems),
                texte=text,
                mots_max=request.model_words or "",
            )
            prompt = f"{user}\n\n{correction}"
    if request.ending and text and not truncated:
        text = f"{text} {request.ending}"
    return text, not problems, "; ".join(problems)


# --------------------------------------------------------------------------------------
# Configuration, key, files
# --------------------------------------------------------------------------------------
def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_settings(path: Path = CONFIG_PATH) -> dict:
    return load_config(path)["ia"]


def load_api_key(env_path: Path = ENV_PATH, name: str = API_KEY_NAME) -> str:
    """The key from the environment, else from .env (never versioned, see .gitignore)."""
    if os.environ.get(name):
        return os.environ[name]
    if env_path.exists():
        # utf-8-sig: Notepad on Windows may start the file with a byte order mark.
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip().strip("\"'")
    raise RuntimeError(
        f"{name} absente : ajoutez la ligne {name}=<votre clé> dans {env_path} "
        "(fichier local, jamais commité)."
    )


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_into_warehouse(csv_path: Path, warehouse: Path) -> int:
    """(Re)create the ai_commentary table from the CSV file; return its number of rows."""
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} manquant : lancez d'abord la génération")
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {TABLE} AS
            SELECT * FROM read_csv(?, header = true, quote = '"', columns = {{
                'page': 'VARCHAR', 'filtre': 'VARCHAR', 'valeur_filtre': 'VARCHAR',
                'texte': 'VARCHAR', 'verifie': 'BOOLEAN', 'date_generation': 'TIMESTAMP'
            }})
            """,
            [str(csv_path)],
        )
        return con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    finally:
        con.close()


def run(
    warehouse: Path = DEFAULT_WAREHOUSE,
    out: Path = DEFAULT_OUT,
    model: Model | None = None,
    settings: dict | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = datetime.now,
) -> list[dict]:
    """Generate and check every text, write the CSV file, load it into the warehouse."""
    if not warehouse.exists():
        raise FileNotFoundError(f"{warehouse} manquant : lancez d'abord `make all`")
    config = load_config()
    settings = settings or config["ia"]
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        requests = build_requests(con, config)
    finally:
        con.close()

    if model is None:
        model = ClaudeModel(load_api_key(), settings)
    model = Throttled(model, settings["delai_entre_appels_s"], sleep)
    stamp = now().isoformat(timespec="seconds")
    rows = []
    rules = settings.get("formulations_interdites") or ()
    regenerations = settings.get("regenerations_max", 1)
    for request in requests:
        text, verified, problem = comment(model, request, rules, regenerations)
        rows.append(
            {
                "page": request.page,
                "filtre": request.filtre,
                "valeur_filtre": request.valeur_filtre,
                "texte": text,
                "verifie": "true" if verified else "false",
                "date_generation": stamp,
            }
        )
        words = count_words(text)
        status = f"vérifié, {words} mots" if verified else f"NON VÉRIFIÉ ({problem})"
        print(f"{request.page:24s} {request.valeur_filtre:14s} {status}")

    write_csv(rows, out)
    loaded = load_into_warehouse(out, warehouse)
    checked = sum(row["verifie"] == "true" for row in rows)
    print(f"\n{checked}/{loaded} commentaires vérifiés, écrits dans : {out.resolve()}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Commentaires IA du dashboard (T9).")
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="recharge le CSV existant dans l'entrepôt, sans appeler le modèle",
    )
    args = parser.parse_args()
    if args.load_only:
        loaded = load_into_warehouse(args.out, args.warehouse)
        print(f"{loaded} commentaires rechargés dans : {args.warehouse.resolve()}")
    else:
        run(args.warehouse, args.out)


if __name__ == "__main__":
    main()
