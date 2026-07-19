"""add structured tab data

Revision ID: 0003_add_structured_tab_data
Revises: 0002_create_generated_tabs
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_structured_tab_data"
down_revision = "0002_create_generated_tabs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_tabs",
        sa.Column("tab_data_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("generated_tabs", "tab_data_json")
