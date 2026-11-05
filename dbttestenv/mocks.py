import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import sqlalchemy
from sqlalchemy import text, Connection

from .dbt_runner import run_dbt


def get_db_obj_types(objects: list[str], connection: Connection, schema: str):
    """Hent database typer for objekter."""
    skjema = sqlalchemy.inspect(connection)
    mviews = skjema.get_materialized_view_names(schema)
    views = skjema.get_view_names(schema)
    tables = skjema.get_table_names(schema)
    db_types = {}
    for name in objects:
        if name in mviews:
            db_types[name] = "materialized view"
        elif name in views:
            db_types[name] = "view"
        elif name in tables:
            db_types[name] = "table"
        else:
            db_types[name] = None
    return db_types


def _get_schema(obj: type) -> str:
    table_args = getattr(obj, "__table_args__", {})
    if isinstance(table_args, dict):
        return table_args["schema"].upper()
    raise ValueError(f"{obj.__name__} has no 'schema' in __table_args__")


@contextmanager
def replace_views_with_tables(
        connection: Connection,
        objects: list[type],
        dbt_project_path: Path,
) -> Generator[None, None, None]:
    """Erstatt (materialiserte) visninger i refererte modeller med tabeller for testing.

    På den måten kan vi skrive senario data direkte til tabellene, uten at man må gå hele veien inn i
    kildetabellene og være avhengig på transformasjonene.

    Args:
        connection: SQLAlchemy Connection mot databasen.
        objects: Liste av ORM-klasser som representerer modellene som skal erstattes.
            Alle klasser må tilhøre samme skjema.
        dbt_project_path: Sti til dbt-prosjektet, brukes for å rekonstruere avhengighetene via dbt.
    """
    schemas = {_get_schema(obj) for obj in objects}
    if len(schemas) != 1:
        raise ValueError(f"Alle avhengigheter må tilhøre samme skjema, fant: {schemas}")
    schema = schemas.pop()

    object_names = [obj.__tablename__ for obj in objects]

    run = lambda sql: connection.execute(text(sql))

    rebuild = lambda: run_dbt("run", dbt_project_path=dbt_project_path,
                              select=[name for name in object_names])

    # Sjekk den aktuelle tilstand av databasne fordi en tidligere
    # kjøring kan ha blitt avbrutt før den hadde rydded opp etter seg.
    db_types = get_db_obj_types(object_names, connection, schema)

    run(f"ALTER SESSION SET CURRENT_SCHEMA = {schema}")

    # I tilfelle en tidligere kjøring har ikke ryddet opp etter seg, og objekter mangler, opprett alle på nytt ved å
    # kjøre dbt
    if any(v is None for v in db_types.values()):
        for name, obj_type in db_types.items():
            if obj_type is not None:
                run(f'DROP {obj_type} IF EXISTS {name}')

        rebuild()

        db_types = get_db_obj_types(object_names, connection, schema)

    for name, db_type in db_types.items():
        tmp_table_name = f"{name}_tmp"
        # Rydd opp om tmp-tabellen finnes fra tidligere kjøring
        run(f'DROP TABLE IF EXISTS {tmp_table_name}')

        if db_type != "table":
            # erstatt visning eller materialisert visning med en tabell
            run(f'CREATE TABLE {tmp_table_name} AS SELECT * FROM {name}')
            run(f'DROP {db_type} {name}')
            run(f'CREATE TABLE {name} AS SELECT * FROM {tmp_table_name}')
            run(f'DROP TABLE {tmp_table_name}')

    # Kjør testene
    yield

    # Hvis ikke det er satt et miljøvariable som sier at vi skal beholde tabellen, gjenopprette den. Det kan være
    # nyttig å hoppe over dette skrittet når man utvikler, da sparer man litt tid.
    if not os.getenv("KEEP_MVIEW_TABLE_REPLACEMENTS", "false").lower() in ("true", "1"):
        for name in object_names:
            run(f'DROP TABLE IF EXISTS {name}')

        rebuild()
