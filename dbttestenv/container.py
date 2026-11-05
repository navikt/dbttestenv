import logging
import os
from typing import Generator
from time import sleep

import docker
import sqlalchemy
from testcontainers.core import testcontainers_config
from testcontainers.oracle import OracleDbContainer

from .config import TestenvConfig
from .dbt_runner import set_dbt_env, run_dbt
from .oracle import ConnectionConfig, get_connection_config, test_connection, truncate_all_schemas, seed, \
    dbt_schema_is_missing_models

CONTAINER_NAME = "testcontainers-oracle-db"

logger = logging.getLogger(__name__)


def assert_database_available(connection_config: ConnectionConfig) -> None:
    waited = 0
    while waited < 20:
        if test_connection(connection_config):
            break
        waited += 1
        sleep(1)
    else:
        raise RuntimeError(
            f"Could not connect to Oracle test container '{CONTAINER_NAME}' after waiting {waited}s. "
            f"Try restarting the test, or deleting the container with `docker container rm -f {CONTAINER_NAME}`.")


def oracle_test_container_as_is() -> Generator[ConnectionConfig, None, None]:
    """Start or reuse an Oracle test container. No initialization is performed.

    If DBTTESTENV_CLEANUP_CONTAINER is set to true, containers will be deleted after the test session.
    If DBTTESTENV_NO_CONTAINER_MANAGEMENT is set to true, the testenv will not manage the container, and will assume it is already running.
    """
    do_cleanup = os.getenv('DBTTESTENV_CLEANUP_CONTAINER', 'false').lower() == 'true'
    no_container_mgmt = os.getenv('DBTTESTENV_NO_CONTAINER_MANAGEMENT', 'false').lower() == 'true'

    connection_config = get_connection_config()

    if no_container_mgmt:
        logger.info("DBTTESTENV_NO_CONTAINER_MANAGEMENT is set, assuming Oracle test container is already running.")
        assert_database_available(connection_config)
        yield connection_config
        logger.info("DBTTESTENV_NO_CONTAINER_MANAGEMENT is set, no container cleanup will be performed.")
        return

    try:
        client = docker.from_env()
        # this will raise an error if the container is not found
        container = client.containers.get(CONTAINER_NAME)

        if container.status == 'running':
            logger.info(f"Using running container '{CONTAINER_NAME}'.")
        else:
            logger.info(f"Found container '{CONTAINER_NAME}' with status '{container.status}', starting it")
            container.start()

            assert_database_available(connection_config)

        yield connection_config

        if do_cleanup:
            logger.info(f"Stopping and removing oracle test container '{CONTAINER_NAME}'")
            container.remove(force=True)

        return

    except docker.errors.NotFound:
        logger.info(f"No existing container with name '{CONTAINER_NAME}' found, creating new one")
        pass
        # fall through to start a new container

    # Don't start the supervisor container, because it needs to be privileged. The worst
    # that can happen is that the container will continue running. This is only an issue
    # when running in a CI environment.
    testcontainers_config.ryuk_disabled = True

    oracle = OracleDbContainer(
        oracle_password=connection_config.password,
        dbname=connection_config.service_name
    )

    # Set the time zone to local, default is UTC which can cause issues when converting to local time
    oracle.with_env("TZ", "Europe/Oslo")
    oracle.with_env("ORA_SDTZ", "Europe/Oslo")

    # testcontainer removed the option to specify the hostname, uses docker-engine default
    # we want a fixed container such that IDE/CLI tools can connect to the db
    oracle.with_bind_ports(1521, connection_config.port)

    # fixed name for reuse and error messages should a container be running from before
    oracle.with_name(CONTAINER_NAME)

    try:
        logger.info(f"Creating oracle test container '{CONTAINER_NAME}'")
        oracle.start()

        yield connection_config
    finally:
        if do_cleanup:
            logger.info(f"Stopping and removing oracle test container '{CONTAINER_NAME}'")
            oracle.stop()
        else:
            logger.info(f"Test container '{CONTAINER_NAME}' is left running. "
                        f"Run `docker container stop {CONTAINER_NAME}` to stop it or "
                        f"delete it with `docker container rm -f {CONTAINER_NAME}`. "
                        f"Set AMS_TEST_CLEANUP_CONTAINER=true to automatically remove containers after tests.")


def oracle_test_container(conn_cfg: ConnectionConfig, config: TestenvConfig) -> ConnectionConfig:
    """Initialize the Oracle test container: create schemas, run dbt.

    When reusing a container, existing schemas and tables will not be modified.
    Runs all lifecycle hooks defined on config.
    """
    from .oracle import initialize_database

    engine = sqlalchemy.create_engine(conn_cfg.connection_url)

    with engine.connect() as connection:
        if config.pre_testenv_setup:
            config.pre_testenv_setup(connection)

        initialize_database(connection, config)
        truncate_all_schemas(connection, config)
        seed(connection, config)

        dbt_schema_initialization_required = dbt_schema_is_missing_models(connection, config)

    set_dbt_env(conn_cfg, config.dbt_schema)

    if dbt_schema_initialization_required:
        logger.info("DBT schema is missing models, running dbt to initialize all objects.")

        if config.pre_dbt_init:
            with engine.connect() as connection:
                config.pre_dbt_init(connection)

        # all objects are empty at this point, so running dbt will create the schema
        # without doing any transformations yet.
        run_dbt("deps", dbt_project_path=config.dbt_project_path, raise_on_error=True)
        run_dbt(
            "build",
            "--exclude-resource-type", "test",
            dbt_project_path=config.dbt_project_path,
            raise_on_error=True,
        )

        if config.post_dbt_init:
            with engine.connect() as connection:
                config.post_dbt_init(connection)

    if config.post_testenv_setup:
        with engine.connect() as connection:
            config.post_testenv_setup(connection)

    return conn_cfg
