from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .models import db, Message, User
from flask_login import LoginManager, current_user
login_manager = LoginManager()
def create_app():
    app = Flask(__name__)
    # Application Configuration
    app.config['SECRET_KEY'] = 'DOCUCERT_SECRET_KEY'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:57642@127.0.0.1/flask_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # To avoid SQLAlchemy warning
    
    # Initialize extensions with the app
    db.init_app(app)
    login_manager.init_app(app)

    # User loader callback for flask-login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    with app.app_context():
        from .views import views
        from .auth import auth
        app.register_blueprint(views, url_prefix='/')
        app.register_blueprint(auth, url_prefix='/auth')  # Changed url_prefix for auth

    # Context Processor for unread_messages_count
    @app.context_processor
    def inject_unread_messages_count():
        if not current_user.is_authenticated:
            return dict(unread_messages_count=0)  # Return 0 if no user is logged in
        
        unread_messages_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return dict(unread_messages_count=unread_messages_count)

    return app

