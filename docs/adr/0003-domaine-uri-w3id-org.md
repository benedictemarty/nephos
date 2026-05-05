# ADR 0003 — Domaine d'URI : `w3id.org/nephos`

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev)
- **Étiquettes** : architecture, identifiant, sémantique, persistance
- **Lié à** : [ADR 0001](0001-adopter-skos-comme-socle-du-referentiel.md) (SKOS)

---

## 1. Contexte et énoncé du problème

L'ADR 0001 acte que SKOS exige des **URI stables** pour identifier de façon univoque chaque concept du référentiel. Une fois publiés, ces URI ne doivent **plus changer** : ce sont des identifiants persistants sur lesquels les consommateurs (autres systèmes, fichiers RDF, citations scientifiques) s'engagent à long terme.

Le sponsor a explicitement écarté `meteo.fr` comme domaine racine, ce qui élimine l'option la plus naturelle dans le contexte météo francophone. Il faut un domaine alternatif, qui satisfasse :

- **Permanence** : ne pas dépendre d'un compte personnel ou d'un domaine que personne ne s'engage à renouveler à perpétuité.
- **Faible coût** : pas d'investissement infrastructure dédié au démarrage.
- **Alignement avec l'écosystème sémantique web** : convention reconnue par les consommateurs SKOS.
- **Lisibilité** : intelligible pour un humain, pas un identifiant opaque.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Permanence garantie sur le long terme** | Un URI publié ne se révoque pas. La permanence du domaine est le contrat avec les consommateurs. |
| D2 | **Coût et engagement opérationnel** | Pas d'achat de domaine, pas de renouvellement à anticiper. |
| D3 | **Alignement écosystème SKOS** | Les vocabulaires SKOS modernes ont une convention partagée. La reproduire facilite la lecture et la réutilisation. |
| D4 | **Découplage URI / hébergement** | Le contenu réel des URI peut bouger (changement d'hébergeur, de domaine de service, de solution de publication) sans casser les URI. |
| D5 | **Pas de lock-in à un compte ou un projet** | L'identifiant ne doit pas être lié à un compte GitHub, GitLab, ou hébergeur précis. |

## 3. Options considérées

### Option A — `https://meteo.fr/vocab/...`

**Disqualifiée d'emblée** par le sponsor.

### Option B — `https://w3id.org/nephos/...` (retenue)

Service du **W3C Permanent Identifier Community Group**, conçu spécifiquement pour fournir des URI persistants aux ressources sémantiques web. Fonctionne par règles de redirection (`.htaccess`) gérées via pull-request sur le repo GitHub `perma-id/w3id.org`. La permanence est portée par le W3C.

### Option C — `https://purl.org/nephos/...`

Service Persistent URL d'OCLC, pionnier des URI persistants. Service plus ancien que w3id.org, encore vivant mais moins dynamique. Convient mais ne bénéficie pas de la même intégration à l'écosystème sémantique web moderne.

### Option D — Domaine personnalisé (`nephos.org`, `nephos.eu`, `nephos.dev`…)

Achat d'un domaine personnel ou organisationnel, pointage DNS sur un hébergement.

### Option E — `https://benedictemarty.github.io/nephos/...`

GitHub Pages sous le compte personnel actuel. Gratuit, immédiat.

## 4. Décision

**Option B retenue** : adopter **`https://w3id.org/nephos/...`** comme racine canonique de tous les URI du référentiel.

### Pattern d'URI fixé

```
https://w3id.org/nephos/vocab/{scheme}/{notation}
```

- `{scheme}` : code court d'un *concept scheme* (par ex. `grandeurs`, `phenomenes`, `methodes`, `niveaux-verticaux`, `cadences`, `processus`, `evenements`, `especes-chimiques`).
- `{notation}` : code court du concept dans le scheme (par ex. `temperature_air`, `temperature_brillance`, `aod`, `orage`).

Exemples canoniques :

```
https://w3id.org/nephos/vocab/grandeurs/temperature_air
https://w3id.org/nephos/vocab/grandeurs/temperature_brillance
https://w3id.org/nephos/vocab/methodes/min
https://w3id.org/nephos/vocab/niveaux-verticaux/2-m
https://w3id.org/nephos/vocab/phenomenes/orage
```

URI complémentaires :

```
https://w3id.org/nephos/                       page d'accueil du référentiel
https://w3id.org/nephos/vocab/                 index des schemes
https://w3id.org/nephos/vocab/{scheme}/        index des concepts d'un scheme
```

### Règles d'usage

1. **Permanence absolue** : un URI publié n'est jamais réutilisé pour un autre concept. Un concept retiré reste atteignable et signale `skos:retired` (déprecation logique, pas suppression).
2. **Notation stable** : la `notation` d'un concept ne change pas après publication. Si un libellé évolue, l'URI ne suit pas — seuls les `prefLabel` et `definition` évoluent.
3. **Casse minuscule, séparateurs `-` ou `_`** : `temperature_air` (snake_case quand sémantiquement composé d'éléments, ex. import CF) ou `niveaux-verticaux` (kebab-case pour identifiants composés non sémantiques). À fixer dans une convention de nommage interne (item de backlog ultérieur).
4. **Pas d'extension** : les URI ne se terminent pas par `.html`, `.ttl`, `.json` ; la négociation de format se fait via `Accept` HTTP.
5. **Hébergement réel découplé** : le `.htaccess` w3id.org redirige vers une URL dynamique (initialement Skosmos ou un service applicatif Nephos). Cette URL peut changer ; les URI w3id ne bougent pas.

### Mise en œuvre opérationnelle

- **Réservation du préfixe** : ouvrir une PR sur `https://github.com/perma-id/w3id.org` avec un dossier `nephos/` et un `.htaccess` initial (item de backlog `E1-10` à créer).
- **Hébergement initial** : tant que Skosmos n'est pas déployé, le `.htaccess` peut renvoyer vers une page placeholder (par exemple `https://github.com/benedictemarty/nephos`) qui annonce que les URI sont réservés et résolvables prochainement.
- **Hébergement cible** : Skosmos ou équivalent, qui gère la négociation de format (HTML pour navigateur, RDF/Turtle/JSON-LD selon `Accept`).

## 5. Conséquences

### Positives

- **(C1) Permanence portée par le W3C** : engagement institutionnel sur la stabilité, indépendant du compte ou de l'organisation porteuse de Nephos.
- **(C2) Coût zéro** : pas d'achat de domaine, pas de renouvellement annuel à anticiper.
- **(C3) Convention SKOS reconnue** : aligné avec la pratique de schema.org/dpv, Open Definition, Eurovoc-Lex (sous variantes), nombreux thésaurus académiques.
- **(C4) Découplage URI / hébergement** : changement d'hébergeur, de domaine d'organisation, ou de solution applicative sans casser un URI.
- **(C5) Pas de lock-in compte personnel** : indépendant du compte `benedictemarty` ; transmissible à une organisation porteuse plus tard.

### Négatives / coûts à accepter

- **(C6) Dépendance opérationnelle au service w3id.org** : si w3id.org tombe ou est arrêté un jour, les URI deviennent non résolvables (mais restent identifiants — la valeur sémantique est préservée). Risque historique faible : le service existe depuis 2013, soutenu par le W3C PIC Group.
- **(C7) Modification d'URI ou de redirection passe par PR GitHub** : le délai de mise à jour dépend du temps de revue PR sur `perma-id/w3id.org` (quelques jours à quelques semaines). À anticiper, mais sans impact sur la persistance.
- **(C8) Lecture moins « brandée » qu'un domaine propre** : `w3id.org/nephos/...` n'est pas aussi lisible qu'un éventuel `nephos.org/...`. Acceptable au regard des bénéfices C1–C5.
- **(C9) Engagement à perpétuité** : une fois la première publication faite, les URI doivent rester résolvables et le namespace ne doit pas être abandonné. C'est un engagement formel.

### Conséquences sur les autres décisions

- **ADR à venir** : convention de nommage interne (snake_case vs kebab-case, gestion des accents et caractères spéciaux dans les `notation`).
- **ADR à venir** : déploiement de Skosmos ou équivalent comme cible de redirection.
- **BACKLOG** : nouvel item `E1-10` à ajouter — réservation du préfixe `nephos` sur `perma-id/w3id.org` (PR + `.htaccess` initial).

## 6. Pros / cons des options non retenues

### Option C — `purl.org/nephos`

- **Pros** : service ancien, encore vivant, concept identique à w3id.org.
- **Cons** : (a) moins dynamique que w3id.org ; (b) interface de gestion datée ; (c) plus faible alignement avec les pratiques SKOS modernes (qui ont migré vers w3id.org). **Rejeté** au profit de B sur D3.

### Option D — Domaine personnalisé

- **Pros** : meilleure lisibilité, branding plus fort, indépendance totale.
- **Cons** : (a) coût annuel à perpétuité (~5 à 50 €/an selon TLD) ; (b) engagement de renouvellement — une simple omission de paiement détruit la permanence ; (c) risque de squatting si le domaine expire ; (d) lock-in à un propriétaire identifié. **Rejeté** au profit de B sur D1, D2, D5.

### Option E — `benedictemarty.github.io/nephos`

- **Pros** : gratuit, immédiat.
- **Cons** : (a) lié à un compte personnel — non transférable proprement à une organisation ; (b) dépendance forte à GitHub ; (c) branding personnel inadapté à un référentiel destiné à être adopté par d'autres ; (d) GitHub peut désactiver le compte (rare mais possible) ou changer ses règles GitHub Pages. **Rejeté** au profit de B sur D5.

## 7. Validation

Cette décision est validée si :

- [ ] Une PR ouverte et acceptée sur `https://github.com/perma-id/w3id.org` réserve le namespace `nephos`.
- [ ] Un test de résolution depuis un client RDF (par exemple `curl -L -H "Accept: text/turtle" https://w3id.org/nephos/vocab/grandeurs/temperature_air`) renvoie une réponse valide une fois l'hébergement réel en place.
- [ ] L'URI canonique est utilisé partout dans le référentiel (`concept.uri`, exports RDF, mappings) sans variation locale.

## 8. Références

- W3C Permanent Identifier Community Group (PIC) : https://www.w3.org/community/perma-id/
- Service w3id.org : https://w3id.org
- Repo `perma-id/w3id.org` : https://github.com/perma-id/w3id.org
- ADR 0001 — Adopter SKOS comme socle du référentiel
