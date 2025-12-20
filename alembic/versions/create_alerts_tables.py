"""create alerts tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-12-20 04:31:09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create alerts and alert_triggers tables."""

    # Create alert_type enum
    alert_type_enum = postgresql.ENUM(
        'cost_threshold',
        'budget_limit',
        'anomaly',
        name='alert_type_enum',
        create_type=True
    )
    alert_type_enum.create(op.get_bind(), checkfirst=True)

    # Create alert_period enum
    alert_period_enum = postgresql.ENUM(
        'daily',
        'weekly',
        'monthly',
        name='alert_period_enum',
        create_type=True
    )
    alert_period_enum.create(op.get_bind(), checkfirst=True)

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('alert_type', alert_type_enum, nullable=False),
        sa.Column(
            'threshold_amount',
            sa.Numeric(10, 2),
            nullable=False,
            comment='Amount in USD that triggers the alert'
        ),
        sa.Column('period', alert_period_enum, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_email', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_slack', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column(
            'slack_webhook_url',
            sa.String(512),
            nullable=True,
            comment='Slack webhook URL for notifications'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            'last_triggered_at',
            sa.DateTime(),
            nullable=True,
            comment='Last time this alert was triggered'
        ),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create index on org_id for faster queries
    op.create_index('ix_alerts_org_id', 'alerts', ['org_id'])

    # Create alert_triggers table
    op.create_table(
        'alert_triggers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'triggered_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment='When the alert was triggered'
        ),
        sa.Column(
            'actual_amount',
            sa.Numeric(10, 2),
            nullable=False,
            comment='Actual cost amount that triggered the alert (USD)'
        ),
        sa.Column(
            'threshold_amount',
            sa.Numeric(10, 2),
            nullable=False,
            comment='Threshold amount at time of trigger (USD)'
        ),
        sa.Column(
            'notified',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Whether notifications were sent successfully'
        ),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
    )

    # Create indexes for faster queries
    op.create_index('ix_alert_triggers_alert_id', 'alert_triggers', ['alert_id'])
    op.create_index('ix_alert_triggers_triggered_at', 'alert_triggers', ['triggered_at'])


def downgrade() -> None:
    """Drop alerts and alert_triggers tables."""

    # Drop tables
    op.drop_index('ix_alert_triggers_triggered_at', table_name='alert_triggers')
    op.drop_index('ix_alert_triggers_alert_id', table_name='alert_triggers')
    op.drop_table('alert_triggers')

    op.drop_index('ix_alerts_org_id', table_name='alerts')
    op.drop_table('alerts')

    # Drop enums
    alert_period_enum = postgresql.ENUM(
        'daily',
        'weekly',
        'monthly',
        name='alert_period_enum'
    )
    alert_period_enum.drop(op.get_bind(), checkfirst=True)

    alert_type_enum = postgresql.ENUM(
        'cost_threshold',
        'budget_limit',
        'anomaly',
        name='alert_type_enum'
    )
    alert_type_enum.drop(op.get_bind(), checkfirst=True)
