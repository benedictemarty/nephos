---
title: "Benchmark des plateformes data météo et environnement"
subtitle: "Comparatif analytique : MARS, NOAA BDP, EUMETSAT, Copernicus, Pangeo, Planetary Computer, Earth Engine, AWS Open Data"
author: "Architecture senior"
date: "2026-05-06"
lang: fr
---

# Avertissement

Ce document compare des plateformes existantes pour éclairer la conception d'une cible. **Il ne classe pas les plateformes en absolu**, il les compare selon des critères pertinents pour un opérateur météo national construisant sa propre plateforme data Po-scale.

Les informations sont **publiques** (documentation officielle, conférences, retours communautaires). **Aucune donnée propriétaire** n'est utilisée. Certaines précisions peuvent être datées ou imparfaites — chaque plateforme évolue. **Une vérification au moment de la décision est nécessaire.**

\newpage

# 1. Périmètre du benchmark

## 1.1 Plateformes retenues

Huit plateformes structurantes, représentatives des différentes approches :

| # | Plateforme | Catégorie | Sponsor |
|---|---|---|---|
| 1 | **ECMWF MARS** | Archive scientifique propriétaire | ECMWF (UE intergouvernemental) |
| 2 | **NOAA Big Data Program** | Open data sur cloud public | NOAA (US gouv) en partenariat AWS / GCP / Azure |
| 3 | **EUMETSAT Data Store** | Catalogue + API satellite | EUMETSAT (UE intergouvernemental) |
| 4 | **Copernicus CDS / ADS / CEMS** | Catalogue + compute web (climat) | ECMWF opère, financé EU Commission |
| 5 | **Pangeo** | Stack OSS communautaire scientifique | Communauté open source (NSF, NASA, CNRS, etc.) |
| 6 | **Microsoft Planetary Computer** | Catalogue STAC + compute managed | Microsoft |
| 7 | **Google Earth Engine** | Catalogue + compute analytics | Google |
| 8 | **AWS Open Data Program** | Vitrine d'hébergement | AWS |

## 1.2 Plateformes non retenues mais à connaître

- **NCAR Research Data Archive** : archive scientifique, modèle MARS-like, périmètre académique.
- **DWD Climate Data Center** : portail open data Allemagne, périmètre national.
- **MetOffice MIDAS / CEDA** : archive UK, ouverte au monde académique.
- **JMA Open Data** : Japon, périmètre régional asiatique.
- **NASA EarthData / Worldview** : vaste, distribué (DAACs), focus terre/satellite.
- **DKRZ / CMIP repositories** : climat académique, ESGF.

\newpage

# 2. Tableau synoptique

| Critère | MARS | NOAA BDP | EUMETSAT DS | Copernicus CDS/ADS | Pangeo | Planetary Computer | Earth Engine | AWS Open Data |
|---|---|---|---|---|---|---|---|---|
| **Périmètre** | Météo + climat | Météo + océan + climat | Satellite météo Europe | Climat + atmosphère + sécurité civile | Sciences environnement | Sciences environnement | Imagerie sat + analyse | Hébergement multi-thème |
| **Statut** | Propriétaire | Open data | Mixte | Open + restreint | OSS | Managed (privé) | Managed (privé) | Hébergement |
| **Modèle** | API MARS + tape | Buckets cloud + STAC | Catalogue + API | Web + API + Toolbox | Stack OSS | Catalogue STAC + JupyterHub | Code Editor + JS/Python API | Buckets ouverts |
| **Volume** | ~30 Po | 100+ Po cumulés | ~10+ Po (sat) | dizaines de Po | n/a (lib) | dizaines de Po | dizaines de Po | 200+ Po cumulés |
| **Catalogue** | MARS interne | Variable selon dataset | STAC | Web custom | n/a | STAC | Custom | Index web |
| **Format** | GRIB / NetCDF / BUFR | GRIB / NetCDF / Zarr / Parquet | NetCDF / SAFE / Zarr | NetCDF / GRIB | Zarr / NetCDF / Parquet | COG / Zarr / Parquet / NetCDF | Tile pyramids interne | Variable |
| **Compute** | Externe (HPC ECMWF) | Externe (cloud user) | Externe (Toolbox limitée) | Toolbox + WPS | Dask / Jupyter user | JupyterHub managed | Dans Earth Engine | Externe |
| **Latence accès** | Minutes-heures (tape) | Secondes (cloud hot) | Secondes-minutes | Secondes-minutes | Selon backend | Secondes | Secondes | Secondes |
| **Coût utilisateur** | Variable (clients ECMWF) | Gratuit lecture | Gratuit ouvert | Gratuit | Gratuit (libs) | Gratuit (compute limité) | Gratuit (limites strictes) | Gratuit lecture |
| **Souveraineté** | Réading (UK) | US | Allemagne | UE | n/a | US | US | US |
| **Lock-in** | Élevé (protocole MARS) | Faible (formats ouverts) | Faible (STAC) | Faible-moyen | Nul | Élevé (API custom) | Très élevé (API custom) | Faible |
| **Audience principale** | Centres météo nationaux + recherche | Tiers économique + recherche | Services climat + national + recherche | Climat services + public | Recherche + science | Recherche env + ONG | Recherche + télédétection | Tout public |
| **Mature depuis** | 1985 | 2015 | 2020 (refonte) | 2018-2020 | 2015 | 2021 | 2010 | 2014 |

\newpage

# 3. Fiches détaillées

## 3.1 ECMWF MARS

**Sponsor.** ECMWF (Centre européen pour les prévisions météorologiques à moyen terme), organisation intergouvernementale UE.

**Description.** Système d'archivage et de récupération de données météorologiques en service depuis 1985. Stocke environ 30 Po de prévisions, ré-analyses (ERA5, ERA5-Land), observations. Accès via le **protocole MARS** (langage de requête propriétaire) et progressivement via des API REST modernes (MARS API, Polytope).

**Architecture.**
- Stockage hiérarchique : disques rapides + tape archive massive.
- Requête MARS : langage déclaratif (syntaxe `retrieve, class=od, type=an, ...`).
- Format de sortie : GRIB principalement, NetCDF, BUFR.
- Polytope (récent) : couche moderne API REST + JSON pour requêtes spatio-temporelles.
- Pas de catalogue STAC public ; vocabulaire MARS interne.

**Adoption.** Centres météorologiques nationaux européens, recherche académique sous accord. Modèle clients-membres ECMWF. Près de 100 millions de requêtes par an (ordre de grandeur public).

**Forces.**
- Longévité opérationnelle exceptionnelle (40 ans).
- Stabilité du protocole d'accès dans la durée.
- Coût marginal d'extension maîtrisé (architecture proven).
- Scaling Po démontré.

**Limites.**
- Système propriétaire ECMWF, non réutilisable par d'autres opérateurs.
- Vocabulaire MARS spécifique, pas mappé CF Standard Names en interne.
- Latence retrieval depuis tape (minutes à heures).
- Évolution technique lente (héritage 40 ans).
- Pas de compute intégré (utilisateur récupère puis calcule ailleurs).

**Pertinence pour un opérateur national construisant sa cible.**
- Inspiration **forte** sur la longévité du protocole d'accès (à protéger contre les ruptures).
- Inspiration **forte** sur la stratégie de tiering (chaud-tape).
- Modèle **non reproductible** directement (propriétaire, lourd, ancien).

## 3.2 NOAA Big Data Program (BDP)

**Sponsor.** NOAA (National Oceanic and Atmospheric Administration, US), partenariats AWS, Google Cloud, Microsoft Azure.

**Description.** Programme lancé en 2015 visant à publier les datasets NOAA (météo, océan, climat, satellite) sur les principaux clouds publics, **gratuitement en lecture**. Plus de 100 Po cumulés exposés. Modèle public-private partnership : les clouds hébergent gratuitement contre la création d'un écosystème de services tiers.

**Architecture.**
- Datasets stockés dans des buckets S3 / GCS / Azure Blob, format majoritairement GRIB et NetCDF, progressivement Zarr.
- Catalogue : fragmenté selon les datasets (parfois STAC, parfois index web).
- Pas de compute fourni : l'utilisateur paie son compute auprès du cloud choisi.
- Le BDP est une **vitrine d'open data**, pas une refonte de la plateforme interne NOAA.

**Adoption.** Massive : services climat, énergie, agriculture, ML privés, recherche académique mondiale. Modèle ayant inspiré EUMETSAT, EU Open Data, etc.

**Forces.**
- Adoption tiers économique massive.
- Multi-cloud (pas de lock-in à un fournisseur).
- Catalyseur d'innovation externe (ML météo en a profité).
- Coût hébergement transféré au cloud (NOAA ne paie pas).

**Limites.**
- Catalogue fragmenté, qualité variable selon dataset.
- Gouvernance interne NOAA reste à l'écart : c'est une couche de diffusion, pas une refonte.
- Dépendance aux clouds (si un cloud arrête le programme, dataset à reproduire ailleurs).
- Pas de compute intégré.

**Pertinence pour un opérateur national.**
- Modèle **fort** de **stratégie de diffusion ouverte** : créer la demande externe peut justifier la refonte interne.
- Modèle **non suffisant** : ne refonde pas la gouvernance interne, juste la couche de publication.
- À considérer comme **complément de la cible**, pas comme la cible elle-même.

## 3.3 EUMETSAT Data Store

**Sponsor.** EUMETSAT (Organisation européenne pour l'exploitation des satellites météorologiques).

**Description.** Refonte récente (active depuis 2020) du portail de diffusion des données satellites EUMETSAT (météo, climat, océan). Catalogue **STAC**, accès via **API REST** unifiée, formats modernes (Zarr en croissance). Des dizaines de Po de données satellite.

**Architecture.**
- Catalogue STAC standard.
- API d'accès unifiée (HTTP, REST).
- Formats : NetCDF, SAFE, COG, Zarr.
- Compute limité (Toolbox web pour visualisations basiques).
- Distribué sur cloud (DIAS — Data and Information Access Services européens).

**Adoption.** Services climat (Copernicus), opérateurs météo nationaux, recherche académique européenne, services environnementaux.

**Forces.**
- Adoption STAC : standard de fait pour catalogues spatialisés.
- Accès API moderne, programmatique.
- Souveraineté européenne.
- Périmètre satellite cohérent et bien gouverné.

**Limites.**
- Périmètre satellite uniquement (pas de modèles NWP, pas d'observations in-situ).
- Compute limité, l'utilisateur télécharge.
- Lien sémantique (CF Standard Names) en cours, pas systématique.
- Adoption STAC partielle (refonte progressive).

**Pertinence pour un opérateur national.**
- Inspiration **forte** sur l'**adoption STAC** comme catalogue spatialisé.
- Inspiration **forte** sur la **gouvernance de catalogue** moderne.
- À considérer pour **interopérabilité** (STAC export du catalogue l'opérateur national).

## 3.4 Copernicus Climate Data Store (CDS), Atmosphere Data Store (ADS), Emergency Management Service (CEMS)

**Sponsor.** Commission européenne (programme Copernicus), opéré par ECMWF.

**Description.** Plateformes web et API pour accéder aux données climat (CDS), atmosphère (ADS), urgences (CEMS), incluant ré-analyses ERA5, données satellites, prévisions saisonnières, modélisation climat (CMIP).

**Architecture.**
- Web frontend + API REST + Toolbox de calcul à la volée (via WPS — Web Processing Service).
- Catalogue web custom (pas STAC standard à l'origine, évolution vers STAC en cours).
- Format : NetCDF principalement, GRIB, parfois CSV.
- Compute partagé : utilisateur soumet une requête de calcul (ex. moyennes, agrégations), reçoit le résultat.
- File d'attente compute selon charge.

**Adoption.** Services climat opérationnels, médias, énergie, agriculture, recherche, ONG. Très large adoption européenne, croissance forte.

**Forces.**
- Modèle **API + compute partagé** très apprécié des consumers métier.
- Données ré-analyses ERA5 inégalées en couverture et qualité.
- Adoption européenne forte.
- Souveraineté européenne (ECMWF opère).

**Limites.**
- Compute limité par utilisateur, files d'attente longues sur jobs lourds.
- Catalogue partiellement modernisé (mix entre web custom et STAC).
- Vocabulaire métier hétérogène entre CDS et ADS et CEMS.
- Couplage fort à ECMWF (continuité dépend de l'ECMWF).

**Pertinence pour un opérateur national.**
- Inspiration **forte** sur le **modèle API + compute partagé** comme service aux consumers.
- Inspiration **moyenne** sur le catalogue (pattern à moderniser).
- Possible **partenariat** plutôt que concurrence : l'opérateur national pourrait s'intégrer comme nœud Copernicus plutôt que de répliquer.

## 3.5 Pangeo

**Sponsor.** Communauté open source (NSF, NASA, CNRS, ECMWF partiellement, Universités).

**Description.** Stack open source pour la science des géosciences : **xarray** (manipulation de tableaux multidimensionnels), **Zarr** (format de stockage cloud-native), **Dask** (parallélisation), **Jupyter** (notebooks). Pas une plateforme en soi : c'est l'**écosystème de référence** pour le calcul scientifique gridded en 2026.

**Architecture.**
- Pas de catalogue ni de stockage propre : c'est un **assemblage de bibliothèques**.
- Adoption Zarr sur S3 / GCS / Azure : datasets accessibles depuis n'importe quel compute.
- Déploiements communautaires : Pangeo Cloud, Pangeo Hub, Pangeo Forge (orchestration ETL communautaire).

**Adoption.** Communauté scientifique mondiale (climatologie, océanographie, météo recherche), partenariats avec NASA / NOAA / ECMWF / CNRS.

**Forces.**
- Standard de fait pour gridded scientifique.
- 100 % open source, formats ouverts.
- Pas de lock-in.
- Communauté active, innovations continues.
- Compatible avec la plupart des clouds.

**Limites.**
- Ce n'est pas un produit clés-en-main : il faut intégrer.
- Pas de gouvernance, pas de catalogue, pas de contracts intégrés.
- Maturité opérationnelle variable selon les briques.
- Dépendance à la communauté (pas de support commercial).

**Pertinence pour un opérateur national.**
- **Brique de base obligatoire** pour le compute scientifique gridded.
- À **intégrer** dans la cible, pas à concurrencer.
- Aligner les formats internes (Zarr) avec Pangeo = adoption gratuite par la communauté scientifique.

## 3.6 Microsoft Planetary Computer

**Sponsor.** Microsoft (Azure).

**Description.** Catalogue STAC + JupyterHub managé pour les sciences environnementales (climat, biodiversité, agriculture, océan). Lancé en 2021. Datasets satellite, climat, observations terrestres. Compute accessible gratuitement avec quota.

**Architecture.**
- Catalogue **STAC** standard, exposé en REST.
- Datasets en COG (Cloud Optimized GeoTIFF), Zarr, Parquet.
- Compute : JupyterHub managé sur Kubernetes Azure, accès gratuit avec limites (CPU-heures, RAM).
- Outils intégrés : `planetary-computer` Python SDK, intégration `xarray-spatial`.

**Adoption.** Recherche environnementale, ONG, agriculture, ML environnemental. Croissance rapide.

**Forces.**
- Catalogue STAC propre.
- Compute managé : utilisateurs n'ont pas à provisionner.
- Datasets bien gouvernés et catalogués.
- Documentation excellente.

**Limites.**
- Lock-in **élevé** : compute uniquement sur Azure, dépendance Microsoft.
- Quota compute limité au-delà de tests.
- Périmètre environnemental, pas spécifiquement météo opérationnelle.
- Pérennité dépend de la stratégie Microsoft.

**Pertinence pour un opérateur national.**
- Inspiration **forte** sur le **catalogue STAC + compute managé**.
- À **éviter en lock-in** pour une plateforme souveraine, mais à **étudier comme référence** d'expérience utilisateur.

## 3.7 Google Earth Engine

**Sponsor.** Google.

**Description.** Plateforme de catalogage et d'analyse d'imagerie géospatiale (sat, météo, climat, terrain), lancée en 2010. Très grande adoption en télédétection. Compute distribué intégré, langage spécifique JavaScript / Python.

**Architecture.**
- Catalogue Google interne, vaste (PB de données satellites, climatiques, terrain).
- Compute distribué massif (équivalent Spark interne Google).
- API JavaScript (Code Editor web) et Python.
- Datasets pré-indexés en pyramides de tuiles.

**Adoption.** Télédétection scientifique mondiale, ONG environnement, recherche climat. Outil de référence en télédétection.

**Forces.**
- Performance compute exceptionnelle.
- Catalogue très étendu.
- Modèle gratuit pour usage non commercial.

**Limites.**
- **Lock-in extrême** : API custom, pas portable.
- Pas open source.
- Limites strictes pour usage commercial (tarifs élevés, licences spéciales).
- Souveraineté nulle (Google).
- Difficile à intégrer dans une plateforme propre.

**Pertinence pour un opérateur national.**
- **Inspiration forte** sur la performance compute distribué.
- **Non utilisable comme brique** dans une plateforme souveraine.
- À considérer comme **référence d'expérience** ou éventuellement **partenariat ponctuel** sur des cas d'usage non sensibles.

## 3.8 AWS Open Data Program

**Sponsor.** Amazon Web Services.

**Description.** Programme d'hébergement gratuit de jeux de données ouverts. NOAA BDP en est le principal contributeur météo. Plus de 200 Po cumulés (météo, océan, génomique, sciences sociales, etc.).

**Architecture.**
- Datasets dans des buckets S3 ouverts en lecture.
- Pas de catalogue unifié AWS (chaque dataset a son propre index).
- Pas de compute fourni : utilisateur paie son compute auprès d'AWS.

**Adoption.** Très large, c'est une vitrine pour AWS et un service public de fait.

**Forces.**
- Énorme volume hébergé gratuitement.
- Standards de stockage S3 = facilité d'accès.
- Pérennité (Amazon engagé).

**Limites.**
- Pas de catalogue unifié.
- Pas de compute.
- Souveraineté nulle (US).
- Dépendance Amazon.

**Pertinence pour un opérateur national.**
- À considérer comme **canal de diffusion** secondaire (publier des extraits sur AWS Open Data pour visibilité).
- **Pas une plateforme cible**.

\newpage

# 4. Comparaison transversale par dimension

## 4.1 Modèle économique

| Plateforme | Pour les producteurs | Pour les consumers | Soutenable long terme ? |
|---|---|---|---|
| MARS | ECMWF finance via membres | Variable selon contrat | Oui (40 ans prouvés) |
| NOAA BDP | NOAA gratuit, cloud héberge | Gratuit lecture, paie compute | Dépend des partenariats AWS/GCP/Azure |
| EUMETSAT DS | EUMETSAT finance | Gratuit ouvert | Oui (mandat européen) |
| Copernicus | EU Commission finance | Gratuit | Oui (programme EU pluri-annuel) |
| Pangeo | Communauté + grants | Gratuit | Dépend de la communauté |
| Planetary Computer | Microsoft finance | Gratuit limité | Risque (stratégie Microsoft) |
| Earth Engine | Google finance | Gratuit non-commercial | Risque (stratégie Google) |
| AWS Open Data | AWS finance hébergement | Gratuit lecture | Probable (vitrine AWS) |

**Leçon** : les modèles les plus pérennes sont **gouvernementaux ou intergouvernementaux** (MARS, EUMETSAT, Copernicus). Les modèles privés (Microsoft, Google) sont à risque de pivot stratégique. Le modèle NOAA BDP est résilient mais dépendant des partenariats cloud.

## 4.2 Souveraineté

| Plateforme | Hébergement | Gouvernance | Évaluable pour un opérateur souverain ? |
|---|---|---|---|
| MARS | Reading (UK) | ECMWF | ✅ (UE intergouvernemental) |
| NOAA BDP | Multi-cloud US | NOAA | ⚠️ (US, pas UE) |
| EUMETSAT DS | Allemagne / DIAS UE | EUMETSAT | ✅ (UE) |
| Copernicus | Multi-DIAS UE | EU Commission / ECMWF | ✅ (UE) |
| Pangeo | Distribué | Communauté | ✅ (briques OSS souveraines) |
| Planetary Computer | Azure US | Microsoft | ❌ (US privé) |
| Earth Engine | Google US | Google | ❌ (US privé) |
| AWS Open Data | AWS US | AWS | ❌ (US privé) |

**Leçon** : pour une plateforme nationale ou européenne, les options souveraines sont **MARS, EUMETSAT DS, Copernicus, Pangeo**. Les autres impliquent dépendance hors UE.

## 4.3 Lock-in technologique

| Plateforme | API | Format | Vocabulaire | Score lock-in |
|---|---|---|---|---|
| MARS | Propriétaire MARS | GRIB / NetCDF | MARS | Élevé |
| NOAA BDP | S3 standard | GRIB / NetCDF / Zarr | CF / WMO | Faible |
| EUMETSAT DS | STAC / REST | NetCDF / Zarr | CF | Faible |
| Copernicus | API custom + WPS | NetCDF / GRIB | CF (partiel) | Moyen |
| Pangeo | Python xarray | Zarr / NetCDF | CF | Nul |
| Planetary Computer | STAC + custom | COG / Zarr | STAC | Moyen-élevé |
| Earth Engine | API custom JS/Python | Pyramides interne | Custom | Très élevé |
| AWS Open Data | S3 | Variable | Variable | Faible |

**Leçon** : les plateformes adoptant **STAC + Zarr + Iceberg + CF** (Pangeo, EUMETSAT, NOAA BDP) offrent la plus grande portabilité. Earth Engine est l'exception en lock-in extrême malgré sa puissance.

## 4.4 Capacité de compute intégré

| Plateforme | Compute | Latence interactive | Limites |
|---|---|---|---|
| MARS | Aucun | n/a | utilisateur calcule ailleurs |
| NOAA BDP | Aucun | n/a | utilisateur paie son compute |
| EUMETSAT DS | Toolbox limitée | Rapide pour basiques | jobs lourds non |
| Copernicus | Toolbox + WPS | Variable, files d'attente | jobs limités |
| Pangeo | À déployer (Dask) | Excellent si auto-déployé | requiert compétences |
| Planetary Computer | JupyterHub managed | Excellent | quota gratuit |
| Earth Engine | Distribué interne | Très rapide | langage propriétaire |
| AWS Open Data | Aucun | n/a | utilisateur paie |

**Leçon** : le **compute intégré** est un facteur d'adoption fort. Copernicus, Planetary Computer, Earth Engine ont un avantage net. La cible nationale doit prévoir un compute partagé (Dask + Jupyter ou équivalent) dès le pilote.

## 4.5 Adoption tiers économique

| Plateforme | Adoption industrie | Innovation tiers | Indicateur public |
|---|---|---|---|
| MARS | Faible (clients ECMWF) | Limitée | n/a |
| NOAA BDP | Très forte | Massive (ML météo, services climat) | Centaines de services dérivés |
| EUMETSAT DS | Moyenne | Croissante | Adoption services climat |
| Copernicus | Forte | Croissante | Climate services européens |
| Pangeo | Moyenne (recherche) | Forte (innovations méthodologiques) | Communauté |
| Planetary Computer | Moyenne | Forte (ML environnemental) | Recherche |
| Earth Engine | Très forte (télédétection) | Très forte (apps environnement) | Milliers d'apps |
| AWS Open Data | Très forte | Très forte | Vitrine adoption |

**Leçon** : l'**ouverture publique** (NOAA BDP, AWS Open Data, Earth Engine) génère plus d'innovation tiers que les modèles fermés. Une cible nationale devrait prévoir un **canal d'ouverture public** dès le pilote, en complément du back-office souverain.

\newpage

# 5. Patterns architecturaux retenus

Synthèse des patterns à reprendre, à adapter, à éviter.

## 5.1 Patterns à reprendre

| Pattern | Plateforme(s) source | Application cible |
|---|---|---|
| **Catalogue STAC** comme standard de fait | EUMETSAT DS, Planetary Computer, NOAA BDP partiellement | Catalogue technique cible export STAC ou implémentation native |
| **Format Zarr** pour gridded | Pangeo, EUMETSAT DS, NOAA BDP | Format pivot interne pour gridded météo |
| **CF Standard Names** comme vocabulaire pivot | Pangeo, EUMETSAT DS, NOAA BDP | Glossaire métier de la cible |
| **API + compute partagé** | Copernicus CDS, Planetary Computer | Service de compute partagé dès le pilote |
| **Open data en complément** du back-office souverain | NOAA BDP, AWS Open Data | Canal d'ouverture publique en complément |
| **Public-private partnership** pour l'hébergement open data | NOAA BDP | Modèle pour réduire les coûts d'hébergement public |
| **Modèle membres / clients** pour soutenir le service | ECMWF MARS, EUMETSAT | Modèle pour services à valeur ajoutée internes |
| **Time-travel** (snapshots historiques accessibles) | MARS (par tape), Iceberg natif | Reproductibilité scientifique |

## 5.2 Patterns à adapter

| Pattern | Plateforme(s) source | Adaptation |
|---|---|---|
| **Hiérarchie disque-tape** pour tiering | MARS | Hot-warm-cold-frozen avec object store moderne (S3 + glacier) |
| **API custom propriétaire** | MARS, Earth Engine | À éviter ; préférer REST + STAC standards |
| **Catalogue web custom** | Copernicus | À moderniser en STAC ou Iceberg REST |
| **Compute managé fermé** | Planetary Computer, Earth Engine | Compute partagé OSS (Dask sur k8s) |

## 5.3 Patterns à éviter

| Pattern | Plateforme(s) source | Raison de l'éviter |
|---|---|---|
| **Vocabulaire interne propriétaire** | MARS, Earth Engine | Lock-in et difficulté d'évolution |
| **Lock-in compute sur un cloud privé unique** | Planetary Computer, Earth Engine | Souveraineté et pérennité |
| **Catalogue fragmenté par dataset** | NOAA BDP, AWS Open Data | Difficulté de découvrabilité transverse |
| **Pas de gouvernance interne** | NOAA BDP | C'est juste une couche de diffusion |
| **Compute ailleurs systématiquement** | MARS, NOAA BDP, AWS Open Data | Force l'utilisateur à recopier les données |

\newpage

# 6. Quelle cible nationale au regard de ce benchmark ?

## 6.1 Diagnostic synthétique

Aucune des plateformes existantes n'est **directement réutilisable** comme cible nationale :

- **MARS** : propriétaire ECMWF, non transposable.
- **NOAA BDP / AWS Open Data** : modèles US, pas souverains, et c'est juste de la diffusion ouverte.
- **EUMETSAT DS / Copernicus** : périmètres partiels (satellite, climat). Bon pour s'**intégrer**, pas pour remplacer.
- **Pangeo** : briques OSS à intégrer, pas une plateforme.
- **Planetary Computer / Earth Engine** : lock-in privé, exclu pour cible souveraine.

## 6.2 Stratégie cible argumentée

**Trois principes hérités du benchmark** :

1. **Catalogue STAC + Iceberg comme standard d'interopérabilité**. Aligne avec EUMETSAT, Planetary Computer, NOAA BDP. Garantit l'adoption par la communauté scientifique.
2. **Format Zarr + CF Standard Names**. Aligne avec Pangeo. Garantit la portabilité et l'absence de lock-in.
3. **API + compute partagé dès le pilote**. Aligne avec Copernicus. Garantit l'adoption par les consumers métier qui n'ont pas le temps de recopier.

**Trois différenciateurs propres à la cible** :

1. **Glossaire sémantique transverse comme pivot** (ce qu'aucune plateforme ne fait à ce niveau d'intégration). Différenciateur fort.
2. **Data contracts versionnés couplant technique + métier + qualité + accès**. Aucune plateforme actuelle ne fait ça intégralement.
3. **Gouvernance par construction** (single source of truth à 3 niveaux). Pattern emprunté au monde Data Mesh, encore peu appliqué en météo.

**Trois partenariats à instruire** :

1. **Intégration Copernicus** comme nœud opérateur national (au lieu de répliquer).
2. **Diffusion ouverte sur cloud public** (modèle NOAA BDP) en complément du back-office souverain.
3. **Contribution à Pangeo / STAC** pour ancrage communautaire et ouverture aux talents.

## 6.3 Ce que la cible nationale peut apporter à l'écosystème

Aucune plateforme actuelle ne combine :

- Souveraineté nationale.
- Single source of truth à 3 niveaux.
- Data contracts gouvernant techniques et métier ensemble.
- Couverture météo complète (NWP + observations + satellite + climat + saisie).
- Compute partagé OSS souverain.

C'est une position **défendable et différenciante** sur la scène européenne et internationale.

\newpage

# 7. Risques d'inertie

Le benchmark révèle aussi des **risques d'inertie** :

| Risque | Manifestation | Mitigation |
|---|---|---|
| Réinventer un MARS bis | Système propriétaire, vocabulaire interne, lourd | Discipline architecturale stricte, choix OSS, formats ouverts |
| Réinventer un NOAA BDP bis | Couche d'open data sans gouvernance interne | Investir d'abord dans la gouvernance interne, puis ouvrir |
| Choisir un Earth Engine bis | Compute lock-in, vocabulaire custom | Refuser tout API non standard, exiger formats ouverts |
| Construire sans communauté | Produit isolé, talents difficiles à attirer | Aligner avec Pangeo, contribuer aux standards |
| Construire sans modèle économique | OPEX permanent sans retour | Modèle membres / facturation usage / B2B services à clarifier dès le début |

\newpage

# 8. Synthèse

Aucune plateforme existante n'est la cible. Mais l'ensemble du benchmark dessine clairement :

- **Les standards à adopter** : STAC, Zarr, CF, Iceberg, Parquet.
- **Les API à proposer** : REST modernes + compute partagé + Jupyter.
- **Les modèles économiques viables** : intergouvernemental (MARS, EUMETSAT, Copernicus) ou public-private partnership pour la diffusion (NOAA BDP).
- **Les partenariats à instruire** : Copernicus, Pangeo, EUMETSAT.
- **Les pièges à éviter** : lock-in propriétaire, vocabulaire custom, plateforme isolée sans communauté, ouverture sans gouvernance interne.

La cible nationale a une **position défendable** : combiner souveraineté + gouvernance par construction + interopérabilité par standards + ouverture mesurée + compute partagé. Cette combinaison n'existe pas aujourd'hui. C'est une opportunité.

---

*Document évolutif. Vérification des données publiques recommandée à la décision.*
