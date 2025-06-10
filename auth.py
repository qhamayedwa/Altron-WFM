from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from models import User, Role, Department, Job
from forms import LoginForm, RegistrationForm, EditUserForm, ChangePasswordForm

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

def generate_employee_id():
    """Generate automatic employee ID"""
    # Get the current year
    current_year = datetime.now().year
    year_suffix = str(current_year)[2:]  # Last 2 digits of year
    
    # Find the highest employee ID for this year
    highest_id = db.session.query(User.employee_id).filter(
        User.employee_id.like(f'EMP{year_suffix}%')
    ).order_by(User.employee_id.desc()).first()
    
    if highest_id and highest_id[0]:
        # Extract the numeric part and increment
        try:
            last_num = int(highest_id[0][5:])  # Remove "EMP" and year digits
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    # Format as EMP + year + 3-digit number (e.g., EMP25001)
    return f"EMP{year_suffix}{next_num:03d}"

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=form.remember_me.data)
        
        # Redirect to intended page or home
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        flash(f'Welcome back, {user.full_name}!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

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
    
    # Auto-generate employee ID on form load
    if request.method == 'GET':
        form.employee_id.data = generate_employee_id()
    
    if form.validate_on_submit():
        try:
            # Generate employee ID if not provided
            employee_id = form.employee_id.data or generate_employee_id()
            
            user = User()
            user.username = form.username.data
            user.email = form.email.data
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.employee_id = employee_id
            user.department_id = form.department_id.data if form.department_id.data else None
            user.job_id = form.job_id.data if form.job_id.data else None
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
            
            flash(f'Employee {user.full_name} (ID: {employee_id}) has been registered successfully!', 'success')
            return redirect(url_for('auth.user_management'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Error creating user: {str(e)}', 'danger')
            return render_template('auth/register.html', title='Register Employee', form=form)
    
    return render_template('auth/register.html', title='Register Employee', form=form)

@auth_bp.route('/users')
@super_user_required
def user_management():
    """User management page (Super User only)"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    users = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('auth/user_management.html', 
                         title='User Management', 
                         users=users)

@auth_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@super_user_required
def edit_user(user_id):
    """Edit user route (Super User only)"""
    user = User.query.get_or_404(user_id)
    form = EditUserForm(user.username, user.email)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
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

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password route"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Invalid current password', 'danger')
            return redirect(url_for('auth.change_password'))
        
        current_user.set_password(form.password.data)
        db.session.commit()
        
        flash('Your password has been changed successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html', 
                         title='Change Password', 
                         form=form)

@auth_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@super_user_required
def edit_user(user_id):
    """Edit user route (Super User only)"""
    user = User.query.get_or_404(user_id)
    
    form = EditUserForm(
        original_username=user.username,
        original_email=user.email,
        obj=user
    )
    
    # Populate form fields with existing data
    if request.method == 'GET':
        form.roles.data = [role.id for role in user.roles]
        form.department.data = user.department_id
        form.manager_id.data = user.line_manager_id
    
    if form.validate_on_submit():
        # Update basic information
        user.username = form.username.data
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.is_active = form.is_active.data
        
        # Update contact information
        user.phone_number = form.phone.data
        user.mobile_number = form.mobile.data
        
        # Update address information
        user.address_line1 = form.address_line1.data
        user.address_line2 = form.address_line2.data
        user.city = form.city.data
        user.postal_code = form.postal_code.data
        
        # Update emergency contact
        user.emergency_contact_name = form.emergency_contact_name.data
        user.emergency_contact_phone = form.emergency_contact_phone.data
        user.emergency_contact_relationship = form.emergency_contact_relationship.data
        
        # Update employment information
        user.employee_id = form.employee_id.data
        user.department_id = form.department.data if form.department.data else None
        user.position = form.position.data
        user.employment_type = form.employment_type.data
        user.hire_date = form.hire_date.data
        user.line_manager_id = form.manager_id.data if form.manager_id.data else None
        user.hourly_rate = form.hourly_rate.data
        user.pay_code = request.form.get('pay_code')
        
        # Update professional information
        user.education_level = form.education_level.data
        user.skills = form.skills.data
        user.notes = form.notes.data
        
        # Update roles
        user.roles.clear()
        selected_roles = Role.query.filter(Role.id.in_(form.roles.data)).all()
        for role in selected_roles:
            user.roles.append(role)
        
        db.session.commit()
        
        flash(f'User {user.username} has been updated successfully!', 'success')
        return redirect(url_for('auth.user_management'))
    
    return render_template('auth/edit_user.html', 
                         title='Edit User', 
                         form=form, 
                         user=user)

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