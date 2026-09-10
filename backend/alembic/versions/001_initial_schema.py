"""Initial schema - baseline matching init.sql

Revision ID: 001_initial
Revises:
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgcrypto extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # Investigations table
    op.create_table(
        "investigations",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="created"),
        sa.Column("depth", sa.Text(), nullable=False, server_default="standard"),
        sa.Column("api_calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_budget", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_investigations_status", "investigations", ["status"])
    op.create_index("idx_investigations_created", "investigations", [sa.text("created_at DESC")])

    # Observations table (immutable evidence records)
    op.create_table(
        "observations",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_adapter", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text()),
        sa.Column("collected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("normalized_value", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_observations_investigation", "observations", ["investigation_id"])
    op.create_index("idx_observations_source", "observations", ["source_adapter"])

    # Entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True)),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "properties", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_entities_investigation", "entities", ["investigation_id"])
    op.create_index("idx_entities_type", "entities", ["type"])
    op.create_index("idx_entities_value", "entities", ["value"])

    # Activity log table
    op.create_table(
        "activity_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_activity_log_investigation", "activity_log", ["investigation_id"])

    # Reports table
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_reports_investigation", "reports", ["investigation_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("activity_log")
    op.drop_table("entities")
    op.drop_table("observations")
    op.drop_table("investigations")
