# models/user.py — SHARED STUB (Person 4 / Person 1 own the real version).
# Person 3's code only relies on: User.id, User.name, User.role, User.flat_id,
# User.flat, and Flat.id, Flat.number. Keep those names when merging.
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager

ROLE_RESIDENT = "resident"
ROLE_GUARD = "guard"
ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"          # maintenance staff


class Flat(db.Model):
    __tablename__ = "flats"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False)   # e.g. "A-101"

    residents = db.relationship("User", back_populates="flat")

    def __repr__(self):
        return f"<Flat {self.number}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_RESIDENT)
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=True)

    flat = db.relationship("Flat", back_populates="residents")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
