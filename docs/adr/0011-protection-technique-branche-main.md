# ADR 0011 — Protection technique de la branche `main` : enforcement de la chaîne de revue

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, mainteneur principal)
- **Étiquettes** : gouvernance, sécurité, ci, gitops
- **Lié à** : `CONTRIBUTING.md` § 1 (chaîne de revue à trois niveaux)

---

## 1. Contexte et énoncé du problème

`CONTRIBUTING.md` § 1 a posé une **politique de gouvernance** : aucun changement n'arrive sur `main` sans la chaîne **auteur → revue agentique → validation humaine senior**. Cette politique est *opposable documentairement* mais reste techniquement contournable tant qu'aucun verrou n'est en place côté plateforme :

- Un mainteneur peut pousser directement sur `main` (avec ou sans intention).
- Un agent IA en autonomie peut, par construction, tenter le même bypass.
- L'historique récent du dépôt confirme le risque : tous les commits du sprint 1 ont été poussés directement sur `main`, ce qui viole déjà la politique posée dans CONTRIBUTING.md.

Il faut donc **un mécanisme technique d'enforcement** qui empêche le contournement, pas seulement le décourage.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Opposabilité technique de la politique** | Une politique non enforcée est un vœu pieux. La règle CONTRIBUTING.md doit pouvoir être appliquée par la plateforme, pas seulement par la bonne volonté. |
| D2 | **Auditabilité** | Toute modification de `main` doit être traçable à une PR avec rapport de revue agentique et approbation humaine identifiée. |
| D3 | **Pas de bypass admin** | Le mainteneur principal lui-même doit être soumis à la règle. Sans cela, l'autonomie agentique reste à risque (un agent qui agit sous l'identité d'un admin contournerait tout). |
| D4 | **Cohérence avec l'écosystème** | Mécanisme natif GitHub privilégié, sans dépendance à des outils tiers. |
| D5 | **Réversibilité opérationnelle** | La configuration doit pouvoir être ajustée (ajout d'un nouveau status check, par exemple) sans refonte. |
| D6 | **Pas de régression de productivité** | L'enforcement doit pouvoir être levé temporairement si nécessaire (incident, urgence justifiée), sans rendre la mécanique impraticable au quotidien. |

## 3. Options considérées

### Option A — Pas d'enforcement technique (statu quo)

`CONTRIBUTING.md` reste politique, aucun verrou plateforme.

### Option B — Branch Protection Rules (« classic ») (retenue)

Mécanisme historique GitHub. Configurable par l'API REST `repos/{owner}/{repo}/branches/{branch}/protection`. Couvre : PR obligatoire, reviews requises, status checks requis, linear history, restriction de push, no admin bypass.

### Option C — Repository Rulesets (« nouvelle » API)

Mécanisme plus récent (2023+) qui généralise les branch protection rules avec un modèle de rule sets gérables au niveau repo ou organisation, importables / exportables, avec audit log enrichi.

### Option D — Hooks pre-receive côté serveur Git auto-hébergé

Si on quittait GitHub pour une instance Git auto-hébergée, on pourrait écrire des hooks `pre-receive` qui appliquent les règles à la racine.

### Option E — GitHub App tierce (CodeOwners stricts, Bulldozer, Mergify…)

Confier l'enforcement à une App externe.

## 4. Décision

**Option B retenue** : Branch Protection Rules « classic » sur la branche `main`, configurées via `gh api` pour garantir la reproductibilité et l'auditabilité.

### Configuration appliquée

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| `required_pull_request_reviews.required_approving_review_count` | `1` | Au moins une revue humaine approuvée. |
| `required_pull_request_reviews.dismiss_stale_reviews` | `true` | Une nouvelle commit invalide les anciennes approbations. |
| `required_status_checks.strict` | `true` | La PR doit être à jour de `main` au moment du merge. |
| `required_status_checks.contexts` | Liste des jobs CI requis | Empêche tout merge sur CI rouge. |
| `enforce_admins` | `true` | **Le mainteneur lui-même est soumis à la règle.** Aucun bypass possible. |
| `required_linear_history` | `true` | Squash ou rebase obligatoire, pas de merge commits — historique propre. |
| `allow_force_pushes` | `false` | Aucune réécriture d'historique. |
| `allow_deletions` | `false` | `main` ne peut pas être supprimée. |
| `required_conversation_resolution` | `true` | Tous les commentaires de revue doivent être résolus avant merge. |

### Status checks requis (à reproduire dans la config)

Issus des workflows `.github/workflows/ci.yml` :

- `Lint, format, hygiene`
- `Type-check (mypy strict)`
- `Security (bandit, pip-audit)`
- `Tests (pytest, Postgres 14)`
- `Tests (pytest, Postgres 16)`
- `Docstring coverage (interrogate)`
- `Build sdist + wheel`

La règle est appliquée **après** vérification que la CI complète passe verte sur `main`, sinon les status checks ne sont pas connus de GitHub.

### Hors-périmètre

- **Signature des commits (`Require signed commits`)** : non activée au démarrage. Coût d'onboarding élevé pour les contributeurs (configuration GPG ou SSH signing). À réévaluer dans un ADR ultérieur si la sensibilité du référentiel le justifie.
- **CODEOWNERS** : non requis tant que le projet n'a qu'un mainteneur. À introduire quand l'équipe s'élargit.
- **Rulesets (option C)** : non retenus pour cet ADR ; migration possible plus tard si on a besoin d'audit log enrichi ou de partage entre repos. Branch protection rules sont suffisantes pour le besoin actuel.
- **Protection des autres branches** : `main` seule pour l'instant. Pas de release branches en place.

### Mode opératoire d'application

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
    "required_approving_review_count": 1,
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

Une fois appliquée, **plus aucun push direct sur `main` n'est possible**, y compris pour le mainteneur. Toute modification, y compris de la documentation ou de la configuration, passe par PR + review.

### Procédure d'urgence (rollback temporaire)

Dans le cas d'un incident grave nécessitant un correctif sans délai (production en panne, faille de sécurité critique), la procédure est :

1. Désactiver temporairement la protection : `gh api repos/benedictemarty/nephos/branches/main/protection --method DELETE`.
2. Pousser le correctif minimal sur `main`.
3. Réactiver la protection avec la même configuration : ré-exécuter la commande `PUT` ci-dessus.
4. Documenter dans une issue ou un journal d'incident pourquoi le bypass a eu lieu, par qui, sur quel commit.

L'auditabilité est garantie par l'historique d'audit GitHub (visible dans les logs du repo et de l'organisation si applicable).

## 5. Conséquences

### Positives

- **(C1) Politique CONTRIBUTING.md devenue opposable techniquement** : aucun bypass possible, pas même par le mainteneur principal.
- **(C2) Auditabilité totale** : chaque modification de `main` correspond à une PR identifiable avec rapport de revue agentique (lorsque l'agent reviewer sera en place, item E1-12) et approbation humaine.
- **(C3) Verrou structurel contre les agents IA en autonomie** : un agent ne peut plus pousser directement, ce qui rend la mécanique de chaîne de revue **techniquement obligatoire**, pas seulement contractuelle.
- **(C4) Historique propre** : `required_linear_history` garantit un `git log --oneline` lisible, sans merge commits parasites.
- **(C5) Configuration reproductible** : la commande `gh api` complète est versionnée dans cet ADR, donc rejouable et auditable.

### Négatives / coûts à accepter

- **(C6) Plus de push direct, même pour les corrections triviales** : toute modification — typo dans le README, ajout d'un commentaire, etc. — passe désormais par une PR. C'est intentionnel mais ralentit légèrement les itérations mineures.
- **(C7) Dépendance à la santé de la CI** : si la CI échoue (faux positif, indisponibilité GitHub Actions), aucun merge n'est possible. À mitiger par la procédure d'urgence (§ 4).
- **(C8) Coût de modification de la configuration** : modifier la liste des status checks requis (par exemple ajouter `Validate ADR format` plus tard) demande de refaire un appel `gh api`, à versionner dans un commit.
- **(C9) Risque de blocage en cas de mise à jour de workflow** : si un nom de job change (par exemple `Tests (pytest, Postgres 14)` devient `Tests (pytest, Postgres 16, 17)`), le status check requis devient introuvable et le merge est bloqué jusqu'à mise à jour de la protection.

### Conséquences sur les autres décisions

- **`CONTRIBUTING.md` § 1** : la chaîne de revue devient techniquement opposable, plus seulement contractuelle. Mention à ajouter dans la section « Branches protégées » qui est déjà indicative.
- **Item `E1-11`** du backlog : passe à ✅ une fois la commande `gh api` exécutée avec succès et la protection vérifiée.
- **ADR à venir** sur l'agent reviewer (`E1-12`) : sa configuration GitHub Actions devra produire un check qui peut, à terme, devenir un status check requis (verrou technique sur la revue agentique en plus de la revue humaine).
- **ADR à venir éventuel** sur la signature des commits, à réévaluer au-delà du démarrage projet.

## 6. Pros / cons des options non retenues

### Option A — Pas d'enforcement technique

- **Pros** : aucun coût opérationnel ; aucune contrainte sur les itérations.
- **Cons** : (a) la politique CONTRIBUTING.md reste un vœu ; (b) un agent IA peut bypass à volonté ; (c) un mainteneur peut bypass par habitude ou inattention. **Rejeté** : invalide sur D1, D3.

### Option C — Repository Rulesets

- **Pros** : audit log enrichi, importable/exportable comme JSON, gérable au niveau organisation, plus adapté à un futur multi-repo.
- **Cons** : (a) API plus récente, moins documentée que les branch protection rules ; (b) certaines fonctionnalités encore en bêta ; (c) bénéfices marginaux à un seul repo ; (d) migration toujours possible plus tard. **Différé** : à réévaluer si Nephos devient une organisation avec plusieurs repos.

### Option D — Hooks pre-receive serveur Git auto-hébergé

- **Pros** : contrôle total côté infrastructure ; pas de dépendance à GitHub.
- **Cons** : (a) impose de quitter GitHub, ou de doubler avec un miroir ; (b) coût d'opération d'un Git auto-hébergé ; (c) hors-sujet pour ce projet hébergé sur GitHub. **Rejeté** sur D4.

### Option E — GitHub App tierce (Bulldozer, Mergify, etc.)

- **Pros** : fonctionnalités avancées de merge queue, batch merging, retry automatique.
- **Cons** : (a) introduit une dépendance externe avec son propre risque (compromission, abandon, changement de modèle économique) ; (b) over-engineering pour un repo à faible cadence de PR ; (c) bénéfices non requis aujourd'hui. **Rejeté** sur D4 et D5.

## 7. Validation

Cette décision est validée si :

- [ ] La commande `gh api repos/benedictemarty/nephos/branches/main/protection --method GET` retourne un objet avec `enforce_admins.enabled = true` et tous les paramètres listés en § 4.
- [ ] Une tentative de `git push` direct sur `main` (par n'importe quel utilisateur, y compris l'admin) est rejetée par GitHub.
- [ ] Une PR ne peut être mergée sans au moins une revue humaine approuvée.
- [ ] Une PR avec CI rouge ne peut pas être mergée.
- [ ] La procédure de rollback temporaire (§ 4) est documentée et reproductible.
- [ ] L'item `E1-11` du backlog est marqué ✅.

## 8. Références

- GitHub REST API — Branch protection : https://docs.github.com/en/rest/branches/branch-protection
- GitHub Docs — About protected branches : https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- `CONTRIBUTING.md` § 1 — Chaîne de revue obligatoire avant merge
- ADR à venir : agent reviewer GitHub Actions (item `E1-12`)
