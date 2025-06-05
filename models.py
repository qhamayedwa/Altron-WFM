from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Association table for many-to-many relationship between users and roles
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

class Role(db.Model):
    """Role model for role-based access control"""
    
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    """User model for authentication and user management"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(64), index=True)  # Add index for name searches
    last_name = db.Column(db.String(64), index=True)   # Add index for name searches
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # Add index for date queries
    last_login = db.Column(db.DateTime, index=True)    # Add index for activity tracking
    is_active = db.Column(db.Boolean, default=True, index=True)  # Add index for active user queries
    
    # Additional fields for employee management
    employee_id = db.Column(db.String(20), unique=True, nullable=False, index=True)  # Employee ID - required key identifier
    department = db.Column(db.String(64), nullable=True, index=True)  # Department with index
    position = db.Column(db.String(64), nullable=True)
    hire_date = db.Column(db.Date, nullable=True, index=True)  # Hire date with index
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    roles = db.relationship('Role', secondary=user_roles, lazy='subquery',
                           backref=db.backref('users', lazy=True))
    
    # Additional indexes for performance optimization
    __table_args__ = (
        db.Index('idx_users_full_name', 'first_name', 'last_name'),  # Composite index for full name searches
        db.Index('idx_users_dept_active', 'department', 'is_active'),  # Composite index for active employees by department
        db.Index('idx_users_hire_date_desc', 'hire_date', postgresql_using='btree'),  # Optimized for date range queries
    )
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        if not self.roles:
            return False
        return any(role.name == role_name for role in self.roles)
    
    def add_role(self, role):
        """Add a role to the user"""
        if not self.has_role(role.name):
            self.roles.append(role)
    
    def remove_role(self, role):
        """Remove a role from the user"""
        if self.has_role(role.name):
            self.roles.remove(role)
    
    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>'

class Post(db.Model):
    """Sample Post model to demonstrate relationships"""
    
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Indexes for better query performance
    __table_args__ = (
        db.Index('idx_posts_created_at', 'created_at'),
        db.Index('idx_posts_user_published', 'user_id', 'published'),
    )
    
    def __repr__(self):
        return f'<Post {self.title}>'

class Category(db.Model):
    """Sample Category model"""
    
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class TimeEntry(db.Model):
    """Time Entry model for employee time tracking"""
    
    __tablename__ = 'time_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clock_in_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    clock_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Open', nullable=False)  # 'Open', 'Closed', 'Exception'
    notes = db.Column(db.Text, nullable=True)
    approved_by_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_overtime_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # GPS location data (optional for mobile tracking)
    clock_in_latitude = db.Column(db.Float, nullable=True)
    clock_in_longitude = db.Column(db.Float, nullable=True)
    clock_out_latitude = db.Column(db.Float, nullable=True)
    clock_out_longitude = db.Column(db.Float, nullable=True)
    
    # Break time tracking
    break_start_time = db.Column(db.DateTime, nullable=True)
    break_end_time = db.Column(db.DateTime, nullable=True)
    total_break_minutes = db.Column(db.Integer, default=0)
    
    # Pay code for this time entry
    pay_code_id = db.Column(db.Integer, db.ForeignKey('pay_codes.id'), nullable=True)
    
    # Absence tracking
    absence_pay_code_id = db.Column(db.Integer, db.ForeignKey('pay_codes.id'), nullable=True)
    absence_reason = db.Column(db.Text, nullable=True)
    absence_approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    absence_approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    employee = db.relationship('User', foreign_keys=[user_id], backref='time_entries')
    approved_by = db.relationship('User', foreign_keys=[approved_by_manager_id])
    absence_approved_by = db.relationship('User', foreign_keys=[absence_approved_by_id])
    
    # Comprehensive indexes for better query performance
    __table_args__ = (
        # Primary composite indexes for common query patterns
        db.Index('idx_time_entries_user_date', 'user_id', 'clock_in_time'),  # Most common: user + date queries
        db.Index('idx_time_entries_user_status', 'user_id', 'status'),       # User's entries by status
        db.Index('idx_time_entries_date_status', 'clock_in_time', 'status'), # Date range + status queries
        
        # Individual column indexes for filtering
        db.Index('idx_time_entries_status', 'status'),                       # Status-based filtering
        db.Index('idx_time_entries_approval', 'approved_by_manager_id'),     # Manager approval queries
        db.Index('idx_time_entries_pay_code', 'pay_code_id'),               # Pay code filtering
        db.Index('idx_time_entries_absence_code', 'absence_pay_code_id'),   # Absence code filtering
        
        # Date-specific indexes for reporting
        db.Index('idx_time_entries_clock_in_desc', 'clock_in_time', postgresql_using='btree'),    # Chronological ordering
        db.Index('idx_time_entries_clock_out', 'clock_out_time'),            # Clock out time queries
        db.Index('idx_time_entries_created_at', 'created_at'),               # Entry creation tracking
        
        # Composite indexes for complex queries
        db.Index('idx_time_entries_user_date_status', 'user_id', 'clock_in_time', 'status'),  # User + date + status
        db.Index('idx_time_entries_manager_date', 'approved_by_manager_id', 'clock_in_time'), # Manager approval by date
        
        # Geographic indexes for mobile tracking
        db.Index('idx_time_entries_location', 'clock_in_latitude', 'clock_in_longitude'),     # GPS location queries
    )
    
    @property
    def total_hours(self):
        """Calculate total hours worked"""
        if not self.clock_out_time:
            return 0
        
        total_time = self.clock_out_time - self.clock_in_time
        total_minutes = total_time.total_seconds() / 60
        
        # Subtract break time
        total_minutes -= self.total_break_minutes
        
        return round(total_minutes / 60, 2)
    
    @property
    def is_overtime(self):
        """Check if this entry qualifies as overtime (>8 hours)"""
        return self.total_hours > 8
    
    @property
    def overtime_hours(self):
        """Calculate overtime hours"""
        return max(0, self.total_hours - 8)
    
    @property
    def regular_hours(self):
        """Calculate regular hours (up to 8)"""
        return min(8, self.total_hours)
    
    @property
    def work_date(self):
        """Get the work date (date of clock-in)"""
        return self.clock_in_time.date()
    
    def can_be_approved_by(self, user):
        """Check if a user can approve this time entry"""
        # Super Users and Admins can approve any entry
        if user.has_role('Super User') or user.has_role('Admin'):
            return True
        
        # Managers can approve their team members' entries
        # (This would require a team/department structure - simplified for now)
        if user.has_role('Manager'):
            return True
        
        return False
    
    def __repr__(self):
        return f'<TimeEntry {self.employee.username} - {self.work_date}>'


class ShiftType(db.Model):
    """Shift Type model for defining work shifts"""
    
    __tablename__ = 'shift_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    default_start_time = db.Column(db.Time, nullable=False)
    default_end_time = db.Column(db.Time, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    schedules = db.relationship('Schedule', backref='shift_type', lazy='dynamic')
    
    def duration_hours(self):
        """Calculate shift duration in hours"""
        if self.default_end_time and self.default_start_time:
            # Handle overnight shifts
            start = datetime.combine(datetime.today(), self.default_start_time)
            end = datetime.combine(datetime.today(), self.default_end_time)
            
            if end < start:  # Overnight shift
                end += timedelta(days=1)
            
            delta = end - start
            return delta.total_seconds() / 3600
        return 0
    
    def __repr__(self):
        return f'<ShiftType {self.name}>'


class Schedule(db.Model):
    """Schedule model for employee work schedules"""
    
    __tablename__ = 'schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shift_type_id = db.Column(db.Integer, db.ForeignKey('shift_types.id'), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    assigned_by_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    pay_rule_link_id = db.Column(db.Integer, nullable=True)  # Placeholder for pay rules
    status = db.Column(db.String(20), default='Scheduled', nullable=False)  # 'Scheduled', 'Confirmed', 'Cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('User', foreign_keys=[user_id], backref='schedules')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_manager_id])
    
    # Comprehensive indexes for scheduling performance
    __table_args__ = (
        # Primary composite indexes for common scheduling queries
        db.Index('idx_schedules_user_date', 'user_id', 'start_time'),        # Most common: user + date queries
        db.Index('idx_schedules_user_status', 'user_id', 'status'),          # User's schedules by status
        db.Index('idx_schedules_date_range', 'start_time', 'end_time'),      # Date range overlap queries
        
        # Individual column indexes for filtering
        db.Index('idx_schedules_shift_type', 'shift_type_id'),               # Shift type filtering
        db.Index('idx_schedules_manager', 'assigned_by_manager_id'),         # Manager assignment queries
        db.Index('idx_schedules_status', 'status'),                         # Status-based filtering
        
        # Date-specific indexes for scheduling optimization
        db.Index('idx_schedules_start_time_desc', 'start_time', postgresql_using='btree'),  # Chronological ordering
        db.Index('idx_schedules_end_time', 'end_time'),                      # End time queries
        db.Index('idx_schedules_created_at', 'created_at'),                  # Schedule creation tracking
        
        # Composite indexes for complex scheduling queries
        db.Index('idx_schedules_user_date_status', 'user_id', 'start_time', 'status'),     # User + date + status
        db.Index('idx_schedules_manager_date', 'assigned_by_manager_id', 'start_time'),    # Manager schedules by date
        db.Index('idx_schedules_shift_date', 'shift_type_id', 'start_time'),               # Shift type scheduling
        
        # Conflict detection indexes
        db.Index('idx_schedules_overlap_check', 'user_id', 'start_time', 'end_time'),      # Overlap detection
    )
    
    def duration_hours(self):
        """Calculate scheduled duration in hours"""
        if self.end_time and self.start_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 3600
        return 0
    
    def is_past_due(self):
        """Check if schedule is past due"""
        return self.end_time < datetime.utcnow()
    
    def conflicts_with(self, other_schedule):
        """Check if this schedule conflicts with another"""
        return (self.start_time < other_schedule.end_time and 
                self.end_time > other_schedule.start_time)
    
    def work_date(self):
        """Get the work date (date of start time)"""
        return self.start_time.date()
    
    def __repr__(self):
        return f'<Schedule {self.employee.username} on {self.start_time.strftime("%Y-%m-%d")}>'


class LeaveType(db.Model):
    """Leave Type model for defining types of leave"""
    
    __tablename__ = 'leave_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    default_accrual_rate = db.Column(db.Float, nullable=True)  # Hours per month/year
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    requires_approval = db.Column(db.Boolean, default=True)
    max_consecutive_days = db.Column(db.Integer, nullable=True)  # Maximum consecutive days allowed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    leave_applications = db.relationship('LeaveApplication', backref='leave_type', lazy='dynamic')
    leave_balances = db.relationship('LeaveBalance', backref='leave_type', lazy='dynamic')
    
    def __repr__(self):
        return f'<LeaveType {self.name}>'


class LeaveApplication(db.Model):
    """Leave Application model for employee leave requests"""
    
    __tablename__ = 'leave_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # 'Pending', 'Approved', 'Rejected', 'Cancelled'
    is_hourly = db.Column(db.Boolean, default=False)
    hours_requested = db.Column(db.Float, nullable=True)  # For hourly leave requests
    manager_approved_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    manager_comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    employee = db.relationship('User', foreign_keys=[user_id], backref='leave_applications')
    manager_approved = db.relationship('User', foreign_keys=[manager_approved_id])
    
    # Comprehensive indexes for leave application performance
    __table_args__ = (
        # Primary composite indexes for common leave queries
        db.Index('idx_leave_applications_user_date', 'user_id', 'start_date'),     # Most common: user + date queries
        db.Index('idx_leave_applications_user_status', 'user_id', 'status'),       # User's applications by status
        db.Index('idx_leave_applications_date_range', 'start_date', 'end_date'),   # Date range overlap queries
        
        # Individual column indexes for filtering
        db.Index('idx_leave_applications_status', 'status'),                       # Status-based filtering
        db.Index('idx_leave_applications_manager', 'manager_approved_id'),         # Manager approval queries
        db.Index('idx_leave_applications_type', 'leave_type_id'),                  # Leave type filtering
        
        # Date-specific indexes for leave management
        db.Index('idx_leave_applications_start_date_desc', 'start_date', postgresql_using='btree'),  # Chronological ordering
        db.Index('idx_leave_applications_end_date', 'end_date'),                   # End date queries
        db.Index('idx_leave_applications_created_at', 'created_at'),               # Application creation tracking
        db.Index('idx_leave_applications_approved_at', 'approved_at'),             # Approval date tracking
        
        # Composite indexes for complex leave queries
        db.Index('idx_leave_applications_user_type_status', 'user_id', 'leave_type_id', 'status'),     # User + type + status
        db.Index('idx_leave_applications_manager_date', 'manager_approved_id', 'start_date'),          # Manager approvals by date
        db.Index('idx_leave_applications_type_date', 'leave_type_id', 'start_date'),                   # Leave type scheduling
        
        # Overlap detection and conflict resolution indexes
        db.Index('idx_leave_applications_overlap_check', 'user_id', 'start_date', 'end_date'),        # Overlap detection
        db.Index('idx_leave_applications_pending_approval', 'status', 'created_at'),                  # Pending approval queue
    )
    
    def total_days(self):
        """Calculate total days requested"""
        if self.is_hourly and self.hours_requested:
            return self.hours_requested / 8  # Assuming 8-hour workday
        return (self.end_date - self.start_date).days + 1
    
    def total_hours(self):
        """Calculate total hours requested"""
        if self.is_hourly and self.hours_requested:
            return self.hours_requested
        return self.total_days() * 8  # Assuming 8-hour workday
    
    def is_past_due(self):
        """Check if application start date has passed"""
        return self.start_date < datetime.utcnow().date()
    
    def can_be_cancelled(self):
        """Check if application can be cancelled by employee"""
        return (self.status in ['Pending', 'Approved'] and 
                not self.is_past_due())
    
    def overlaps_with(self, other_application):
        """Check if this application overlaps with another"""
        return (self.start_date <= other_application.end_date and 
                self.end_date >= other_application.start_date)
    
    def __repr__(self):
        return f'<LeaveApplication {self.employee.username} - {self.leave_type.name} ({self.start_date} to {self.end_date})>'


class LeaveBalance(db.Model):
    """Leave Balance model for tracking employee leave balances"""
    
    __tablename__ = 'leave_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)  # Available hours/days
    accrued_this_year = db.Column(db.Float, default=0.0)  # Total accrued this year
    used_this_year = db.Column(db.Float, default=0.0)  # Total used this year
    last_accrual_date = db.Column(db.Date, nullable=True)
    year = db.Column(db.Integer, nullable=False, default=lambda: datetime.utcnow().year)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('User', foreign_keys=[user_id], backref='leave_balances')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'leave_type_id', 'year', name='uq_user_leave_type_year'),
        db.Index('idx_leave_balances_user', 'user_id'),
        db.Index('idx_leave_balances_type', 'leave_type_id'),
        db.Index('idx_leave_balances_year', 'year'),
    )
    
    def add_accrual(self, hours):
        """Add accrued leave hours"""
        self.balance += hours
        self.accrued_this_year += hours
        self.last_accrual_date = datetime.utcnow().date()
    
    def deduct_usage(self, hours):
        """Deduct used leave hours"""
        if self.balance >= hours:
            self.balance -= hours
            self.used_this_year += hours
            return True
        return False
    
    def adjust_balance(self, new_balance, reason="Manual adjustment"):
        """Manually adjust balance (admin function)"""
        old_balance = self.balance
        self.balance = new_balance
        # Log the adjustment (could be expanded to include audit trail)
        return f"Balance adjusted from {old_balance} to {new_balance}. Reason: {reason}"
    
    def __repr__(self):
        return f'<LeaveBalance {self.employee.username} - {self.leave_type.name}: {self.balance} hours>'


class PayRule(db.Model):
    """Pay Rule model for configurable payroll calculations"""
    
    __tablename__ = 'pay_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    conditions = db.Column(db.Text, nullable=False)  # JSON string for rule conditions
    actions = db.Column(db.Text, nullable=False)  # JSON string for rule actions
    priority = db.Column(db.Integer, default=100, nullable=False)  # Lower number = higher priority
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_pay_rules_active', 'is_active'),
        db.Index('idx_pay_rules_priority', 'priority'),
        db.Index('idx_pay_rules_created_by', 'created_by_id'),
    )
    
    def get_conditions(self):
        """Parse and return conditions as dictionary"""
        import json
        try:
            return json.loads(self.conditions) if self.conditions else {}
        except json.JSONDecodeError:
            return {}
    
    def set_conditions(self, conditions_dict):
        """Set conditions from dictionary"""
        import json
        self.conditions = json.dumps(conditions_dict)
    
    def get_actions(self):
        """Parse and return actions as dictionary"""
        import json
        try:
            return json.loads(self.actions) if self.actions else {}
        except json.JSONDecodeError:
            return {}
    
    def set_actions(self, actions_dict):
        """Set actions from dictionary"""
        import json
        self.actions = json.dumps(actions_dict)
    
    def matches_conditions(self, time_entry, context=None):
        """Check if a time entry matches this rule's conditions"""
        conditions = self.get_conditions()
        if not conditions:
            return False
        
        # Day of week condition (0=Monday, 6=Sunday)
        if 'day_of_week' in conditions:
            entry_day = time_entry.clock_in_time.weekday()
            if entry_day not in conditions['day_of_week']:
                return False
        
        # Time of day condition (hour range)
        if 'time_range' in conditions:
            start_hour = conditions['time_range'].get('start', 0)
            end_hour = conditions['time_range'].get('end', 24)
            entry_hour = time_entry.clock_in_time.hour
            if not (start_hour <= entry_hour < end_hour):
                return False
        
        # Overtime threshold condition
        if 'overtime_threshold' in conditions:
            daily_hours = time_entry.total_hours()
            threshold = conditions['overtime_threshold']
            if daily_hours <= threshold:
                return False
        
        # Employee condition (specific users)
        if 'employee_ids' in conditions:
            if time_entry.user_id not in conditions['employee_ids']:
                return False
        
        # Role condition
        if 'roles' in conditions and context and 'user' in context:
            user_roles = [role.name for role in context['user'].roles]
            if not any(role in user_roles for role in conditions['roles']):
                return False
        
        return True
    
    def apply_actions(self, time_entry, context=None):
        """Apply this rule's actions to calculate pay components"""
        actions = self.get_actions()
        if not actions:
            return {}
        
        total_hours = time_entry.total_hours()
        pay_components = {}
        
        # Pay multiplier action
        if 'pay_multiplier' in actions:
            multiplier = actions['pay_multiplier']
            component_name = actions.get('component_name', f'{self.name}_hours')
            
            # Calculate applicable hours based on rule type
            if 'overtime_threshold' in self.get_conditions():
                threshold = self.get_conditions()['overtime_threshold']
                applicable_hours = max(0, total_hours - threshold)
            else:
                applicable_hours = total_hours
            
            pay_components[component_name] = {
                'hours': applicable_hours,
                'multiplier': multiplier,
                'rule_name': self.name
            }
        
        # Flat allowance action
        if 'flat_allowance' in actions:
            allowance = actions['flat_allowance']
            component_name = actions.get('allowance_name', f'{self.name}_allowance')
            pay_components[component_name] = {
                'amount': allowance,
                'type': 'allowance',
                'rule_name': self.name
            }
        
        # Shift differential action
        if 'shift_differential' in actions:
            differential = actions['shift_differential']
            component_name = actions.get('differential_name', f'{self.name}_differential')
            pay_components[component_name] = {
                'hours': total_hours,
                'differential': differential,
                'rule_name': self.name
            }
        
        return pay_components
    
    def __repr__(self):
        return f'<PayRule {self.name} (Priority: {self.priority})>'


class PayCalculation(db.Model):
    """Pay Calculation model to store calculated pay results"""
    
    __tablename__ = 'pay_calculations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    time_entry_id = db.Column(db.Integer, db.ForeignKey('time_entries.id'), nullable=False)
    pay_period_start = db.Column(db.Date, nullable=False)
    pay_period_end = db.Column(db.Date, nullable=False)
    pay_components = db.Column(db.Text, nullable=False)  # JSON string for pay breakdown
    total_hours = db.Column(db.Float, default=0.0)
    regular_hours = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)
    double_time_hours = db.Column(db.Float, default=0.0)
    total_allowances = db.Column(db.Float, default=0.0)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    calculated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    employee = db.relationship('User', foreign_keys=[user_id], backref='pay_calculations')
    time_entry = db.relationship('TimeEntry', foreign_keys=[time_entry_id])
    calculated_by = db.relationship('User', foreign_keys=[calculated_by_id])
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_pay_calculations_user_period', 'user_id', 'pay_period_start', 'pay_period_end'),
        db.Index('idx_pay_calculations_time_entry', 'time_entry_id'),
        db.Index('idx_pay_calculations_calculated_at', 'calculated_at'),
    )
    
    def get_pay_components(self):
        """Parse and return pay components as dictionary"""
        import json
        try:
            return json.loads(self.pay_components) if self.pay_components else {}
        except json.JSONDecodeError:
            return {}
    
    def set_pay_components(self, components_dict):
        """Set pay components from dictionary"""
        import json
        self.pay_components = json.dumps(components_dict)
    
    def __repr__(self):
        return f'<PayCalculation {self.employee.username} ({self.pay_period_start} to {self.pay_period_end})>'


class PayCode(db.Model):
    """Pay Code model for standardized payroll and absence codes"""
    
    __tablename__ = 'pay_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    is_absence_code = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Pay code configuration (JSON for flexibility)
    configuration = db.Column(db.Text, nullable=True)  # JSON string for code-specific settings
    
    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_pay_codes_active', 'is_active'),
        db.Index('idx_pay_codes_absence', 'is_absence_code'),
        db.Index('idx_pay_codes_created_by', 'created_by_id'),
    )
    
    def get_configuration(self):
        """Parse and return configuration as dictionary"""
        import json
        try:
            return json.loads(self.configuration) if self.configuration else {}
        except json.JSONDecodeError:
            return {}
    
    def set_configuration(self, config_dict):
        """Set configuration from dictionary"""
        import json
        self.configuration = json.dumps(config_dict)
    
    def is_paid_absence(self):
        """Check if this is a paid absence code"""
        if not self.is_absence_code:
            return False
        config = self.get_configuration()
        return config.get('is_paid', False)
    
    def get_pay_rate_factor(self):
        """Get pay rate factor for this code (1.0 = normal rate)"""
        config = self.get_configuration()
        return config.get('pay_rate_factor', 1.0)
    
    def requires_approval(self):
        """Check if this code requires manager approval"""
        config = self.get_configuration()
        return config.get('requires_approval', True)
    
    def max_hours_per_day(self):
        """Get maximum hours allowed per day for this code"""
        config = self.get_configuration()
        return config.get('max_hours_per_day')
    
    def max_consecutive_days(self):
        """Get maximum consecutive days allowed for this code"""
        config = self.get_configuration()
        return config.get('max_consecutive_days')
    
    def deducts_from_leave_balance(self):
        """Check if this code deducts from leave balance"""
        if not self.is_absence_code:
            return False
        config = self.get_configuration()
        return config.get('deducts_from_balance', False)
    
    def get_linked_leave_type_id(self):
        """Get linked leave type ID for balance deduction"""
        config = self.get_configuration()
        return config.get('leave_type_id')
    
    @staticmethod
    def get_default_codes():
        """Get standard pay codes that should exist in the system"""
        return [
            {
                'code': 'NORMAL',
                'description': 'Normal Working Hours',
                'is_absence_code': False,
                'configuration': {'pay_rate_factor': 1.0}
            },
            {
                'code': 'OT1.5',
                'description': 'Overtime 1.5x Rate',
                'is_absence_code': False,
                'configuration': {'pay_rate_factor': 1.5}
            },
            {
                'code': 'OT2.0',
                'description': 'Double Time Overtime',
                'is_absence_code': False,
                'configuration': {'pay_rate_factor': 2.0}
            },
            {
                'code': 'SICK_PAY',
                'description': 'Paid Sick Leave',
                'is_absence_code': True,
                'configuration': {
                    'is_paid': True,
                    'pay_rate_factor': 1.0,
                    'requires_approval': True,
                    'deducts_from_balance': True,
                    'max_consecutive_days': 5
                }
            },
            {
                'code': 'VACATION',
                'description': 'Paid Vacation Time',
                'is_absence_code': True,
                'configuration': {
                    'is_paid': True,
                    'pay_rate_factor': 1.0,
                    'requires_approval': True,
                    'deducts_from_balance': True
                }
            },
            {
                'code': 'UNPAID_LEAVE',
                'description': 'Unpaid Leave of Absence',
                'is_absence_code': True,
                'configuration': {
                    'is_paid': False,
                    'requires_approval': True,
                    'max_consecutive_days': 30
                }
            },
            {
                'code': 'HOLIDAY',
                'description': 'Holiday Pay',
                'is_absence_code': True,
                'configuration': {
                    'is_paid': True,
                    'pay_rate_factor': 1.0,
                    'requires_approval': False
                }
            },
            {
                'code': 'BEREAVEMENT',
                'description': 'Bereavement Leave',
                'is_absence_code': True,
                'configuration': {
                    'is_paid': True,
                    'pay_rate_factor': 1.0,
                    'requires_approval': True,
                    'max_consecutive_days': 3
                }
            }
        ]
    
    def __repr__(self):
        return f'<PayCode {self.code} - {self.description}>'
