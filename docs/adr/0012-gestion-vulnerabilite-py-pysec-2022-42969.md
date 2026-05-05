# ADR 0012 — Gestion de la vulnérabilité PYSEC-2022-42969 (paquet `py` 1.11.0, EOL)

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, mainteneur principal, agent reviewer)
- **Étiquettes** : sécurité, dépendances, ci, vulnérabilité, risque
- **Lié à** : ADR 0006 (outillage qualité — incluant `pip-audit`), ADR 0011 (protection branche `main`)

---

## 1. Contexte et énoncé du problème

Lors de la première exécution de la pipeline CI sur PostgreSQL 16, le job `Security (bandit, pip-audit)` a échoué sur la vulnérabilité suivante :

```
Found 1 known vulnerability in 1 package
Name Version ID               Fix Versions
---- ------- ---------------- ------------
py   1.11.0  PYSEC-2022-42969
```

Caractéristiques de cette CVE :

- **Identifiant** : PYSEC-2022-42969 (équivalent CVE-2022-42969).
- **Paquet concerné** : `py`, ancienne bibliothèque utilitaire historiquement séparée de `pytest`.
- **Statut amont** : le paquet `py` est en **fin de vie (EOL)** depuis 2022. Le projet a été archivé. **Aucune version corrigée n'a été publiée et n'en sera publiée.**
- **Nature de la vulnérabilité** : `ReDoS` (Regular Expression Denial of Service) dans le module `py.path.svnwc`, exploité uniquement si l'application appelle ces fonctions sur des chaînes contrôlées par un attaquant.
- **Présence dans Nephos** : transitive (probablement tirée par `pytest-postgresql` ou un autre outil de tests). Pas d'import direct dans le code applicatif.
- **Surface d'attaque réelle dans Nephos** : nulle — le code vulnérable (`py.path.svnwc`) n'est pas dans le chemin d'exécution de Nephos, ni en runtime, ni en CI.

Le job `Security` étant un **status check obligatoire** dans la protection de branche acté par ADR 0011, son échec bloque tout merge sur `main`. Il faut donc une décision explicite : ignorer, retirer la dépendance, ou suspendre temporairement le check.

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Cohérence avec la sévérité réelle** | Une CVE non exploitée dans le contexte d'usage ne doit pas bloquer le projet, mais elle doit être documentée pour ne pas être oubliée. |
| D2 | **Auditabilité** | Tout ignore de CVE doit être traçable : par qui, pourquoi, quand le réévaluer. |
| D3 | **Productivité de la CI** | Bloquer la CI sur une CVE inactionnable rend le verrou contre-productif et incite à des bypass. |
| D4 | **Réversibilité** | L'ignore doit être facile à retirer dès qu'une condition de sortie est remplie. |
| D5 | **Pas de désactivation globale du check** | On ne désactive pas `pip-audit` dans son ensemble — d'autres CVE futures doivent continuer de bloquer. |

## 3. Options considérées

### Option A — Désactiver le job `Security` (suspension globale du check)

Retirer le job du workflow CI ou de la liste des status checks requis.

### Option B — Ignorer cette CVE spécifique avec justification documentée (retenue)

Ajouter `--ignore-vuln PYSEC-2022-42969` à l'invocation de `pip-audit`, avec un commentaire dans le workflow qui explique le motif et la condition de sortie.

### Option C — Retirer la dépendance `py` de l'arbre

Identifier la dépendance qui ramène `py` (probablement `pytest-postgresql` ou un autre paquet) et soit la mettre à jour vers une version qui n'a plus besoin de `py`, soit en changer.

### Option D — Forker / vendoriser `py` avec un patch local

Maintenir une version corrigée localement.

### Option E — Bloquer la CI et attendre une résolution amont

Laisser le job rouge, ne rien fusionner tant que le problème n'est pas résolu.

## 4. Décision

**Option B retenue** : ignorer **explicitement et exclusivement** la CVE PYSEC-2022-42969 dans la commande `pip-audit`, avec :

1. Un commentaire dans `.github/workflows/ci.yml` qui rappelle le motif et la condition de sortie.
2. Le présent ADR comme référence pérenne.

### Configuration appliquée

Dans `.github/workflows/ci.yml`, job `security` :

```yaml
- name: pip-audit (CVE des dépendances)
  # Ignores documentés :
  # - PYSEC-2022-42969 : CVE sur le paquet `py` 1.11.0 (EOL, sans fix
  #   publié), tiré comme transitive sans impact réel (le code
  #   vulnérable n'est pas exécuté par notre pile). À retirer si une
  #   version corrigée de `py` apparaît ou si on parvient à le faire
  #   sortir de l'arbre de deps.
  run: uv run pip-audit --ignore-vuln PYSEC-2022-42969
```

### Conditions de sortie de l'ignore

L'ignore doit être **retiré** dès qu'**au moins une** des conditions suivantes est remplie :

- **CS1** Une version corrigée de `py` est publiée (peu probable étant donné l'EOL, mais à surveiller).
- **CS2** La dépendance qui tire `py` (à identifier précisément) cesse d'en avoir besoin dans une version ultérieure.
- **CS3** Une analyse approfondie démontre qu'un chemin d'exécution réel de Nephos atteint le code vulnérable de `py` (auquel cas l'ignore devient invalide et il faut traiter la vulnérabilité par migration).

### Procédure de réévaluation

- **Revue annuelle** systématique de l'ignore lors de la première semaine de chaque année calendaire.
- **Réévaluation immédiate** à chaque mise à jour majeure de `pytest-postgresql`, `pytest`, ou de tout autre paquet identifié comme amenant `py`.
- **Audit ad hoc** lors de tout incident de sécurité majeur sur l'écosystème Python.

### Hors-périmètre

- **Établir une policy générale d'ignore de CVE** : non couverte par cet ADR. Cet ignore est une décision *spécifique à PYSEC-2022-42969*. Une éventuelle politique générale (par exemple : « toute CVE de sévérité < HIGH non exploitable peut être ignorée pendant 90 jours ») ferait l'objet d'un ADR ultérieur si le besoin émerge.
- **Suppression de la dépendance `py`** : effort de remédiation ouvert (cf. option C non retenue), mais déléguée à un item de backlog (E9-05 à créer) plutôt que traitée dans cet ADR.

## 5. Conséquences

### Positives

- **(C1) CI à nouveau verte** : `Security` redevient un status check passable, qui peut être inclus dans la protection de branche acté par ADR 0011.
- **(C2) Décision auditable** : l'ignore est *explicite, justifié, daté, conditionné*. Pas un bypass silencieux.
- **(C3) Productivité préservée** : aucun blocage sur une CVE inactionnable.
- **(C4) Vigilance maintenue** : les autres CVE continuent de bloquer la CI normalement.
- **(C5) Réversibilité** : retirer une option `--ignore-vuln` du workflow est une opération triviale et locale.

### Négatives / coûts à accepter

- **(C6) Risque résiduel** : si un futur changement du code Nephos introduit un appel à `py.path.svnwc` (très improbable mais possible), la vulnérabilité deviendrait exploitable sans déclencher d'alerte CI. Mitigation : revue annuelle (cf. § 4).
- **(C7) Risque de dérive** : la facilité d'ajouter `--ignore-vuln` peut inciter à ignorer d'autres CVE sans le même soin. Mitigation : tout nouvel ignore doit faire l'objet d'un ADR ou d'une mise à jour de cet ADR (un ignore = une justification documentée).
- **(C8) Maintenance de la documentation** : cet ADR doit être tenu à jour à chaque revue annuelle (statut amont de `py`, identification précise de la dépendance qui le tire).

### Conséquences sur les autres décisions

- **ADR 0011** : la décision de protéger `main` avec `Security` comme status check requis est désormais opérationnelle, puisque le check passe vert.
- **BACKLOG** : item `E9-05` à créer — *« Identifier la dépendance qui ramène `py` 1.11.0 et tenter de la faire sortir de l'arbre (mise à jour amont, alternative, fork) »*. Priorité P2 (qualité, pas urgence).
- **Backlog d'ADR à venir** : si plus d'une CVE doit être ignorée, déclencher un ADR sur la **politique générale** de gestion des vulnérabilités (et arrêter d'ouvrir un ADR par CVE).

## 6. Pros / cons des options non retenues

### Option A — Désactiver le job `Security` globalement

- **Pros** : suppression immédiate du blocage.
- **Cons** : (a) **toute** CVE future est ignorée silencieusement ; (b) régression majeure de la posture de sécurité ; (c) viole l'esprit de l'outillage acté en ADR 0006. **Rejeté** sur D5.

### Option C — Retirer la dépendance `py` de l'arbre

- **Pros** : la solution propre — supprime la cause racine.
- **Cons** : (a) effort d'investigation (qui tire `py` ? trois ou quatre suspects probables) ; (b) peut nécessiter de changer de version d'outil de test, avec impact sur `tests/`; (c) coût/bénéfice défavorable à court terme pour une CVE non exploitable. **Différé** : créé en item de backlog `E9-05` (P2). À reprendre si la CVE devient exploitable ou si une autre CVE de la même origine apparaît.

### Option D — Forker / vendoriser `py` avec un patch local

- **Pros** : contrôle total.
- **Cons** : (a) maintenance d'un fork pour un paquet EOL — engagement perpétuel ; (b) risque de divergence avec d'éventuels usages tiers ; (c) over-engineering. **Rejeté** sur D3, D5.

### Option E — Bloquer la CI et attendre

- **Pros** : posture maximaliste de sécurité.
- **Cons** : (a) blocage indéfini pour une CVE inactionnable ; (b) pousserait au bypass des règles de protection — effet inverse à celui recherché ; (c) attendre quoi ? aucune résolution amont n'est attendue (paquet EOL). **Rejeté** sur D1, D3.

## 7. Validation

Cette décision est validée si :

- [ ] Le job `Security (bandit, pip-audit)` passe vert sur la pipeline CI suivante.
- [ ] Le commentaire dans `.github/workflows/ci.yml` cite cet ADR (ou l'identifiant `PYSEC-2022-42969`) et la condition de sortie.
- [ ] L'item `E9-05` est créé dans le backlog avec priorité P2.
- [ ] La revue annuelle est tracée (au minimum dans une issue ou un commentaire de cet ADR avec un trailer `Reviewed: YYYY-MM-DD`).

## 8. Références

- PYSEC-2022-42969 : https://github.com/pytest-dev/py/issues/287 (discussion amont)
- Avis de sécurité GitHub : https://github.com/advisories/GHSA-w596-4wvx-j9j6
- Statut amont du paquet `py` : https://pypi.org/project/py/ (dernière release 1.11.0, 2022)
- ADR 0006 (outillage qualité — incluant `pip-audit`)
- ADR 0011 (protection technique de la branche `main`)
