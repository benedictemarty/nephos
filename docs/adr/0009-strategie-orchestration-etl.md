# ADR 0009 — Stratégie d'orchestration ETL : démarrage Python pur, cible Kestra

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev, ops si applicable)
- **Étiquettes** : architecture, ETL, orchestration, souveraineté
- **Lié à** : [ADR 0001](0001-adopter-skos-comme-socle-du-referentiel.md) (SKOS), [ADR 0002](0002-python-comme-stack-dimplementation.md) (Python)

---

## 1. Contexte et énoncé du problème

L'ADR 0002 a fixé Python comme stack d'implémentation. Reste à décider **comment orchestrer** les imports : code Python pur déclenché par cron/CI, ou recours à un orchestrateur dédié (Airflow, Dagster, Prefect, Kestra…).

Les contraintes du contexte ont été clarifiées en revue d'architecture :

| # | Élément de contexte | Réponse |
|---|---|---|
| C1 | Existe-t-il déjà un orchestrateur dans l'organisation ? | **Non** — pas d'héritage à respecter, mais aucun composant à mutualiser non plus. |
| C2 | Y a-t-il d'autres pipelines à orchestrer avec Nephos ? | **Peut-être** — l'amortissement d'un orchestrateur central est plausible mais non garanti. |
| C3 | Y a-t-il une politique de souveraineté / préférence FR-EU ? | **Oui** — driver fort. Disqualifie de fait les outils US-only ou hébergés hors UE. |

Le profil de la charge ETL reste celui décrit dans l'ADR 0002 :

- 6 sources externes (CF Standard Names, CF Cell Methods, QUDT, WMO Codes Registry, ECMWF Param DB, NERC BODC).
- Fréquence d'import très basse (1–2 fois par an par source, parfois moins).
- Pas de DAG complexe, pas de streaming, pas de SLA serré.
- Logique métier lourde côté transformation (RDF/SKOS, validation SHACL).
- Idempotence et re-sync gérés par le modèle de données (`import_source_id`, `import_version`, `last_synced_at`, `has_local_override`).

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Souveraineté FR/EU** | Critère organisationnel acté (C3). Disqualifie Airflow, Dagster, Prefect (US). |
| D2 | **Coût opérationnel** | 6 imports occasionnels ne justifient pas l'opération d'un orchestrateur dédié au démarrage. |
| D3 | **Mutualisation future** | Si d'autres pipelines arrivent (C2), un orchestrateur central devient rentable. Il faut préserver l'option. |
| D4 | **Observabilité opérationnelle** | À terme : alerting sur échec, replay manuel, audit centralisé, dashboard pour parties prenantes non-développeurs. |
| D5 | **Réversibilité de la décision** | La stratégie retenue doit pouvoir évoluer sans réécriture du code applicatif. |
| D6 | **Compétences équipe** | Démarrage avec ce qui est déjà connu (Python, GitHub Actions). Apprentissage d'un orchestrateur reporté à quand le besoin existe. |

## 3. Options considérées

### Option A — Code Python pur, orchestré par GitHub Actions et CLI

Workflows GitHub (`workflow_dispatch` + `schedule`) qui exécutent `nephos import <source>`. Aucun orchestrateur dédié déployé. Logs et historique d'exécution dans GitHub. Cron en complément si exécution hors-CI nécessaire.

### Option B — Kestra dès le démarrage

Déploiement de Kestra (binaire Java + PostgreSQL) en complément du backend Python. Workflows définis en YAML, exécutent le CLI `nephos`.

### Option C — Démarrage Python pur, **bascule Kestra** quand un signal apparaît (retenue)

Phase 1 identique à l'option A. Phase 2 : adoption de Kestra dès qu'un des signaux suivants se manifeste (cf. § 4).

### Option D — Airflow / Dagster / Prefect

Orchestrateurs Python natifs.

### Option E — dlt / Meltano

Outils Extract-Load Python.

## 4. Décision

**Option C retenue** : démarrer en code Python pur orchestré par GitHub Actions, avec **Kestra comme cible explicite** quand un signal de bascule apparaît.

### Phase 1 — Démarrage (immédiat)

| Élément | Choix |
|---|---|
| Orchestration | GitHub Actions (`workflow_dispatch` manuel + `schedule` mensuel/trimestriel selon source) |
| Exécution | CLI `nephos` (Python, voir ADR 0002) |
| Journal | Historique GitHub Actions + table `gov.imports` côté Postgres |
| Alerting | Notification GitHub par défaut sur workflow en échec ; e-mail au mainteneur |
| Cron de secours | Possible mais non requis ; à n'introduire que si GHA est inaccessible pour une exécution |

Aucun composant supplémentaire à opérer côté infrastructure.

### Phase 2 — Bascule Kestra (déclenchée par signal)

La bascule est actée dès qu'**au moins un** des signaux suivants se manifeste :

- **S1** Un deuxième pipeline (autre référentiel, ETL data warehouse, exposition métier, etc.) entre dans le périmètre Nephos ou de l'organisation et bénéficierait d'une orchestration partagée.
- **S2** Une partie prenante non-développeuse (gestionnaire métier, opérateur, sponsor) doit lancer, surveiller ou auditer les imports, ce qui exige une UI dédiée.
- **S3** Le besoin d'alerting structuré devient critique (SLA d'import, dashboard temps réel, replay automatisé d'imports échoués).
- **S4** Le volume cumulé dépasse 10 imports orchestrés (toutes sources confondues, planifiés ou ad hoc) — seuil empirique au-delà duquel GitHub Actions devient inconfortable.
- **S5** Une exigence d'audit centralisé (qui, quand, avec quels paramètres) que GitHub Actions ne couvre pas avec la granularité requise.

Choix d'orchestrateur : **Kestra** (origine française, Apache 2.0, multi-langue, YAML déclaratif, UI moderne, conforme au driver D1). Disqualification définitive en phase 2 d'Airflow, Dagster, Prefect au titre de D1.

### Préparation à la bascule

- Le CLI `nephos` doit toujours être directement invocable et testable hors GHA — sa contractualisation (sortie sur stdout/stderr, codes retour, idempotence) sera explicite dès le démarrage.
- Les workflows GHA seront écrits comme des appels minces autour du CLI, sans logique d'orchestration métier dans le YAML GHA. Ce qui rend la transition vers un YAML Kestra triviale.
- Tout secret/configuration sera lu depuis des variables d'environnement, jamais codé dans les workflows.

## 5. Conséquences

### Positives

- **(C1) Aucun coût opérationnel au démarrage** : zéro composant à déployer en plus de Postgres et Python.
- **(C2) Cohérence avec la souveraineté** : Kestra (FR) prévu en cible, écartant les outils US.
- **(C3) Réversibilité maximale** : le code applicatif (CLI Python) est indépendant de l'orchestrateur. Migrer GHA → Kestra prend une demi-journée d'effort principalement YAML.
- **(C4) Décision adaptée au contexte actuel** : pour 6 imports occasionnels et un seul projet, déployer un Kestra dédié serait disproportionné.
- **(C5) Critères de bascule observables** : la phase 2 n'est pas vague, elle est conditionnée par des signaux mesurables qui seront revus périodiquement.

### Négatives / coûts à accepter

- **(C6) Migration future à prévoir** : il faudra un sprint dédié quand un signal de bascule apparaîtra. Coût estimé : ~½ sprint pour porter les workflows et déployer Kestra.
- **(C7) Observabilité limitée en phase 1** : les logs sont consultables dans GitHub Actions, mais sans dashboard agrégé. Acceptable tant que les imports sont rares et qu'aucune partie prenante non-dev ne les surveille.
- **(C8) Dépendance au plan GitHub** : si l'organisation passe en self-hosted Git ou abandonne GitHub Actions, la phase 1 doit être adaptée (cron Linux ou bascule anticipée vers Kestra).
- **(C9) Pas d'UI utilisateur en phase 1** : une demande de partie prenante pour une UI déclencherait une bascule anticipée — c'est précisément le signal S2.

### Conséquences sur les autres décisions

- **ADR à venir** : déploiement Kestra (infra, persistance, sécurité, plan de bascule détaillé) lorsque la bascule est déclenchée.
- **ADR à venir** : politique d'audit et de traçabilité des imports (quel niveau de détail, quelle rétention, quel format).
- **Le BACKLOG** intègre cette décision via E1-09 et conditionne l'item **E4-01 (Framework ETL)** à respecter la contractualisation CLI prévue ici.

## 6. Pros / cons des options non retenues

### Option A — Python pur exclusif, sans cible orchestrateur

- **Pros** : simplicité maximale, aucun engagement futur.
- **Cons** : ne prépare pas l'évolution. Le jour où un signal apparaît, le projet est en réaction, pas en anticipation. Architecture moins lisible pour de nouveaux arrivants. **Rejetée** : ne porte pas la prévisibilité d'évolution attendue de l'archi.

### Option B — Kestra dès le démarrage

- **Pros** : pas de migration à prévoir, observabilité disponible tout de suite, UI dispo pour parties prenantes.
- **Cons** : déploiement et opération d'un service Java + BD pour 6 imports occasionnels. Charge de formation immédiate sans bénéfice immédiat. Risque de surdimensionnement si le « peut-être » de C2 ne se confirme pas. **Rejetée** : déséquilibre entre coût opérationnel immédiat et bénéfice immédiat.

### Option D — Airflow / Dagster / Prefect

- **Cons** : tous trois sont US, échouent sur D1. Pas d'analyse plus poussée nécessaire. **Rejetée** au filtre souveraineté.

### Option E — dlt / Meltano

- **Cons** : conçus pour l'EL haute volume vers data warehouse. Leur auto-schéma ne sait pas modéliser une taxonomie SKOS. Inadaptés au domaine sémantique. **Rejetée** au filtre adéquation domaine.

## 7. Validation

Cette décision est validée si :

- [ ] Phase 1 : un workflow GitHub Actions est en place pour chaque source, déclenchable manuellement et programmé, et exécute le CLI `nephos` correspondant.
- [ ] Phase 1 : la table `gov.imports` enregistre chaque exécution avec compteurs (créés, modifiés, sautés) et état terminal.
- [ ] Phase 1 : la fréquence des échecs nécessitant intervention humaine reste sous 10 % des exécutions sur 6 mois.
- [ ] Phase 2 (lorsque déclenchée) : la bascule Kestra prend moins d'un sprint, sans modification du code applicatif Nephos.
- [ ] Phase 2 : tous les workflows GHA sont reproduits en YAML Kestra avec parité fonctionnelle.

## 8. Références

- Kestra — orchestrateur multi-langue déclaratif : https://kestra.io
- Kestra GitHub : https://github.com/kestra-io/kestra
- ADR 0001 — Adopter SKOS comme socle du référentiel
- ADR 0002 — Python comme stack d'implémentation
