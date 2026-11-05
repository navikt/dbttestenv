#!/usr/bin/env python
# Brought to you by copilot
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import sys

TESTCONTAINER_NAME = "testcontainers-oracle-db"

def print_header(text):
    """Print a header with the given text."""
    print(f"\n{'=' * 80}")
    print(f" {text}")
    print(f"{'=' * 80}")


def print_note(text: object) -> None:
    """Print a information."""
    print(f"  → {text}")


def print_status(text, status, details=None):
    """Print a status message with a colored indicator."""
    status_str = f"{'✅' if status else '❌'}"
    print(f" {status_str} {text}")
    if not status and details:
        if isinstance(details, list):
            for detail in details:
                print_note(detail)
        else:
            print_note(details)


def find_project_root():
    """Find the project root by looking for pyproject.toml."""
    cwd = Path.cwd()
    for path in [cwd] + list(cwd.parents):
        if (path / "pyproject.toml").exists():
            return path
    return None


def test_docker_connection() -> tuple[bool, object]:
    """Test if we can connect to the Docker daemon."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True, client
    except ImportError:
        return False, "Docker Python library not installed. Run: pip install docker"
    except Exception as e:
        return False, str(e)


def check_image_exists(client, image_name):
    """Check if the specified Docker image exists locally."""
    try:
        client.images.get(image_name)
        return True
    except Exception:
        return False


def check_container_status(client, container_name: str):
    """Check if a container with the given name exists and its status."""
    try:
        container = client.containers.get(container_name)
        return True, container
    except Exception:
        return False, None


def test_oracle_connection(connection_config):
    """Test connection to Oracle database."""
    try:
        from dbttestenv.oracle import test_connection
        return test_connection(connection_config)
    except ImportError:
        return False, "Cannot import test_connection function"
    except Exception as e:
        return False, str(e)


def get_connection_config():
    """Get connection config for Oracle test container."""
    try:
        from dbttestenv.oracle import get_connection_config
        return get_connection_config()
    except ImportError:
        raise


def check_venv():
    """Check if running in a virtual environment."""
    return sys.prefix != sys.base_prefix


def get_running_colima_instance_info() -> dict | None:
    """Get Colima instance information of the first running instance."""
    result = subprocess.run(['colima', 'list', '--json'], capture_output=True, text=True)
    if result.returncode == 0:
        colima_info = json.loads(result.stdout)
        if not isinstance(colima_info, list):
            colima_info = [colima_info]

        for instance in colima_info:
            if instance.get('status') == 'Running':
                return instance

    return None


def check_docker_memory(client):
    """Check Docker memory allocation."""
    try:
        if platform.system() == "Darwin":  # macOS
            colima_info = get_running_colima_instance_info()
            if not colima_info:
                return False, "Could not find a running colima instance (see `colima list`)"

            return True, int(colima_info.get('memory', 0))
        else:  # Linux, Windows
            info = client.info()
            memory_bytes = info.get('MemTotal', 0)
            memory_gb = memory_bytes / (1024 ** 3)
            return True, memory_gb
    except Exception as e:
        return False, str(e)


def run_diagnose():
    print_header("DBT Test Environment Diagnostics")

    issues_found = 0
    system = platform.system()
    print(f"Operating System: {system}")

    # Find project root
    project_root = find_project_root()
    if project_root:
        print_status(f"Project root found at {project_root}", True)
        os.chdir(project_root)  # Change to project root
    else:
        print_status("Project root with pyproject.toml not found", False,
                     "Navigate to your project directory or subdirectory")
        issues_found += 1

    # Check Python installation
    print_status(f"Python {sys.version.split()[0]} is installed", True)

    # Check virtual environment
    in_venv = check_venv()
    print_status("Running in virtual environment", in_venv,
                 "Create and activate a virtual environment with: python -m venv .venv && source .venv/bin/activate (Unix) or .venv\\Scripts\\activate (Windows)")
    if not in_venv:
        issues_found += 1

    # Check uv installation
    uv_installed = shutil.which("uv") is not None
    print_status("uv package manager is installed", uv_installed,
                 "Install uv: pip install --user uv")
    if not uv_installed:
        issues_found += 1

    # Check dbt, pytest and testcontainer installation
    try:
        import dbt
        dbt_installed = True
    except ImportError:
        dbt_installed = False
    print_status("dbt is installed", dbt_installed,
                 "Install dependencies: 'uv sync'")
    if not dbt_installed:
        issues_found += 1

    try:
        import pytest
        pytest_installed = True
    except ImportError:
        pytest_installed = False
    print_status("pytest is installed", pytest_installed,
                 "Install pytest: 'uv sync --group test'")
    if not pytest_installed:
        issues_found += 1

    try:
        import testcontainers
        testcontainers_installed = True
    except ImportError:
        testcontainers_installed = False
    print_status("testcontainers is installed", testcontainers_installed,
                 "Install testcontainers: 'uv sync --group test'")
    if not testcontainers_installed:
        issues_found += 1

    # Check Docker/container system
    container_engine = None
    if system == "Darwin":  # macOS
        print_header("MacOS Specific Checks")

        # Check Colima
        colima_installed = shutil.which("colima") is not None
        print_status("Colima is installed", colima_installed,
                     "Install Colima: brew install colima")
        if not colima_installed:
            issues_found += 1

        # Check if Colima is running
        if colima_installed:
            colima_running = get_running_colima_instance_info() is not None
            print_status("Colima is running", colima_running,
                         "Start Colima: colima start")
            if not colima_running:
                issues_found += 1

        # Check Docker
        docker_installed = shutil.which("docker") is not None
        print_status("Docker is installed", docker_installed,
                     "Install Docker: brew install docker")
        if not docker_installed:
            issues_found += 1

        # Check DOCKER_HOST
        docker_host = os.environ.get("DOCKER_HOST")
        user = os.environ.get("USER") or "<your user>"
        print_status(f"DOCKER_HOST environment variable is set to {docker_host}", docker_host is not None,
                     [
                         "Run 'colima status' to obtain the location of your docker socket, export DOCKER_HOST accordingly",
                         f"Example: export DOCKER_HOST=unix:///Users/{user}/.colima/default/docker.sock",
                         "Consider adding this line to your shell profile (~/.bashrc, ~/.zshrc, etc.)"
                     ])
        if not docker_host:
            issues_found += 1

        container_engine = "Colima (Docker)"

    elif system == "Windows":
        print_header("Windows Specific Checks")

        # Check Docker Desktop or Podman
        docker_installed = shutil.which("docker") is not None
        podman_installed = shutil.which("podman") is not None

        if docker_installed:
            container_engine = "Docker"
        elif podman_installed:
            container_engine = "Podman"

        print_status("Docker or Podman is installed", container_engine is not None,
                     "Install Docker Desktop for Windows (needs a license) or Podman")
        if container_engine is None:
            issues_found += 1

    # Common Docker checks
    no_container_mgmt = os.getenv('DBTTESTENV_NO_CONTAINER_MANAGEMENT', 'false').lower() == 'true'
    print_header("Container Checks")
    docker_connection, container_exists, container_status = None, None, None
    if no_container_mgmt:
        print_note("DBTTESTENV_NO_CONTAINER_MANAGEMENT is set, skipping container engine checks")
    else:
        docker_connection, docker_client = test_docker_connection()
        print_status("Can connect to Docker daemon", docker_connection is True,
                     docker_client if docker_connection is False else None)
        if not docker_connection:
            issues_found += 1

        container_exists, container_status = False, None
        if docker_connection is True:
            # Check memory allocation
            memory_check, memory_value = check_docker_memory(docker_client)
            if memory_check:
                has_enough_memory = memory_value >= 4
                print_status(f"Docker has enough memory ({memory_value:.1f} GB)", has_enough_memory,
                             f"Increase Docker memory to at least 4GB (current: {memory_value:.1f} GB)")
                if not has_enough_memory:
                    issues_found += 1
            else:
                print_status("Failed to check Docker memory", False, memory_value)
                issues_found += 1

            # Check if Oracle image exists
            oracle_image = "gvenzl/oracle-free:slim"
            image_exists = check_image_exists(docker_client, oracle_image)
            print_status(f"Oracle image '{oracle_image}' exists", image_exists,
                         f"Image will be downloaded during first test run (may take time)")

            from .container import CONTAINER_NAME
            container_name = CONTAINER_NAME
            container_exists, container = check_container_status(docker_client, container_name)
            container_status = container.status if container_exists else None
            ok_exit_codes = [
                0,    # Exited normally
                143   # Terminated (e.g., SIGTERM)
            ]
            if container_exists:
                if container.status == "running":
                    print_status(f"Oracle test container exists (status: {container.status})", True)
                    print_note("Container is already running, tests will reuse it")
                    print_note(f"To stop: docker container stop {container_name}")
                    print_note(f"To remove: docker container rm -f {container_name}")
                    print_note("Removing the container will rebuild the schema with dbt on next test run")
                elif container.status == "exited" \
                        and not (exit_code := container.attrs.get('State', {}).get('ExitCode', 0)) in ok_exit_codes:
                    print_status(f"Oracle test container failed last run (status: {container.status}, code: {exit_code})", False)
                    print_note(f"Review container logs with: docker logs {container_name}")
                    print_note(f"Try restarting {container_engine}")
                    print_note(f"Try removing the container and running tests again")
                    print_note(f"To remove: docker container rm -f {container_name}")
                    issues_found += 1
                else:
                    print_status(f"Oracle test container exists (status: {container.status})", True)
                    print_note("Container exists but is not running, tests will start it")
                    print_note(f"Start manually: docker container start {container_name}")
                    print_note(f"To remove: docker container rm -f {container_name}")
                    print_note("Removing the container will rebuild the schema with dbt on next test run")
            else:
                print_status("No existing Oracle test container", True)
                print_note("A new container will be created during test run")

    # Check credentials file
    if project_root:
        credential_file_name = ".testcontainer_credentials"
        credentials_file = project_root / credential_file_name
        credentials_exist = credentials_file.exists()
        print_status(f"{credential_file_name} file exists in project root", credentials_exist)
        if not credentials_exist:
            print_note("File will be created with random password during first test run")
            print_note("You can also create it manually with a password of your choice")

    # Try to test database connection if container exists and is running
    if (docker_connection and container_exists and container_status == "running") or no_container_mgmt:
        connection_config = get_connection_config()
        if connection_config:
            print("Testing Oracle database connection...")
            try:
                if test_oracle_connection(connection_config):
                    print_status("Can connect to Oracle database", True)
                else:
                    print_status("Cannot connect to Oracle database", False,
                                 "Container is running but database connection failed")
                    issues_found += 1
            except Exception as e:
                print_status("Error testing Oracle connection", False, str(e))
                issues_found += 1

    # Some dbt versions require the folder ~/.dbt to exist
    dbt_dir = Path("~/.dbt").expanduser()
    if not dbt_dir.exists():
        print_status("~/.dbt folder does not exist, create it manually to avoid dbt errors", False)
        issues_found += 1
    elif dbt_dir.is_file():
        print_status("~/.dbt exists but is a file, it should be a folder", False)
        issues_found += 1


    # Final report
    print_header("Diagnostic Summary")
    if issues_found == 0:
        print_status("No issues detected! Your environment is ready to go.", True)

        print_header("Next Steps")
        print_note("Run tests with: uv run testenv pytest -- -k <test name>")
        print_note("Run dbt with: uv run testenv dbt -- run")
    else:
        print_status(f"Found {issues_found} issue(s) that need to be addressed before running tests.", False,
                     "Review the details above to resolve them.")

    return issues_found

def main():
    run_diagnose()

if __name__ == "__main__":
    main()
