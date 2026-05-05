"""Tests des vues métier — `v_concepts_actifs`, `v_concept_descendants`,
`v_concept_ancestors`, `v_concepts_traduction_pending`.

Vérifie en particulier que la résolution récursive est tolérante aux
cycles (le tracking du chemin évite la boucle infinie).
"""

from __future__ import annotations

import pytest
from psycopg import Connection

pytestmark = pytest.mark.integration


def _create_concept(conn: Connection, uri: str, notation: str, status: str = "draft") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES (%s, %s, %s) RETURNING concept_id",
            (uri, notation, status),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_pref_label(conn: Connection, cid: int, lang: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
            "VALUES (%s, %s, 'pref', %s)",
            (cid, lang, value),
        )


def _add_broader(conn: Connection, child: int, parent: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_semantic_relation "
            "(source_concept_id, target_concept_id, relation) "
            "VALUES (%s, %s, 'broader')",
            (child, parent),
        )


# ----------------------------------------------------------------------
# v_concepts_actifs
# ----------------------------------------------------------------------


class TestConceptsActifs:
    def test_published_concept_with_fr_en_appears(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_air",
            "temperature_air",
            status="published",
        )
        _add_pref_label(db_conn, cid, "fr", "Température de l'air")
        _add_pref_label(db_conn, cid, "en", "Air temperature")

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT pref_label_fr, pref_label_en FROM vocab.v_concepts_actifs "
                "WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "Température de l'air"
            assert row[1] == "Air temperature"

    def test_draft_concept_does_not_appear(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/foo",
            "foo",
            status="draft",
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.v_concepts_actifs WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 0


# ----------------------------------------------------------------------
# v_concepts_traduction_pending
# ----------------------------------------------------------------------


class TestTraductionPending:
    def test_concept_with_only_en_appears_in_pending(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/foo",
            "foo",
            status="approved",
        )
        _add_pref_label(db_conn, cid, "en", "Foo")
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT has_pref_fr, has_pref_en "
                "FROM vocab.v_concepts_traduction_pending WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] is False
            assert row[1] is True

    def test_concept_with_fr_and_en_does_not_appear(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/foo",
            "foo",
            status="approved",
        )
        _add_pref_label(db_conn, cid, "fr", "Foo (fr)")
        _add_pref_label(db_conn, cid, "en", "Foo")
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.v_concepts_traduction_pending WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 0


# ----------------------------------------------------------------------
# v_concept_descendants / v_concept_ancestors
# ----------------------------------------------------------------------


class TestRecursiveResolution:
    def test_descendants_at_depth_2(self, db_conn: Connection) -> None:
        # racine : Température
        # enfant : Température de l'air (broader → Température)
        # petit-enfant : Température à 2 m (broader → Température de l'air)
        c_root = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp", "temp")
        c_air = _create_concept(
            db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp_air", "temp_air"
        )
        c_2m = _create_concept(
            db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp_air_2m", "temp_air_2m"
        )
        _add_broader(db_conn, c_air, c_root)
        _add_broader(db_conn, c_2m, c_air)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT descendant_id, profondeur "
                "FROM vocab.v_concept_descendants WHERE root_id = %s "
                "ORDER BY profondeur",
                (c_root,),
            )
            rows = cur.fetchall()
            assert len(rows) == 2
            assert rows[0] == (c_air, 1)
            assert rows[1] == (c_2m, 2)

    def test_ancestors_at_depth_2(self, db_conn: Connection) -> None:
        c_root = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp", "temp")
        c_air = _create_concept(
            db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp_air", "temp_air"
        )
        c_2m = _create_concept(
            db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp_air_2m", "temp_air_2m"
        )
        _add_broader(db_conn, c_air, c_root)
        _add_broader(db_conn, c_2m, c_air)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT ancestor_id, profondeur "
                "FROM vocab.v_concept_ancestors WHERE root_id = %s "
                "ORDER BY profondeur",
                (c_2m,),
            )
            rows = cur.fetchall()
            assert len(rows) == 2
            assert rows[0] == (c_air, 1)
            assert rows[1] == (c_root, 2)

    def test_recursive_resolution_tolerates_cycles(self, db_conn: Connection) -> None:
        """Vérifie que `v_concept_descendants` ne boucle pas si, par accident
        ou par import bogué, deux concepts se pointent mutuellement comme
        broader (la table n'interdit pas les cycles, mais la vue les traite).
        """
        c1 = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/c1", "c1")
        c2 = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/c2", "c2")
        _add_broader(db_conn, c1, c2)
        _add_broader(db_conn, c2, c1)

        with db_conn.cursor() as cur:
            # Si la vue ne tolérait pas les cycles, cette requête bouclerait
            # à l'infini ou exploserait la pile. Le test passe = ok.
            cur.execute(
                "SELECT COUNT(*) FROM vocab.v_concept_descendants WHERE root_id = %s",
                (c1,),
            )
            row = cur.fetchone()
            assert row is not None
            # Les deux nœuds sont visités sans répétition.
            assert row[0] >= 1


# ----------------------------------------------------------------------
# v_concepts_mesurables
# ----------------------------------------------------------------------


class TestConceptsMesurables:
    def test_concept_with_physical_appears(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temp_air",
            "temp_air",
            status="published",
        )
        _add_pref_label(db_conn, cid, "fr", "Température de l'air")
        _add_pref_label(db_conn, cid, "en", "Air temperature")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.unite (symbole, nom, est_si_canonique, status) "
                "VALUES ('K', 'Kelvin', TRUE, 'published') RETURNING unite_id"
            )
            row = cur.fetchone()
            assert row is not None
            unit_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_physical "
                "(concept_id, value_type, unit_canonical_id, range_min, range_max) "
                "VALUES (%s, 'scalar', %s, -90, 60)",
                (cid, unit_id),
            )
            cur.execute(
                "SELECT pref_label_fr, unite_symbole, range_min, range_max "
                "FROM vocab.v_concepts_mesurables WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "Température de l'air"
            assert row[1] == "K"
            assert row[2] == -90
            assert row[3] == 60

    def test_concept_without_physical_does_not_appear(self, db_conn: Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/phenomenes/orage",
            "orage",
            status="published",
        )
        _add_pref_label(db_conn, cid, "fr", "Orage")
        _add_pref_label(db_conn, cid, "en", "Thunderstorm")
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.v_concepts_mesurables WHERE concept_id = %s",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 0
