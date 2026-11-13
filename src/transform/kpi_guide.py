"""Write data/gold/exports/kpi_guide.csv: one row per KPI of kpi_summary, with its definition.

Usage (from the repository root, after `make kpi`):
    python -m src.transform.kpi_guide [--warehouse FILE] [--out FILE]

Nothing is typed here that a document does not already say:
- definition: the header comment of the SQL view that computes the KPI (the definition the
  field dictionary shows for the view), or, for a tax, the description of its column in the
  dictionary (src/collect/dictionnaire.py);
- formula and source tables: the KPI table of the README (section 2.3), or the view header
  when the README has no row for the KPI;
- threshold: the value carried by kpi_summary, or the README Go / No-Go grid (section 4.2)
  when it differs from one country to another;
- countries, origin, format and scenario: read in kpi_summary; periods and collection dates:
  read in parametres_kpi and in the real tables.
A KPI that matches no family below stops the export: the guide never misses a KPI.
"""

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

from src.collect.dictionnaire import FIELDS
from src.transform.bronze_to_silver import REPO_ROOT
from src.transform.build_gold import DEFAULT_WAREHOUSE
from src.transform.export_gold import DEFAULT_EXPORTS_DIR

README = REPO_ROOT / "README.md"
SQL_DIR = REPO_ROOT / "sql" / "kpi"
DEFAULT_OUT = DEFAULT_EXPORTS_DIR / "kpi_guide.csv"
COLUMNS = [
    "nom",
    "axe",
    "definition",
    "formule",
    "unite",
    "perimetre",
    "source",
    "origine",
    "seuil",
]

# Base of an amount: what the README or the view header says, nothing more.
HT = "HT"
NO_BASE = "HT / TTC sans objet"
UNKNOWN_BASE = "HT ou TTC non précisé dans la source"
# Eurostat, metadata of nama_10_cp18 (« recorded at purchasers' prices ») and glossary « Purchaser
# price » (« excluding any VAT or similar tax deductible by the purchaser »): a household does not
# deduct VAT, so its consumption expenditure includes it.
EUROSTAT_METADATA = "https://ec.europa.eu/eurostat/cache/metadata/en/nama_10_cp18_esms.htm"
PURCHASER_PRICE = (
    "TTC : prix d'acquisition, hors seule TVA déductible par l'acheteur, que les ménages ne "
    "déduisent pas (métadonnées Eurostat de nama_10_cp18)"
)
# src/simulate/generate_data.py, section 7 : « marché total chaussures 2024 (Md€, prix de vente au
# détail TTC) » ; section 8 : parts de marché en valeur de ce segment.
SIMULATED_RETAIL = "TTC : prix de vente au détail, jeu simulé (src/simulate/generate_data.py)"
COUNTRY_LEVEL = "sans objet (niveau pays)"


@dataclass(frozen=True)
class Family:
    """How to describe every KPI whose name matches `pattern`."""

    pattern: str
    view: str  # SQL view that computes the KPI
    readme: str | None  # KPI name in README 2.3 (formula, tables), None if absent
    base: str  # HT, NO_BASE or UNKNOWN_BASE
    period: str  # template filled from parametres_kpi and the collection dates
    # Sentences quoted as the definition: (view, start of the sentence), None = first sentence.
    # Prefixed by « France : » / « Allemagne : » when `by_country` is set.
    definition: tuple[tuple[str, str | None], ...] = ()
    by_country: tuple[str, ...] = ()
    keep_start: bool = False  # quote the sentence from its start instead of after it
    city: str = COUNTRY_LEVEL
    grid: str | None = None  # criterion name in README 4.2
    tax_column: str | None = None  # column of taxes_reference described in FIELDS
    tax_simulated: str | None = None  # same tax in fact_fiscalite (comparison rows)
    tables: str | None = None  # source tables when the README has no row for the KPI


FAMILIES = [
    Family(
        r"^Croissance du secteur",
        "kpi_croissance_secteur",
        "Croissance du secteur",
        SIMULATED_RETAIL,
        "TCAM {tcam_debut}-{tcam_fin}, années observées",
        grid="Croissance du segment en Allemagne",
    ),
    Family(
        r"^Croissance des dépenses des ménages",
        "kpi_croissance_depenses_chaussures",
        None,
        PURCHASER_PRICE,
        "TCAM {tcam_debut}-{tcam_fin} ; collecte Eurostat du {eurostat}",
        tables=(
            f"`eurostat_series` (Eurostat, jeu `nama_10_cp18`, métadonnées : {EUROSTAT_METADATA})"
        ),
    ),
    Family(
        r"^Part de marché Crocs",
        "kpi_part_de_marche",
        "Part de marché Crocs en France",
        SIMULATED_RETAIL,
        "année {annee}",
    ),
    Family(
        r"^Part de marché ",
        "kpi_part_de_marche",
        "Part de marché d'un concurrent en Allemagne",
        SIMULATED_RETAIL,
        "année {annee}",
    ),
    Family(
        r"^Indice prix relatif",
        "kpi_indice_prix",
        "Indice prix relatif",
        HT,
        "réel : relevé du {crocs_prix} ; simulé : relevés de {prix_debut} à {prix_fin}",
        grid="Indice prix relatif (HT)",
    ),
    Family(
        r"^Marge brute post-taxe",
        "kpi_marge_post_taxe",
        "Marge brute post-taxe",
        HT,
        "relevés de prix de {prix_debut} à {prix_fin}",
        grid="Marge brute post-taxe Allemagne",
    ),
    Family(
        r"^Densité concurrentielle",
        "kpi_densite_concurrentielle_pays",
        "Densité concurrentielle",
        NO_BASE,
        "réel : magasins relevés le {osm}, population au {destatis}",
        city="somme des villes du pays (règle 6)",
    ),
    Family(
        r"^Coût moyen au m²",
        "kpi_cout_m2",
        "Coût moyen au m²",
        UNKNOWN_BASE,
        "année {annee}",
        city="moyenne des villes du pays",
    ),
    Family(
        r"^Distance moyenne au hub",
        "kpi_distance_hub_pays",
        "Distance moyenne aux hubs",
        NO_BASE,
        "réel : trajets calculés le {osrm}",
        city="moyenne des villes du pays, zones insulaires exclues",
    ),
    Family(
        r"^TVA standard",
        "kpi_taxes",
        "Droits & taxes locales",
        NO_BASE,
        "réel : sources lues le {taxes}",
        tax_column="taux_tva_standard_pct",
        tax_simulated="taux_tva_standard_pct",
    ),
    Family(
        r"^TVA chaussures enfant",
        "kpi_taxes",
        "Droits & taxes locales",
        NO_BASE,
        "réel : sources lues le {taxes}",
        tax_column="taux_tva_reduite_chaussures_enfant_pct",
        tax_simulated="taux_tva_chaussures_enfant_pct",
    ),
    Family(
        r"^Impôt sur les sociétés",
        "kpi_taxes",
        "Droits & taxes locales",
        NO_BASE,
        "réel : sources lues le {taxes}",
        tax_column="taux_impot_societes_pct",
        tax_simulated="taux_impot_societes_pct",
    ),
    Family(
        r"^Droit de douane UE",
        "kpi_taxes",
        "Droits & taxes locales",
        NO_BASE,
        "réel : sources lues le {taxes}",
        tax_column="droit_douane_ue_chaussures_ch64_pct",
    ),
    Family(
        r"^Droit d'import",
        "kpi_taxes",
        "Droits & taxes locales",
        NO_BASE,
        "jeu simulé",
        tax_simulated="droit_import_marchandise_origine_asie_via_fr_pct",
    ),
    Family(
        r"^Éco-contribution",
        "kpi_taxes",
        "Droits & taxes locales",
        UNKNOWN_BASE,
        "jeu simulé",
        tax_simulated="eco_contribution_par_paire_eur",
    ),
    Family(
        r"^Pénétration : ",
        "kpi_penetration_categories",
        "Pénétration des catégories",
        NO_BASE,
        "année {annee}",
    ),
    Family(
        r"^% du catalogue éligible",
        "kpi_catalogue_eligible",
        "% du catalogue éligible",
        NO_BASE,
        "réel : catalogues relevés le {crocs_catalogue}",
        definition=(
            ("kpi_catalogue_eligible", "Références (code"),
            ("kpi_catalogue_eligible", "SKU éligibles ÷"),
        ),
        by_country=("Réel", "Simulé"),
        keep_start=True,
        grid="% catalogue éligible",
    ),
    Family(
        r"^Coût d'occupation \(loyer ÷ CA\)",
        "kpi_cout_occupation",
        "Coût d'occupation",
        HT,
        "année {annee}, magasins ouverts toute l'année",
    ),
    Family(
        r"^Coût d'occupation .*même périmètre",
        "business_case_france",
        "Coût d'occupation",
        HT,
        "année {annee}, magasins ouverts toute l'année",
        definition=(("business_case", "Coût d'occupation :"), ("business_case_france", None)),
    ),
    Family(
        r"^Coût d'occupation \(loyer \+ charges ÷ CA, scénario",
        "business_case",
        "Coût d'occupation",
        HT,
        "année de croisière d'un horizon de {horizon} ans",
        definition=(("business_case", "Coût d'occupation :"),),
        city="magasin type : loyer + charges moyens des villes allemandes",
        grid="Coût d'occupation",
    ),
    Family(
        r"^Payback \(même périmètre",
        "business_case_france",
        "Payback",
        NO_BASE,
        "année {annee}, magasins à maturité",
        definition=(("business_case_france", "Payback :"), ("business_case_france", None)),
    ),
    Family(
        r"^Payback \(scénario",
        "business_case",
        "Payback",
        NO_BASE,
        "horizon de {horizon} ans, montée en charge comprise",
        definition=(("business_case", "Payback :"),),
        city="magasin type : loyer + charges moyens des villes allemandes",
        grid="Payback, scénario pessimiste",
    ),
    Family(
        r"^Payback : ",
        "kpi_payback",
        "Payback",
        NO_BASE,
        "année {annee}, magasins ouverts toute l'année",
    ),
    Family(
        r"^Point mort par magasin \(même périmètre",
        "business_case_france",
        "Point mort par magasin",
        HT,
        "année {annee}, magasins ouverts toute l'année",
        definition=(("business_case", "Point mort :"), ("business_case_france", None)),
    ),
    Family(
        r"^Point mort par magasin : ",
        "kpi_point_mort",
        "Point mort par magasin",
        HT,
        "France : année {annee} ; Allemagne : année de croisière",
        definition=(("kpi_point_mort", None), ("business_case", "Point mort :")),
        by_country=("France", "Allemagne"),
        tables="vue `business_case` pour l'Allemagne",
    ),
]


def readme_table(section: str, key_column: str) -> dict[str, dict[str, str]]:
    """Rows of the first Markdown table under the README heading `section`, by key column."""
    text = README.read_text(encoding="utf-8")
    start = text.index(section)
    lines = text[start:].splitlines()[1:]
    rows, header = {}, None
    for line in lines:
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            if header:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
        elif not set("".join(cells)) <= set("-: "):
            row = dict(zip(header, cells))
            rows[row[key_column]] = row
    return rows


def header_sentences(view: str) -> list[str]:
    """Sentences of the header comment of a view's SQL file."""
    lines = []
    for line in (SQL_DIR / f"{view}.sql").read_text(encoding="utf-8").splitlines():
        if not line.startswith("--"):
            break
        lines.append(line.lstrip("-").strip())
    text = " ".join(lines)
    return [s.strip() for s in re.split(r"(?<=\.)\s+(?=[A-ZÉ])", text) if s.strip()]


def quoted(view: str, start: str | None, params: dict[str, str], keep: bool = False) -> str:
    """A sentence of a view header: the first one, or the one beginning with `start` (without
    it). The « KPI « … » (README 2.3) : » prefix is dropped and parameter names get their value."""
    sentences = header_sentences(view)
    if start is None:
        text = re.sub(r"^KPI « [^»]+ » \(README 2\.3\)[^:]*:\s*", "", sentences[0])
    else:
        text = next(s for s in sentences if s.startswith(start))
        text = text if keep else text[len(start) :].strip()
    for name, value in params.items():
        text = text.replace(name, value)
    text = text.replace(" (parametres_kpi)", "")
    return text[:1].upper() + text[1:]


def latest(con, table: str, column: str) -> str | None:
    """Latest date of a column of a real table, or None if the table or column is absent."""
    found = con.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
        [table, column],
    ).fetchone()[0]
    if not found:
        return None
    value = con.execute(f'SELECT max("{column}") FROM "{table}"').fetchone()[0]
    return value.strftime("%d/%m/%Y") if value is not None else None


def parameters(con) -> dict[str, str]:
    """Period parameters as the view headers name them, with their value."""
    values = dict(con.execute("SELECT parametre, valeur FROM parametres_kpi").fetchall())
    names = ("kpi.annee_reference", "kpi.tcam_annee_debut", "kpi.tcam_annee_fin")
    return {name: str(int(values[name])) for name in names}


def period_values(con) -> dict[str, str]:
    """Values the period templates refer to; an unknown date reads « non disponible »."""
    params = dict(con.execute("SELECT parametre, valeur FROM parametres_kpi").fetchall())
    months = con.execute("SELECT min(id_date), max(id_date) FROM fact_prix_releves").fetchone()
    values = {
        "annee": int(params["kpi.annee_reference"]),
        "tcam_debut": int(params["kpi.tcam_annee_debut"]),
        "tcam_fin": int(params["kpi.tcam_annee_fin"]),
        "horizon": int(params["business_case_allemagne.horizon_annees"]),
        "prix_debut": f"{months[0] % 100:02d}/{months[0] // 100}" if months[0] else None,
        "prix_fin": f"{months[1] % 100:02d}/{months[1] // 100}" if months[1] else None,
        "crocs_prix": latest(con, "crocs_produits", "date_collecte"),
        "crocs_catalogue": latest(con, "crocs_catalogue", "date_collecte"),
        "osm": latest(con, "osm_villes", "date_collecte"),
        "destatis": latest(con, "destatis_population_villes", "date_reference"),
        "osrm": latest(con, "osrm_distances", "date_collecte"),
        "taxes": latest(con, "taxes_reference", "date_consultation"),
        "eurostat": latest(con, "eurostat_series", "date_collecte"),
    }
    return {key: "non disponible" if value is None else value for key, value in values.items()}


def label_part(name: str, pattern: str) -> str | None:
    match = re.search(pattern, name)
    return match.group(1) if match else None


def build(con: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    """One row per KPI of kpi_summary, in the order axis, name."""
    kpis = con.execute("""
        SELECT kpi, axe, any_value(unite) AS unite,
            list(DISTINCT seuil) FILTER (WHERE seuil IS NOT NULL) AS seuils,
            list(pays || ':' || origine_donnees ORDER BY pays) AS origines
        FROM kpi_summary GROUP BY kpi, axe ORDER BY axe, kpi
        """).fetchall()
    formulas = readme_table("### 2.3 KPIs", "KPI")
    grid = readme_table("### 4.2 Grille de décision", "Critère")
    periods = period_values(con)
    params = parameters(con)
    rows = []
    for name, axis, unit, thresholds, origins in kpis:
        thresholds = thresholds or []
        family = next((f for f in FAMILIES if re.search(f.pattern, name)), None)
        if family is None:
            raise LookupError(f"no family describes the KPI « {name} »: add one to FAMILIES")
        readme = formulas.get(family.readme) if family.readme else None
        if family.tax_column or family.tax_simulated:
            simulated = "jeu simulé" in name or not family.tax_column
            table, column = (
                ("fact_fiscalite", family.tax_simulated)
                if simulated
                else ("taxes_reference", family.tax_column)
            )
            definition = FIELDS[table][column]
            prefix = name.split(" (")[0] + " :"
            extra = [s for s in header_sentences(family.view) if s.startswith(prefix)]
            if extra and not simulated:
                definition += ". " + extra[0]
            formula = readme["Formule"]
        else:
            parts = family.definition or ((family.view, None),)
            texts = [quoted(view, start, params, family.keep_start) for view, start in parts]
            if family.by_country:
                texts = [f"{country} : {text}" for country, text in zip(family.by_country, texts)]
            definition = " ".join(texts)
            if readme:
                formula = readme["Formule"]
            else:
                # no README row: the view header gives « what : how »
                definition, _, formula = definition.partition(" : ")
                formula = formula[:1].upper() + formula[1:]
        tables = readme["Tables"] if readme else family.tables
        if readme and family.tables:
            tables = f"{tables} ; {family.tables}"
        source = f"vue `{family.view}`" + (f" ; {tables}" if tables else "")

        by_origin: dict[str, list[str]] = {}
        for item in origins:
            country, origin = item.split(":")
            by_origin.setdefault(origin, []).append(country)
        origin_text = (
            next(iter(by_origin))
            if len(by_origin) == 1
            else " ; ".join(f"{o} ({', '.join(c)})" for o, c in sorted(by_origin.items()))
        )
        countries = sorted({c for c in sum(by_origin.values(), [])})

        threshold = " ; ".join(thresholds)
        if threshold and family.grid:
            threshold += f" (README 4.2 : {grid[family.grid]['Seuil Go']})"

        fmt = label_part(name, r" : ([^:()]+)$") if " : " in name else None
        if family.view == "kpi_penetration_categories":
            fmt = None
        scenario = label_part(name, r"scénario (\w+)")
        perimeter = [
            f"pays : {', '.join(countries)}",
            f"ville : {family.city}",
            f"format : {fmt or 'sans objet'}",
            f"scénario : {scenario or 'sans objet'}",
            f"période : {family.period.format(**periods)}",
        ]
        rows.append(
            {
                "nom": name,
                "axe": axis,
                "definition": definition,
                "formule": formula,
                "unite": f"{unit} ({family.base})",
                "perimetre": " ; ".join(perimeter),
                "source": source,
                "origine": origin_text,
                "seuil": threshold,
            }
        )
    return rows


def write(rows: list[dict[str, str]], path: Path) -> None:
    """Same CSV format as the other exports: UTF-8 without BOM, comma, LF line ends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    con = duckdb.connect(str(args.warehouse), read_only=True)
    try:
        rows = build(con)
    finally:
        con.close()
    write(rows, args.out)
    print(f"{args.out.name:32s} {len(rows):>8,d} KPI décrits")


if __name__ == "__main__":
    main()
