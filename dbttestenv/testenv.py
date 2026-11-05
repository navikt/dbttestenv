#!/usr/bin/env python
import argparse
import contextlib
import importlib
import importlib.util
import io
import logging
import os
import json
import csv
from pathlib import Path
from typing import List, Any
from importlib.metadata import entry_points
from itertools import chain

import pytest
import sys

from .config import TestenvConfig
from .diagnose import run_diagnose, check_container_status, test_docker_connection


def load_config(config_module: str | None = None) -> TestenvConfig:
    """Load TestenvConfig from a Python module.

    Tries in order:
      1. Import as a dotted Python path (e.g. 'unit_tests.testenv_config')
      2. Search up the directory tree for a 'testenv_config.py' file
    The module must expose a 'config: TestenvConfig' attribute.
    """
    module_name = config_module or "testenv_config"
    if config_module is None:
        eps = entry_points(group="dbttestenv.config")
        if len(eps) == 1:
            return (next(iter(eps))).load()
        if len(eps) > 1:
            names = ", ".join(e.name for e in eps)
            raise RuntimeError(
                f"Multiple 'dbttestenv.config' entry points found: {names}. "
                "Pass --config-module to disambiguate."
            )
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        cwd = Path.cwd()
        for candidate in [cwd] + list(cwd.parents):
            config_file = candidate / f"{module_name.split('.')[-1]}.py"
            if config_file.exists():
                spec = importlib.util.spec_from_file_location("testenv_config", config_file)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not load config from {config_file}")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                break
        else:
            raise FileNotFoundError(
                f"Could not find config module '{module_name}'. "
                "Create a testenv_config.py with a 'config: TestenvConfig = ...' attribute, "
                "or pass --config-module with the dotted import path."
            )

    if not hasattr(module, "config"):
        raise AttributeError(f"Config module '{module_name}' does not expose a 'config' attribute.")

    return module.config


def no_container_management():
    no_container_mgmt = os.getenv('DBTTESTENV_NO_CONTAINER_MANAGEMENT', 'false').lower() == 'true'
    return no_container_mgmt


def diagnose_ok() -> bool:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return run_diagnose() == 0


def get_docker_client() -> Any | None:
    try:
        _, docker_client = test_docker_connection()
        return docker_client if docker_client else None
    except Exception:
        return None


def assert_docker_running():
    docker_client = get_docker_client()
    if not docker_client:
        print("❌ Cannot connect to Docker daemon. Run 'testenv diagnose' for details.")
        raise SystemExit(1)


def get_container() -> Any | None:
    docker_client = get_docker_client()
    if not docker_client:
        return None

    from .container import CONTAINER_NAME
    _, container = check_container_status(docker_client, CONTAINER_NAME)
    return container


def assert_container_running() -> Any:
    assert_docker_running()
    container = get_container()
    if not container:
        print("❌ No container found. Run 'testenv init' to create it.")
        raise SystemExit(1)
    if container.status != "running":
        print("❌ Container is not running. Run 'testenv start' to start it or 'testenv init --rm' to recreate it.")
        raise SystemExit(1)
    return container


def cmd_dbt(args: argparse.Namespace, config: TestenvConfig) -> int:
    if not no_container_management():
        assert_container_running()

    from .oracle import get_connection_config
    from .dbt_runner import set_dbt_env, run_dbt

    conn_cfg = get_connection_config()
    set_dbt_env(conn_cfg, config.dbt_schema)

    dbt_args = args.dbt_args
    if not dbt_args:
        dbt_args = ["--help"]

    run_dbt(dbt_args[0], *dbt_args[1:], dbt_project_path=config.dbt_project_path, raise_on_error=False)
    return 0


def cmd_status(args: argparse.Namespace, config: TestenvConfig) -> int:
    if diagnose_ok():
        container = get_container()
        if container:
            if container.status == "running":
                print("✅ No issues detected. Container is running.")
            else:
                print("✅ No issues detected. Container is stopped.")
        else:
            if no_container_management():
                print("✅ No issues detected.")
            else:
                print("✅ No issues detected. No container found.")
        return 0
    else:
        print("❌ Issues detected. Please run 'testenv diagnose' for details.")
        return 1


def cmd_init(args: argparse.Namespace, config: TestenvConfig) -> int:
    from .container import oracle_test_container_as_is, oracle_test_container

    if args.rm:
        container = get_container()
        if container:
            print("Removing existing container...")
            container.remove(force=True)

    assert_docker_running()

    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("dbttestenv.container").setLevel(logging.INFO)

    test_container = next(oracle_test_container_as_is())

    print("Initializing database...")
    oracle_test_container(test_container, config)

    print("✅ Container created.")
    return 0


def cmd_remove(args: argparse.Namespace, config: TestenvConfig) -> int:
    assert_docker_running()

    container = get_container()
    if container:
        if container.status == "running":
            if not args.force:
                print("❌ testcontainer is running. Remove anyways?")
                if input("Type 'y' to confirm: ") != "y":
                    print("Aborting.")
                    return 1
            container.remove(force=True)
            print("✅ Container removed.")
            return 0
        else:
            container.remove(force=True)
            print("✅ Container removed.")
            return 0
    else:
        print("❌ No container found to remove.")
        return 1


def cmd_start(args: argparse.Namespace, config: TestenvConfig) -> int:
    assert_docker_running()

    container = get_container()
    if container:
        if container.status == "running":
            print("❌ testcontainer is already running.")
            return 1
        else:
            container.start()
            print("✅ Container started.")
            return 0
    else:
        print("❌ No container found to start. Run 'testenv init' to create it.")
        return 1


def cmd_stop(args: argparse.Namespace, config: TestenvConfig) -> int:
    assert_docker_running()

    container = get_container()
    if container:
        if container.status == "running":
            container.stop()
            print("✅ Container stopped.")
            return 0
        else:
            print("❌ testcontainer is already stopped.")
            return 1
    else:
        print("❌ No container found to stop. Run 'testenv init' to create it.")
        return 1


def cmd_pytest(args: argparse.Namespace, config: TestenvConfig) -> int:
    if not no_container_management():
        assert_container_running()
    return pytest.main(args.pytest_args)


def cmd_clear(args: argparse.Namespace, config: TestenvConfig) -> int:
    """Truncate all schemas and re-seed the test database."""
    if not no_container_management():
        assert_container_running()

    import sqlalchemy
    from .oracle import get_connection_config, truncate_all_schemas, seed

    connection_config = get_connection_config()
    engine = sqlalchemy.create_engine(connection_config.connection_url)
    with engine.connect() as connection:
        truncate_all_schemas(connection, config)
        seed(connection, config)

    print("✅ Database cleared and re-seeded.")
    return 0


def cmd_diagnose(args: argparse.Namespace, config: TestenvConfig) -> int:
    return 0 if run_diagnose() == 0 else 1


def cmd_query(args: argparse.Namespace, config: TestenvConfig) -> int:
    """Run a SQL query against the test database and output results."""
    if not no_container_management():
        assert_container_running()

    import sqlalchemy
    from sqlalchemy import text
    from dbttestenv.oracle import get_connection_config

    config = get_connection_config()
    engine = sqlalchemy.create_engine(config.connection_url)

    try:
        with engine.connect() as connection:
            result = connection.execute(text(args.sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
    except Exception as e:
        print(f"❌ Query failed: {e}")
        return 1

    output_format = args.format

    if output_format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)

    elif output_format == "json":
        data = [dict(zip(columns, row)) for row in rows]
        print(json.dumps(data, indent=2, default=str))

    elif output_format == "markdown":
        sizes = [0 for _ in columns]
        for row in chain([columns], rows):
            for i, value in enumerate(row):
                sizes[i] = max(sizes[i], len(str(value)))

        # Header
        columns = [f"{col:>{sizes[i]}}" for i, col in enumerate(columns)]
        print("| " + " | ".join(columns) + " |")
        # Separator
        print("|-" + "-|-".join("-"*s for s in sizes) + "-|")
        # Rows
        for row in rows:
            row = [f"{str(value):>{sizes[i]}}" for i, value in enumerate(row)]
            print("| " + " | ".join(str(v) for v in row) + " |")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testenv",
        description="CLI to control the unit test environment.",
    )
    parser.add_argument(
        "--config-module",
        default=None,
        help="Dotted Python import path to the config module (default: 'testenv_config').",
    )

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    p_status = sub.add_parser("status", help="'testenv diagnose' pass/fail, container status.")
    p_status.set_defaults(func=cmd_status)

    p_init = sub.add_parser("init", help="Prepare the container, initialize sources and run dbt.")
    p_init.add_argument("--remove", "--rm", dest="rm", action="store_true",
                        help="Remove a running container without confirmation.")
    p_init.set_defaults(func=cmd_init)

    p_dbt = sub.add_parser("dbt", help="Run dbt against the test database container.")
    p_dbt.add_argument("dbt_args", nargs="*", help="Arguments passed through to dbt. Must be preceeded by --, for eksempel: 'testenv dbt -- run'")
    p_dbt.set_defaults(func=cmd_dbt)

    p_pytest = sub.add_parser("pytest", help="Check status and run pytest.")
    p_pytest.add_argument("pytest_args", nargs="*", help="Arguments passed through to pytest. Must be preceeded by --, for eksempel: 'testenv pytest -- -k mytest'")
    p_pytest.set_defaults(func=cmd_pytest)

    p_start = sub.add_parser("start", help="Start the test database container.")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop the test database container.")
    p_stop.set_defaults(func=cmd_stop)

    p_remove = sub.add_parser("remove", help="Remove the test database container.")
    p_remove.add_argument("--force", "-f", action="store_true", help="Force removal without confirmation.")
    p_remove.set_defaults(func=cmd_remove)

    p_clear = sub.add_parser("clear", help="Truncate all tables and re-seed the test database.")
    p_clear.set_defaults(func=cmd_clear)

    p_diagnose = sub.add_parser("diagnose", help="Run checks for problems with the system and test environment.")
    p_diagnose.set_defaults(func=cmd_diagnose)

    p_query = sub.add_parser("query", help="Run a SQL query against the test database.")
    p_query.add_argument("sql", help="The SQL query to execute.")
    p_query.add_argument("-f", "--format", choices=["csv", "markdown", "json"], default="markdown",
                         help="Output format (default: markdown).")
    p_query.set_defaults(func=cmd_query)

    p_heeelp = sub.add_parser("heeelp", help="Alias for 'diagnose'.")
    p_heeelp.set_defaults(func=cmd_diagnose)

    return parser


def main(argv: List[str] | None = None, config: TestenvConfig | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if config is None:
        config = load_config(args.config_module)

    return args.func(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
