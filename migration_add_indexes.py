"""
Database Migration: Add Comprehensive Indexing for Scalability
This migration adds strategic database indexes to optimize query performance
for the Time & Attendance System.
"""

from sqlalchemy import text
from app import app, db

def add_user_columns_and_indexes():
    """Add new User columns and comprehensive indexes"""
    migrations = [
        # Add new columns to users table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(20) UNIQUE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(64);", 
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS position VARCHAR(64);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS hire_date DATE;",
        
        # Add indexes to existing columns
        "CREATE INDEX IF NOT EXISTS idx_users_first_name ON users(first_name);",
        "CREATE INDEX IF NOT EXISTS idx_users_last_name ON users(last_name);",
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);",
        "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);",
        
        # Add indexes to new columns
        "CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_department ON users(department);",
        "CREATE INDEX IF NOT EXISTS idx_users_hire_date ON users(hire_date);",
        
        # Add composite indexes for User model
        "CREATE INDEX IF NOT EXISTS idx_users_full_name ON users(first_name, last_name);",
        "CREATE INDEX IF NOT EXISTS idx_users_dept_active ON users(department, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_users_hire_date_desc ON users(hire_date);",
    ]
    return migrations

def add_time_entry_indexes():
    """Add comprehensive TimeEntry indexes"""
    migrations = [
        # Primary composite indexes for common query patterns
        "CREATE INDEX IF NOT EXISTS idx_time_entries_user_status ON time_entries(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_date_status ON time_entries(clock_in_time, status);",
        
        # Individual column indexes for filtering
        "CREATE INDEX IF NOT EXISTS idx_time_entries_pay_code ON time_entries(pay_code_id);",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_absence_code ON time_entries(absence_pay_code_id);",
        
        # Date-specific indexes for reporting
        "CREATE INDEX IF NOT EXISTS idx_time_entries_clock_in_desc ON time_entries(clock_in_time);",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_clock_out ON time_entries(clock_out_time);",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_created_at ON time_entries(created_at);",
        
        # Composite indexes for complex queries
        "CREATE INDEX IF NOT EXISTS idx_time_entries_user_date_status ON time_entries(user_id, clock_in_time, status);",
        "CREATE INDEX IF NOT EXISTS idx_time_entries_manager_date ON time_entries(approved_by_manager_id, clock_in_time);",
        
        # Geographic indexes for mobile tracking
        "CREATE INDEX IF NOT EXISTS idx_time_entries_location ON time_entries(clock_in_latitude, clock_in_longitude);",
    ]
    return migrations

def add_schedule_indexes():
    """Add comprehensive Schedule indexes"""
    migrations = [
        # Primary composite indexes for common scheduling queries
        "CREATE INDEX IF NOT EXISTS idx_schedules_user_status ON schedules(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_date_range ON schedules(start_time, end_time);",
        
        # Individual column indexes for filtering
        "CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status);",
        
        # Date-specific indexes for scheduling optimization
        "CREATE INDEX IF NOT EXISTS idx_schedules_start_time_desc ON schedules(start_time);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_end_time ON schedules(end_time);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_created_at ON schedules(created_at);",
        
        # Composite indexes for complex scheduling queries
        "CREATE INDEX IF NOT EXISTS idx_schedules_user_date_status ON schedules(user_id, start_time, status);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_manager_date ON schedules(assigned_by_manager_id, start_time);",
        "CREATE INDEX IF NOT EXISTS idx_schedules_shift_date ON schedules(shift_type_id, start_time);",
        
        # Conflict detection indexes
        "CREATE INDEX IF NOT EXISTS idx_schedules_overlap_check ON schedules(user_id, start_time, end_time);",
    ]
    return migrations

def add_leave_application_indexes():
    """Add comprehensive LeaveApplication indexes"""
    migrations = [
        # Primary composite indexes for common leave queries
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_user_status ON leave_applications(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_date_range ON leave_applications(start_date, end_date);",
        
        # Date-specific indexes for leave management
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_start_date_desc ON leave_applications(start_date);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_end_date ON leave_applications(end_date);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_created_at ON leave_applications(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_approved_at ON leave_applications(approved_at);",
        
        # Composite indexes for complex leave queries
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_user_type_status ON leave_applications(user_id, leave_type_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_manager_date ON leave_applications(manager_approved_id, start_date);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_type_date ON leave_applications(leave_type_id, start_date);",
        
        # Overlap detection and conflict resolution indexes
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_overlap_check ON leave_applications(user_id, start_date, end_date);",
        "CREATE INDEX IF NOT EXISTS idx_leave_applications_pending_approval ON leave_applications(status, created_at);",
    ]
    return migrations

def add_leave_balance_indexes():
    """Add comprehensive LeaveBalance indexes"""
    migrations = [
        # Individual column indexes
        "CREATE INDEX IF NOT EXISTS idx_leave_balances_user ON leave_balances(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_leave_balances_type ON leave_balances(leave_type_id);",
        "CREATE INDEX IF NOT EXISTS idx_leave_balances_year ON leave_balances(year);",
        
        # Composite indexes for balance queries
        "CREATE INDEX IF NOT EXISTS idx_leave_balances_user_year ON leave_balances(user_id, year);",
        "CREATE INDEX IF NOT EXISTS idx_leave_balances_type_year ON leave_balances(leave_type_id, year);",
    ]
    return migrations

def run_migration():
    """Execute all migration scripts"""
    with app.app_context():
        try:
            # Collect all migrations
            all_migrations = []
            all_migrations.extend(add_user_columns_and_indexes())
            all_migrations.extend(add_time_entry_indexes())
            all_migrations.extend(add_schedule_indexes())
            all_migrations.extend(add_leave_application_indexes())
            all_migrations.extend(add_leave_balance_indexes())
            
            print("Starting database indexing migration...")
            
            # Execute each migration
            for i, migration in enumerate(all_migrations, 1):
                try:
                    db.session.execute(text(migration))
                    db.session.commit()
                    print(f"✓ Migration {i}/{len(all_migrations)}: {migration[:50]}...")
                except Exception as e:
                    print(f"✗ Failed migration {i}: {migration[:50]}... - Error: {e}")
                    db.session.rollback()
                    # Continue with other migrations
            
            print("Database indexing migration completed!")
            print("\nIndexes added for optimal scalability:")
            print("• User table: employee_id, department, name searches, activity tracking")
            print("• TimeEntry table: user+date combinations, status filtering, manager approvals")
            print("• Schedule table: user+date combinations, conflict detection, shift management")
            print("• LeaveApplication table: user+date+status, overlap detection, approval workflows")
            print("• LeaveBalance table: user+type+year combinations for balance tracking")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    run_migration()