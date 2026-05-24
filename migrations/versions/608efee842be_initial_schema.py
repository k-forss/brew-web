"""Initial schema

Revision ID: 608efee842be
Revises: 
Create Date: 2026-05-24 18:29:32.626509

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '608efee842be'
down_revision = None
branch_labels = None
depends_on = None


def table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def column_map(inspector, table_name):
    return {column['name']: column for column in inspector.get_columns(table_name)}


def ensure_user_compatibility(inspector):
    columns = column_map(inspector, 'user')

    if 'email' not in columns:
        op.add_column('user', sa.Column('email', sa.String(length=255), nullable=True))
    if 'display_name' not in columns:
        op.add_column('user', sa.Column('display_name', sa.String(length=255), nullable=True))
    if 'oidc_subject' not in columns:
        op.add_column('user', sa.Column('oidc_subject', sa.String(length=255), nullable=True))
    if 'auth_source' not in columns:
        op.add_column('user', sa.Column('auth_source', sa.String(length=20), server_default=sa.text("'local'"), nullable=True))
    if 'role' not in columns:
        op.add_column('user', sa.Column('role', sa.String(length=50), server_default=sa.text("'user'"), nullable=True))
    if 'last_login_at' not in columns:
        op.add_column('user', sa.Column('last_login_at', sa.DateTime(), nullable=True))

    password_hash = columns.get('password_hash')
    if password_hash is not None and not password_hash.get('nullable', True):
        op.alter_column('user', 'password_hash', existing_type=sa.String(length=512), nullable=True)

    op.execute("UPDATE \"user\" SET auth_source = 'local' WHERE auth_source IS NULL")
    op.execute("UPDATE \"user\" SET role = 'user' WHERE role IS NULL OR role = 'viewer'")
    op.execute('ALTER TABLE "user" ALTER COLUMN auth_source SET NOT NULL')
    op.execute("ALTER TABLE \"user\" ALTER COLUMN role SET DEFAULT 'user'")
    op.execute('ALTER TABLE "user" ALTER COLUMN role SET NOT NULL')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS user_email_key ON "user" (email)')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS user_oidc_subject_key ON "user" (oidc_subject)')


def ensure_app_settings(inspector):
    if not table_exists(inspector, 'app_settings'):
        op.create_table('app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('base_url', sa.String(length=255), nullable=True),
        sa.Column('unit_preference', sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
        return

    columns = column_map(inspector, 'app_settings')
    if 'unit_preference' not in columns:
        op.add_column('app_settings', sa.Column('unit_preference', sa.String(length=10), nullable=True))


def upgrade():
    inspector = sa.inspect(op.get_bind())

    ensure_app_settings(inspector)

    if not table_exists(inspector, 'user'):
        op.create_table('user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('oidc_subject', sa.String(length=255), nullable=True),
        sa.Column('auth_source', sa.String(length=20), server_default=sa.text("'local'"), nullable=False),
        sa.Column('password_hash', sa.String(length=512), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('role', sa.String(length=50), server_default=sa.text("'user'"), nullable=False),
        sa.Column('theme', sa.String(length=20), nullable=True),
        sa.Column('font_size', sa.String(length=10), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('oidc_subject'),
        sa.UniqueConstraint('username')
        )
    else:
        ensure_user_compatibility(inspector)

    if not table_exists(inspector, 'yeast'):
        op.create_table('yeast',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('alcohol_type', sa.String(length=20), nullable=False),
        sa.Column('tolerance', sa.String(length=50), nullable=True),
        sa.Column('strength', sa.String(length=50), nullable=True),
        sa.Column('sweetness_retention', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('flocculation', sa.String(length=50), nullable=True),
        sa.Column('attenuation', sa.String(length=10), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    if not table_exists(inspector, 'recipe'):
        op.create_table('recipe',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('alcohol_type', sa.String(length=20), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('water_type', sa.String(length=50), nullable=True),
        sa.Column('yeast_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['yeast_id'], ['yeast.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if not table_exists(inspector, 'batch'):
        op.create_table('batch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('batch_size', sa.Float(), nullable=True),
        sa.Column('fermentation_temp', sa.String(length=50), nullable=True),
        sa.Column('initial_gravity', sa.Float(), nullable=True),
        sa.Column('final_gravity', sa.Float(), nullable=True),
        sa.Column('abv', sa.Float(), nullable=True),
        sa.Column('yeast_type', sa.String(length=100), nullable=True),
        sa.Column('backsweetened', sa.Boolean(), nullable=True),
        sa.Column('flavor_additions', sa.Text(), nullable=True),
        sa.Column('pectic_used', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('water_type', sa.String(length=50), nullable=True),
        sa.Column('alcohol_type', sa.String(length=20), nullable=True),
        sa.Column('tosna_total', sa.Float(), nullable=True, comment='Total Fermaid O needed in grams'),
        sa.Column('tosna_per_day', sa.Float(), nullable=True, comment='Fermaid O per day over 4 days'),
        sa.Column('tosna_enabled', sa.Boolean(), nullable=True),
        sa.Column('yeast_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
        sa.ForeignKeyConstraint(['yeast_id'], ['yeast.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if not table_exists(inspector, 'ingredient'):
        op.create_table('ingredient',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('amount_per_gallon', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if not table_exists(inspector, 'calendar_event'):
        op.create_table('calendar_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('start', sa.Date(), nullable=False),
        sa.Column('end', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('all_day', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if not table_exists(inspector, 'measurement'):
        op.create_table('measurement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=True),
        sa.Column('gravity', sa.Float(), nullable=True),
        sa.Column('ph', sa.Float(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
        sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('measurement')
    op.drop_table('calendar_event')
    op.drop_table('ingredient')
    op.drop_table('batch')
    op.drop_table('recipe')
    op.drop_table('yeast')
    op.drop_table('user')
    op.drop_table('app_settings')
    # ### end Alembic commands ###
