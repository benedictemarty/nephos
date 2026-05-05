"""Tests d'intégrité du schéma v4 SKOS — contraintes UNIQUE / CHECK / FK.

Vérifie que les invariants posés par `schema_v4_skos.sql` sont effectivement
appliqués par PostgreSQL :

- URI doivent commencer par http(s)://
- notation au pattern `^[a-z0-9][a-z0-9_-]*$`
- prefLabel unique par (concept, lang)
- valid_to > valid_from
- relation source ≠ target
- BCP 47 sur lang
- mapping vers source non déclarée → FK violée
"""

from __future__ import annotations

import pytest
from psycopg import Connection
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

pytestmark = pytest.mark.integration


def _insert_scheme(conn: Connection, code: str, uri: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.scheme (uri, code, title, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING scheme_id
            """,
            (uri, code, f"Test scheme {code}"),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _insert_concept(conn: Connection, uri: str, notation: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept (uri, notation, status)
            VALUES (%s, %s, 'draft')
            RETURNING concept_id
            """,
            (uri, notation),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


# ----------------------------------------------------------------------
# Scheme : URI ^https?://
# ----------------------------------------------------------------------

class TestSchemeConstraints:
    def test_scheme_accepts_https_uri(self, db_conn: Connection) -> None:
        sid = _insert_scheme(db_conn, "test", "https://w3id.org/nephos/vocab/test")
        assert sid > 0

    def test_scheme_accepts_http_uri(self, db_conn: Connection) -> None:
        sid = _insert_scheme(db_conn, "test", "http://example.org/vocab/test")
        assert sid > 0

    def test_scheme_rejects_non_http_uri(self, db_conn: Connection) -> None:
        with pytest.raises(CheckViolation):
            _insert_scheme(db_conn, "test", "ftp://example.org/vocab/test")

    def test_scheme_uri_unique(self, db_conn: Connection) -> None:
        _insert_scheme(db_conn, "test1", "https://w3id.org/nephos/vocab/test")
        with pytest.raises(UniqueViolation):
            _insert_scheme(db_conn, "test2", "https://w3id.org/nephos/vocab/test")


# ----------------------------------------------------------------------
# Concept : notation pattern, URI, valid_from < valid_to
# ----------------------------------------------------------------------

class TestConceptConstraints:
    def test_concept_accepts_snake_case_notation(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_air",
            "temperature_air",
        )
        assert cid > 0

    def test_concept_accepts_kebab_case_notation(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/niveaux/2-m",
            "2-m",
        )
        assert cid > 0

    def test_concept_rejects_uppercase_notation(self, db_conn: Connection) -> None:
        with pytest.raises(CheckViolation):
            _insert_concept(
                db_conn,
                "https://w3id.org/nephos/vocab/test/Bad",
                "Bad",
            )

    def test_concept_rejects_notation_starting_with_dash(self, db_conn: Connection) -> None:
        with pytest.raises(CheckViolation):
            _insert_concept(
                db_conn,
                "https://w3id.org/nephos/vocab/test/-bad",
                "-bad",
            )

    def test_concept_uri_unique(self, db_conn: Connection) -> None:
        uri = "https://w3id.org/nephos/vocab/grandeurs/temperature_air"
        _insert_concept(db_conn, uri, "temperature_air")
        with pytest.raises(UniqueViolation):
            _insert_concept(db_conn, uri, "temperature_air_v2")

    def test_concept_valid_to_must_be_after_valid_from(
        self, db_conn: Connection
    ) -> None:
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    """
                    INSERT INTO vocab.concept
                      (uri, notation, status, valid_from, valid_to)
                    VALUES
                      (%s, %s, 'draft', '2025-01-01', '2024-01-01')
                    """,
                    ("https://w3id.org/nephos/vocab/test/x", "x"),
                )


# ----------------------------------------------------------------------
# Labels : prefLabel unique par (concept, lang), BCP 47
# ----------------------------------------------------------------------

class TestLabelConstraints:
    @pytest.fixture
    def concept_id(self, db_conn: Connection) -> int:
        return _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_air",
            "temperature_air",
        )

    def test_pref_label_unique_per_lang(
        self, db_conn: Connection, concept_id: int
    ) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'fr', 'pref', 'Température de l''air')",
                (concept_id,),
            )
            with pytest.raises(UniqueViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                    "VALUES (%s, 'fr', 'pref', 'T° de l''air')",
                    (concept_id,),
                )

    def test_two_pref_labels_in_distinct_languages(
        self, db_conn: Connection, concept_id: int
    ) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'fr', 'pref', 'Température')",
                (concept_id,),
            )
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'en', 'pref', 'Temperature')",
                (concept_id,),
            )
            cur.execute(
                "SELECT COUNT(*) FROM vocab.concept_label WHERE concept_id = %s",
                (concept_id,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 2

    def test_alt_labels_can_be_multiple(
        self, db_conn: Connection, concept_id: int
    ) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'fr', 'alt', 'T2m')",
                (concept_id,),
            )
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'fr', 'alt', 'temp 2 mètres')",
                (concept_id,),
            )

    def test_lang_must_be_bcp47(
        self, db_conn: Connection, concept_id: int
    ) -> None:
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                    "VALUES (%s, 'FRENCH', 'pref', 'Température')",
                    (concept_id,),
                )

    def test_label_value_cannot_be_empty(
        self, db_conn: Connection, concept_id: int
    ) -> None:
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                    "VALUES (%s, 'fr', 'pref', '')",
                    (concept_id,),
                )


# ----------------------------------------------------------------------
# Relations sémantiques
# ----------------------------------------------------------------------

class TestRelationConstraints:
    def test_relation_source_cannot_equal_target(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/test/x",
            "x",
        )
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_semantic_relation "
                    "(source_concept_id, target_concept_id, relation) "
                    "VALUES (%s, %s, 'broader')",
                    (cid, cid),
                )

    def test_multi_broader_supported(self, db_conn: Connection) -> None:
        c_temp = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature",
            "temperature",
        )
        c_meas = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/satellite/mesure_radiometrique",
            "mesure_radiometrique",
        )
        c_tb = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_brillance",
            "temperature_brillance",
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'broader'), (%s, %s, 'broader')",
                (c_tb, c_temp, c_tb, c_meas),
            )
            cur.execute(
                "SELECT COUNT(*) FROM vocab.concept_semantic_relation "
                "WHERE source_concept_id = %s AND relation = 'broader'",
                (c_tb,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 2


# ----------------------------------------------------------------------
# Mapping vers source externe
# ----------------------------------------------------------------------

class TestMappingConstraints:
    def test_mapping_requires_known_source(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/test/x",
            "x",
        )
        with db_conn.cursor() as cur:
            with pytest.raises(ForeignKeyViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_mapping "
                    "(concept_id, target_source_id, target_uri, mapping_relation) "
                    "VALUES (%s, 99999, 'https://example.org/x', 'exactMatch')",
                    (cid,),
                )

    def test_mapping_to_known_source_succeeds(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_air",
            "temperature_air",
        )
        with db_conn.cursor() as cur:
            cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'CF'")
            row = cur.fetchone()
            assert row is not None
            cf_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_mapping "
                "(concept_id, target_source_id, target_uri, mapping_relation) "
                "VALUES (%s, %s, %s, 'exactMatch')",
                (cid, cf_id, "https://cfconventions.org/Data/cf-standard-names/77/build/cf-standard-name-table.html#air_temperature"),
            )


# ----------------------------------------------------------------------
# Concept physical : value_type valide, range cohérent
# ----------------------------------------------------------------------

class TestConceptPhysicalConstraints:
    def test_range_min_must_not_exceed_range_max(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/test/x",
            "x",
        )
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_physical "
                    "(concept_id, value_type, range_min, range_max) "
                    "VALUES (%s, 'scalar', 100, 50)",
                    (cid,),
                )

    def test_value_type_must_be_in_enum(self, db_conn: Connection) -> None:
        cid = _insert_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/test/x",
            "x",
        )
        with db_conn.cursor() as cur:
            with pytest.raises(CheckViolation):
                cur.execute(
                    "INSERT INTO vocab.concept_physical "
                    "(concept_id, value_type) VALUES (%s, 'matrix')",
                    (cid,),
                )
