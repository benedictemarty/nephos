# Architecture — Programme Nephos (Plateforme SI Météo Gouvernée)

Ce dossier contient les documents de **vision stratégique** du **programme Nephos**, plateforme SI météo gouvernée Po-scale.

## Taxonomie Nephos

Nephos est un **programme** composé de plusieurs **briques techniques** :

```
Nephos (programme)
├── Nephos Vocab       — couche sémantique (SKOS + CF + QUDT + WMO + ECMWF)  ✅ en place
├── Nephos Catalog     — catalogue technique Iceberg + Lakekeeper             📋 à construire
├── Nephos Storage     — stockage objet MinIO/Ceph + Zarr / Parquet            📋 à construire
├── Nephos Workflow    — orchestration Dagster ou Kestra                       📋 à construire
├── Nephos Contracts   — data contracts versionnés en Git                      📋 à construire
├── Nephos Watch       — alerting métier + fraîcheur SLA + complétude          📋 à construire
├── Nephos Vault       — habilitations + classifications L0-L3 (ABAC)          📋 à construire
├── Nephos Capture     — saisie opérateur (DataWindow)                         📋 à construire
└── Nephos Trace       — modifications append-only event sourcing              📋 à construire
```

Chaque sous-marque désigne **l'intégration et la gouvernance** d'une couche, pas une réimplémentation des briques OSS sous-jacentes (Iceberg, Lakekeeper, Dagster, Kestra, OPA, etc.) qui gardent leurs noms d'origine. Nephos est l'**intégrateur**, pas un fork.

## Historique

Le projet a démarré comme **référentiel SKOS** des grandeurs météo. Ce composant est devenu **Nephos Vocab** dans la taxonomie actuelle. Toutes les PR mergées (19 au moment de la réorientation, 152 tests verts) sont préservées et continuent de couvrir Nephos Vocab.

Le sens du projet a évolué : Nephos n'est plus seulement un référentiel, c'est une **plateforme** dont la sémantique est l'une des briques.

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

## État des briques Nephos

| Brique | État | Référence |
|---|---|---|
| **Nephos Vocab** | ✅ en place — code Python + schéma SQL + 152 tests verts | `src/nephos/`, `schema_v4_skos.sql`, ADR 0001-0014 |
| **Nephos Catalog** | 📋 à construire | EPIC E11 du backlog |
| **Nephos Storage** | 📋 à construire | EPIC E12 |
| **Nephos Workflow** | 📋 à construire | EPIC E13 |
| **Nephos Contracts** | 📋 à construire | EPIC E14 |
| **Nephos Watch** (alerting) | 📋 à construire | EPIC E15, annexe A du document technique |
| **Nephos Watch** (fraîcheur + complétude) | 📋 à construire | EPIC E16, annexes B et C |
| **Nephos Vault** | 📋 à construire | EPIC E17, annexe H |
| **Nephos Capture** | 📋 à construire | EPIC E18, annexe F |
| **Nephos Trace** | 📋 à construire | EPIC E19, annexe G |

## État de validation

Ces documents sont **drafts** soumis à critique structurante. Décisions à prendre avant tout engagement :

1. Sponsor exécutif identifié et engagé pour 3 ans minimum ?
2. Cible (l'opérateur national seul / consortium ALADIN-ACCORD-EUMETNET / produit générique) ?
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
