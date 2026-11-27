# maintenance/utils.py — PERSON 3: small helpers used by the routes.
import os
import secrets
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import current_app
from werkzeug.utils import secure_filename

from maintenance import bp


# ---------------------------------------------------------------- money
def rupees_to_paise(text):
    """'1250.5' -> 125050.  Raises ValueError for junk, negatives, or >2 decimals.
    Decimal (not float) is used so '0.1' is exactly 0.1."""
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount, e.g. 1500 or 1500.50")
    if value < 0:
        raise ValueError("Amount cannot be negative")
    if value.as_tuple().exponent < -2:
        raise ValueError("Amount can have at most 2 decimal places")
    return int(value * 100)


@bp.app_template_filter("rupees")
def format_rupees(paise):
    """Jinja filter: {{ 125050 | rupees }} -> '₹1,250.50'.
    app_template_filter makes it available in EVERY template, not just ours."""
    paise = paise or 0
    return f"₹{paise // 100:,}.{paise % 100:02d}"


# ---------------------------------------------------------------- uploads
# The first bytes of a file ("magic numbers") reveal its real type.
# Checking them stops someone renaming virus.exe to cute.jpg.
_IMAGE_SIGNATURES = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "webp": [b"RIFF"],                 # plus "WEBP" at bytes 8-12, checked below
}


def _looks_like_image(header, ext):
    if ext == "webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return any(header.startswith(sig) for sig in _IMAGE_SIGNATURES.get(ext, []))


def save_complaint_photo(file_storage):
    """Validate and save an uploaded photo. Returns the stored filename,
    None if no file was chosen, or raises ValueError with a friendly message."""
    if file_storage is None or file_storage.filename == "":
        return None

    original = secure_filename(file_storage.filename)    # strips ../ and odd chars
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    allowed = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    if ext not in allowed:
        raise ValueError(f"Photo must be one of: {', '.join(sorted(allowed))}")

    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)                           # rewind before saving
    if not _looks_like_image(header, ext):
        raise ValueError("That file doesn't look like a real image.")

    # Random name: users can't guess other people's photo URLs, and two
    # uploads called "leak.jpg" don't overwrite each other.
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, stored_name))
    return stored_name


# ---------------------------------------------------------------- ids
def new_transaction_ref():
    """Fake gateway reference, e.g. MOCK-20261121-8F3A1C2B."""
    return f"MOCK-{datetime.now():%Y%m%d}-{secrets.token_hex(4).upper()}"


def new_receipt_number(payment_id):
    """Readable, unique receipt number, e.g. RCPT-2026-000042."""
    return f"RCPT-{datetime.now():%Y}-{payment_id:06d}"
