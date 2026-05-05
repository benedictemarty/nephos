# ADR NNNN — Titre court de la décision

> **À renseigner avant publication** : remplacer `NNNN` par le numéro d'ordre suivant et adapter ce gabarit. Supprimer ce bloc une fois fait.
>
> Convention de nommage du fichier : `NNNN-titre-en-kebab-case.md`.

- **Statut** : `Proposé` | `Accepté` | `Rejeté` | `Supersédé par ADR XXXX` | `Déprécié`
- **Date** : `YYYY-MM-DD` (date d'acceptation ou de dernière mise à jour)
- **Décideurs** : sponsor métier, lead dev, autres parties prenantes nommées
- **Étiquettes** : `architecture`, `juridique`, `infra`… (libres, mais cohérentes avec les ADR existants)
- **Lié à** : références aux ADR amont qui contraignent celui-ci
- **Supersède** / **Différé par** : si applicable

---

## 1. Contexte et énoncé du problème

Décrire le contexte qui rend la décision nécessaire. Quels signaux ont déclenché la réflexion ? Qu'est-ce que l'équipe doit trancher ?

Idéalement, un lecteur qui découvre le projet doit comprendre la question en lisant cette section, sans connaître la conversation amont.

## 2. Drivers de décision

Lister les critères qui pèsent dans le choix. Une ligne par driver, avec un identifiant `D1`, `D2`… réutilisé plus loin.

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | … | … |
| D2 | … | … |

## 3. Options considérées

### Option A — …

Description courte.

### Option B — … (retenue)

Description courte.

### Option C — …

Description courte.

## 4. Décision

Écrire la décision en clair. Préciser :

- Le périmètre concret (qu'est-ce qui change, qu'est-ce qui ne change pas).
- Les versions / outils / paramètres figés par la décision.
- Le **hors-périmètre** explicite, pour borner ce que la décision ne couvre **pas**.

## 5. Conséquences

### Positives

- **(C1) …** — bénéfice direct.
- **(C2) …**

### Négatives / coûts à accepter

- **(C3) …** — coût ou contrainte introduite.
- **(C4) …**

### Conséquences sur les autres décisions

- ADR à venir : …
- Items du `BACKLOG.md` impactés : …

## 6. Pros / cons des options non retenues

### Option A — …

- **Pros** : …
- **Cons** : … **Rejeté** sur D1, D3.

### Option C — …

- **Pros** : …
- **Cons** : … **Différé** : à réévaluer si …

## 7. Validation

La décision est validée si :

- [ ] Critère testable 1.
- [ ] Critère testable 2.
- [ ] Critère testable 3.

## 8. Références

- Lien externe vers standard / outil / spécification.
- ADR connexes : …
