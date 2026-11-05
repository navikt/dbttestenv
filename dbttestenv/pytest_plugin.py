from typing import Generator

import pytest
import sqlalchemy
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from dbttestenv.config import TestenvConfig
from dbttestenv.container import oracle_test_container_as_is
from dbttestenv.container import oracle_test_container as _setup_container
from dbttestenv.fakes import FakerFactory
from dbttestenv.oracle import ConnectionConfig, truncate_all_schemas, seed


@pytest.fixture(scope='session')
def testenv_config() -> TestenvConfig:
    from dbttestenv.testenv import load_config
    return load_config()


@pytest.fixture(scope='session')
def _oracle_test_container_as_is() -> Generator[ConnectionConfig, None, None]:
    yield from oracle_test_container_as_is()


@pytest.fixture(scope='session')
def oracle_test_container(
    _oracle_test_container_as_is: ConnectionConfig,
    testenv_config: TestenvConfig,
) -> ConnectionConfig:
    return _setup_container(_oracle_test_container_as_is, testenv_config)


@pytest.fixture(scope='function')
def connection(oracle_test_container: ConnectionConfig, testenv_config: TestenvConfig) -> Generator[Connection, None, None]:
    engine = sqlalchemy.create_engine(oracle_test_container.connection_url)
    with engine.connect() as connection:
        truncate_all_schemas(connection, testenv_config)
        seed(connection, testenv_config)
        yield connection


@pytest.fixture(scope='function')
def session(connection: Connection) -> Generator[Session, None, None]:
    with Session(bind=connection) as session:
        yield session


@pytest.fixture(scope='module')
def connection_module_scope(oracle_test_container: ConnectionConfig, testenv_config: TestenvConfig) -> Generator[Connection, None, None]:
    engine = sqlalchemy.create_engine(oracle_test_container.connection_url)
    with engine.connect() as connection:
        truncate_all_schemas(connection, testenv_config)
        seed(connection, testenv_config)
        yield connection


@pytest.fixture(scope='module')
def session_module_scope(connection_module_scope: Connection) -> Generator[Session, None, None]:
    with Session(bind=connection_module_scope) as session:
        yield session


@pytest.fixture(scope='class')
def connection_class_scope(oracle_test_container: ConnectionConfig, testenv_config: TestenvConfig) -> Generator[Connection, None, None]:
    engine = sqlalchemy.create_engine(oracle_test_container.connection_url)
    with engine.connect() as connection:
        truncate_all_schemas(connection, testenv_config)
        seed(connection, testenv_config)
        yield connection


@pytest.fixture(scope='class')
def session_class_scope(connection_class_scope: Connection) -> Generator[Session, None, None]:
    with Session(bind=connection_class_scope) as session:
        yield session


@pytest.fixture(scope="function")
def ff() -> FakerFactory:
    return FakerFactory()
