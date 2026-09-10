"""Add entity_provenance and notes tables for Items 8 and 14

Revision ID: 002_notes_provenance
Revises: 001_initial
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_notes_provenance"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Entity provenance table (links entities to the observations that discovered them)
    op.create_table(
        "entity_provenance",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column(
            "observation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_entity_provenance_entity", "entity_provenance", ["entity_id"])
    op.create_index("idx_entity_provenance_observation", "entity_provenance", ["observation_id"])
    op.create_index(
        "idx_entity_provenance_investigation", "entity_provenance", ["investigation_id"]
    )

    # Add unique constraint to prevent duplicate provenance records
    op.create_unique_constraint(
        "uq_entity_provenance", "entity_provenance", ["entity_id", "observation_id"]
    )

    # Notes table for analyst annotations
    op.create_table(
        "notes",
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
        sa.Column("entity_id", sa.Text()),  # NULL = investigation-level note
        sa.Column("content", sa.Text(), nullable=False),
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
    op.create_index("idx_notes_investigation", "notes", ["investigation_id"])
    op.create_index("idx_notes_entity", "notes", ["entity_id"])

    # Add confidence_overrides table for Item 20
    op.create_table(
        "confidence_overrides",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column(
            "investigation_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_confidence", sa.Float(), nullable=False),
        sa.Column("override_confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_confidence_overrides_entity", "confidence_overrides", ["entity_id"])
    op.create_index(
        "idx_confidence_overrides_investigation", "confidence_overrides", ["investigation_id"]
    )


def downgrade() -> None:
    op.drop_table("confidence_overrides")
    op.drop_table("notes")
    op.drop_table("entity_provenance")
