# ADR 0001 — Adopter SKOS comme socle du référentiel de métadonnées météo

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, architecte data, lead dev référentiel)
- **Étiquettes** : architecture, sémantique, vocabulaire, interopérabilité
- **Supersède** : la modélisation `vocab.types_grandeur` + `vocab.champs` + `catalog.*` du fichier `schema_referentiel_v3.sql`

---

## 1. Contexte et énoncé du problème

Le besoin a été clarifié au cours de la revue d'architecture :

> *« Un référentiel de métadonnées qui permet de décrire les données météo. Il doit pouvoir accueillir toutes les notions météo (grandeurs, phénomènes, méthodes, niveaux, indices, événements, espèces chimiques…). Une notion peut avoir plusieurs parents légitimes selon le point de vue (par exemple `Température de brillance` se rattache à `Température` côté grandeur physique et à `Mesure radiométrique` côté satellite). Le périmètre se limite aux concepts (option A) — pas aux instances physiques (stations, instruments, modèles), pas aux produits de données. »*

La modélisation actuelle (`schema_referentiel_v3.sql`, v3) bute sur trois limites incompatibles avec ce besoin :

1. **Hiérarchie figée à un seul niveau** : `vocab.types_grandeur` et `vocab.champs` forment une hiérarchie déguisée à profondeur 2, sans relation parent/enfant explicite. Impossible d'ajouter un niveau intermédiaire ni de descendre plus bas sans encoder la sémantique dans la chaîne du `code`.
2. **Mono-hiérarchie implicite** : un concept ne peut avoir qu'un seul parent, ce qui interdit les rattachements multiples par point de vue.
3. **Périmètre fermé** : le typage est pensé pour les variables atmosphériques classiques. Les phénomènes qualitatifs (orage, brouillard), indices climatiques (NAO, SPI), événements, processus, espèces chimiques, n'ont pas de place.

Par ailleurs le schéma essaie de redéfinir localement des notions déjà standardisées et publiées par les organismes internationaux (CF Conventions, WMO Codes Registry, QUDT, NERC BODC), au risque de produire un nouveau silo non interopérable.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Multi-hiérarchie** | Un concept doit pouvoir appartenir à plusieurs taxonomies (par grandeur, par domaine d'observation, par chaîne de traitement). |
| D2 | **Périmètre extensible à toute notion météo** | Doit absorber grandeurs, phénomènes, méthodes, niveaux, indices, événements, processus, espèces chimiques, sans refonte du schéma. |
| D3 | **Interopérabilité avec les standards internationaux** | CF, WMO, QUDT, BODC, GCMD sont les sources de référence. Le référentiel doit s'aligner, pas réinventer. |
| D4 | **Multilingue** | Sources amont en anglais ; usage local francophone ; ouverture INSPIRE/EU à terme. |
| D5 | **Versionnement et gouvernance** | Référentiel normatif : tracer les changements, valider les évolutions, garder un historique exploitable. |
| D6 | **Stack opérable par l'équipe actuelle** | PostgreSQL est en place, les compétences sont SQL ; éviter d'introduire un triple store sans nécessité. |
| D7 | **Coût de remplissage maîtrisé** | Une saisie manuelle exhaustive de plusieurs milliers de concepts est irréaliste ; il faut un modèle compatible avec un import en masse depuis les sources standards. |

## 3. Options considérées

### Option A — Conserver le modèle relationnel maison actuel et l'étendre

Garder `types_grandeur` + `champs` + facettes en colonnes, ajouter une table `concept_parent` pour la multi-hiérarchie, ajouter au coup par coup les tables nécessaires aux nouveaux types de notions (phénomènes, événements, indices…).

### Option B — Modèle SKOS implémenté en relationnel PostgreSQL (retenu)

Adopter le modèle conceptuel SKOS Core (W3C, 2009) — concepts, schemes, relations hiérarchiques (`broader`/`narrower`), associatives (`related`), et de mapping (`exactMatch`, `closeMatch`, `broadMatch`…), labels multilingues, notes — implémenté dans 5 à 7 tables PostgreSQL. Conserver Postgres comme moteur de stockage. Compléter par une extension locale pour le typage physique (unités, plages, dimensions) et le bloc gouvernance déjà esquissé dans la v3.

### Option C — Modèle ontologique OWL complet

Modéliser en OWL DL (classes, propriétés typées, axiomes, contraintes, raisonnement). Stocker en relationnel ou en triple store.

### Option D — Triple store RDF natif

Apache Jena, GraphDB, Stardog ou équivalent. Stockage RDF, requêtage SPARQL, import direct des sources SKOS/OWL externes.

## 4. Décision

**Option B retenue** : adopter SKOS Core comme modèle conceptuel, l'implémenter en PostgreSQL relationnel, le compléter par une extension locale pour le typage physique des concepts mesurables et par le bloc de gouvernance déjà prévu.

### Périmètre concret

Le futur schéma comportera trois étages indépendants :

1. **Étage SKOS** (≈ 6 tables) : `scheme`, `concept`, `concept_label`, `concept_in_scheme`, `concept_semantic_relation` (broader / related / *Match), `concept_note`.
2. **Étage typage physique** (≈ 2 tables) : `concept_physical` (value_type, unité canonique, plage, dimension, précision) qui ne s'applique qu'aux concepts mesurables ; `unite` et `unite_conversion` conservés depuis la v3.
3. **Étage gouvernance** (déjà présent en v3, à conserver) : `users`, `roles`, `statuses`, `import_sources`, `imports`, `audit_log`, `proposals`, plus les colonnes transverses (`status`, `version`, `valid_from/to`, `created_*`, `modified_*`, `import_*`) répliquées sur chaque concept.

### Hors périmètre (exclusions actées)

- Les tables `catalog.*` (stations, instruments, radars, plateformes_sat, capteurs_sat, canaux_sat, modeles, grilles_def) sont **retirées** : ce sont des instances physiques, hors du périmètre « concepts uniquement ».
- Les tables `vocab.acteurs`, `vocab.licences` sont **retirées** au sens « décrire la donnée elle-même » : elles décrivent des producteurs et conditions d'usage, pas des notions météo.
- Aucune table de produit / dataset / observation n'est introduite.

### Stratégie de remplissage

Importer en priorité depuis les sources standards plutôt que saisir :

| Source | Stratégie | Volume estimé |
|---|---|---|
| CF Standard Names | Clone local | ~5500 concepts |
| CF Cell Methods, Areas, Regions | Clone local | ~600 concepts |
| QUDT Units & QuantityKinds | Clone local (alignement avec `vocab.unite`) | ~2000 unités |
| WMO Codes Registry (vocabs ciblés : types de plateforme, descripteurs BUFR utiles) | Clone partiel | quelques centaines |
| NERC BODC (P01, P02…) | Alignement par mapping seul | non clonés |
| ECMWF Parameter Database | Alignement par mapping seul | non clonés |
| Concepts propres (vocabulaire métier interne, schemes éditoriaux, traductions FR) | Saisie locale | 50 à 500 concepts |

### URI et engagement long terme

Adopter un domaine d'URI stable de la forme :

```
https://referentiel.meteo.fr/vocab/{scheme}/{notation}
```

à confirmer avec le sponsor métier. Une fois publié, un URI ne change plus ; un concept retiré est marqué `deprecated`, jamais supprimé.

### Stockage et exposition

- **Stockage** : PostgreSQL 14+ (statu quo).
- **Exposition lecture** : vues métier SQL + API REST (PostgREST ou équivalent).
- **Export RDF/SKOS** : prévu à la demande, pour interopérabilité avec outils externes (Skosmos, VocBench, catalogues INSPIRE). Implémenté côté application, pas dans la base.
- **Migration vers triple store** : non prévue, réévaluée si un besoin de raisonnement formel ou de SPARQL fédéré émerge.

## 5. Conséquences

### Positives

- **Standard reconnu, hors-silo** : tout consommateur familier de SKOS sait lire le référentiel ; toute publication SKOS amont (CF, WMO, QUDT) est mécaniquement importable.
- **Universalité du périmètre** : le même mécanisme (`concept` + `scheme`) absorbe grandeurs, phénomènes, méthodes, niveaux, indices, événements, espèces chimiques. Plus besoin de créer une table par type de notion.
- **Multi-hiérarchie native** : la table `concept_semantic_relation` permet à un concept d'avoir plusieurs `broader`, éventuellement scopés par `scheme`.
- **Mappings cross-source comme citoyens de première classe** : l'alignement sur les standards externes est une relation SKOS standard, pas un add-on bricolé.
- **Réduction drastique du schéma** : passage estimé de 873 lignes SQL à environ 200, par élimination des tables `catalog.*` et fusion `types_grandeur`/`champs` dans `concept`.
- **Coût de remplissage divisé par un ordre de grandeur** : import en masse au lieu de saisie.

### Négatives / coûts à accepter

- **Refonte du schéma v3** : `vocab.types_grandeur`, `vocab.champs`, l'intégralité de `catalog.*`, `vocab.acteurs`, `vocab.licences` sont à retirer ou à externaliser. Les seeds correspondants sont à rejouer en mode SKOS.
- **Engagement sur un domaine d'URI** : décision irréversible une fois publication faite. Choix à valider avec le sponsor métier avant le premier import.
- **Pipeline d'import à construire** : 200-400 lignes Python par source (rdflib, lxml, requests). Outillage à industrialiser dans la durée (re-sync, gestion des overrides locaux).
- **Pas de typage formel SKOS** : SKOS ne contraint pas qu'un concept ait un seul `prefLabel` par langue, ni que les unités soient cohérentes. Ces contraintes sont à imposer côté SQL (`UNIQUE` partiels, `CHECK`).
- **Pas d'inférence native** : la transitivité hiérarchique (`broader` de `broader`) se fait à l'exécution via `WITH RECURSIVE`, pas par raisonnement automatique.
- **Composition de facettes non couverte** : un « observable » au sens « T° air, niveau 2 m, méthode min, période P1D » n'est pas modélisé. Cohérent avec l'option A (concepts seuls) mais à rouvrir si le périmètre s'étend ultérieurement à la description de produits.

### Conséquences sur les autres décisions

- ADR à venir : choix du domaine d'URI (`referentiel.meteo.fr` ou autre).
- ADR à venir : stratégie multilingue (FR seul au démarrage vs FR+EN dès l'import).
- ADR à venir : choix de l'outil de curation (VocBench, Directus + UI custom, Skosmos en lecture seule).
- ADR à venir : stratégie de licence des données importées (compatibilité CF/QUDT/WMO avec la licence cible de publication).

## 6. Pros / cons des options non retenues

### Option A — Modèle maison étendu

- **Pros** : continuité avec la v3 ; pas de re-modélisation ; équipe en terrain connu.
- **Cons** : (a) reste un silo non interopérable avec les standards ; (b) chaque nouveau type de notion (événement, indice, processus) demande une nouvelle table ; (c) la dette de re-modélisation s'aggrave avec le temps ; (d) la saisie manuelle exhaustive reste inévitable, ce qui rend le référentiel impossible à compléter à effectif raisonnable. **Rejeté** : bloque sur D2, D3, D7.

### Option C — OWL complet

- **Pros** : expressivité maximale ; raisonnement formel ; contraintes typées (domaine, range, cardinalité).
- **Cons** : (a) complexité de modélisation hors de proportion avec le besoin ; (b) montée en compétence longue (OWL DL, profils, raisonneurs) ; (c) outillage plus rare et plus cher ; (d) la plupart des sources amont sont en SKOS, pas en OWL — l'expressivité supplémentaire ne sert pas. **Rejeté** : surinvestissement face à D6, sans retour sur les drivers métier.

### Option D — Triple store RDF natif

- **Pros** : fidélité totale au modèle SKOS ; SPARQL fédéré possible ; import RDF direct sans transformation.
- **Cons** : (a) introduction d'un nouveau composant d'infrastructure à opérer ; (b) compétences SPARQL à acquérir ; (c) écosystème d'outillage applicatif moins riche que SQL (admin, BI, audit, sauvegarde) ; (d) coût de licence si choix non open source (Stardog, GraphDB Enterprise) ; (e) bénéfice principal — raisonnement et fédération — pas requis par les drivers actuels. **Rejeté à ce stade** : potentiellement réévalué si les besoins évoluent. SKOS-en-relationnel peut être migré vers triple store sans perte sémantique.

## 7. Validation

Cette décision est validée si, à l'issue de l'implémentation :

- [ ] L'import en masse de CF Standard Names produit ≥ 5000 concepts utilisables, en moins de 5 minutes d'exécution.
- [ ] Un concept peut être rattaché à au moins deux `broader` dans deux schemes différents (test : `Température de brillance`).
- [ ] Un concept local porte au moins un mapping `exactMatch` ou `closeMatch` vers une source externe (test : alignement CF).
- [ ] Les schemes initiaux (grandeurs, phénomènes, méthodes, niveaux verticaux, cadences) sont peuplés et requêtables par `WITH RECURSIVE` pour la résolution hiérarchique.
- [ ] L'export RDF/SKOS d'un sous-ensemble du référentiel est validé par un outil tiers (Skosmos ou validateur SKOS-Play).

## 8. Références

- W3C — *SKOS Simple Knowledge Organization System Reference* : https://www.w3.org/TR/skos-reference/
- W3C — *SKOS Primer* : https://www.w3.org/TR/skos-primer/
- CF Conventions — *Standard Names* : https://cfconventions.org/standard-names.html
- WMO Codes Registry : https://codes.wmo.int
- QUDT — *Quantities, Units, Dimensions and Types* : https://qudt.org
- NERC Vocabulary Server (BODC) : https://vocab.nerc.ac.uk
- Format ADR retenu : MADR (Markdown Architectural Decision Records) — https://adr.github.io/madr/
