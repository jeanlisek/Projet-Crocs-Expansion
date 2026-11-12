"""T9: AI commentary of the dashboard, one text per page and per filter value.

The texts are generated in advance, checked, then written to data/gold/ai_commentary.csv
and loaded into the warehouse, from which `make exports` writes the versioned CSV read by
Power BI. The dashboard shows the row of the active filter (join on page + valeur_filtre):
it never calls the model, so the demo needs neither the network nor a key.

Guard rail (docs/equipe/briac.md): the model only receives the rows of the page and of the
filter concerned. Every number of the generated text must be a number of that input, rounded
or not; any other number triggers one regeneration, then `verifie = false`.

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
NO_FILTER = "aucun"
ALL_VALUES = "tous"
TARGET_COUNTRY = "DE"
MARKET_AXES = ("Marché", "Prix")
BUSINESS_AXIS = "Rentabilité"
COMEX_QUESTION = (
    "L'ouverture d'un réseau de magasins Crocs en propre en Allemagne sur 2027-2029 "
    "est-elle réalisable et rentable ?"
)

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
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return str(value)


def render_kpi(row: dict) -> str:
    """One row of kpi_summary, with every column of the contract."""
    value = format_value(row["valeur"])
    if value is None:
        value = MISSING_PAYBACK if row["kpi"].startswith("Payback") else MISSING_VALUE
    else:
        unit = row["unite"] or ""
        # A TCAM is a yearly mean rate: "3,89 %" alone reads as a total growth.
        if "TCAM" in row["kpi"] and unit == "%":
            unit = "% par an"
        value = f"{value} {unit}".strip()
    origin = ORIGIN_LABELS.get(row["origine_donnees"], row["origine_donnees"])
    return (
        f"- {row['kpi']} | axe : {row['axe']} | valeur : {value} | "
        f"seuil : {row['seuil'] or 'aucun'} | verdict : {row['statut_go']} | "
        f"statut : {row['statut_epistemique']} | données : {origin}"
    )


def render_record(row: dict) -> tuple[str, ...]:
    """One row of a gold view other than kpi_summary, one line per column."""
    lines = []
    for column, raw in row.items():
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


def _decision_items(prefix: str, value) -> list[str]:
    """Flatten the decision section, whatever its keys, into one line per value."""
    if isinstance(value, dict):
        return [
            line
            for key, item in value.items()
            for line in _decision_items(f"{prefix} / {key}", item)
        ]
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return [f"- {prefix} : " + " ; ".join(format_value(item) or "" for item in value)]
        return [line for item in value for line in _decision_items(prefix, item)]
    return [f"- {prefix} : {format_value(value) or MISSING_VALUE}"]


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


def build_requests(con: duckdb.DuckDBPyConnection, config: dict | None = None) -> list[Request]:
    """Every (page, filter value) of the dashboard, each with the rows it is allowed to see.

    `config` is the whole of config/hypotheses.yaml (read from the file when omitted).
    """
    config = config if config is not None else load_config()
    kpis = fetch_dicts(con, "SELECT * FROM kpi_summary ORDER BY axe, kpi")
    target = [row for row in kpis if row["pays"] == TARGET_COUNTRY]
    verdicts = [row["statut_go"] for row in target]
    requests = [
        Request(
            page=PAGE_SYNTHESIS,
            filtre=NO_FILTER,
            valeur_filtre=ALL_VALUES,
            question=COMEX_QUESTION,
            lines=(
                *(render_kpi(row) for row in target),
                f"- Verdicts des KPI à seuil : {verdicts.count('GO')} GO, "
                f"{verdicts.count('NO-GO')} NO-GO",
                *decision_lines(config.get(DECISION_SECTION)),
            ),
            template="synthese.md",
            # A text box of the dashboard, not a report: a longer synthesis was cut at
            # max_tokens on 12/11/2026, ending in the middle of a word.
            max_words=config["ia"]["synthese_mots_max"],
        )
    ]

    page_words = config["ia"]["commentaire_mots_max"]
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
                lines=tuple(render_kpi(row) for row in rows),
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
                lines=(*reading, *render_record(city), *criterion_ranks(city, cities)),
                max_words=page_words,
            )
        )

    scenarios = [
        row["scenario"]
        for row in fetch_dicts(con, "SELECT DISTINCT scenario FROM business_case ORDER BY 1")
    ]
    business = [row for row in target if row["axe"] == BUSINESS_AXIS]
    condition = lifting_condition(con, config.get(DECISION_SECTION))
    for scenario in scenarios:
        # The rows of this scenario, and the ones that do not depend on any (break-even).
        rows = [
            row
            for row in business
            if f"scénario {scenario})" in row["kpi"] or "scénario" not in row["kpi"]
        ]
        extra = (condition,) if condition and scenario == PAYBACK_SCENARIO else ()
        requests.append(
            Request(
                page=PAGE_BUSINESS,
                filtre="scenario",
                valeur_filtre=scenario,
                question=f"Que montre le business case allemand dans le scénario {scenario} ?",
                lines=(*(render_kpi(row) for row in rows), *extra),
                max_words=page_words,
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
        mots_max=request.max_words,
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


def _problem(text: str, truncated: bool, allowed: list[float]) -> str:
    """Why a text cannot be shown as verified; empty when it can.

    An empty text has no number at all and a truncated one may have only right numbers:
    both would pass a check of the numbers alone, so they are rejected first.
    """
    if truncated:
        return "texte tronqué"
    if not text:
        return "texte vide"
    rejected = unsupported_numbers(text, allowed)
    return f"chiffres hors données : {', '.join(rejected)}" if rejected else ""


def comment(model: Model, request: Request) -> tuple[str, bool, str]:
    """Generate one text and check it; regenerate once if it fails: (text, verified, why)."""
    system = read_prompt("systeme.md")
    user = user_prompt(request)
    # Built from the first prompt only: the correction prompt quotes the rejected numbers,
    # which must not become allowed by being quoted.
    allowed = allowed_values(user)
    text, truncated = _attempt(model, system, user)
    problem = _problem(text, truncated, allowed)
    if problem:
        prompt = user
        rejected = [] if truncated else unsupported_numbers(text, allowed)
        if rejected:
            correction = read_prompt("correction.md").format(
                nombres=", ".join(rejected), texte=text
            )
            prompt = f"{user}\n\n{correction}"
        text, truncated = _attempt(model, system, prompt)
        problem = _problem(text, truncated, allowed)
    return text, not problem, problem


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
    for request in requests:
        text, verified, problem = comment(model, request)
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
        status = f"vérifié, {len(text)} caractères" if verified else f"NON VÉRIFIÉ ({problem})"
        print(f"{request.page:16s} {request.valeur_filtre:14s} {status}")

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
