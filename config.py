# config.py  — SHARED (owned by Person 4). Person 3 only added the
# UPLOAD / MAX_CONTENT_LENGTH / LATE_FEE settings at the bottom.
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "ams.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- Person 3 settings ----
    # Complaint photos are stored OUTSIDE /static so that only logged-in,
    # permitted users can view them (served through a protected route).
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads", "complaints")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # reject uploads > 5 MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    LATE_FEE_PAISE = 100_00                         # ₹100 flat late fee
    STALE_DAYS = 2      # resident may report "no progress" after this many days without an update
