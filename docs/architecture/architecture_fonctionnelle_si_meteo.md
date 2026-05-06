---
title: "Architecture fonctionnelle — Plateforme SI Météo"
subtitle: "Vue par capacités, hypothèses à valider, business case, scénarios, transition"
author: "Architecture senior"
date: "2026-05-06"
version: "v2 — révisée après auto-critique"
lang: fr
---

# Avertissement de posture

Cette version v2 intègre une auto-critique de la v1. Limites du document **assumées et signalées** :

- **Le diagnostic de l'existant est posé en hypothèses à valider en audit terrain**, pas en constats. Les chiffres avancés sont des ordres de grandeur conservateurs et explicités.
- **Le document n'a pas encore été relu par un juriste** sur les sujets WMO Resolution 40, IGI 1300, OACI Annexe 3, RGPD. Toutes les mentions sont marquées comme nécessitant relecture experte.
- **Les choix techniques sont volontairement absents** ; ils sont traités dans le document `architecture_si_meteo.docx`. Toute mention technique restante dans ce document est un défaut de séparation à corriger.
- **Le business case est posé en ordres de grandeur**, à préciser avec données réelles dans les premiers ateliers de cadrage.

Ce document **n'est pas une décision** ; il est un cadre de discussion structuré qui **provoque** les décisions.

\newpage

# 0. Synthèse exécutive (1 page)

**Problème.** Les opérateurs météorologiques nationaux ont accumulé un patrimoine de données fragmenté : copies multiples, gouvernance implicite, sémantique non unifiée, capacité limitée à introduire de nouveaux usages (ML, services climat, partenariats). Ces patterns sont publiquement reconnus chez plusieurs acteurs comparables (NOAA, DWD, MetOffice). À volumétrie croissante (de 5 à 30 Po actifs), la dette devient bloquante.

**Hypothèse de rupture.** Une plateforme structurée par **trois principes d'unicité** (notions, méta-données, données) permet de réduire les copies, fluidifier la découvrabilité, garantir la conformité par construction, et libérer la capacité d'innovation. Ce n'est pas une promesse technologique ; c'est une discipline architecturale qui exige adoption et sponsorship.

**Périmètre cible.** Plateforme cible couvrant les douze capacités fonctionnelles d'un SI météo (acquérir, normaliser, cataloguer, stocker, calculer, présenter, diffuser, saisir, surveiller, habiliter, gouverner, évoluer), sur un périmètre Po-scale, avec interopérabilité ouverte et compatibilité avec les standards WMO / OACI / RGPD.

**Effort estimé (à confirmer).** Phase 1 démonstrateur 6 semaines, 2 ETP. Phase 2 pilote 9-12 mois, 3-4 ETP. Phase 3 industrialisation 18-24 mois, 6-8 ETP. Plateforme cible exploitable à 3 ans avec sponsorship continu.

**Coût estimé (ordres de grandeur, à préciser).** Investissement RH 3 ans : 4-8 M€ selon ampleur. Infra cible : 0,5 à 2 M€/an selon souveraineté retenue. Coût du non-changement (extrapolation conservative du surcoût stockage actuel à volumétrie projetée) : potentiellement 5-15 M€/an d'ici 5 ans, à mesurer en audit.

**Décision attendue.** Sponsor exécutif engagé, périmètre cible (Météo-France seul / consortium / produit), budget pluri-annuel, équipe dédiée, mandat de gouvernance transverse. Sans ces quatre, ce document reste un exercice intellectuel.

**Risque principal.** Pas la technologie. C'est l'adoption par les équipes métier en place et la persistance du sponsorship sur 3 ans, à travers les changements de direction.

\newpage

# 1. Préambule

## 1.1 Objet et public

Document de cadrage stratégique pour une plateforme SI météo cible. Décrit ce que le système doit *faire*, par capacités métier, indépendamment des choix techniques.

| Public | Usage du document |
|---|---|
| Sponsor exécutif | Synthèse exécutive (section 0), business case (section 8), risques (section 14) |
| DSI métier | Sections 2, 3, 4, 7, 12 — état perçu, scénarios, cible, transition |
| Architectes solution | Sections 6, 7, 9 — capacités, comparatifs, make vs buy |
| Owners de domaine | Sections 5, 7, 10 — scénarios concrets, capacités détaillées, acteurs |
| Équipes opérationnelles | Sections 11, 12 — processus, transition |

Pour les choix techniques (composants OSS, stack, déploiement), se reporter au document `architecture_si_meteo.docx`.

## 1.2 Méthode

- Le document **part d'hypothèses sur l'existant**, à valider par audit terrain. Aucun chiffre n'est posé sans qualification de sa source.
- Le document **dialogue avec les contre-arguments** légitimes (résistances opérationnelles, contraintes capital, conformité) avant de poser la cible.
- Le découpage par capacités s'inspire du framework **DAMA-DMBOK** (référence du data management), avec adaptation au contexte météo.
- Le document **assume ne pas connaître précisément** Météo-France ou tout autre opérateur : c'est un cadre **générique** à instancier après audit.

\newpage

# 2. Hypothèses sur l'existant (à valider en audit)

## 2.1 Avertissement

Cette section formule des **hypothèses fondées sur des patterns publiquement décrits chez plusieurs opérateurs météo nationaux**. Elles ne constituent pas un audit de Météo-France. **Chaque hypothèse doit être confirmée ou infirmée** par mesure et entretiens avant tout investissement majeur.

## 2.2 Liste des hypothèses

| H | Hypothèse | Indicateur à mesurer | Source publique du pattern |
|---|---|---|---|
| H1 | Acquisition fragmentée : plusieurs équipes télé-chargent indépendamment les mêmes sources externes | Nombre de connecteurs par source amont, volume cumulé téléchargé / volume utile | Patterns observés chez NOAA, DWD avant leur Big Data Programs |
| H2 | Réplication massive du stockage avec multiplicateur supérieur à 2 | Taux de duplication mesuré sur un échantillon de datasets représentatifs | Constat partagé en plusieurs retours d'expérience opérateurs |
| H3 | Gouvernance par tradition orale plutôt que par contracts formels | Nombre de datasets disposant d'un schéma documenté + owner identifié + SLA défini | Pattern industriel large (au-delà de la météo) |
| H4 | Sémantique fragmentée : pas d'utilisation systématique des CF Standard Names comme clé pivot interne | Couverture CF dans les catalogues internes vs publication open data | Cas spécifique au domaine météo |
| H5 | Calculs dérivés (CAPE, indices, agrégations) non versionnés centralement | Existence d'un dépôt unique de recettes, taux de réutilisation cross-équipes | Pattern courant en data science non gouvernée |
| H6 | Saisie d'observations terrain hébergée dans des SI de consommateurs externes | Latence et perte d'information sur la chaîne saisie → utilisable | Cas spécifique météo (sécurité civile, services régaliens) |
| H7 | Modifications de données par UPDATE direct, sans audit ni cascade | Existence de tables append-only avec event sourcing sur les datasets critiques | Pattern industriel courant |
| H8 | Habilitations gérées par chaque application, comptes zombies | Nombre de comptes uniques par utilisateur, taux de re-validation annuelle | Pattern industriel courant |
| H9 | Cycle de vie ad-hoc, pas de tiering automatique | Distribution du stockage par âge des données vs accès observés | Pattern industriel courant |
| H10 | Surveillance par équipe, pas transverse | Existence d'un dashboard SLA cross-domaine | Pattern industriel courant |
| H11 | Interfaçage international (WMO Resolution 40 / 60) tracé manuellement | Audit légal des flux entrants/sortants, traçabilité des licences amont | Cas spécifique météo |
| H12 | Capacité limitée à introduire de nouveaux services rapidement | Time-to-market d'un nouveau cas d'usage métier (semaines vs trimestres) | Pattern industriel courant |

## 2.3 Démarche d'audit recommandée

Avant tout engagement majeur :

- **Audit quantitatif** sur 3-5 datasets représentatifs : volumes, copies, latences, accès, coûts.
- **Entretiens semi-directifs** avec 5-10 owners de domaine : pratiques actuelles, frictions, attentes.
- **Revue documentaire** : data contracts existants (s'il y en a), wikis, lookups, dictionnaires.
- **Cartographie SI** : flux de données entre systèmes, points de duplication.

Durée typique : 6-8 semaines, 2 personnes. Coût : équivalent à 2 % du budget projet pluri-annuel. Sans cet audit, les hypothèses ci-dessus pilotent les décisions à l'aveugle.

\newpage

# 3. Pourquoi l'existant existe : reconnaître les rationalités du présent

Avant de proposer une cible, prendre au sérieux pourquoi l'existant a été construit ainsi. Une cible qui méprise les rationalités du présent **échoue à l'adoption**. Quelques raisons légitimes typiques :

## 3.1 Continuité de service

L'opérateur produit des bulletins H24, des prévisions aéronautiques engageantes juridiquement, des vigilances de sécurité civile. **On ne refactorise pas un SI critique en production sans plan de continuité.** Toute migration doit prouver qu'elle ne dégrade pas la disponibilité.

## 3.2 Spécialisation des équipes

Les équipes prévi, climat, aéro, recherche ont chacune des cycles, des outils et des cultures spécifiques. La fragmentation actuelle reflète une **autonomie pragmatique** qui a permis à chacune d'avancer à son rythme. Une plateforme transverse exige un **changement organisationnel**, pas seulement technique.

## 3.3 Investissements capital lock-in

Les NAS, GPFS HPC, contrats licences sont amortis sur plusieurs années. Une migration prématurée détruit du capital. La cible doit composer avec **les amortissements en cours**, ne pas les ignorer.

## 3.4 Conformité réglementaire en place

Les chaînes existantes sont **conformes** (OACI, WMO, RGPD, IGI 1300 le cas échéant) parce qu'elles ont été certifiées dans leur état actuel. Migrer signifie **re-certifier**, ce qui prend du temps et de l'argent. Le coût de re-certification est rarement budgété au démarrage des projets cibles.

## 3.5 Connaissance tacite

La documentation incomplète n'est pas (toujours) de l'incurie : c'est aussi de la **connaissance tacite** détenue par des experts. La migration risque d'**effacer cette connaissance** si elle ne traduit pas les pratiques implicites en data contracts explicites avec ces experts.

## 3.6 Dépendances externes asymétriques

Les sources amont (NOAA, ECMWF, EUMETSAT, capteurs privés) imposent leurs formats, leurs licences, leurs SLA. L'opérateur **subit** ces contraintes plus qu'il ne les choisit. Une cible idéale doit composer avec cette asymétrie, pas l'ignorer.

## 3.7 Conséquence pour la cible

La cible n'est légitime que si elle :

- **Coexiste** avec le legacy pendant la transition (pas de big-bang).
- **Reconnaît** la valeur des autonomies d'équipe (gouvernance fédérée plutôt qu'imposée).
- **Préserve** les investissements capital amortis (réutilisation des stockages existants quand possible).
- **Maintient** la conformité (re-certification planifiée et financée).
- **Capte** la connaissance tacite (data contracts co-rédigés avec les owners actuels).
- **Adapte** sa cadence aux contraintes externes (les sources amont ne pivotent pas pour nous).

Sans cette reconnaissance, la cible est une posture, pas un programme.

\newpage

# 4. Apprentissages externes : ne pas réinventer

Plusieurs initiatives publiques offrent un retour d'expérience exploitable. À analyser avant de poser la cible Météo-France.

## 4.1 ECMWF MARS (Meteorological Archival and Retrieval System)

- **30 ans de service**, environ 30 Po archivés.
- **Catalog + tape archive + protocole MARS** propriétaire, accès programmatique stable.
- **Réussite** : longévité, scaling continu, fiabilité opérationnelle.
- **Limites** : système propriétaire, vocabulaire MARS spécifique (non SKOS), évolution lente, latence retrieval.
- **À retenir** : la stabilité du protocole d'accès dans la durée prime sur l'élégance du design. Un catalogue simple bien tenu vaut mieux qu'un catalogue ambitieux mal tenu.

## 4.2 NOAA Big Data Project (BDP)

- **Ouverture massive** des datasets météo NOAA sur AWS, GCP, Azure.
- Modèle **public-private partnership** : les clouds hébergent gratuitement, NOAA gagne en accessibilité, le tiers économique se développe.
- **Réussite** : adoption tiers (services climat, aviation, recherche, ML) en explosion.
- **Limites** : c'est une vitrine d'open data, pas une refonte de la plateforme interne NOAA. La gouvernance interne reste un autre sujet.
- **À retenir** : la diffusion ouverte crée une demande de **fournisseur** unifié interne. C'est un argument fort pour la cible.

## 4.3 EUMETSAT Data Store

- **Refonte récente** (catalogue STAC, accès API normalisé).
- Périmètre **satellite** européen.
- **Réussite** : adoption par les services climat (Copernicus), interopérabilité.
- **Limites** : périmètre réduit (satellite uniquement), pas de couche calcul intégrée.
- **À retenir** : le standard **STAC** (SpatioTemporal Asset Catalog) est devenu un standard de fait pour les catalogues spatialisés ; à étudier comme complément ou alternative à un catalogue Iceberg pur.

## 4.4 Pangeo

- **Communauté scientifique open source** (xarray + Zarr + Dask + Jupyter).
- Adopté par CNRS, ECMWF (partiellement), NASA (partiellement).
- **Réussite** : standard de fait pour le calcul scientifique gridded.
- **Limites** : ce n'est pas un produit clés-en-main ; il faut intégrer.
- **À retenir** : composer avec les standards Pangeo plutôt que les ignorer ; ce sont les utilisateurs scientifiques de demain.

## 4.5 Copernicus Climate Data Store / Atmosphere Data Store

- **ECMWF**, accès public, catalogue + API + Toolbox de calcul à la volée.
- **Réussite** : adoption métier large (climat services, agro, énergie, médias).
- **Limites** : compute limité par utilisateur, files d'attente.
- **À retenir** : le **modèle d'API + compute partagé** est une attente forte des consumers métier. À intégrer dans la cible.

## 4.6 Initiatives au-delà de la météo

- **AWS Open Data Program** : 100+ datasets ouverts, modèle de catalogue distribué.
- **Microsoft Planetary Computer** : catalogue STAC + compute Dask managé pour la science environnementale. À comparer.
- **Banque mondiale / FAO / EU Data Spaces** : initiatives de plateformes thématiques avec gouvernance.

## 4.7 Synthèse des apprentissages

| Apprentissage | Conséquence pour la cible |
|---|---|
| La stabilité d'accès dans la durée prime sur l'élégance | Ne pas multiplier les API ; garantir compatibilité ascendante |
| L'ouverture (open data) crée la demande d'un fournisseur unifié | Construire la cible avec l'ouverture comme cas d'usage de premier rang |
| STAC est un standard de fait pour les catalogues spatialisés | Le considérer comme complément ou format d'export du catalogue technique |
| Pangeo est l'écosystème scientifique de référence | Aligner les formats (Zarr) et l'API de lecture (xarray) avec Pangeo |
| Le modèle API + compute partagé est une attente | Intégrer un compute service dès la phase pilote |
| Plusieurs réussites n'ont pas refondu leur back-office, juste ouvert leur front | Possibilité de stratégie « front avant back » à évaluer |

\newpage

# 5. Scénarios métier (vue concrète de la cible)

La cible se mesure à ce qu'elle change pour les acteurs réels. Sept scénarios représentatifs.

## 5.1 Sophie, prévisionniste aéronautique

**Aujourd'hui.** Sophie ouvre 4 outils différents, joint mentalement leurs sorties, vérifie sur 2 sites externes la cohérence de la donnée. Briefing matinal préparé en 90 minutes.

**Avec la plateforme.** Sophie interroge `nephos resolve T@FL60 paris 06:00` ou son équivalent UI. En 2 secondes, elle obtient la valeur consolidée multi-modèles avec sa qualité, sa fraîcheur, ses sources, et la cascade de dépendances. Briefing préparé en 30 minutes. Le temps gagné sert à enrichir l'analyse, pas à compiler.

**Valeur** : gain de productivité, qualité d'analyse améliorée, traçabilité du briefing.

## 5.2 Marc, chef d'équipe vigilance météorologique

**Aujourd'hui.** Marc évalue les seuils manuellement à partir de cartes, croise sur les écrans, juge d'une éventuelle vigilance. La décision repose sur son expertise, peu documentée pour ses successeurs.

**Avec la plateforme.** Les seuils sont dans des **alert contracts** versionnés en Git. La machine évalue en permanence. Marc reçoit des **propositions de vigilance** ré-évaluées, motivées, traçables. Il décide ; sa décision est tracée. Sa connaissance tacite s'inscrit progressivement dans les contracts.

**Valeur** : continuité de service à travers les départs, auditabilité, ré-évaluation rapide en cas de correction de donnée.

## 5.3 Léa, chercheuse climat

**Aujourd'hui.** Léa veut reproduire une étude publiée en 2018. Le notebook a disparu avec son auteur. Les données ont été ré-archivées dans un autre format. Reproduction abandonnée.

**Avec la plateforme.** Léa interroge le catalogue : la recette de calcul est en Git, taggée v2.3.1. Les snapshots Iceberg de 2018 sont accessibles via time-travel. Reproduction en 1 journée. L'étude vaut maintenant ce qu'elle prétend valoir.

**Valeur** : reproductibilité scientifique, valeur d'archive renforcée, légitimité méthodologique.

## 5.4 Paul, dispatcher sécurité civile

**Aujourd'hui.** Paul reçoit un signalement de feu de forêt en zone 31. Il le saisit dans le SI pompiers. La donnée arrive à Météo-France en CSV nocturne, H+18h plus tard, dans une chaîne d'enrichissement parallèle.

**Avec la plateforme.** Paul saisit dans une DataWindow connectée à la plateforme. Validation supervisée en 5 minutes. La donnée alimente immédiatement les modèles de propagation, les alertes vigilance feu, le briefing préfecture. Latence saisie → utilisable : minutes.

**Valeur** : réactivité opérationnelle, qualité de la décision préfectorale, retour d'expérience accéléré.

## 5.5 Anne, responsable data DSI

**Aujourd'hui.** Anne ne sait pas ce que les équipes consomment ; quand elle veut renégocier un contrat avec NOMADS ou facturer en interne un usage, elle assemble manuellement des estimations contestables.

**Avec la plateforme.** Anne interroge l'audit transverse : volume téléchargé, datasets exposés par équipe, accès par consumer. Reporting mensuel automatique. Décisions de pilotage chiffrées.

**Valeur** : pilotage data sourcé, optimisation des coûts amont, maturité de gouvernance.

## 5.6 Vincent, ingénieur dataops

**Aujourd'hui.** AROME en retard à 14h. Vincent l'apprend par un mail d'une équipe aval qui se plaint. Il diagnostique en 2h.

**Avec la plateforme.** AROME en retard détecté à 13:45 (15 min après l'horaire SLA). Notification automatique. Cascade calculée : 14 secondaires bloqués, 38 produits dégradés. Cause identifiée : NOMADS source amont. Communication aux consumers automatisée. MTTD : 15 min, MTTR : maîtrisé.

**Valeur** : opérabilité, transparence vis-à-vis des consumers, réduction du stress ops.

## 5.7 Service aviation client externe

**Aujourd'hui.** Un METAR est émis avec une valeur erronée. Correction interne 30 min plus tard. Le client externe ne le sait pas, utilise la mauvaise valeur pour son déroutement.

**Avec la plateforme.** Émission d'un METAR `COR` automatique sur le canal AMSS, conforme OACI Annexe 3. Le client reçoit la correction, son système la traite. Conformité réglementaire automatisée.

**Valeur** : conformité, responsabilité légale tenue, confiance client renforcée.

\newpage

# 6. Cadre fonctionnel cible

## 6.1 Principe directeur

Une donnée existe une fois, est trouvable, comprise, gouvernée, exploitable. Cette unicité s'applique à trois niveaux :

1. **Notions** (sens métier) — un concept = un identifiant canonique partagé.
2. **Méta-données** (techniques) — un schéma = une autorité unique.
3. **Données** (physiques) — une donnée = un emplacement référencé, pas copié.

La cible n'est pas plus moderne que l'existant : elle est plus **disciplinée**.

## 6.2 Capacités fonctionnelles (alignées DAMA-DMBOK)

Le découpage suit les fonctions du **DAMA-DMBOK** (référence professionnelle du data management), avec adaptation au contexte météo où certaines capacités ont une importance spécifique (sémantique, latence, conformité réglementaire forte).

| # | Capacité (DAMA) | Adaptation météo | Verbe directeur |
|---|---|---|---|
| 1 | Data Architecture | Architecture en couches : raw → bronze → primaire → secondaire → produit | Concevoir |
| 2 | Data Modeling and Design | Modélisation pivotée sur les concepts CF + grilles + référentiels | Modéliser |
| 3 | Data Storage and Operations | Stockage immuable, tiering hot/warm/cold/frozen, conservation patrimoniale | Stocker |
| 4 | Data Security | Classifications L0-L3, ABAC, conformité OACI / WMO / RGPD / IGI 1300 | Habiliter |
| 5 | Data Integration and Interoperability | Acquisition mutualisée, normalisation déterministe, API d'accès | Acquérir + Normaliser + Diffuser |
| 6 | Reference and Master Data | Glossaire transverse, mappings inter-encodings (CF / GRIB / BUFR / ECMWF) | Catalogue sémantique |
| 7 | Metadata Management | Catalogue technique, lineage, contracts, audit | Cataloguer |
| 8 | Data Quality | Qualité par contract, qualité par recette, qualité par usage | Qualifier |
| 9 | Document and Content Management | Templates produits, briefings, exports paramétrés | Présenter |
| 10 | Data Warehousing and BI | Compute scientifique partagé, requêtage cross-source, exploration | Calculer |
| 11 | Data Governance | Data contracts, ADR, comités de curation, conformité, RGPD | Gouverner |

Trois capacités spécifiques à la météo, complémentaires au DAMA :

| # | Capacité météo | Verbe directeur |
|---|---|---|
| 12 | Saisie & contribution opérateur (observations terrain, observations citoyennes) | Saisir |
| 13 | Évolution dans le temps (versionnement de schémas, recettes, archives lisibles à 30 ans) | Évoluer |
| 14 | Surveillance fonctionnelle de bout en bout (SLA, fraîcheur, complétude, accès) | Surveiller |

\newpage

# 7. Description fonctionnelle des capacités (synthèse)

Pour chaque capacité : *ce qu'elle fait, hypothèse sur le défaut actuel, cible, indicateurs d'évaluation.* Description condensée — détails dans les annexes du document technique.

## 7.1 Acquérir
- **Cible** : un connecteur mutualisé par source amont, manifeste versionné (URL, fréquence, format, owner amont, licence), audit unifié des volumes et latences.
- **Hypothèse défaut** (H1) : connecteurs dupliqués par équipe.
- **Indicateurs** : nombre de connecteurs par source, taux de redondance évité.

## 7.2 Normaliser
- **Cible** : une recette unique versionnée par source, glossaire pivot CF, validation post-normalisation, traitement identique externe / interne (HPC inclus).
- **Hypothèse défaut** (H4) : normalisation refaite par pipeline.
- **Indicateurs** : couverture CF, taux de validation passant.

## 7.3 Cataloguer
- **Cible** : catalogue transverse navigable, recherche par concept ou attribut, lien technique ↔ métier, API + UI.
- **Hypothèse défaut** (H3) : pas de catalogue transverse, doc dans wikis.
- **Indicateurs** : couverture catalogue, temps moyen de découverte.

## 7.4 Stocker
- **Cible** : stockage immuable unique, tiering par usage observé, conservation patrimoniale documentée, retrieval testé.
- **Hypothèse défaut** (H2, H9) : multiplicateur copies, tiering ad-hoc.
- **Indicateurs** : taux de réplication non gouvernée, coût €/To/tier, succès retrieval frozen.

## 7.5 Calculer
- **Cible** : recettes Git versionnées, lineage automatique, mutualisation des secondaires.
- **Hypothèse défaut** (H5) : recettes en notebooks dispersés.
- **Indicateurs** : couverture recettes versionnées, taux de mutualisation, reproductibilité testée.

## 7.6 Présenter / produire
- **Cible** : templates partagés, URN déterministe, lineage produit → primaire, regénération sur correction.
- **Hypothèse défaut** : templates dupliqués, lineage absent.
- **Indicateurs** : nombre de templates partagés, taux cache hit, couverture lineage.

## 7.7 Diffuser
- **Cible** : canaux unifiés, SLA mesurés par dataset/canal/consumer, re-diffusion automatique.
- **Hypothèse défaut** : canaux multiples non centralisés.
- **Indicateurs** : latence p95 par canal vs SLA, audit consumers.

## 7.8 Saisir / contribuer
- **Cible** : DataWindow générée du contract, validation côté client + serveur, statut explicite, audit nominatif, mode offline + sync.
- **Hypothèse défaut** (H6) : saisies dans SI tiers, retours CSV.
- **Indicateurs** : latence saisie → disponible, taux de validation supervisée.

## 7.9 Surveiller
- **Cible** : surveillance unifiée (retards, complétude, qualité, accès), indicateurs publiés comme données gouvernées, reporting SLA automatique.
- **Hypothèse défaut** (H10) : surveillance par équipe.
- **Indicateurs** : couverture observabilité, MTTD, MTTR.

## 7.10 Habiliter
- **Cible** : identité unique fédérée, ABAC déclaratif, re-validation périodique, isolation physique L3, audit unifié.
- **Hypothèse défaut** (H8) : habilitations par app, comptes zombies.
- **Indicateurs** : comptes uniques par utilisateur, taux re-validation, tests de fuite.

## 7.11 Gouverner (transverse)
- **Cible** : data contracts en Git, validation CI, ADR, comité curation glossaire, audit semestriel écarts contract/réalité.
- **Hypothèse défaut** (H3) : gouvernance par tradition orale.
- **Indicateurs** : couverture contracts, délai validation contract, taux écart contract/réalité.

## 7.12 Évoluer (transverse)
- **Cible** : schema evolution non cassante, politique re-traitement explicite, lisibilité archives à 30 ans testée.
- **Hypothèse défaut** : évolutions cassantes, archives partiellement illisibles.
- **Indicateurs** : nombre évolutions cassantes/an, taux lisibilité archives.

\newpage

# 8. Business case (ordres de grandeur, à préciser)

## 8.1 Avertissement

Cette section pose des **ordres de grandeur conservateurs** à valider en audit. Chaque chiffre est explicité. **Aucun ne doit être utilisé comme référence sans vérification terrain.**

## 8.2 Coût du non-changement (estimation)

Hypothèses :
- Volumétrie active : ~10 Po (ordre de grandeur opérateur national).
- Multiplicateur copies : entre x3 et x8 (à mesurer ; H2).
- Coût stockage : 50 €/To/an en stockage actif amorti, hors CAPEX initial.

Scénario conservateur :

| Poste | Hypothèse basse | Hypothèse haute |
|---|---|---|
| Surcoût stockage (réplications gouvernables) | 6 Po de copies évitables × 50 €/To/an = 300 k€/an | 25 Po × 50 €/To/an = 1,25 M€/an |
| RH redéployable (connecteurs et pipelines dupliqués) | 5 ETP × 100 k€ = 500 k€/an | 15 ETP × 100 k€ = 1,5 M€/an |
| Time-to-market manqué (services non créés) | non chiffré | non chiffré |
| Coûts incidents (corrections, re-traitements) | 100 k€/an | 500 k€/an |
| Risque réglementaire | non chiffré, potentiellement majeur sur OACI / RGPD | |
| **Total estimable** | **~1 M€/an** | **~3,5 M€/an** |

À **5 ans cumulés**, à volumétrie constante : 5 à 17,5 M€. À volumétrie en croissance (probable), majoration de 30-50 %.

**Ces chiffres sont des ordres de grandeur**. Audit indispensable avant tout engagement.

## 8.3 Coût investissement plateforme cible

Hypothèses :
- Phase démonstrateur (6 sem, 2 ETP) : 50 k€.
- Phase pilote (9-12 mois, 3-4 ETP + infra dédiée) : 700 k€ - 1,2 M€.
- Phase industrialisation (18-24 mois, 6-8 ETP + infra cible) : 2,5 - 5 M€.
- Plateforme cible exploitable à 3 ans : OPEX continu 1,5 - 3 M€/an (RH + infra).

Investissement total 3 ans : **4 à 8 M€** selon ampleur retenue.

## 8.4 Bénéfices quantifiables (à 3 ans)

- Réduction des copies : économies stockage 1-3 M€/an récurrent.
- Réutilisation RH : 3-10 ETP redéployés vers innovation (services, ML).
- Time-to-market nouveaux services : passage de trimestres à semaines (gain qualitatif, à monétiser via revenus B2B nouveaux).
- Conformité réglementaire automatisée : risque d'amende RGPD ou perte d'agrément OACI évité (impact non chiffré, potentiellement majeur).
- Fiabilité opérationnelle : MTTD / MTTR divisés par 2-5.

## 8.5 Synthèse business case

**Hypothèse basse, conservateur** : coût 4 M€ sur 3 ans, économies cumulées 3 M€ sur la même période + ouverture de capacités d'innovation. ROI marginal en investissement direct, mais **création de capacité durable**.

**Hypothèse moyenne** : coût 6 M€, économies 8-12 M€ + nouveaux services : ROI clairement positif à 3-5 ans.

**Hypothèse haute (transformation profonde)** : coût 8 M€, économies 15-20 M€ + bascule de positionnement (l'opérateur devient fournisseur unifié de référence) : ROI fort, valeur stratégique majeure.

**À retenir** : le ROI direct dépend du multiplicateur de copies actuel. Plus le multiplicateur réel est élevé, plus le ROI investissement est rapide. **L'audit préalable détermine le scénario applicable.**

\newpage

# 9. Make vs Buy

## 9.1 Le débat

Faire (build OSS souverain) ou acheter (SaaS commercial type Snowflake, Databricks, Microsoft Fabric, BigQuery) ?

## 9.2 Comparaison principale

| Critère | Build OSS souverain | SaaS commercial (Snowflake/Databricks/Fabric) |
|---|---|---|
| Coût initial | Élevé (RH, intégration) | Faible (mise en route rapide) |
| Coût récurrent | Modéré et maîtrisé | Élevé et croissant avec volumes |
| Lock-in | Faible (formats ouverts) | Élevé (formats internes, API propriétaire partielle) |
| Souveraineté données | Maximale (on-premise possible) | Variable (cloud public, parfois localisé) |
| Couverture fonctionnelle | 100 % du besoin si on construit | 60-80 % typiquement, le reste à construire en plus |
| Compétences requises | Internes, durables | Marché tendu, dépendance fournisseur |
| Time-to-value initial | 12-18 mois | 3-6 mois |
| Maturité écosystème | En croissance (Iceberg, Zarr) | Élevée mais propriétaire |
| Spécificités météo (gridded Zarr) | Excellente (Pangeo) | Médiocre (gridded mal supporté) |
| Conformité défense IGI 1300 | Possible (déploiement isolé) | Difficile à impossible (cloud public) |
| Évolutivité Po-scale | Démontrée par ECMWF, NOAA | Coûts qui explosent |

## 9.3 Verdict

Pour un opérateur météo national :

- Le **gridded météo (Zarr)** est mal supporté par les SaaS commerciaux. C'est une faiblesse rédhibitoire pour un SI où 70 % du volume est gridded.
- La **souveraineté** est généralement requise (institution publique, conformité défense possible).
- Le **lock-in** est un risque majeur sur un horizon 10-30 ans (durée de vie d'archives météo).
- Le **time-to-value** d'un SaaS est attractif initialement, mais **construit la dette** que le programme ambitionne précisément de résoudre.

**Recommandation** : **build OSS souverain** sur le cœur (gridded, catalogue, gouvernance), **avec usage tactique** de SaaS commercial sur les périphériques où la valeur est rapide et le lock-in faible (par exemple, BI dashboard avec Metabase ou Superset OSS, ou éventuellement un connector vers un SaaS pour l'analytique métier non-critique).

**Conditions à vérifier avant de figer cette recommandation** :
- Maturité interne en compétences data engineering OSS.
- Sponsorship pluri-annuel garanti (le build coûte cher en année 1-2).
- Capacité à recruter ou former.

## 9.4 Hybride à examiner

Une option intermédiaire à instruire :

- **Build OSS** sur le data lake (Iceberg + Zarr + catalogue + glossaire + gouvernance).
- **SaaS** ou produit packagé sur les surfaces consumer (BI managed, dashboard managed) où la rapidité prime.
- **Engagement open source** sur les briques de niche manquantes (cache produit, tile server météo) si la communauté ne couvre pas suffisamment.

\newpage

# 10. Acteurs et rôles

| Acteur | Rôle dans la cible | Évolution depuis l'existant |
|---|---|---|
| Producteur de donnée (ingénieur prévi, modélisateur, gestionnaire capteur) | Owner d'un primaire, rédacteur du data contract | Propriétaire de pipeline silo → owner contractualisé |
| Producteur de recette (chercheur, ingénieur calcul, ingénieur métier) | Owner d'un secondaire ou d'un produit | Scripteur isolé → contributeur Git mutualisable |
| Curateur sémantique (linguiste métier, expert domaine) | Maintient le glossaire, valide les concepts | Rôle nouveau ou transformé |
| DataOps / SRE plateforme | Opère la plateforme, monitore, corrige les incidents | Ops par équipe → équipe transverse |
| Architecte data | Cadre les évolutions, rédige les ADR | Rôle structurant central |
| Consumer interne | Lit la plateforme via API | Copieur de fichiers → consommateur référencé |
| Opérateur saisie (terrain, dispatcher) | Saisit via DataWindow, valide, corrige | Utilisateur SI tiers → contributeur direct gouverné |
| Superviseur / validateur | Validation 2-yeux des saisies et corrections critiques | Rôle explicite, traçable |
| DPO / juriste | Validation des access contracts, RGPD, conformité | Intégré au workflow plateforme |
| Sponsor exécutif | Arbitre, finance, priorise | Indispensable, durable |

\newpage

# 11. Processus métier transverses

## 11.1 De la source au consumer (nominal)

Sources amont publient → acquisition mutualisée → atterrissage zone raw → normalisation versionnée → validation qualité+complétude → promotion en primaire → catalogage automatique → lineage tracé → disponibilité aux consumers → calcul secondaires → produits → diffusion canaux contractualisés.

À chaque étape : audit, observabilité, application de la politique d'accès, contrôle de fraîcheur.

## 11.2 De l'opérateur à la base (saisie)

Opérateur ouvre DataWindow → saisie validée client → soumission API → validation serveur → stockage en draft → validation 2-yeux si critique → promotion published → cascade downstream → diffusion vers consumers concernés.

## 11.3 De la détection à la notification (alerte métier)

Évaluation périodique ou sur événement → lecture primaires/secondaires → application alert contract → décision seuil franchi → état alerte → routage canaux → notification → acquittement → cycle de vie (open / acknowledged / resolved / silenced).

## 11.4 Du retard à la transparence (SLA fraîcheur)

Schedule attendu déclaré → évaluation périodique → statut late/very_late/missing → détection cause → notification ops → cascade SLA aux downstream → reprise sur arrivée tardive → reporting SLA mensuel.

## 11.5 De la correction à la cascade (modification valeur)

Opérateur identifie valeur fausse → événement corrected avec raison → validation 2-yeux → publication → vue current mise à jour → cascade : downstream invalidés et rejoués → diffusion publique de l'event de correction → audit immuable conservé.

\newpage

# 12. Stratégie de transition

## 12.1 Principe : strangler pattern (jamais big-bang)

Migration progressive, dataset par dataset. La plateforme cible vit en parallèle du legacy ; chaque dataset migre selon son propre rythme et ses propres critères de bascule. Le legacy disparaît à la fin de la transition, dataset par dataset, jamais en bloc.

## 12.2 Quatre phases par dataset

| Phase | État cible | État legacy | Critère de bascule |
|---|---|---|---|
| 1 | Lecture seule, en miroir du legacy | Source de vérité | Mise en cohérence quotidienne validée |
| 2 | Double-écriture (writes répliqués vers cible) | Toujours source de vérité, mais validé en parallèle | Égalité des deux pendant 4 semaines minimum |
| 3 | Source de vérité, legacy en lecture seule | Lecture seule, conservé pour fallback | Stabilité 3 mois, consumers migrés |
| 4 | Seule source | Retiré | Décommissionnement officiel, archive lue depuis cible |

## 12.3 Continuité de service

Pendant les phases 1-3, le legacy reste opérationnel. **Aucun consumer critique n'est forcé de migrer avant la phase 3 stabilisée.** La cible doit prouver qu'elle ne dégrade pas avant d'imposer.

## 12.4 Gouvernance de la transition

- **Comité de transition** : sponsor + DSI + owners de domaine, mensuel.
- **Plan dataset par dataset** : owner identifié, date cible, critères bascule, responsable de la conformité.
- **Communication régulière** aux consumers : changements à venir, formation, support.
- **Réversibilité prévue** : à chaque phase, la régression est possible sans perte de données.

## 12.5 Préservation de la connaissance tacite

À chaque migration de dataset :

- Atelier avec l'owner actuel pour rédiger le data contract (capture explicite des règles implicites).
- Documentation des « pourquoi » historiques (pas seulement les « comment »).
- Formation des successeurs avant le départ de l'expert.

C'est probablement **la phase la plus critique et la plus sous-estimée** d'une transformation comme celle-ci.

## 12.6 Conformité et re-certification

- Plan de re-certification OACI / WMO / RGPD / IGI 1300 par dataset.
- Coût et délai chiffrés en amont (typiquement 3-6 mois par certification, 50-200 k€).
- Anticipation des obstacles légaux : certains datasets ne pourront migrer qu'après évolution réglementaire.

## 12.7 Réversibilité

Décision-clé : **la cible doit prouver qu'elle peut se retirer** d'un dataset (régression vers legacy) tant que la phase 4 n'est pas effective. Cette réversibilité **rassure les owners** et **réduit la résistance**.

\newpage

# 13. Indicateurs de succès

## 13.1 Indicateurs business (priorité 1)

| Indicateur | Cible à 3 ans |
|---|---|
| Économies stockage récurrent | 1-3 M€/an mesurés en sortie d'audit final |
| ETP redéployés vers innovation | 5-10 ETP, justifiés et documentés |
| Time-to-market d'un nouveau cas d'usage métier | < 3 mois (vs. trimestres-années aujourd'hui) |
| Adoption interne | ≥ 80 % des équipes métier consommatrices référencées |
| Audits réglementaires passés sans réserve | 100 % des datasets critiques |
| NPS interne (équipes utilisatrices) | ≥ +30 |
| Nouveaux services facturables (B2B) | Au moins 3 lignes nouvelles ouvertes |
| Coût total de possession (TCO) à 5 ans | < TCO du legacy équivalent à volume égal |

## 13.2 Indicateurs opérationnels (priorité 2)

| Indicateur | Cible à 3 ans |
|---|---|
| Datasets couverts par data contract publié | ≥ 90 % |
| Couverture du glossaire (concepts liés aux datasets) | ≥ 90 % |
| Taux de réplication non gouvernée | < 5 % |
| MTTD plateforme (détection retard / incident) | < 15 min |
| MTTR plateforme | < 1 h sur 95 % des incidents |
| SLA fraîcheur respectés sur datasets critiques | ≥ 99 % |
| Comptes zombies | < 1 % |
| Re-validation annuelle habilitations | 100 % |
| Reproductibilité d'études : régénération bit-à-bit | ≥ 99 % testée trimestriellement |
| Taux d'écart contract / réalité | 0 sur incidents critiques |

## 13.3 Cadence d'évaluation

- **Mensuelle** : indicateurs opérationnels, dashboard direction.
- **Trimestrielle** : indicateurs business avec analyse d'impact.
- **Annuelle** : revue stratégique, ajustement roadmap.

\newpage

# 14. Risques

## 14.1 Risques majeurs et mitigation

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Adoption faible : équipes refusent ou contournent la migration | Très élevée | Critique | Sponsor exécutif fort et durable, ambassadeurs internes, double-lecture parallèle, valeur visible avant migration, réversibilité |
| Recréation de silos : la plateforme devient un énième silo | Moyenne | Critique | Charte single-source, validation CI bloquante, audit semestriel, pas de dérogation tacite |
| Sur-promesse : cible inatteignable en délai | Moyenne | Élevé | Roadmap incrémentale, valeur livrée avant exhaustivité, MVP démontré |
| Sous-estimation facteur humain : changement non accompagné | Élevée | Élevé | Plan de formation, ambassadeurs, support pédagogique dédié |
| Gouvernance lourde : data contract devient un frein | Moyenne | Moyen | Outillage léger, validation rapide, accompagnement |
| Conformité défaillante : OACI / WMO / RGPD non respectés | Moyenne | Critique | DPO et juristes intégrés au workflow, audits planifiés |
| Échec transition : legacy maintenu indéfiniment en parallèle | Élevée | Élevé | Plan de sunset par dataset avec dates fermes, comité de transition |
| Dépendance sponsor unique : départ → mort du projet | Élevée | Critique | Sponsorship plural, ouverture progressive, documentation institutionnelle |
| Dette technique cachée : choix techniques à reprendre dans 3 ans | Moyenne | Moyen | ADR rigoureux, choix OSS portables, formats ouverts |
| Perte de mémoire institutionnelle | Très élevée | Élevé | Migration accompagnée par owners actuels, recettes traduites en contract avant retrait |
| Coût RH sous-estimé | Élevée | Critique | Calibrage sur retours comparables, marge 30 % |
| Sécurité / compliance défense (IGI 1300) | Moyenne | Critique | Architecture isolée pour L3, audit régulier |

## 14.2 Risques spécifiques à l'opérateur (à évaluer en audit)

- Désalignement entre direction métier et DSI.
- Contrats fournisseurs en cours non résiliables.
- Capacité de recrutement sur le marché français data engineering.
- Dépendances d'autres directions (ressources humaines, achats, juridique).

\newpage

# 15. Questions ouvertes

Document complémentaire `architecture_si_meteo.docx` (section 7) contient 78 questions classées en 13 axes. Quatre sont **préalables à tout démarrage** :

1. **Sponsor exécutif identifié et engagé pour 3 ans minimum ?**
2. **Cible (Météo-France seul, consortium européen, produit générique) ?**
3. **Budget pluri-annuel provisionné ?**
4. **Équipe minimale viable identifiée et engagée ?**

Sans réponse documentée à ces quatre, **arrêt du programme**, le document reste cadre intellectuel.

\newpage

# 16. Conclusion

L'existant n'est pas en panne par défaut technique. Les équipes sont compétentes, les outils sont corrects à leur échelle d'origine. Le défaut est **fonctionnel et organisationnel** : la plateforme actuelle manque d'unicité par construction, et le pétaoctet rend cette absence d'unicité de plus en plus coûteuse.

La cible n'est pas une révolution technique. C'est une **discipline architecturale** : *une donnée existe une fois, gouvernée, traçable, exploitable*. Cette discipline exige :

- Un **sponsorship durable** (3 ans minimum).
- Une **gouvernance plurale** qui respecte les rationalités d'équipe.
- Une **transition progressive** avec réversibilité prouvée.
- Un **capital RH formé** sur les compétences cibles.
- Une **co-rédaction** des data contracts avec les owners actuels (capture de la connaissance tacite).
- Une **conformité re-certifiée** par dataset migré.

Les principes architecturaux sont **nécessaires mais pas suffisants**. Ce qui décide du succès, c'est la persistance du sponsorship, la qualité de l'accompagnement, la rigueur de la transition, la capacité à dialoguer avec les rationalités du présent.

Aucun choix technique (Iceberg ou Polaris, Dagster ou Kestra, OSS souverain ou SaaS commercial) ne sauve un programme qui néglige ces conditions. Inversement, un programme qui les respecte peut s'accommoder de plusieurs choix techniques alternatifs sans changer de trajectoire.

C'est la lecture honnête : ce document propose un cadre. **Il ne se substitue pas à la décision.**

---

*Document v2 — révisé après auto-critique.*
*Limites assumées et signalées : hypothèses à valider, pas de juriste relecteur, pas de chiffres terrain.*
*Évolutif. Critique structurelle attendue avant rédaction des ADR détaillés et démarrage du POC.*
