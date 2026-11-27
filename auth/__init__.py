# auth/ — SHARED STUB (Person 4 owns the real login system).
# Just enough login/logout to test Person 3's pages with different roles.
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from extensions import db
from models.user import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if user and user.check_password(password):
            login_user(user)
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
