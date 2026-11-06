from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import sqlalchemy
from sqlalchemy import text, MetaData, Connection

from .config import TestenvConfig

TEST_CONTAINER_CREDENTIALS_FILE = Path(".testcontainer_credentials")


@dataclass
class ConnectionConfig:
    host: str
    port: int
    service_name: str
    user: str
    password: str

    @property
    def connection_url(self) -> str:
        """Return the connection string for the Oracle database."""
        return (f'oracle+oracledb://{self.user}:{self.password}@{self.host}:{self.port}'
                f'/?service_name={self.service_name}')

    @classmethod
    def from_connection_url(cls, connection_string: str):
        """Parse a connection url and return a Connection object."""
        import re
        pattern = re.compile(
            r'^[\w+]+://'
            r'(?P<user>[^:]+):(?P<password>[^@]+)@'
            r'(?P<host>[^:]+):(?P<port>\d+)/\?'
            r'service_name=(?P<service_name>[^&]+)$'
        )
        match = pattern.match(connection_string)
        if match:
            return cls(**match.groupdict())

        raise ValueError("Invalid connection url format.")

    def __str__(self):
        return (f"ConnectionConfig(host={self.host}, port={self.port}, "
                f"service_name={self.service_name}, user={self.user})")

    def __repr__(self):
        return self.__str__()


def read_test_db_credentials_from_disk() -> str | None:
    """Read the system user test container database credentials from .testcontainer_credentials.

    The file is either in the working directory, or the function searches in the parent directories to find
    the root project directory (where pyproject.toml is) and takes the file from there.
    """
    work_dir = Path.cwd()
    credentials_file = TEST_CONTAINER_CREDENTIALS_FILE
    if not (work_dir / credentials_file).exists():
        for candidate in [work_dir] + list(work_dir.parents):
            if (candidate / "pyproject.toml").exists():
                credentials_file = candidate / TEST_CONTAINER_CREDENTIALS_FILE
                break

    if credentials_file and credentials_file.exists():
        return credentials_file.read_text(encoding="utf-8").strip()

    return None


def write_random_db_credentials_to_disk() -> str:
    """Write a random credential to .testcontainer_credentials in project root directory.
    """
    # random string of 12 characters
    import random
    import string
    random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    work_dir = Path.cwd()
    credentials_file = None
    for candidate in [work_dir] + list(work_dir.parents):
        if (candidate / "pyproject.toml").exists():
            credentials_file = candidate / TEST_CONTAINER_CREDENTIALS_FILE
            break

    if not credentials_file:
        raise RuntimeError(
            "Could not find project root directory (with pyproject.toml) to write credentials file."
        )

    credentials_file.write_text(random_password, encoding="utf-8")
    return random_password


def get_connection_config() -> ConnectionConfig:
    """Get the default connection config for the Oracle test container.

    The credentials will be read from .testcontainer_credentials if it exists in the working directory or project root,
    otherwise random credentials will be generated and written to the file in the project root.
    """
    credentials = read_test_db_credentials_from_disk()
    if not credentials:
        credentials = write_random_db_credentials_to_disk()

    return ConnectionConfig(
        # this is not actually used by testcontainers, which removed the option to bind to a host and uses the
        # docker engine default, but we need it to connect to the database from the test code. Assume localhost.
        host="127.0.0.1",
        port=1521,
        service_name="FREEPDB1",
        user="system",
        password=credentials,
    )


def test_connection(config: ConnectionConfig) -> bool:
    """Test the connection to the Oracle database."""
    try:
        engine = sqlalchemy.create_engine(config.connection_url)
        with engine.connect() as connection:
            connection.execute(text("select 1 from dual"))
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


def _get_source_metadata(config: TestenvConfig) -> MetaData:
    from . import model_generator
    return model_generator.collect(config.models_output_dir, dbt_models=False)


def initialize_database(connection: Connection, config: TestenvConfig):
    """Create all schemas and source tables. Idempotent."""
    sql_path = Path(__file__).parent / "sql" / "ensure_schema_exists.sql"
    ensure_schema_exists_sql = sql_path.read_text(encoding="utf-8")

    if config.pre_source_schema_init:
        config.pre_source_schema_init(connection)

    source_metadata = _get_source_metadata(config)
    source_schema_names: set[str] = {
        table.schema for table in source_metadata.tables.values() if table.schema
    }

    all_schemas = source_schema_names | {config.dbt_schema} | set(config.extra_schemas)
    for schema in all_schemas:
        connection.execute(text(ensure_schema_exists_sql), {"schema_name": schema})

    source_metadata.create_all(connection)

    for table in source_metadata.tables.values():
        if table.schema and table.schema.upper() != config.dbt_schema.upper():
            connection.execute(
                text(
                    f"GRANT SELECT ON {table.schema}.{table.name} TO {config.dbt_schema} WITH GRANT OPTION"
                )
            )

    for sql_file in config.init_sql_files:
        connection.execute(text(sql_file.read_text(encoding="utf-8")))

    if config.post_source_schema_init:
        config.post_source_schema_init(connection)

    connection.commit()


def truncate_schemas(connection: Connection, schemas: Iterable[str]):
    """Truncate all tables in all source schemas and the DBT schema."""
    sql_path = Path(__file__).parent / "sql" / "truncate_schema.sql"
    truncate_sql = sql_path.read_text(encoding="utf-8")

    for schema in schemas:
        connection.execute(text(truncate_sql), {"schema_name": schema})

    connection.commit()


def truncate_all_schemas(connection: Connection, config: TestenvConfig):
    source_metadata = _get_source_metadata(config)
    all_schema_names: set[str] = (
        {table.schema for table in source_metadata.tables.values() if table.schema}
        | {config.dbt_schema}
        | set(config.extra_schemas)
    )
    truncate_schemas(connection, all_schema_names)


def seed(connection: Connection, config: TestenvConfig):
    if not config.seed_sql_dir or not config.seed_sql_dir.exists():
        return

    for seed_file in config.seed_sql_dir.glob("*.sql"):
        seed_sql = seed_file.read_text(encoding="utf-8")
        connection.execute(text(seed_sql))

    connection.commit()


def dbt_schema_is_missing_models(connection: Connection, config: TestenvConfig) -> bool:
    from . import model_generator
    dbt_models_file = config.models_output_dir / "dbt_models.py"
    if not dbt_models_file.exists():
        return False

    dbt_module = model_generator.import_module_from_path(dbt_models_file)
    db_inspector = sqlalchemy.inspect(connection)
    return any(
        not db_inspector.has_table(tbl.name, schema=tbl.schema)
        for tbl in dbt_module.Base.metadata.tables.values()
    )


def trunc(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
