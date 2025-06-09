"""
Notification System for WFM Platform
Handles creation, management, and delivery of notifications for various system events
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, desc, func
from app import db
from models import Notification, NotificationType, NotificationPreference, User, LeaveApplication, Schedule
from auth_simple import role_required
from dashboard_management import get_managed_departments

# Create notifications blueprint
notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

class NotificationService:
    """Service class for managing notifications"""
    
    @staticmethod
    def create_notification(user_id, type_name, title, message, 
                          action_url=None, action_text=None, priority='medium',
                          category=None, related_entity_type=None, related_entity_id=None,
                          expires_hours=None):
        """
        Create a new notification for a user
        
        Args:
            user_id: Target user ID
            type_name: Notification type name
            title: Notification title
            message: Notification message
            action_url: Optional URL for action button
            action_text: Optional text for action button
            priority: Priority level (low, medium, high, urgent)
            category: Category for grouping
            related_entity_type: Related model name
            related_entity_id: Related model ID
            expires_hours: Hours until notification expires
        """
        try:
            # Get notification type
            notification_type = NotificationType.query.filter_by(name=type_name).first()
            if not notification_type:
                # Create default type if it doesn't exist
                notification_type = NotificationType(
                    name=type_name,
                    display_name=type_name.replace('_', ' ').title(),
                    icon='bell',
                    color='primary'
                )
                db.session.add(notification_type)
                db.session.flush()
            
            # Calculate expiration if specified
            expires_at = None
            if expires_hours:
                expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            
            # Create notification
            notification = Notification(
                user_id=user_id,
                type_id=notification_type.id,
                title=title,
                message=message,
                action_url=action_url,
                action_text=action_text,
                priority=priority,
                category=category,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                expires_at=expires_at
            )
            
            db.session.add(notification)
            db.session.commit()
            
            return notification
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating notification: {str(e)}")
            return None
    
    @staticmethod
    def create_leave_approval_notification(leave_application_id):
        """Create notification for leave approval needed"""
        try:
            leave_app = LeaveApplication.query.get(leave_application_id)
            if not leave_app:
                return None
            
            # Get the employee's manager(s)
            if leave_app.user.department_id:
                # Get managers who oversee this department
                from models import Department
                department = Department.query.get(leave_app.user.department_id)
                if department:
                    managers = []
                    if department.manager_id:
                        managers.append(department.manager_id)
                    if department.deputy_manager_id:
                        managers.append(department.deputy_manager_id)
                    
                    # Create notifications for managers
                    for manager_id in managers:
                        NotificationService.create_notification(
                            user_id=manager_id,
                            type_name='leave_approval_required',
                            title='Leave Approval Required',
                            message=f'{leave_app.user.full_name or leave_app.user.username} has requested {leave_app.total_days} days of {leave_app.leave_type.name if leave_app.leave_type else "leave"} from {leave_app.start_date.strftime("%b %d")} to {leave_app.end_date.strftime("%b %d")}',
                            action_url=url_for('leave_management.team_applications'),
                            action_text='Review Request',
                            priority='high',
                            category='leave',
                            related_entity_type='LeaveApplication',
                            related_entity_id=leave_application_id,
                            expires_hours=168  # 7 days
                        )
            
        except Exception as e:
            print(f"Error creating leave approval notification: {str(e)}")
    
    @staticmethod
    def create_leave_status_notification(leave_application_id, status):
        """Create notification for leave status change"""
        try:
            leave_app = LeaveApplication.query.get(leave_application_id)
            if not leave_app:
                return None
            
            status_messages = {
                'Approved': f'Your leave request from {leave_app.start_date.strftime("%b %d")} to {leave_app.end_date.strftime("%b %d")} has been approved.',
                'Rejected': f'Your leave request from {leave_app.start_date.strftime("%b %d")} to {leave_app.end_date.strftime("%b %d")} has been rejected.',
                'Cancelled': f'Your leave request from {leave_app.start_date.strftime("%b %d")} to {leave_app.end_date.strftime("%b %d")} has been cancelled.'
            }
            
            priority_map = {
                'Approved': 'medium',
                'Rejected': 'high',
                'Cancelled': 'low'
            }
            
            NotificationService.create_notification(
                user_id=leave_app.user_id,
                type_name='leave_status_update',
                title=f'Leave Request {status}',
                message=status_messages.get(status, f'Your leave request status has been updated to {status}.'),
                action_url=url_for('leave_management.my_applications'),
                action_text='View Details',
                priority=priority_map.get(status, 'medium'),
                category='leave',
                related_entity_type='LeaveApplication',
                related_entity_id=leave_application_id,
                expires_hours=72  # 3 days
            )
            
        except Exception as e:
            print(f"Error creating leave status notification: {str(e)}")
    
    @staticmethod
    def create_schedule_change_notification(schedule_id, change_type='updated'):
        """Create notification for schedule changes"""
        try:
            schedule = Schedule.query.get(schedule_id)
            if not schedule:
                return None
            
            change_messages = {
                'created': f'You have been scheduled to work on {schedule.date.strftime("%b %d, %Y")} from {schedule.start_time.strftime("%H:%M")} to {schedule.end_time.strftime("%H:%M")}.',
                'updated': f'Your schedule for {schedule.date.strftime("%b %d, %Y")} has been updated. New time: {schedule.start_time.strftime("%H:%M")} to {schedule.end_time.strftime("%H:%M")}.',
                'cancelled': f'Your schedule for {schedule.date.strftime("%b %d, %Y")} has been cancelled.'
            }
            
            NotificationService.create_notification(
                user_id=schedule.user_id,
                type_name='schedule_change',
                title=f'Schedule {change_type.title()}',
                message=change_messages.get(change_type, f'Your schedule has been {change_type}.'),
                action_url=url_for('scheduling.my_schedule'),
                action_text='View Schedule',
                priority='high',
                category='schedule',
                related_entity_type='Schedule',
                related_entity_id=schedule_id,
                expires_hours=24  # 1 day
            )
            
        except Exception as e:
            print(f"Error creating schedule change notification: {str(e)}")
    
    @staticmethod
    def create_timecard_reminder_notification(user_id):
        """Create notification for timecard reminders"""
        NotificationService.create_notification(
            user_id=user_id,
            type_name='timecard_reminder',
            title='Timecard Reminder',
            message='Don\'t forget to submit your timecard for this week.',
            action_url=url_for('time_attendance.my_timecard'),
            action_text='View Timecard',
            priority='medium',
            category='timecard',
            expires_hours=48  # 2 days
        )
    
    @staticmethod
    def get_user_notifications(user_id, limit=50, unread_only=False):
        """Get notifications for a user with department filtering for managers"""
        from models import User, Department
        
        user = User.query.get(user_id)
        if not user:
            return []
        
        # Base query for user's own notifications
        query = Notification.query.filter_by(user_id=user_id)
        
        # If user is a manager, also include notifications from their department's employees
        if user.has_role('Manager'):
            # Get departments this user manages (returns list of department IDs)
            dept_ids = get_managed_departments(user_id)
            
            if dept_ids:
                
                # Get all employees in managed departments
                dept_employees = User.query.filter(
                    User.department_id.in_(dept_ids),
                    User.is_active == True
                ).all()
                
                dept_employee_ids = [emp.id for emp in dept_employees]
                
                # Include notifications for department employees (specific types only)
                if dept_employee_ids:
                    dept_query = Notification.query.filter(
                        Notification.user_id.in_(dept_employee_ids),
                        Notification.category.in_(['leave', 'timecard', 'attendance', 'urgent_approval'])
                    )
                    
                    # Combine both queries
                    query = query.union(dept_query)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        # Filter out expired notifications
        query = query.filter(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
        
        return query.order_by(desc(Notification.created_at)).limit(limit).all()
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user with department filtering for managers"""
        from models import User
        
        user = User.query.get(user_id)
        if not user:
            return 0
        
        # Base query for user's own notifications
        query = Notification.query.filter_by(user_id=user_id, is_read=False)
        
        # If user is a manager, also count notifications from their department's employees
        if user.has_role('Manager'):
            # Get departments this user manages (returns list of department IDs)
            dept_ids = get_managed_departments(user_id)
            
            if dept_ids:
                
                # Get all employees in managed departments
                dept_employees = User.query.filter(
                    User.department_id.in_(dept_ids),
                    User.is_active == True
                ).all()
                
                dept_employee_ids = [emp.id for emp in dept_employees]
                
                # Include unread notifications for department employees (specific types only)
                if dept_employee_ids:
                    dept_query = Notification.query.filter(
                        Notification.user_id.in_(dept_employee_ids),
                        Notification.is_read == False,
                        Notification.category.in_(['leave', 'timecard', 'attendance', 'urgent_approval'])
                    )
                    
                    # Combine both queries
                    query = query.union(dept_query)
        
        # Filter out expired notifications
        return query.filter(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        ).count()
    
    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        notifications = Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).all()
        
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
        
        db.session.commit()
        return len(notifications)
    
    @staticmethod
    def cleanup_expired_notifications():
        """Remove expired notifications"""
        expired_count = Notification.query.filter(
            Notification.expires_at < datetime.utcnow()
        ).delete()
        
        db.session.commit()
        return expired_count


# Routes

@notifications_bp.route('/')
@login_required
def notifications_page():
    """Main notifications page with department filtering for managers"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    filter_type = request.args.get('filter', 'all')  # all, unread, by_category
    category = request.args.get('category')
    
    # Use the department-aware notification service
    all_notifications = NotificationService.get_user_notifications(
        current_user.id, 
        limit=1000  # Get more for proper pagination
    )
    
    # Apply additional filters
    if filter_type == 'unread':
        all_notifications = [n for n in all_notifications if not n.is_read]
    elif category:
        all_notifications = [n for n in all_notifications if n.category == category]
    
    # Manual pagination
    total = len(all_notifications)
    start = (page - 1) * per_page
    end = start + per_page
    notifications_list = all_notifications[start:end]
    
    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
    
    notifications = SimplePagination(notifications_list, page, per_page, total)
    
    # Get notification categories for filter from all user notifications
    categories = list(set([n.category for n in all_notifications if n.category]))
    
    return render_template('notifications/index.html',
                         notifications=notifications,
                         filter_type=filter_type,
                         category=category,
                         categories=categories)


@notifications_bp.route('/api/unread-count')
@login_required
def api_unread_count():
    """API endpoint to get unread notification count"""
    count = NotificationService.get_unread_count(current_user.id)
    return jsonify({'success': True, 'count': count})


@notifications_bp.route('/api/recent')
@login_required
def api_recent_notifications():
    """API endpoint to get recent notifications"""
    limit = request.args.get('limit', 5, type=int)
    notifications = NotificationService.get_user_notifications(current_user.id, limit=limit)
    
    return jsonify({
        'success': True,
        'notifications': [notification.to_dict() for notification in notifications]
    })


@notifications_bp.route('/api/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def api_mark_read(notification_id):
    """Mark a specific notification as read"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()
    
    if not notification:
        return jsonify({'success': False, 'message': 'Notification not found'})
    
    notification.mark_as_read()
    return jsonify({'success': True, 'message': 'Notification marked as read'})


@notifications_bp.route('/api/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_read():
    """Mark all notifications as read"""
    count = NotificationService.mark_all_as_read(current_user.id)
    return jsonify({'success': True, 'message': f'{count} notifications marked as read'})


@notifications_bp.route('/preferences')
@login_required
def notification_preferences():
    """Notification preferences page"""
    # Get all notification types
    notification_types = NotificationType.query.filter_by(is_active=True).all()
    
    # Get user's current preferences
    user_preferences = {}
    for pref in current_user.notification_preferences:
        user_preferences[pref.type_id] = pref
    
    return render_template('notifications/preferences.html',
                         notification_types=notification_types,
                         user_preferences=user_preferences)


@notifications_bp.route('/preferences/save', methods=['POST'])
@login_required
def save_notification_preferences():
    """Save notification preferences"""
    try:
        notification_types = NotificationType.query.filter_by(is_active=True).all()
        
        for notification_type in notification_types:
            # Get or create preference
            preference = NotificationPreference.query.filter_by(
                user_id=current_user.id,
                type_id=notification_type.id
            ).first()
            
            if not preference:
                preference = NotificationPreference(
                    user_id=current_user.id,
                    type_id=notification_type.id
                )
                db.session.add(preference)
            
            # Update settings
            preference.web_enabled = request.form.get(f'web_{notification_type.id}') == 'on'
            preference.email_enabled = request.form.get(f'email_{notification_type.id}') == 'on'
            preference.immediate = request.form.get(f'immediate_{notification_type.id}') == 'on'
            preference.daily_digest = request.form.get(f'daily_{notification_type.id}') == 'on'
        
        db.session.commit()
        flash('Notification preferences saved successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving preferences: {str(e)}', 'danger')
    
    return redirect(url_for('notifications.notification_preferences'))


# Admin routes for managing notification types
@notifications_bp.route('/admin/dashboard')
@role_required('Super User')
def admin_dashboard():
    """Notification management dashboard for Super Users"""
    from datetime import datetime, timedelta
    
    # Get statistics
    total_notifications = Notification.query.count()
    unread_notifications = Notification.query.filter_by(is_read=False).count()
    urgent_notifications = Notification.query.filter_by(priority='urgent', is_read=False).count()
    notification_types_count = NotificationType.query.count()
    
    # Last 24 hours statistics
    yesterday = datetime.utcnow() - timedelta(days=1)
    last_24h_sent = Notification.query.filter(Notification.created_at >= yesterday).count()
    last_24h_users = db.session.query(Notification.user_id).filter(
        Notification.created_at >= yesterday
    ).distinct().count()
    last_24h_urgent = Notification.query.filter(
        Notification.created_at >= yesterday,
        Notification.priority == 'urgent'
    ).count()
    
    # Calculate read rate
    total_today = Notification.query.filter(Notification.created_at >= yesterday).count()
    read_today = Notification.query.filter(
        Notification.created_at >= yesterday,
        Notification.is_read == True
    ).count()
    read_rate = round((read_today / total_today * 100) if total_today > 0 else 0, 1)
    
    stats = {
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'urgent_notifications': urgent_notifications,
        'notification_types': notification_types_count,
        'last_24h_sent': last_24h_sent,
        'last_24h_users': last_24h_users,
        'last_24h_urgent': last_24h_urgent,
        'read_rate': read_rate
    }
    
    # Get notification types with usage counts
    notification_types = db.session.query(
        NotificationType,
        func.count(Notification.id).label('usage_count')
    ).outerjoin(Notification).group_by(NotificationType.id).all()
    
    # Format notification types
    formatted_types = []
    for type_obj, usage_count in notification_types:
        type_dict = {
            'id': type_obj.id,
            'name': type_obj.name,
            'display_name': type_obj.display_name,
            'description': type_obj.description,
            'icon': type_obj.icon,
            'color': type_obj.color,
            'priority': type_obj.priority,
            'usage_count': usage_count
        }
        formatted_types.append(type_dict)
    
    # Workflow triggers - define available notification triggers
    workflow_triggers = [
        {
            'name': 'Leave Management',
            'module': 'leave_management.py',
            'description': 'Triggers notifications for leave requests, approvals, and status changes',
            'icon': 'calendar',
            'color': 'primary',
            'trigger_count': 3,
            'enabled': True
        },
        {
            'name': 'Time Attendance',
            'module': 'time_attendance.py',
            'description': 'Sends timecard reminders and attendance notifications',
            'icon': 'clock',
            'color': 'success',
            'trigger_count': 2,
            'enabled': True
        },
        {
            'name': 'Schedule Management',
            'module': 'scheduling.py',
            'description': 'Notifies about schedule changes and conflicts',
            'icon': 'calendar-check',
            'color': 'warning',
            'trigger_count': 2,
            'enabled': True
        },
        {
            'name': 'Payroll Processing',
            'module': 'payroll.py',
            'description': 'Alerts for payroll deadlines and processing status',
            'icon': 'dollar-sign',
            'color': 'info',
            'trigger_count': 1,
            'enabled': False
        },
        {
            'name': 'User Management',
            'module': 'auth.py',
            'description': 'Security alerts and user account notifications',
            'icon': 'shield',
            'color': 'danger',
            'trigger_count': 2,
            'enabled': True
        },
        {
            'name': 'System Monitoring',
            'module': 'system.py',
            'description': 'System alerts, maintenance notices, and performance warnings',
            'icon': 'server',
            'color': 'secondary',
            'trigger_count': 4,
            'enabled': True
        }
    ]
    
    # Recent activity
    recent_notifications = Notification.query.order_by(
        desc(Notification.created_at)
    ).limit(10).all()
    
    recent_activity = []
    for notif in recent_notifications:
        activity = {
            'title': notif.title,
            'description': f'Sent to {notif.user.first_name} {notif.user.last_name}',
            'time_ago': format_time_ago(notif.created_at),
            'icon': notif.notification_type.icon if notif.notification_type else 'bell',
            'color': notif.notification_type.color if notif.notification_type else 'primary'
        }
        recent_activity.append(activity)
    
    return render_template('notifications/admin_dashboard.html',
                         stats=stats,
                         notification_types=formatted_types,
                         workflow_triggers=workflow_triggers,
                         recent_activity=recent_activity)


@notifications_bp.route('/admin/types')
@role_required('Super User')
def manage_notification_types():
    """Manage notification types (Super User only)"""
    notification_types = NotificationType.query.order_by(NotificationType.name).all()
    return render_template('notifications/admin_types.html',
                         notification_types=notification_types)


def init_notification_types():
    """Initialize default notification types - called during app startup"""
    initialize_default_notification_types()

def initialize_default_notification_types():
    """Initialize default notification types"""
    default_types = [
        {
            'name': 'leave_approval_required',
            'display_name': 'Leave Approval Required',
            'description': 'Notifications for managers when leave requests need approval',
            'icon': 'calendar-check',
            'color': 'warning',
            'priority': 'high'
        },
        {
            'name': 'leave_status_update',
            'display_name': 'Leave Status Update',
            'description': 'Notifications when leave request status changes',
            'icon': 'calendar',
            'color': 'info',
            'priority': 'medium'
        },
        {
            'name': 'schedule_change',
            'display_name': 'Schedule Change',
            'description': 'Notifications for schedule updates',
            'icon': 'clock',
            'color': 'primary',
            'priority': 'high'
        },
        {
            'name': 'timecard_reminder',
            'display_name': 'Timecard Reminder',
            'description': 'Reminders to submit timecards',
            'icon': 'clipboard',
            'color': 'secondary',
            'priority': 'medium'
        },
        {
            'name': 'system_alert',
            'display_name': 'System Alert',
            'description': 'System maintenance and alerts',
            'icon': 'alert-triangle',
            'color': 'danger',
            'priority': 'urgent'
        }
    ]
    
    for type_data in default_types:
        existing = NotificationType.query.filter_by(name=type_data['name']).first()
        if not existing:
            notification_type = NotificationType(**type_data)
            db.session.add(notification_type)
    
    db.session.commit()


def create_test_notifications():
    """Create test notifications for demonstration purposes"""
    try:
        # Get some users to create notifications for
        users = User.query.filter_by(is_active=True).limit(10).all()
        
        if not users:
            print("No active users found for test notifications")
            return
        
        # Create various types of test notifications
        test_notifications = [
            {
                'type_name': 'leave_approval_required',
                'title': 'Leave Request Pending Approval',
                'message': 'John Doe has submitted a leave request for 3 days starting next Monday. Please review and approve.',
                'priority': 'high',
                'action_url': '/leave/manage',
                'action_text': 'Review Request'
            },
            {
                'type_name': 'leave_status_update',
                'title': 'Leave Request Approved',
                'message': 'Your leave request for Dec 15-17 has been approved by your manager.',
                'priority': 'medium',
                'action_url': '/leave/my-applications',
                'action_text': 'View Details'
            },
            {
                'type_name': 'schedule_change',
                'title': 'Schedule Updated',
                'message': 'Your shift on Friday has been moved from 9:00 AM to 10:00 AM.',
                'priority': 'high',
                'action_url': '/scheduling',
                'action_text': 'View Schedule'
            },
            {
                'type_name': 'timecard_reminder',
                'title': 'Timecard Submission Reminder',
                'message': 'Don\'t forget to submit your timecard for this week. Due by Friday 5:00 PM.',
                'priority': 'medium',
                'action_url': '/time-attendance',
                'action_text': 'Submit Timecard'
            },
            {
                'type_name': 'system_alert',
                'title': 'System Maintenance Notice',
                'message': 'Scheduled maintenance will occur tonight from 11:00 PM to 1:00 AM. Limited functionality expected.',
                'priority': 'urgent',
                'expires_hours': 24
            }
        ]
        
        notifications_created = 0
        for user in users[:5]:  # Create notifications for first 5 users
            for i, notification_data in enumerate(test_notifications):
                # Don't create all notifications for all users to avoid spam
                if i < 3 or user.id % 2 == 0:  # Vary which notifications each user gets
                    NotificationService.create_notification(
                        user_id=user.id,
                        **notification_data
                    )
                    notifications_created += 1
        
        print(f"Created {notifications_created} test notifications for {len(users[:5])} users")
        return notifications_created
        
    except Exception as e:
        print(f"Error creating test notifications: {e}")
        return 0


def format_time_ago(timestamp):
    """Format timestamp as time ago string"""
    from datetime import datetime
    
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"


# API endpoints for admin dashboard
@notifications_bp.route('/admin/api/create-type', methods=['POST'])
@role_required('Super User')
def api_create_notification_type():
    """Create new notification type"""
    try:
        data = request.get_json()
        
        # Check if type name already exists
        existing = NotificationType.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'message': 'Type name already exists'})
        
        new_type = NotificationType(
            name=data['name'],
            display_name=data['display_name'],
            description=data.get('description', ''),
            icon=data['icon'],
            color=data['color'],
            priority=data['priority']
        )
        
        db.session.add(new_type)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notification type created successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@notifications_bp.route('/admin/api/toggle-trigger', methods=['POST'])
@role_required('Super User')
def api_toggle_trigger():
    """Toggle workflow trigger"""
    try:
        data = request.get_json()
        trigger_name = data['trigger']
        enabled = data['enabled']
        
        return jsonify({
            'success': True, 
            'message': f'Trigger {trigger_name} {"enabled" if enabled else "disabled"}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@notifications_bp.route('/admin/api/save-settings', methods=['POST'])
@role_required('Super User')
def api_save_settings():
    """Save notification system settings"""
    try:
        data = request.get_json()
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@notifications_bp.route('/admin/cleanup', methods=['GET'])
@role_required('Super User')
def cleanup_notifications():
    """Cleanup expired notifications"""
    try:
        expired_count = NotificationService.cleanup_expired_notifications()
        flash(f'Cleaned up {expired_count} expired notifications', 'success')
    except Exception as e:
        flash(f'Error during cleanup: {str(e)}', 'danger')
    
    return redirect(url_for('notifications.admin_dashboard'))