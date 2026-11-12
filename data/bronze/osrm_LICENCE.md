# Données OSRM et Nominatim

Les fichiers `osrm_*` de ce dossier viennent de deux services fondés sur OpenStreetMap : Nominatim pour les coordonnées des communes des hubs (`osrm_geocodage_<id_hub>_<date>.json`) et le serveur public OSRM pour les trajets (`osrm_trajet_<id_hub>_<id_zone>_<date>.json`). `osrm_distances.csv` en est tiré par `src/collect/osrm.py`.

Itinéraires : OSRM. Données © les contributeurs d'OpenStreetMap, disponibles sous licence ODbL : <https://www.openstreetmap.org/copyright>.

Instantané du 12/11/2026. L'emplacement des hubs est une hypothèse du scénario : chaque hub est placé au centre de sa commune.
