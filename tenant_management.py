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

@tenant_bp.route('/admin/organizations')
@login_required
def admin_organization_list():
    """System super admin view of all organizations"""
    # Check if user is system super admin
    if not current_user.is_system_super_admin():
        flash('Access denied. System super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenants = Tenant.query.all()
    return render_template('tenant/admin_organization_list.html', tenants=tenants)

@tenant_bp.route('/admin/create-organization', methods=['GET', 'POST'])
@login_required
def admin_create_organization():
    """Create new organization with tenant admin (system super admin only)"""
    if not current_user.is_system_super_admin():
        flash('Access denied. System super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    form = TenantForm()
    
    if form.validate_on_submit():
        # Create the organization
        tenant = Tenant(
            name=form.name.data,
            subdomain=form.subdomain.data,
            domain=form.domain.data,
            admin_email=form.admin_email.data,
            phone=form.phone.data,
            address=form.address.data,
            subscription_plan=form.subscription_plan.data,
            max_users=form.max_users.data,
            is_active=form.is_active.data,
            timezone=form.timezone.data,
            currency=form.currency.data,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(tenant)
        db.session.flush()  # Get the tenant ID
        
        # Create default settings for new tenant
        settings = TenantSettings(
            tenant_id=tenant.id,
            primary_color='#27C1E3',
            secondary_color='#ffffff',
            enable_geolocation=True,
            enable_overtime_alerts=True,
            enable_leave_workflow=True,
            enable_payroll_integration=False,
            enable_ai_scheduling=False,
            default_pay_frequency='monthly',
            overtime_threshold=8,
            weekend_overtime_rate=1.5,
            holiday_overtime_rate=2.0,
            default_annual_leave_days=21,
            default_sick_leave_days=10,
            leave_approval_required=True,
            email_notifications=True,
            sms_notifications=False
        )
        db.session.add(settings)
        
        db.session.commit()
        flash(f'Organization "{tenant.name}" created successfully!', 'success')
        return redirect(url_for('tenant.admin_organization_list'))
    
    return render_template('tenant/admin_create_organization.html', form=form)

@tenant_bp.route('/admin/edit/<int:tenant_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_tenant(tenant_id):
    """Edit organization details (system super admin only)"""
    if not current_user.is_system_super_admin():
        flash('Access denied. System super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenant = Tenant.query.get_or_404(tenant_id)
    form = TenantForm(obj=tenant, original_subdomain=tenant.subdomain)
    
    if form.validate_on_submit():
        tenant.name = form.name.data
        tenant.subdomain = form.subdomain.data
        tenant.domain = form.domain.data
        tenant.admin_email = form.admin_email.data
        tenant.phone = form.phone.data
        tenant.address = form.address.data
        tenant.subscription_plan = form.subscription_plan.data
        tenant.max_users = form.max_users.data
        tenant.is_active = form.is_active.data
        tenant.timezone = form.timezone.data
        tenant.currency = form.currency.data
        tenant.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Organization "{tenant.name}" updated successfully!', 'success')
        return redirect(url_for('tenant.admin_organization_list'))
    
    return render_template('tenant/admin_edit_organization.html', form=form, tenant=tenant)

@tenant_bp.route('/admin/create-tenant-admin/<int:tenant_id>', methods=['GET', 'POST'])
@login_required
def create_tenant_admin(tenant_id):
    """Create a tenant admin for an organization (system super admin only)"""
    if not current_user.is_system_super_admin():
        flash('Access denied. System super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenant = Tenant.query.get_or_404(tenant_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        employee_id = request.form.get('employee_id')
        
        # Validation
        if not all([username, email, first_name, last_name, password, employee_id]):
            flash('All fields are required.', 'danger')
            return render_template('tenant/create_tenant_admin.html', tenant=tenant)
        
        # Check for duplicates within tenant
        if User.query.filter_by(tenant_id=tenant_id, username=username).first():
            flash('Username already exists in this organization.', 'danger')
            return render_template('tenant/create_tenant_admin.html', tenant=tenant)
        
        if User.query.filter_by(tenant_id=tenant_id, email=email).first():
            flash('Email already exists in this organization.', 'danger')
            return render_template('tenant/create_tenant_admin.html', tenant=tenant)
        
        if User.query.filter_by(tenant_id=tenant_id, employee_id=employee_id).first():
            flash('Employee ID already exists in this organization.', 'danger')
            return render_template('tenant/create_tenant_admin.html', tenant=tenant)
        
        # Get tenant admin role
        tenant_admin_role = Role.query.filter_by(name='tenant_admin').first()
        if not tenant_admin_role:
            flash('Tenant admin role not found. Please contact system administrator.', 'danger')
            return render_template('tenant/create_tenant_admin.html', tenant=tenant)
        
        # Create tenant admin user
        tenant_admin = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            tenant_id=tenant_id,
            is_active=True,
            created_at=datetime.utcnow()
        )
        tenant_admin.set_password(password)
        tenant_admin.add_role(tenant_admin_role)
        
        db.session.add(tenant_admin)
        db.session.commit()
        
        flash(f'Tenant admin "{username}" created successfully for {tenant.name}!', 'success')
        return redirect(url_for('tenant.admin_organization_list'))
    
    return render_template('tenant/create_tenant_admin.html', tenant=tenant)

@tenant_bp.route('/admin/view/<int:tenant_id>')
@login_required
def view_tenant_details(tenant_id):
    """View detailed organization information (system super admin only)"""
    if not current_user.is_system_super_admin():
        flash('Access denied. System super admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    tenant = Tenant.query.get_or_404(tenant_id)
    settings = TenantSettings.query.filter_by(tenant_id=tenant_id).first()
    users = User.query.filter_by(tenant_id=tenant_id).all()
    tenant_admins = [user for user in users if user.has_role('tenant_admin')]
    
    return render_template('tenant/view_organization.html', 
                         tenant=tenant, 
                         settings=settings, 
                         users=users,
                         tenant_admins=tenant_admins)

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