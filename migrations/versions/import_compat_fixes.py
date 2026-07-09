"""Import compatibility fixes

Revision ID: import_compat
Revises: 608efee842be
Create Date: 2026-07-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'import_compat'
down_revision = '608efee842be'
branch_labels = None
depends_on = None


def upgrade():
    """
    Apply schema compatibility fixes for legacy SQL backup imports.
    
    This migration converts the raw SQL commands from _apply_import_compat_fixes()
    to Alembic operations. All operations are idempotent.
    """
    inspector = sa.inspect(op.get_bind())
    
    # 1. Create app_settings table if missing
    if 'app_settings' not in inspector.get_table_names():
        op.create_table('app_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('base_url', sa.String(length=255), nullable=True),
            sa.Column('unit_preference', sa.String(length=10), server_default=sa.text("'imperial'"), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
    else:
        # Ensure unit_preference column exists
        app_settings_columns = {col['name'] for col in inspector.get_columns('app_settings')}
        if 'unit_preference' not in app_settings_columns:
            op.add_column('app_settings', sa.Column('unit_preference', sa.String(length=10), server_default=sa.text("'imperial'"), nullable=True))
    
    # 2. Add columns to user table if missing
    if 'user' in inspector.get_table_names():
        user_columns = {col['name']: col for col in inspector.get_columns('user')}
        user_column_names = set(user_columns.keys())
        
        if 'email' not in user_column_names:
            op.add_column('user', sa.Column('email', sa.String(length=255), nullable=True))
        if 'display_name' not in user_column_names:
            op.add_column('user', sa.Column('display_name', sa.String(length=255), nullable=True))
        if 'oidc_subject' not in user_column_names:
            op.add_column('user', sa.Column('oidc_subject', sa.String(length=255), nullable=True))
        if 'auth_source' not in user_column_names:
            op.add_column('user', sa.Column('auth_source', sa.String(length=20), server_default=sa.text("'local'"), nullable=True))
        if 'role' not in user_column_names:
            op.add_column('user', sa.Column('role', sa.String(length=50), server_default=sa.text("'user'"), nullable=True))
        if 'last_login_at' not in user_column_names:
            op.add_column('user', sa.Column('last_login_at', sa.DateTime(), nullable=True))
        
        # Modify password_hash to allow NULL
        password_hash_col = user_columns.get('password_hash')
        if password_hash_col and not password_hash_col.get('nullable', True):
            op.alter_column('user', 'password_hash', existing_type=sa.String(length=512), nullable=True)
        
        # Update existing rows for default values
        op.execute("UPDATE \"user\" SET auth_source = 'local' WHERE auth_source IS NULL")
        op.execute("UPDATE \"user\" SET role = 'user' WHERE role IS NULL OR role = 'viewer'")
        
        # Set NOT NULL and DEFAULT constraints
        op.execute("ALTER TABLE \"user\" ALTER COLUMN auth_source SET NOT NULL")
        op.execute("ALTER TABLE \"user\" ALTER COLUMN role SET DEFAULT 'user'")
        op.execute("ALTER TABLE \"user\" ALTER COLUMN role SET NOT NULL")
        
        # Create unique indexes
        op.execute('CREATE UNIQUE INDEX IF NOT EXISTS user_email_key ON "user" (email)')
        op.execute('CREATE UNIQUE INDEX IF NOT EXISTS user_oidc_subject_key ON "user" (oidc_subject)')
    
    # 3. Add yeast_id foreign key to recipe table
    if 'recipe' in inspector.get_table_names():
        recipe_columns = {col['name'] for col in inspector.get_columns('recipe')}
        if 'yeast_id' not in recipe_columns:
            op.add_column('recipe', sa.Column('yeast_id', sa.Integer(), nullable=True))
        
        # Check if foreign key constraint exists
        recipe_fks = inspector.get_foreign_keys('recipe')
        has_yeast_fk = any(fk.get('referred_table') == 'yeast' for fk in recipe_fks)
        if not has_yeast_fk:
            op.create_foreign_key('recipe_yeast_id_fkey', 'recipe', 'yeast', ['yeast_id'], ['id'])
    
    # 4. Add columns to batch table
    if 'batch' in inspector.get_table_names():
        batch_columns = {col['name']: col for col in inspector.get_columns('batch')}
        
        batch_additions = [
            ('batch_size', sa.Float(), True),
            ('fermentation_temp', sa.String(length=50), True),
            ('initial_gravity', sa.Float(), True),
            ('final_gravity', sa.Float(), True),
            ('abv', sa.Float(), True),
            ('yeast_type', sa.String(length=100), True),
            ('backsweetened', sa.Boolean(), True),
            ('flavor_additions', sa.Text(), True),
            ('pectic_used', sa.Boolean(), True),
            ('notes', sa.Text(), True),
            ('water_type', sa.String(length=50), True),
            ('alcohol_type', sa.String(length=20), True),
            ('tosna_total', sa.Float(), True),
            ('tosna_per_day', sa.Float(), True),
            ('tosna_enabled', sa.Boolean(), True),
            ('yeast_id', sa.Integer(), True),
        ]
        
        for col_name, col_type, nullable in batch_additions:
            if col_name not in batch_columns:
                op.add_column('batch', sa.Column(col_name, col_type, nullable=nullable))
        
        # Check if foreign key constraint exists for batch.yeast_id
        batch_fks = inspector.get_foreign_keys('batch')
        has_batch_yeast_fk = any(
            fk.get('referred_table') == 'yeast' and 'yeast_id' in fk.get('constrained_columns', [])
            for fk in batch_fks
        )
        if not has_batch_yeast_fk:
            op.create_foreign_key('batch_yeast_id_fkey', 'batch', 'yeast', ['yeast_id'], ['id'])
    
    # 5. Add columns to ingredient table
    if 'ingredient' in inspector.get_table_names():
        ingredient_columns = {col['name']: col for col in inspector.get_columns('ingredient')}
        
        ingredient_additions = [
            ('amount_per_gallon', sa.Float(), False),
            ('unit', sa.String(length=20), False),
            ('note', sa.String(length=200), True),
        ]
        
        for col_name, col_type, nullable in ingredient_additions:
            if col_name not in ingredient_columns:
                op.add_column('ingredient', sa.Column(col_name, col_type, nullable=nullable))
    
    # 6. Add columns to measurement table
    if 'measurement' in inspector.get_table_names():
        measurement_columns = {col['name']: col for col in inspector.get_columns('measurement')}
        
        if 'ph' not in measurement_columns:
            op.add_column('measurement', sa.Column('ph', sa.Float(), nullable=True))
        if 'temperature' not in measurement_columns:
            op.add_column('measurement', sa.Column('temperature', sa.Float(), nullable=True))


def downgrade():
    """
    Reverse the import compatibility fixes.
    
    Note: This removes columns and constraints added by the upgrade.
    Data in these columns will be lost.
    """
    inspector = sa.inspect(op.get_bind())
    
    # 1. Remove columns from measurement table
    if 'measurement' in inspector.get_table_names():
        measurement_columns = {col['name'] for col in inspector.get_columns('measurement')}
        if 'temperature' in measurement_columns:
            op.drop_column('measurement', 'temperature')
        if 'ph' in measurement_columns:
            op.drop_column('measurement', 'ph')
    
    # 2. Remove columns from ingredient table
    if 'ingredient' in inspector.get_table_names():
        ingredient_columns = {col['name'] for col in inspector.get_columns('ingredient')}
        if 'note' in ingredient_columns:
            op.drop_column('ingredient', 'note')
        if 'unit' in ingredient_columns:
            op.drop_column('ingredient', 'unit')
        if 'amount_per_gallon' in ingredient_columns:
            op.drop_column('ingredient', 'amount_per_gallon')
    
    # 3. Remove foreign key and columns from batch table
    if 'batch' in inspector.get_table_names():
        batch_columns = {col['name'] for col in inspector.get_columns('batch')}
        
        # Drop foreign key first
        batch_fks = inspector.get_foreign_keys('batch')
        has_batch_yeast_fk = any(
            fk.get('constrained_columns') == ['yeast_id'] and fk.get('referred_table') == 'yeast'
            for fk in batch_fks
        )
        if has_batch_yeast_fk:
            op.drop_constraint('batch_yeast_id_fkey', 'batch', type_='foreignkey')
        
        # Drop columns in reverse order
        for col_name in ['yeast_id', 'tosna_enabled', 'tosna_per_day', 'tosna_total', 
                         'alcohol_type', 'water_type', 'notes', 'pectic_used', 
                         'flavor_additions', 'backsweetened', 'yeast_type', 'abv',
                         'final_gravity', 'initial_gravity', 'fermentation_temp', 'batch_size']:
            if col_name in batch_columns:
                op.drop_column('batch', col_name)
    
    # 4. Remove foreign key and column from recipe table
    if 'recipe' in inspector.get_table_names():
        recipe_columns = {col['name'] for col in inspector.get_columns('recipe')}
        
        recipe_fks = inspector.get_foreign_keys('recipe')
        has_yeast_fk = any(fk.get('referred_table') == 'yeast' for fk in recipe_fks)
        if has_yeast_fk:
            op.drop_constraint('recipe_yeast_id_fkey', 'recipe', type_='foreignkey')
        
        if 'yeast_id' in recipe_columns:
            op.drop_column('recipe', 'yeast_id')
    
    # 5. Remove columns and indexes from user table
    if 'user' in inspector.get_table_names():
        user_columns_dict = {col['name']: col for col in inspector.get_columns('user')}
        user_columns = set(user_columns_dict.keys())
        
        # Drop indexes
        op.execute('DROP INDEX IF EXISTS user_oidc_subject_key')
        op.execute('DROP INDEX IF EXISTS user_email_key')
        
        # Drop columns in reverse order
        for col_name in ['last_login_at', 'role', 'auth_source', 'oidc_subject', 
                         'display_name', 'email']:
            if col_name in user_columns:
                op.drop_column('user', col_name)
        
        # Restore password_hash NOT NULL constraint
        password_hash_col = user_columns_dict.get('password_hash')
        if password_hash_col and password_hash_col.get('nullable', True):
            op.alter_column('user', 'password_hash', existing_type=sa.String(length=512), nullable=False)
    
    # 6. Remove unit_preference from app_settings (but keep table)
    if 'app_settings' in inspector.get_table_names():
        app_settings_columns = {col['name'] for col in inspector.get_columns('app_settings')}
        if 'unit_preference' in app_settings_columns:
            op.drop_column('app_settings', 'unit_preference')
