-- ============================================================
-- NEPHOS — Schéma v4 (SKOS)
-- ------------------------------------------------------------
-- Référentiel de métadonnées météorologiques modélisé sur
-- SKOS Core (W3C, https://www.w3.org/TR/skos-reference/).
--
-- Architecture en trois étages :
--   gov.*    — gouvernance (users, rôles, workflow, audit, imports, proposals)
--   vocab.*  — taxonomie SKOS (scheme, concept, labels, relations, notes, mappings)
--   physical — extension de typage physique (concept_physical, unite, conversions)
--              -- réside dans vocab.* pour cohérence d'imports
--
-- Toutes les entités vocab.* portent les colonnes communes :
--   - workflow : status (draft → proposed → approved → published → deprecated → retired)
--   - temporalité : valid_from, valid_to
--   - versionnement : version
--   - audit : created_by/at, modified_by/at
--   - traçabilité d'import : import_source_id, import_version,
--                            last_synced_at, has_local_override
--
-- Conventions :
--   - URI canonique : https://w3id.org/nephos/vocab/{scheme}/{notation}  (ADR 0003)
--   - Multilingue obligatoire FR + EN sur publié                         (ADR 0004)
--   - Licence des données originales : CC-BY 4.0                         (ADR 0005)
--
-- Cible : PostgreSQL 14+.
-- ============================================================

DROP SCHEMA IF EXISTS gov   CASCADE;
DROP SCHEMA IF EXISTS vocab CASCADE;

CREATE SCHEMA gov;
CREATE SCHEMA vocab;

SET search_path = vocab, gov, public;


-- ============================================================
-- 1. GOUVERNANCE (gov.*)
-- ============================================================

CREATE TABLE gov.users (
  user_id        BIGSERIAL PRIMARY KEY,
  username       TEXT UNIQUE NOT NULL,
  full_name      TEXT,
  email          TEXT UNIQUE,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE gov.users IS 'Utilisateurs du référentiel. Le compte ''system'' (id=1) est utilisé pour les imports automatiques.';

CREATE TABLE gov.roles (
  role_id        SMALLSERIAL PRIMARY KEY,
  code           TEXT UNIQUE NOT NULL,
  libelle        TEXT NOT NULL,
  description    TEXT
);

CREATE TABLE gov.user_roles (
  user_role_id   BIGSERIAL PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES gov.users(user_id) ON DELETE CASCADE,
  role_id        SMALLINT NOT NULL REFERENCES gov.roles(role_id),
  scope          TEXT,
  granted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  granted_by     BIGINT REFERENCES gov.users(user_id)
);
CREATE UNIQUE INDEX uq_user_role_scope ON gov.user_roles(user_id, role_id, COALESCE(scope, ''));

CREATE TABLE gov.statuses (
  status         TEXT PRIMARY KEY,
  ordre          SMALLINT NOT NULL,
  description    TEXT
);

CREATE TABLE gov.import_sources (
  import_source_id  BIGSERIAL PRIMARY KEY,
  code              TEXT UNIQUE NOT NULL,
  nom               TEXT NOT NULL,
  url               TEXT,
  description       TEXT,
  format            TEXT,
  default_license   TEXT
);

CREATE TABLE gov.imports (
  import_id         BIGSERIAL PRIMARY KEY,
  import_source_id  BIGINT NOT NULL REFERENCES gov.import_sources(import_source_id),
  version           TEXT NOT NULL,
  imported_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  imported_by       BIGINT REFERENCES gov.users(user_id),
  nb_entites        INTEGER,
  nb_creations      INTEGER,
  nb_modifications  INTEGER,
  nb_skipped        INTEGER,
  notes             TEXT,
  status            TEXT NOT NULL DEFAULT 'success'
                      CHECK (status IN ('success','partial','failed','aborted'))
);

CREATE TABLE gov.audit_log (
  audit_id          BIGSERIAL PRIMARY KEY,
  schema_name       TEXT NOT NULL,
  table_name        TEXT NOT NULL,
  entity_id         BIGINT NOT NULL,
  action            TEXT NOT NULL,
  old_data          JSONB,
  new_data          JSONB,
  changed_columns   TEXT[],
  performed_by      BIGINT REFERENCES gov.users(user_id),
  performed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_entity ON gov.audit_log(schema_name, table_name, entity_id);
CREATE INDEX ix_audit_time   ON gov.audit_log(performed_at DESC);

CREATE TABLE gov.proposals (
  proposal_id       BIGSERIAL PRIMARY KEY,
  target_schema     TEXT NOT NULL,
  target_table      TEXT NOT NULL,
  target_entity_id  BIGINT,
  action            TEXT NOT NULL CHECK (action IN ('CREATE','UPDATE','DEPRECATE','RETIRE')),
  proposed_payload  JSONB NOT NULL,
  current_payload   JSONB,
  justification     TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'submitted'
                      CHECK (status IN ('submitted','under_review','approved','rejected','withdrawn','applied')),
  created_by        BIGINT NOT NULL REFERENCES gov.users(user_id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by       BIGINT REFERENCES gov.users(user_id),
  reviewed_at       TIMESTAMPTZ,
  review_comment    TEXT,
  applied_at        TIMESTAMPTZ
);
CREATE INDEX ix_proposals_status ON gov.proposals(status);
CREATE INDEX ix_proposals_target ON gov.proposals(target_schema, target_table, target_entity_id);


-- ============================================================
-- 2. UNITÉS (vocab.unite)
--    Couche typage physique — alignée QUDT à terme via mappings.
-- ============================================================

CREATE TABLE vocab.unite (
  unite_id               BIGSERIAL PRIMARY KEY,
  symbole                TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  grandeur               TEXT,
  dimension              TEXT,
  unite_si_canonique_id  BIGINT REFERENCES vocab.unite(unite_id),
  facteur_conversion     DOUBLE PRECISION,
  offset_conversion      DOUBLE PRECISION DEFAULT 0,
  est_si_canonique       BOOLEAN NOT NULL DEFAULT FALSE,
  qudt_uri               TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  import_source_id       BIGINT REFERENCES gov.import_sources(import_source_id),
  import_version         TEXT,
  last_synced_at         TIMESTAMPTZ,
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (est_si_canonique = FALSE OR unite_si_canonique_id IS NULL)
);
COMMENT ON TABLE vocab.unite IS 'Unités de mesure. Self-référence pour pointer l''unité SI canonique d''une unité d''usage.';


-- ============================================================
-- 3. SKOS CORE (vocab.scheme, vocab.concept, …)
-- ============================================================

-- 3.1 Concept Schemes
CREATE TABLE vocab.scheme (
  scheme_id              BIGSERIAL PRIMARY KEY,
  uri                    TEXT UNIQUE NOT NULL,
  code                   TEXT UNIQUE NOT NULL,
  title                  TEXT NOT NULL,
  description            TEXT,
  default_license        TEXT NOT NULL DEFAULT 'CC-BY-4.0',
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  import_source_id       BIGINT REFERENCES gov.import_sources(import_source_id),
  import_version         TEXT,
  last_synced_at         TIMESTAMPTZ,
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (uri ~ '^https?://')
);
COMMENT ON TABLE vocab.scheme IS 'skos:ConceptScheme — collection de concepts pour un usage ou un point de vue donné.';

-- 3.2 Concepts
CREATE TABLE vocab.concept (
  concept_id             BIGSERIAL PRIMARY KEY,
  uri                    TEXT UNIQUE NOT NULL,
  notation               TEXT NOT NULL,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  import_source_id       BIGINT REFERENCES gov.import_sources(import_source_id),
  import_version         TEXT,
  last_synced_at         TIMESTAMPTZ,
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (uri ~ '^https?://'),
  CHECK (notation ~ '^[a-z0-9][a-z0-9_-]*$')
);
CREATE INDEX ix_concept_status ON vocab.concept(status) WHERE status = 'published';
CREATE INDEX ix_concept_notation ON vocab.concept(notation);
COMMENT ON TABLE vocab.concept IS 'skos:Concept — unité sémantique du référentiel. Identité stable par URI ; libellés portés par concept_label.';

-- 3.3 Labels multilingues (skos:prefLabel / altLabel / hiddenLabel)
CREATE TABLE vocab.concept_label (
  concept_label_id       BIGSERIAL PRIMARY KEY,
  concept_id             BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  lang                   TEXT NOT NULL,
  kind                   TEXT NOT NULL CHECK (kind IN ('pref','alt','hidden')),
  value                  TEXT NOT NULL,
  CHECK (lang ~ '^[a-z]{2,3}(-[A-Za-z0-9]+)*$'),
  CHECK (length(value) > 0)
);
-- Un seul prefLabel par (concept, langue)
CREATE UNIQUE INDEX uq_concept_pref_lang
  ON vocab.concept_label(concept_id, lang)
  WHERE kind = 'pref';
-- Pas de doublons d'altLabel/hiddenLabel sur (concept, lang, value)
CREATE UNIQUE INDEX uq_concept_label_unique
  ON vocab.concept_label(concept_id, lang, kind, value);
CREATE INDEX ix_concept_label_search ON vocab.concept_label(lower(value));
COMMENT ON TABLE vocab.concept_label IS 'Étiquettes SKOS multilingues. lang en BCP 47 (fr, en, de, es…).';

-- 3.4 Notes (skos:definition / scopeNote / example / historyNote)
CREATE TABLE vocab.concept_note (
  concept_note_id        BIGSERIAL PRIMARY KEY,
  concept_id             BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  kind                   TEXT NOT NULL CHECK (kind IN ('definition','scopeNote','example','historyNote','editorialNote','changeNote')),
  lang                   TEXT NOT NULL,
  value                  TEXT NOT NULL,
  CHECK (lang ~ '^[a-z]{2,3}(-[A-Za-z0-9]+)*$'),
  CHECK (length(value) > 0)
);
CREATE INDEX ix_concept_note_concept ON vocab.concept_note(concept_id);

-- 3.5 Appartenance d'un concept à plusieurs schemes (n-n)
CREATE TABLE vocab.concept_in_scheme (
  concept_in_scheme_id   BIGSERIAL PRIMARY KEY,
  concept_id             BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  scheme_id              BIGINT NOT NULL REFERENCES vocab.scheme(scheme_id) ON DELETE CASCADE,
  is_top_concept         BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (concept_id, scheme_id)
);
CREATE INDEX ix_cis_scheme ON vocab.concept_in_scheme(scheme_id);
CREATE INDEX ix_cis_top    ON vocab.concept_in_scheme(scheme_id) WHERE is_top_concept = TRUE;

-- 3.6 Relations sémantiques (broader, narrower, related, *Match)
--     Multi-hiérarchie : un concept peut avoir plusieurs broader,
--     éventuellement scopés à un scheme particulier.
CREATE TABLE vocab.concept_semantic_relation (
  relation_id            BIGSERIAL PRIMARY KEY,
  source_concept_id      BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  target_concept_id      BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  relation               TEXT NOT NULL CHECK (relation IN (
                            'broader','narrower','related',
                            'exactMatch','closeMatch','broadMatch','narrowMatch','relatedMatch'
                          )),
  scheme_id              BIGINT REFERENCES vocab.scheme(scheme_id) ON DELETE CASCADE,
  CHECK (source_concept_id <> target_concept_id),
  UNIQUE (source_concept_id, target_concept_id, relation, COALESCE(scheme_id, 0))
);
CREATE INDEX ix_csr_source   ON vocab.concept_semantic_relation(source_concept_id, relation);
CREATE INDEX ix_csr_target   ON vocab.concept_semantic_relation(target_concept_id, relation);
CREATE INDEX ix_csr_relation ON vocab.concept_semantic_relation(relation);
COMMENT ON TABLE vocab.concept_semantic_relation IS
  'Relations SKOS entre concepts. broader/narrower/related sont locales au référentiel ; *Match établissent des correspondances avec d''autres vocabulaires (concept ↔ concept Nephos importé).';

-- 3.7 Mappings vers ressources externes non importées
--     Pour aligner sur des concepts externes sans en cloner le contenu.
CREATE TABLE vocab.concept_mapping (
  mapping_id             BIGSERIAL PRIMARY KEY,
  concept_id             BIGINT NOT NULL REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  target_source_id       BIGINT NOT NULL REFERENCES gov.import_sources(import_source_id),
  target_uri             TEXT NOT NULL,
  target_label           TEXT,
  mapping_relation       TEXT NOT NULL CHECK (mapping_relation IN (
                            'exactMatch','closeMatch','broadMatch','narrowMatch','relatedMatch'
                          )),
  notes                  TEXT,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (target_uri ~ '^https?://'),
  UNIQUE (concept_id, target_uri, mapping_relation)
);
CREATE INDEX ix_cmap_concept ON vocab.concept_mapping(concept_id);
CREATE INDEX ix_cmap_source  ON vocab.concept_mapping(target_source_id);
COMMENT ON TABLE vocab.concept_mapping IS
  'Alignement d''un concept Nephos vers une ressource externe non clonée localement (par ex. NERC P01, ECMWF param). Distinct de concept_semantic_relation qui ne lie que des concepts internes.';


-- ============================================================
-- 4. EXTENSION TYPAGE PHYSIQUE (vocab.concept_physical)
--    Ne s'applique qu'aux concepts mesurables / scalaires.
-- ============================================================

CREATE TABLE vocab.concept_physical (
  concept_id             BIGINT PRIMARY KEY REFERENCES vocab.concept(concept_id) ON DELETE CASCADE,
  value_type             TEXT NOT NULL CHECK (value_type IN ('scalar','vector','tensor','code','boolean','string','datetime')),
  unit_canonical_id      BIGINT REFERENCES vocab.unite(unite_id),
  range_min              DOUBLE PRECISION,
  range_max              DOUBLE PRECISION,
  precision_decimal      DOUBLE PRECISION,
  dimension              TEXT,
  cf_standard_name       TEXT,
  CHECK (range_max IS NULL OR range_min IS NULL OR range_max >= range_min)
);
COMMENT ON TABLE vocab.concept_physical IS
  'Typage physique d''un concept mesurable. Optionnel : un concept de type phénomène (orage, brouillard) n''a pas de concept_physical associé.';


-- ============================================================
-- 5. TRIGGER GÉNÉRIQUE D'AUDIT
-- ============================================================

CREATE OR REPLACE FUNCTION gov.audit_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
  v_changed_cols TEXT[];
  v_old_data     JSONB;
  v_new_data     JSONB;
  v_pk_col       TEXT;
  v_entity_id    BIGINT;
BEGIN
  v_pk_col := COALESCE(TG_ARGV[0], TG_TABLE_NAME || '_id');

  IF (TG_OP = 'DELETE') THEN
    v_old_data := to_jsonb(OLD);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING OLD;
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, old_data)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, 'DELETE', v_old_data);
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    v_old_data := to_jsonb(OLD);
    v_new_data := to_jsonb(NEW);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING NEW;
    SELECT array_agg(key) INTO v_changed_cols
      FROM jsonb_each(v_new_data) k(key, value)
      WHERE v_old_data->k.key IS DISTINCT FROM v_new_data->k.key
        AND k.key NOT IN ('modified_at','modified_by','version');
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, old_data, new_data, changed_columns)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id,
              CASE WHEN to_jsonb(OLD)->>'status' IS DISTINCT FROM to_jsonb(NEW)->>'status'
                   THEN 'STATUS_CHANGE' ELSE 'UPDATE' END,
              v_old_data, v_new_data, v_changed_cols);
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    v_new_data := to_jsonb(NEW);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING NEW;
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, new_data)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, 'INSERT', v_new_data);
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_scheme
  AFTER INSERT OR UPDATE OR DELETE ON vocab.scheme
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('scheme_id');

CREATE TRIGGER trg_audit_concept
  AFTER INSERT OR UPDATE OR DELETE ON vocab.concept
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('concept_id');

CREATE TRIGGER trg_audit_unite
  AFTER INSERT OR UPDATE OR DELETE ON vocab.unite
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('unite_id');


-- ============================================================
-- 6. DONNÉES DE RÉFÉRENCE
-- ============================================================

INSERT INTO gov.statuses VALUES
  ('draft',      1, 'Brouillon, en cours de saisie, non visible aux lecteurs'),
  ('proposed',   2, 'Proposé pour validation'),
  ('approved',   3, 'Validé, en attente de publication'),
  ('published',  4, 'Publié, en vigueur'),
  ('deprecated', 5, 'Déprécié, à éviter pour les nouveaux usages'),
  ('retired',    6, 'Retiré, plus en service');

INSERT INTO gov.roles (code, libelle, description) VALUES
  ('reader',      'Lecteur',         'Consultation uniquement.'),
  ('contributor', 'Contributeur',    'Soumet des propositions de modification.'),
  ('reviewer',    'Validateur',      'Approuve ou rejette les propositions.'),
  ('translator',  'Traducteur',      'Ajoute ou révise des labels et notes en français.'),
  ('admin',       'Administrateur',  'Droits étendus, gestion des utilisateurs et configuration.');

INSERT INTO gov.users (username, full_name, email) VALUES
  ('system',     'Système (imports automatiques)', NULL),
  ('admin',      'Administrateur initial',         'admin@local');

INSERT INTO gov.user_roles (user_id, role_id, granted_by) VALUES
  (2, (SELECT role_id FROM gov.roles WHERE code = 'admin'), NULL);

INSERT INTO gov.import_sources (code, nom, url, format, default_license) VALUES
  ('CF',            'CF Standard Names',          'https://cfconventions.org/standard-names.html', 'XML',     'CC-BY-4.0'),
  ('CF_CELL',       'CF Cell Methods',            'https://cfconventions.org/cf-conventions/cf-conventions.html', 'XML', 'CC-BY-4.0'),
  ('CF_AREA',       'CF Standardized Region Names','https://cfconventions.org/standardized-region-list.html', 'XML',  'CC-BY-4.0'),
  ('WMO_CODES',     'WMO Code Registry',          'https://codes.wmo.int',                          'RDF/SKOS','WMO-RES40'),
  ('QUDT_UNIT',     'QUDT Units',                 'https://qudt.org/vocab/unit',                    'OWL/RDF', 'CC-BY-4.0'),
  ('QUDT_QK',       'QUDT QuantityKinds',         'https://qudt.org/vocab/quantitykind',            'OWL/RDF', 'CC-BY-4.0'),
  ('ECMWF_PARAMS',  'ECMWF Parameter Database',   'https://codes.ecmwf.int/grib/param-db/',         'JSON',    'A_VERIFIER'),
  ('NERC_P01',      'NERC BODC P01 Parameters',   'https://vocab.nerc.ac.uk/collection/P01/',       'SKOS',    'CC-BY-4.0');


-- ============================================================
-- 7. VUES MÉTIER
-- ============================================================

-- 7.1 Concepts publiés et en vigueur, avec prefLabel FR/EN
CREATE OR REPLACE VIEW vocab.v_concepts_actifs AS
SELECT
  c.concept_id,
  c.uri,
  c.notation,
  fr.value           AS pref_label_fr,
  en.value           AS pref_label_en,
  c.version,
  c.modified_at,
  c.import_source_id
FROM vocab.concept c
LEFT JOIN vocab.concept_label fr
       ON fr.concept_id = c.concept_id AND fr.kind = 'pref' AND fr.lang = 'fr'
LEFT JOIN vocab.concept_label en
       ON en.concept_id = c.concept_id AND en.kind = 'pref' AND en.lang = 'en'
WHERE c.status = 'published'
  AND now() >= c.valid_from
  AND (c.valid_to IS NULL OR now() < c.valid_to);
COMMENT ON VIEW vocab.v_concepts_actifs IS 'Concepts publiés actifs, avec leurs prefLabel canoniques FR et EN.';

-- 7.2 Concepts mesurables (avec typage physique)
CREATE OR REPLACE VIEW vocab.v_concepts_mesurables AS
SELECT
  c.concept_id,
  c.uri,
  c.notation,
  fr.value                    AS pref_label_fr,
  en.value                    AS pref_label_en,
  cp.value_type,
  u.symbole                   AS unite_symbole,
  u.nom                       AS unite_nom,
  cp.range_min,
  cp.range_max,
  cp.precision_decimal,
  cp.dimension,
  cp.cf_standard_name
FROM vocab.concept c
JOIN vocab.concept_physical cp ON cp.concept_id = c.concept_id
LEFT JOIN vocab.unite u        ON u.unite_id = cp.unit_canonical_id
LEFT JOIN vocab.concept_label fr
       ON fr.concept_id = c.concept_id AND fr.kind = 'pref' AND fr.lang = 'fr'
LEFT JOIN vocab.concept_label en
       ON en.concept_id = c.concept_id AND en.kind = 'pref' AND en.lang = 'en'
WHERE c.status = 'published'
  AND now() >= c.valid_from
  AND (c.valid_to IS NULL OR now() < c.valid_to);

-- 7.3 Résolution hiérarchique récursive (descendants d'un concept)
CREATE OR REPLACE VIEW vocab.v_concept_descendants AS
WITH RECURSIVE descend AS (
  SELECT
    csr.target_concept_id  AS root_id,
    csr.source_concept_id  AS descendant_id,
    1                      AS profondeur,
    ARRAY[csr.source_concept_id] AS chemin,
    csr.scheme_id
  FROM vocab.concept_semantic_relation csr
  WHERE csr.relation = 'broader'
  UNION ALL
  SELECT
    d.root_id,
    csr.source_concept_id  AS descendant_id,
    d.profondeur + 1,
    d.chemin || csr.source_concept_id,
    COALESCE(csr.scheme_id, d.scheme_id)
  FROM descend d
  JOIN vocab.concept_semantic_relation csr
       ON csr.target_concept_id = d.descendant_id
      AND csr.relation = 'broader'
  WHERE NOT csr.source_concept_id = ANY(d.chemin)
)
SELECT root_id, descendant_id, profondeur, scheme_id
FROM descend;
COMMENT ON VIEW vocab.v_concept_descendants IS
  'Tous les descendants d''un concept via la relation broader, transitivement. Tolérant aux cycles via tracking du chemin.';

-- 7.4 Résolution hiérarchique récursive (ascendants d'un concept)
CREATE OR REPLACE VIEW vocab.v_concept_ancestors AS
WITH RECURSIVE ascend AS (
  SELECT
    csr.source_concept_id  AS root_id,
    csr.target_concept_id  AS ancestor_id,
    1                      AS profondeur,
    ARRAY[csr.target_concept_id] AS chemin,
    csr.scheme_id
  FROM vocab.concept_semantic_relation csr
  WHERE csr.relation = 'broader'
  UNION ALL
  SELECT
    a.root_id,
    csr.target_concept_id  AS ancestor_id,
    a.profondeur + 1,
    a.chemin || csr.target_concept_id,
    COALESCE(csr.scheme_id, a.scheme_id)
  FROM ascend a
  JOIN vocab.concept_semantic_relation csr
       ON csr.source_concept_id = a.ancestor_id
      AND csr.relation = 'broader'
  WHERE NOT csr.target_concept_id = ANY(a.chemin)
)
SELECT root_id, ancestor_id, profondeur, scheme_id
FROM ascend;

-- 7.5 Propositions en attente
CREATE OR REPLACE VIEW gov.v_proposals_pending AS
SELECT
  p.proposal_id,
  p.target_schema || '.' || p.target_table AS cible,
  p.action,
  p.status,
  u.username   AS proposed_by,
  p.created_at AS proposed_at,
  p.justification
FROM gov.proposals p
JOIN gov.users     u ON u.user_id = p.created_by
WHERE p.status IN ('submitted','under_review')
ORDER BY p.created_at;

-- 7.6 Audit récent (7 derniers jours)
CREATE OR REPLACE VIEW gov.v_audit_recent AS
SELECT
  a.performed_at,
  u.username,
  a.schema_name || '.' || a.table_name AS table_cible,
  a.entity_id,
  a.action,
  a.changed_columns
FROM gov.audit_log a
LEFT JOIN gov.users u ON u.user_id = a.performed_by
WHERE a.performed_at > now() - INTERVAL '7 days'
ORDER BY a.performed_at DESC;

-- 7.7 État des imports
CREATE OR REPLACE VIEW gov.v_imports_status AS
SELECT
  s.code             AS source,
  s.nom              AS source_nom,
  s.default_license  AS licence,
  COUNT(DISTINCT i.version) AS nb_versions_importees,
  MAX(i.imported_at) AS derniere_import,
  COUNT(DISTINCT t.concept_id) AS nb_concepts,
  COUNT(DISTINCT t.concept_id) FILTER (WHERE t.has_local_override) AS nb_overrides_locaux
FROM gov.import_sources s
LEFT JOIN gov.imports i        ON i.import_source_id = s.import_source_id
LEFT JOIN vocab.concept t      ON t.import_source_id = s.import_source_id
GROUP BY s.code, s.nom, s.default_license;

-- 7.8 Concepts publiés sans couverture multilingue complète (file de traduction)
CREATE OR REPLACE VIEW vocab.v_concepts_traduction_pending AS
SELECT
  c.concept_id,
  c.uri,
  c.notation,
  c.status,
  EXISTS (SELECT 1 FROM vocab.concept_label l
          WHERE l.concept_id = c.concept_id AND l.kind = 'pref' AND l.lang = 'fr') AS has_pref_fr,
  EXISTS (SELECT 1 FROM vocab.concept_label l
          WHERE l.concept_id = c.concept_id AND l.kind = 'pref' AND l.lang = 'en') AS has_pref_en
FROM vocab.concept c
WHERE c.status IN ('approved','published')
  AND NOT (
    EXISTS (SELECT 1 FROM vocab.concept_label l
            WHERE l.concept_id = c.concept_id AND l.kind = 'pref' AND l.lang = 'fr')
    AND
    EXISTS (SELECT 1 FROM vocab.concept_label l
            WHERE l.concept_id = c.concept_id AND l.kind = 'pref' AND l.lang = 'en')
  );
COMMENT ON VIEW vocab.v_concepts_traduction_pending IS
  'Concepts qui ne respectent pas l''ADR 0004 (FR + EN obligatoires sur publié). Sert de file d''attente de traduction.';

-- ============================================================
-- FIN DU SCRIPT — schema_v4_skos.sql
-- ============================================================
