"""expand structured tab data storage

Revision ID: 0004_expand_tab_data_json
Revises: 0003_add_structured_tab_data
Create Date: 2026-07-12
"""

from alembic import op
from sqlalchemy.dialects import mysql


revision = "0004_expand_tab_data_json"
down_revision = "0003_add_structured_tab_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "generated_tabs",
        "tab_data_json",
        existing_type=mysql.TEXT(),
        type_=mysql.LONGTEXT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "generated_tabs",
        "tab_data_json",
        existing_type=mysql.LONGTEXT(),
        type_=mysql.TEXT(),
        existing_nullable=False,
    )
