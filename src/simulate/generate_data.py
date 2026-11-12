"""
Générateur de données simulées – Projet Data Analytics « Crocs France : expansion européenne 2027-2029 »

Toutes les données sont SIMULÉES mais calibrées sur des ordres de grandeur publics
(prix publics Crocs, taux de TVA, droits de douane TARIC, loyers prime, salaires minimum...).
Script déterministe (seed fixe) : relancer le script régénère exactement les mêmes fichiers.

Usage :  python generate_data.py [dossier_sortie]
"""
import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2027
rng = np.random.default_rng(SEED)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
OUT.mkdir(parents=True, exist_ok=True)


def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
    print(f"{name:32s} {len(df):>8,d} lignes")


# --------------------------------------------------------------------------------------
# 1. DIM_PAYS – France (référence) + 6 pays candidats
# --------------------------------------------------------------------------------------
pays = pd.DataFrame([
    # code, nom, devise, taux_change_eur, population_m, pib_hab_spa, chomage, indice_niveau_prix_chaussures(UE27=100), confiance_conso, langue
    ("FR", "France",      "EUR", 1.000, 68.4, 101, 7.4, 103, -18, "français"),
    ("DE", "Allemagne",   "EUR", 1.000, 83.5, 116, 3.5, 100, -21, "allemand"),
    ("ES", "Espagne",     "EUR", 1.000, 48.6,  91, 11.0, 92, -12, "espagnol"),
    ("IT", "Italie",      "EUR", 1.000, 58.9,  97, 6.3, 101, -15, "italien"),
    ("BE", "Belgique",    "EUR", 1.000, 11.8, 117, 5.9, 106, -10, "français/néerlandais"),
    ("NL", "Pays-Bas",    "EUR", 1.000, 18.0, 130, 3.8, 104,  -25, "néerlandais"),
    ("GB", "Royaume-Uni", "GBP", 0.850, 68.3, 98, 4.6, 108, -19, "anglais"),
], columns=["code_pays", "nom_pays", "devise", "taux_change_vs_eur", "population_millions",
            "pib_habitant_spa_ue100", "taux_chomage_pct", "indice_niveau_prix_chaussures_ue100",
            "indice_confiance_conso", "langue_principale"])
pays["membre_ue"] = pays["code_pays"] != "GB"
pays["union_douaniere_avec_fr"] = pays["membre_ue"]
pays["est_pays_reference"] = pays["code_pays"] == "FR"
save(pays, "dim_pays")

# --------------------------------------------------------------------------------------
# 2. DIM_TEMPS – mensuelle 2019-2029
# --------------------------------------------------------------------------------------
mois = pd.date_range("2019-01-01", "2029-12-01", freq="MS")
saisons = {12: "Hiver", 1: "Hiver", 2: "Hiver", 3: "Printemps", 4: "Printemps", 5: "Printemps",
           6: "Été", 7: "Été", 8: "Été", 9: "Automne", 10: "Automne", 11: "Automne"}
noms_mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]
dim_temps = pd.DataFrame({
    "id_date": mois.strftime("%Y%m").astype(int),
    "date_debut_mois": mois.date,
    "annee": mois.year,
    "trimestre": "T" + mois.quarter.astype(str),
    "mois": mois.month,
    "nom_mois": [noms_mois[m - 1] for m in mois.month],
    "saison": [saisons[m] for m in mois.month],
    "periode_soldes_fr": mois.month.isin([1, 7]),
    "black_friday": mois.month == 11,
})
dim_temps["est_historique"] = dim_temps["date_debut_mois"] <= pd.Timestamp("2026-10-01").date()
save(dim_temps, "dim_temps")

# --------------------------------------------------------------------------------------
# 3. DIM_PRODUIT – catalogue France (Crocs + HEYDUDE)
# --------------------------------------------------------------------------------------
COULEURS = ["Noir", "Blanc", "Bleu marine", "Os", "Rose ballerine", "Vert kaki", "Gris ardoise",
            "Rouge pepper", "Bleu digital", "Jaune soleil", "Lavande", "Camouflage"]

# (marque, categorie, sous_categorie, modele, cible, prix_ttc_fr, fob_usd, code_sh, profil_saison, nb_coloris, licence)
MODELES = [
    ("Crocs", "Sabots", "Classic", "Classic Clog", "Adulte", 49.99, 9.10, "6402.99", "ete", 12, False),
    ("Crocs", "Sabots", "Classic", "Classic Clog Kids", "Enfant", 39.99, 7.20, "6402.99", "ete", 10, False),
    ("Crocs", "Sabots", "Classic", "Classic Clog Toddler", "Bébé", 34.99, 6.30, "6402.99", "ete", 6, False),
    ("Crocs", "Sabots", "Classic", "Classic Lined Clog", "Adulte", 64.99, 12.40, "6402.99", "hiver", 5, False),
    ("Crocs", "Sabots", "Classic", "Classic Lined Clog Kids", "Enfant", 49.99, 9.80, "6402.99", "hiver", 4, False),
    ("Crocs", "Sabots", "Plateforme", "Classic Platform Clog", "Adulte", 64.99, 11.60, "6402.99", "ete", 6, False),
    ("Crocs", "Sabots", "Plateforme", "Mega Crush Clog", "Adulte", 79.99, 14.20, "6402.99", "ete", 5, False),
    ("Crocs", "Sabots", "Plateforme", "Classic Crush Clog", "Adulte", 74.99, 13.30, "6402.99", "ete", 4, False),
    ("Crocs", "Sabots", "Sport", "Crocband Clog", "Adulte", 54.99, 10.10, "6402.99", "ete", 6, False),
    ("Crocs", "Sabots", "Sport", "Echo Clog", "Adulte", 69.99, 12.90, "6402.99", "ete", 5, False),
    ("Crocs", "Sabots", "Sport", "LiteRide 360 Clog", "Adulte", 64.99, 12.10, "6402.99", "ete", 4, False),
    ("Crocs", "Sabots", "Pro", "Bistro Clog", "Adulte", 49.99, 9.40, "6402.99", "plat", 2, False),
    ("Crocs", "Sandales", "Sandales", "Classic Sandal", "Adulte", 34.99, 6.10, "6402.99", "ete_fort", 6, False),
    ("Crocs", "Sandales", "Sandales", "Brooklyn Low Wedge", "Adulte", 54.99, 10.20, "6402.99", "ete_fort", 4, False),
    ("Crocs", "Sandales", "Sandales", "Getaway Strappy", "Adulte", 44.99, 8.10, "6402.99", "ete_fort", 4, False),
    ("Crocs", "Sandales", "Claquettes", "Classic Slide", "Adulte", 34.99, 5.90, "6402.20", "ete_fort", 5, False),
    ("Crocs", "Sandales", "Claquettes", "Baya Slide", "Adulte", 29.99, 5.10, "6402.20", "ete_fort", 4, False),
    ("Crocs", "Sandales", "Tongs", "Classic Flip", "Adulte", 24.99, 4.20, "6402.20", "ete_fort", 4, False),
    ("Crocs", "Bottes", "Bottes de pluie", "Classic Crush Rain Boot", "Adulte", 79.99, 15.10, "6401.92", "automne", 3, False),
    ("Crocs", "Bottes", "Bottes fourrées", "Classic Neo Puff Boot", "Adulte", 79.99, 15.80, "6402.91", "hiver", 3, False),
    ("Crocs", "Bottes", "Bottes de pluie", "Classic Rain Boot Kids", "Enfant", 44.99, 8.60, "6401.92", "automne", 3, False),
    ("Crocs", "Jibbitz", "Charms unitaires", "Jibbitz Charm unitaire", "Mixte", 5.99, 0.55, "3926.40", "plat", 8, False),
    ("Crocs", "Jibbitz", "Packs", "Jibbitz Pack 3", "Mixte", 14.99, 1.40, "3926.40", "plat", 4, False),
    ("Crocs", "Jibbitz", "Packs", "Jibbitz Pack 5", "Mixte", 19.99, 1.90, "3926.40", "plat", 4, False),
    ("Crocs", "Jibbitz", "Packs licence", "Jibbitz Pack 5 Licence", "Mixte", 24.99, 3.10, "3926.40", "noel", 6, True),
    ("Crocs", "Sabots", "Licence", "Classic Clog Licence", "Enfant", 54.99, 10.90, "6402.99", "noel", 4, True),
    ("HEYDUDE", "Chaussures toile", "Mocassins", "Wally", "Adulte", 74.99, 15.20, "6404.19", "printemps", 5, False),
    ("HEYDUDE", "Chaussures toile", "Mocassins", "Wendy", "Adulte", 69.99, 14.10, "6404.19", "printemps", 5, False),
    ("HEYDUDE", "Chaussures toile", "Mocassins", "Wally Sox", "Adulte", 79.99, 16.10, "6404.19", "printemps", 3, False),
    ("HEYDUDE", "Chaussures toile", "Enfant", "Wendy Youth", "Enfant", 49.99, 9.90, "6404.19", "printemps", 3, False),
]

PROFILS_SAISON = {  # poids mensuels (jan..déc)
    "ete":       [0.55, 0.60, 0.85, 1.05, 1.35, 1.55, 1.60, 1.40, 0.95, 0.70, 0.75, 0.65],
    "ete_fort":  [0.20, 0.25, 0.50, 0.95, 1.60, 2.10, 2.30, 1.90, 0.90, 0.40, 0.45, 0.45],
    "hiver":     [1.40, 1.10, 0.60, 0.35, 0.20, 0.15, 0.15, 0.25, 0.70, 1.40, 2.30, 2.40],
    "automne":   [0.90, 0.80, 0.90, 0.80, 0.50, 0.30, 0.25, 0.45, 1.40, 1.90, 1.60, 1.20],
    "printemps": [0.65, 0.75, 1.20, 1.40, 1.30, 1.10, 1.00, 0.95, 1.05, 0.95, 0.90, 0.75],
    "plat":      [0.80, 0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.05, 0.95, 0.95, 1.15, 1.25],
    "noel":      [0.60, 0.55, 0.65, 0.75, 0.80, 0.85, 0.90, 0.85, 0.85, 1.00, 1.80, 2.60],
}
for k, v in PROFILS_SAISON.items():
    s = sum(v) / 12
    PROFILS_SAISON[k] = [x / s for x in v]

DROITS_UE = {"6402.99": 16.9, "6402.20": 3.5, "6401.92": 17.0, "6402.91": 16.9, "3926.40": 6.5, "6404.19": 17.0}
DROITS_UK = {"6402.99": 16.0, "6402.20": 0.0, "6401.92": 16.0, "6402.91": 16.0, "3926.40": 6.0, "6404.19": 16.0}
POIDS_KG = {"Sabots": 0.42, "Sandales": 0.28, "Bottes": 0.85, "Jibbitz": 0.02, "Chaussures toile": 0.55}
ORIGINES = {"Crocs": ["Vietnam", "Vietnam", "Chine", "Indonésie"], "HEYDUDE": ["Chine", "Vietnam"]}
USD_EUR = 0.92

rows = []
pid = 1
for (marque, cat, scat, modele, cible, prix, fob, sh, profil, nbc, licence) in MODELES:
    cols = rng.choice(COULEURS, size=nbc, replace=False) if nbc < len(COULEURS) else COULEURS
    for c in cols:
        fob_c = round(fob * 1.12 * rng.uniform(0.95, 1.06), 2)
        fob_eur = fob_c * USD_EUR
        fret_unit = round(POIDS_KG[cat] * 1.15 + 0.35, 2)          # fret maritime + pré/post-acheminement
        droits = round((fob_eur + fret_unit) * DROITS_UE[sh] / 100, 2)  # droits sur valeur CAF
        cout_debarque = round(fob_eur + fret_unit + droits, 2)
        lancement = int(rng.choice([2019, 2020, 2021, 2022, 2023, 2024], p=[.3, .15, .15, .15, .15, .1]))
        if modele in ("Classic Crush Clog", "Classic Neo Puff Boot", "Wally Sox", "Brooklyn Low Wedge"):
            lancement = max(lancement, 2023)
        rows.append(dict(
            id_produit=f"P{pid:04d}",
            sku=f"{'CR' if marque == 'Crocs' else 'HD'}-{modele.upper().replace(' ', '')[:10]}-{c[:3].upper()}{pid:03d}",
            marque=marque, categorie=cat, sous_categorie=scat, modele=modele, coloris=c, cible=cible,
            prix_vente_ttc_fr=prix, prix_vente_ht_fr=round(prix / 1.20, 2),
            cout_fob_usd=fob_c, cout_fob_eur=round(fob_eur, 2), cout_fret_unitaire_eur=fret_unit,
            droits_douane_ue_eur=droits, cout_debarque_eur=cout_debarque,
            code_sh=sh, taux_droit_ue_pct=DROITS_UE[sh], taux_droit_uk_pct=DROITS_UK[sh],
            pays_origine=rng.choice(ORIGINES[marque]), poids_unitaire_kg=POIDS_KG[cat],
            profil_saisonnier=profil, produit_sous_licence=licence, annee_lancement=lancement,
            statut="Actif" if not (marque == "HEYDUDE" and rng.random() < 0.15) else "Fin de série",
        ))
        pid += 1
dim_produit = pd.DataFrame(rows)
dim_produit["taux_marge_theorique_pct"] = round(
    (dim_produit.prix_vente_ht_fr - dim_produit.cout_debarque_eur) / dim_produit.prix_vente_ht_fr * 100, 1)
save(dim_produit, "dim_produit")

# --------------------------------------------------------------------------------------
# 4. DIM_HUB_LOGISTIQUE
# --------------------------------------------------------------------------------------
hubs = pd.DataFrame([
    ("H01", "Hub Île-de-France", "Moissy-Cramayel", "FR", 48.6236, 2.5939, 28000, "Entrepôt groupe (simulé)", 2015),
    ("H02", "Hub Rhône-Alpes", "Saint-Quentin-Fallavier", "FR", 45.6453, 5.1095, 18000, "Entrepôt groupe (simulé)", 2019),
    ("H03", "DC Europe Crocs", "Dordrecht", "NL", 51.8133, 4.6901, 60000, "Centre de distribution fournisseur (EMEA)", 2011),
], columns=["id_hub", "nom_hub", "ville", "code_pays", "latitude", "longitude", "surface_m2", "type_hub", "annee_ouverture"])
hubs["capacite_palettes"] = (hubs.surface_m2 * 1.1).astype(int)
save(hubs, "dim_hub_logistique")


def haversine(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------------------
# 5. DIM_MAGASIN – réseau France (X = 48 magasins + 1 canal web)
# --------------------------------------------------------------------------------------
VILLES_FR = [  # ville, région, lat, lon, poids population
    ("Paris", "Île-de-France", 48.8566, 2.3522, 6), ("Lyon", "Auvergne-Rhône-Alpes", 45.7640, 4.8357, 3),
    ("Marseille", "Provence-Alpes-Côte d'Azur", 43.2965, 5.3698, 3), ("Toulouse", "Occitanie", 43.6047, 1.4442, 2),
    ("Nice", "Provence-Alpes-Côte d'Azur", 43.7102, 7.2620, 2), ("Nantes", "Pays de la Loire", 47.2184, -1.5536, 2),
    ("Bordeaux", "Nouvelle-Aquitaine", 44.8378, -0.5792, 2), ("Lille", "Hauts-de-France", 50.6292, 3.0573, 2),
    ("Montpellier", "Occitanie", 43.6108, 3.8767, 2), ("Strasbourg", "Grand Est", 48.5734, 7.7521, 2),
    ("Rennes", "Bretagne", 48.1173, -1.6778, 1), ("Grenoble", "Auvergne-Rhône-Alpes", 45.1885, 5.7245, 1),
    ("Toulon", "Provence-Alpes-Côte d'Azur", 43.1242, 5.9280, 1), ("Dijon", "Bourgogne-Franche-Comté", 47.3220, 5.0415, 1),
    ("Angers", "Pays de la Loire", 47.4784, -0.5632, 1), ("Reims", "Grand Est", 49.2583, 4.0317, 1),
    ("Le Havre", "Normandie", 49.4944, 0.1079, 1), ("Clermont-Ferrand", "Auvergne-Rhône-Alpes", 45.7772, 3.0870, 1),
    ("Tours", "Centre-Val de Loire", 47.3941, 0.6848, 1), ("Biarritz", "Nouvelle-Aquitaine", 43.4832, -1.5586, 1),
    ("La Rochelle", "Nouvelle-Aquitaine", 46.1603, -1.1511, 1), ("Metz", "Grand Est", 49.1193, 6.1757, 1),
    ("Rouen", "Normandie", 49.4431, 1.0993, 1), ("Avignon", "Provence-Alpes-Côte d'Azur", 43.9493, 4.8055, 1),
]
TYPES = {  # type: (surface min, max, loyer €/m²/an, productivité relative)
    "Centre-ville": (70, 140, 1100, 1.15),
    "Centre commercial": (80, 160, 750, 1.00),
    "Outlet": (120, 220, 380, 0.85),
    "Gare / Aéroport": (40, 80, 1900, 1.35),
}
mag_rows = []
mid = 1
for ville, region, lat, lon, w in VILLES_FR:
    for _ in range(w):
        if mid > 48:
            break
        t = rng.choice(list(TYPES), p=[.40, .38, .12, .10])
        if ville == "Paris" and mid in (1, 2):
            t = "Centre-ville"
        smin, smax, loyer, prod = TYPES[t]
        surf = int(rng.integers(smin, smax))
        mult_ville = 1.8 if ville == "Paris" else (1.25 if w >= 2 else 1.0)
        hub = min(hubs[hubs.code_pays == "FR"].itertuples(),
                  key=lambda h: haversine(lat, lon, h.latitude, h.longitude))
        ouverture = int(rng.choice(range(2012, 2025)))
        mag_rows.append(dict(
            id_magasin=f"M{mid:03d}", nom_magasin=f"Crocs {ville} {t.split()[0]}{'' if w == 1 else ' ' + str(mid)}",
            ville=ville, region=region, code_pays="FR",
            latitude=round(lat + rng.normal(0, .02), 4), longitude=round(lon + rng.normal(0, .02), 4),
            type_emplacement=t, surface_vente_m2=surf, annee_ouverture=ouverture,
            loyer_annuel_eur=int(surf * loyer * mult_ville * rng.uniform(.85, 1.15)),
            nb_etp=round(max(3, surf / 22 + rng.normal(0, .8)), 1),
            capex_ouverture_eur=int(surf * rng.uniform(1300, 1800) + 45000),
            id_hub_rattachement=hub.id_hub,
            distance_hub_km=round(haversine(lat, lon, hub.latitude, hub.longitude) * 1.25, 0),
            productivite_relative=prod * (1.25 if ville == "Paris" else 1.0) * rng.uniform(.85, 1.15),
            statut="Ouvert",
        ))
        mid += 1
while mid <= 48:  # compléter jusqu'à 48 avec villes moyennes
    ville, region, lat, lon, w = VILLES_FR[int(rng.integers(0, 10))]
    t = "Centre commercial"
    surf = int(rng.integers(80, 160))
    hub = min(hubs[hubs.code_pays == "FR"].itertuples(), key=lambda h: haversine(lat, lon, h.latitude, h.longitude))
    mag_rows.append(dict(
        id_magasin=f"M{mid:03d}", nom_magasin=f"Crocs {ville} Centre {mid}", ville=ville, region=region, code_pays="FR",
        latitude=round(lat + rng.normal(0, .05), 4), longitude=round(lon + rng.normal(0, .05), 4),
        type_emplacement=t, surface_vente_m2=surf, annee_ouverture=int(rng.choice(range(2016, 2025))),
        loyer_annuel_eur=int(surf * 750 * rng.uniform(.85, 1.15)), nb_etp=round(max(3, surf / 22), 1),
        capex_ouverture_eur=int(surf * rng.uniform(1300, 1800) + 45000), id_hub_rattachement=hub.id_hub,
        distance_hub_km=round(haversine(lat, lon, hub.latitude, hub.longitude) * 1.25, 0),
        productivite_relative=rng.uniform(.85, 1.1), statut="Ouvert"))
    mid += 1
# 2 ouvertures en 2025-2026 pour la dynamique du réseau
mag_rows[-1]["annee_ouverture"] = 2025
mag_rows[-2]["annee_ouverture"] = 2026
dim_magasin = pd.DataFrame(mag_rows)
web = dict(id_magasin="WEB", nom_magasin="crocs.fr (e-commerce)", ville="Moissy-Cramayel", region="Île-de-France",
           code_pays="FR", latitude=48.6236, longitude=2.5939, type_emplacement="E-commerce", surface_vente_m2=0,
           annee_ouverture=2012, loyer_annuel_eur=0, nb_etp=14.0, capex_ouverture_eur=0, id_hub_rattachement="H01",
           distance_hub_km=0, productivite_relative=14.0, statut="Ouvert")
dim_magasin = pd.concat([dim_magasin, pd.DataFrame([web])], ignore_index=True)
prod_rel = dim_magasin.set_index("id_magasin")["productivite_relative"]
dim_magasin_out = dim_magasin.drop(columns="productivite_relative")
dim_magasin_out["canal"] = np.where(dim_magasin_out.id_magasin == "WEB", "Digital", "Magasin physique")
save(dim_magasin_out, "dim_magasin")

# --------------------------------------------------------------------------------------
# 6. FACT_VENTES_FRANCE – mensuel, magasin x produit, jan 2023 -> oct 2026
# --------------------------------------------------------------------------------------
periode = pd.date_range("2023-01-01", "2026-10-01", freq="MS")
CROISSANCE = {2023: 1.00, 2024: 1.065, 2025: 1.095, 2026: 1.12}       # Crocs brand
CROISSANCE_HD = {2023: 1.00, 2024: 0.86, 2025: 0.74, 2026: 0.70}     # HEYDUDE en recul
# vitesse de base (unités / mois / magasin de productivité 1) par modèle
BASE_UNITS = {
    "Classic Clog": 30, "Classic Clog Kids": 22, "Classic Clog Toddler": 14, "Classic Lined Clog": 18,
    "Classic Lined Clog Kids": 12, "Classic Platform Clog": 14, "Mega Crush Clog": 9, "Classic Crush Clog": 8,
    "Crocband Clog": 11, "Echo Clog": 8, "LiteRide 360 Clog": 6, "Bistro Clog": 5, "Classic Sandal": 10,
    "Brooklyn Low Wedge": 7, "Getaway Strappy": 6, "Classic Slide": 9, "Baya Slide": 8, "Classic Flip": 7,
    "Classic Crush Rain Boot": 4, "Classic Neo Puff Boot": 4, "Classic Rain Boot Kids": 4,
    "Jibbitz Charm unitaire": 55, "Jibbitz Pack 3": 16, "Jibbitz Pack 5": 13, "Jibbitz Pack 5 Licence": 12,
    "Classic Clog Licence": 7, "Wally": 6, "Wendy": 5, "Wally Sox": 3, "Wendy Youth": 3,
}
# poids coloris : noir/blanc/marine dominent
POIDS_COUL = {"Noir": 1.8, "Blanc": 1.3, "Bleu marine": 1.2, "Os": 1.0, "Rose ballerine": 0.9}

recs = []
for m in dim_magasin.itertuples():
    pr = prod_rel[m.id_magasin]
    # profondeur d'assortiment : les petits magasins n'ont pas tout
    if m.id_magasin == "WEB":
        part_assort = 1.0
    else:
        part_assort = min(1.0, 0.55 + m.surface_vente_m2 / 400)
    sud = m.latitude < 45.0
    for p in dim_produit.itertuples():
        if m.id_magasin != "WEB" and rng.random() > part_assort and p.coloris not in ("Noir", "Blanc"):
            continue
        base = 3.8 * BASE_UNITS[p.modele] / (len(dim_produit[dim_produit.modele == p.modele]) ** 0.55) \
               * POIDS_COUL.get(p.coloris, 0.75) * pr
        prof = PROFILS_SAISON[p.profil_saisonnier]
        for d in periode:
            if d.year < m.annee_ouverture or (d.year == m.annee_ouverture and d.month < 4):
                continue
            if d.year < p.annee_lancement:
                continue
            g = (CROISSANCE_HD if p.marque == "HEYDUDE" else CROISSANCE)[d.year]
            climat = 1.0
            if sud and p.profil_saisonnier in ("ete", "ete_fort"):
                climat = 1.18
            if sud and p.profil_saisonnier == "hiver":
                climat = 0.75
            mu = base * prof[d.month - 1] * g * climat
            q = int(rng.poisson(max(mu, 0.01)))
            if q == 0:
                continue
            # remise moyenne : soldes, Black Friday, outlet
            remise = 0.03
            if d.month in (1, 7):
                remise = 0.22
            elif d.month == 11:
                remise = 0.15
            elif d.month in (2, 8):
                remise = 0.10
            if m.type_emplacement == "Outlet":
                remise += 0.20
            if p.statut == "Fin de série":
                remise += 0.15
            remise = min(0.6, remise * rng.uniform(0.8, 1.2))
            prix_ttc = p.prix_vente_ttc_fr * (1.0 + 0.03 * (d.year - 2023))  # hausse tarifaire annuelle ~3 %
            ca_brut_ttc = q * prix_ttc
            ca_ttc = ca_brut_ttc * (1 - remise)
            ca_ht = ca_ttc / 1.20
            cogs = q * p.cout_debarque_eur * (1 + 0.02 * (d.year - 2023))
            recs.append((int(d.strftime("%Y%m")), m.id_magasin, p.id_produit, q,
                         round(ca_brut_ttc, 2), round(ca_ttc, 2), round(ca_ht, 2), round(cogs, 2)))

ventes = pd.DataFrame(recs, columns=["id_date", "id_magasin", "id_produit", "quantite_vendue",
                                     "ca_brut_ttc_eur", "ca_net_ttc_eur", "ca_net_ht_eur", "cout_marchandises_eur"])
ventes["remise_eur"] = (ventes.ca_brut_ttc_eur - ventes.ca_net_ttc_eur).round(2)
ventes["marge_brute_eur"] = (ventes.ca_net_ht_eur - ventes.cout_marchandises_eur).round(2)
# taux de retour (surtout web)
ventes["quantite_retournee"] = np.where(ventes.id_magasin == "WEB",
                                        rng.binomial(ventes.quantite_vendue, 0.11),
                                        rng.binomial(ventes.quantite_vendue, 0.025))
ventes.insert(0, "id_vente", np.arange(1, len(ventes) + 1))
save(ventes, "fact_ventes_france")

# --------------------------------------------------------------------------------------
# 7. FACT_MARCHE – taille de marché par pays, segment, année (2019-2029, projections incluses)
# --------------------------------------------------------------------------------------
# marché total chaussures 2024 (Md€, prix de vente au détail TTC) et part du segment « casual moulé & sandales »
MARCHE_2024 = {"FR": (9.7, .105), "DE": (11.6, .095), "ES": (5.9, .135), "IT": (8.9, .110),
               "BE": (1.9, .100), "NL": (2.9, .090), "GB": (12.4, .100)}
CAGR = {"FR": .021, "DE": .018, "ES": .034, "IT": .015, "BE": .019, "NL": .022, "GB": .024}
CAGR_SEG = {"FR": .046, "DE": .052, "ES": .061, "IT": .041, "BE": .044, "NL": .047, "GB": .055}
choc = {2019: 1.0, 2020: 0.82, 2021: 0.93, 2022: 1.0}  # COVID
mk = []
for c, (tot24, seg24) in MARCHE_2024.items():
    for y in range(2019, 2030):
        if y <= 2022:
            tot = tot24 / (1 + CAGR[c]) ** (2024 - 2022) * choc[y] * (1 + CAGR[c]) ** (y - 2022) if y < 2022 else tot24 / (1 + CAGR[c]) ** 2
            seg = seg24 * tot * (1 - 0.012 * (2024 - y))
        else:
            tot = tot24 * (1 + CAGR[c]) ** (y - 2024)
            seg = seg24 * tot24 * (1 + CAGR_SEG[c]) ** (y - 2024)
        noise = rng.normal(1, .008) if y <= 2025 else 1.0
        mk.append(dict(code_pays=c, annee=y, segment="Chaussures (total)", taille_marche_meur=round(tot * 1000 * noise, 1)))
        mk.append(dict(code_pays=c, annee=y, segment="Casual moulé & sandales", taille_marche_meur=round(seg * 1000 * noise, 1)))
marche = pd.DataFrame(mk).sort_values(["code_pays", "segment", "annee"])
marche["taux_croissance_annuel_pct"] = (marche.groupby(["code_pays", "segment"]).taille_marche_meur.pct_change() * 100).round(2)
marche["est_projection"] = marche.annee >= 2026
marche["source"] = np.where(marche.est_projection, "Projection interne (CAGR)", "Panel marché simulé (calibré Euromonitor/Statista)")
save(marche.reset_index(drop=True), "fact_marche")

# --------------------------------------------------------------------------------------
# 8. DIM_CONCURRENT + FACT_PARTS_DE_MARCHE (segment casual moulé & sandales)
# --------------------------------------------------------------------------------------
conc = pd.DataFrame([
    ("C00", "Crocs", "Marque (nous)", "Moyen", 50, "USA"),
    ("C01", "Birkenstock", "Marque premium", "Premium", 110, "Allemagne"),
    ("C02", "Havaianas", "Marque", "Entrée/Moyen", 30, "Brésil"),
    ("C03", "Skechers", "Marque", "Moyen", 60, "USA"),
    ("C04", "Adidas (Adilette)", "Équipementier sport", "Moyen", 35, "Allemagne"),
    ("C05", "Nike (Slides)", "Équipementier sport", "Moyen", 40, "USA"),
    ("C06", "Deichmann (MDD)", "Distributeur spécialisé", "Entrée", 18, "Allemagne"),
    ("C07", "Primark", "Distributeur mode discount", "Entrée", 8, "Irlande"),
    ("C08", "Decathlon", "Distributeur sport", "Entrée", 15, "France"),
    ("C09", "Inditex (Zara/Bershka)", "Distributeur mode", "Entrée/Moyen", 30, "Espagne"),
    ("C10", "Hunter / Aigle", "Spécialiste bottes", "Premium", 120, "Royaume-Uni/France"),
    ("C99", "Autres / MDD", "Divers", "Divers", 25, "-"),
], columns=["id_concurrent", "nom_concurrent", "type_acteur", "positionnement_prix", "prix_moyen_eur", "pays_origine"])
save(conc, "dim_concurrent")

PDM_2025 = {  # parts de marché valeur du segment, 2025
    "FR": {"C00": 24, "C01": 13, "C02": 9, "C03": 6, "C04": 7, "C05": 6, "C06": 2, "C07": 4, "C08": 9, "C09": 5, "C10": 3},
    "DE": {"C00": 14, "C01": 23, "C02": 5, "C03": 7, "C04": 9, "C05": 6, "C06": 12, "C07": 4, "C08": 2, "C09": 4, "C10": 2},
    "ES": {"C00": 17, "C01": 10, "C02": 15, "C03": 6, "C04": 7, "C05": 6, "C06": 3, "C07": 6, "C08": 8, "C09": 10, "C10": 1},
    "IT": {"C00": 15, "C01": 14, "C02": 12, "C03": 6, "C04": 9, "C05": 7, "C06": 2, "C07": 2, "C08": 7, "C09": 8, "C10": 2},
    "BE": {"C00": 16, "C01": 15, "C02": 8, "C03": 7, "C04": 8, "C05": 6, "C06": 5, "C07": 6, "C08": 9, "C09": 5, "C10": 3},
    "NL": {"C00": 15, "C01": 17, "C02": 7, "C03": 8, "C04": 9, "C05": 7, "C06": 6, "C07": 7, "C08": 4, "C09": 5, "C10": 4},
    "GB": {"C00": 18, "C01": 14, "C02": 6, "C03": 9, "C04": 7, "C05": 9, "C06": 0, "C07": 10, "C08": 2, "C09": 5, "C10": 6},
}
TENDANCE = {"C00": .6, "C01": .5, "C03": .2, "C07": -.2, "C09": -.1, "C02": -.3}  # pts de part / an
pdm = []
seg = marche[marche.segment == "Casual moulé & sandales"].set_index(["code_pays", "annee"]).taille_marche_meur
for c, d in PDM_2025.items():
    for y in range(2021, 2026):
        parts = {k: max(0.0, v - TENDANCE.get(k, 0) * (2025 - y) + rng.normal(0, .3)) for k, v in d.items()}
        parts["C99"] = max(5.0, 100 - sum(parts.values()))
        s = sum(parts.values())
        for k, v in parts.items():
            pct = v / s * 100
            pdm.append(dict(code_pays=c, annee=y, id_concurrent=k, part_marche_valeur_pct=round(pct, 2),
                            ca_estime_meur=round(pct / 100 * seg[(c, y)], 1)))
pdm = pd.DataFrame(pdm)
save(pdm, "fact_parts_de_marche")

# --------------------------------------------------------------------------------------
# 9. DIM_ZONE_CHALANDISE (villes cibles) + FACT_IMPLANTATION (densité concurrentielle, loyers)
# --------------------------------------------------------------------------------------
VILLES = {
    "DE": [("Berlin", 3.75, 52.5200, 13.4050, 2400), ("Hamburg", 1.91, 53.5511, 9.9937, 2700), ("München", 1.51, 48.1351, 11.5820, 3300),
           ("Köln", 1.09, 50.9375, 6.9603, 2500), ("Frankfurt", 0.77, 50.1109, 8.6821, 2600), ("Stuttgart", 0.63, 48.7758, 9.1829, 2200),
           ("Düsseldorf", 0.63, 51.2277, 6.7735, 2800), ("Leipzig", 0.62, 51.3397, 12.3731, 1100), ("Dortmund", 0.59, 51.5136, 7.4653, 1300),
           ("Nürnberg", 0.53, 49.4521, 11.0767, 1500), ("Hannover", 0.54, 52.3759, 9.7320, 1500), ("Dresden", 0.56, 51.0504, 13.7373, 1200)],
    "ES": [("Madrid", 3.33, 40.4168, -3.7038, 3200), ("Barcelona", 1.66, 41.3874, 2.1686, 3400), ("Valencia", 0.80, 39.4699, -0.3763, 1500),
           ("Sevilla", 0.68, 37.3891, -5.9845, 1300), ("Zaragoza", 0.68, 41.6488, -0.8891, 1000), ("Málaga", 0.59, 36.7213, -4.4214, 1600),
           ("Palma", 0.42, 39.5696, 2.6502, 1700), ("Bilbao", 0.35, 43.2630, -2.9350, 1500), ("Alicante", 0.35, 38.3452, -0.4810, 1100),
           ("Las Palmas", 0.38, 28.1235, -15.4363, 1000)],
    "IT": [("Roma", 2.75, 41.9028, 12.4964, 3800), ("Milano", 1.37, 45.4642, 9.1900, 5200), ("Napoli", 0.91, 40.8518, 14.2681, 1800),
           ("Torino", 0.85, 45.0703, 7.6869, 1700), ("Palermo", 0.63, 38.1157, 13.3615, 1200), ("Genova", 0.56, 44.4056, 8.9463, 1300),
           ("Bologna", 0.39, 44.4949, 11.3426, 1900), ("Firenze", 0.36, 43.7696, 11.2558, 2900), ("Verona", 0.26, 45.4384, 10.9916, 1800),
           ("Bari", 0.32, 41.1171, 16.8719, 1100)],
    "BE": [("Bruxelles", 1.24, 50.8503, 4.3517, 1900), ("Antwerpen", 0.53, 51.2194, 4.4025, 1800), ("Gent", 0.27, 51.0543, 3.7174, 1300),
           ("Liège", 0.20, 50.6326, 5.5797, 900), ("Charleroi", 0.20, 50.4108, 4.4446, 600), ("Brugge", 0.12, 51.2093, 3.2247, 1000)],
    "NL": [("Amsterdam", 0.92, 52.3676, 4.9041, 3000), ("Rotterdam", 0.66, 51.9244, 4.4777, 1500), ("Den Haag", 0.56, 52.0705, 4.3007, 1300),
           ("Utrecht", 0.37, 52.0907, 5.1214, 1600), ("Eindhoven", 0.24, 51.4416, 5.4697, 1000), ("Groningen", 0.24, 53.2194, 6.5665, 900)],
    "GB": [("London", 8.90, 51.5074, -0.1278, 6500), ("Manchester", 0.55, 53.4808, -2.2426, 2300), ("Birmingham", 1.14, 52.4862, -1.8904, 2100),
           ("Glasgow", 0.63, 55.8642, -4.2518, 1800), ("Leeds", 0.80, 53.8008, -1.5491, 1900), ("Liverpool", 0.50, 53.4084, -2.9916, 1600),
           ("Bristol", 0.47, 51.4545, -2.5879, 1700), ("Edinburgh", 0.52, 55.9533, -3.1883, 2000), ("Newcastle", 0.30, 54.9783, -1.6178, 1300)],
}
REVENU = {"DE": 108, "ES": 84, "IT": 92, "BE": 106, "NL": 112, "GB": 98}
zones, impl, flux = [], [], []
zid = 1
for c, lst in VILLES.items():
    for ville, pop, lat, lon, loyer_hs in lst:
        z = f"Z{zid:03d}"
        zones.append(dict(
            id_zone=z, code_pays=c, ville=ville, latitude=lat, longitude=lon,
            population_ville_millions=pop,
            population_zone_chalandise_millions=round(pop * rng.uniform(1.6, 2.6), 2),
            indice_revenu_ue100=round(REVENU[c] * rng.uniform(.88, 1.15)),
            indice_frequentation_commerce=round(min(100, 40 + pop * 9 + rng.normal(0, 6)), 1),
            nb_centres_commerciaux=int(max(1, round(pop * rng.uniform(4, 7)))),
            part_touristes_pct=round(rng.uniform(4, 22) if ville in ("Barcelona", "Palma", "Málaga", "Roma", "Firenze", "Amsterdam", "London", "Brugge", "München") else rng.uniform(1, 7), 1),
            climat_temperature_moy_ete=round({"DE": 23, "ES": 30, "IT": 29, "BE": 22, "NL": 21, "GB": 20}[c] + rng.normal(0, 1.5), 1),
        ))
        # densité concurrentielle : nb de points de vente concurrents dans la zone
        for k, nom in conc[["id_concurrent", "nom_concurrent"]].itertuples(index=False):
            if k in ("C00", "C99"):
                continue
            part = PDM_2025[c][k]
            n = int(rng.poisson(pop * part * 0.9))
            if n:
                impl.append(dict(id_zone=z, id_concurrent=k, nb_points_de_vente=n,
                                 dont_magasins_propres=int(n * rng.uniform(0.05, 0.35) if k in ("C01", "C03", "C06", "C07", "C08", "C09") else n * 0.03)))
        # Crocs présent seulement via revendeurs
        impl.append(dict(id_zone=z, id_concurrent="C00", nb_points_de_vente=int(rng.poisson(pop * 8)), dont_magasins_propres=0))
        for h in hubs.itertuples():
            dist = haversine(h.latitude, h.longitude, lat, lon) * 1.25
            transmanche = c == "GB"
            cout_pal = 45 + dist * 0.13 + (95 if transmanche else 0)
            flux.append(dict(id_hub=h.id_hub, id_zone=z, distance_route_km=round(dist),
                             delai_livraison_jours=round(1 + dist / 650 + (1.5 if transmanche else 0), 1),
                             cout_transport_palette_eur=round(cout_pal, 2),
                             cout_transport_unitaire_eur=round(cout_pal / 180, 3),  # ~180 paires / palette
                             frais_dedouanement_par_envoi_eur=85.0 if transmanche else 0.0,
                             emissions_co2_kg_palette=round(dist * 0.062, 1)))
        zid += 1
zones = pd.DataFrame(zones)
impl = pd.DataFrame(impl)
dens = impl[impl.id_concurrent != "C00"].groupby("id_zone").nb_points_de_vente.sum()
zones["nb_points_vente_concurrents"] = zones.id_zone.map(dens).fillna(0).astype(int)
zones["densite_concurrentielle_pour_100k_hab"] = (zones.nb_points_vente_concurrents / (zones.population_ville_millions * 10)).round(2)
save(zones, "dim_zone_chalandise")
save(impl, "fact_presence_concurrents")
save(pd.DataFrame(flux), "fact_logistique")

# Loyers commerciaux par zone et type d'emplacement (€/m²/an, hors charges) 2023-2026
loy = []
lookup = {v[0]: v[4] for lst in VILLES.values() for v in lst}
for zr in zones.itertuples():
    hs = lookup[zr.ville]
    for y in range(2023, 2027):
        idx = (1 + 0.025) ** (y - 2023)
        for t, ratio in (("Centre-ville (prime)", 1.0), ("Centre-ville (secondaire)", 0.38),
                         ("Centre commercial", 0.30), ("Outlet", 0.14), ("Gare / Aéroport", 0.75)):
            base = hs * ratio * idx * rng.uniform(.92, 1.08)
            if zr.code_pays == "GB":
                base *= 1.0  # déjà converti en € (taux 0,85)
            loy.append(dict(id_zone=zr.id_zone, annee=y, type_emplacement=t, loyer_m2_an_eur=round(base),
                            charges_m2_an_eur=round(base * rng.uniform(.10, .18)),
                            taux_vacance_pct=round(rng.uniform(4, 14), 1)))
save(pd.DataFrame(loy), "fact_immobilier")

# --------------------------------------------------------------------------------------
# 10. FACT_FISCALITE – TVA, IS, droits de douane, éco-contribution (une ligne par pays)
# --------------------------------------------------------------------------------------
fisc = pd.DataFrame([
    # pays, tva_std, tva_chauss_enfant, is_pct, taxe_locale_pct, eco_contrib_paire, droit_import_depuis_fr_pct, regime_douane
    ("FR", 20.0, 20.0, 25.00, 0.0, 0.07, 0.0, "Marché national", "Refashion (REP TLC)"),
    ("DE", 19.0, 19.0, 29.90, 0.0, 0.00, 0.0, "Marché unique UE", "Aucune REP chaussures"),
    ("ES", 21.0, 21.0, 25.00, 0.0, 0.00, 0.0, "Marché unique UE", "REP textile en déploiement (2025+)"),
    ("IT", 22.0, 22.0, 27.90, 0.0, 0.00, 0.0, "Marché unique UE", "Aucune REP chaussures"),
    ("BE", 21.0, 21.0, 25.00, 0.0, 0.00, 0.0, "Marché unique UE", "Aucune REP chaussures"),
    ("NL", 21.0, 21.0, 25.80, 0.0, 0.03, 0.0, "Marché unique UE", "UPV textiel (2023+)"),
    ("GB", 20.0, 0.0, 25.00, 0.0, 0.00, 16.0, "Pays tiers (post-Brexit)", "Aucune REP chaussures"),
], columns=["code_pays", "taux_tva_standard_pct", "taux_tva_chaussures_enfant_pct", "taux_impot_societes_pct",
            "taxe_locale_additionnelle_pct", "eco_contribution_par_paire_eur", "droit_import_marchandise_origine_asie_via_fr_pct",
            "regime_douanier", "regime_rep"])
fisc["note"] = np.where(fisc.code_pays == "GB",
                        "Produits d'origine Asie : pas d'origine préférentielle UE -> droits UK Global Tariff + déclarations import ; TVA enfant à 0 %",
                        np.where(fisc.code_pays == "FR", "Pays de référence", "Libre circulation : droits déjà acquittés à l'entrée UE"))
save(fisc, "fact_fiscalite")

# --------------------------------------------------------------------------------------
# 11. FACT_COUTS_EXPLOITATION – coûts d'exploitation magasin par pays (2026)
# --------------------------------------------------------------------------------------
couts = pd.DataFrame([
    # pays, salaire brut mensuel vendeur, charges patronales %, smic mensuel, fitout €/m², énergie €/m²/an, marketing lancement €/magasin, heures hebdo
    ("FR", 1950, 42.0, 1802, 1550, 42, 40000, 35),
    ("DE", 2550, 21.0, 2222, 1650, 55, 55000, 39),
    ("ES", 1600, 31.5, 1381, 1250, 38, 35000, 40),
    ("IT", 1850, 30.0, None, 1400, 48, 40000, 40),
    ("BE", 2400, 27.0, 2070, 1600, 50, 35000, 38),
    ("NL", 2450, 22.0, 2280, 1600, 52, 40000, 38),
    ("GB", 2150, 15.0, 2050, 1700, 60, 60000, 39),
], columns=["code_pays", "salaire_brut_mensuel_vendeur_eur", "taux_charges_patronales_pct", "salaire_minimum_mensuel_eur",
            "cout_amenagement_m2_eur", "cout_energie_m2_an_eur", "budget_marketing_lancement_eur", "duree_hebdo_travail_h"])
couts["cout_complet_annuel_etp_eur"] = (couts.salaire_brut_mensuel_vendeur_eur * 12.5 * (1 + couts.taux_charges_patronales_pct / 100)).round(0)
couts["annee_reference"] = 2026
save(couts, "fact_couts_exploitation")

# --------------------------------------------------------------------------------------
# 12. FACT_PRIX_RELEVES – relevés de prix (scraping simulé), Crocs + équivalents concurrents
# --------------------------------------------------------------------------------------
ENSEIGNES = {
    "FR": ["crocs.fr", "Zalando", "Sarenza", "Courir", "Amazon"],
    "DE": ["crocs.de", "Zalando", "About You", "Deichmann", "Amazon"],
    "ES": ["crocs.es", "Zalando", "El Corte Inglés", "Foot Locker", "Amazon"],
    "IT": ["crocs.it", "Zalando", "Foot Locker", "AW Lab", "Amazon"],
    "BE": ["crocs.be", "Zalando", "Torfs", "Bristol", "Amazon"],
    "NL": ["crocs.nl", "Zalando", "Bol.com", "Schuurman Schoenen", "Amazon"],
    "GB": ["crocs.co.uk", "JD Sports", "Schuh", "Office", "Amazon"],
}
# prix officiel local relatif à la France (la marque harmonise largement ses prix en zone euro)
PRIX_REL = {"FR": 1.00, "DE": 0.995, "ES": 1.00, "IT": 1.00, "BE": 1.00, "NL": 1.00, "GB": 0.90 / 0.85}  # £44.99 ≈ 52.9 €
EQUIV = [("C01", "Birkenstock Arizona EVA", 40), ("C01", "Birkenstock Boston", 150), ("C02", "Havaianas Top", 28),
         ("C04", "Adidas Adilette Comfort", 35), ("C05", "Nike Victori One Slide", 32), ("C03", "Skechers Foamies", 45),
         ("C06", "Deichmann Graceland Clog", 13), ("C07", "Primark sabot EVA", 8), ("C08", "Decathlon sabot EVA", 12)]
modeles_releve = dim_produit[dim_produit.coloris == "Noir"].drop_duplicates("modele")
rel = []
rid = 1
for d in pd.date_range("2025-01-01", "2026-10-01", freq="QS"):
    for c, ens in ENSEIGNES.items():
        for e in ens:
            officiel = e.startswith("crocs")
            for p in modeles_releve.itertuples():
                if rng.random() < (0.05 if officiel else 0.35):
                    continue
                base = p.prix_vente_ttc_fr * PRIX_REL[c]
                promo = rng.random() < (0.12 if officiel else 0.30)
                remise = rng.uniform(.15, .35) if promo else 0
                if not officiel:
                    base *= rng.uniform(.95, 1.0)
                prix = base * (1 - remise)
                rel.append(dict(id_releve=rid, id_date=int(d.strftime("%Y%m")), code_pays=c, enseigne=e,
                                id_concurrent="C00", id_produit=p.id_produit, libelle_produit=p.modele,
                                categorie=p.categorie, prix_affiche_eur=round(prix, 2),
                                prix_affiche_devise_locale=round(prix * (0.85 if c == "GB" else 1), 2),
                                en_promotion=promo, taux_remise_pct=round(remise * 100, 1)))
                rid += 1
            if officiel:
                continue
            for k, lib, px in EQUIV:
                if (k == "C06" and c not in ("DE", "NL", "BE", "ES", "IT")) or rng.random() < 0.4:
                    continue
                niveau = pays.set_index("code_pays").indice_niveau_prix_chaussures_ue100[c] / 103
                promo = rng.random() < 0.25
                remise = rng.uniform(.1, .3) if promo else 0
                prix = px * niveau * rng.uniform(.95, 1.05) * (1 - remise)
                rel.append(dict(id_releve=rid, id_date=int(d.strftime("%Y%m")), code_pays=c, enseigne=e,
                                id_concurrent=k, id_produit=None, libelle_produit=lib,
                                categorie="Sabots" if "lo" in lib.lower() or "sabot" in lib.lower() else "Sandales",
                                prix_affiche_eur=round(prix, 2), prix_affiche_devise_locale=round(prix * (0.85 if c == "GB" else 1), 2),
                                en_promotion=promo, taux_remise_pct=round(remise * 100, 1)))
                rid += 1
save(pd.DataFrame(rel), "fact_prix_releves")

# --------------------------------------------------------------------------------------
# 13. FACT_PENETRATION_CATEGORIES – % de consommateurs (18-65) ayant acheté la catégorie sur 12 mois
# --------------------------------------------------------------------------------------
PEN = {  # Sabots, Sandales, Bottes, Jibbitz, Chaussures toile
    "FR": (14.5, 38.0, 12.0, 4.8, 7.5), "DE": (11.0, 34.0, 13.5, 3.1, 6.0), "ES": (15.5, 46.0, 6.5, 4.2, 5.5),
    "IT": (12.0, 43.0, 8.0, 3.6, 5.0), "BE": (12.5, 33.0, 15.0, 3.5, 6.5), "NL": (10.5, 31.0, 17.5, 2.9, 7.0),
    "GB": (13.0, 33.0, 18.0, 4.5, 9.5),
}
CATS = ["Sabots", "Sandales", "Bottes", "Jibbitz", "Chaussures toile"]
pen = []
for c, vals in PEN.items():
    for y in (2024, 2025):
        for cat, v in zip(CATS, vals):
            vv = v * (0.96 if y == 2024 else 1.0) * rng.uniform(.98, 1.02)
            pen.append(dict(code_pays=c, annee=y, categorie=cat, taux_penetration_pct=round(vv, 1),
                            panier_moyen_categorie_eur=round({"Sabots": 47, "Sandales": 36, "Bottes": 58, "Jibbitz": 16, "Chaussures toile": 62}[cat]
                                                             * pays.set_index("code_pays").indice_niveau_prix_chaussures_ue100[c] / 103 * rng.uniform(.95, 1.05), 2),
                            taille_echantillon=int(rng.integers(1800, 2600)), source="Enquête consommateurs simulée (panel online)"))
save(pd.DataFrame(pen), "fact_penetration_categories")

# --------------------------------------------------------------------------------------
# 14. FACT_ELIGIBILITE_ASSORTIMENT – produit x pays
# --------------------------------------------------------------------------------------
elig = []
for c in ["DE", "ES", "IT", "BE", "NL", "GB"]:
    for p in dim_produit.itertuples():
        ok, motif = True, "Éligible"
        if p.produit_sous_licence and c in ("GB", "IT"):
            ok, motif = False, "Droits de licence non couverts sur le territoire"
        elif p.marque == "HEYDUDE" and c == "IT":
            ok, motif = False, "Contrat de distribution exclusif existant (HEYDUDE Italie)"
        elif p.statut == "Fin de série":
            ok, motif = False, "Produit en fin de série"
        elif p.modele == "Bistro Clog" and c in ("ES", "IT"):
            ok, motif = False, "Certification EN ISO 20347 locale non obtenue"
        demande = 1.0
        if p.profil_saisonnier == "hiver" and c in ("ES", "IT"):
            demande = 0.45
        if p.categorie == "Bottes" and c in ("NL", "GB", "BE"):
            demande = 1.4
        if p.profil_saisonnier == "ete_fort" and c in ("ES", "IT"):
            demande = 1.35
        if p.marque == "HEYDUDE" and c in ("GB",):
            demande = 1.3
        demande = round(demande * rng.uniform(.9, 1.1), 2)
        reco = "Exclu" if not ok else ("Assortiment cœur" if demande >= 0.9 else "Assortiment optionnel")
        elig.append(dict(code_pays=c, id_produit=p.id_produit, eligible=ok, motif=motif,
                         indice_demande_locale=demande, recommandation_assortiment=reco,
                         adaptation_requise="Étiquetage tailles UK + marquage UKCA" if c == "GB" and ok else
                         ("Notice multilingue NL/FR" if c == "BE" and ok else ("Traduction étiquetage" if ok else ""))))
save(pd.DataFrame(elig), "fact_eligibilite_assortiment")

# --------------------------------------------------------------------------------------
# 15. FACT_TENDANCES_RECHERCHE – intérêt de recherche mensuel « crocs » (type Google Trends, 0-100)
# --------------------------------------------------------------------------------------
tr = []
NIVEAU = {"FR": 62, "DE": 48, "ES": 66, "IT": 55, "BE": 58, "NL": 50, "GB": 70}
for c, lvl in NIVEAU.items():
    for d in pd.date_range("2022-01-01", "2026-10-01", freq="MS"):
        s = PROFILS_SAISON["ete"][d.month - 1]
        if c in ("ES", "IT"):
            s = s ** 1.25
        trend = 1 + 0.045 * (d.year - 2022 + d.month / 12)
        v = lvl * s * trend * rng.normal(1, .05)
        tr.append(dict(code_pays=c, id_date=int(d.strftime("%Y%m")), mot_cle="crocs", indice_interet=v))
tr = pd.DataFrame(tr)
tr["indice_interet"] = (tr.indice_interet / tr.indice_interet.max() * 100).round(0).astype(int)
save(tr, "fact_tendances_recherche")

print(f"\nFichiers écrits dans : {OUT.resolve()}")
