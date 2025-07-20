from flask import Flask
from db import db
from app.auth.routes import auth
from app.flashcards.routes import flashcards
from app.main.routes import main
from config import Config
from flask_login import LoginManager
from flask_mail import Mail
login_manager = LoginManager()
mail = Mail()
from models import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    app.register_blueprint(auth)
    app.register_blueprint(flashcards)
    app.register_blueprint(main)
    return app
