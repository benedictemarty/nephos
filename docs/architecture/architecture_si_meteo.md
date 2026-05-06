---
title: "Plateforme SI Météo Gouvernée — Document d'Architecture"
author: "Architecture senior"
date: "2026-05-06"
subtitle: "Vision, principes, fonctions, alerting, fraîcheur, complétude, questions critiques"
lang: fr
---

# 1. Contexte et constat

Les opérateurs météorologiques nationaux (l'opérateur national, DWD, NOAA, MetOffice) partagent un constat structurel :

- **Volumétrie hors contrôle** : 5 à 30 Po actifs, croissance non-linéaire portée par la haute résolution (modèles km-scale), les ensembles probabilistes et les nouvelles missions satellites.
- **Réplication systémique** : chaque équipe métier (prévi, climat, aéro, recherche, climatique régional) opère ses propres copies. Multiplicateur effectif x5 à x10 sur les volumes utiles.
- **Gouvernance absente ou implicite** : pas de catalogue transverse, pas de data contract, pas de lineage, ownership flou, schémas qui dérivent silencieusement.
- **Sémantique fragmentée** : CF Standard Names utilisés en aval, mais **pas comme clé pivot** dans le catalogue technique. Chaque équipe maintient ses propres lookups CF / GRIB / BUFR.
- **Patrimoine outils hétérogène** : Hadoop legacy, NAS classiques, scripts ad-hoc, notebooks isolés, peu de containerisation.

Le coût n'est pas que financier (stockage). Il est **organisationnel** (impossibilité d'auditer, latence de mise à disposition, dette technique cumulative) et **scientifique** (irreproductibilité des résultats, perte de mémoire institutionnelle).

# 2. Vision cible

> **Une plateforme data météo où la donnée existe une fois, est trouvable, comprise, gouvernée et exploitable à l'échelle pétaoctet — par construction, pas par discipline.**

Trois principes fondateurs structurent toute la plateforme.

## 2.1 — Unicité à trois niveaux (single source of truth)

| Niveau | Source autoritative unique | Identifiant canonique |
|---|---|---|
| **Notions** (sens métier) | Glossaire sémantique unifié | URI `https://w3id.org/{org}/vocab/{scheme}/{notation}` |
| **Méta-données** (techniques) | Catalogue Iceberg | `{namespace}.{table}@{snapshot_id}` |
| **Données** (physiques) | Object store immuable | `lake://{namespace}/{dataset}@{snapshot}` |

**Aucun consumer ne stocke. Tous référencent.** La performance est résolue par caching transparent, jamais par copie applicative.

## 2.2 — Trois strates de données strictement distinctes

| Strate | Caractère | Exemple |
|---|---|---|
| **Primaires** | Brutes, immuables, source de vérité | GRIB modèle régional, BUFR SYNOP, radar L2 |
| **Secondaires** | Calculées par recette **déterministe** versionnée | T à FL60, CAPE, cumul 6h |
| **Produits** | Artefacts métier paramétrés (présentation) | Carte PNG, METAR, briefing |

Confondre secondaire et produit est l'erreur architecturale classique : un secondaire est une **donnée typée géoréférencée**, un produit est une **fonction paramétrée**.

## 2.3 — Gouvernance par contracts, pas par discipline

Chaque dataset publié dispose d'un **data contract** versionné en Git, qui couple :

- **Schéma technique** (Iceberg / Avro)
- **Concept métier** (URI sémantique)
- **Règles de qualité** (bornes physiques, complétude, fraîcheur)
- **Owner** + **SLA**
- **Politique d'accès**

Sans contract, pas de publication. Le contract est le pivot entre couches techniques et métier.

\newpage

# 3. Schéma fonctionnel de la plateforme

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          CONSUMERS (read-only)                            │
│  Humains :  Briefing aéro │ Carto │ Dashboard │ Notebook │ Public         │
│  Systèmes : Modèles aval │ Aviation │ Climat │ Apps tiers via API         │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
                                     │  3 patterns d'accès, lecture seule
┌────────────────────────────────────┴─────────────────────────────────────┐
│                        FONCTIONS DE SERVICE                              │
│                                                                          │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│   │ Discovery  │  │  Resolve   │  │   Fetch    │  │ Product render   │  │
│   │            │  │            │  │            │  │                  │  │
│   │ "Qu'existe-│  │ "Quel(s)   │  │ "Donne la  │  │ "Génère carte /  │  │
│   │  t-il qui  │  │  produit(s)│  │  slice/    │  │  METAR / PDF     │  │
│   │  couvre ?" │  │  pour ma   │  │  valeur,   │  │  paramétré"      │  │
│   │            │  │  question?"│  │  lazy"     │  │                  │  │
│   └────────────┘  └────────────┘  └────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌────────────────────────────────────┴─────────────────────────────────────┐
│                  GOUVERNANCE & SÉMANTIQUE (transverse)                   │
│                                                                          │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│   │ Glossaire  │  │ Catalogue  │  │ Lineage &  │  │ Data contracts   │  │
│   │ métier     │  │ technique  │  │ observa-   │  │ + qualité        │  │
│   │            │  │            │  │ bility     │  │                  │  │
│   │ Notions CF │  │ Tables,    │  │ Qui consom-│  │ Schémas + sens   │  │
│   │ + QUDT +   │  │ schémas,   │  │ me quoi,   │  │ + bornes + SLA   │  │
│   │ WMO + ECMWF│  │ snapshots, │  │ freshness, │  │ + owner +        │  │
│   │            │  │ partitions │  │ alertes    │  │ politique accès  │  │
│   └────────────┘  └────────────┘  └────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌────────────────────────────────────┴─────────────────────────────────────┐
│              ORCHESTRATION (3 modes, un seul moteur)                     │
│                                                                          │
│   ┌────────────┐  ┌────────────┐  ┌────────────────────────────────┐    │
│   │ Heure      │  │ Ressource  │  │ Pivot (lineage)                │    │
│   │ (cron)     │  │ (event)    │  │                                │    │
│   │            │  │            │  │                                │    │
│   │ Poll       │  │ Snapshot   │  │ Concept ou recette change →    │    │
│   │ sources    │  │ Iceberg →  │  │ assets dépendants stale →      │    │
│   │ externes,  │  │ trigger    │  │ rematérialisation auto         │    │
│   │ archive    │  │ DAG        │  │                                │    │
│   └────────────┘  └────────────┘  └────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
                                     │  écrit immuablement
┌────────────────────────────────────┴─────────────────────────────────────┐
│                       3 STRATES DE DONNÉES                               │
│                                                                          │
│   ┌────────────┐    ┌────────────────┐    ┌────────────────────────┐    │
│   │ PRIMAIRES  │ →  │ SECONDAIRES    │ →  │ PRODUITS               │    │
│   │            │    │                │    │                        │    │
│   │ Modèles    │    │ Recettes       │    │ Templates paramétrés   │    │
│   │ HPC, obs,  │    │ déterministes  │    │ (carte, METAR, PDF)    │    │
│   │ satel.,    │    │ versionnées    │    │ — URN déterministe     │    │
│   │ radar —    │    │ (Git)          │    │ — cache CDN            │    │
│   │ bruts      │    │                │    │                        │    │
│   │ immuables  │    │                │    │                        │    │
│   └────────────┘    └────────────────┘    └────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌────────────────────────────────────┴─────────────────────────────────────┐
│                       FONDATIONS PHYSIQUES                               │
│                                                                          │
│   ┌──────────────────────┐  ┌──────────────────────────────────────┐    │
│   │ Object store         │  │ Compute                              │    │
│   │ S3 / Ceph (Po-scale) │  │ k8s + Dask + DuckDB + bridge HPC     │    │
│   │ Zarr v3 (gridded)    │  │ "Bring code to data" :               │    │
│   │ Parquet (tabulaire)  │  │  zéro copie pour calcul              │    │
│   └──────────────────────┘  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌────────────────────────────────────┴─────────────────────────────────────┐
│           INGESTION (toujours pull / webhook, jamais push aveugle)       │
│  Sources externes (GFS, IFS Open, Copernicus, AviationWeather, EUMETSAT) │
│  Sources internes (HPC modèles régionaux et globaux nationaux, réseau d'observation national, radar mosaïque, capteurs) │
│                                                                          │
│  → tout passe par un connecteur déclaré, contractualisé, observé         │
└──────────────────────────────────────────────────────────────────────────┘
```

\newpage

# 4. Stack technique de référence (open source uniquement)

| Couche fonctionnelle | Composant retenu | Justification |
|---|---|---|
| Object store | **MinIO** (POC) → **Ceph / S3** (prod) | Standard S3, déployable seul |
| Format gridded | **Zarr v3** | Standard scientifique Pangeo, adopté par ECMWF |
| Format tabulaire | **Parquet** | Standard analytique de facto |
| Catalogue technique | **Apache Iceberg + Lakekeeper** | Snapshots, time-travel, schema evolution, REST OSS |
| Glossaire métier | **Référentiel SKOS** (CF + QUDT + WMO + ECMWF) | Standards W3C, mappings inter-encodings |
| Orchestrateur (option principale) | **Dagster** | Asset-based, lineage natif, freshness + auto-materialize natifs |
| Orchestrateur (option souveraine) | **Kestra** (FR, Lyon) | YAML déclaratif, multi-langage, UI métier ; coût : recoder freshness + auto-materialize |
| Transformations SQL | **dbt-core** sur DuckDB / Trino | Standard analytique |
| Compute scientifique | **xarray + Dask + flox** | Standard météo |
| Compute interactif | **DuckDB** | Lecture native Iceberg / Parquet / Zarr |
| Qualité | **Soda Core / Great Expectations** | OSS, intégrable CI |
| Lineage / observability | **OpenMetadata** ou **DataHub** | Ingest catalog Iceberg + glossaire |
| Cartographie | **Martin** (vector tiles) + **MapLibre** | OSS, perf cloud-native |
| Cartes scientifiques | **Cartopy / xarray + datashader** | Standard météo |
| API service | **FastAPI** | Standard Python 2026 |
| Démos / saisie | **Streamlit / NiceGUI** (POC) | Pas de React custom |
| Bus d'événement | **Aucun en V1** ; **NATS** ou **Redpanda** si volume streaming le justifie en V2 | Iceberg snapshots + sensors couvrent 80% du besoin |

## 4.1 — Le choix d'orchestrateur : Dagster ou Kestra ?

Les deux sont des candidats sérieux et **OSS Apache 2.0**. La décision dépend du contexte d'organisation et n'est pas purement technique.

| Critère | Dagster | Kestra |
|---|---|---|
| Paradigme | Asset-based (data-aware) | Task / flow (workflow classique) |
| Définition workflow | Python décorateurs | YAML déclaratif |
| Lineage natif | ✅ first-class | ⚠️ via plugins, moins central |
| Freshness policies (détection retard) | ✅ natif | ❌ à coder |
| Auto-materialize sur changement (mode pivot) | ✅ natif | ⚠️ via triggers explicites custom |
| Multi-langage | ⚠️ Python d'abord | ✅ first-class (Python, JS, Groovy, etc.) |
| UI / accessibilité non-tech | Bonne | **Excellente** (low-code, très visuelle) |
| **Souveraineté** | États-Unis (Elementl) | **UE (éditeur européen)** |
| Maturité écosystème data engineering | Très large | En croissance |
| Maturité écosystème workflow général | Bonne | Excellente |

**Recommandation** :

- **Si le sponsor pèse sur la souveraineté** (l'opérateur national, sécurité civile nationale, services de l'État) : Kestra mérite d'être retenu, avec un coût documenté de ~2 mois pour recoder en Python les capacités natives Dagster (freshness + auto-materialize). Le différentiel UI et multi-langage compense l'effort.
- **Si l'équipe est purement data engineering Python** et que le lineage column-level + asset-aware est central : Dagster reste plus court à mettre en œuvre.
- **Hybride réaliste** : Kestra en orchestrateur de surface (visibilité, multi-langage, gouvernance, adoption métier) + module Python custom léger (~500 lignes) pour les freshness / pivots. Évite de réimplémenter un Dagster complet.

Le choix doit être tranché en arbitrage architectural avec sponsor, pas par préférence technique.

## 4.2 — Décisions techniques actées comme non négociables

- Pas de Hadoop / HDFS.
- Pas de Hive Metastore (remplacé par Iceberg REST).
- Pas d'Airflow (data-aware insuffisant).
- Pas de Kafka direct sans équipe ops dédiée.
- Pas de Snowflake / Databricks / BigQuery (lock-in, coût Po-scale).
- Pas de Tableau / Power BI (duplication client, anti single-source).

# 5. Principes de gouvernance opérationnelle

## 5.1 — Toute publication passe par un data contract

Aucune table Iceberg ni dataset Zarr n'est exposé sans contract YAML versionné. Le contract est validé en CI : schéma cohérent, concept référentiel existant, règles qualité exécutables, owner identifié, SLA défini.

## 5.2 — Toute consommation est tracée

- API Discovery / Resolve / Fetch : log structuré avec consumer ID, dataset URN, snapshot, slice.
- OpenMetadata reçoit le lineage en quasi-temps réel.
- Audit possible à 30 jours minimum.

## 5.3 — Toute ressource a un owner unique

Personne, équipe ou service identifié, joignable, responsable des incidents qualité. Ownership déclaré dans le contract.

## 5.4 — Anti-patterns explicitement interdits

À graver dans une charte de gouvernance :

- Copier une table dans un Postgres applicatif.
- Maintenir une copie locale « pour mon notebook ».
- Coder un lookup CF → GRIB hors du glossaire.
- Documenter un schéma dans un wiki (le schéma est dans Iceberg).
- Lancer un job en cron Linux hors orchestrateur.
- Stocker un produit autrement que par URN cache.
- Republier sous un autre nom une donnée déjà publiée.
- Pousser un blob > 1 Mo dans un bus d'événement.

\newpage

# 6. Roadmap de mise en œuvre

| Phase | Durée | Livrable | Périmètre |
|---|---|---|---|
| **POC démonstrateur** | 3-4 mois solo / 6 sem. duo | Chaîne end-to-end sur 1-2 sources | MinIO + Iceberg + orchestrateur + référentiel + résolveur sur GFS + IFS Open |
| **Pilote interne** | 6-9 mois | Adoption par 1 équipe métier réelle | Ajout modèles régionaux et globaux nationaux, OpenMetadata, premiers data contracts en prod, alerting V1, freshness V1, complétude V1 |
| **Industrialisation** | 12-18 mois | Plateforme cible en parallèle du legacy | k8s, multi-tenant, bridge HPC, retrait progressif des copies historiques |
| **Prod Po-scale** | 24+ mois | Décommissionnement legacy | Réplication multi-site, broker NATS / Redpanda si streaming obs validé, archive ré-analyse |

**Principe de migration** : la plateforme nouvelle vit en parallèle du legacy, avec **double lecture** sur les datasets clés. Le legacy ne disparaît que dataset par dataset, après migration validée par l'équipe propriétaire.

\newpage

# 7. Questions à challenger (à arbitrer avant tout lancement)

Ces questions ne sont pas rhétoriques. Chacune **change matériellement** l'architecture, le calendrier ou le sponsor. Elles doivent recevoir une réponse explicite, datée, validée.

## 7.1 — Stratégiques (sponsor)

1. **Sponsor exécutif identifié ?** Sans sponsor au niveau direction, la plateforme se heurtera aux silos et aux baronnies historiques. Une plateforme transverse sans sponsor transverse meurt.
2. **Cible : l'opérateur national seul, consortium européen (EUMETNET / ECMWF), ou produit générique vendable ?** Change la roadmap, le mode de financement, la gouvernance.
3. **Migration legacy gérée comment ?** Big-bang (impossible), parallèle puis bascule (long, coûteux, prudent), greenfield sur nouveaux usages uniquement (rapide mais ne résout pas la dette) ?
4. **Modèle économique en interne ?** Plateforme gratuite (centre de coût), facturation à l'usage (responsabilise les équipes mais alourdit), modèle showback (visibilité sans facturation) ?

## 7.2 — Architecture / techno

5. **HPC interne (d'un opérateur national) : intégration native ou bridge ?** Le code data plane fonctionne-t-il sur les calculateurs internes (Bull / Atos) ou faut-il copier vers k8s ? La réponse change radicalement le périmètre du « bring code to data ».
6. **Souveraineté du stockage ?** Object store on-premise (Ceph), souverain (OVH, Outscale, Scaleway, S3NS) ou cloud public (AWS / GCP) ? Contraintes RGPD, RGS, licence data WMO Resolution 40, climat.
7. **Reprise sur incident à l'échelle Po ?** Une corruption silencieuse sur 100 To, ça se restaure en combien de temps ? Plan de continuité explicite ou pas ?
8. **Cycle de vie des secondaires matérialisés ?** Combien de temps on les garde ? Régénération depuis primaires + recettes versionnées (cher en compute) ou rétention longue (cher en stockage) ?
9. **Versioning des recettes : règles strictes ou liberté ?** Une recette CAPE v1 → v2 invalide-t-elle automatiquement 5 ans de secondaires ? Politique de compatibilité ascendante.
10. **Choix d'orchestrateur Dagster vs Kestra** — argument souveraineté vs maturité data-aware. À trancher avec sponsor + DSI.

## 7.3 — Gouvernance / humain

11. **Qui est légitime à créer un concept dans le glossaire ?** Comité de curation (lent, robuste), self-service avec review (équilibré), open (rapide, dérive) ? Modèle de Wikipédia, GitHub, Confluence ? Ce choix structure tout.
12. **Que faire des cas où une équipe refuse de migrer ?** Plan de dérogation, sunset forcé, parallèle indéfini, escalade direction ? Politique explicite ou flou ?
13. **Comment former les équipes ?** Une plateforme moderne sans accompagnement reste inutilisée. Plan de formation, ambassadeurs, documentation, support ?
14. **Sécurité et politique d'accès ?** Modèle RBAC, ABAC, attribut métier ? Qui voit quoi, comment l'auditer, comment masquer une donnée sensible (positionnement militaire, météo aéronautique réglementée) ?

## 7.4 — Coût et faisabilité

15. **Budget infra cible à 18 mois ?** Po-scale honnête, c'est ~50 k€/an minimum en hardware, ou 200 k€/an minimum en cloud public, hors RH. Le sponsor a-t-il provisionné ?
16. **Équipe minimale viable ?** Un solo livre un POC. Un produit pilote demande 3 ETP minimum (1 archi data, 1 dataops, 1 dev plateforme). La prod demande 6-8 ETP minimum.
17. **Make vs Buy ?** Snowflake / Databricks couvrent 60% du besoin techniquement à coût élevé et lock-in. Un build OSS donne 100% du besoin avec 3 ans d'investissement RH. Décision : où placer le curseur ?

## 7.5 — Différenciation

18. **Qu'est-ce que cette plateforme fait que ECMWF MARS, EUMETSAT Data Store, NOAA Big Data ne font pas déjà ?** La réponse honnête : **la fusion sémantique + technique + contract dans un même catalogue**. Mais c'est défendable seulement si on tient le principe d'unicité jusqu'au bout. Sinon, on construit un énième silo.
19. **Pérennité au-delà du sponsor initial ?** Une plateforme qui repose sur 2 personnes risque la mort à leur départ. Politique de bus factor, documentation, ouverture éventuelle en open source ?

## 7.6 — Alerting (annexe A)

20. **Cible métier prioritaire ?** Vigilance l'opérateur national (interfaçage avec système existant), aviation (FIR, SIGMET automatisés), agro (parcelle, ETP), hydro (bassins) ? Change le modèle de zone et le partenaire d'intégration.
21. **Niveau d'engagement légal ?** Une alerte aviation a une portée réglementaire (OACI). Une alerte vigilance autorité locale engage la responsabilité publique. Quelle classe de SLA, quelle traçabilité, quelle redondance imposées ?
22. **Modes dégradés ?** Si la plateforme principale tombe, les alertes critiques continuent-elles ? Architecture de fallback (chemin court depuis observation brute) ou échec accepté ?
23. **Politique de silence / inhibition ?** Un opérateur peut-il temporairement masquer une alerte (« on sait, on traite ») et selon quelle gouvernance ?
24. **Cycle de vie des règles obsolètes ?** Une règle non déclenchée depuis 5 ans : on garde, on archive, on supprime ?
25. **Acquittement individuel ou collectif ?** Une équipe d'astreinte de 3 personnes : la première qui acquitte ferme pour tous, ou chacun doit voir et accuser ?
26. **Multi-canalité dégradée ?** Si l'email tombe, on bascule SMS automatique (escalade) ou on attend ?
27. **Ingestion d'alertes externes ?** Vigilance l'opérateur national, alertes EUMETNET MeteoAlarm, alertes Copernicus EFAS : la plateforme les **republie** ou les **rebroadcast** ?

## 7.7 — Fraîcheur SLA (annexe B)

28. **Engagement contractuel ou best-effort ?** Quels datasets ont un SLA *garanti* (avec pénalité, ressources dédiées) vs *best-effort* (« on essaie ») ?
29. **Modèle de causes amont** : quand NOMADS est en retard, est-ce que c'est *leur* problème ou *le nôtre* ? Politique d'imputation, contractualisation avec sources amont.
30. **Cascade acceptable** : si le modèle régional est en retard de 30 min, est-ce qu'on accepte que la diffusion soit en retard de 30 min, ou on bascule sur un fallback (GFS dégradé) automatiquement ?
31. **Réseau OPS hors heures ouvrées** : un retard détecté à 03:00 UTC, qui est notifié, comment, jusqu'à quand on attend avant escalade ?
32. **Reporting SLA** : à qui, à quelle fréquence, sous quel format ?
33. **Politique de purge des partitions manquantes** : un cycle attendu jamais arrivé reste « missing » à perpétuité ou on l'archive en `permanently_unavailable` après N jours ?
34. **Alerte sur récurrence** : un dataset qui rate son SLA 3 fois en 24h doit-il déclencher une alerte distincte (« source instable ») au-delà des alertes individuelles ?

## 7.8 — Complétude / runs partiels (annexe C)

35. **Politique strict vs degraded par dataset ?** Quels datasets refusent toute incomplétude (rejet du run) vs lesquels acceptent une publication partielle marquée ?
36. **Distinction mandatory vs optional** : qui décide quels champs sont essentiels ? Owner du contract seul ou comité ?
37. **Lineage column-level (par champ)** est-il possible avec l'outillage retenu (OpenMetadata, dbt) ou faut-il custom ?
38. **Récupération tardive** : si les champs manquants arrivent 2h plus tard, on bascule en `partial_recovered` et on rejoue les downstream — politique de cascade ?
39. **Marquage des secondaires construits sur dataset partiel** : le secondaire issu d'un primaire `partial` est-il automatiquement marqué `degraded` ou conservé `ok` si les champs manquants ne le concernent pas ?
40. **Reporting de complétude** : taux de complétude par cycle, par source, par champ — qui consulte, à quelle fréquence ?

## 7.9 — Cycle de vie hot / warm / cold / frozen (annexe D)

41. **Critères de promotion / démotion** : par quels seuils d'accès observe-t-on qu'une donnée passe d'un tier à l'autre ? Politique automatique ou intervention ?
42. **Latence acceptable du frozen** : minutes ou heures pour un retrieval Glacier / bande ? Le métier accepte-t-il l'asynchronisme ou faut-il un fallback warm permanent pour certains datasets ?
43. **Conservation patrimoniale** : quels datasets sont gardés à perpétuité (climat, vigilance, aviation), avec quelle conformité (WMO, OACI, archives nationales) ? Politique explicite par contract.
44. **Plan de retrieval testé** : le frozen est-il vraiment lisible quand on en aura besoin dans 10 ans ? Tests de restauration réguliers ou découverte le jour J ?
45. **Économie du tiering** : ROI mesuré (coût stockage évité vs latence consumers) ? Sinon le tiering devient cosmétique.
46. **Tiering des secondaires régénérables** : on archive ou on supprime sachant qu'on peut régénérer ? Politique « expire plutôt qu'archive » à acter.

## 7.10 — Pré-traitement raw → bronze → primaire (annexe E)

47. **Sunset des formats internes legacy** : engagement avec les équipes HPC pour produire directement en format standard, à quel horizon ? Migration progressive ou définitive ?
48. **Versionning des recettes de normalisation** : si une recette v2 corrige un bug v1, rejoue-t-on tout l'historique de la zone bronze ? Politique explicite.
49. **TTL de la zone raw** : 24h, 7j, plus long pour audit ? Compromis entre coût stockage et capacité de rejeu.
50. **Pertes de précision déclarées** : une normalisation qui réduit la précision (ex. troncature, downsample) est-elle bloquée ou autorisée si déclarée explicitement dans le contract ?
51. **Reprojection / régrillage** : qui décide de la grille de référence cible et avec quelle gouvernance ? Une seule grille pour tout (simple, perte information) ou multi-grilles (complexe, fidèle) ?
52. **Validation entre bronze et primaire** : quel niveau d'effort de validation accepte-t-on (qualité, complétude) avant de promouvoir ? Garde-fou bloquant ou warning ?

## 7.11 — Saisie opérateur (annexe F)

53. **Liste des données métier saisies** : feux de forêt, dégâts tempête, observations citoyennes, mesures manuelles, niveau d'eau, qualité air, autres ? Périmètre à arbitrer.
54. **Modèle de validation par superviseur** : auto-validation par rôle, validation 2-yeux, validation comité ? Selon criticité métier.
55. **Saisie offline et conflit de sync** : un même feu signalé par 2 observateurs hors connexion, qui prime à la reconnexion ?
56. **Saisie citoyenne encadrée** : intégration de plateformes citoyennes (signalement vigilance crues, qualité air locale) via API. Confiance, modération, validation ?
57. **Pièces jointes (photos, vidéos)** : politique de rétention, anonymisation (visages, plaques), conformité RGPD. Lifecycle distinct des données tabulaires.
58. **Audit de saisie** : quel niveau d'enregistrement (user agent, geoloc, version DataWindow) ? Contraintes RGPD vs traçabilité opérationnelle.
59. **Synchronisation avec systèmes métier externes** : SI pompiers, autorités locales, sécurité civile — la plateforme est-elle source ou consommatrice ? Politique d'API et engagement contractuel.

## 7.12 — Modification d'une valeur existante (annexe G)

60. **Matrice rôle × type de donnée × type de modification** : qui peut modifier quoi, à quel statut, sous quelle validation ?
61. **Validation 2-yeux** : pour tout, ou seulement les données réglementées (METAR, vigilance) ? Compromis rigueur / réactivité.
62. **Délai maximum pour corriger** : une heure, une journée, à perpétuité ? Une correction d'une donnée climatologique de 1995 est-elle légitime aujourd'hui ?
63. **Notification des consumers** : tous, ou seulement ceux qui ont récemment lu cette donnée ? Mécanisme de subscription / rappel.
64. **Cascade downstream très large** : une correction qui invalide 200 secondaires et 1000 produits — rejouer tout, prévenir, demander validation supplémentaire ?
65. **Override prévisionniste vs correction** : journalisés séparément ? Beaucoup d'opérateurs (NOAA, MetOffice) les distinguent.
66. **Responsabilité légale** : qui est responsable d'une correction tardive d'un METAR aviation qui aurait pu prévenir un incident ?
67. **Format de diffusion d'event de correction** : OACI prévoit `COR` sur METAR ; pour les autres flux (API tiers, webhooks autorité locale), quel format standard adopter ?
68. **Conservation des chaînes de versions** : 5 ans (réglementaire OACI), 30 ans (climat), perpétuelle ? Politique par type de donnée.

## 7.13 — Politiques d'accès et classifications (annexe H)

69. **Périmètre de classification** : L0/L1/L2/L3 retenu ou modèle existant l'opérateur national à recoder ? Cohérence avec IGI 1300, OACI, RGPD à valider avec juriste.
70. **Plateforme L3 défense** : plateforme jumelle complète ou enclave isolée ? Niveau de cloisonnement réseau (air gap, diode, VPN classifié) ?
71. **Attribution des habilitations** : auto-déclaratif (contrôle a posteriori), comité, intégration RH automatique, cycle de re-validation ?
72. **Embargos opérationnels** (vigilance, sécurité civile) : qui décide de la levée, sous quelle gouvernance, quelle traçabilité ?
73. **Données de capteurs privés sous contrat** : intégration de l'exclusivité commerciale dans le moteur ABAC vs gestion contractuelle externe ?
74. **Audit d'accès** : conservation 5 ans, 10 ans, 30 ans ? Plus longtemps que la donnée elle-même probablement.
75. **Tests de fuites par recoupement** : red team interne pour valider qu'un consumer L0 ne peut pas reconstituer L1 par jointure ? Politique de test.
76. **DPO et chaîne juridique** : qui valide les access contracts, qui répond aux demandes RGPD, en combien de temps ?
77. **Recherche académique** : politique d'agrément, sandbox isolée, possibilité de publication, vérification non-commerciale ?
78. **Souveraineté de stockage** : résidence périmètre national imposée pour L1+ ? Cloud souverain (S3NS, OVH, Outscale) imposé ou cloud public toléré pour L0 ?

\newpage

# 8. Risques structurants

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Adoption par les équipes legacy refusée | Élevée | Critique | Sponsor exécutif fort, dérogations bornées, double-lecture en parallèle, ambassadeurs internes |
| Dérive vers énième silo (« notre catalogue ») | Moyenne | Critique | Charte single-source contractuelle, validation CI bloquante, audit semestriel |
| Sous-estimation effort orchestration / qualité | Élevée | Élevé | Démarrer sur 1 source, étendre seulement après stabilisation |
| Lock-in implicite (concept, recette, contract liés à un OSS spécifique) | Faible-Moyenne | Moyen | Choix stack OSS portable, formats ouverts (Iceberg, Parquet, Zarr), pas de propriétaire critique |
| Perte de mémoire institutionnelle (recettes legacy non documentées) | Très élevée | Élevé | Migration accompagnée par les équipes propriétaires, recettes traduites en data contract avant retrait |
| Coût RH sous-estimé | Élevée | Critique | Calibrage sur retours d'expérience comparables (PSPC, EDF, BNP) ; pas moins de 3 ETP en pilote |
| Sécurité / compliance (données réglementées aviation, défense) | Moyenne | Critique | Architecture multi-tenant dès la V2, OPA / Lakekeeper policies, audit régulier |
| Échec en démonstration faute de cas d'usage convaincant | Moyenne | Élevé | Cas d'usage métier validé en amont avec sponsor (« T à FL60 multi-source » est un bon démonstrateur, pas une preuve d'adoption) |

# 9. Décisions architecturales actées (à formaliser en ADR)

| ADR | Sujet | Statut |
|---|---|---|
| ADR-001 | Modèle SKOS comme socle sémantique | Acté |
| ADR-006 | Pivot vers plateforme data météo gouvernée Po-scale | À rédiger |
| ADR-007 | Trois strates de données : primaires / secondaires / produits | À rédiger |
| ADR-008 | Stack technique de référence (Iceberg + Lakekeeper + Dagster ou Kestra + Zarr) | À rédiger |
| ADR-009 | Trois modes de déclenchement (heure / ressource / pivot), orchestrateur unique | À rédiger |
| ADR-010 | Anti-patterns gouvernance et single-source à 3 niveaux | À rédiger |
| ADR-011 | Pas de bus d'événements en V1, conditions de réintroduction (NATS / Redpanda) | À rédiger |
| ADR-012 | Modèle d'alerting : alert contracts + state machine + notifier découplé | À rédiger |
| ADR-013 | SLA de fraîcheur : freshness policies natives + état gouverné en Iceberg | À rédiger |
| ADR-014 | Politique de complétude : mandatory vs optional, lineage column-level | À rédiger |
| ADR-015 | Cycle de vie hot / warm / cold / frozen, pilotage par usage observé | À rédiger |
| ADR-016 | Pré-traitement raw → bronze → primaire (sources externes ET internes) | À rédiger |
| ADR-017 | Saisie opérateur : DataWindow générée depuis contract, primaire gouvernée | À rédiger |
| ADR-018 | Modification de valeur : event sourcing append-only, statuts explicites, cascade obligatoire | À rédiger |
| ADR-019 | Politiques d'accès : classifications L0-L3, ABAC OPA, isolation physique L3 défense | À rédiger |

# 10. Prochaine étape recommandée

**Ne pas écrire de code avant qu'au moins 4 questions de la section 7 aient une réponse documentée :**

- Question 1 (sponsor)
- Question 2 (cible)
- Question 15 (budget)
- Question 16 (équipe)

Sans ces 4, le projet reste un exercice technique. Avec ces 4, il devient un programme défendable, finançable et durable.

Une fois cadré, **un POC de 6 semaines avec 2 personnes** suffit à démontrer la chaîne de bout en bout sur 2 sources (GFS + IFS Open) et à constituer un démonstrateur défendable en réunion de direction.

\newpage

# Annexe A — Notification & alerting

## A.1 Positionnement architectural

L'alerting **n'est pas un nouveau silo**. C'est un **consumer dérivé** de la plateforme qui consomme primaires et secondaires, applique des règles versionnées, produit des événements alerte gouvernés et délègue le routage à un service séparé.

Trois niveaux à ne **jamais** confondre :

| Niveau | Rôle | Artefact |
|---|---|---|
| **Détection** | Évaluer si une condition est franchie | `alert_rule` versionnée + moteur d'évaluation |
| **État** | Suivre la vie d'une alerte (open / acknowledged / resolved / silenced) | Table `alerts` Iceberg + state machine |
| **Notification** | Acheminer vers les canaux (mail, SMS, webhook, push) | Service `notifier` découplé |

## A.2 Modèle « Alert Contract »

Une règle d'alerte est un artefact **gouverné comme un data contract** : YAML versionné en Git, validé en CI, lié à un concept du glossaire.

```yaml
id: vigilance-vent-fort-occitanie
concept: https://w3id.org/nephos/vocab/grandeurs-cf/wind_speed
scope:
  spatial: dept:[31, 32, 65, 81]
  temporal: rolling 1h
  forecast_horizon: 0-24h
condition:
  statistic: max
  comparator: ">="
  threshold: 100        # km/h, unité résolue via QUDT
  duration_consecutive: 30min
audience:
  - role: ops-prevention
  - role: prefecture-31
channels:
  - type: email
    template: alert.severe-wind.v2
  - type: webhook
    endpoint: https://api.autorite-locale.gouv.fr/alerts
state_machine:
  open_after: 1 evaluation
  resolved_after: 3 evaluations under threshold
  acknowledge_required: true
  escalation_after: 30min unacknowledged
severity: high
owner: equipe-vigilance
sla_evaluation: ≤ 5min
```

Sans alert contract en Git, **pas d'alerte en prod**.

## A.3 Pourquoi cette séparation est non négociable

- **Versionnage du seuil** : si on passe le seuil de 100 à 110 km/h, l'historique des alertes émises sous l'ancienne règle reste auditable.
- **Reproductibilité** : on peut rejouer une journée historique avec une règle modifiée.
- **Découplage canaux** : changer de provider SMS ne touche pas la détection.
- **Audit** : qui a été notifié, quand, sur quelle valeur, calculée depuis quel snapshot.
- **Single-source** : une règle = un fichier.

## A.4 Stack recommandée

| Fonction | V1 (POC / pilote) | V2 (industrialisation) |
|---|---|---|
| Évaluation des règles | Sensors orchestrateur sur commits Iceberg + schedule 1-5 min | Idem + offload partiel sur Faust / Bytewax si streaming |
| Stockage règles | **Git + repo `alert-contracts/`** | Idem |
| Stockage événements alerte | **Iceberg `alerts.events`** (immuable) + **Postgres `alerts.state`** (mutable) | Idem |
| Bus de notifications | **Postgres LISTEN / NOTIFY** + worker Python | **NATS JetStream** |
| Notifier (routage) | Service Python dédié (FastAPI) | Idem en k8s + retries / DLQ |
| Email | **Postfix / SES / Mailgun** | Idem |
| SMS | **OVH SMS / Twilio / Free Mobile** | Idem |
| Webhook | HTTP simple, retries exponentiels, DLQ | Idem + circuit breaker |
| Push web / mobile | **WebPush** + **Firebase Cloud Messaging** | Idem |
| UI alertes | **Streamlit / NiceGUI** lecture Iceberg + Postgres state | App dédiée si volume |
| Système d'astreinte | Pas en V1 — V2 : **PagerDuty / Opsgenie / Grafana Oncall** | Idem |

**Ne pas confondre alerting métier et alerting technique** :

- Les alertes **métier** (dépassement de seuil météo) vivent dans la plateforme.
- Les alertes **plateforme** (job orchestrateur cassé, latence Iceberg, espace MinIO plein) vivent dans Grafana / Alertmanager / Prometheus. Architecture parallèle, ne pas mélanger.

## A.5 Anti-patterns à bannir

- ❌ Coder un seuil dans une app de visualisation. Le seuil doit être dans un alert contract, l'app le lit.
- ❌ Avoir un cron qui interroge la base et envoie un mail. Tout passe par l'orchestrateur + Notifier service.
- ❌ Notifier sans état. Sans state machine, on re-spam à chaque évaluation ou on perd des alertes.
- ❌ Mélanger alerting métier et alerting plateforme. Deux mondes, deux outils.
- ❌ Confondre seuil et règle. Une règle = condition + scope + audience + canaux + état + escalade.
- ❌ Stocker les notifications envoyées dans une base d'app. Les events vivent dans Iceberg `alerts.events`.
- ❌ Acquittement par email sauvage. Acquittement = action API tracée.

\newpage

# Annexe B — SLA de fraîcheur (détection des données attendues non disponibles)

## B.1 Le problème

En météo, **l'absence d'une donnée est elle-même une donnée**. Une prévision modèle régional qui ne sort pas à l'heure prévue, c'est un signal critique :

- La carte H+0 est vide ou périmée.
- L'alerte vigilance ne peut plus être évaluée.
- Les downstream calculent sur de la donnée stale ou échouent silencieusement.

**Principe à acter** : *toute donnée attendue qui n'arrive pas à l'heure produit un événement gouverné* — au même titre qu'une donnée qui arrive.

## B.2 Modèle « Expected Schedule » dans le data contract

```yaml
id: nwp.gfs.t_pl
concept: https://w3id.org/nephos/vocab/grandeurs-cf/air_temperature
expected_publication:
  type: cron
  expression: "45 3,9,15,21 * * *"
  timezone: UTC
  partitioned_by: run_cycle
freshness_sla:
  warning_after: 15min
  error_after: 30min
  critical_after: 60min
  retention_alert_after_publish: 30min
upstream_dependency:
  source: external://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs
  expected_lag_from_cycle: 3h45min
on_late_data:
  recovery: true
  rebuild_downstream: true
  cascade_sla_to_downstream: true
owner: equipe-ingestion
sla_engagement: 99.5% à l'heure mensuel
```

## B.3 Distinguer retard plateforme et conséquence métier

| Niveau | Nature | Cible | Outil |
|---|---|---|---|
| **Retard plateforme** | Un dataset attendu n'est pas là à T | Équipe ops / dataops, source amont | Freshness policies + Grafana / Alertmanager |
| **Conséquence métier** | Sans ce dataset, telle alerte / produit ne peut plus être généré | Métier, public final | Alert contract qui dépend de l'état de fraîcheur |
| **Cascade SLA** | Le retard d'un primaire fait basculer ses secondaires/produits en retard | Observabilité + reporting | Lineage temporel via OpenMetadata |

## B.4 État de fraîcheur comme donnée gouvernée

```
platform.dataset_freshness_state           (Iceberg, append-only)
  - dataset_urn
  - expected_at         (timestamp UTC)
  - actual_arrival_at   (timestamp UTC, nullable)
  - state               (on_time / late / very_late / missing / recovered)
  - lag_seconds
  - cause               (upstream / internal / unknown)
  - upstream_source     (URN externe si cause = upstream)
  - detected_by         (sensor id / schedule id)

platform.dataset_freshness_current         (Postgres, mutable)
  - dataset_urn (PK)
  - state
  - since
  - last_event_iceberg_id
```

## B.5 Cascade SLA — exemple

```
nwp.gfs.t_pl@cycle=12z              expected: 13:45  actual: 14:30  late=45min  cause=upstream
   │
   ▼ derived_from
secondary.t_at_FL.gfs@cycle=12z     expected: 14:00  actual: 14:32  late=32min  cause=upstream-cascade
   │
   ▼ derived_from
product.maps.t_FL60.zone@12z      expected: 14:15  actual: 14:35  late=20min  cause=upstream-cascade
   │
   ▼ consumed_by
alert.eval.vigilance.vent.12z       expected: 14:30  actual: 14:30  late=0min   degraded_data=true
```

## B.6 Métriques exposées

À publier comme **secondaires** gouvernés :

- **Taux de ponctualité** par dataset (rolling 7j, 30j, 12 mois).
- **Retard p50 / p95 / p99 / max** par dataset.
- **Distribution des causes** (amont vs interne).
- **Cascade impact** : nombre de downstream impactés en moyenne, durée moyenne.
- **MTTR** par cause.
- **Disponibilité contractuelle** vs **engagement SLA**.

## B.7 Anti-patterns à bannir

- ❌ Pas de schedule explicite : « on espère que GFS arrivera ». Sans schedule attendu, pas de détection.
- ❌ Check posé en cron Linux indépendant : le contrôle vit dans l'orchestrateur.
- ❌ Retry infini sans backoff : retente avec backoff exponentiel + DLQ + alerte si DLQ se remplit.
- ❌ Logs sans persistance gouvernée : si l'historique des retards vit dans Grafana ou un fichier, pas de reporting.
- ❌ Confondre erreur d'ingestion et retard.
- ❌ Notifier à chaque check : déduplication via state machine.
- ❌ Ne pas propager : un downstream qui hérite d'un retard amont doit le savoir.
- ❌ Considérer un dataset « on time » dès qu'il arrive : si la fenêtre SLA est dépassée, il reste « late at arrival ».

\newpage

# Annexe C — Complétude des runs (données partielles)

## C.1 Le problème

Distinct du retard. Un dataset peut être **présent mais incomplet** :

- GRIB modèle régional publié, mais 3 paramètres sur 50 manquent (post-processing échoué).
- BUFR SYNOP arrivé, mais sans la pression au mer.
- Radar mosaïque arrivée, mais 2 radars sur 30 manquants.
- Satellite : 1 canal sur 16 corrompu.

**L'erreur classique** : traiter `partial` comme `present` → les consumers cassent en aval ou produisent de la mauvaise donnée silencieusement.

États possibles d'un dataset attendu :

| État | Signification |
|---|---|
| `present_complete` | Tout est là, conforme au manifeste de complétude |
| `partial` | Présent mais champs manquants (mandatory ou optional selon politique) |
| `partial_rejected` | Présent mais incomplet sur des champs mandatory → publication bloquée |
| `degraded` | Présent et complet structurellement, mais valeurs aberrantes / NaN excessifs |
| `late` / `very_late` / `missing` | Cf. annexe B |
| `partial_recovered` | Initialement partiel, complété par regrib tardif |

## C.2 Manifeste de complétude dans le data contract

Le contract déclare explicitement la liste des champs attendus, avec une politique :

```yaml
id: nwp.arome.publish.0p025deg
expected_fields:
  mandatory:
    - air_temperature@850hPa
    - geopotential_height@500hPa
    - eastward_wind@10m
    - northward_wind@10m
    - air_pressure_at_mean_sea_level
  optional:
    - cloud_area_fraction@850hPa
    - surface_downwelling_shortwave_flux
    - convective_available_potential_energy
completeness_policy: mandatory_subset
on_partial:
  publish_anyway: true
  mark_state: partial
  notify: equipe-ingestion
  block_downstream:
    - product.maps.t850            # bloque si T850 manque
    - alert.vigilance.vent         # bloque si vent manque
on_partial_rejected:
  retry_after: 15min
  max_retries: 3
  fallback: nwp.arpege.0p1deg      # fallback dataset si échec définitif
```

Politiques disponibles :

| Politique | Comportement |
|---|---|
| `strict` | Aucune incomplétude tolérée, rejet si un champ manque (mandatory ou optional). Pour datasets critiques régulés. |
| `mandatory_subset` | Mandatory complet exigé pour publication, optional toléré manquant. Cas le plus fréquent. |
| `degraded` | Publication systématique, marquage `partial` toujours. Pour datasets best-effort (recherche, expérimental). |

## C.3 Lineage column-level (par champ)

Aujourd'hui Iceberg trace lineage **table-à-table**. Pour la météo, on a besoin de **lineage par champ / variable** :

- Le secondaire `cape_calculé` dépend de `t_pl`, `q_pl`, `p_sl` du primaire modèle régional.
- Si `q_pl` (humidité) manque dans un cycle, alors `cape_calculé` ne peut pas être produit.
- Mais si seul `cloud_cover` (optional) manque, `cape_calculé` est produit normalement.

La cascade doit être dirigée **par champ**, pas par dataset entier. Trois approches :

| Approche | Avantage | Coût |
|---|---|---|
| Dagster assets partitionnés par champ | Granularité fine | Explosion combinatoire pour datasets riches |
| OpenMetadata column-level lineage | Standard catalog | Configuration fine, support partiel selon engine |
| Modélisation explicite dans le data contract (`derives_from: [field_uri, ...]`) | Contrôle total, single-source | À implémenter dans le moteur de complétude |

**Recommandation** : combinaison **data contract `derives_from` par champ** (autorité métier) + **OpenMetadata column-level** (visualisation et audit).

## C.4 État de complétude comme donnée gouvernée

```
platform.dataset_completeness_state    (Iceberg, append-only)
  - dataset_urn
  - cycle_id / partition_key
  - field_uri              (concept Nephos / CF)
  - expected: bool
  - present: bool
  - quality: ok | corrupt | empty | aberrant
  - completeness_pct       (calculé global ou par groupe)
  - mandatory_missing      (booléen agrégé)
  - detected_at

platform.dataset_completeness_current  (Postgres, mutable)
  - dataset_urn (PK)
  - cycle_id (PK)
  - completeness_pct
  - mandatory_missing
  - state                  (cf. tableau états ci-dessus)
  - last_event_iceberg_id
```

## C.5 Stack technique

| Fonction | Outil |
|---|---|
| Détection complétude GRIB | **`pygrib` / `eccodes`** : lit le manifeste sans charger les données complètes |
| Détection complétude Zarr | Inspection du store : `.zmetadata` liste les variables et chunks |
| Détection complétude Parquet | Inspection du schéma fichier : colonnes présentes vs attendues |
| Détection qualité valeurs | **Soda Core / Great Expectations** : règles déclaratives sur ranges, NaN ratio, monotonicité |
| Évaluation par cycle | Asset orchestrateur déclenché à arrivée du dataset (sensor commit Iceberg) |
| Politique fallback | Logique dans le moteur d'orchestration : si `partial_rejected`, switcher sur dataset de fallback déclaré |
| Notification | Notifier service (cf. annexe A) — événement de type `data_completeness` |

## C.6 Cascade complétude — exemple

```
nwp.arome.publish.0p025deg@cycle=12z       state=partial   completeness=94%
                                            missing=[cloud_cover@850, solar_flux]
   │
   ▼ derived_from (par champ)
   ├─ secondary.cape@cycle=12z              state=ok        (ne dépend pas de cloud_cover)
   ├─ secondary.cloud_top_height@cycle=12z  state=blocked   (dépend de cloud_cover, manquant)
   └─ secondary.t_FL60@cycle=12z            state=ok        (ne dépend que de t_pl, p_sl)

   ▼ derived_from
   ├─ product.maps.cape@cycle=12z           state=ok
   ├─ product.maps.cloud_top@cycle=12z      state=blocked   cause=upstream-incomplete
   └─ product.aviation.briefing@cycle=12z   state=degraded  cause=upstream-incomplete
                                            (cloud info reduced)
```

Chaque ligne est un **événement gouverné**. La cause et la dépendance par champ sont tracées. Un consommateur final voit immédiatement *« le briefing aviation est dégradé parce que la couverture nuageuse à 850hPa est manquante côté modèle régional »*.

## C.7 Anti-patterns à bannir

- ❌ Considérer un dataset incomplet comme « présent » → consumers cassent en aval.
- ❌ Considérer un dataset incomplet comme « manquant » → on perd la donnée partielle utilisable.
- ❌ Détection par essai de lecture (« je tente, ça plante, donc incomplet ») : centralisée, pas dans l'app cliente.
- ❌ Pas de modèle « essentiel vs optionnel » : on bloque tout pour un champ optionnel manquant.
- ❌ Pas de récupération possible : un cycle partiel reste partiel à vie alors que les champs auraient pu arriver tardivement.
- ❌ Lineage table-only : sans column-level, la cascade est sur-conservative (tout downstream est marqué `degraded` même quand le champ manquant ne le concerne pas).
- ❌ Bloquer en cascade sans nuance : un secondaire qui ne dépend pas du champ manquant doit pouvoir être produit normalement.

## C.8 Métriques exposées

Comme pour la fraîcheur, des secondaires gouvernés :

- **Taux de complétude moyen** par dataset, par cycle, par champ.
- **Champs les plus souvent manquants** (top 10 par source).
- **Causes de l'incomplétude** : panne post-processing, erreur transmission, bug encodage.
- **Impact downstream** : nombre de secondaires / produits bloqués par cycle, durée moyenne.
- **Taux de récupération** : % de cycles `partial` devenus `partial_recovered` dans les 6h.

## C.9 Insertion dans la roadmap

| Phase | Livrable complétude |
|---|---|
| **POC** | Manifeste de complétude sur 2 datasets + détection à l'arrivée + état Iceberg |
| **Pilote** | Couverture de tous les datasets pilotes, lineage column-level basique, politique fallback testée |
| **Industrialisation** | Cascade column-level sur tous les downstream, intégration Soda Core, métriques de complétude exposées |
| **Prod** | Engagement contractuel chiffré sur taux de complétude par dataset critique |

\newpage

# Annexe D — Cycle de vie de la donnée : hot / warm / cold / frozen

## D.1 Le problème

Sans politique de cycle de vie, **un Po-scale devient ingérable en coût et en performance**. Mais en météo, le tiering par âge brut est faux : une ré-analyse ERA5 de 1995 peut être plus consultée qu'une prévision GFS de 7 jours. Le tiering doit suivre **l'usage observé**, pas le calendrier.

## D.2 Quatre tiers explicites

| Tier | Critère | Latence cible | Stockage typique | Coût relatif |
|---|---|---|---|---|
| **Hot** (fraîche) | < 24h **ou** accès > 10×/jour | < 100 ms | NVMe + cache mémoire devant Iceberg | x1 |
| **Warm** (chaude) | 1-30j **ou** accès régulier (1-10/jour) | < 5 s | S3 Standard / Ceph SSD | x0.3 |
| **Cold** (froide) | > 30j et accès rare (< 1/sem) | < 5 min | S3 IA / Ceph HDD | x0.1 |
| **Frozen** (archive) | > 5 ans, valeur patrimoniale | minutes - heures | S3 Glacier / bande LTO / HSM | x0.02 |

**Principe non négociable** : la donnée reste **interrogeable dans tous les tiers**, son URN ne change pas. Seule la latence varie. Un consumer qui demande une donnée frozen reçoit une réponse asynchrone (« en cours de retrieval, ETA 5 min »), pas une erreur.

## D.3 Pilotage par usage, pas par âge

Le moteur de tiering observe les métriques d'accès Iceberg + S3 (`access_log`) et applique des règles déclaratives par data contract :

```yaml
lifecycle_policy:
  initial_tier: hot
  promotion_rules:
    - if: access_count_7d >= 10
      to: hot
  demotion_rules:
    - if: age >= 24h AND access_count_7d < 10
      to: warm
    - if: age >= 30d AND access_count_30d < 4
      to: cold
    - if: age >= 5y AND archive_eligible
      to: frozen
  retention_minimum: 30y       # patrimoine météo, conformité WMO
  retention_legal:
    - dataset: aviation.metar
      duration: 5y minimum     # OACI
    - dataset: vigilance.events
      duration: 10y minimum    # responsabilité publique
```

## D.4 Tiers distincts par strate (primaires / secondaires / produits)

Chaque strate a sa propre politique :

| Strate | Logique de tiering |
|---|---|
| **Primaires** | Conservation longue (patrimoine), accès décroissant. Hot 24-48h, warm 1 mois, cold puis frozen. ERA5 reste warm en permanence (climat). |
| **Secondaires matérialisés** | Régénérables depuis primaires + recettes versionnées. Politique « expirer plutôt qu'archiver » : > 6 mois, on supprime, on régénère à la demande. |
| **Produits** | Cache : TTL court (heures-jours), régénération à la demande depuis URN déterministe. Pas de frozen, pas de patrimoine. |

## D.5 Anti-patterns

- ❌ Tiering par âge brut sans observation des accès.
- ❌ Tiering qui change l'URN (« archive_/ » différent de « current/ »). L'URN est stable.
- ❌ Pas de cold à long terme : tout en hot devient ruineux.
- ❌ Frozen sans plan de retrieval testé : on découvre le jour J que la bande est illisible.
- ❌ Suppression silencieuse de patrimoine : toute purge est gouvernée par le contract et auditée.
- ❌ Réplication multi-tier (« je copie en hot pour mon notebook ») : viole le single-source.

## D.6 Stack technique

| Fonction | Composant |
|---|---|
| Lifecycle automation | **Iceberg snapshot expiration** + **S3 lifecycle rules** (ou Ceph equivalent) |
| Métriques d'accès | Logs Lakekeeper + S3 access logs ingérés en Iceberg |
| Politique déclarative | YAML par contract, validé en CI |
| Retrieval frozen | Service async dédié (Glacier restore, bande HSM) avec callback |
| UI / observation | Grafana panels par tier, par contract |

\newpage

# Annexe E — Pré-traitement des données : raw → bronze → primaire

## E.1 Le problème

Les sources réelles ne sont **jamais** au format souhaité. Quelques cas concrets :

- **NOMADS GFS** : GRIB1 ou GRIB2, variables nommées selon ECMWF GRIB tables, pas CF.
- **IFS Open Data** : GRIB2 + index `.idx`, à parser à part.
- **EUMETSAT MSG** : NetCDF3 ou format propriétaire, projection geostationnaire.
- **HPC interne** (d'un opérateur national) : sortie GRIB0 (format obsolète) ou formats internes hérités (FA, LFI, et autres formats propriétaires de chaînes nationales).
- **Réseau d'observation national** : BUFR avec encodage spécifique, parfois non-standard.
- **Satellite L1** : formats constructeurs (Sentinel-3 SAFE, etc.).

Aucun de ces formats ne peut être exposé tel quel comme **primaire gouverné**. Une étape de **normalisation** est nécessaire — pour les sources externes ET internes.

## E.2 Trois zones, frontières strictes

```
┌──────────────────────────────────────────────────────────────┐
│  ZONE RAW (atterrissage, transitoire)                        │
│  - Format source brut (GRIB0/1/2, NetCDF3, FA, BUFR, ...)    │
│  - TTL court (24h - 7j)                                      │
│  - Non exposée aux consumers métier                          │
│  - Buffer pour rejouer la conversion si bug détecté          │
└──────────────────────────────────────────────────────────────┘
                          │  recette de normalisation versionnée
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  ZONE BRONZE (normalisée)                                    │
│  - Format standard plateforme : Zarr v3 (gridded) /          │
│    Parquet (tabulaire) / GRIB2 si conservation legacy        │
│  - Variables mappées vers CF Standard Names                  │
│  - Unités converties en SI via QUDT                          │
│  - Grille de référence (reprojection si nécessaire)          │
│  - Manifeste de complétude (annexe C) appliqué               │
└──────────────────────────────────────────────────────────────┘
                          │  validation data contract + qualité
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  ZONE PRIMAIRE (gouvernée, exposée)                          │
│  - Validée contractuellement                                 │
│  - Owner identifié, SLA défini                               │
│  - Lineage tracé jusqu'à la source raw                       │
│  - Politique d'accès appliquée                               │
└──────────────────────────────────────────────────────────────┘
```

## E.3 Pas de différence interne / externe

Une sortie HPC interne `modèle régional GRIB0` et un fichier externe `GFS GRIB1 NOMADS` suivent **le même chemin architectural** :

1. Atterrissage en zone **raw** (S3 bucket dédié, namespace par source).
2. **Recette de normalisation versionnée** : code Python ou Spark, idempotent, taggé Git.
3. Écriture en zone **bronze** (Iceberg / Zarr).
4. Validation : qualité (Soda), complétude (annexe C), schéma contract.
5. Promotion en **primaire** : visible des consumers.

La distinction interne / externe n'apparaît qu'au niveau du **connecteur d'entrée** (HTTP poll, FTP, NFS partagé, webhook HPC). Tout ce qui suit est uniforme.

## E.4 Recette de normalisation = artefact gouverné

Comme une recette secondaire : code Git, taggé, idempotent, lineage tracé.

```yaml
id: normalize.gfs.nomads
input:
  source: external://nomads.ncep.noaa.gov/...
  format: grib2
  raw_zone: s3://lake-raw/external/gfs/{cycle}/
output:
  format: zarr
  bronze_zone: s3://lake-bronze/nwp/gfs/{cycle}/
  schema_contract: contracts/nwp.gfs.t_pl.yaml
recipe:
  module: nephos.normalize.grib_to_zarr
  function: convert
  version: "2.1.0"
operations:
  - decode_grib: pygrib
  - rename_variables: gfs_to_cf_mapping_v3.yaml   # CF Standard Names
  - convert_units: qudt                            # SI
  - reproject_to: epsg:4326 grid_0p25deg           # grille référence
  - chunk: { time: 1, level: 1, lat: 360, lon: 720 }
quality_checks:
  - no_nan_ratio_above: 0.05
  - value_ranges:
      air_temperature: [180, 330]
on_failure:
  retry: 3 with backoff
  fallback: keep_in_raw
  notify: equipe-ingestion
owner: equipe-ingestion
```

## E.5 Cas particulier : formats internes legacy

Pour les formats HPC internes (GRIB0, FA Aladin/modèle régional propriétaire, formats custom) :

- **Phase 1 (POC / pilote)** : recettes de conversion versionnées, traduisent vers Zarr/GRIB2.
- **Phase 2 (industrialisation)** : engagement avec les équipes HPC pour produire **directement** en format standard plateforme. Le format legacy est mis en sunset.
- **Phase 3 (cible)** : la zone raw ne reçoit plus de format legacy interne. Seules les sources externes non-maîtrisées y atterrissent.

## E.6 Anti-patterns

- ❌ Exposer la zone raw aux consumers (« j'ai juste besoin du GRIB brut »). Une exception devient la règle.
- ❌ Normalisation dans un script lancé à la main : pas versionné, pas tracé, pas reproductible.
- ❌ Pas de validation entre bronze et primaire : on publie de la donnée non conforme au contract.
- ❌ Conversion qui perd de l'information sans le déclarer (downsample silencieux, troncature de précision).
- ❌ Pas de lineage raw → bronze → primaire : impossible de rejouer ou de débugger.
- ❌ TTL infini sur la zone raw : 5 Po de raw inutile en 6 mois.
- ❌ Différencier le traitement interne / externe (« le HPC c'est interne, on lui fait confiance, pas de validation »). Tout passe par le même pipeline.

## E.7 Stack technique

| Fonction | Composant |
|---|---|
| Conversion GRIB | **eccodes** (lib ECMWF) + **xarray + cfgrib** |
| Conversion BUFR | **eccodes** + **pdbufr** |
| Conversion NetCDF | **xarray + netcdf4** |
| Conversion FA / LFI / autres formats internes | bibliothèques l'opérateur national ad-hoc, encapsulées en module Python plateforme |
| Mapping variables source → CF | tables YAML versionnées, intégrées au glossaire référentiel |
| Conversion d'unités | **QUDT** + module Python `pint-qudt` |
| Reprojection / régrillage | **xesmf** (regridding) ou **pyproj** (projection) |
| Chunking optimisé | **rechunker** + **kerchunk** pour virtualisation |
| Orchestration | Dagster ou Kestra (recette = asset / flow) |

\newpage

# Annexe F — Saisie opérateur (observations terrain : feux, dégâts, mesures manuelles)

## F.1 Nature de la donnée saisie

Les observations saisies par opérateur (feux de forêt, dégâts tempête, niveau d'eau lu manuellement, observations citoyennes encadrées) sont des **données primaires** au sens architectural strict :

- **Source de vérité** pour l'événement (irréductible, pas calculée).
- **Producteur humain** via une **DataWindow** générée depuis le data contract.
- **Statut « primaire » indépendant du producteur** : machine, capteur, ou humain — peu importe.

## F.2 Stockage : dans la plateforme, pas dans un SI métier séparé

C'est le point qui empêche la réplication.

| Anti-pattern | Pattern correct |
|---|---|
| Les feux sont saisis dans le SI pompiers, copiés en CSV vers l'opérateur national une fois par jour | Les feux sont saisis directement dans la plateforme, le SI pompiers consomme via API |
| L'app de saisie a sa propre base Postgres et ses propres règles | L'app de saisie est une UI sur le data contract, validation centralisée |
| Les corrections sont faites en UPDATE sur la base d'origine | Toute correction est un nouvel événement (lineage `corrects: ...`) |

**Stockage** : table **Iceberg** `obs.feux_foret` (ou similaire), comme toute observation tabulaire. Pas de Postgres applicatif.

## F.3 Schéma type (data contract)

```yaml
id: obs.feux_foret.saisie_terrain
concept: https://w3id.org/nephos/vocab/grandeurs/forest_fire_event
storage: iceberg.obs.feux_foret
schema:
  - feu_id              uuid, PK
  - observed_at         timestamp UTC, mandatory
  - lat                 float, mandatory, range [41.0, 51.5]    # zone nationale
  - lon                 float, mandatory, range [-5.0, 10.0]
  - surface_ha          float, mandatory, range [0, 100000]
  - intensity           enum [low, medium, high, extreme]
  - vegetation_type     concept-ref → vocab/vegetation/*
  - photos              array<urn> → S3 references
  - status              enum [draft, validated, retracted]
  - observer_user_id    fk → users
  - validator_user_id   fk → users, nullable
  - source              enum [terrain, aerial, satellite, citizen]
  - corrects            uuid, nullable, fk → feu_id (chaîne de corrections)
quality_rules:
  - lat/lon dans le polygone périmètre national (PostGIS contains)
  - surface_ha cohérente avec intensity (sanity check)
  - status transitions valides : draft → validated | retracted
  - immutable_after_validation: [observed_at, lat, lon]
write_policy:
  roles_can_write_draft: [observer, dispatcher, citizen-validated]
  roles_can_validate: [supervisor]
  roles_can_retract: [supervisor, original_observer]
audit:
  log_user_agent: true
  log_geolocation_of_input: true
  immutable_log_in_iceberg: true
owner: equipe-securite-civile
```

## F.4 Workflow de saisie

1. **Génération de la DataWindow** : formulaire web/mobile dérivé du data contract (JSON Schema → React JSON Schema Form, ou Pydantic → Streamlit/NiceGUI).
2. **Validation côté client** : règles du contract (range, enum, regex, mandatory).
3. **Validation côté serveur** : re-validation + cohérence cross-field + qualité Soda.
4. **Commit Iceberg** : nouveau snapshot, nouvelle ligne en `obs.feux_foret`.
5. **Lineage tracé** : qui (opérateur), quand (timestamp serveur), depuis où (IP, geolocalisation appareil), avec quelle version de DataWindow et de contract.
6. **État `draft`** par défaut. Transition `validated` par superviseur ou règle automatique (ex. `observer_role >= dispatcher → auto-validate`).
7. **Notifications** : alert contracts métier consomment ces événements (un feu `validated` en zone à risque → alerte sécurité civile).

## F.5 Cas spécifiques

**Correction d'une saisie erronée** :
- Ne **JAMAIS** UPDATE la ligne d'origine.
- Émettre une **nouvelle ligne** avec `corrects: feu_id_X`, `status: validated`, valeurs corrigées.
- La ligne d'origine reste auditable (« qui a saisi quoi initialement »).
- Les consumers regardent la dernière ligne valide de la chaîne.

**Suppression d'une saisie** :
- Pas de DELETE.
- Marquage `status: retracted` + raison + validateur.
- La ligne reste dans Iceberg (audit, reproductibilité).

**Pièces jointes (photos, audio)** :
- Les blobs vivent en **S3** sous URN déterministe : `media://{namespace}/{feu_id}/{filename}`.
- La ligne Iceberg référence l'URN, pas le binaire.
- Lifecycle policy distincte sur les blobs (rétention, anonymisation après N ans).

**Saisie offline (terrain sans réseau)** :
- App mobile avec queue locale chiffrée.
- Sync à la reconnexion.
- Lineage inclut la latence de sync (`observed_at` vs `committed_at` peuvent différer de plusieurs heures).
- Conflits potentiels résolus par règle déclarative (premier arrivé, ou validation superviseur).

## F.6 Trois flux d'entrée, même destination

| Flux | Producteur | Exemple | Connecteur | Aboutissement |
|---|---|---|---|---|
| Ingestion automatique externe | Sources publiques | GFS, IFS, EUMETSAT | HTTP poll, S3 sync, webhook | primaire gouverné |
| Diffusion HPC interne | Calculateurs internes | Sortie HPC modèles régional+global GRIB0 | NFS shared, webhook fin de run | primaire gouverné |
| Saisie humaine | Opérateurs, citoyens encadrés | Feux, dégâts, observations manuelles | DataWindow + API REST | primaire gouverné |

Le SI ne distingue pas ces flux **après** normalisation/validation. Tous sont des primaires gouvernés en Iceberg, tous ont un data contract, tous ont un lineage.

## F.7 Anti-patterns

- ❌ Stocker les saisies dans un Postgres applicatif (« plus pratique pour l'app »). Réplication garantie, single-source brisée.
- ❌ UPDATE direct des saisies pour corriger. Toujours nouvelle ligne avec lineage.
- ❌ Suppression DELETE. Toujours `retracted` avec raison.
- ❌ App de saisie qui définit ses propres règles de validation hors du contract. Dérive garantie.
- ❌ Pas de version du data contract loggée à la saisie : impossible de rejouer une saisie historique.
- ❌ Pas de lineage géo / user-agent : audit sécurité impossible.
- ❌ Pièce jointe stockée en BLOB Iceberg (au lieu de référence URN) : explosion taille table, perf dégradée.
- ❌ Confondre `draft` et `validated` côté consumers : un consumer naïf qui prend le `draft` peut diffuser une fausse alerte.

## F.8 Stack technique

| Fonction | Composant |
|---|---|
| Génération DataWindow | **JSON Schema → react-jsonschema-form** OU **Pydantic → Streamlit / NiceGUI** |
| Backend API saisie | **FastAPI** + Pydantic dérivé du contract |
| Validation qualité | **Soda Core** côté serveur |
| Stockage tabulaire | **Iceberg** + **DuckDB** pour requêtes |
| Stockage médias | **S3 / MinIO** + URN déterministe |
| App mobile offline | React Native ou Flutter, queue **SQLite** locale, sync API |
| Audit / lineage | **OpenMetadata** + audit log immuable Iceberg |

\newpage

# Annexe G — Modification d'une valeur existante par opérateur

## G.1 La règle non négociable

Aucune valeur n'est jamais modifiée. Toute opération sur une valeur existante émet **une nouvelle ligne** dans la table d'événements, avec un statut explicite et un lineage strict vers l'antécédent. La table primaire est **append-only**, l'historique est **inviolable**.

C'est la règle qui permet :

- **Auditabilité** légale (aviation OACI, vigilance autorité locale).
- **Reproductibilité** scientifique (rejouer une étude climatologique avec les données telles qu'elles étaient en 2005).
- **Cascade fiable** : connaître exactement quelles données dépendaient d'une valeur modifiée.

## G.2 Cinq types de modification distincts

Sémantiques différentes, conséquences différentes. Ne **jamais** les confondre.

| Cas | Sémantique | Statut résultant | Exemple |
|---|---|---|---|
| **Correction** | La valeur originale était fausse | `corrected` (nouvelle ligne) + originale → `superseded_by_correction` | Capteur de Brest -50°C, panne, vraie valeur 5°C |
| **Validation expert** | La valeur est conservée mais marquée comme contrôlée par un humain | `validated_expert` (même valeur) | QC manuel d'un radiosondage |
| **Override (forecaster)** | La valeur automatique est correcte mais l'expert assume une modification éditoriale | `forecaster_override` (nouvelle ligne) + originale → `present_with_override` | Prévisionniste force la T H+24 vu un contexte que le modèle ne capte pas |
| **Retrait** | La valeur n'aurait jamais dû exister | `retracted` (originale conservée mais marquée) | Saisie test passée en prod |
| **Flag** | Suspecte, à examiner — pas encore tranchée | `flagged` (originale toujours active) | Outlier détecté automatiquement, en attente de vérif |

**Distinction critique entre correction et override** :

- Une **correction** dit : « la donnée originale était fausse ».
- Un **override** dit : « elle était correcte mais on assume une modification éditoriale ».

Conséquences légales et scientifiques opposées. Mélangées, elles polluent les études climat et exposent juridiquement.

## G.3 Modèle de stockage : event sourcing append-only

```
obs.synop_metar.events                    (Iceberg, append-only)
  - event_id           uuid PK
  - observation_id     uuid (clé logique partagée par toutes les versions)
  - version            int (1, 2, 3, ...)
  - event_type         enum [original, corrected, validated_expert,
                              forecaster_override, retracted, flagged]
  - parent_event_id    uuid, nullable (pointe vers la version précédente)
  - value              ...
  - status             enum [draft, validated, published, superseded,
                              superseded_by_correction, retracted,
                              present_with_override]
  - reason             text, mandatory pour event_type ≠ original
  - operator_user_id   fk → users
  - operator_role      enum [observer, supervisor, forecaster, qc_expert]
  - validated_by       fk → users, nullable (validation 2-yeux)
  - validated_at       timestamp
  - committed_at       timestamp UTC
  - effective_at       timestamp UTC (instant à partir duquel la modification s'applique)
```

Plus une **vue / cache** pour les consumers nominaux :

```
obs.synop_metar.current                   (vue Iceberg ou table Postgres)
  - observation_id PK
  - active_event_id      → la dernière ligne validée et non superseded
  - active_value
  - active_status
```

Les consumers métier lisent **`current`** par défaut. Audits, études, replays lisent **`events`**.

## G.4 Workflow type pour une modification

1. **L'opérateur identifie** une valeur à modifier (correction ou override).
2. **Justification obligatoire** : un texte non vide expliquant pourquoi (`reason: "capteur en panne, mesure 5°C cohérente avec stations voisines"`). Bloquant en validation.
3. **Émission d'un event** avec parent pointant vers l'event original. Statut `draft`.
4. **Validation 2-yeux** si la criticité l'exige (METAR aviation, vigilance autorité locale) : un superviseur signe, statut → `validated`.
5. **Publication** : statut → `published`, le `current` est mis à jour pour pointer vers ce nouvel event.
6. **Cascade downstream** : tous les secondaires / produits / alertes qui ont consommé l'ancienne valeur sont automatiquement invalidés et rejoués via le mode pivot de l'orchestrateur.
7. **Notification consumers externes** : event `data_correction` émis sur le bus interne et republié vers les consumers tiers (API, webhook, AMSS aviation).
8. **Audit immuable** : chaîne `event_v1 (original) → event_v2 (correction) → event_v3 (correction de correction)` consultable à perpétuité.

## G.5 Cascade : la conséquence souvent oubliée

Si une primaire est corrigée à T+2h, les downstream dérivés à T+1h **doivent être rejoués** :

```
obs.synop.lfpg.t@13:00 (v1 = -50°C original) ───┐
                                                 │ event corrected
                                                 ▼
obs.synop.lfpg.t@13:00 (v2 = +5°C corrected) ───┐
                                                 │
                                                 ▼ invalide downstream
secondary.zone.t.gridded@13:00     → rebuilt   │
product.maps.t.zone@13:00          → rebuilt   │
alert.canicule.eval@13:00            → re-evaluated, peut être annulée
metar.lfpg@13:00                     → COR émis vers AMSS aviation
```

**Sans cette cascade, la correction est cosmétique** : la primaire est corrigée, les produits restent faux. Anti-pattern fréquent.

## G.6 Diffusion publique d'une correction

Si la valeur fausse a été **diffusée** (METAR officiel, vigilance, API tiers), corriger en interne ne suffit pas :

| Canal | Mécanisme de correction publique |
|---|---|
| METAR aviation | Émission d'un METAR `COR` (correction) conforme OACI Annexe 3 |
| Vigilance autorité locale | Bulletin de correction explicite, traçabilité légale |
| API REST / GraphQL | Header `X-Data-Correction-Of: <event_id>` + content updated |
| Webhook abonné | Push d'un event `data.correction` sur l'abonnement |
| Diffusion publique web | Marqueur visible (« donnée corrigée le ... ») + lien vers historique |

**Le silence n'est pas une option** : un consumer qui a reçu la valeur fausse continuera à la diffuser ou à l'utiliser tant qu'on ne lui dit pas qu'elle est corrigée.

## G.7 Statuts possibles d'une valeur (récapitulatif)

| Statut | Signification | Visible par les consumers métier ? |
|---|---|---|
| `draft` | Saisi / produit, pas encore validé | Non (sauf opt-in explicite) |
| `validated` | Validé en interne | Oui |
| `published` | Diffusé externalement | Oui (tous canaux) |
| `flagged` | Suspecte, à examiner | Oui avec marqueur de doute |
| `superseded` | Remplacée par version plus récente (mise à jour normale) | Non par défaut |
| `superseded_by_correction` | Remplacée parce que **fausse** | Non par défaut, accessible avec marqueur |
| `retracted` | Retirée (n'aurait jamais dû exister) | Non |
| `present_with_override` | Conservée comme antécédent éditorial | Non par défaut |
| `validated_expert` | Conservée et explicitement validée par un humain | Oui, avec marqueur de validation |

## G.8 Anti-patterns à bannir absolument

- ❌ **UPDATE direct sur la table primaire**. Brise toute auditabilité.
- ❌ **DELETE d'une valeur originale**, même fausse. La trace doit subsister.
- ❌ **Correction sans `reason` justifié**. Bloquant en validation, jamais d'exception.
- ❌ **Pas de validation 2-yeux** pour les modifications critiques (METAR, vigilance, sécurité civile).
- ❌ **Pas de cascade downstream** : correction cosmétique, produits encore faux.
- ❌ **Confondre correction et override** : conséquences légales opposées.
- ❌ **Modification après publication officielle sans diffusion d'event de correction**. Le consumer externe ignore qu'on a corrigé.
- ❌ **Modification effectuée hors plateforme** (« on me l'a demandé en urgence, je l'ai fait directement en SQL »). Trace perdue, gouvernance brisée. Bloquer techniquement (révoquer les droits SQL).
- ❌ **Pas de limite temporelle** ou règle explicite : permet une correction d'une donnée de 1995 sans gouvernance, polluant les études déjà publiées.
- ❌ **Statuts implicites ou non documentés** : si l'opérateur ne sait pas si sa modification est une correction ou un override, le code ne peut pas distinguer non plus.

## G.9 Stack technique

| Fonction | Composant |
|---|---|
| Append-only | **Iceberg** (snapshots, append-only par construction) |
| Vue `current` performante | **Postgres** matérialisé (refresh sur event publié) ou **vue Iceberg** lue via DuckDB |
| Validation 2-yeux | Workflow dans le backend FastAPI + signature stockée en event |
| Cascade downstream | **Dagster auto-materialize** ou **Kestra trigger custom** propage l'invalidation |
| Diffusion correction publique | Service `notifier` (cf. annexe A) + connecteurs canaux (METAR-COR, webhook, etc.) |
| Audit consultatif | UI dédiée lecture `events` (tableau filtrable, timeline, diff valeur) |
| Bloquer accès SQL direct | Iceberg seul writer, droits Postgres lecture seule pour humains, RBAC strict |

## G.10 Insertion dans la roadmap

| Phase | Livrable |
|---|---|
| **POC** | Modèle event-sourcing sur 1 dataset (saisie feux), workflow correction simple, cascade démontrée sur 1 secondaire |
| **Pilote** | Workflow validation 2-yeux, audit UI, intégration sur tous les datasets pilote |
| **Industrialisation** | Diffusion publique des corrections (METAR-COR, webhook autorités locales), conformité OACI |
| **Prod** | SLA garantis sur cascade (rejeu < 5 min), audit temps réel, intégration avec systèmes métier externes |

\newpage

# Annexe H — Politiques d'accès et classifications (aviation, marine, militaire, embargos)

## H.1 Le problème

Toutes les données ne sont **pas accessibles à tous**, et la plateforme doit l'imposer **par construction**, pas par discipline.

Sources de restrictions concrètes :

| Domaine | Source de restriction | Exemple |
|---|---|---|
| Aviation | OACI Annexe 3, contrats commerciaux | METAR/TAF/SIGMET à clients certifiés ; AMSS aux compagnies abonnées |
| Marine | SHOM, contrats opérateurs maritimes | Routage commercial, prévisions hauturières souscripteurs |
| Défense / Militaire | IGI 1300, classification *Diffusion Restreinte* à *Secret Défense* | Prévisions zone d'opération, capteurs militaires, données OTAN |
| Sécurité civile | Embargo opérationnel | Vigilance avant publication officielle |
| Capteurs privés | Contrat d'exclusivité | Stations privées (énergie, agro) payées pour exclusivité 24h |
| Échange international | WMO Resolution 40 / 60 | Données amont WMO redistribuées sous licence |
| RGPD | Règlement européen | Saisie citoyenne, photos avec visages/plaques, géoloc opérateurs |
| Embargo temporel | Politique éditoriale | ECMWF Open après 6h, données commerciales avant 24h |

L'erreur classique : **traiter les autorisations comme du middleware applicatif** posé devant la plateforme. L'autorisation appartient à la plateforme elle-même, au niveau du catalogue et du moteur de lecture.

## H.2 Quatre niveaux de classification

| Niveau | Public visé | Stockage | Authentification | Audit |
|---|---|---|---|---|
| **L0 — Public** | Open data, citoyens, recherche académique ouverte | Plateforme principale, lecture libre | Anonyme ou comptes simples | Métriques agrégées |
| **L1 — Restreint professionnel** | Clients certifiés (aviation, marine, agro), partenaires contractualisés | Plateforme principale + ABAC | Authentifié + rôle/organisation | Log par consumer + dataset |
| **L2 — Confidentiel** | Personnel habilité interne, défense intérieure non classifiée, capteurs privés sous contrat | Plateforme principale + isolation tenant + chiffrement at-rest renforcé | Authentifié + habilitation explicite + 2FA | Log nominatif + alerting accès anormal |
| **L3 — Classifié défense** | Habilités défense (DR, CD, SD) | **Architecture séparée**, **air gap** ou enclave physique distincte | Habilitation officielle + multi-facteurs forts | Audit conforme IGI 1300 |

**Règle structurelle** : L0 → L2 vivent sur la même plateforme avec ABAC. **L3 est sur une plateforme jumelle isolée physiquement** — partage de code et de modèles, pas de données. Mélanger L3 avec le reste expose à un déclassement de classification de toute la plateforme.

## H.3 Modèle d'autorisation : ABAC, pas RBAC seul

Le RBAC simple (« rôle aviation peut tout voir aviation ») est insuffisant. Il faut **ABAC** parce que les règles dépendent de :

- **Attributs du consumer** : rôle, organisation, certification (numéro OACI, immatriculation marine), niveau d'habilitation, géolocalisation IP, contrat actif.
- **Attributs de la donnée** : classification, source, zone géographique, embargo temporel, owner.
- **Contexte** : heure (embargo), zone d'urgence active (déclassification temporaire vigilance), durée d'accès demandée.

Exemple de règle déclarative (OPA / Rego) :

```rego
package nephos.access

default allow = false

# L0 : public, toujours ok
allow {
  data_classification == "L0"
}

# L1 aviation : compagnie certifiée OACI active
allow {
  data_classification == "L1"
  data_domain == "aviation"
  consumer.certified_oaci == true
  consumer.contract_active == true
}

# Embargo ECMWF : public après 6h
allow {
  data_classification == "L1"
  data_source == "ecmwf-open"
  time.since(data.published_at) > "6h"
}

# Capteur privé exclusif 24h
allow {
  data_classification == "L2"
  data_source == "private-sensor"
  consumer.org_id == data.exclusive_owner_org_id
  time.since(data.published_at) < "24h"
}
allow {
  data_classification == "L2"
  data_source == "private-sensor"
  time.since(data.published_at) >= "24h"
  consumer.contract_active == true
}
```

Les règles vivent en Git, versionnées, reviewées comme du code.

## H.4 Le contract d'accès

Chaque dataset a, en plus du data contract technique, un **access contract** :

```yaml
id: nwp.arome.publish.0p025deg
classification: L1
domain: aviation
licence: WMO-RES40-restricted
embargo:
  public_after: 24h
allowed_audiences:
  - role: ops-prevention-mf
  - role: aviation-certified
    organization_filter: "aoc_certified == true"
  - role: research-academic
    requires_research_agreement: true
denied_audiences:
  - role: anonymous (sauf après public_after)
data_residency: national_territory
encryption_at_rest: AES-256-GCM
encryption_in_transit: TLS 1.3
audit_level: nominal_with_dataset_dimensions
retention_audit: 5y
owner: equipe-prevision-aero
legal_contact: legal@meteo.gouv.fr
```

Sans access contract, **pas de publication** au-delà de L0.

## H.5 Mécanismes techniques

| Besoin | Mécanisme |
|---|---|
| Filtrage **row-level** (un consumer voit certaines lignes) | Iceberg row-level filters via Lakekeeper + ABAC OPA |
| Filtrage **column-level** (masquage colonnes sensibles) | Iceberg column projection policy (cf. observation marine où la position du capteur est masquée) |
| Filtrage **géographique** | Politique ABAC sur attribut `bbox` ou `geom` |
| **Embargo temporel** | Règle ABAC sur `time.since(published_at)` |
| **Masquage RGPD** | Anonymisation à la lecture (hash visages, généralisation lat/lon) |
| **Chiffrement at-rest** différencié | Buckets MinIO/S3 avec clés KMS distinctes par niveau |
| **Chiffrement in-transit** | TLS 1.3 imposé, mTLS pour services internes |
| **Audit d'accès** | Logs structurés Lakekeeper + Iceberg, ingérés en Iceberg `platform.access_log` |
| **Détection accès anormal** | Alert contract sur `platform.access_log` |

## H.6 L'isolation L3 (militaire) est physique, pas logique

Pour les données classifiées défense, **ne pas tenter le multi-tenant logique sur la même plateforme**. Risques :

- Accident de configuration : politique ABAC mal écrite expose des données SD aux non-habilités. Sur du SD, c'est un incident d'État.
- Risque de compromission : un ver / une vulnérabilité OS sur la plateforme principale propage potentiellement.
- Conformité IGI 1300 : exige généralement un cloisonnement physique pour CD/SD.

```
┌─────────────────────────────┐    ┌──────────────────────────────┐
│  Plateforme principale      │    │  Plateforme défense isolée   │
│  (L0 / L1 / L2)             │    │  (L3 : DR, CD, SD)           │
│                             │    │                              │
│  - MinIO/Ceph               │    │  - Stockage durci, séparé    │
│  - Iceberg + Lakekeeper     │    │  - Mêmes briques OSS         │
│  - Glossaire référentiel    │    │  - Déploiement indépendant   │
│  - Code orchestration       │    │  - Réseau séparé / air-gap   │
└─────────────────────────────┘    └──────────────────────────────┘
              │                                    │
              │  Sync uni-directionnel L0/L1 → L3  │
              │  (donnée publique enrichit défense)│
              └────────────────────────────────────┘
                          │
                          ▼  jamais l'inverse :
                          la donnée L3 ne sort pas
```

Le code et les modèles peuvent être identiques entre les deux plateformes, **les données ne se mélangent pas**.

## H.7 Cas particuliers

**Vigilance et embargo opérationnel** : une vigilance niveau orange en élaboration est L2 jusqu'à publication officielle, puis bascule L1 à publication. L'event de levée d'embargo est lui-même une donnée gouvernée.

**WMO Resolution 40 / 60** : licences imbriquées (essentielles libres ; additionnelles avec restrictions selon pays émetteur). L'access contract porte explicitement la licence amont et la propage aux consumers.

**Capteurs privés et exclusivité commerciale** : `embargo.exclusive_to_org_id` + `embargo_duration: 24h`. Au-delà, bascule L1 ou L0 selon contrat. Audit nominatif des accès exclusifs (preuve de respect contractuel).

**RGPD sur saisie citoyenne et opérateur** : photos avec visages, plaques, géoloc. Anonymisation à la lecture (hash, blur, généralisation lat/lon à 1 km). Droit à l'effacement : `retracted_for_rgpd`, masquage dans toutes les vues consumers, conservation dans audit.

**Recherche académique** : `research_agreement` formel → rôle dédié → accès L1/L2 sur usage déclaré non-commercial. Audit nominatif renforcé. Sandbox isolée (pas de re-publication possible).

## H.8 Anti-patterns

- ❌ Autorisation gérée par chaque application cliente : single-source brisée.
- ❌ Mélanger L3 et L0/L1/L2 sur la même plateforme physique.
- ❌ Politique ABAC dans le code au lieu de Git versionné.
- ❌ Audit d'accès stocké dans Grafana / fichier de log uniquement (doit vivre en Iceberg gouverné).
- ❌ Pas de DPO ni de juriste dans les owners de contracts sensibles.
- ❌ Embargo géré par cron : l'embargo est une règle ABAC sur attribut temporel.
- ❌ Une seule règle catch-all : on rate les nuances (embargo, exclusivité, recherche).
- ❌ Habilitation déclarative sans vérification périodique : re-validation annuelle minimale.
- ❌ Pas de chiffrement différencié par classification.
- ❌ Logs d'audit conservés moins longtemps que la donnée elle-même.
- ❌ Fuites par jointures : un consumer L0 qui reconstitue L1 par recoupement. Tester explicitement.

## H.9 Stack technique

| Fonction | Composant |
|---|---|
| Moteur de politiques | **Open Policy Agent (OPA)** ou **Cedar** (AWS, OSS) |
| Application policies sur Iceberg | **Lakekeeper** + plugin OPA, ou **Apache Polaris** + **Apache Ranger** |
| Authentification | **Keycloak** (OSS, IDP standard SAML/OIDC) ou **Authentik** |
| Autorisation niveau service | **OPA sidecar** par service FastAPI / Streamlit |
| Audit d'accès gouverné | Logs structurés → Iceberg `platform.access_log` |
| Détection accès anormal | Alert contracts sur `access_log` (cf. annexe A) |
| Chiffrement at-rest | **MinIO/Ceph + KMS Vault** ou **PKCS#11 HSM** pour L2+ |
| Chiffrement in-transit | TLS 1.3 systématique, mTLS interne |
| Anonymisation RGPD | Modules Python dédiés (CV pour visages, généralisation géoloc) |
| Plateforme jumelle L3 | Même stack OSS, déploiement isolé, équipe ops dédiée habilitée |

## H.10 Métriques exposées

- **Taux d'accès refusé** par dataset, consumer, règle (alerte si pic).
- **Distribution des accès par classification**.
- **Couverture RGPD** : datasets avec données personnelles dont l'anonymisation est testée.
- **Durée moyenne d'habilitation** (alerte si habilitations expirées non révoquées).
- **Taux de re-validation annuelle**.
- **Temps de réponse aux demandes RGPD**.

## H.11 Insertion dans la roadmap

| Phase | Livrable accès |
|---|---|
| **POC** | OPA + Lakekeeper basique, classification L0/L1 sur 2 datasets, audit log Iceberg minimal |
| **Pilote** | L2 avec chiffrement différencié, audit complet, intégration Keycloak, tests de fuites |
| **Industrialisation** | Embargo gouverné, capteurs privés exclusivité, RGPD opérationnel, DPO intégré au workflow |
| **Prod** | Plateforme jumelle L3 si l'opérateur national valide ce périmètre, conformité IGI 1300 documentée, re-validation annuelle automatisée |

\newpage

# Synthèse — familles d'événements et flux gouvernés

Le document couvre quatre familles d'événements gouvernés et trois flux d'entrée, tous unifiés sous le même modèle.

## Familles d'événements gouvernés

| Famille | Source | Public | Annexe |
|---|---|---|---|
| **Données** (primaires, secondaires, produits) | Plateforme principale | Consumers métier | Corps |
| **Alertes métier** (dépassement seuil) | Alert contracts + moteur d'évaluation | Vigilance, autorités locales, aviation | A |
| **Fraîcheur** (retard, indisponibilité) | Freshness policies + état gouverné | Ops, dataops, SLA reporting | B |
| **Complétude** (runs partiels, dégradés) | Manifestes de complétude + lineage column-level | Ops, métiers consumers | C |

## Cycle de vie, flux d'entrée, modifications, accès

| Couche | Description | Annexe |
|---|---|---|
| **Tiering hot / warm / cold / frozen** | Pilotage par usage observé, pas par âge brut | D |
| **Pré-traitement raw → bronze → primaire** | Identique pour sources externes et internes (HPC) | E |
| **Saisie opérateur** | DataWindow générée depuis contract, primaire gouvernée comme toute observation | F |
| **Modification de valeur existante** | Event sourcing append-only, statuts explicites, cascade obligatoire | G |
| **Politiques d'accès et classifications** | L0-L3, ABAC, isolation physique L3 défense, embargos, RGPD | H |

## Le modèle commun

Tous partagent **le même modèle architectural** :

- **Événements immuables** en Iceberg (append-only, snapshots).
- **État courant** en Postgres (mutable, requêtable rapidement).
- **Gouvernance** par contract YAML versionné en Git.
- **Lineage** tracé de bout en bout (column-level dès que possible).
- **Single source of truth** à 3 niveaux (notions, méta, données).
- **Pas de réplication non déclarée**.

C'est cette **uniformité** qui rend la plateforme cohérente, auditable et scalable au pétaoctet — par construction, pas par discipline.

---

*Document évolutif. Toute critique structurante est attendue avant rédaction des ADR détaillés.*
