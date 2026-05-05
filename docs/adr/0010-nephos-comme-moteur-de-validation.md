# ADR 0010 — Étendre le périmètre Nephos aux outils de validation et de qualité de données

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev)
- **Étiquettes** : architecture, périmètre, qualité de données, outillage
- **Lié à** : [ADR 0001](0001-adopter-skos-comme-socle-du-referentiel.md) (option A : concepts uniquement)

---

## 1. Contexte et énoncé du problème

L'ADR 0001 a fixé l'**option A** comme périmètre : Nephos décrit les concepts du domaine météo, ne stocke pas d'observations, ne modélise pas d'instances physiques (stations, instruments, modèles), ne porte pas de fiches de produits de données. Cette borne reste valable.

Une question pratique a émergé en revue : *« si je soumets un fichier GRIB, puis-je avoir un outil qui valide son vocabulaire depuis la base ? »*. Ce cas d'usage révèle un volet absent du périmètre tel qu'il est actuellement formulé : les **outils consommateurs** qui exploitent le référentiel pour qualifier des artefacts externes (fichiers de données scientifiques, dumps, exports) sans les stocker ni étendre le modèle.

Trois constats :

1. Sans ce volet, Nephos reste un *dictionnaire passif* — un corpus structuré que d'autres outils peuvent éventuellement consommer, mais sans utilité immédiate pour ses sponsors.
2. Avec ce volet, Nephos devient un *outil actif de qualité de données* — quelque chose qu'un producteur ou un consommateur de données météo invoque pour vérifier la conformité de ses fichiers, signaler des codes inconnus, suggérer des enrichissements.
3. Le modèle SKOS posé en v4 contient déjà tout ce qu'il faut pour la résolution (`concept_mapping` vers ECMWF Param DB, `cf_standard_name` dans `concept_physical`, `unit_canonical_id`). Il manque uniquement le code applicatif et l'orchestration.

La question est donc : **étendre le périmètre projet** pour englober ces outils, ou **les laisser hors-projet** comme dépendances externes à construire ailleurs ?

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Démontrer la valeur du référentiel** | Un dictionnaire publié sans cas d'usage actif est rarement adopté. Un outil qui valide un GRIB convainc en 30 secondes. |
| D2 | **Cohérence avec l'option A** | Étendre aux outils ne doit pas réintroduire de stockage d'instances, d'observations, ni de gestion de produits. |
| D3 | **Réutilisation du modèle existant** | Le schéma v4 contient déjà ce qu'il faut. Ne pas en faire un schéma supplémentaire. |
| D4 | **Coût d'opération** | Les validateurs ont des dépendances natives (eccodes pour GRIB) qui complexifient le déploiement. |
| D5 | **Effet de levier sur les sources amont** | Implémenter un validateur GRIB exige d'avoir importé ECMWF Param DB et CF Standard Names. Ça aligne les priorités. |
| D6 | **Extension future à d'autres formats** | NetCDF-CF, BUFR, et plus tard CSV/JSON de stations seraient des candidats naturels. La décision doit ouvrir cette voie. |

## 3. Options considérées

### Option A — Statu quo : pas de validateurs dans Nephos

Les outils de validation sont laissés à la charge de tiers ou de projets séparés. Nephos se limite au référentiel et à son API.

### Option B — Étendre le périmètre aux outils consommateurs (retenue)

Nephos absorbe une nouvelle famille de livrables : des **validateurs** qui consomment le référentiel pour qualifier des fichiers externes. Ces outils ne stockent rien, ne créent pas d'instances, ne modifient pas le schéma — ils lisent seulement.

### Option C — Créer un projet jumeau dédié

Un dépôt séparé (`nephos-validators` par exemple) qui dépend de Nephos comme bibliothèque et porte les outils.

## 4. Décision

**Option B retenue** : Nephos étend son périmètre pour englober les outils de validation et de qualité de données, sous **trois invariants stricts** qui préservent l'option A :

1. **Aucun stockage d'instance** : aucun fichier GRIB/NetCDF/BUFR validé n'est conservé en base. Le référentiel ne grossit pas.
2. **Aucune modification automatique du référentiel** : un validateur peut *suggérer* des mappings manquants (en créant une entrée dans `gov.proposals`), mais jamais les appliquer directement. Le workflow de validation reste humain.
3. **Lecture seule sur le référentiel** : les validateurs interrogent les vues métier (`v_concepts_actifs`, `v_concepts_mesurables`) ou les tables (`concept`, `concept_mapping`, `concept_physical`), sans écriture autre que des entrées de proposition.

### Périmètre concret

| Brique | Inclus dans Nephos ? |
|---|---|
| Décodage GRIB / NetCDF / BUFR (extraction de paramètres) | Oui, via dépendances tierces (`eccodes`/`cfgrib`, `xarray`, `pdbufr` ou équivalent) |
| Résolution paramètre externe → concept Nephos | Oui, requêtes sur `concept_mapping` et `concept_physical` |
| Rapport de validation (Rich / JSON / Markdown) | Oui |
| Suggestion d'enrichissement (création de proposition) | Oui, écrit dans `gov.proposals` uniquement |
| Stockage du fichier validé | **Non** |
| Stockage des résultats de validation passés | **Non** au démarrage. Réévaluable plus tard si besoin de tableau de bord historique. |
| Outils de transformation (rewriting d'un GRIB pour le rendre conforme) | **Non** |
| Action GitHub publique pour valider en CI | Oui (item E10-07) |

### Architecture cible (récapitulatif)

```
fichier externe (GRIB, NetCDF, BUFR…)
        │
        ▼  parser format-spécifique (eccodes, xarray, pdbufr…)
liste de paramètres normalisés
        │
        ▼  résolveur Nephos (lecture concept_mapping / concept_physical)
résultats par paramètre : résolu / ambigu / inconnu
        │
        ▼  rapport (Rich / JSON / Markdown) + suggestions optionnelles
sortie utilisateur ou CI
```

### Versions cibles

- Validateurs livrés sous forme de sous-commandes du CLI `nephos validate <format>`.
- Architecture en plugins : un module `nephos.validators.<format>` par format pris en charge, exposant une interface commune (`extract`, `resolve`, `report`).

## 5. Conséquences

### Positives

- **(C1) Cas d'usage démonstratif immédiat** : un sponsor peut lancer `nephos validate grib fichier.grib2` et voir tout de suite la valeur du référentiel.
- **(C2) Boucle de feedback sur les imports** : la commande `--suggest` génère des propositions de mappings manquants, ce qui aide à prioriser le contenu du référentiel par usage réel.
- **(C3) Effet d'entraînement sur les imports** : implémenter le validateur GRIB force à finaliser l'import ECMWF Param DB, ce qui ne pouvait être que bénéfique.
- **(C4) Extension naturelle à d'autres formats** : la même architecture sert pour NetCDF-CF, BUFR, et plus tard pour des formats moins formels (CSV de stations, JSON de capteurs).
- **(C5) Periph. CI / GitHub Action** : un producteur de données peut valider ses fichiers en CI avant publication. Cas d'usage industriel sérieux.

### Négatives / coûts à accepter

- **(C6) Dépendances natives complexes** : `eccodes` est une bibliothèque C de l'ECMWF qui doit être installée au niveau système, pas via pip. Impact sur le `Dockerfile` et la documentation d'installation.
- **(C7) Risque de dérive de périmètre** : la tentation va exister d'ajouter du stockage de résultats de validation, des dashboards, des historiques. Les trois invariants énoncés en § 4 doivent être tenus.
- **(C8) Nouveau volet à maintenir** : un nouvel EPIC (E10) entre dans le backlog ; ressources à provisionner sur 2-3 sprints au moins pour livrer le validateur GRIB minimal.
- **(C9) Charge de tests d'intégration** : valider un validateur GRIB exige des fixtures GRIB licites. À constituer (échantillons publics ECMWF/Météo-France, ou GRIB générés synthétiquement).

### Conséquences sur les autres décisions

- **ADR 0001** : périmètre option A confirmé et précisé — on ajoute un volet « consommateurs » qui n'invalide pas l'exclusion des instances physiques et des observations.
- **BACKLOG** : nouvel **EPIC 10 — Outils de validation et qualité de données** ajouté avec 7 items initiaux (`E10-01` à `E10-07`).
- **ADR à venir** sur le déploiement / containerisation devra prévoir les dépendances natives `eccodes`.
- **Item E4-06** (mappings ECMWF Param DB) devient prérequis fonctionnel du validateur GRIB ; sa priorité monte si le validateur est demandé.

## 6. Pros / cons des options non retenues

### Option A — Statu quo

- **Pros** : périmètre minimal, pas de nouvelles dépendances natives, pas de charge de maintenance.
- **Cons** : (a) Nephos reste un produit documentaire sans usage immédiat ; (b) adoption plus lente faute de démonstration concrète ; (c) chaque consommateur potentiel doit réécrire la logique de résolution dans son propre projet — duplication. **Rejeté** sur D1.

### Option C — Projet jumeau séparé

- **Pros** : sépare proprement les responsabilités (référentiel vs outils) ; permet à chaque projet d'évoluer à son rythme.
- **Cons** : (a) overhead organisationnel pour deux dépôts au démarrage (CI, releases, gouvernance) alors qu'un seul mainteneur les porte ; (b) couplage fort entre les deux — toute évolution du modèle impacte les validateurs ; (c) friction d'installation pour un utilisateur (deux paquets à installer). **Différé** : viable à long terme, prématuré aujourd'hui. À réévaluer si Nephos atteint plusieurs équipes mainteneurs distinctes.

## 7. Validation

Cette décision est validée si :

- [ ] L'EPIC 10 est intégré au backlog avec items priorisés et dépendances explicitées.
- [ ] Les trois invariants (pas de stockage, pas de modification automatique, lecture seule) sont rappelés en tête du module `nephos.validators` lors de son implémentation.
- [ ] Le premier validateur livré (GRIB, item E10-02) prouve la chaîne de bout en bout : décodage → résolution → rapport.
- [ ] Le mode `--suggest` (item E10-04) crée bien des entrées dans `gov.proposals` et n'écrit nulle part ailleurs.
- [ ] Une action GitHub réutilisable est publiée (item E10-07) et démontre l'usage en CI sur un repo tiers.

## 8. Références

- ECMWF eccodes (décodeur GRIB/BUFR de référence) : https://confluence.ecmwf.int/display/ECC
- cfgrib (binding xarray-friendly) : https://github.com/ecmwf/cfgrib
- pygrib (binding alternatif) : https://github.com/jswhit/pygrib
- pdbufr (BUFR via pandas) : https://github.com/ecmwf/pdbufr
- ADR 0001 — Adopter SKOS comme socle du référentiel
- ADR 0002 — Python comme stack d'implémentation
