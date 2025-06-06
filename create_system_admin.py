#!/usr/bin/env python3
"""
System Super Admin Creation Script
Creates the initial system super admin who can manage all organizations
"""

from app import app, db
from models import User, Role
from werkzeug.security import generate_password_hash
import sys

def create_system_super_admin():
    """Create the initial system super admin"""
    with app.app_context():
        # Check if system super admin role exists
        super_admin_role = Role.query.filter_by(name='system_super_admin').first()
        if not super_admin_role:
            super_admin_role = Role(
                name='system_super_admin',
                description='System Super Administrator - can create and manage all organizations'
            )
            db.session.add(super_admin_role)
            db.session.commit()
            print("Created system_super_admin role")

        # Check if system super admin already exists
        existing_admin = User.query.filter(User.roles.any(name='system_super_admin')).first()
        if existing_admin:
            print(f"System super admin already exists: {existing_admin.username}")
            return existing_admin

        # Create system super admin
        print("Creating system super admin...")
        username = input("Enter username for system super admin: ").strip()
        email = input("Enter email for system super admin: ").strip()
        password = input("Enter password for system super admin: ").strip()
        
        if not username or not email or not password:
            print("All fields are required!")
            return None

        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            print(f"Username '{username}' already exists!")
            return None
        
        if User.query.filter_by(email=email).first():
            print(f"Email '{email}' already exists!")
            return None

        # Create the super admin user
        super_admin = User(
            username=username,
            email=email,
            first_name="System",
            last_name="Administrator",
            employee_id="SYSTEM_ADMIN_001",
            tenant_id=None,  # System super admin doesn't belong to any specific tenant
            is_active=True
        )
        super_admin.set_password(password)
        super_admin.add_role(super_admin_role)
        
        db.session.add(super_admin)
        db.session.commit()
        
        print(f"System super admin created successfully!")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print("This user can now create and manage all organizations.")
        
        return super_admin

if __name__ == "__main__":
    create_system_super_admin()