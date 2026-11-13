"""Add user accounts, persisted login sessions, and per-user analysis history."""
from alembic import op
import sqlalchemy as sa

revision = "0003_accounts_sessions"
down_revision = "0002_analysis_verdict"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("full_name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("password_hash", sa.String(256), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if "user_sessions" not in tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        )
        op.create_index("ix_user_sessions_id", "user_sessions", ["id"])
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
        op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
        op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    columns = {column["name"] for column in sa.inspect(bind).get_columns("analyses")}
    if "user_id" not in columns:
        op.add_column("analyses", sa.Column("user_id", sa.Integer(), nullable=True))
        with op.batch_alter_table("analyses") as batch:
            batch.create_foreign_key("fk_analyses_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")
        op.create_index("ix_analyses_user_id", "analyses", ["user_id"])


def downgrade():
    op.drop_index("ix_analyses_user_id", table_name="analyses")
    with op.batch_alter_table("analyses") as batch:
        batch.drop_constraint("fk_analyses_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
