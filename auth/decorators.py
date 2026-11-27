# auth/decorators.py — SHARED (Person 4). Person 3 uses role_required a lot.
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    """Allow the view only for logged-in users whose role is in `roles`.

    Usage:
        @role_required("admin")
        @role_required("admin", "staff")
    """
    def decorator(view):
        @wraps(view)
        @login_required                       # first: must be logged in
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)                    # logged in, but wrong role
            return view(*args, **kwargs)
        return wrapped
    return decorator
