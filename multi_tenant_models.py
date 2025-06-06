"""
Multi-Tenant Models for WFM Application
Provides organization-based data isolation and tenant management
"""

from datetime import datetime
from app import db
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

class Tenant(db.Model):
    """Tenant/Organization model for multi-tenancy"""
    __tablename__ = 'tenants'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subdomain = db.Column(db.String(50), unique=True, nullable=False)
    domain = db.Column(db.String(100), nullable=True)  # Custom domain if provided
    
    # Tenant settings
    timezone = db.Column(db.String(50), default='Africa/Johannesburg')
    currency = db.Column(db.String(3), default='ZAR')
    date_format = db.Column(db.String(20), default='%Y-%m-%d')
    time_format = db.Column(db.String(20), default='%H:%M:%S')
    
    # Billing and subscription
    subscription_plan = db.Column(db.String(50), default='basic')
    max_users = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    
    # Contact information
    admin_email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship('User', back_populates='tenant', cascade='all, delete-orphan')
    time_entries = relationship('TimeEntry', back_populates='tenant', cascade='all, delete-orphan')
    schedules = relationship('Schedule', back_populates='tenant', cascade='all, delete-orphan')
    leave_applications = relationship('LeaveApplication', back_populates='tenant', cascade='all, delete-orphan')
    pay_rules = relationship('PayRule', back_populates='tenant', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Tenant {self.name}>'
    
    @property
    def user_count(self):
        """Get current user count for this tenant"""
        return len(self.users)
    
    @property
    def is_over_limit(self):
        """Check if tenant has exceeded user limit"""
        return self.user_count > self.max_users
    
    def can_add_user(self):
        """Check if tenant can add more users"""
        return self.user_count < self.max_users and self.is_active

class TenantSettings(db.Model):
    """Extended tenant settings for customization"""
    __tablename__ = 'tenant_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    
    # Branding
    company_logo_url = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(7), default='#27C1E3')  # Hex color
    secondary_color = db.Column(db.String(7), default='#ffffff')
    
    # Features enabled
    enable_geolocation = db.Column(db.Boolean, default=True)
    enable_overtime_alerts = db.Column(db.Boolean, default=True)
    enable_leave_workflow = db.Column(db.Boolean, default=True)
    enable_payroll_integration = db.Column(db.Boolean, default=False)
    enable_ai_scheduling = db.Column(db.Boolean, default=False)
    
    # Payroll settings
    default_pay_frequency = db.Column(db.String(20), default='monthly')  # weekly, bi-weekly, monthly
    overtime_threshold = db.Column(db.Integer, default=8)  # hours per day
    weekend_overtime_rate = db.Column(db.Float, default=1.5)
    holiday_overtime_rate = db.Column(db.Float, default=2.0)
    
    # Leave settings
    default_annual_leave_days = db.Column(db.Integer, default=21)
    default_sick_leave_days = db.Column(db.Integer, default=10)
    leave_approval_required = db.Column(db.Boolean, default=True)
    
    # Notifications
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship('Tenant', backref='settings')
    
    def __repr__(self):
        return f'<TenantSettings for {self.tenant.name}>'