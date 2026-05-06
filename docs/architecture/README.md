# Architecture — Plateforme SI Météo Gouvernée

Ce dossier contient les documents de **vision stratégique** d'une plateforme SI météo cible. Ils ont été produits collectivement et structurent la **réorientation du projet Nephos** comme couche sémantique de cette plateforme cible.

## Pourquoi cette réorientation

Le projet Nephos a démarré comme **référentiel SKOS** des grandeurs météo (CF + QUDT + WMO + ECMWF). Cette mission reste valide et les 19 PR mergées sont préservées.

Mais le sens du projet a évolué : Nephos n'est pas une fin en soi. C'est la **couche sémantique** d'une plateforme plus large dont l'enjeu est de résoudre les problèmes structurels des opérateurs météo nationaux (réplications, gouvernance, scalabilité au pétaoctet).

Les quatre documents ci-dessous formalisent cette vision élargie.

## Les quatre livrables

| Document | Rôle | Public principal |
|---|---|---|
| [`architecture_si_meteo.md`](architecture_si_meteo.md) | Vision technique + 8 annexes opérationnelles (alerting, fraîcheur, complétude, cycle de vie, pré-traitement, saisie, modifications, accès) | Architectes, DSI, équipes data |
| [`architecture_fonctionnelle_si_meteo.md`](architecture_fonctionnelle_si_meteo.md) | Capacités fonctionnelles, business case, scénarios métier, transition | Sponsor exécutif, DSI métier |
| [`benchmark_plateformes_meteo.md`](benchmark_plateformes_meteo.md) | Comparatif analytique de 8 plateformes existantes (MARS, NOAA BDP, EUMETSAT, Copernicus, Pangeo, Planetary Computer, Earth Engine, AWS Open Data) | Architectes, sponsor |
| [`sin_internes_smn.md`](sin_internes_smn.md) | Cartographie des SI internes propriétaires des services météo nationaux | Architectes, sponsor |

Versions `.docx` générées dans [`docx/`](docx/) (générées via `pandoc`).

## Ordre de lecture suggéré

1. **Synthèse exécutive** (section 0 du document fonctionnel) — 1 page, pour décider si on continue.
2. **Document fonctionnel** complet — pour comprendre la cible, son business case, sa transition.
3. **Document technique** — pour comprendre l'architecture, les principes, les annexes opérationnelles.
4. **Benchmark** + **SI internes** — pour situer la cible dans l'écosystème mondial.

## Position de Nephos dans la cible

Dans l'architecture cible décrite, Nephos couvre **une couche** : la **couche sémantique** (glossaire métier, mappings inter-encodings CF / GRIB / BUFR / ECMWF / WMO).

Les autres couches restent à construire :

- **Catalogue technique** (Iceberg + Lakekeeper) : pas encore amorcé.
- **Stockage objet** (MinIO / Ceph + Zarr / Parquet) : pas encore amorcé.
- **Orchestration** (Dagster ou Kestra) : pas encore amorcé.
- **Compute** (DuckDB + xarray + Dask) : pas encore amorcé.
- **Service de résolution sémantique** : esquissé dans le code Nephos, à étendre.
- **Gouvernance** (data contracts, alerting, fraîcheur, complétude, modifications, accès) : conceptualisée dans les documents, à implémenter.

## État de validation

Ces documents sont **drafts** soumis à critique structurante. Décisions à prendre avant tout engagement :

1. Sponsor exécutif identifié et engagé pour 3 ans minimum ?
2. Cible (Météo-France seul / consortium ALADIN-ACCORD-EUMETNET / produit générique) ?
3. Budget pluri-annuel provisionné ?
4. Équipe minimale viable identifiée et engagée ?

Sans réponse à ces quatre, ces documents restent un cadre intellectuel.

## Limites assumées

- Le diagnostic de l'existant est posé en **hypothèses à valider** par audit terrain, pas en constats.
- Les chiffres avancés sont des **ordres de grandeur conservateurs** explicités.
- Les documents n'ont **pas été relus par un juriste** sur OACI / WMO Resolution 40 / RGPD / IGI 1300.
- Les choix techniques sont **substituables** ; les principes architecturaux ne le sont pas.

## Évolution

Toute critique structurante est **attendue avant rédaction des ADR détaillés** (ADR 0006 à 0019, listés en section 9 du document technique) **et avant démarrage du POC Sprint 1**.

Les ADR seront rédigés **dataset par dataset, capacité par capacité**, à mesure des décisions d'arbitrage.
