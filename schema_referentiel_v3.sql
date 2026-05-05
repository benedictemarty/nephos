-- ============================================================
-- ⚠ DÉPRÉCIÉ — voir schema_v4_skos.sql
--
-- Ce schéma v3 est conservé pour référence et exploration.
-- La v4 (schema_v4_skos.sql) le remplace en se fondant sur SKOS Core
-- (W3C), conformément à l'ADR 0001. Les apports de la v4 :
--   - Hiérarchie multi-parent à profondeur arbitraire (vs profondeur 2 figée).
--   - Périmètre extensible à toutes les notions météo (phénomènes,
--     indices, événements, processus…), pas seulement les variables
--     atmosphériques classiques.
--   - URI SKOS canoniques (https://w3id.org/nephos/...), ADR 0003.
--   - Multilingue obligatoire FR+EN sur publié, ADR 0004.
--   - Mappings cross-source (skos:exactMatch / closeMatch / *Match).
--
-- Ne pas baser de production sur cette version.
-- ============================================================

-- ============================================================
-- BASE DE GESTION DE RÉFÉRENTIEL MÉTÉOROLOGIQUE — v3 (DÉPRÉCIÉ)
-- ------------------------------------------------------------
-- Architecture :
--   gov.*     — gouvernance (users, rôles, workflow, audit, imports)
--   vocab.*   — vocabulaires sémantiques (types, champs, unités…)
--   catalog.* — catalogues d'instances physiques (stations, modèles…)
--
-- Toutes les entités vocab.* et catalog.* portent :
--   - workflow : status (draft → proposed → approved → published → deprecated → retired)
--   - temporalité : valid_from, valid_to
--   - versionnement : version
--   - audit : created_by/at, modified_by/at
--   - traçabilité d'import : import_source_id, import_version, last_synced_at, has_local_override
--
-- Cible : PostgreSQL 14+. Recommandé : exposer via Directus / Strapi / Hasura / PostgREST.
-- ============================================================

DROP SCHEMA IF EXISTS gov     CASCADE;
DROP SCHEMA IF EXISTS vocab   CASCADE;
DROP SCHEMA IF EXISTS catalog CASCADE;

CREATE SCHEMA gov;
CREATE SCHEMA vocab;
CREATE SCHEMA catalog;

-- Permettre la recherche dans tous les schémas
SET search_path = vocab, catalog, gov, public;

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
COMMENT ON TABLE gov.users IS 'Utilisateurs du référentiel. Le compte ''system'' est utilisé pour les imports automatiques.';

CREATE TABLE gov.roles (
  role_id        SMALLSERIAL PRIMARY KEY,
  code           TEXT UNIQUE NOT NULL,    -- reader, contributor, reviewer, admin
  libelle        TEXT NOT NULL,
  description    TEXT
);
COMMENT ON TABLE gov.roles IS 'Rôles fonctionnels.';

CREATE TABLE gov.user_roles (
  user_role_id   BIGSERIAL PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES gov.users(user_id) ON DELETE CASCADE,
  role_id        SMALLINT NOT NULL REFERENCES gov.roles(role_id),
  scope          TEXT,                     -- ex. 'vocab.unites', 'catalog.stations.FR' ; NULL = global
  granted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  granted_by     BIGINT REFERENCES gov.users(user_id)
);
CREATE UNIQUE INDEX uq_user_role_scope ON gov.user_roles(user_id, role_id, COALESCE(scope, ''));
COMMENT ON TABLE gov.user_roles IS 'Affectation utilisateur ↔ rôle, avec portée optionnelle (table ou périmètre).';

CREATE TABLE gov.statuses (
  status         TEXT PRIMARY KEY,
  ordre          SMALLINT NOT NULL,
  description    TEXT
);
COMMENT ON TABLE gov.statuses IS 'Statuts du workflow de cycle de vie. Référencé par toutes les entités vocab.* et catalog.*.';

CREATE TABLE gov.import_sources (
  import_source_id  BIGSERIAL PRIMARY KEY,
  code              TEXT UNIQUE NOT NULL,  -- CF, WMO_CODES, QUDT, OSCAR_SURFACE, OSCAR_SPACE, ECMWF_PARAMS
  nom               TEXT NOT NULL,
  url               TEXT,
  description       TEXT,
  format            TEXT                    -- XML, RDF/SKOS, JSON, CSV
);
COMMENT ON TABLE gov.import_sources IS 'Sources externes pré-déclarées pour les imports de vocabulaires.';

CREATE TABLE gov.imports (
  import_id         BIGSERIAL PRIMARY KEY,
  import_source_id  BIGINT NOT NULL REFERENCES gov.import_sources(import_source_id),
  version           TEXT NOT NULL,           -- version de la source importée
  imported_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  imported_by       BIGINT REFERENCES gov.users(user_id),
  nb_entites        INTEGER,
  nb_creations      INTEGER,
  nb_modifications  INTEGER,
  nb_skipped        INTEGER,
  notes             TEXT
);
COMMENT ON TABLE gov.imports IS 'Journal des opérations d''import.';

CREATE TABLE gov.audit_log (
  audit_id          BIGSERIAL PRIMARY KEY,
  schema_name       TEXT NOT NULL,
  table_name        TEXT NOT NULL,
  entity_id         BIGINT NOT NULL,
  action            TEXT NOT NULL,           -- INSERT, UPDATE, DELETE, STATUS_CHANGE
  old_data          JSONB,
  new_data          JSONB,
  changed_columns   TEXT[],
  performed_by      BIGINT REFERENCES gov.users(user_id),
  performed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE gov.audit_log IS 'Journal d''audit complet, alimenté par trigger.';
CREATE INDEX ix_audit_entity ON gov.audit_log(schema_name, table_name, entity_id);
CREATE INDEX ix_audit_time   ON gov.audit_log(performed_at DESC);

CREATE TABLE gov.proposals (
  proposal_id       BIGSERIAL PRIMARY KEY,
  target_schema     TEXT NOT NULL,           -- 'vocab' ou 'catalog'
  target_table      TEXT NOT NULL,           -- ex. 'champs', 'types_grandeur'
  target_entity_id  BIGINT,                  -- NULL si proposition de création
  action            TEXT NOT NULL,           -- CREATE, UPDATE, DEPRECATE, RETIRE
  proposed_payload  JSONB NOT NULL,          -- valeurs proposées
  current_payload   JSONB,                   -- snapshot état avant (pour UPDATE/DEPRECATE)
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
COMMENT ON TABLE gov.proposals IS 'Workflow : propositions de modification d''entités du référentiel.';
CREATE INDEX ix_proposals_status ON gov.proposals(status);
CREATE INDEX ix_proposals_target ON gov.proposals(target_schema, target_table, target_entity_id);


-- ============================================================
-- 2. VOCABULAIRES (vocab.*)
-- Toutes ces tables portent les colonnes communes de gouvernance.
-- ============================================================

CREATE TABLE vocab.acteurs (
  acteur_id              BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  type                   TEXT,
  pays                   CHAR(2),
  contact_url            TEXT,
  description            TEXT,
  -- gouvernance
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE vocab.acteurs IS 'Vocabulaire des organismes producteurs / gestionnaires.';

CREATE TABLE vocab.licences (
  licence_id             BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  url                    TEXT,
  description            TEXT,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE vocab.codes_qualite (
  code                   SMALLINT PRIMARY KEY,
  libelle                TEXT NOT NULL,
  description            TEXT,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE vocab.niveaux_validation (
  niveau_validation_id   SMALLSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  libelle                TEXT NOT NULL,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocab.niveaux_traitement (
  niveau_traitement_id   SMALLSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  libelle                TEXT NOT NULL,
  schema_origine         TEXT,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocab.unites (
  unite_id               BIGSERIAL PRIMARY KEY,
  symbole                TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  grandeur               TEXT,
  dimension              TEXT,
  unite_si_canonique_id  BIGINT REFERENCES vocab.unites(unite_id),
  facteur_conversion     DOUBLE PRECISION,
  offset_conversion      DOUBLE PRECISION DEFAULT 0,
  est_si_canonique       BOOLEAN DEFAULT FALSE,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE vocab.methodes (
  methode_id             SMALLSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  cf_cell_method         TEXT,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocab.types_grandeur (
  type_id                BIGSERIAL PRIMARY KEY,
  nom                    TEXT UNIQUE NOT NULL,
  type_valeur            TEXT NOT NULL,
  unite_defaut_id        BIGINT REFERENCES vocab.unites(unite_id),
  precision_decimale     DOUBLE PRECISION,
  plage_min_absolue      DOUBLE PRECISION,
  plage_max_absolue      DOUBLE PRECISION,
  dimension_physique     TEXT,
  description            TEXT,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE vocab.champs (
  champ_id               BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  type_id                BIGINT NOT NULL REFERENCES vocab.types_grandeur(type_id),
  hauteur_profondeur     TEXT,
  methode_id             SMALLINT REFERENCES vocab.methodes(methode_id),
  periode_iso8601        TEXT,
  description            TEXT,
  unite_override_id      BIGINT REFERENCES vocab.unites(unite_id),
  plage_op_min           DOUBLE PRECISION,
  plage_op_max           DOUBLE PRECISION,
  cf_standard_name       TEXT,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE vocab.champs IS 'Définition typée des variables. Cœur du référentiel sémantique.';
CREATE INDEX ix_champs_status ON vocab.champs(status) WHERE status = 'published';
CREATE INDEX ix_champs_type   ON vocab.champs(type_id);


-- ============================================================
-- 3. CATALOGUES D'INSTANCES (catalog.*)
-- ============================================================

CREATE TABLE catalog.stations (
  station_id             BIGSERIAL PRIMARY KEY,
  code_wigos             TEXT UNIQUE,
  code_omm               TEXT,
  code_oaci              TEXT,
  nom                    TEXT NOT NULL,
  type_plateforme        TEXT NOT NULL,
  latitude               DOUBLE PRECISION NOT NULL,
  longitude              DOUBLE PRECISION NOT NULL,
  altitude               DOUBLE PRECISION,
  pays                   CHAR(2),
  region                 TEXT,
  fuseau_horaire         TEXT,
  classe_environnement   SMALLINT,
  operateur_id           BIGINT REFERENCES vocab.acteurs(acteur_id),
  date_mise_service      DATE,
  date_arret             DATE,
  description            TEXT,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_stations_geo  ON catalog.stations(latitude, longitude);
CREATE INDEX ix_stations_pays ON catalog.stations(pays);
CREATE INDEX ix_stations_pub  ON catalog.stations(status) WHERE status = 'published';

CREATE TABLE catalog.instruments (
  instrument_id          BIGSERIAL PRIMARY KEY,
  station_id             BIGINT NOT NULL REFERENCES catalog.stations(station_id) ON DELETE CASCADE,
  type                   TEXT NOT NULL,
  fabricant              TEXT,
  modele                 TEXT,
  numero_serie           TEXT,
  methode_mesure         TEXT,
  hauteur_exposition_m   DOUBLE PRECISION,
  precision_declaree     DOUBLE PRECISION,
  date_installation      DATE,
  date_demontage         DATE,
  date_calibration       DATE,
  reference_calibration  TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.modeles (
  modele_id              BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  version_modele         TEXT,
  centre_producteur_id   BIGINT REFERENCES vocab.acteurs(acteur_id),
  type_modele            TEXT,
  resolution_native_km   DOUBLE PRECISION,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.grilles_def (
  grille_id              BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE,
  nom                    TEXT,
  type_grille            TEXT NOT NULL,
  crs_epsg               INTEGER,
  nx                     INTEGER,
  ny                     INTEGER,
  nz                     INTEGER,
  resolution_x           DOUBLE PRECISION,
  resolution_y           DOUBLE PRECISION,
  unite_resolution       TEXT,
  bbox_lat_min           DOUBLE PRECISION,
  bbox_lon_min           DOUBLE PRECISION,
  bbox_lat_max           DOUBLE PRECISION,
  bbox_lon_max           DOUBLE PRECISION,
  parametres_projection  JSONB,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.radars (
  radar_id               BIGSERIAL PRIMARY KEY,
  station_id             BIGINT NOT NULL REFERENCES catalog.stations(station_id),
  code                   TEXT UNIQUE,
  bande_frequence        TEXT,
  longueur_onde_m        DOUBLE PRECISION,
  polarisation           TEXT,
  portee_max_m           DOUBLE PRECISION,
  resolution_radiale_m   DOUBLE PRECISION,
  prf_hz                 DOUBLE PRECISION,
  largeur_faisceau_deg   DOUBLE PRECISION,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.plateformes_sat (
  plateforme_id          BIGSERIAL PRIMARY KEY,
  code                   TEXT UNIQUE NOT NULL,
  nom                    TEXT NOT NULL,
  agence_id              BIGINT REFERENCES vocab.acteurs(acteur_id),
  type_orbite            TEXT NOT NULL,
  longitude_sub_sat      DOUBLE PRECISION,
  altitude_orbite_km     DOUBLE PRECISION,
  date_lancement         DATE,
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
  has_local_override     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE catalog.capteurs_sat (
  capteur_id             BIGSERIAL PRIMARY KEY,
  plateforme_id          BIGINT NOT NULL REFERENCES catalog.plateformes_sat(plateforme_id),
  code                   TEXT NOT NULL,
  nom                    TEXT NOT NULL,
  type                   TEXT,
  resolution_native_km   DOUBLE PRECISION,
  fauchee_km             DOUBLE PRECISION,
  description            TEXT,
  status                 TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                INTEGER NOT NULL DEFAULT 1,
  valid_from             TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to               TIMESTAMPTZ,
  created_by             BIGINT REFERENCES gov.users(user_id),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by            BIGINT REFERENCES gov.users(user_id),
  modified_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (plateforme_id, code)
);

CREATE TABLE catalog.canaux_sat (
  canal_id                    BIGSERIAL PRIMARY KEY,
  capteur_id                  BIGINT NOT NULL REFERENCES catalog.capteurs_sat(capteur_id),
  numero_canal                INTEGER,
  code                        TEXT,
  longueur_onde_centrale_m    DOUBLE PRECISION NOT NULL,
  largeur_bande_m             DOUBLE PRECISION,
  gamme_spectrale             TEXT,
  grandeur_restituee          TEXT,
  unite_typique_id            BIGINT REFERENCES vocab.unites(unite_id),
  fonction_reponse_spectrale  TEXT,
  status                      TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status),
  version                     INTEGER NOT NULL DEFAULT 1,
  valid_from                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to                    TIMESTAMPTZ,
  created_by                  BIGINT REFERENCES gov.users(user_id),
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  modified_by                 BIGINT REFERENCES gov.users(user_id),
  modified_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (capteur_id, numero_canal)
);


-- ============================================================
-- 4. FONCTION TRIGGER D'AUDIT (à attacher à chaque table)
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
  -- Détection de la colonne PK (convention : finit par _id, ou code pour codes_qualite)
  v_pk_col := COALESCE(TG_ARGV[0], TG_TABLE_NAME || '_id');

  IF (TG_OP = 'DELETE') THEN
    v_old_data := to_jsonb(OLD);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING OLD;
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, old_data, performed_at)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, 'DELETE', v_old_data, now());
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    v_old_data := to_jsonb(OLD);
    v_new_data := to_jsonb(NEW);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING NEW;
    SELECT array_agg(key) INTO v_changed_cols
      FROM jsonb_each(v_new_data) k(key, value)
      WHERE v_old_data->k.key IS DISTINCT FROM v_new_data->k.key
        AND k.key NOT IN ('modified_at','modified_by','version');
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, old_data, new_data, changed_columns, performed_at)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id,
              CASE WHEN OLD.status IS DISTINCT FROM NEW.status THEN 'STATUS_CHANGE' ELSE 'UPDATE' END,
              v_old_data, v_new_data, v_changed_cols, now());
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    v_new_data := to_jsonb(NEW);
    EXECUTE format('SELECT ($1).%I::BIGINT', v_pk_col) INTO v_entity_id USING NEW;
    INSERT INTO gov.audit_log(schema_name, table_name, entity_id, action, new_data, performed_at)
      VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, 'INSERT', v_new_data, now());
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION gov.audit_trigger_func IS 'Trigger générique d''audit. Argument optionnel : nom de la colonne PK.';

-- Attacher le trigger à toutes les tables suivies
CREATE TRIGGER trg_audit_champs
  AFTER INSERT OR UPDATE OR DELETE ON vocab.champs
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('champ_id');

CREATE TRIGGER trg_audit_types
  AFTER INSERT OR UPDATE OR DELETE ON vocab.types_grandeur
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('type_id');

CREATE TRIGGER trg_audit_unites
  AFTER INSERT OR UPDATE OR DELETE ON vocab.unites
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('unite_id');

CREATE TRIGGER trg_audit_stations
  AFTER INSERT OR UPDATE OR DELETE ON catalog.stations
  FOR EACH ROW EXECUTE FUNCTION gov.audit_trigger_func('station_id');

-- (Reproduire pour les autres tables selon besoin)


-- ============================================================
-- 5. DONNÉES DE RÉFÉRENCE
-- ============================================================

-- Statuts du workflow
INSERT INTO gov.statuses VALUES
  ('draft',      1, 'Brouillon, en cours de saisie, non visible aux lecteurs'),
  ('proposed',   2, 'Proposé pour validation'),
  ('approved',   3, 'Validé, en attente de publication'),
  ('published',  4, 'Publié, en vigueur'),
  ('deprecated', 5, 'Déprécié, à éviter pour les nouveaux usages'),
  ('retired',    6, 'Retiré, plus en service');

-- Rôles
INSERT INTO gov.roles (code, libelle, description) VALUES
  ('reader',      'Lecteur',     'Consultation uniquement.'),
  ('contributor', 'Contributeur','Soumet des propositions de modification.'),
  ('reviewer',    'Validateur',  'Approuve / rejette les propositions.'),
  ('admin',       'Administrateur','Droits étendus, gestion des utilisateurs et configuration.');

-- Utilisateurs (système)
INSERT INTO gov.users (username, full_name, email) VALUES
  ('system',     'Système (imports automatiques)', NULL),
  ('admin',      'Administrateur initial',         'admin@local');

INSERT INTO gov.user_roles (user_id, role_id, scope, granted_by) VALUES
  ((SELECT user_id FROM gov.users WHERE username='admin'),
   (SELECT role_id FROM gov.roles WHERE code='admin'),
   NULL, NULL);

-- Sources d'import
INSERT INTO gov.import_sources (code, nom, url, format) VALUES
  ('CF',            'CF Standard Names',          'https://cfconventions.org/standard-names.html', 'XML'),
  ('WMO_CODES',     'WMO Code Registry',          'https://codes.wmo.int',                          'RDF/SKOS'),
  ('QUDT',          'QUDT Quantity Kinds & Units','https://qudt.org',                               'OWL/RDF'),
  ('ECMWF_PARAMS',  'ECMWF Parameter Database',   'https://codes.ecmwf.int/grib/param-db/',         'JSON'),
  ('OSCAR_SURFACE', 'WMO OSCAR/Surface',          'https://oscar.wmo.int/surface',                  'JSON/REST'),
  ('OSCAR_SPACE',   'WMO OSCAR/Space',            'https://space.oscar.wmo.int',                    'JSON/REST');

-- Acteurs
INSERT INTO vocab.acteurs (code, nom, type, pays, status, created_by) VALUES
  ('MF',         'Météo-France',                                       'agence_meteo',     'FR',  'published', 2),
  ('ECMWF',      'European Centre for Medium-Range Weather Forecasts', 'agence_meteo',     NULL, 'published', 2),
  ('EUMETSAT',   'European Org. for Meteorological Satellites',        'agence_spatiale',  NULL, 'published', 2),
  ('NOAA',       'National Oceanic and Atmospheric Administration',    'agence_meteo',     'US',  'published', 2),
  ('NASA',       'National Aeronautics and Space Administration',      'agence_spatiale',  'US',  'published', 2),
  ('DWD',        'Deutscher Wetterdienst',                             'agence_meteo',     'DE',  'published', 2),
  ('UKMO',       'Met Office',                                         'agence_meteo',     'GB',  'published', 2),
  ('JMA',        'Japan Meteorological Agency',                        'agence_meteo',     'JP',  'published', 2),
  ('EUMETNET',   'EUMETNET',                                           'reseau',           NULL, 'published', 2),
  ('COPERNICUS', 'Programme Copernicus',                               'programme',        NULL, 'published', 2);

-- Licences
INSERT INTO vocab.licences (code, nom, url, status, created_by) VALUES
  ('ETALAB-2.0',   'Licence Ouverte Etalab 2.0',          'https://www.etalab.gouv.fr/licence-ouverte-open-licence/', 'published', 2),
  ('CC-BY-4.0',    'Creative Commons Attribution 4.0',    'https://creativecommons.org/licenses/by/4.0/',             'published', 2),
  ('CC0-1.0',      'Creative Commons Zero',               'https://creativecommons.org/publicdomain/zero/1.0/',       'published', 2),
  ('PROPRIETAIRE', 'Propriétaire',                        NULL,                                                       'published', 2),
  ('WMO-RES40',    'WMO Resolution 40',                   'https://public.wmo.int',                                   'published', 2);

-- Codes qualité
INSERT INTO vocab.codes_qualite (code, libelle, description, status, created_by) VALUES
  (0, 'Valide',     'Aucun problème détecté',                       'published', 2),
  (1, 'Incertaine', 'Doute, à confirmer',                           'published', 2),
  (2, 'Erronée',    'Valeur jugée incorrecte',                      'published', 2),
  (3, 'Estimée',    'Reconstituée par modèle',                      'published', 2),
  (5, 'Interpolée', 'Calculée à partir d''observations voisines',   'published', 2),
  (7, 'Modifiée',   'Corrigée manuellement',                        'published', 2),
  (9, 'Manquante',  'Donnée absente',                               'published', 2);

-- Niveaux
INSERT INTO vocab.niveaux_validation (code, libelle, description, status, created_by) VALUES
  ('raw',        'Brute',     'Donnée non contrôlée',                    'published', 2),
  ('controlled', 'Contrôlée', 'Contrôles automatiques passés',           'published', 2),
  ('validated',  'Validée',   'Contrôles + revue manuelle',              'published', 2),
  ('certified',  'Certifiée', 'Référence officielle',                    'published', 2);

INSERT INTO vocab.niveaux_traitement (code, libelle, schema_origine, description, status, created_by) VALUES
  ('L0',  'L0 — Brut',          'générique', 'Donnée capteur non corrigée',          'published', 2),
  ('L1',  'L1 — Calibré',       'générique', 'Calibration appliquée',                'published', 2),
  ('L1A', 'L1A — Reconstruit',  'CEOS',      'L0 + auxiliaires annotées',            'published', 2),
  ('L1B', 'L1B — Calibré',      'CEOS',      'Mesures physiques géolocalisées',      'published', 2),
  ('L1C', 'L1C — Géo-rectifié', 'CEOS',      'L1B sur grille régulière',             'published', 2),
  ('L2',  'L2 — Géophysique',   'CEOS',      'Variables géophysiques restituées',    'published', 2),
  ('L3',  'L3 — Composite',     'CEOS',      'Agrégat spatio-temporel',              'published', 2),
  ('L4',  'L4 — Modélisé',      'CEOS',      'Produit dérivé / fusion',              'published', 2);

-- Unités SI canoniques
INSERT INTO vocab.unites (symbole, nom, grandeur, dimension, est_si_canonique, facteur_conversion, status, created_by) VALUES
  ('K',     'Kelvin',            'Température',   'T',           TRUE, 1, 'published', 2),
  ('Pa',    'Pascal',            'Pression',      'M·L⁻¹·T⁻²',  TRUE, 1, 'published', 2),
  ('m/s',   'Mètre par seconde', 'Vitesse',       'L·T⁻¹',      TRUE, 1, 'published', 2),
  ('m',     'Mètre',             'Longueur',      'L',           TRUE, 1, 'published', 2),
  ('s',     'Seconde',           'Durée',         'T',           TRUE, 1, 'published', 2),
  ('rad',   'Radian',            'Angle',         'sans',        TRUE, 1, 'published', 2),
  ('W/m²',  'Watt par m²',       'Densité flux',  'M·T⁻³',      TRUE, 1, 'published', 2),
  ('kg/m²', 'Kg par m²',         'Précipitation', 'L (eau)',     TRUE, 1, 'published', 2),
  ('kg/kg', 'Kg par kg',         'Sans dim.',     'sans',        TRUE, 1, 'published', 2),
  ('1',     'Sans dimension',    'Sans dim.',     'sans',        TRUE, 1, 'published', 2),
  ('dB',    'Décibel',           'Logarithmique', 'sans',        TRUE, 1, 'published', 2),
  ('dBZ',   'Décibel-Z (radar)', 'Réflectivité',  'sans',        TRUE, 1, 'published', 2);

-- Unités d'usage
INSERT INTO vocab.unites (symbole, nom, grandeur, dimension, unite_si_canonique_id, facteur_conversion, offset_conversion, status, created_by) VALUES
  ('°C',   'Degré Celsius',       'Température',   'T',          (SELECT unite_id FROM vocab.unites WHERE symbole='K'),    1,        273.15, 'published', 2),
  ('°F',   'Degré Fahrenheit',    'Température',   'T',          (SELECT unite_id FROM vocab.unites WHERE symbole='K'),    0.5556,   255.372,'published', 2),
  ('hPa',  'Hectopascal',         'Pression',      'M·L⁻¹·T⁻²', (SELECT unite_id FROM vocab.unites WHERE symbole='Pa'),   100,      0,      'published', 2),
  ('mbar', 'Millibar',            'Pression',      'M·L⁻¹·T⁻²', (SELECT unite_id FROM vocab.unites WHERE symbole='Pa'),   100,      0,      'published', 2),
  ('km/h', 'Kilomètre par heure', 'Vitesse',       'L·T⁻¹',     (SELECT unite_id FROM vocab.unites WHERE symbole='m/s'),  0.27778,  0,      'published', 2),
  ('kn',   'Nœud',                'Vitesse',       'L·T⁻¹',     (SELECT unite_id FROM vocab.unites WHERE symbole='m/s'),  0.51444,  0,      'published', 2),
  ('mm',   'Millimètre (eau)',    'Précipitation', 'L (eau)',    (SELECT unite_id FROM vocab.unites WHERE symbole='kg/m²'),1,        0,      'published', 2),
  ('mm/h', 'Millimètre par heure','Flux précip.',  'L·T⁻¹',     NULL,                                                      NULL,     NULL,   'published', 2),
  ('km',   'Kilomètre',           'Longueur',      'L',          (SELECT unite_id FROM vocab.unites WHERE symbole='m'),    1000,     0,      'published', 2),
  ('cm',   'Centimètre',          'Longueur',      'L',          (SELECT unite_id FROM vocab.unites WHERE symbole='m'),    0.01,     0,      'published', 2),
  ('°',    'Degré (angle)',       'Angle',         'sans',       (SELECT unite_id FROM vocab.unites WHERE symbole='rad'),  0.017453, 0,      'published', 2),
  ('min',  'Minute',              'Durée',         'T',          (SELECT unite_id FROM vocab.unites WHERE symbole='s'),    60,       0,      'published', 2),
  ('h',    'Heure',               'Durée',         'T',          (SELECT unite_id FROM vocab.unites WHERE symbole='s'),    3600,     0,      'published', 2),
  ('%',    'Pourcent',            'Sans dim.',     'sans',       (SELECT unite_id FROM vocab.unites WHERE symbole='1'),    0.01,     0,      'published', 2),
  ('octas','Octa',                'Sans dim.',     'sans',       (SELECT unite_id FROM vocab.unites WHERE symbole='1'),    0.125,    0,      'published', 2),
  ('g/kg', 'Gramme par kg',       'Sans dim.',     'sans',       (SELECT unite_id FROM vocab.unites WHERE symbole='kg/kg'),0.001,    0,      'published', 2),
  ('°/km', 'Degré par km',        'Phase / dist.', 'L⁻¹',       NULL,                                                      NULL,     NULL,   'published', 2);

-- Méthodes
INSERT INTO vocab.methodes (code, cf_cell_method, description, status, created_by) VALUES
  ('instantanee', 'point',              'Valeur ponctuelle',                'published', 2),
  ('moyenne',     'mean',               'Moyenne sur la période',           'published', 2),
  ('min',         'minimum',            'Minimum sur la période',           'published', 2),
  ('max',         'maximum',            'Maximum sur la période',           'published', 2),
  ('somme',       'sum',                'Cumul sur la période',             'published', 2),
  ('mediane',     'median',             'Médiane',                          'published', 2),
  ('mode',        'mode',               'Valeur la plus fréquente',         'published', 2),
  ('ecart_type',  'standard_deviation', 'Écart-type',                       'published', 2),
  ('p95',         NULL,                 '95ᵉ percentile',                   'published', 2),
  ('aucune',      NULL,                 'Sans agrégation',                  'published', 2);

-- Types de grandeur (avec types corrigés pour radar/satellite)
INSERT INTO vocab.types_grandeur (nom, type_valeur, unite_defaut_id, precision_decimale, plage_min_absolue, plage_max_absolue, dimension_physique, description, status, created_by) VALUES
  ('Temperature',           'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='°C'),  0.1,    -90,    60,     'Température',       'T_rosée ≤ T_air en physique',                                'published', 2),
  ('Pression',              'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='hPa'), 0.1,    500,    1100,   'Pression',          NULL,                                                          'published', 2),
  ('VitesseVent',           'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='m/s'), 0.1,    0,      80,     'Vitesse',           NULL,                                                          'published', 2),
  ('VitesseRadiale',        'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='m/s'), 0.1,    -100,   100,    'Vitesse signée',    'Vitesse Doppler radiale (signe = sens par rapport au radar)','published', 2),
  ('DirectionVent',         'int',      (SELECT unite_id FROM vocab.unites WHERE symbole='°'),   1,      0,      360,    'Angle',             'NULL si vent < 0,5 m/s',                                      'published', 2),
  ('HumiditeRelative',      'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='%'),   0.1,    0,      105,    'Sans dim.',         NULL,                                                          'published', 2),
  ('HumiditeSpecifique',    'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='g/kg'),0.01,   0,      40,     'Sans dim.',         NULL,                                                          'published', 2),
  ('PrecipitationCumul',    'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='mm'),  0.1,    0,      1500,   'Hauteur d''eau',    NULL,                                                          'published', 2),
  ('PrecipitationFlux',     'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='mm/h'),0.1,    0,      300,    'Flux',              NULL,                                                          'published', 2),
  ('HauteurNeige',          'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='cm'),  1,      0,      1500,   'Longueur',          NULL,                                                          'published', 2),
  ('Visibilite',            'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='m'),   10,     0,      100000, 'Longueur',          NULL,                                                          'published', 2),
  ('NebulositeOctas',       'int',      (SELECT unite_id FROM vocab.unites WHERE symbole='octas'),1,     0,      9,      'Sans dim.',         '9 = ciel invisible',                                          'published', 2),
  ('FractionNuageuse',      'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='%'),   1,      0,      100,    'Sans dim.',         NULL,                                                          'published', 2),
  ('RayonnementFlux',       'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='W/m²'),1,      0,      1500,   'Densité flux',      NULL,                                                          'published', 2),
  ('DureeInsolation',       'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='min'), 1,      0,      1440,   'Durée',             NULL,                                                          'published', 2),
  ('CodeWMO',               'int',      (SELECT unite_id FROM vocab.unites WHERE symbole='1'),   1,      0,      99,     'Sans dim.',         'Code de table OMM',                                           'published', 2),
  ('Identifiant',           'string',   NULL,                                                    NULL,   NULL,   NULL,   NULL,                NULL,                                                          'published', 2),
  ('HorodatageUTC',         'datetime', NULL,                                                    NULL,   NULL,   NULL,   'Temps',             'ISO 8601 UTC',                                                'published', 2),
  ('Latitude',              'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='°'),   0.00001,-90,    90,     'Angle WGS84',       NULL,                                                          'published', 2),
  ('Longitude',             'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='°'),   0.00001,-180,   180,    'Angle WGS84',       NULL,                                                          'published', 2),
  ('Altitude',              'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='m'),   0.1,    -500,   9000,   'Longueur',          NULL,                                                          'published', 2),
  -- TYPES CORRIGÉS POUR RADAR/SATELLITE :
  ('Reflectivite_dBZ',      'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='dBZ'), 0.5,    -32,    80,     'Logarithmique',     'Réflectivité radar Z exprimée en dBZ (échelle logarithmique)','published', 2),
  ('ReflectiviteDiff_dB',   'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='dB'),  0.1,    -8,     8,      'Logarithmique',     'Réflectivité différentielle ZDR en dB',                       'published', 2),
  ('PhaseDifferentielle',   'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='°/km'),0.1,    -2,     20,     'Phase / distance',  'KDP : phase différentielle spécifique',                       'published', 2),
  ('CoefficientCorrelation','float',    (SELECT unite_id FROM vocab.unites WHERE symbole='1'),   0.001,  0,      1.05,   'Sans dim.',         'Coefficient de corrélation polarimétrique ρHV',               'published', 2),
  ('IndiceNormalise',       'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='1'),   0.01,   -1,     1,      'Sans dim.',         'Indice normalisé dans [-1, 1] (NDVI, NDSI, etc.)',            'published', 2),
  ('EpaisseurOptique',      'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='1'),   0.01,   0,      200,    'Sans dim.',         'Épaisseur optique (AOD, COD)',                                'published', 2),
  ('Reflectance',           'float',    (SELECT unite_id FROM vocab.unites WHERE symbole='1'),   0.001,  0,      1.5,    'Sans dim.',         'Réflectance bidirectionnelle',                                'published', 2);

-- Champs (avec types CORRIGÉS pour radar/satellite)
INSERT INTO vocab.champs (code, type_id, hauteur_profondeur, methode_id, periode_iso8601, plage_op_min, plage_op_max, cf_standard_name, description, status, created_by) VALUES
  ('temperature_air',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='Temperature'),       '2 m',    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -50, 50,   'air_temperature',                  'Température de l''air à 2 m',                       'published', 2),
  ('temperature_min',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='Temperature'),       '2 m',    (SELECT methode_id FROM vocab.methodes WHERE code='min'),        'P1D',   -50, 45,   'air_temperature',                  'Tn (jour climato 6h→6h UTC)',                        'published', 2),
  ('temperature_max',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='Temperature'),       '2 m',    (SELECT methode_id FROM vocab.methodes WHERE code='max'),        'P1D',   -45, 55,   'air_temperature',                  'Tx (jour climato 18h→18h UTC)',                      'published', 2),
  ('temperature_rosee',     (SELECT type_id FROM vocab.types_grandeur WHERE nom='Temperature'),       '2 m',    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -60, 35,   'dew_point_temperature',            'Point de rosée (≤ T_air)',                          'published', 2),
  ('humidite_relative',     (SELECT type_id FROM vocab.types_grandeur WHERE nom='HumiditeRelative'),  '2 m',    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   100,  'relative_humidity',                'HR à 2 m',                                          'published', 2),
  ('pression_mer',          (SELECT type_id FROM vocab.types_grandeur WHERE nom='Pression'),          NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    950, 1050, 'air_pressure_at_mean_sea_level',   'Pression niveau mer (QFF)',                          'published', 2),
  ('vent_vitesse_10m',      (SELECT type_id FROM vocab.types_grandeur WHERE nom='VitesseVent'),       '10 m',   (SELECT methode_id FROM vocab.methodes WHERE code='moyenne'),    'PT10M', 0,   60,   'wind_speed',                       'Vent moyen 10 min à 10 m',                          'published', 2),
  ('vent_direction_10m',    (SELECT type_id FROM vocab.types_grandeur WHERE nom='DirectionVent'),     '10 m',   (SELECT methode_id FROM vocab.methodes WHERE code='moyenne'),    'PT10M', 0,   360,  'wind_from_direction',              'Direction. NULL si vent < 0,5 m/s',                  'published', 2),
  ('vent_rafale_10m',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='VitesseVent'),       '10 m',   (SELECT methode_id FROM vocab.methodes WHERE code='max'),        NULL,    0,   110,  'wind_speed_of_gust',               'Rafale max',                                        'published', 2),
  ('precipitation_1h',      (SELECT type_id FROM vocab.types_grandeur WHERE nom='PrecipitationCumul'),'sol',    (SELECT methode_id FROM vocab.methodes WHERE code='somme'),      'PT1H',  0,   305,  'precipitation_amount',             'Cumul 1 h',                                          'published', 2),
  ('precipitation_24h',     (SELECT type_id FROM vocab.types_grandeur WHERE nom='PrecipitationCumul'),'sol',    (SELECT methode_id FROM vocab.methodes WHERE code='somme'),      'P1D',   0,   1825, 'precipitation_amount',             'Cumul 24 h',                                         'published', 2),
  ('rayonnement_global',    (SELECT type_id FROM vocab.types_grandeur WHERE nom='RayonnementFlux'),   'sol',    (SELECT methode_id FROM vocab.methodes WHERE code='moyenne'),    'PT1H',  0,   1400, 'surface_downwelling_shortwave_flux_in_air','Rayonnement global',                                'published', 2),
  ('temps_present',         (SELECT type_id FROM vocab.types_grandeur WHERE nom='CodeWMO'),           NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   99,   NULL,                               'Code OMM 4677',                                      'published', 2),
  -- Radar (TYPES CORRIGÉS) :
  ('reflectivite_z',        (SELECT type_id FROM vocab.types_grandeur WHERE nom='Reflectivite_dBZ'),  NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -32, 75,   'equivalent_reflectivity_factor',   'Réflectivité radar Z',                              'published', 2),
  ('vitesse_doppler',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='VitesseRadiale'),    NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -100,100,  'radial_velocity_of_scatterers_away_from_instrument','Vitesse radiale Doppler',                  'published', 2),
  ('zdr',                   (SELECT type_id FROM vocab.types_grandeur WHERE nom='ReflectiviteDiff_dB'),NULL,    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -8,  8,    'log_derived_radar_reflectivity_differential','Réflectivité différentielle ZDR',          'published', 2),
  ('kdp',                   (SELECT type_id FROM vocab.types_grandeur WHERE nom='PhaseDifferentielle'),NULL,    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -2,  20,   'specific_differential_phase_hv',   'Phase différentielle spécifique KDP',                'published', 2),
  ('rho_hv',                (SELECT type_id FROM vocab.types_grandeur WHERE nom='CoefficientCorrelation'),NULL, (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   1.05, 'cross_correlation_ratio_hv',       'Coefficient de corrélation ρHV',                    'published', 2),
  ('rr_radar_estime',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='PrecipitationFlux'), NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   300,  'rainfall_rate',                    'Pluie radar estimée',                               'published', 2),
  -- Satellite (TYPES CORRIGÉS) :
  ('temperature_brillance', (SELECT type_id FROM vocab.types_grandeur WHERE nom='Temperature'),       'TOA',    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    150, 350,  'toa_brightness_temperature',       'T° brillance TOA',                                  'published', 2),
  ('reflectance_toa',       (SELECT type_id FROM vocab.types_grandeur WHERE nom='Reflectance'),       'TOA',    (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   1.5,  'toa_bidirectional_reflectance',    'Réflectance TOA',                                   'published', 2),
  ('aod',                   (SELECT type_id FROM vocab.types_grandeur WHERE nom='EpaisseurOptique'),  NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   5,    'atmosphere_optical_thickness_due_to_ambient_aerosol_particles','Épaisseur optique aérosols','published', 2),
  ('cod',                   (SELECT type_id FROM vocab.types_grandeur WHERE nom='EpaisseurOptique'),  NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    0,   200,  'atmosphere_optical_thickness_due_to_cloud','Épaisseur optique de nuage',                'published', 2),
  ('ndvi',                  (SELECT type_id FROM vocab.types_grandeur WHERE nom='IndiceNormalise'),   NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -1,  1,    'normalized_difference_vegetation_index','Indice NDVI',                                  'published', 2),
  ('ndsi',                  (SELECT type_id FROM vocab.types_grandeur WHERE nom='IndiceNormalise'),   NULL,     (SELECT methode_id FROM vocab.methodes WHERE code='instantanee'),NULL,    -1,  1,    'normalized_difference_snow_index', 'Indice NDSI (neige)',                               'published', 2);


-- ============================================================
-- 6. VUES MÉTIER
-- ============================================================

-- Champs en vigueur (publiés et dans leur fenêtre de validité)
CREATE OR REPLACE VIEW vocab.v_champs_actifs AS
SELECT
  c.champ_id,
  c.code                                AS champ_code,
  c.description                         AS champ_description,
  t.nom                                 AS type_nom,
  t.type_valeur,
  t.precision_decimale,
  COALESCE(uo.symbole, ud.symbole)      AS unite_symbole,
  c.hauteur_profondeur,
  m.code                                AS methode_code,
  m.cf_cell_method,
  c.periode_iso8601,
  c.plage_op_min,
  c.plage_op_max,
  c.cf_standard_name,
  c.version,
  c.modified_at
FROM vocab.champs c
JOIN vocab.types_grandeur t  ON t.type_id = c.type_id
LEFT JOIN vocab.unites    ud ON ud.unite_id = t.unite_defaut_id
LEFT JOIN vocab.unites    uo ON uo.unite_id = c.unite_override_id
LEFT JOIN vocab.methodes  m  ON m.methode_id = c.methode_id
WHERE c.status = 'published'
  AND now() >= c.valid_from
  AND (c.valid_to IS NULL OR now() < c.valid_to);
COMMENT ON VIEW vocab.v_champs_actifs IS 'Champs publiés et dans leur fenêtre de validité courante.';

-- Propositions en attente de validation
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

-- Audit récent (7 derniers jours)
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

-- État de la synchronisation des imports
CREATE OR REPLACE VIEW gov.v_imports_status AS
SELECT
  s.code             AS source,
  s.nom              AS source_nom,
  COUNT(DISTINCT t.import_version) AS nb_versions_importees,
  MAX(t.last_synced_at)            AS derniere_synchro,
  COUNT(*)                         AS nb_entites_via_cette_source,
  COUNT(*) FILTER (WHERE t.has_local_override) AS nb_avec_override_local
FROM gov.import_sources s
LEFT JOIN (
  SELECT import_source_id, import_version, last_synced_at, has_local_override FROM vocab.unites WHERE import_source_id IS NOT NULL
  UNION ALL
  SELECT import_source_id, import_version, last_synced_at, has_local_override FROM vocab.types_grandeur WHERE import_source_id IS NOT NULL
  UNION ALL
  SELECT import_source_id, import_version, last_synced_at, has_local_override FROM vocab.champs WHERE import_source_id IS NOT NULL
  UNION ALL
  SELECT import_source_id, import_version, last_synced_at, has_local_override FROM catalog.stations WHERE import_source_id IS NOT NULL
  UNION ALL
  SELECT import_source_id, import_version, last_synced_at, has_local_override FROM catalog.plateformes_sat WHERE import_source_id IS NOT NULL
) t ON t.import_source_id = s.import_source_id
GROUP BY s.code, s.nom;

-- ============================================================
-- FIN DU SCRIPT
-- ============================================================
