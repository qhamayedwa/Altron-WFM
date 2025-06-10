#!/usr/bin/env python3
"""
Reset Admin Password Script
Securely updates the admin user password with proper hashing
"""

from werkzeug.security import generate_password_hash
from app import app, db
from models import User

def reset_admin_password(new_password="admin123"):
    """Reset admin password to a new secure password"""
    with app.app_context():
        try:
            # Find admin user
            admin_user = User.query.filter_by(username='admin').first()
            
            if not admin_user:
                print("❌ Admin user not found")
                return False
            
            # Generate new secure password hash
            password_hash = generate_password_hash(new_password)
            
            # Update password
            admin_user.password_hash = password_hash
            db.session.commit()
            
            print(f"✅ Admin password successfully reset")
            print(f"Username: admin")
            print(f"Password: {new_password}")
            print("You can now log in with these credentials")
            
            return True
            
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    reset_admin_password()