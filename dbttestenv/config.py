from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy import Connection


@dataclass
class TestenvConfig:
    dbt_schema: str
    dbt_project_path: Path
    models_output_dir: Path

    extra_schemas: list[str] = field(default_factory=list)
    init_sql_files: list[Path] = field(default_factory=list)
    seed_sql_dir: Path | None = None

    pre_testenv_setup: Callable[[Connection], None] | None = None
    post_testenv_setup: Callable[[Connection], None] | None = None
    pre_source_schema_init: Callable[[Connection], None] | None = None
    post_source_schema_init: Callable[[Connection], None] | None = None
    pre_dbt_init: Callable[[Connection], None] | None = None
    post_dbt_init: Callable[[Connection], None] | None = None
