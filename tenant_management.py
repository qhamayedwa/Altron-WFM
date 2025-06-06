"""
Tenant Management Module
Handles multi-tenant organization management and data isolation
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from flask_login import login_required, current_user
from app import db
from models import Tenant, TenantSettings, User, Role
from forms import TenantForm, TenantSettingsForm
from datetime import datetime

tenant_bp = Blueprint('tenant', __name__, url_prefix='/tenant')

@tenant_bp.before_request
def load_tenant():
    """Load current tenant context for all requests"""
    if current_user.is_authenticated and current_user.tenant_id:
        g.current_tenant = Tenant.query.get(current_user.tenant_id)
    else:
        g.current_tenant = None

@tenant_bp.route('/dashboard')
@login_required
def tenant_dashboard():
    """Tenant dashboard showing organization overview"""
    if not g.current_tenant:
        flash('No tenant assigned to your account.', 'warning')
        return redirect(url_for('main.index'))
    
    # Get tenant statistics
    total_users = User.query.filter_by(tenant_id=g.current_tenant.id).count()
    active_users = User.query.filter_by(tenant_id=g.current_tenant.id, is_active=True).count()
    
    # Get tenant settings
    settings = TenantSettings.query.filter_by(tenant_id=g.current_tenant.id).first()
    if not settings:
        # Create default settings if none exist
        settings = TenantSettings(tenant_id=g.current_tenant.id)
        db.session.add(settings)
        db.session.commit()
    
    return render_template('tenant/dashboard.html', 
                         tenant=g.current_tenant,
                         settings=settings,
                         total_users=total_users,
                         active_users=active_users)

@tenant_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def tenant_settings():
    """Manage tenant settings and configuration"""
    if not g.current_tenant:
        flash('No tenant assigned to your account.', 'warning')
        return redirect(url_for('main.index'))
    
    settings = TenantSettings.query.filter_by(tenant_id=g.current_tenant.id).first()
    if not settings:
        settings = TenantSettings(tenant_id=g.current_tenant.id)
        db.session.add(settings)
        db.session.commit()
    
    form = TenantSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        form.populate_obj(settings)
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Tenant settings updated successfully!', 'success')
        return redirect(url_for('tenant.tenant_settings'))
    
    return render_template('tenant/settings.html', form=form, tenant=g.current_tenant)

@tenant_bp.route('/users')
@login_required
def tenant_users():
    """List all users in current tenant"""
    if not g.current_tenant:
        flash('No tenant assigned to your account.', 'warning')
        return redirect(url_for('main.index'))
    
    users = User.query.filter_by(tenant_id=g.current_tenant.id).all()
    return render_template('tenant/users.html', users=users, tenant=g.current_tenant)

@tenant_bp.route('/admin/tenants')
@login_required
def admin_tenant_list():
    """System admin view of all tenants (super admin only)"""
    # Check if user is super admin
    if not current_user.has_role('super_admin'):
        flash('Access denied. Super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenants = Tenant.query.all()
    return render_template('tenant/admin_list.html', tenants=tenants)

@tenant_bp.route('/admin/create', methods=['GET', 'POST'])
@login_required
def admin_create_tenant():
    """Create new tenant (super admin only)"""
    if not current_user.has_role('super_admin'):
        flash('Access denied. Super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    form = TenantForm()
    
    if form.validate_on_submit():
        tenant = Tenant()
        form.populate_obj(tenant)
        tenant.created_at = datetime.utcnow()
        tenant.updated_at = datetime.utcnow()
        
        db.session.add(tenant)
        db.session.flush()  # Get the tenant ID
        
        # Create default settings for new tenant
        settings = TenantSettings(tenant_id=tenant.id)
        db.session.add(settings)
        
        db.session.commit()
        flash(f'Tenant "{tenant.name}" created successfully!', 'success')
        return redirect(url_for('tenant.admin_tenant_list'))
    
    return render_template('tenant/admin_create.html', form=form)

@tenant_bp.route('/admin/edit/<int:tenant_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_tenant(tenant_id):
    """Edit tenant details (super admin only)"""
    if not current_user.has_role('super_admin'):
        flash('Access denied. Super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenant = Tenant.query.get_or_404(tenant_id)
    form = TenantForm(obj=tenant)
    
    if form.validate_on_submit():
        form.populate_obj(tenant)
        tenant.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Tenant "{tenant.name}" updated successfully!', 'success')
        return redirect(url_for('tenant.admin_tenant_list'))
    
    return render_template('tenant/admin_edit.html', form=form, tenant=tenant)

def get_current_tenant():
    """Helper function to get current tenant"""
    if hasattr(g, 'current_tenant'):
        return g.current_tenant
    return None

def require_tenant(f):
    """Decorator to ensure user has a tenant assigned"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.tenant_id:
            flash('No tenant assigned to your account. Please contact your administrator.', 'warning')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function