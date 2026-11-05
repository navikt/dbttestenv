import json
from pathlib import Path

from dbt.cli.main import dbtRunner, dbtRunnerResult

from dbttestenv.oracle import ConnectionConfig


def set_dbt_env(config: ConnectionConfig, dbt_schema: str):
    """Set environment variables for the testcontainer Oracle database."""
    import os
    os.environ["DBT_HOST"] = config.host
    os.environ["DBT_PORT"] = str(config.port)
    os.environ["DBT_ENV_SERVICE_NAME"] = config.service_name
    os.environ["DBT_ENV_DB_NAME"] = config.service_name
    os.environ["DBT_ENV_SECRET_USER"] = config.user
    os.environ["DBT_ENV_SECRET_PASS"] = config.password
    os.environ["DBT_DB_SCHEMA"] = dbt_schema
    os.environ["DBT_DB_TARGET"] = "TEST"


def run_dbt(
        command: str,
        *args,
        dbt_project_path: Path,
        raise_on_error: bool = True,
        unittesting_var: bool = True,
        snapshot_passthrough_var: bool = True,
        **kwargs
) -> dbtRunnerResult:
    """Run a dbt command.

    Args:
        command (str): The dbt command to run, e.g., "build", "test", "run".
        dbt_project_path (Path): The path to the dbt project directory.
        raise_on_error (bool): Whether to raise an error if the dbt command fails.
            Defaults to True.
        unittesting_var (bool): Whether to set the "unittesting" variable to True. This enables optimizations, such as
            replacing materialized views with views. Defaults to True.
        snapshot_passthrough_var (bool): Whether to set the "snapshot_passthrough" variable to True. This enables
            snapshots to be sidelined by pointing to the source table directly. This way, dbt does not have to be run.
            Defaults to True.
        *args: Additional arguments for the dbt command (CLI).
        **kwargs: Additional keyword arguments for the dbt command,
            for example "select=["model1", "model2"], fail_fast=True".
    """
    dbt_cli = dbtRunner()
    dbt_directory = dbt_project_path.absolute()
    kwargs["project_dir"] = str(dbt_directory)
    kwargs["profiles_dir"] = str(dbt_directory)
    project_vars = {"unittesting": unittesting_var, "snapshot_passthrough": snapshot_passthrough_var}
    if "vars" in kwargs:
        kwargs_vars = kwargs["vars"]
        if isinstance(kwargs_vars, dict):
            project_vars.update(kwargs_vars)
        elif isinstance(kwargs_vars, str):
            project_vars.update(json.loads(kwargs_vars))
        else:
            raise ValueError("Invalid type for 'vars' argument. Must be dict or JSON string.")

    kwargs["vars"] = project_vars

    args = list(args) + ["--no-partial-parse"]
    result = dbt_cli.invoke([command] + args, **kwargs)
    if raise_on_error and not result.success:
        if result.exception:
            raise result.exception
        else:
            all_args = (
                    " ".join([command] + list(args))
                    + " "
                    + " ".join(f"--{k}={v}" for k, v in kwargs.items())
            )
            raise RuntimeError(f"DBT command '{all_args}' failed")

    return result
