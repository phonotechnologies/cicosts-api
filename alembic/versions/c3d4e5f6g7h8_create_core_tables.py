"""create core tables (workflow_runs, jobs, github_installations)

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2024-12-20 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workflow_runs, jobs, and github_installations tables."""

    # Check if tables already exist (might have been created by Supabase)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # Create workflow_runs table
    if 'workflow_runs' not in existing_tables:
        op.create_table(
            'workflow_runs',
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('github_run_id', sa.BigInteger(), nullable=False),
            sa.Column('repo_name', sa.String(255), nullable=False),
            sa.Column('repo_id', sa.BigInteger(), nullable=True),
            sa.Column('workflow_name', sa.String(255), nullable=False),
            sa.Column('workflow_id', sa.BigInteger(), nullable=True),
            sa.Column('run_number', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('conclusion', sa.String(50), nullable=True),
            sa.Column('event', sa.String(50), nullable=True),
            sa.Column('triggered_by', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('billable_ms', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, server_default='0'),
            sa.Column('created_locally_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('org_id', 'github_run_id'),
        )

        # Create indexes for faster queries
        op.create_index('ix_workflow_runs_org_id', 'workflow_runs', ['org_id'])
        op.create_index('ix_workflow_runs_created_at', 'workflow_runs', ['created_at'])
        op.create_index('ix_workflow_runs_repo_name', 'workflow_runs', ['repo_name'])

    # Create jobs table
    if 'jobs' not in existing_tables:
        op.create_table(
            'jobs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('github_job_id', sa.BigInteger(), nullable=False),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('run_github_id', sa.BigInteger(), nullable=False),
            sa.Column('repo_name', sa.String(255), nullable=False),
            sa.Column('job_name', sa.String(255), nullable=False),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('conclusion', sa.String(50), nullable=True),
            sa.Column('runner_type', sa.String(100), nullable=False, server_default='ubuntu-latest'),
            sa.Column('billable_ms', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('cost_usd', sa.Numeric(10, 4), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(
                ['org_id', 'run_github_id'],
                ['workflow_runs.org_id', 'workflow_runs.github_run_id'],
                ondelete='CASCADE'
            ),
            sa.PrimaryKeyConstraint('id'),
        )

        # Create indexes
        op.create_index('ix_jobs_org_id', 'jobs', ['org_id'])
        op.create_index('ix_jobs_run_github_id', 'jobs', ['run_github_id'])
        op.create_index('ix_jobs_github_job_id', 'jobs', ['github_job_id'])
        op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])

    # Create github_installations table
    if 'github_installations' not in existing_tables:
        op.create_table(
            'github_installations',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('installation_id', sa.BigInteger(), nullable=False, unique=True),
            sa.Column('account_id', sa.BigInteger(), nullable=False),
            sa.Column('account_type', sa.String(50), nullable=False, server_default='Organization'),
            sa.Column('account_login', sa.String(255), nullable=False),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('target_type', sa.String(50), nullable=False, server_default='Organization'),
            sa.Column('repository_selection', sa.String(50), nullable=False, server_default='all'),
            sa.Column('permissions', sa.Text(), nullable=True, comment='JSON string of permissions'),
            sa.Column('events', sa.Text(), nullable=True, comment='JSON string of subscribed events'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('installed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('uninstalled_at', sa.DateTime(), nullable=True),
            sa.Column('suspended_at', sa.DateTime(), nullable=True),
            sa.Column('suspended_by', sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )

        # Create indexes
        op.create_index('ix_github_installations_installation_id', 'github_installations', ['installation_id'])
        op.create_index('ix_github_installations_account_id', 'github_installations', ['account_id'])
        op.create_index('ix_github_installations_org_id', 'github_installations', ['org_id'])


def downgrade() -> None:
    """Drop workflow_runs, jobs, and github_installations tables."""

    # Check which tables exist before dropping
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # Drop jobs first (depends on workflow_runs)
    if 'jobs' in existing_tables:
        op.drop_index('ix_jobs_created_at', table_name='jobs')
        op.drop_index('ix_jobs_github_job_id', table_name='jobs')
        op.drop_index('ix_jobs_run_github_id', table_name='jobs')
        op.drop_index('ix_jobs_org_id', table_name='jobs')
        op.drop_table('jobs')

    # Drop workflow_runs
    if 'workflow_runs' in existing_tables:
        op.drop_index('ix_workflow_runs_repo_name', table_name='workflow_runs')
        op.drop_index('ix_workflow_runs_created_at', table_name='workflow_runs')
        op.drop_index('ix_workflow_runs_org_id', table_name='workflow_runs')
        op.drop_table('workflow_runs')

    # Drop github_installations
    if 'github_installations' in existing_tables:
        op.drop_index('ix_github_installations_org_id', table_name='github_installations')
        op.drop_index('ix_github_installations_account_id', table_name='github_installations')
        op.drop_index('ix_github_installations_installation_id', table_name='github_installations')
        op.drop_table('github_installations')
