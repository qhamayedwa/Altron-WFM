from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectMultipleField, TextAreaField, BooleanField, IntegerField, FloatField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from wtforms.widgets import CheckboxInput, ListWidget
from models import User, Role

class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """User registration form"""
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64, message='Username must be between 3 and 64 characters')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    
    # Employee-specific fields
    employee_id = StringField('Employee ID', validators=[DataRequired(), Length(min=1, max=20, message='Employee ID is required and must be between 1 and 20 characters')])
    department = StringField('Department', validators=[Length(max=64)])
    position = StringField('Position/Job Title', validators=[Length(max=64)])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    roles = MultiCheckboxField('Roles', coerce=int)
    is_active = BooleanField('Active User', default=True)
    submit = SubmitField('Register')
    
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        # Populate roles choices
        self.roles.choices = [(role.id, role.name) for role in Role.query.all()]
    
    def validate_username(self, username):
        """Validate username is unique"""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')
    
    def validate_email(self, email):
        """Validate email is unique"""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')
    
    def validate_employee_id(self, employee_id):
        """Validate employee ID is unique"""
        user = User.query.filter_by(employee_id=employee_id.data).first()
        if user is not None:
            raise ValidationError('This Employee ID is already in use. Please use a different Employee ID.')

class EditUserForm(FlaskForm):
    """Form for editing user information"""
    username = StringField('Username', validators=[
        DataRequired(), 
        Length(min=3, max=64)
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[Length(max=64)])
    last_name = StringField('Last Name', validators=[Length(max=64)])
    employee_id = StringField('Employee ID', validators=[Length(max=20)])
    department = StringField('Department', validators=[Length(max=64)])
    position = StringField('Position/Job Title', validators=[Length(max=64)])
    roles = MultiCheckboxField('Roles', coerce=int)
    is_active = BooleanField('Active User')
    submit = SubmitField('Update User')
    
    def __init__(self, original_username, original_email, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email
        # Populate roles choices
        self.roles.choices = [(role.id, role.name) for role in Role.query.all()]
    
    def validate_username(self, username):
        """Validate username is unique (except for current user)"""
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')
    
    def validate_email(self, email):
        """Validate email is unique (except for current user)"""
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError('Please use a different email address.')

class ChangePasswordForm(FlaskForm):
    """Form for changing user password"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password2 = PasswordField('Repeat New Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

class RoleForm(FlaskForm):
    """Form for creating/editing roles"""
    name = StringField('Role Name', validators=[
        DataRequired(), 
        Length(min=2, max=64)
    ])
    description = TextAreaField('Description', validators=[Length(max=255)])
    submit = SubmitField('Save Role')
    
    def __init__(self, original_name=None, *args, **kwargs):
        super(RoleForm, self).__init__(*args, **kwargs)
        self.original_name = original_name
    
    def validate_name(self, name):
        """Validate role name is unique"""
        if self.original_name is None or name.data != self.original_name:
            role = Role.query.filter_by(name=name.data).first()
            if role is not None:
                raise ValidationError('Please use a different role name.')

class TenantForm(FlaskForm):
    """Form for creating/editing tenants"""
    name = StringField('Organization Name', validators=[
        DataRequired(), 
        Length(min=2, max=100)
    ])
    subdomain = StringField('Subdomain', validators=[
        DataRequired(), 
        Length(min=2, max=50)
    ])
    domain = StringField('Custom Domain (optional)', validators=[Length(max=100)])
    admin_email = StringField('Admin Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[Length(max=20)])
    address = TextAreaField('Address')
    
    # Subscription settings
    subscription_plan = SelectField('Subscription Plan', 
                                  choices=[('basic', 'Basic'), ('premium', 'Premium'), ('enterprise', 'Enterprise')],
                                  default='basic')
    max_users = IntegerField('Maximum Users', validators=[DataRequired(), NumberRange(min=1, max=1000)], default=10)
    is_active = BooleanField('Active Tenant', default=True)
    
    # Localization settings
    timezone = SelectField('Timezone', 
                          choices=[('Africa/Johannesburg', 'South Africa (GMT+2)'), 
                                 ('UTC', 'UTC'), ('US/Eastern', 'US Eastern')],
                          default='Africa/Johannesburg')
    currency = SelectField('Currency', 
                          choices=[('ZAR', 'South African Rand'), ('USD', 'US Dollar'), ('EUR', 'Euro')],
                          default='ZAR')
    
    submit = SubmitField('Save Tenant')
    
    def __init__(self, original_subdomain=None, *args, **kwargs):
        super(TenantForm, self).__init__(*args, **kwargs)
        self.original_subdomain = original_subdomain
    
    def validate_subdomain(self, subdomain):
        """Validate subdomain is unique"""
        from models import Tenant
        if self.original_subdomain is None or subdomain.data != self.original_subdomain:
            tenant = Tenant.query.filter_by(subdomain=subdomain.data).first()
            if tenant is not None:
                raise ValidationError('Please use a different subdomain.')

class TenantSettingsForm(FlaskForm):
    """Form for tenant settings and configuration"""
    
    # Branding
    company_logo_url = StringField('Company Logo URL', validators=[Length(max=255)])
    primary_color = StringField('Primary Color (Hex)', validators=[Length(max=7)], default='#27C1E3')
    secondary_color = StringField('Secondary Color (Hex)', validators=[Length(max=7)], default='#ffffff')
    
    # Feature toggles
    enable_geolocation = BooleanField('Enable Geolocation Tracking', default=True)
    enable_overtime_alerts = BooleanField('Enable Overtime Alerts', default=True)
    enable_leave_workflow = BooleanField('Enable Leave Workflow', default=True)
    enable_payroll_integration = BooleanField('Enable Payroll Integration', default=False)
    enable_ai_scheduling = BooleanField('Enable AI Scheduling', default=False)
    
    # Payroll settings
    default_pay_frequency = SelectField('Default Pay Frequency',
                                      choices=[('weekly', 'Weekly'), ('bi-weekly', 'Bi-weekly'), ('monthly', 'Monthly')],
                                      default='monthly')
    overtime_threshold = IntegerField('Overtime Threshold (hours/day)', 
                                    validators=[NumberRange(min=1, max=24)], default=8)
    weekend_overtime_rate = FloatField('Weekend Overtime Rate', 
                                     validators=[NumberRange(min=1.0, max=5.0)], default=1.5)
    holiday_overtime_rate = FloatField('Holiday Overtime Rate', 
                                     validators=[NumberRange(min=1.0, max=5.0)], default=2.0)
    
    # Leave settings
    default_annual_leave_days = IntegerField('Default Annual Leave Days', 
                                           validators=[NumberRange(min=0, max=365)], default=21)
    default_sick_leave_days = IntegerField('Default Sick Leave Days', 
                                         validators=[NumberRange(min=0, max=365)], default=10)
    leave_approval_required = BooleanField('Leave Approval Required', default=True)
    
    # Notifications
    email_notifications = BooleanField('Email Notifications', default=True)
    sms_notifications = BooleanField('SMS Notifications', default=False)
    
    submit = SubmitField('Save Settings')