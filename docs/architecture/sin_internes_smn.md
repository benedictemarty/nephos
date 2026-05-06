---
title: "SI internes des services météo nationaux"
subtitle: "Cartographie des plateformes et chaînes opérationnelles propriétaires (informations publiques)"
author: "Architecture senior"
date: "2026-05-06"
lang: fr
---

# Avertissement

Ce document compile **uniquement des informations publiques** : présentations en conférences (ECMWF Workshops, EMS, AMS, EGU), papiers, retours d'expérience documentés, sites institutionnels, GitHub des services qui publient.

**Limites assumées** :
- Les SI internes sont **par définition peu documentés publiquement**. La qualité des informations varie selon la transparence de chaque service.
- Certaines informations sont **datées** (les services évoluent en permanence, parfois sans communication publique).
- **Aucune information confidentielle** n'est utilisée. Pour une décision engageante, des **entretiens directs** avec les services concernés sont indispensables.
- Le document ne prétend pas être exhaustif. Il vise les composants **les plus structurants** publiquement connus.

\newpage

# 1. Pourquoi regarder les SI internes ?

Les plateformes ouvertes (MARS, NOAA BDP, EUMETSAT DS, Copernicus, Pangeo, Planetary Computer, Earth Engine, AWS Open Data) **ne sont qu'une partie de l'écosystème**. La majorité de la valeur opérationnelle d'un service météo national vit dans des **systèmes internes** :

- Chaînes opérationnelles HPC (modèles, post-processing).
- Systèmes de production de prévision et de produits.
- Outils de visualisation pour prévisionnistes.
- Systèmes de vigilance et d'alerte.
- Bases climatologiques et observations.
- Outils d'archivage long terme.

Ces systèmes :
- **Représentent l'investissement historique** majeur (parfois 20-40 ans d'amortissement).
- **Sont la cible d'une éventuelle modernisation** (et donc l'enjeu réel de la transformation).
- **Inspirent des choix architecturaux** souvent transposables.
- **Imposent des contraintes** (interopérabilité, formats hérités, vocabulaires propriétaires).

Comprendre ces SI internes aide à **calibrer** la cible et à **anticiper la résistance au changement** ainsi que les coûts de migration.

# 2. ECMWF (informations publiques)

## 3.1 Chaînes opérationnelles et modèles

| Composant | Périmètre | Statut public |
|---|---|---|
| **IFS (Integrated Forecasting System)** | Modèle global ECMWF, référence mondiale | Code propriétaire, **OpenIFS** version éducative open source |
| **CY... cycles** | Versions trimestrielles d'IFS | Documentation publique des changements |
| **HRES / ENS / SEAS** | Configurations opérationnelles (haute résolution, ensemble, saisonnier) | Documentées |

## 3.2 Outils ECMWF (OSS et internes)

| Composant | Statut | Description |
|---|---|---|
| **ecCodes** | OSS (Apache 2.0) | Bibliothèque de référence pour GRIB/BUFR — utilisée mondialement |
| **MIR (Meteorological Interpolation and Regridding)** | OSS | Interpolation et régrillage |
| **Magics** | OSS | Génération de cartes |
| **Metview** | OSS | Workstation de visualisation |
| **Polytope** | OSS récent (Apache 2.0) | API REST moderne pour requêtes spatio-temporelles |
| **MARS** | Propriétaire | Système d'archivage (déjà documenté dans benchmark) |
| **eccharts** | Interne | Système de visualisation web pour clients ECMWF |
| **MIR-Web / Charts** | Interne | Services internes prévi |
| **OpenIFS** | OSS partiel | Version éducative d'IFS, utilisée en recherche |
| **ATLAS** | OSS récent | Bibliothèque de modélisation NWP nouvelle génération (C++) |
| **fdb (Field Database)** | Partiellement OSS | Système de stockage de champs en ligne |

**Pertinence pour la cible** : ECMWF est **le service le plus prolifique en OSS** dans la météo. Plusieurs briques (ecCodes, MIR, Magics, Metview, Polytope, ATLAS, fdb) sont **directement réutilisables** dans une cible nationale. ECMWF a **investi consciemment dans l'open source** ces dernières années — bénéfice à capter.

## 3.3 Initiatives récentes

- **Polytope** : moderniser l'accès MARS via API REST + JSON, avec serveur HTTP standard. Open source.
- **Adoption Zarr** progressive (notamment pour Copernicus CDS).
- **AIFS (AI Forecasting System)** : modèle AI publié 2024-2025, ouvert.
- **Migration vers Bologne** : nouveau data centre HPC, plus moderne.

**À retenir** : ECMWF est un **partenaire** plus qu'un concurrent. Toute cible nationale gagne à s'**aligner** sur les briques ECMWF OSS et à **contribuer**.

\newpage

# 3. DWD — Deutscher Wetterdienst (Allemagne)

## 4.1 Chaînes et modèles

| Composant | Périmètre | Statut public |
|---|---|---|
| **ICON** | Modèle global et régional, référence allemande | Code partiellement public, consortium recherche |
| **ICON-D2 / ICON-EU** | Configurations régionales | Documentées |

## 4.2 Systèmes internes

| Composant | Périmètre | Statut public |
|---|---|---|
| **NinJo** | Workstation de visualisation prévi (Java), développé par DWD avec consortium | **Partagé** entre DWD, MeteoSwiss, Bundeswehr, BOM Australie, et autres |
| **PAMORE** | Archive ICON et observations | Référencé |
| **MEC (Meteorological Environment for Computing)** | Environnement HPC | Référencé |
| **CDC (Climate Data Center)** | Portail observations climatologiques | Public, accès libre |

## 4.3 Particularité : NinJo

**NinJo** est un cas remarquable. Workstation prévi développée par DWD à partir de 2002, **mutualisée** avec d'autres services nationaux : MeteoSwiss, Bundeswehr (météo militaire allemande), Bureau of Meteorology Australie, KNMI Pays-Bas (partiellement). Modèle de **partage entre services nationaux** sur un outil métier critique.

**Pertinence pour la cible** : NinJo prouve qu'un **partage entre services météo** est possible sur des outils métier. Modèle inspirant pour des collaborations futures (par exemple l'opérateur national / Belgique / Suisse / Maroc / etc.).

\newpage

# 4. MetOffice (Royaume-Uni)

## 5.1 Chaînes et modèles

| Composant | Périmètre | Statut public |
|---|---|---|
| **Unified Model (UM)** | Modèle global et régional | Consortium Unified Model (Australie, Inde, Corée, etc.) |
| **MOGREPS** | Ensemble probabiliste | Documenté |

## 5.2 Systèmes internes

| Composant | Statut public |
|---|---|
| **MASS (Mass Archive Storage System)** | Équivalent MARS, propre au MetOffice |
| **DACE (Data Acquisition and Control Environment)** | Système d'ingestion |
| **Visual Cortex** | Visualisation interne (anciennement) |
| **PaaS interne UM** | Plateforme HPC |
| **CEDA Archive** | Archive partagée avec NCAS, semi-publique |

**Pertinence pour la cible** : le MetOffice a **modernisé tôt** son archivage (MASS) sur le modèle MARS. Bonne référence pour les questions d'archivage à grande échelle.

\newpage

# 5. NOAA et NWS (États-Unis)

## 6.1 Chaînes et modèles

| Composant | Périmètre | Statut public |
|---|---|---|
| **GFS (Global Forecast System)** | Modèle global | Public |
| **HRRR (High-Resolution Rapid Refresh)** | Modèle régional rapide | Public |
| **RAP (Rapid Refresh)** | Modèle régional | Public |
| **GEFS** | Ensemble | Public |

## 6.2 Systèmes internes

| Composant | Périmètre | Statut public |
|---|---|---|
| **AWIPS-2 (Advanced Weather Interactive Processing System)** | Système ops principal des Weather Forecast Offices NWS | OSS partiel via Unidata |
| **NOMADS** | Diffusion publique modèles (déjà cité dans benchmark) | Public |
| **NCEP/NWS internal pipelines** | Variables selon centres | Référencés |
| **GAEA** | HPC interne | Référencé |

**Pertinence pour la cible** : **AWIPS-2 a une part OSS** (via Unidata) — utilisable en source d'inspiration. NOAA a fait le **choix d'ouverture** publique forte (NOMADS / BDP).

\newpage

# 6. Autres services météo nationaux

## 7.1 JMA (Japon)

- **GSM (Global Spectral Model)** : modèle global.
- **MSM (Meso Scale Model)** : modèle régional.
- **NAPS (Numerical Analysis and Prediction System)** : environnement de production.
- **JRA-55, JRA-3Q** : ré-analyses, semi-publiques.

## 7.2 BOM (Australie)

- **ACCESS** : modèle dérivé du UM britannique.
- **APP3 (Access Production Platform v3)** : environnement de production.
- **AMPS** : Australian Meteorological & Oceanographic Society's product server.
- Utilise **NinJo** (visualisation).

## 7.3 KNMI (Pays-Bas)

- **HARMONIE-AROME** : configuration régionale du modèle ALADIN/AROME.
- **KDP (Knowledge & Data Platform)** : initiative de data platform interne, communiquée publiquement, à étudier de près.

## 7.4 MeteoSwiss (Suisse)

- **COSMO / ICON** : modèles régionaux, héritage COSMO.
- **NinJo** (partagé avec DWD).
- **SwissMetNet** : réseau d'observations.
- Adoption Pangeo / Zarr récente (publications).

## 7.5 KMA (Corée du Sud)

- **Unified Model** (consortium UK).
- Plateforme moderne **KIM (Korean Integrated Model)** en développement.

\newpage

# 7. Composants partagés entre services météo

Quelques composants ont été **mutualisés** ou **co-développés** entre plusieurs services nationaux. À étudier comme modèles de coopération.

| Composant | Services impliqués | Type |
|---|---|---|
| **NinJo** | DWD, MeteoSwiss, BOM, Bundeswehr, KNMI partiel | Workstation prévi (Java) |
| **ecCodes** | ECMWF + adoption mondiale (NOAA, autres opérateurs nationaux, MetOffice, etc.) | Bibliothèque GRIB/BUFR (OSS) |
| **Unified Model** | MetOffice + Australie + Inde + Corée + Nouvelle-Zélande | Modèle NWP (consortium) |
| **ALADIN / ACCORD** | France, Belgique, Hongrie, Maroc, Tunisie, Algérie, Bulgarie, etc. (16+ pays) | Modèle régional consortium |
| **HIRLAM** (fusionné dans ACCORD) | Pays nordiques + autres | Modèle régional |
| **COSMO** (en sunset, transition vers ICON) | Anciennement DWD, MeteoSwiss, Italie, Russie, etc. | Modèle régional |
| **OpenIFS** | ECMWF + adoption recherche mondiale | Modèle global éducation |
| **STAC** (standard) | Adoption croisée (EUMETSAT, NASA, Microsoft, etc.) | Standard catalogue |

**Pertinence pour la cible** : la **mutualisation entre services nationaux est un modèle prouvé**. Inspirer la cible nationale par cette logique : développer comme bien commun ce qui peut l'être, plutôt que développer pour soi seul.

\newpage

# 8. Patterns observés dans les SI internes

Quelques **patterns transverses** que l'on retrouve chez la plupart des services :

## 9.1 Architecture en chaînes opérationnelles (pipelines HPC)

Les SI internes sont **structurés autour des chaînes** : ingestion observations → assimilation → modèle global → modèle régional → post-processing → produits → diffusion. Chaque étape est un **maillon** souvent ancien, optimisé pour son temps d'exécution, peu modulaire.

**Conséquence pour la cible** : la cible plateforme **ne remplace pas les chaînes**. Elle **lit leurs sorties** (primaires) et les expose comme données gouvernées. Ne pas confondre **plateforme data** et **chaîne opérationnelle**.

## 9.2 Vocabulaires propriétaires hérités

Chaque service a son **vocabulaire interne** (paramètres, conventions de nommage, codes), souvent ancien, parfois aligné CF à l'export, mais rarement en interne.

**Conséquence pour la cible** : c'est précisément ce qu'un glossaire pivotal (CF + WMO + ECMWF + QUDT) doit unifier. La cible apporte ici une **valeur architecturale réelle**.

## 9.3 Stockage à plusieurs niveaux ad-hoc

NAS + GPFS + S3 + bandes + parfois cloud. Conservation patrimoniale par bandes. Peu de tiering automatique.

**Conséquence pour la cible** : stratégie de tiering moderne (cf. Annexe D du document technique) reste un différenciateur fort.

## 9.4 Visualisation : forte tension entre standardisation et diversité

NinJo est l'exception (mutualisation). La majorité des services développent leurs propres outils de visualisation prévi. Coût d'intégration élevé.

**Conséquence pour la cible** : **ne pas reconstruire un NinJo**. Soit adopter NinJo (si licence le permet), soit s'appuyer sur des standards web (Martin / MapLibre / Cartopy / Streamlit) sans réinventer.

## 9.5 Production de produits métier : maillons isolés

Vigilance, METAR, SIGMET, cartographie publique, briefings : chaque service a **son chaînon de production**, rarement modulaire, souvent code legacy.

**Conséquence pour la cible** : Annexe « Présenter / produire » du document technique reste pertinent. Modulariser ce qui ne l'a jamais été.

## 9.6 Open source : adoption tardive mais croissante

ECMWF mène. l'opérateur national, DWD, MetOffice, NOAA suivent. Pangeo accélère.

**Conséquence pour la cible** : la cible peut être **construite OSS de bout en bout** sans pari technologique fou — c'est la direction industrielle.

\newpage

# 9. Ce que ces SI internes nous apprennent pour la cible

## 10.1 La cible n'est pas une refonte des chaînes

Les chaînes opérationnelles HPC (ARPEGE, AROME, IFS, ICON, UM, GFS) **ne sont pas le périmètre** de la cible plateforme data. Elles produisent les primaires. La cible **les ingère**, les normalise, les expose. Ne pas confondre.

## 10.2 La cible n'est pas une plateforme HPC

La compute scientifique partagé (Dask + Pangeo) est **complémentaire** au HPC, pas substitut. Les modèles tournent sur HPC ; les analyses descendantes peuvent tourner sur compute partagé.

## 10.3 La cible apporte ce qui manque transversalement

Les SI internes **ne font pas** :
- Catalogue transverse unifié.
- Glossaire pivotal CF/QUDT/WMO/ECMWF intégré au catalogue technique.
- Data contracts gouvernant techniques + métier ensemble.
- Cycle de vie automatisé par usage.
- Politique d'accès ABAC déclarative.
- Single source of truth à 3 niveaux.
- Lineage column-level.

C'est précisément le **différenciateur** de la cible.

## 10.4 La cible doit composer avec le legacy, pas le détruire

Le strangler pattern décrit dans la section 12 du document fonctionnel **est obligatoire**. Aucun service météo national n'a réussi un big-bang sur ses chaînes critiques.

## 10.5 La cible peut être un bien commun

L'exemple NinJo (DWD partagé), l'exemple ALADIN/ACCORD (consortium régional, 16 pays), l'exemple Unified Model (MetOffice + Australie + Corée) montrent que **la mutualisation entre services nationaux fonctionne** sur un produit métier critique. La cible nationale pourrait :

- Co-développer avec un consortium (EUMETNET, ALADIN/ACCORD, autres).
- Proposer en open source pour adoption tierce (modèle ECMWF récent).
- Servir de socle européen pour les centres météo qui n'ont pas le bandwidth de construire leur propre plateforme.

C'est une **opportunité géopolitique** au-delà du seul intérêt technique.

\newpage

# 10. Risques spécifiques aux migrations de SI internes

| Risque | Manifestation | Mitigation |
|---|---|---|
| Réécriture des chaînes opérationnelles dans la cible | Tentation de tout refaire ; échec garanti | Cibler la plateforme data, pas les chaînes |
| Cassure d'interface avec les SI legacy non migrés | Bulletins, AMSS, VIGI cassent le jour de la bascule | Phase de double-lecture obligatoire 6+ mois |
| Perte de la connaissance des vocabulaires internes | Mappings hérités perdus, secondaires non reproductibles | Co-rédaction des data contracts avec experts métier en place |
| Sous-estimation du coût de re-certification OACI / WMO / RGPD | Conformité perdue temporairement | Plan de re-certification chiffré dataset par dataset |
| Concurrence entre cibles internes (chaque direction veut sa plateforme) | Énième silo créé | Sponsor exécutif transverse, charte single-source |
| Refus d'ouverture (« on ne peut pas, c'est sensible ») sans audit réel | Cible cantonnée à un périmètre étroit | Classification fine (L0-L3), pas catch-all « tout sensible » |
| Patrimoine OSS l'opérateur national faible vs ECMWF | Recrutement difficile, dépendance fournisseurs | Investissement RH formation + contribution OSS visible |

\newpage

# 11. Synthèse

## 12.1 Le paysage est plus riche qu'il n'y paraît

Au-delà des plateformes ouvertes (benchmark précédent), les services météo nationaux disposent d'un **patrimoine de SI internes** considérable. La plupart est **propriétaire et peu documenté publiquement**, mais quelques composants OSS structurants (ecCodes, OpenIFS, MIR, Magics, Metview, ATLAS, fdb, NinJo en partie) sont des **briques disponibles**.

## 12.2 Trois leçons clés

1. **La cible plateforme data n'est pas la refonte des chaînes opérationnelles**. Distinguer impérativement.
2. **Plusieurs services ont déjà ouvert leur catalogue ou diffusion** (NOAA BDP, Copernicus). Aucun n'a encore unifié glossaire + catalogue + contract + politique d'accès dans une plateforme cohérente. **C'est la position défendable de la cible nationale**.
3. **La mutualisation est possible et prouvée** sur des produits métier (NinJo, ALADIN/ACCORD, UM consortium). La cible nationale gagnerait à s'inscrire dans une logique de **bien commun ouvert**.

## 12.3 Implication pour le sponsor

Construire la cible nationale **isolément** = effort important, valeur captée seule.

Construire la cible nationale **comme socle ouvert pour le consortium ALADIN/ACCORD ou EUMETNET** = effort partagé, valeur captée collectivement, leadership technique européen, soutien financier potentiellement plus large.

C'est une **option stratégique majeure** à instruire en amont du POC.

---

*Document évolutif. Pour les décisions engageantes, des entretiens directs avec les services concernés sont indispensables : leurs représentants en conférences (ECMWF Workshops, EMS, AMS, EGU) sont le canal usuel.*
