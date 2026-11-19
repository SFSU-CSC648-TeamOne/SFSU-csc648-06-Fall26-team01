"""merge bodyweight and program phase migrations

Revision ID: 590867838351
Revises: 03, 5ccfa689be01
Create Date: 2026-11-18 07:45:07.784567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '590867838351'
down_revision: Union[str, Sequence[str], None] = ('03', '5ccfa689be01')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
