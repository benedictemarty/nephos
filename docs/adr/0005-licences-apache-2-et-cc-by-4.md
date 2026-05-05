# ADR 0005 — Licences : Apache 2.0 (code) + CC-BY 4.0 (données originales)

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev)
- **Étiquettes** : juridique, licences, ouverture, conformité
- **Lié à** : [ADR 0001](0001-adopter-skos-comme-socle-du-referentiel.md) (SKOS, sources amont), [ADR 0002](0002-python-comme-stack-dimplementation.md) (code Python)

---

## 1. Contexte et énoncé du problème

Le projet Nephos contient deux natures distinctes d'œuvres :

- **Du code** : code Python à venir (ETL, validation, export, CLI), schéma SQL, scripts d'orchestration, workflows CI, configurations.
- **Des données** : concepts originaux Nephos, traductions françaises, mappings éditoriaux entre sources, schemes Nephos, notes et définitions rédigées localement.

À cela s'ajoutent les **données importées** depuis les sources standards (CF Standard Names, QUDT, WMO Codes Registry, NERC BODC, ECMWF), chacune sous sa propre licence.

Le sponsor a indiqué une préférence initiale pour Apache 2.0, puis a clarifié qu'il accepte **CC pour les données**. La revue d'architecture a établi qu'**Apache 2.0 est une licence de logiciel inadaptée pour des données** (le texte parle de « source code », « binary form », « object code », « derivative works » — termes mal alignés avec un référentiel SKOS sérialisé en RDF). De plus, les sources amont sont en **CC-BY 4.0** (CF, QUDT, NERC) ou sous régimes spécifiques (WMO Resolution 40), et leur intégration sous Apache 2.0 serait juridiquement floue.

Il faut donc **deux licences distinctes**, l'une pour le code, l'autre pour les données originales, et une politique claire pour les données importées.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Compatibilité avec les sources amont** | Mélanger des données CC-BY dans un référentiel publié sous une licence incompatible exposerait le projet à un litige ou une obligation de retrait. |
| D2 | **Adéquation juridique de la licence à l'objet** | Une licence de logiciel n'est pas faite pour les données ; une licence de contenu n'est pas faite pour le code. |
| D3 | **Adoption** | La licence doit être lisible et reconnue, pour ne pas freiner les utilisateurs ni les contributeurs. |
| D4 | **Conformité des publications EU** | INSPIRE et publications data.gouv.fr / Etalab s'alignent naturellement sur CC-BY 4.0. |
| D5 | **Réutilisation du code** | Le code applicatif (ETL, CLI, etc.) doit pouvoir être repris dans d'autres projets sans friction. |
| D6 | **Préservation de l'attribution amont** | Obligation contractuelle des sources CC-BY. |

## 3. Options considérées

### Option A — Apache 2.0 sur tout (code + données)

Application uniforme.

### Option B — CC-BY 4.0 sur tout (code + données)

Application uniforme.

### Option C — CC0 sur tout (domaine public)

Aucune restriction, aucune attribution requise.

### Option D — Double licence : Apache 2.0 (code) + CC-BY 4.0 (données originales) (retenue)

Les deux licences cohabitent, chacune sur son périmètre. Les données importées conservent leur licence d'origine, l'attribution est maintenue.

### Option E — CC-BY-SA 4.0 sur les données (copyleft fort)

Variante de la double licence avec partage à l'identique imposé.

## 4. Décision

**Option D retenue** : double licence séparant clairement code et données, avec préservation des licences amont sur les données importées.

### Périmètre détaillé

| Couche | Licence | Périmètre concret |
|---|---|---|
| **Code** | **Apache 2.0** | Code Python à venir, schémas SQL (`*.sql`), migrations, scripts, workflows GitHub Actions, configurations applicatives, tests, outillage interne. |
| **Documentation projet** | **Apache 2.0** | `README.md`, `CHANGELOG.md`, `BACKLOG.md`, `CLAUDE.md`, ADR (sont des artefacts d'ingénierie liés au code). |
| **Données originales Nephos** | **CC-BY 4.0** | Concepts créés localement (notation, prefLabel/altLabel/hiddenLabel/definition/scopeNote rédigés en interne), schemes Nephos, mappings éditoriaux entre sources amont, traductions françaises. |
| **Données importées des sources standards** | **Licence d'origine** (préservée et documentée) | CF Standard Names → CC-BY 4.0 ; QUDT → CC-BY 4.0 ; NERC BODC → CC-BY 4.0 ; WMO → Resolution 40 (à respecter) ; ECMWF → selon parameter, à vérifier au cas par cas. |

### Attribution

L'attribution est portée par les **mappings dans `concept_mapping`** :

- Chaque concept importé garde un `target_source_id` et un `target_uri` traçables.
- L'export RDF/SKOS conserve les triplets `dcterms:source` ou équivalents pointant vers les ressources amont.
- Le `README.md` et la page de présentation du référentiel listent explicitement les sources amont avec leur licence.

### Compatibilité juridique vérifiée

| Source | Licence | Compatibilité avec CC-BY 4.0 (cible Nephos) |
|---|---|---|
| CF Standard Names | CC-BY 4.0 | Identique, compatibilité totale |
| QUDT | CC-BY 4.0 | Identique, compatibilité totale |
| NERC BODC | CC-BY 4.0 | Identique, compatibilité totale |
| WMO Codes | Resolution 40 | À documenter au cas par cas. Données issues de la liste « essential » sous Resolution 40 sont libres avec attribution. Une partie peut être restreinte ; à filtrer à l'import. |
| ECMWF Param DB | À vérifier | Inventaire à conduire dans `E1-03 / ADR 0005` future réévaluation. |

Aucune incompatibilité majeure pour les sources prioritaires (CF, QUDT, NERC). La compatibilité WMO sera traitée à l'import en filtrant les vocabulaires sous régime restrictif.

### Mise en œuvre

- Fichier **`LICENSE`** à la racine : texte canonique d'Apache 2.0.
- Fichier **`DATA_LICENSE`** à la racine : référence et périmètre CC-BY 4.0, avec lien vers le texte canonique CC.
- **Header** Apache 2.0 dans les fichiers source Python (à mettre en place lors du bootstrap E3-01).
- Le `README.md` mentionne explicitement la double licence et la politique sur les sources amont.
- À chaque export RDF, ajouter un triplet `dcterms:license` sur le `scheme` pointant vers `https://creativecommons.org/licenses/by/4.0/`.

## 5. Conséquences

### Positives

- **(C1) Adéquation juridique** : chaque type d'œuvre est sous la licence faite pour lui.
- **(C2) Compatibilité avec les sources amont** : CC-BY 4.0 est le PGCD des licences des sources prioritaires.
- **(C3) Conformité INSPIRE / Etalab** : CC-BY 4.0 est le standard de fait pour les données ouvertes EU et FR.
- **(C4) Code réutilisable** : Apache 2.0 reste l'une des licences open source les plus permissives, attractive pour les contributeurs.
- **(C5) Attribution préservée** : obligation amont respectée par construction (mappings + métadonnées d'export).

### Négatives / coûts à accepter

- **(C6) Complexité de communication** : il faut expliquer la double licence aux utilisateurs ; une formulation claire dans le README et dans les exports RDF est requise.
- **(C7) Filtrage WMO à l'import** : les données WMO sous régime Resolution 40 restrictif doivent être identifiées et exclues de la couche republiée sous CC-BY. Travail à faire au cas par cas dans le pipeline ETL.
- **(C8) ECMWF à inventorier** : avant d'importer ECMWF Parameter Database, vérifier la licence applicable. Si incompatible, se limiter aux mappings (sans clonage) — cohérent avec la stratégie déjà actée en ADR 0001.
- **(C9) Engagement à perpétuité** : un concept publié sous CC-BY 4.0 ne peut pas être remplacé silencieusement par une version sous une autre licence. Tout changement de politique de licence est rétroactivement complexe.

### Conséquences sur les autres décisions

- **ADR 0001 (stratégie d'import)** : confirmation que le filtrage par licence est un critère de décision « clone vs alignement ». À documenter dans le runbook d'import.
- **Header de fichier** : le bootstrap Python (`E3-01`) inclura un header Apache 2.0 standard dans tous les nouveaux fichiers `.py`.
- **`README.md`** : section Licence à mettre à jour pour pointer vers cet ADR et expliquer la double licence.
- **Exports RDF** : ajouter `dcterms:license` à chaque export.

## 6. Pros / cons des options non retenues

### Option A — Apache 2.0 sur tout

- **Pros** : simplicité, une seule licence à maintenir.
- **Cons** : (a) inadéquation juridique d'Apache 2.0 pour des données (terminologie « source code » non applicable) ; (b) incompatibilité de fait avec les sources amont CC-BY ; (c) signal négatif pour la communauté open data EU. **Rejeté** sur D1, D2.

### Option B — CC-BY 4.0 sur tout

- **Pros** : simplicité, compatibilité données sans réserve.
- **Cons** : (a) CC-BY pour du code Python est très inhabituel — fait fuir les contributeurs habitués à Apache/MIT/BSD ; (b) ambiguïté juridique sur la « notice » à inclure dans chaque fichier source ; (c) limite la réutilisation du code dans des projets sous d'autres licences. **Rejeté** sur D5.

### Option C — CC0 sur tout

- **Pros** : maximum d'adoption, pas d'obligation d'attribution, pas de friction.
- **Cons** : (a) **incompatible avec l'obligation d'attribution des sources amont CC-BY** — Nephos ne peut pas placer en CC0 des données qu'il a obtenues sous CC-BY ; (b) abandonne l'attribution Nephos elle-même, qui est utile pour la traçabilité. **Rejeté** sur D6.

### Option E — CC-BY-SA 4.0 (copyleft fort) sur les données

- **Pros** : garantie que toute réutilisation reste ouverte.
- **Cons** : (a) trop restrictif — les utilisateurs publics et industriels sont réticents au share-alike ; (b) **incompatible** avec les sources CF, QUDT, NERC (qui sont CC-BY simple, sans clause SA) — on ne peut pas durcir une licence amont ; (c) freine l'adoption. **Rejeté** sur D1, D3.

## 7. Validation

Cette décision est validée si :

- [ ] Un fichier `LICENSE` à la racine contient le texte canonique d'Apache 2.0.
- [ ] Un fichier `DATA_LICENSE` à la racine documente la licence CC-BY 4.0 des données originales et la politique sur les données importées.
- [ ] Le `README.md` explique la double licence avec un lien vers cet ADR.
- [ ] Les futurs exports RDF du référentiel incluent un triplet `dcterms:license` sur chaque `scheme` Nephos.
- [ ] Le pipeline ETL identifie les vocabulaires sous régime restrictif WMO et les exclut du clonage local.

## 8. Références

- Apache License 2.0 : https://www.apache.org/licenses/LICENSE-2.0
- Creative Commons Attribution 4.0 International (CC-BY 4.0) : https://creativecommons.org/licenses/by/4.0/
- WMO Resolution 40 : https://library.wmo.int (texte officiel sur la politique de données)
- Open Data Commons — comparatif licences données : https://opendatacommons.org
- ADR 0001 — Adopter SKOS comme socle du référentiel
- ADR 0002 — Python comme stack d'implémentation
