# app.py — SHARED STUB (Person 4 owns the real one).
# The only lines Person 3 needs in the real app.py are marked "PERSON 3".
import os

from flask import Flask, redirect, render_template, url_for
from flask_login import current_user, login_required

from config import Config, INSTANCE_DIR
from extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    import models  # noqa: F401  (registers all tables)
    from auth import bp as auth_bp
    from maintenance import bp as maintenance_bp          # PERSON 3
    app.register_blueprint(auth_bp)
    app.register_blueprint(maintenance_bp)                # PERSON 3

    @app.route("/")
    @login_required
    def index():
        return render_template("home.html")

    @app.errorhandler(413)                                # PERSON 3: upload too big
    def too_large(_e):
        return render_template("error.html", code=413,
                               message="That photo is larger than 5 MB."), 413

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", code=403,
                               message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="Page not found."), 404

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
