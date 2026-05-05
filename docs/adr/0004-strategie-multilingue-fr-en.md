# ADR 0004 — Stratégie multilingue : FR + EN obligatoires sur les concepts publiés

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev, équipe curation à venir)
- **Étiquettes** : architecture, internationalisation, qualité, gouvernance
- **Lié à** : [ADR 0001](0001-adopter-skos-comme-socle-du-referentiel.md) (SKOS), [ADR 0002](0002-python-comme-stack-dimplementation.md) (Python)

---

## 1. Contexte et énoncé du problème

L'ADR 0001 acte l'adoption de SKOS, modèle nativement multilingue : chaque concept peut porter plusieurs `prefLabel`, `altLabel`, `hiddenLabel`, `definition`, `scopeNote` etc. dans plusieurs langues, identifiées par un tag de langue (`fr`, `en`, `de`, `es`, …).

La question : **quelle politique linguistique** Nephos applique-t-il ?

- Les sources amont (CF Standard Names, QUDT, WMO, ECMWF) sont **majoritairement en anglais**. NERC BODC est partiellement multilingue (mais surtout EN).
- Le public cible francophone (et l'ancrage du projet) demande un accès en **français**.
- Une publication INSPIRE / EU à terme exigera au minimum **FR + EN**.
- Une politique trop large (« multilingue ouvert sans contrainte ») produit un référentiel à qualité variable. Une politique trop stricte (« toutes les langues sur tout ») bloque la publication.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Interopérabilité internationale** | Les sources, les consommateurs externes, et les standards (CF, WMO) parlent EN. Un EN solide est non négociable. |
| D2 | **Accessibilité francophone** | Public cible et ancrage projet francophones. Le référentiel doit être consultable en français. |
| D3 | **Coût de traduction** | Les sources arrivent en EN ; traduire ~5500 concepts CF demanderait un effort considérable. La politique doit être réaliste. |
| D4 | **Qualité éditoriale** | Une traduction baclée nuit plus qu'elle n'aide. Mieux vaut un FR partiel mais correct qu'un FR exhaustif et fautif. |
| D5 | **Niveau d'exigence par maturité du concept** | Un concept en `draft` n'a pas les mêmes obligations qu'un concept `published`. La contrainte doit être proportionnée. |

## 3. Options considérées

### Option A — FR seul

Tout le référentiel en français exclusivement, EN optionnel.

### Option B — EN seul

Tout en anglais (langue des sources amont), FR optionnel.

### Option C — FR + EN obligatoires sur les concepts publiés (retenue)

Les `prefLabel@fr` et `prefLabel@en` sont obligatoires pour qu'un concept passe au statut `published`. Les autres types de label, les notes, et les autres langues sont opportunistes.

### Option D — Multilingue ouvert sans contrainte

Toute langue acceptée, aucune obligation.

### Option E — FR + EN partout, dès `draft`

Contrainte stricte dès la création.

## 4. Décision

**Option C retenue** : `prefLabel@fr` **et** `prefLabel@en` obligatoires pour la publication d'un concept ; autres langues, autres types de label et notes en best effort.

### Politique linguistique précisée

| Élément | Règle | Périmètre |
|---|---|---|
| `prefLabel@en` | **Obligatoire** | Tout concept publié. Hérité de la source si import EN, sinon créé manuellement. |
| `prefLabel@fr` | **Obligatoire** | Tout concept publié. Traduit lors du passage `proposed → approved` ou créé directement pour les concepts locaux. |
| `prefLabel` autres langues (`de`, `es`, `it`, `nl`, `pt`…) | Acceptées | Si la source les fournit (rare). Jamais traduites manuellement. |
| `altLabel`, `hiddenLabel` | Best effort | Tagués avec leur langue. Aucune obligation de couverture. |
| `definition`, `scopeNote`, `example`, `historyNote` | Best effort | EN si la source la fournit ; FR ajouté manuellement à mesure. Pas obligatoire pour la publication, fortement recommandé pour les concepts à fort usage. |

### Cycle de vie linguistique

```
[ draft ]      → minimum un prefLabel dans une langue (souvent EN, hérité de l'import)
[ proposed ]   → idem
[ approved ]   → prefLabel@fr ET prefLabel@en présents
[ published ]  → idem (la contrainte SHACL bloque sinon)
[ deprecated ] → contraintes inchangées (pas de relâchement)
[ retired ]    → idem
```

La traduction française devient une **étape du workflow de validation** (revue par un curateur), pas une étape technique automatisée. Pas de traduction machine (DeepL, Google Translate) appliquée silencieusement — risque trop élevé sur des termes techniques météo.

### Conséquences sur le modèle

- La table `concept_label` portera (au moins) :
  - `concept_id`, `lang` (BCP 47 : `fr`, `en`, `de`…), `kind` (`pref`, `alt`, `hidden`), `value`.
  - **Contrainte** : `UNIQUE (concept_id, lang) WHERE kind = 'pref'` — un seul prefLabel par langue.
- Une **shape SHACL** Nephos vérifie qu'un concept publié a au moins un `prefLabel@fr` et un `prefLabel@en` distincts, non vides, non identiques au `notation` brut.
- L'API exposera la sélection de langue par paramètre (`?lang=fr`) ou par `Accept-Language`, avec fallback sur EN si la langue demandée n'est pas disponible.

### Identifiants de langue

- Code de langue conforme à **BCP 47** (RFC 5646), aligné avec SKOS. Cas courants : `fr`, `en`, `de`, `es`, `it`. Pas de variantes régionales par défaut (`fr-CA`, `en-GB`) sauf si la source les apporte explicitement et qu'elles diffèrent du parent.

## 5. Conséquences

### Positives

- **(C1) Couverture FR garantie** sur tous les concepts publiés — accessibilité francophone réelle.
- **(C2) Couverture EN garantie** — interopérabilité internationale immédiate, alignement naturel avec les sources amont.
- **(C3) Coût de traduction maîtrisé** : la contrainte ne s'applique qu'au franchissement du seuil `published`, pas à `draft`. La traduction devient une étape du workflow contrôlée par les curateurs.
- **(C4) Pas de qualité dégradée** : pas de traduction machine silencieuse ; chaque FR est validé par un humain.
- **(C5) Alignement INSPIRE / EU** : FR + EN est le minimum attendu pour publication officielle européenne.
- **(C6) Modèle SKOS pleinement exploité** : le multilinguisme natif n'est pas désactivé par une politique trop restrictive.

### Négatives / coûts à accepter

- **(C7) Volume de traduction non négligeable** : ~5500 concepts CF à traduire FR. Mitigation : étalement sur plusieurs sprints, priorisation par usage attendu (concepts météo de surface avant concepts de chimie atmosphérique avancée).
- **(C8) Contrainte SHACL bloque la publication** : un concept sans FR ne peut pas passer `published`. Ce *blocage est intentionnel* mais il faut un workflow clair pour gérer la file d'attente de traduction.
- **(C9) Risque de pression sur les curateurs francophones** : la traduction ne peut pas être déléguée massivement. Solution : commencer par les concepts à valeur métier élevée, accepter qu'une partie du référentiel reste en `approved` (non publié) plus longtemps.
- **(C10) Pas de couverture systématique des langues UE étendues** (DE, ES, IT…) : politique acceptée, mais l'absence de DE peut poser question pour DWD ou MeteoSwiss en consommateurs potentiels. Réévaluable plus tard si demande explicite.

### Conséquences sur les autres décisions

- **ADR 0001 (SKOS)** : confirmé, la table `concept_label` est multilingue dès la phase 1.
- **Ressources curation** : un volet « traduction FR » émerge dans le workflow ; un curateur dédié ou un comité linguistique sera utile (à acter en ADR 0007 sur l'outil de curation).
- **BACKLOG** : item `E5-02` (shapes SHACL Nephos) doit inclure la règle « publication requiert FR + EN ».
- **ADR à venir** : politique d'extension à DE / ES si demande consommateur émerge.

## 6. Pros / cons des options non retenues

### Option A — FR seul

- **Pros** : simplicité, coût de traduction nul depuis EN.
- **Cons** : (a) inutilisable par consommateurs internationaux ; (b) incompatible avec import direct des sources EN (il faudrait traduire chaque concept à l'import) ; (c) bloque les publications INSPIRE/EU. **Rejeté** sur D1.

### Option B — EN seul

- **Pros** : alignement total avec les sources, coût nul, interopérabilité maximale.
- **Cons** : (a) inaccessibilité francophone ; (b) n'honore pas l'ancrage projet ; (c) ne permet pas une appropriation par les communautés métier locales. **Rejeté** sur D2.

### Option D — Multilingue ouvert sans contrainte

- **Pros** : flexibilité totale, pas de blocage.
- **Cons** : (a) qualité variable ; (b) certains concepts publiés sans FR ni EN deviennent inutilisables pour la moitié des publics ; (c) impossible de garantir une couverture minimale. **Rejeté** sur D4.

### Option E — FR + EN partout, dès `draft`

- **Pros** : qualité maximale, jamais de concept publié incomplet.
- **Cons** : (a) bloque l'import de masse — un import CF ne peut pas créer ~5500 concepts en `draft` sans traduction ; (b) inverse la logique de la pipeline d'import ; (c) coût de traduction immédiat insoutenable. **Rejeté** sur D3.

## 7. Validation

Cette décision est validée si :

- [ ] La table `concept_label` impose `UNIQUE (concept_id, lang) WHERE kind = 'pref'`.
- [ ] Une shape SHACL Nephos vérifie qu'un concept en `published` a au moins un `prefLabel@fr` et un `prefLabel@en` distincts, non vides.
- [ ] La validation à l'import distingue les violations bloquantes (un `draft` peut passer sans FR) des violations bloquantes pour `published`.
- [ ] Une commande `nephos validate --lang-coverage` rapporte les concepts approuvés sans FR (file d'attente de traduction).
- [ ] L'API expose la négociation de langue (`?lang=fr` ou `Accept-Language`) avec fallback sur EN.

## 8. Références

- BCP 47 — Tags for Identifying Languages : https://www.rfc-editor.org/info/bcp47
- W3C SKOS — Multilingual Labels : https://www.w3.org/TR/skos-primer/#secmultilingual
- INSPIRE Metadata Regulation (multilinguisme exigé) : https://inspire.ec.europa.eu
- ADR 0001 — Adopter SKOS comme socle du référentiel
- ADR 0002 — Python comme stack d'implémentation
