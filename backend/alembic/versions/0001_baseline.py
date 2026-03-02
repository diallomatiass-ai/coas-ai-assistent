"""Baseline migration — eksisterende tabeller er allerede oprettet via create_all().

Denne migration markerer baseline og håndterer fremtidige schema-ændringer sikkert.

Revision ID: 0001
Revises:
Create Date: 2026-03-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline: alle tabeller eksisterer allerede fra SQLAlchemy create_all().
    Fremtidige migrationer tilføjes som 0002, 0003 osv.
    """
    pass


def downgrade() -> None:
    pass
