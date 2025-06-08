from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from models import User, Role, user_roles
from forms import RegistrationForm

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Initialize Flask-Login
login_manager = LoginManager()

def init_login_manager(app):
    """Initialize login manager with the app"""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return User.query.get(int(user_id))

def role_required(*roles):
    """Decorator to require specific roles for access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            if not any(current_user.has_role(role) for role in roles):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def super_user_required(f):
    """Decorator to require Super User role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.has_role('Super User'):
            flash('Super User privileges required.', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=remember_me)
        
        # Redirect to intended page or home
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        flash(f'Welcome back, {user.full_name}!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@super_user_required
def register():
    """User registration route (Super User only)"""
    form = RegistrationForm()
    
    if form.validate_on_submit():
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.employee_id = form.employee_id.data
        user.department = form.department.data if form.department.data else None
        user.position = form.position.data if form.position.data else None
        user.is_active = form.is_active.data
        user.set_password(form.password.data)
        
        # Add selected roles
        if form.roles.data:
            for role_id in form.roles.data:
                role = Role.query.get(role_id)
                if role:
                    user.add_role(role)
        else:
            # Default to User role if no roles selected
            user_role = Role.query.filter_by(name='User').first()
            if user_role:
                user.add_role(user_role)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} has been registered successfully!', 'success')
        return redirect(url_for('auth.user_management'))
    
    return render_template('auth/register.html', title='Register User', form=form)

@auth_bp.route('/users')
@super_user_required
def user_management():
    """User management page (Super User only)"""
    page = request.args.get('page', 1, type=int)
    per_page = 15
    role_filter = request.args.get('role')
    
    # Build query with role filtering
    query = User.query
    
    if role_filter:
        query = query.filter(User.roles.any(Role.name == role_filter))
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all available roles for the filter dropdown
    all_roles = Role.query.order_by(Role.name).all()
    
    return render_template('auth/user_management.html', 
                         title='User Management', 
                         users=users,
                         all_roles=all_roles,
                         current_role_filter=role_filter)

@auth_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@super_user_required
def edit_user(user_id):
    """Edit user route (Super User only)"""
    user = User.query.get_or_404(user_id)
    from forms import EditUserForm
    form = EditUserForm(user.username, user.email)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.employee_id = form.employee_id.data
        user.department = form.department.data
        user.position = form.position.data
        user.is_active = form.is_active.data
        
        # Update roles
        user.roles.clear()
        if form.roles.data:
            for role_id in form.roles.data:
                role = Role.query.get(role_id)
                if role:
                    user.add_role(role)
        
        db.session.commit()
        flash(f'User {user.username} has been updated!', 'success')
        return redirect(url_for('auth.user_management'))
    
    elif request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.employee_id.data = user.employee_id
        form.department.data = user.department
        form.position.data = user.position
        form.is_active.data = user.is_active
        form.roles.data = [role.id for role in user.roles]
    
    return render_template('auth/edit_user.html', 
                         title=f'Edit User - {user.username}', 
                         form=form, user=user)

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html', title='My Profile')

@auth_bp.route('/user/<int:user_id>/delete')
@super_user_required
def delete_user(user_id):
    """Delete user route (Super User only)"""
    user = User.query.get_or_404(user_id)
    
    # Prevent deletion of own account
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('auth.user_management'))
    
    # Prevent deletion of other super users
    if user.has_role('Super User'):
        flash('Cannot delete other Super Users.', 'danger')
        return redirect(url_for('auth.user_management'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} has been deleted.', 'success')
    return redirect(url_for('auth.user_management'))