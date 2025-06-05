"""
Database Update Script: Add Employee IDs to Existing Users
This script ensures all existing users have unique employee IDs as required by the updated model.
"""

from app import app, db
from models import User
import sys

def update_existing_users():
    """Add employee IDs to existing users who don't have them"""
    
    with app.app_context():
        # Find users without employee IDs
        users_without_ids = User.query.filter_by(employee_id=None).all()
        
        if not users_without_ids:
            print("All users already have employee IDs.")
            return
        
        print(f"Found {len(users_without_ids)} users without employee IDs.")
        
        # Generate employee IDs for existing users
        existing_ids = set()
        all_users = User.query.all()
        for user in all_users:
            if user.employee_id:
                existing_ids.add(user.employee_id)
        
        counter = 1
        for user in users_without_ids:
            # Generate unique employee ID
            while True:
                new_id = f"EMP{counter:03d}"
                if new_id not in existing_ids:
                    user.employee_id = new_id
                    existing_ids.add(new_id)
                    print(f"Assigned employee ID {new_id} to user {user.username}")
                    break
                counter += 1
        
        try:
            db.session.commit()
            print(f"Successfully updated {len(users_without_ids)} users with employee IDs.")
        except Exception as e:
            db.session.rollback()
            print(f"Error updating users: {e}")
            sys.exit(1)

if __name__ == "__main__":
    update_existing_users()