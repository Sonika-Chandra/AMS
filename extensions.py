# extensions.py — SHARED (Person 4).
# Extensions are created here WITHOUT an app, then attached in create_app().
# This avoids circular imports: models can do `from extensions import db`.
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"
