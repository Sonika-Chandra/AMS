# maintenance/ — PERSON 3's blueprint.
# A Blueprint is a "mini app": a bundle of routes that Person 4 plugs into
# the main app with app.register_blueprint(bp). Every URL here starts with
# /maintenance, so it can never clash with Person 1/2/4's routes.
from flask import Blueprint

bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")

# Imported AFTER bp exists, because these files do `from maintenance import bp`.
from maintenance import complaints, billing, utils  # noqa: E402,F401
