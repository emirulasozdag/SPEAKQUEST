"""The Alembic migrations form one chain. Two PRs that each add a migration on the same parent
create two heads; this test fails then, so the second PR rebases and regenerates its migration."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

API_DIR = Path(__file__).resolve().parents[1]


def test_there_is_exactly_one_migration_head():
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))

    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, f"more than one Alembic head: {heads}. Rebase and regenerate your migration."
