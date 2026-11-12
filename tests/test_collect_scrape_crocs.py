"""Tests of the Crocs price collector. No test reaches the network."""

import json

import pandas as pd

from src.collect import scrape_crocs as sc

ROBOTS = """User-Agent: *
Allow: /c/
Allow: /p/
Disallow: /*?sort=
Disallow: /c/*_*
Disallow: /search
Disallow: /api/

User-Agent: PowerMapper
Allow: /
"""


def test_robots_rules_of_the_star_group_only():
    rules = sc.parse_robots(ROBOTS)
    assert (True, "/") not in rules  # the PowerMapper group is ignored
    assert (False, "/search") in rules


def test_robots_allows_category_and_product_pages():
    rules = sc.parse_robots(ROBOTS)
    assert sc.is_allowed(rules, "https://www.crocs.fr/c/silhouette/sabots")
    assert sc.is_allowed(rules, "https://www.crocs.fr/p/classic-clog/10001.html")


def test_robots_refuses_search_api_filters_and_sorting():
    rules = sc.parse_robots(ROBOTS)
    assert not sc.is_allowed(rules, "https://www.crocs.fr/search?q=clog")
    assert not sc.is_allowed(rules, "https://www.crocs.fr/api/products")
    assert not sc.is_allowed(rules, "https://www.crocs.fr/c/silhouette/sabots?sort=price")
    assert not sc.is_allowed(rules, "https://www.crocs.fr/c/femme_homme")


def page(payload: dict) -> str:
    """A page whose Next.js data chunk holds `payload`, split in two chunks."""
    text = "x:" + json.dumps(payload, separators=(",", ":"))  # compact, as the site serves it
    middle = len(text) // 2
    chunks = [
        json.dumps([1, part], separators=(",", ":")) for part in (text[:middle], text[middle:])
    ]
    return "".join(f"<script>self.__next_f.push({chunk})</script>" for chunk in chunks)


def variant(colour, price, retail, size="M4W6", orderable=True):
    return {
        "price": price,
        "retailPrice": retail,
        "variationValues": {"size": size, "color": colour},
        "orderable": orderable,
        "online": True,
    }


PRODUCT = {
    "id": "10001",
    "masterProductId": "10001",
    "name": "Classic Clog",
    "currency": "EUR",
    "price": 32.99,
    "retailPrice": 54.99,
    "variants": [
        variant("001", 38.49, 54.99),
        variant("001", 32.99, 54.99, size="M9W11", orderable=False),
        variant("530", 54.99, 54.99),
    ],
    "variationAttributes": [
        {"id": "color", "values": [{"value": "001", "name": "Black"}, {"value": "530"}]}
    ],
    "primaryCategoryId": "clogs",
    "gender": "unisex",
    "silhouette": "Clog",
}


def test_category_models_keeps_the_order_and_drops_duplicates():
    hits = [
        {"productId": "10001", "slug": "/p/classic-clog/10001.html"},
        {"productId": "10126", "slug": "/p/baya-clog/10126.html"},
        {"productId": "10001", "slug": "/p/classic-clog/10001.html"},
    ]
    models = sc.category_models(page({"hits": hits, "nbHits": 3}))
    assert [model["productId"] for model in models] == ["10001", "10126"]


def test_product_data_finds_the_model_object():
    product = sc.product_data(page({"product": PRODUCT}), "10001")
    assert product["name"] == "Classic Clog"
    assert len(product["variants"]) == 3


def test_colour_rows_one_row_per_colour_with_lowest_price():
    rows = sc.colour_rows(PRODUCT, "FR", "https://www.crocs.fr", "/p/c/10001.html", "2026-11-12")
    by_colour = {row["code_coloris"]: row for row in rows}
    assert set(by_colour) == {"001", "530"}
    black = by_colour["001"]
    assert (black["prix_affiche"], black["prix_barre"], black["coloris"]) == (32.99, 54.99, "Black")
    assert black["disponible"] is True
    assert black["url"] == "https://www.crocs.fr/p/c/10001.html?cid=001"
    # Reference price equal to the displayed one: nothing is crossed out.
    assert by_colour["530"]["prix_barre"] is None
    assert by_colour["530"]["coloris"] is None


def test_listing_rows_merge_the_colours_of_a_model_listed_twice():
    listing = {
        "site": "FR",
        "categorie": "Sabots",
        "path": "/c/silhouette/sabots",
        "day": "2026-11-12",
        "hits": [
            {"productId": "10001", "name": "Classic Clog", "colorVariations": [{"id": "001"}]},
            {
                "productId": "10001",
                "name": "Classic Clog",
                "colorVariations": [{"id": "001"}, {"id": "530", "name": "Lavender"}],
            },
        ],
    }
    rows = sc.listing_rows(listing, "https://www.crocs.fr")
    assert [(row["code_modele"], row["code_coloris"]) for row in rows] == [
        ("10001", "001"),
        ("10001", "530"),
    ]


def catalogue(rows):
    return pd.DataFrame(rows, columns=["site", "categorie", "code_modele", "code_coloris"])


CATEGORIES = ["Sabots", "Sandales", "Chaussures"]


def test_model_category_is_exclusive_and_follows_the_configuration_order():
    table = catalogue(
        [
            ("FR", "Chaussures", "A", "1"),
            ("FR", "Sabots", "A", "1"),
            ("FR", "Chaussures", "B", "1"),
            ("DE", "Sandales", "C", "1"),
        ]
    )
    assert sc.model_category(table, CATEGORIES).to_dict() == {
        "A": "Sabots",
        "B": "Chaussures",
        "C": "Sandales",
    }


def test_catalogue_share_recomputes_the_total_from_the_counts():
    table = catalogue(
        [
            ("FR", "Sabots", "A", "1"),
            ("FR", "Sabots", "A", "2"),
            ("FR", "Sabots", "A", "3"),
            ("FR", "Sandales", "B", "1"),
            ("DE", "Chaussures", "A", "1"),  # any German category counts
            ("DE", "Sabots", "B", "9"),  # same model, other colour: not present
        ]
    )
    share = sc.catalogue_share(table, CATEGORIES).set_index("categorie")
    assert share.loc["Sabots", "part_catalogue_pct"] == round(100 / 3, 1)
    assert share.loc["Sandales", "nb_presentes_de"] == 0
    # 1 reference out of 4, not the mean of 33.3 % and 0 %.
    assert share.loc["Total", "part_catalogue_pct"] == 25.0


def test_price_pairs_and_index_before_tax_on_orderable_colours_only():
    columns = ["site", "code_modele", "code_coloris", "nom", "categorie", "coloris"]
    base = dict(zip(columns[3:], ["Classic Clog", "Sabots", "Black"]))
    products = pd.DataFrame(
        [
            {"site": "FR", "code_modele": "A", "code_coloris": "1", **base, "prix_affiche": 40.0,
             "prix_barre": 60.0, "disponible": True, "url": "fr"},
            {"site": "DE", "code_modele": "A", "code_coloris": "1", **base, "prix_affiche": 40.0,
             "prix_barre": 60.0, "disponible": True, "url": "de"},
            {"site": "FR", "code_modele": "A", "code_coloris": "2", **base, "prix_affiche": 60.0,
             "prix_barre": None, "disponible": False, "url": "fr"},
            {"site": "DE", "code_modele": "A", "code_coloris": "2", **base, "prix_affiche": 60.0,
             "prix_barre": None, "disponible": True, "url": "de"},
        ]
    )  # fmt: skip
    pairs = sc.price_pairs(products, {"FR": 20, "DE": 19})
    assert list(pairs["code_coloris"]) == ["1"]  # colour 2 is sold out in France
    index = sc.price_index(pairs).set_index("categorie")
    # Same price incl. VAT: (60 / 1.19) / (60 / 1.20) x 100.
    assert index.loc["Total", "indice_prix_ht_reference"] == round(100 * 1.20 / 1.19, 2)
