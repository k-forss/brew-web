import os
from datetime import datetime
from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import db, oauth, limiter
from .models import User
from .utils import current_user_is_admin, is_strong_password, local_login_enabled, normalize_role, oidc_enabled
from config import Config

auth_bp = Blueprint('auth_bp', __name__)


def oidc_client_name():
    return current_app.config.get('OIDC_CLIENT_NAME', 'oidc')


def oidc_login_redirect():
    return redirect(url_for('auth_bp.oidc_login'))


def oidc_client():
    client_name = oidc_client_name()
    client = oauth.create_client(client_name)
    if client is None:
        oauth.register(
            name=client_name,
            server_metadata_url=current_app.config['OIDC_DISCOVERY_URL'],
            client_id=current_app.config['OIDC_CLIENT_ID'],
            client_secret=current_app.config['OIDC_CLIENT_SECRET'],
            client_kwargs={'scope': current_app.config['OIDC_SCOPES']},
        )
        client = oauth.create_client(client_name)
    return client


from typing import Any, Dict, List, Union

def claim_values(claims: Dict[str, Any], claim_name: str) -> List[str]:
    """Extract values from OIDC claims, handling multiple types (str, list, tuple, set).
    
    Args:
        claims: Dict of OIDC claims
        claim_name: Name of the claim to extract
        
    Returns:
        List of string values from the claim
    """
    if not claim_name:
        return []

    raw_value = claims.get(claim_name)
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        return [item.strip() for item in raw_value.split(',') if item.strip()]
    if isinstance(raw_value, (list, tuple, set)):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    return [str(raw_value).strip()]


def claim_bool(claims: Dict[str, Any], claim_name: str, default: bool = False) -> bool:
    """Extract boolean value from OIDC claims.
    
    Args:
        claims: Dict of OIDC claims
        claim_name: Name of the claim to extract
        default: Default value if claim is missing
        
    Returns:
        Boolean value from claim, or default if missing
    """
    if not claim_name:
        return default

    raw_value = claims.get(claim_name)
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(raw_value)


def map_role(claims):
    """
    Map OIDC claims to Brew application role and admin status.
    
    Role mapping is based on group membership claims from the OIDC provider.
    The function checks claims in priority order: admin → editor → user.
    
    Args:
        claims: Dict of OIDC claims from userinfo endpoint
        
    Returns:
        Tuple of (role: str, is_admin: bool)
        
    Raises:
        ValueError: If OIDC_ALLOW_UNMAPPED_USERS is False and no role mapping matches
        
    Example:
        claims = {'groups': ['brew-admins', 'brew-users']}
        role, is_admin = map_role(claims)
        # Returns: ('admin', True) if OIDC_ADMIN_GROUPS contains 'brew-admins'
    """
    role_claim = current_app.config.get('OIDC_ROLE_CLAIM') or current_app.config.get('OIDC_GROUPS_CLAIM', 'groups')
    claim_set = set(claim_values(claims, role_claim))
    role_routes = (
        (Config.RBAC_ADMIN_ROLE, set(current_app.config.get('OIDC_ADMIN_GROUPS', []))),
        (Config.RBAC_EDITOR_ROLE, set(current_app.config.get('OIDC_EDITOR_GROUPS', []))),
        (Config.RBAC_USER_ROLE, set(current_app.config.get('OIDC_USER_GROUPS', []))),
    )

    for role, routed_values in role_routes:
        if routed_values and routed_values & claim_set:
            return role, role == Config.RBAC_ADMIN_ROLE

    default_role = normalize_role(current_app.config.get('OIDC_DEFAULT_ROLE', Config.RBAC_USER_ROLE))
    if current_app.config.get('OIDC_ALLOW_UNMAPPED_USERS', True):
        return default_role, default_role == Config.RBAC_ADMIN_ROLE

    raise ValueError('OIDC account is not mapped to an allowed Brew role.')


def unique_username(candidate):
    base = (candidate or 'brew-user').strip() or 'brew-user'
    max_length = getattr(User.username.property.columns[0].type, 'length', None) or 120
    base = base[:max_length]
    username = base
    suffix = 1
    while User.query.filter_by(username=username).first():
        suffix_text = f'-{suffix}'
        trimmed_base = base[:max(0, max_length - len(suffix_text))]
        username = f'{trimmed_base}{suffix_text}'
        # Security: Validate total length after suffix append to prevent overflow
        if len(username) > max_length:
            raise ValueError('Unable to generate unique username within length limit')
        suffix += 1
    return username


def resolve_oidc_user(subject, email, email_verified):
    """
    Resolve or create an OIDC user account.
    
    Security: Prevents account takeover by requiring explicit linking for:
    - Local accounts (auth_source != 'oidc')
    - OIDC accounts with different subject identifiers
    
    CRITICAL: Email verification is checked BEFORE querying by email to prevent
    account takeover via unverified email claims from OIDC provider.
    
    Returns None if no matching user found (new user will be created).
    Raises ValueError if account linking conflict detected.
    """
    if subject:
        user = User.query.filter_by(oidc_subject=subject).first()
        if user is not None:
            return user

    # Security: Only query by email if email is verified to prevent account takeover
    if not email or not email_verified:
        return None

    user = User.query.filter_by(email=email).first()
    if user is None:
        return None

    # Do not automatically link to local accounts - requires explicit migration
    if user.auth_source != 'oidc':
        raise ValueError(
            'A local account already uses this verified email address. '
            'Use an OIDC account with a different email or migrate the existing account first.'
        )

    # Prevent linking to an OIDC account with a different subject
    if user.oidc_subject and subject and user.oidc_subject != subject:
        raise ValueError(
            'This verified email is already linked to a different OIDC identity.'
        )

    return user


def sync_oidc_user(claims):
    username_claim = current_app.config.get('OIDC_USERNAME_CLAIM', 'preferred_username')
    email_claim = current_app.config.get('OIDC_EMAIL_CLAIM', 'email')
    name_claim = current_app.config.get('OIDC_NAME_CLAIM', 'name')
    email_verified_claim = current_app.config.get('OIDC_EMAIL_VERIFIED_CLAIM', 'email_verified')

    subject = claims.get('sub')
    if not subject:
        raise ValueError('OIDC response did not include a subject identifier.')

    email = claims.get(email_claim)
    email_verified = claim_bool(claims, email_verified_claim, default=False)
    preferred_username = claims.get(username_claim) or email or subject
    display_name = claims.get(name_claim) or preferred_username

    role, is_admin = map_role(claims)

    # Security: No First-User-Is-Admin, admin privileges
    # MUST come from explicit OIDC claims. Log warning if admin granted without
    # explicit admin group claim to help detect misconfigurations.
    if is_admin:
        admin_groups = current_app.config.get('OIDC_ADMIN_GROUPS', [])
        claim_set = set(claim_values(claims, current_app.config.get('OIDC_ROLE_CLAIM') or current_app.config.get('OIDC_GROUPS_CLAIM', 'groups')))
        if not admin_groups or not (set(admin_groups) & claim_set):
            if not current_app.config.get('OIDC_ALLOW_ADMIN_WITHOUT_EXPLICIT_CLAIM', False):
                current_app.logger.error(
                    'OIDC_ADMIN_GRANT_WITHOUT_EXPLICIT_CLAIM',
                    extra={
                        'error_type': 'AdminGrantError',
                        'error_message': 'Admin role granted without explicit admin group claim match (blocked by OIDC_ALLOW_ADMIN_WITHOUT_EXPLICIT_CLAIM)',
                        'claim_set': list(claim_set),
                        'expected_admin_groups': admin_groups,
                    }
                )
                return None
            current_app.logger.warning(
                'OIDC_ADMIN_GRANT_WITHOUT_EXPLICIT_CLAIM',
                extra={
                    'error_type': 'AdminGrantWarning',
                    'error_message': 'Admin role granted without explicit admin group claim match',
                    'claim_set': list(claim_set),
                    'expected_admin_groups': admin_groups,
                }
            )

    user = resolve_oidc_user(subject, email, email_verified)

    if user is None:
        user = User(
            username=unique_username(preferred_username),
            auth_source='oidc',
        )

    verified_email = email if email_verified else None

    user.oidc_subject = subject
    if verified_email is not None:
        user.email = verified_email
    user.display_name = display_name
    user.auth_source = 'oidc'
    user.role = role
    user.is_admin = is_admin
    user.last_login_at = datetime.utcnow()
    if not user.username:
        user.username = unique_username(preferred_username)

    db.session.add(user)
    db.session.commit()
    return user

@auth_bp.before_app_request
def require_setup_or_reset():
    # Skip static assets
    if request.endpoint in ('static', 'health'):
        return

    # If no user exists yet, redirect to setup
    if not User.query.first() and not oidc_enabled() and request.endpoint != 'auth_bp.setup':
        return redirect(url_for('auth_bp.setup'))

    # If a force_reset flag is present, require all local users to reset their password.
    # In OIDC mode local_login_enabled() is always False so this block is never entered.
    flag_path = os.path.join(current_app.instance_path, 'force_reset.flag')
    if os.path.exists(flag_path) and local_login_enabled():
        allowed_endpoints = ['auth_bp.reset_password', 'auth_bp.login', 'auth_bp.setup', 'auth_bp.oidc_login', 'auth_bp.oidc_callback', 'static']
        if request.endpoint not in allowed_endpoints:
            return redirect(url_for('auth_bp.reset_password'))

@auth_bp.route('/force-reset', methods=['POST'])
@login_required
def trigger_force_reset():
    if not local_login_enabled():
        flash('Password resets are disabled while OIDC SSO is enabled.', 'warning')
        return redirect(url_for('routes.admin_bp.admin_settings'))

    if not current_user_is_admin():
        flash("You are not authorized to do this.", "danger")
        return redirect(url_for('routes.index'))

    flag_path = os.path.join(current_app.instance_path, 'force_reset.flag')
    os.makedirs(current_app.instance_path, exist_ok=True)
    with open(flag_path, 'w') as f:
        f.write('1')

    # Set restrictive file permissions to prevent exploitation
    os.chmod(flag_path, 0o600)

    flash("Forced password reset activated.", "success")
    return redirect(url_for('routes.index'))

@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if oidc_enabled():
        return oidc_login_redirect()

    if User.query.first():
        return redirect(url_for('auth_bp.login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']  # ✅ new field

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('auth_bp.setup'))

        user = User(
            username=username,
            is_admin=True,
            role=Config.RBAC_ADMIN_ROLE
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Ensure a force reset is NOT pending for fresh setups
        flag_path = os.path.join(current_app.instance_path, 'force_reset.flag')
        if os.path.exists(flag_path):
            os.remove(flag_path)

        login_user(user)
        flash('Admin account created and logged in.', 'success')
        return redirect(url_for('routes.index'))

    return render_template('setup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if oidc_enabled():
        return render_template('login.html')

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('routes.index'))
        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')


@auth_bp.route('/oidc/login')
@limiter.limit("5 per minute")
def oidc_login():
    if not oidc_enabled():
        return redirect(url_for('auth_bp.login'))

    redirect_uri = url_for('auth_bp.oidc_callback', _external=True)
    return oidc_client().authorize_redirect(redirect_uri)


@auth_bp.route('/oidc/callback')
@limiter.limit("5 per minute")
def oidc_callback():
    if not oidc_enabled():
        return redirect(url_for('auth_bp.login'))

    try:
        token = oidc_client().authorize_access_token()
        claims = token.get('userinfo')
        if not claims:
            claims = oidc_client().userinfo()
    except OAuthError as error:
        # Structured logging for OIDC failure monitoring
        current_app.logger.warning(
            'OIDC_AUTH_FAILURE',
            extra={
                'error_type': 'OAuthError',
                'error_message': str(error),
                'error_code': getattr(error, 'error', None),
                'remote_addr': request.remote_addr,
            }
        )
        flash('OIDC sign-in failed. Please try again.', 'danger')
        return redirect(url_for('auth_bp.login'))
    except Exception as error:
        # Structured logging for unexpected OIDC failures
        current_app.logger.error(
            'OIDC_AUTH_FAILURE',
            extra={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'remote_addr': request.remote_addr,
            },
            exc_info=True
        )
        flash('OIDC sign-in failed. Please try again.', 'danger')
        return redirect(url_for('auth_bp.login'))

    try:
        user = sync_oidc_user(claims)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('auth_bp.login'))

    login_user(user)
    flash('Signed in with OIDC SSO.', 'success')
    # Security: Intentionally redirect to index instead of 'next' parameter
    # This prevents open redirect attacks where malicious 'next' URLs could
    # redirect users to phishing sites after successful authentication
    return redirect(url_for('routes.index'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/reset', methods=['GET', 'POST'])
def reset_password():
    """
    Handle forced password reset for local users.
    
    All POST requests to this route automatically validate CSRF tokens via Flask-WTF.
    """
    if not local_login_enabled():
        flash('Password management is handled by your identity provider.', 'info')
        if oidc_enabled():
            return oidc_login_redirect()
        return redirect(url_for('auth_bp.login'))

    if not User.query.first():
        return redirect(url_for('auth_bp.setup'))

    flag_path = os.path.join(current_app.instance_path, 'force_reset.flag')

    if not current_user.is_authenticated:
        flash('Please sign in before resetting your password.', 'warning')
        return redirect(url_for('auth_bp.login'))

    if not os.path.exists(flag_path):
        flash('No forced password reset is currently active.', 'info')
        return redirect(url_for('routes.settings_bp.settings_password'))

    user = current_user

    if request.method == 'POST':
        new = request.form['new_password']
        confirm = request.form['confirm_password']

        if new != confirm:
            flash('Passwords do not match.', 'error')
        elif not is_strong_password(new):
            flash('Password is too weak.', 'error')
        else:
            user.set_password(new)
            db.session.commit()
            # Removing the flag unlocks normal access
            if os.path.exists(flag_path):
                os.remove(flag_path)
            flash('Password changed successfully. Please log in.', 'success')
            return redirect(url_for('auth_bp.login'))

    return render_template('auth/reset_password.html')
