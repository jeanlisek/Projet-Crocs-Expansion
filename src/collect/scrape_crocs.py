"""Collect the public prices of the Crocs websites of France and Germany (task T3).

Usage (from the repository root):
    python -m src.collect.scrape_crocs [--bronze DIR]

Two steps, both from public pages, each answer saved dated in data/bronze/ and never asked
for again:

1. Catalogue. Every page of the three "silhouette" categories of each site (sabots, sandals,
   shoes; no filter, no sorting; `?page=N` for the next pages). A category page lists each
   model with the colours it shows. Table crocs_catalogue: one row per site, category,
   model and colour.
2. Prices. For each category, the first models of the French list that crocs.de also sells
   are read on both sites. A model page holds every colour with, per size, the displayed
   price and the reference price. Table crocs_produits: one row per site, model and colour.

The share of the French catalogue (model + colour) also listed on crocs.de, per category,
is then printed (KPI "% catalogue éligible", task T3).

robots.txt of www.crocs.fr and www.crocs.de, read on 2026-11-12 (the same file on both
sites): category pages (/c/) and model pages (/p/) are allowed for every user-agent; search,
the API, the account pages and category URLs with filters or sorting are not. The file sets
no crawl delay. Each run reads robots.txt again before its first page and checks every URL
against it (pagination uses `?page=N`, which it allows; the search API is never called); it
sends an explicit User-Agent, waits at least the project delay between two
requests, and stops at the first refusal (HTTP 403 or 429, CAPTCHA page): no retry, no
workaround (project rule 7).
"""

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"

# Identifies the client: project name and public repository.
USER_AGENT = "Projet-Crocs-Expansion/1.0 (+https://github.com/jeanlisek/Projet-Crocs-Expansion)"
SOURCE = "Site {url}, page produit publique, relevé du {day}"
LISTING_SOURCE = "Site {url}, pages de la catégorie {path}, relevé du {day}"

PRODUCTS_TABLE = "crocs_produits"
CATALOGUE_TABLE = "crocs_catalogue"
RAW_FILE = "crocs_{site}_{model}_{day}.json"
LISTING_FILE = "crocs_liste_{site}_{category}_{day}.json"
# Statuses that mean the site refuses the client: the script stops, it does not retry.
REFUSAL_STATUSES = (401, 403, 429)
# Words of a bot-protection page served with a 200 status.
CHALLENGE_MARKERS = ("captcha", "are you a robot", "access denied", "cf-challenge")
# Parts of the model page kept in the raw file; the rest (images, texts) is not needed.
KEPT_PRODUCT_KEYS = (
    "id",
    "masterProductId",
    "name",
    "currency",
    "price",
    "retailPrice",
    "variants",
    "variationAttributes",
    "primaryCategoryId",
    "gender",
    "silhouette",
    "sapMaterialGroup",
)

# The pages are rendered by Next.js: their data comes in `self.__next_f.push([1, "..."])`
# script chunks, JSON strings to decode and join back together.
FLIGHT_CHUNK = re.compile(r"self\.__next_f\.push\((\[1,\".*?\"\])\)</script>", re.S)


class Refused(RuntimeError):
    """The site refuses the client: the collection stops there."""


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["collecte"]


# --- robots.txt ---------------------------------------------------------------------------


def parse_robots(text: str) -> list[tuple[bool, str]]:
    """Allow and Disallow rules of the `User-agent: *` group, as (allowed, pattern) pairs."""
    rules, in_star_group, previous_was_agent = [], False, False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            # Consecutive User-agent lines open one group together.
            in_star_group = (in_star_group and previous_was_agent) or value == "*"
            previous_was_agent = True
            continue
        previous_was_agent = False
        if in_star_group and field in ("allow", "disallow") and value:
            rules.append((field == "allow", value))
    return rules


def _pattern_regex(pattern: str) -> re.Pattern:
    """robots.txt pattern to regex: `*` is any sequence, a final `$` anchors the end."""
    anchored = pattern.endswith("$")
    body = re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
    return re.compile(body + ("$" if anchored else ""))


def is_allowed(rules: list[tuple[bool, str]], url: str) -> bool:
    """Google / RFC 9309 rule: the longest matching pattern wins, Allow wins a tie."""
    parts = urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    best_length, allowed = -1, True
    for rule_allows, pattern in rules:
        if _pattern_regex(pattern).match(path):
            length = len(pattern)
            if length > best_length or (length == best_length and rule_allows):
                best_length, allowed = length, rule_allows
    return allowed


# --- HTTP -----------------------------------------------------------------------------------


class Client:
    """One site: reads its robots.txt, then sends the requests one at a time, spaced out."""

    def __init__(self, base_url: str, delay_s: float, timeout_s: float):
        self.base_url = base_url.rstrip("/")
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.last_request = None
        self.requests_sent = 0
        self.rules = None  # robots.txt is read before the first page: no page, no request

    def _get(self, path: str) -> requests.Response:
        if self.last_request is not None:
            wait = self.delay_s - (time.monotonic() - self.last_request)
            if wait > 0:
                time.sleep(wait)
        url = self.base_url + path
        response = self.session.get(url, timeout=self.timeout_s)
        self.last_request = time.monotonic()
        self.requests_sent += 1
        if response.status_code in REFUSAL_STATUSES:
            raise Refused(f"{url} : HTTP {response.status_code}, arrêt sans nouvel essai")
        response.raise_for_status()
        head = response.text[:5000].lower()
        if any(marker in head for marker in CHALLENGE_MARKERS):
            raise Refused(f"{url} : page anti-robot détectée, arrêt sans contournement")
        return response

    def page(self, path: str) -> str:
        if self.rules is None:
            self.rules = parse_robots(self._get("/robots.txt").text)
        if not is_allowed(self.rules, self.base_url + path):
            raise Refused(f"{self.base_url}{path} : interdit par robots.txt")
        return self._get(path).text


# --- Page parsing ---------------------------------------------------------------------------


def flight_data(html: str) -> str:
    """Join the Next.js data chunks of a page into one text."""
    return "".join(json.loads(chunk)[1] for chunk in FLIGHT_CHUNK.findall(html))


def _enclosing_object(text: str, key: str, opener: str) -> dict:
    """Decode the JSON object that starts at the last `opener` before `key`."""
    decoder = json.JSONDecoder()
    for match in re.finditer(re.escape(key), text):
        start = text.rfind(opener, 0, match.end())
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(text, start)
                return obj
            except json.JSONDecodeError:
                start = text.rfind(opener, 0, start)
    raise ValueError(f"no JSON object holding {key} in the page")


def category_models(html: str) -> list[dict]:
    """Models of a category page, in the order shown: productId and page path."""
    listing = _enclosing_object(flight_data(html), '"hits":[', '{"hits"')
    models, seen = [], set()
    for hit in listing["hits"]:
        if hit["productId"] not in seen:
            seen.add(hit["productId"])
            models.append({"productId": hit["productId"], "slug": hit["slug"]})
    return models


def product_data(html: str, model: str) -> dict:
    """The model object of a model page (every colour and size, with prices)."""
    text = flight_data(html)
    decoder = json.JSONDecoder()
    opener = '{"id":"' + model + '"'
    for match in re.finditer(re.escape('"variants":['), text):
        start = text.rfind(opener, 0, match.start())
        if start == -1:
            continue
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if obj.get("variants") and obj.get("variationAttributes"):
            return {key: obj.get(key) for key in KEPT_PRODUCT_KEYS}
    raise ValueError(f"model {model}: no product data with variants in the page")


# --- Table rows -----------------------------------------------------------------------------


def colour_rows(product: dict, site: str, base_url: str, slug: str, day: str) -> list[dict]:
    """One row per colour. The displayed price is the lowest one among the colour's sizes,
    as the site shows it on the category page; the crossed-out price is the reference price
    of that same size, kept only when it is above the displayed price."""
    names = {}
    for attribute in product["variationAttributes"]:
        if attribute.get("id") == "color":
            names = {value["value"]: value.get("name") for value in attribute["values"]}
    by_colour: dict[str, list[dict]] = {}
    for variant in product["variants"]:
        if variant.get("online", True):
            by_colour.setdefault(variant["variationValues"]["color"], []).append(variant)

    rows = []
    for colour, variants in by_colour.items():
        cheapest = min(variants, key=lambda variant: variant["price"])
        retail = cheapest.get("retailPrice")
        rows.append(
            {
                "site": site,
                "code_modele": product["masterProductId"] or product["id"],
                "nom": product["name"],
                "code_coloris": colour,
                "coloris": names.get(colour),
                "silhouette": product.get("silhouette"),
                "categorie_site": product.get("primaryCategoryId"),
                "genre": product.get("gender"),
                "prix_affiche": cheapest["price"],
                "prix_barre": retail if retail and retail > cheapest["price"] else None,
                "devise": product["currency"],
                "disponible": any(variant.get("orderable") for variant in variants),
                "url": f"{base_url}{slug}?cid={colour}",
                "date_collecte": day,
                "source": SOURCE.format(url=base_url, day=day),
            }
        )
    return rows


def listing_rows(listing: dict, base_url: str) -> list[dict]:
    """One row per model and colour shown on the pages of a category. A model can come in
    several hits (one per group of colours): their colours are merged."""
    rows, seen = [], set()
    for hit in listing["hits"]:
        for colour in hit.get("colorVariations") or []:
            key = (hit["productId"], colour["id"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "site": listing["site"],
                    "categorie": listing["categorie"],
                    "code_modele": hit["productId"],
                    "nom": hit["name"],
                    "code_coloris": colour["id"],
                    "coloris": colour.get("name"),
                    "date_collecte": listing["day"],
                    "source": LISTING_SOURCE.format(
                        url=base_url, path=listing["path"], day=listing["day"]
                    ),
                }
            )
    return rows


def category_listing(html: str) -> dict:
    """The listing object of a category page: hits of the page, number of pages."""
    return _enclosing_object(flight_data(html), '"hits":[', '{"hits"')


def kept_hit(hit: dict) -> dict:
    """The fields of a listed model kept in the raw file."""
    return {
        "productId": hit["productId"],
        "name": hit.get("name"),
        "slug": hit.get("slug"),
        "primaryCategoryId": hit.get("primaryCategoryId"),
        "pricing": hit.get("pricing"),
        "colorVariations": [
            {"id": colour["id"], "name": colour.get("name")}
            for colour in hit.get("colorVariations") or []
        ],
    }


# --- KPI ------------------------------------------------------------------------------------


def model_category(catalogue: pd.DataFrame, categories: list[str]) -> pd.Series:
    """One category per model. The category pages overlap (most models of the "shoes" page
    are also on the sabots or sandals page): a model takes the first category of the
    configuration order whose French list holds it, then the German list if France has none.
    The categories are thus exclusive and add up to the total."""
    rank = {category: position for position, category in enumerate(categories)}
    listed = catalogue.assign(
        rang=catalogue["categorie"].map(rank), pays_rang=(catalogue["site"] != "FR").astype(int)
    ).sort_values(["pays_rang", "rang"])
    return listed.drop_duplicates("code_modele").set_index("code_modele")["categorie"]


def catalogue_share(catalogue: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    """Share of the French catalogue (model + colour) also listed on crocs.de, per category
    (exclusive, see model_category) and in total. A reference counts as present when the
    same model and colour codes are listed in any category of crocs.de. The shares are
    recomputed from the counts (rule 6): the total is not an average of the categories."""
    keys = ["code_modele", "code_coloris"]
    german = set(map(tuple, catalogue.loc[catalogue["site"] == "DE", keys].to_numpy()))
    french = catalogue.loc[catalogue["site"] == "FR", keys].drop_duplicates()
    french = french.assign(
        categorie=french["code_modele"].map(model_category(catalogue, categories)),
        present_de=[tuple(key) in german for key in french[keys].to_numpy()],
    )
    groups = [(category, french[french["categorie"] == category]) for category in categories]
    groups.append(("Total", french))
    table = pd.DataFrame(
        [
            {
                "categorie": category,
                "nb_references_fr": len(group),
                "nb_presentes_de": int(group["present_de"].sum()),
                "nb_modeles_fr": group["code_modele"].nunique(),
                "nb_modeles_presents_de": group.loc[group["present_de"], "code_modele"].nunique(),
            }
            for category, group in groups
        ]
    )
    table["part_catalogue_pct"] = (
        100 * table["nb_presentes_de"] / table["nb_references_fr"]
    ).round(1)
    return table


def price_pairs(products: pd.DataFrame, vat_pct: dict) -> pd.DataFrame:
    """FR/DE pairs on the same model and colour codes, with prices before tax. Only colours
    that can be ordered on both sites are paired: a sold-out colour keeps an old price and
    its `?cid=` link opens another colour (checked on 2026-11-12). The reference price is
    the crossed-out price when there is one, the displayed price otherwise: it is the price
    outside promotion that the README index compares (section 2)."""
    keys = ["code_modele", "code_coloris"]
    columns = [*keys, "nom", "categorie", "coloris", "prix_affiche", "prix_barre", "url"]
    available = products[products["disponible"].astype(str) == "True"]
    french = available.loc[available["site"] == "FR", columns]
    german = available.loc[available["site"] == "DE", [*keys, "prix_affiche", "prix_barre", "url"]]
    pairs = french.merge(german, on=keys, suffixes=("_fr", "_de"))
    for site in ("fr", "de"):
        rate = 1 + vat_pct[site.upper()] / 100
        reference = pairs[f"prix_barre_{site}"].fillna(pairs[f"prix_affiche_{site}"])
        pairs[f"prix_reference_ht_{site}"] = (reference / rate).round(2)
        pairs[f"prix_affiche_ht_{site}"] = (pairs[f"prix_affiche_{site}"] / rate).round(2)
    return pairs


def price_index(pairs: pd.DataFrame) -> pd.DataFrame:
    """Price index DE vs FR = mean over the pairs of (price before tax DE / FR) x 100, as the
    README defines it (section 2), per category and in total; on reference prices (the KPI)
    and, for information, on displayed prices."""
    pairs = pairs.assign(
        ratio_reference=pairs["prix_reference_ht_de"] / pairs["prix_reference_ht_fr"],
        ratio_affiche=pairs["prix_affiche_ht_de"] / pairs["prix_affiche_ht_fr"],
    )
    groups = [(category, group) for category, group in pairs.groupby("categorie", sort=False)]
    groups.append(("Total", pairs))
    return pd.DataFrame(
        [
            {
                "categorie": category,
                "nb_paires": len(group),
                "nb_modeles": group["code_modele"].nunique(),
                "nb_paires_prix_ttc_identique": int(
                    (group["prix_affiche_fr"] == group["prix_affiche_de"]).sum()
                ),
                "indice_prix_ht_reference": round(100 * group["ratio_reference"].mean(), 2),
                "indice_prix_ht_affiche": round(100 * group["ratio_affiche"].mean(), 2),
            }
            for category, group in groups
        ]
    )


# --- Collection -----------------------------------------------------------------------------


def cached(bronze_dir: Path, pattern: str, **names) -> Path | None:
    """Most recent raw file already saved for these names, if any."""
    files = sorted(bronze_dir.glob(pattern.format(day="*", **names)))
    return files[-1] if files else None


def collect_listing(client: Client, site: str, category: str, path: str, bronze_dir: Path):
    """Save every page of a category (first page, then `?page=N`); return the raw file."""
    path_cached = cached(bronze_dir, LISTING_FILE, site=site, category=category)
    if path_cached is not None:
        print(f"{site} {category:10s} déjà en cache ({path_cached.name})")
        return path_cached
    first = category_listing(client.page(path))
    hits = [kept_hit(hit) for hit in first["hits"]]
    for page_number in range(1, first["nbPages"]):
        listing = category_listing(client.page(f"{path}?page={page_number}"))
        hits.extend(kept_hit(hit) for hit in listing["hits"])
    day = date.today().isoformat()
    raw = {
        "site": site,
        "categorie": category,
        "path": path,
        "day": day,
        "nbHits": first["nbHits"],
        "nbPages": first["nbPages"],
        "hits": hits,
    }
    raw_path = bronze_dir / LISTING_FILE.format(site=site, category=category, day=day)
    raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    print(
        f"{site} {category:10s} {first['nbPages']:>2d} page(s), {first['nbHits']:>4d} modèles"
        f" annoncés, {len(hits):>4d} lus   ({raw_path.name})"
    )
    return raw_path


def collect_product(client: Client, site: str, model: str, slug: str, bronze_dir: Path):
    """Save the useful part of a model page, unless it is already saved."""
    if cached(bronze_dir, RAW_FILE, site=site, model=model) is not None:
        return False
    product = product_data(client.page(slug), model)
    day = date.today().isoformat()
    raw = {"site": site, "slug": slug, "day": day, "product": product}
    path = bronze_dir / RAW_FILE.format(site=site, model=model, day=day)
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    print(f"{site} {model:>8s}   {product['name']}   ({path.name})")
    return True


def rebuild_catalogue(bronze_dir: Path, settings: dict) -> pd.DataFrame:
    """Rebuild crocs_catalogue from the most recent listing of each site and category."""
    crocs = settings["crocs"]
    rows = []
    for site, base_url in crocs["sites"].items():
        for category in crocs["categories"]:
            path = cached(bronze_dir, LISTING_FILE, site=site, category=category)
            if path is not None:
                rows.extend(listing_rows(json.loads(path.read_text(encoding="utf-8")), base_url))
    table = pd.DataFrame(rows)
    table.to_csv(bronze_dir / f"{CATALOGUE_TABLE}.csv", index=False, encoding="utf-8-sig")
    return table


def rebuild_products(bronze_dir: Path, settings: dict, catalogue: pd.DataFrame) -> pd.DataFrame:
    """Rebuild crocs_produits from the raw model pages, with the category of model_category."""
    crocs = settings["crocs"]
    rows = []
    for site, base_url in crocs["sites"].items():
        for path in sorted(bronze_dir.glob(RAW_FILE.format(site=site, model="*", day="*"))):
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows.extend(colour_rows(raw["product"], site, base_url, raw["slug"], raw["day"]))
    table = pd.DataFrame(rows)
    if not table.empty:
        # The latest reading of each model wins when it was read on several days.
        table = table.sort_values("date_collecte").drop_duplicates(
            ["site", "code_modele", "code_coloris"], keep="last"
        )
        category = model_category(catalogue, list(crocs["categories"]))
        table.insert(5, "categorie", table["code_modele"].map(category))
    table.to_csv(bronze_dir / f"{PRODUCTS_TABLE}.csv", index=False, encoding="utf-8-sig")
    return table


def models_to_price(
    catalogue: pd.DataFrame, categories: list[str], per_category: int
) -> list[tuple[str, str]]:
    """Per category, the first `per_category` models of the French lists (site order) that
    crocs.de lists with at least one same colour."""
    keys = ["code_modele", "code_coloris"]
    german = catalogue.loc[catalogue["site"] == "DE", keys].drop_duplicates()
    common = catalogue[catalogue["site"] == "FR"].merge(german, on=keys)
    common = common.assign(classe=common["code_modele"].map(model_category(catalogue, categories)))
    chosen = []
    for category in categories:
        models = common.loc[common["classe"] == category, "code_modele"].drop_duplicates()
        chosen.extend((category, model) for model in models.head(per_category))
    return chosen


def collect(bronze_dir: Path = DEFAULT_BRONZE_DIR, per_category: int | None = None):
    settings = load_config()
    crocs = settings["crocs"]
    per_category = per_category or crocs["nb_modeles_par_categorie"]
    clients, sent = {}, 0
    slugs: dict[tuple[str, str], str] = {}
    try:
        for site, base_url in crocs["sites"].items():
            clients[site] = Client(
                base_url, settings["delai_entre_requetes_s"], crocs["delai_reponse_s"]
            )
            for category, paths in crocs["categories"].items():
                raw_path = collect_listing(clients[site], site, category, paths[site], bronze_dir)
                for hit in json.loads(raw_path.read_text(encoding="utf-8"))["hits"]:
                    slugs.setdefault((site, hit["productId"]), hit["slug"])
        catalogue = rebuild_catalogue(bronze_dir, settings)
        print()
        for category, model in models_to_price(catalogue, list(crocs["categories"]), per_category):
            for site in crocs["sites"]:
                collect_product(clients[site], site, model, slugs[(site, model)], bronze_dir)
    finally:
        sent = sum(client.requests_sent for client in clients.values())
        catalogue = rebuild_catalogue(bronze_dir, settings)
        products = rebuild_products(bronze_dir, settings, catalogue)
        print(
            f"\n{sent} requête(s) envoyée(s) ; {len(catalogue)} ligne(s) dans"
            f" {CATALOGUE_TABLE}.csv, {len(products)} dans {PRODUCTS_TABLE}.csv"
        )
    categories = list(crocs["categories"])
    print("\nPart du catalogue France (modèle + coloris) présente sur crocs.de :")
    print(catalogue_share(catalogue, categories).to_string(index=False))
    pairs = price_pairs(products, crocs["tva_pct"])
    print("\nIndice prix HT DE / FR (base 100 = France), paires modèle + coloris :")
    print(price_index(pairs).to_string(index=False))
    return catalogue, products


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nb-modeles-par-categorie", type=int)
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    collect(args.bronze, args.nb_modeles_par_categorie)


if __name__ == "__main__":
    main()
