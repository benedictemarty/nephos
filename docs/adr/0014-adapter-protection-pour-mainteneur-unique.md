# ADR 0014 — Adapter la chaîne de revue au cas du mainteneur unique

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (mainteneur principal)
- **Étiquettes** : gouvernance, revue, ci, exception
- **Lié à** : [ADR 0011](0011-protection-technique-branche-main.md) (qu'il **supersède partiellement**), [ADR 0013](0013-agent-reviewer-claude-code-action.md), `CONTRIBUTING.md` § 1
- **Supersède partiellement** : ADR 0011, sur le seul paramètre `required_pull_request_reviews.required_approving_review_count`.

---

## 1. Contexte et énoncé du problème

L'ADR 0011 a posé une protection stricte de la branche `main` exigeant au minimum **une approbation humaine** par PR (`required_approving_review_count: 1`), avec `enforce_admins: true` (le mainteneur lui-même est soumis à la règle).

Cette configuration s'est révélée **inapplicable** dans le contexte actuel du projet, dès la première tentative de merge :

- Le projet n'a qu'**un seul compte mainteneur GitHub** (`benedictemarty`).
- Toutes les PR sont créées par ce compte (que ce soit en saisie humaine ou via l'agent IA en autonomie qui utilise le `gh` token du mainteneur).
- **GitHub interdit l'auto-approbation** : un compte ne peut pas approuver une PR qu'il a créée. C'est une règle plateforme, pas un paramètre de configuration.

**Conséquence directe** : aucune PR ne peut être mergée tant que l'ADR 0011 reste appliqué tel quel et que le projet reste à un seul mainteneur. PR #1 (framework ETL, CI verte) en a fait la démonstration concrète : 7 status checks verts, 0 approbation possible, blocage permanent.

C'est un **trou architectural** dans l'ADR 0011 : la décision n'avait pas pris en compte que le pré-requis à `required_approving_review_count: 1` est l'existence d'au moins deux comptes mainteneurs distincts. Tant que le projet est un repo solo, cette exigence est inopposable.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Préserver l'esprit de la chaîne de revue** | La chaîne à 3 niveaux de CONTRIBUTING.md § 1 reste l'horizon. La dégradation actuelle doit être documentée et **réversible** quand un second mainteneur entre. |
| D2 | **Maintenir l'opposabilité des autres verrous** | Status checks requis, linear history, no force push, no deletion, conversation resolution, `enforce_admins` — tout cela doit rester. Seul le compteur de reviews change. |
| D3 | **Pas de bypass déguisé** | La solution ne doit pas créer un précédent de bypass facile. Une décision documentée et amendable vaut mieux qu'un contournement répété de la procédure d'urgence. |
| D4 | **Transition future automatisable** | Quand un second mainteneur arrive, la transition vers `required_approving_review_count: 1` doit être triviale et explicitée. |
| D5 | **Compensation par d'autres verrous** | L'absence de la « deuxième paire d'yeux humaine » doit être compensée autant que possible par les autres niveaux de la chaîne (CI verte obligatoire, agent reviewer ADR 0013, autodiscipline du mainteneur). |

## 3. Options considérées

### Option A — Statu quo ADR 0011 (refusé)

Garder `required_approving_review_count: 1` et exiger qu'un second compte humain existe pour approuver.

### Option B — Bypass d'urgence répété (refusé)

Désactiver/réactiver la protection à chaque merge via la procédure d'urgence d'ADR 0011 § 4.

### Option C — Inviter un second compte GitHub (différé)

Ajouter un collaborateur (humain ami, ou second compte du mainteneur) pour permettre l'approbation à deux comptes distincts.

### Option D — Amender ADR 0011 pour le cas mainteneur unique : `required_approving_review_count = 0` (retenue)

Ramener temporairement le compteur de reviews à 0, conserver tous les autres verrous, documenter explicitement la dégradation et la condition de retour automatique à 1.

### Option E — Désactiver entièrement la protection (refusé d'office)

Trivial et stupide.

## 4. Décision

**Option D retenue** : amender la configuration de protection `main` en mettant **`required_approving_review_count: 0`** **tant que le projet a un seul mainteneur GitHub**. Tous les autres paramètres d'ADR 0011 sont **conservés sans modification**.

### Configuration appliquée

```bash
gh api repos/benedictemarty/nephos/branches/main/protection \
  --method PUT \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint, format, hygiene",
      "Type-check (mypy strict)",
      "Security (bandit, pip-audit)",
      "Tests (pytest, Postgres 14)",
      "Tests (pytest, Postgres 16)",
      "Docstring coverage (interrogate)",
      "Build sdist + wheel"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

### Ce qui change vs ADR 0011

| Paramètre | ADR 0011 | ADR 0014 (présent) |
|---|---|---|
| `required_approving_review_count` | **1** | **0** |
| Tous les autres paramètres | inchangés | inchangés |

### Ce qui est préservé

- ✅ **PR obligatoire** (pas de push direct sur `main`).
- ✅ **7 status checks verts requis** : lint, type-check, security, tests Postgres 14, tests Postgres 16, docstring coverage, build.
- ✅ **`enforce_admins: true`** : le mainteneur n'est pas dispensé.
- ✅ **`required_linear_history`** : squash ou rebase, pas de merge commits.
- ✅ **`allow_force_pushes: false`**, **`allow_deletions: false`**.
- ✅ **`required_conversation_resolution: true`**.
- ✅ **`dismiss_stale_reviews: true`** : si un jour une review est posée puis le code change, elle est invalidée (utile en transition vers 1 review).

### Conditions de retour à `required_approving_review_count: 1`

La transition est **automatique** dès qu'**au moins un** de ces signaux est avéré :

- **CR1** Un second mainteneur GitHub (humain ou bot d'orga validé) est ajouté au repo avec droits d'approbation.
- **CR2** Le projet rejoint une organisation GitHub multi-membres avec d'autres mainteneurs actifs.
- **CR3** Un agent reviewer obtient le droit d'approbation par décision explicite (peu probable car contraire à l'ADR 0013, mais à mentionner pour exhaustivité).

Dès que CR1 ou CR2 est avéré, le mainteneur applique la commande `gh api … PUT` d'ADR 0011 (compteur à 1) et ferme cet ADR (statut → `Supersédé par ADR 0011`).

### Compensations à la dégradation

L'absence de la « deuxième paire d'yeux humaine » est partiellement compensée par :

| Compensation | Acté par | Effet |
|---|---|---|
| 7 status checks requis (lint, types, sécu, tests, build) | ADR 0011 (préservé) | Aucun merge sur CI rouge |
| Agent reviewer (rapport structuré sur chaque PR) | ADR 0013 | Lecture critique automatisée publique |
| `enforce_admins: true` (préservé) | ADR 0011 | Le mainteneur reste soumis aux status checks |
| Auto-discipline et auto-revue par le mainteneur | Pratique | Lecture du diff complet avant chaque merge |

Ces compensations **ne remplacent pas** une review humaine indépendante, mais elles maintiennent un filet de sécurité non négligeable.

### Hors-périmètre

- **Politique de qualité de l'auto-revue** : pas formalisée (pas de checklist obligatoire avant merge solo). Si la dérive devient observable, on rouvre.
- **Branch protection sur les autres branches** : `main` seule, comme dans ADR 0011.
- **Modification du CODEOWNERS** : non, pas de CODEOWNERS au démarrage.

## 5. Conséquences

### Positives

- **(C1) Le projet redevient mergeable.** PR #1 (framework ETL), PR #2 (agent reviewer), futures PRs débloquées.
- **(C2) Pas de bypass répété.** L'ADR 0011 § 4 (procédure d'urgence) est préservée pour ce qu'elle est : un dernier recours, pas une routine.
- **(C3) Les autres verrous tiennent.** Aucun merge ne passe sur CI rouge ; aucune écriture force-push n'est tolérée ; aucune suppression de `main` n'est possible.
- **(C4) Transition future explicitée.** Quand un second mainteneur entre, la commande de retour à `1` est documentée et la décision se ferme automatiquement.
- **(C5) Décision auditable.** L'historique du repo gardera trace de l'amendement et de ses conditions de retour.

### Négatives / coûts à accepter

- **(C6) Un mainteneur peut merger ses propres PR sans review humaine.** C'est précisément le coût de l'option D. La règle CONTRIBUTING.md § 1 niveau 3 dit *« examen matériel par un mainteneur senior »* ; dans le cas solo, le « mainteneur senior » et l'« auteur » sont la même personne — la dégradation est inhérente au cas d'usage.
- **(C7) Risque de dérive de qualité** si l'auto-discipline relâche. Mitigation : l'agent reviewer (ADR 0013) post un rapport critique externe, et les status checks restent un filet technique.
- **(C8) Les contributions externes** (PR depuis un fork) restent traitées par la même règle ; un contributeur externe peut donc voir sa PR mergée par le mainteneur seul. Pour ce cas-là, la pratique recommandée est que le mainteneur applique une auto-discipline renforcée (lecture explicite + commentaire public sur la PR avant merge). Pas formalisé dans cet ADR.
- **(C9) Cohérence partielle avec CONTRIBUTING.md § 1.** La section niveau 3 reste écrite comme si une review humaine indépendante existait. Mise à jour à apporter pour reconnaître la dégradation actuelle.

### Conséquences sur les autres décisions

- **CONTRIBUTING.md § 1** : ajouter une note explicite sur le cas mainteneur unique, pointant vers cet ADR.
- **ADR 0011** : son § 4 (configuration appliquée) est partiellement obsolète sur la valeur de `required_approving_review_count`. Le reste tient.
- **ADR 0013** (agent reviewer) : son rôle de « deuxième paire d'yeux » devient particulièrement important dans cette dégradation. Renforcement implicite de sa pertinence.
- **BACKLOG** : nouvel item `E1-13` à créer — *« Documenter la procédure de retour à require_approving_review_count=1 lorsqu'un second mainteneur entre »* (P2, à activer quand CR1 ou CR2 est observé).

## 6. Pros / cons des options non retenues

### Option A — Statu quo ADR 0011

- **Pros** : préserve l'esprit de la chaîne de revue à 100 %.
- **Cons** : (a) bloquant en pratique tant qu'il n'y a qu'un mainteneur ; (b) tend à pousser au bypass répété de la procédure d'urgence, qui est exactement l'inverse de la posture voulue. **Rejeté** sur D1 (ne préserve pas la chaîne — il l'abolit en bloquant le projet) et D3 (incite au bypass).

### Option B — Bypass d'urgence répété

- **Pros** : aucun changement de configuration, conserve l'ADR 0011 tel quel.
- **Cons** : (a) banalise une procédure d'urgence ; (b) ne laisse pas de trace formelle d'amendement ; (c) chaque bypass crée une fenêtre où aucune protection n'est active. **Rejeté** sur D3.

### Option C — Inviter un second mainteneur

- **Pros** : c'est **la vraie solution**. Permet la chaîne de revue à 3 niveaux pleine.
- **Cons** : (a) demande une action écosystème (trouver un humain, ou créer un second compte GitHub) ; (b) hors du périmètre maîtrisable par cet ADR ; (c) doit de toute façon être préparée par une transition documentée — précisément ce que cet ADR pose en condition de retour CR1/CR2. **Différé** : à activer quand un humain volontaire se manifeste, ou à reconsidérer si le projet attire des contributeurs externes.

### Option E — Désactiver entièrement la protection

- **Pros** : aucun.
- **Cons** : tout. **Rejeté** d'office.

## 7. Validation

Cette décision est validée si :

- [ ] La commande `gh api repos/benedictemarty/nephos/branches/main/protection --method GET` retourne `required_pull_request_reviews.required_approving_review_count: 0` et tous les autres paramètres conformes à ADR 0011.
- [ ] PR #1 (framework ETL) peut être mergée par `gh pr merge --squash` sans approbation, mais uniquement après que les 7 status checks sont verts.
- [ ] Une tentative de push direct sur `main` reste rejetée.
- [ ] Une tentative de merge sur PR avec un status check rouge reste rejetée.
- [ ] Le mainteneur applique l'auto-discipline documentée dans cet ADR (lecture du diff complet avant merge).

## 8. Références

- ADR 0011 — Protection technique de la branche `main`
- ADR 0013 — Adopter Claude Code GitHub Action comme agent reviewer
- `CONTRIBUTING.md` § 1 — Chaîne de revue obligatoire avant merge
- GitHub docs — *About protected branches* : https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub docs — *Required reviews* (limitation auto-approbation) : https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews
