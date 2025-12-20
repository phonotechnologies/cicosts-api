"""add user notification settings

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2024-12-20 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notification settings columns to users table."""

    # Add notification_email column (nullable, defaults to user's email)
    op.add_column(
        'users',
        sa.Column(
            'notification_email',
            sa.String(255),
            nullable=True,
            comment='Email address for notifications (defaults to primary email)'
        )
    )

    # Add weekly_digest_enabled column
    op.add_column(
        'users',
        sa.Column(
            'weekly_digest_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Whether to receive weekly cost digest emails'
        )
    )

    # Add alert_emails_enabled column
    op.add_column(
        'users',
        sa.Column(
            'alert_emails_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='true',
            comment='Whether to receive alert notification emails'
        )
    )


def downgrade() -> None:
    """Remove notification settings columns from users table."""

    op.drop_column('users', 'alert_emails_enabled')
    op.drop_column('users', 'weekly_digest_enabled')
    op.drop_column('users', 'notification_email')
