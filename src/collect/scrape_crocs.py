"""Collect the public prices of the Crocs websites of France and Germany (task T3).

Usage (from the repository root):
    python -m src.collect.scrape_crocs [--sites FR DE] [--nb-modeles N] [--bronze DIR]

For each site, the start category page (no filter, no sorting) gives the list of models in
the order the site shows them; the first N models are kept. Each model page holds every
colour of the model with, per size, the displayed price and the reference price. The useful
part of each model page is saved, dated, in data/bronze/; a model already saved for a site
is never asked for again. The table crocs_produits (one row per site, model and colour) is
then rebuilt from those raw files.

robots.txt of www.crocs.fr and www.crocs.de, read on 2026-11-12 (the same file on both
sites): category pages (/c/) and model pages (/p/) are allowed for every user-agent; search,
the API, the account pages and category URLs with filters or sorting are not. The file sets
no crawl delay. Before each request, this script reads robots.txt again and checks the URL
against it; it sends an explicit User-Agent, waits at least the project delay between two
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

TABLE = "crocs_produits"
RAW_FILE = "crocs_{site}_{model}_{day}.json"
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
        self.rules = parse_robots(self._get("/robots.txt").text)

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
                "categorie": product.get("silhouette"),
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


# --- Collection -----------------------------------------------------------------------------


def cached_product(bronze_dir: Path, site: str, model: str) -> Path | None:
    """Most recent raw file already saved for a model of a site, if any."""
    files = sorted(bronze_dir.glob(RAW_FILE.format(site=site, model=model, day="*")))
    return files[-1] if files else None


def rebuild_table(bronze_dir: Path, settings: dict) -> pd.DataFrame:
    """Rebuild crocs_produits from every raw file of data/bronze/."""
    rows = []
    for path in sorted(bronze_dir.glob(RAW_FILE.format(site="*", model="*", day="*"))):
        raw = json.loads(path.read_text(encoding="utf-8"))
        site = raw["site"]
        rows.extend(
            colour_rows(
                raw["product"],
                site,
                settings["crocs"]["sites"][site]["url"],
                raw["slug"],
                raw["day"],
            )
        )
    table = pd.DataFrame(rows)
    table.to_csv(bronze_dir / f"{TABLE}.csv", index=False, encoding="utf-8-sig")
    return table


def collect_site(site: str, settings: dict, nb_models: int, bronze_dir: Path) -> int:
    """Save the first `nb_models` models of a site's start category; return requests sent."""
    crocs = settings["crocs"]
    site_settings = crocs["sites"][site]
    client = Client(
        site_settings["url"], settings["delai_entre_requetes_s"], crocs["delai_reponse_s"]
    )
    models = category_models(client.page(site_settings["categorie_depart"]))[:nb_models]
    for model in models:
        model_id = model["productId"]
        cached = cached_product(bronze_dir, site, model_id)
        if cached is not None:
            print(f"{site} {model_id:>8s}   déjà en cache ({cached.name})")
            continue
        product = product_data(client.page(model["slug"]), model_id)
        day = date.today().isoformat()
        raw = {"site": site, "slug": model["slug"], "day": day, "product": product}
        path = bronze_dir / RAW_FILE.format(site=site, model=model_id, day=day)
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        print(f"{site} {model_id:>8s}   {product['name']}   ({path.name})")
    return client.requests_sent


def collect(
    bronze_dir: Path = DEFAULT_BRONZE_DIR, sites: list[str] | None = None, nb_models=None
) -> pd.DataFrame:
    settings = load_config()
    crocs = settings["crocs"]
    sites = sites or list(crocs["sites"])
    nb_models = nb_models or crocs["nb_modeles_par_site"]
    sent = 0
    try:
        for site in sites:
            sent += collect_site(site, settings, nb_models, bronze_dir)
    finally:
        table = rebuild_table(bronze_dir, settings)
        print(f"\n{sent} requête(s) envoyée(s), {len(table)} ligne(s) dans {TABLE}.csv")
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sites", nargs="+", choices=("FR", "DE"))
    parser.add_argument("--nb-modeles", type=int)
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    collect(args.bronze, args.sites, args.nb_modeles)


if __name__ == "__main__":
    main()
