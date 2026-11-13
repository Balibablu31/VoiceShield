from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_legacy_sqlite_schema_migrates(tmp_path):
    database = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE analyses (
            id INTEGER PRIMARY KEY, kind VARCHAR(16) NOT NULL, label VARCHAR(80) NOT NULL,
            risk_score FLOAT NOT NULL, language VARCHAR(16), summary TEXT NOT NULL,
            evidence JSON NOT NULL, created_at DATETIME NOT NULL)"""))
        connection.execute(text("INSERT INTO analyses VALUES (1, 'text', 'old', 42, 'en', 'kept', '[]', '2026-01-01')"))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "head")
    columns = {column["name"]: column for column in inspect(engine).get_columns("analyses")}
    assert columns["risk_score"]["nullable"] is True
    assert {"fact_checks", "model_confidence", "processing_metadata", "verdict", "user_id"} <= columns.keys()
    assert {"users", "user_sessions", "password_reset_tokens"} <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        row = connection.execute(text("SELECT summary, fact_checks FROM analyses WHERE id=1")).one()
        assert row.summary == "kept" and row.fact_checks == "[]"
    engine.dispose()
