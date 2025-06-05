from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from models import User, Post, Category
import logging

# Create blueprint for main routes
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page route"""
    try:
        # Get some basic statistics from the database
        user_count = User.query.count()
        post_count = Post.query.count()
        category_count = Category.query.count()
        
        # Get recent posts
        recent_posts = Post.query.filter_by(published=True)\
                              .order_by(Post.created_at.desc())\
                              .limit(5)\
                              .all()
        
        return render_template('index.html',
                             user_count=user_count,
                             post_count=post_count,
                             category_count=category_count,
                             recent_posts=recent_posts)
    except Exception as e:
        logging.error(f"Error in index route: {e}")
        flash("An error occurred while loading the page.", "error")
        return render_template('index.html',
                             user_count=0,
                             post_count=0,
                             category_count=0,
                             recent_posts=[])

@main_bp.route('/users')
def users():
    """List all users"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        users = User.query.filter_by(is_active=True)\
                         .order_by(User.created_at.desc())\
                         .paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('users.html', users=users)
    except Exception as e:
        logging.error(f"Error in users route: {e}")
        flash("An error occurred while loading users.", "error")
        return redirect(url_for('main.index'))

@main_bp.route('/posts')
def posts():
    """List all published posts"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        posts = Post.query.filter_by(published=True)\
                         .order_by(Post.created_at.desc())\
                         .paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('posts.html', posts=posts)
    except Exception as e:
        logging.error(f"Error in posts route: {e}")
        flash("An error occurred while loading posts.", "error")
        return redirect(url_for('main.index'))

@main_bp.route('/db-status')
def db_status():
    """Check database connection status"""
    try:
        # Try to execute a simple query
        result = db.session.execute(db.text('SELECT 1'))
        result.fetchone()
        
        # Get table information
        tables_info = {}
        tables_info['users'] = User.query.count()
        tables_info['posts'] = Post.query.count()
        tables_info['categories'] = Category.query.count()
        
        return jsonify({
            'status': 'connected',
            'message': 'Database connection successful',
            'tables': tables_info
        })
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/create-sample-data')
def create_sample_data():
    """Create sample data for testing (development only)"""
    try:
        # Check if we already have data
        if User.query.count() > 0:
            return jsonify({
                'status': 'info',
                'message': 'Sample data already exists'
            })
        
        # Create sample user
        user = User(username='testuser', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Create sample category
        category = Category(name='Technology', description='Technology related posts')
        db.session.add(category)
        
        # Create sample posts
        post1 = Post(
            title='Welcome to Flask PostgreSQL App',
            content='This is a sample post to test the database integration.',
            published=True,
            user_id=user.id
        )
        
        post2 = Post(
            title='Database Migration Success',
            content='Flask-Migrate has been successfully configured.',
            published=True,
            user_id=user.id
        )
        
        db.session.add(post1)
        db.session.add(post2)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Sample data created successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating sample data: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
