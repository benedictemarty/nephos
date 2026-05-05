# ADR 0013 — Adopter Claude Code GitHub Action comme agent reviewer

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, mainteneur principal)
- **Étiquettes** : ci, ia, gouvernance, revue, agentique
- **Lié à** : `CONTRIBUTING.md` § 1 (chaîne de revue à trois niveaux), [ADR 0011](0011-protection-technique-branche-main.md) (protection technique de la branche `main`)

---

## 1. Contexte et énoncé du problème

`CONTRIBUTING.md` § 1 acte une **chaîne de revue à trois niveaux** : auteur → revue agentique → validation humaine senior. L'ADR 0011 a posé l'enforcement technique du niveau 3 (branch protection rules + review humaine obligatoire). Le **niveau 2 — la revue agentique automatisée** — reste à implémenter.

L'objectif n'est pas de **remplacer** la revue humaine, mais de **l'éclairer** : produire systématiquement, à l'ouverture de chaque PR, un rapport structuré qui couvre les six critères définis dans `CONTRIBUTING.md` § 1 niveau 2 (cohérence architecturale, qualité du code, sécurité, cohérence documentaire, tests/couverture, risque de régression). Ce rapport ne bloque pas le merge ; il sert d'aide à la décision pour le reviewer humain.

Le sponsor utilise un **abonnement Claude Max**. Cela ouvre un mode de consommation alternatif à la facturation API : un *OAuth token* dédié permet à des automatisations (dont GitHub Actions) de consommer le quota Max sans coût marginal au token, dans la limite très large de l'abonnement.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Connaissance native du contexte projet** | L'agent doit pouvoir lire les ADR, le BACKLOG, le CONTRIBUTING.md et l'historique pour produire un rapport pertinent — pas un commentaire générique. |
| D2 | **Coût opérationnel** | Pas de budget alloué pour une facturation API au token. L'abo Max disponible permet une consommation sans coût marginal. |
| D3 | **Time-to-value** | Mise en place rapide (sprint 2) attendue, sans développement custom long. |
| D4 | **Réversibilité** | Si la qualité ou le format de rapport déçoit, basculer vers une autre solution (custom, CodeRabbit) doit être possible sans surcoût important. |
| D5 | **Pas de droit de merge** | L'agent ne doit jamais court-circuiter la chaîne de revue humaine — pas d'auto-approve, pas d'auto-merge. Lecture du repo + écriture de commentaires uniquement. |
| D6 | **Sécurité (forks, exfiltration de secret)** | Le déclenchement sur PRs depuis des forks ne doit pas exposer le token OAuth Max à du code tiers. |

## 3. Options considérées

### Option A — `anthropics/claude-code-action@v1` (Claude Code GitHub Action officielle) (retenue)

Action GitHub maintenue par Anthropic. Authentification via API key Anthropic *ou* via OAuth token Max (`CLAUDE_CODE_OAUTH_TOKEN`). Lit le contexte du repo, accepte un prompt structuré inline, post un commentaire de PR.

### Option B — CodeRabbit (SaaS tiers)

Setup quasi zero-config via `.coderabbit.yaml`. Modèles propriétaires. Gratuit en plan open source.

### Option C — GitHub Copilot Code Review

Bouton « Request review » Copilot dans l'UI GitHub. Inclus avec abonnement Copilot.

### Option D — Action custom Python + API Claude

Workflow GitHub Action maison qui charge le contexte (ADR, diff, BACKLOG), appelle l'API Claude avec un prompt complet, post un commentaire formaté.

### Option E — Outils OSS communautaires

PR-Agent (Codium), Mentat, autres. Variable en qualité et en maintien.

## 4. Décision

**Option A retenue** : adopter `anthropics/claude-code-action@v1` avec authentification par OAuth token Max.

### Configuration concrète

| Élément | Valeur |
|---|---|
| Action | `anthropics/claude-code-action@v1` |
| Authentification | OAuth token Max via secret `CLAUDE_CODE_OAUTH_TOKEN` |
| Génération du token | `claude setup-token` (commande Claude Code locale, génère un token valide ~1 an) |
| Triggers | `pull_request: [opened, synchronize]` (pas `pull_request_target` — voir D6) + `workflow_dispatch` pour relance manuelle |
| Permissions | `contents: read`, `pull-requests: write`, `issues: write`. **Aucun `merge` ni `actions: write`.** |
| Mode | Automatique (le paramètre `prompt` déclenche le mode immédiat de l'action v1). |
| Bornes d'exécution | `claude_args: --max-turns 5` pour éviter qu'un dialogue dégénère. |
| Concurrence | `concurrency: agent-review-${{ github.ref }}, cancel-in-progress: true` — un nouveau push annule la revue précédente. |

### Format du rapport demandé

L'agent doit poster en commentaire de PR un rapport markdown qui suit **strictement** ce squelette :

```
## 🤖 Revue agentique automatisée

### 1. Cohérence architecturale
[…cohérence avec les ADR pertinents, invariants option A (ADR 0001),
   invariants validation (ADR 0010), URI w3id.org (ADR 0003), multilingue
   (ADR 0004), licences (ADR 0005)…]

### 2. Qualité du code
[…lisibilité, dette introduite, typage, simplicité…]

### 3. Sécurité
[…validation des entrées, secrets, droits accordés (auth, BD, exécution),
   absence de patterns à risque (SQL-injection, code arbitraire, etc.)…]

### 4. Cohérence documentaire
[…CHANGELOG.md à jour, BACKLOG.md synchronisé, ADR référencé si décision
   structurante, README mis à jour si applicable…]

### 5. Tests et couverture
[…tests présents, significatifs, fixtures plausibles, pas de tautologies,
   couverture estimée du code applicatif neuf…]

### 6. Risque de régression
[…impacts sur les autres modules, contrats CLI/API, schéma SQL,
   compatibilité descendante…]

### Verdict
**[À faire passer en revue humaine | À retravailler avant revue humaine | Bloquant — refonte requise]**

[justification synthétique en 2-4 lignes]
```

Le verdict est un **éclairage** pour le reviewer humain, **pas une décision de merge**. Le merge reste conditionné à l'approbation humaine acté en ADR 0011.

### Hors-périmètre

- **Status check requis** : le commentaire de l'agent ne devient **pas** un status check bloquant pour le merge. Conséquence : le verdict « Bloquant — refonte requise » est consultatif, le mainteneur humain peut surcharger. Cette latitude est intentionnelle (cf. règle « rapport agentique = éclairage, pas oracle » de CONTRIBUTING.md § 1 niveau 3).
- **Persistance des rapports en base** : non. Le commentaire vit dans GitHub seulement.
- **Auto-approval / auto-merge** : non, sous aucune condition.
- **Réponses aux commentaires utilisateur** (mode `@claude` interactif) : non au démarrage. Pourra être ajouté plus tard si utile.
- **Revue agentique sur les PRs depuis des forks externes** : volontairement non couverte au démarrage. Le projet n'a pas de PRs depuis des forks aujourd'hui ; lorsque ce cas surviendra, un workflow dédié `pull_request_target` sécurisé devra être ajouté avec contrôle explicite par un mainteneur (label `safe-to-review` posé manuellement).

## 5. Conséquences

### Positives

- **(C1) Le niveau 2 de la chaîne de revue devient opérationnel** sur chaque PR ouverte.
- **(C2) Coût marginal nul** : l'abo Max couvre la consommation. Pas de risque budgétaire.
- **(C3) Connaissance native du contexte** : Claude lit directement les ADR et le BACKLOG dans son contexte d'exécution, pas besoin de pré-charger un knowledge base externe.
- **(C4) Mise en place rapide** : workflow YAML + secret + un test sur la première PR suffisent.
- **(C5) Réversibilité** : changer d'option (vers B, D, ou autre) ne demande que de remplacer le workflow ; le prompt structuré est portable.

### Négatives / coûts à accepter

- **(C6) Souveraineté** : Anthropic est une société américaine. Cette dépendance pèse sur le filtre souveraineté FR/EU acté en ADR 0009. Compromis assumé : l'agent reviewer n'est pas un composant de production, son indisponibilité n'arrête pas le service ; il accélère la revue humaine, mais celle-ci reste possible sans lui.
- **(C7) Quota Max** : si l'abo Max est interrompu, suspendu, ou si le quota est saturé, l'agent ne tourne plus. Mitigation : la chaîne de revue continue (niveaux 1 et 3), seul le niveau 2 disparaît.
- **(C8) Token longue durée** : un token OAuth valide ~1 an stocké en secret. Si compromis, l'attaquant pourrait épuiser le quota Max. Mitigation : rotation annuelle, secret limité au repo (`Repository secret`, pas `Organization`), no `pull_request_target` (cf. D6).
- **(C9) Qualité variable du rapport** : un agent IA peut halluciner, mal nommer un ADR, suggérer des changements non pertinents. La règle « rapport = éclairage, pas oracle » (CONTRIBUTING.md § 1) est précisément là pour absorber ce risque.

### Conséquences sur les autres décisions

- **CONTRIBUTING.md § 1** : niveau 2 désormais opérationnel. À mettre à jour pour pointer vers cet ADR et nommer Claude Code Action comme implémentation actuelle.
- **Item E1-12** du backlog : passe à ✅.
- **ADR à venir** éventuel : si l'agent reviewer devient un check requis (changement de bloquance), le acter dans un nouvel ADR. Pas envisagé au démarrage.
- **Procédure de rotation du token** : à documenter dans un runbook ops futur (item E9-04).

## 6. Pros / cons des options non retenues

### Option B — CodeRabbit

- **Pros** : setup ultra rapide, modèles dédiés à la code review, gratuit en open source.
- **Cons** : (a) ne connaît pas nativement le format MADR ni notre cadre architectural — le prompt custom est plus difficile ; (b) souveraineté également US ; (c) dépendance à un service tiers (cycle de vie produit moins maîtrisé qu'Anthropic, qui est plus établi). **Différé** : option de repli si A déçoit.

### Option C — GitHub Copilot Code Review

- **Pros** : intégration native GitHub, déjà disponible avec un abonnement Copilot.
- **Cons** : (a) trop générique, ne sait pas suivre un cadre ADR ; (b) format de rapport non personnalisable ; (c) souveraineté Microsoft (US). **Rejeté** sur D1.

### Option D — Action custom Python + API Claude

- **Pros** : contrôle total sur le prompt, le format, le contexte chargé. Utile si A ne suffit pas.
- **Cons** : (a) effort de développement initial (~200 lignes Python + workflow) ; (b) maintenance du code à terme ; (c) bénéfices non prouvés tant que A n'a pas été essayé. **Différé** : à reconsidérer si A déçoit après 5–10 PR de test.

### Option E — Outils OSS communautaires

- **Pros** : open source, modifiable.
- **Cons** : (a) qualité et maintien variables ; (b) pas de garantie d'intégration native avec un abo Max ; (c) coût d'évaluation élevé. **Rejeté** sur D3.

## 7. Validation

Cette décision est validée si :

- [ ] Le secret `CLAUDE_CODE_OAUTH_TOKEN` est ajouté au repo (action manuelle du mainteneur).
- [ ] Le workflow `.github/workflows/agent-review.yml` est en place et utilise `anthropics/claude-code-action@v1`.
- [ ] L'ouverture d'une PR (par exemple PR #1 framework ETL) déclenche le workflow et un commentaire de revue agentique structuré apparaît dans la PR sous 5 minutes.
- [ ] Le format du rapport respecte le squelette défini en § 4 (6 sections + verdict).
- [ ] Le verdict ne déclenche **aucune** action de merge ou d'approbation automatique.
- [ ] Le workflow respecte les permissions minimales définies (`contents: read`, `pull-requests: write`, `issues: write` ; rien d'autre).

## 8. Références

- Claude Code GitHub Actions — documentation officielle : https://code.claude.com/docs/en/github-actions.md
- Authentification longue durée Claude Code : https://code.claude.com/docs/en/authentication.md
- Repo de l'action : https://github.com/anthropics/claude-code-action
- `CONTRIBUTING.md` § 1 — Chaîne de revue obligatoire avant merge
- ADR 0011 — Protection technique de la branche `main`
- ADR 0009 — Stratégie d'orchestration ETL (filtre souveraineté FR/EU)
