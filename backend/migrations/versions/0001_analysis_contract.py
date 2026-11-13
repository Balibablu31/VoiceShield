"""Introduce the nullable analysis contract and persist cross-check results."""
from alembic import op
import sqlalchemy as sa

revision = "0001_analysis_contract"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "analyses" not in inspector.get_table_names():
        op.create_table("analyses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("status", sa.String(24), server_default="completed", nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.Column("risk_score", sa.Float(), nullable=True),
            sa.Column("model_confidence", sa.Float(), nullable=True),
            sa.Column("language", sa.String(16), nullable=True),
            sa.Column("model_status", sa.String(32), server_default="not_configured", nullable=False),
            sa.Column("model_name", sa.String(200), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("fact_checks", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("fact_check_status", sa.String(32), server_default="not_configured", nullable=False),
            sa.Column("processing_metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        return
    columns = {column["name"] for column in inspector.get_columns("analyses")}
    additions = [
        ("status", sa.String(24), "'completed'"),
        ("model_confidence", sa.Float(), None),
        ("model_status", sa.String(32), "'not_configured'"),
        ("model_name", sa.String(200), None),
        ("fact_checks", sa.JSON(), "'[]'"),
        ("fact_check_status", sa.String(32), "'not_configured'"),
        ("processing_metadata", sa.JSON(), "'{}'"),
    ]
    for name, type_, default in additions:
        if name not in columns:
            clause = f" DEFAULT {default}" if default else ""
            op.execute(sa.text(f"ALTER TABLE analyses ADD COLUMN {name} {type_.compile(dialect=op.get_bind().dialect)}{clause}"))
    if any(column["name"] == "risk_score" and not column["nullable"] for column in inspector.get_columns("analyses")):
        with op.batch_alter_table("analyses") as batch:
            batch.alter_column("risk_score", existing_type=sa.Float(), nullable=True)


def downgrade():
    # Data-bearing columns are intentionally retained on downgrade.
    pass
