"""Persist model verdict separately from scores and publisher checks."""
from alembic import op
import sqlalchemy as sa

revision = "0002_analysis_verdict"
down_revision = "0001_analysis_contract"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analyses")}
    if "verdict" not in columns:
        op.add_column("analyses", sa.Column("verdict", sa.String(32), nullable=True))


def downgrade():
    op.drop_column("analyses", "verdict")
