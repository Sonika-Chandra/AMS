# maintenance/complaints.py — PERSON 3: Helpdesk routes.
#
#   URL                                       Who
#   /maintenance/complaints                   resident (own flat) | staff (assigned) | admin (all)
#   /maintenance/complaints/new               resident
#   /maintenance/complaints/<id>              anyone allowed to see that complaint
#   /maintenance/complaints/<id>/assign       admin           (POST)
#   /maintenance/complaints/<id>/status       admin | assigned staff (POST) — status change or progress update
#   /maintenance/complaints/<id>/escalate     resident (POST) — "no progress" / "not actually fixed"
#   /maintenance/complaints/photo/<filename>  anyone allowed to see that complaint
from datetime import datetime, timedelta

from flask import (abort, current_app, flash, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_login import current_user, login_required

from auth.decorators import role_required
from extensions import db
from maintenance import bp
from maintenance.utils import save_complaint_photo
from models import (ROLE_ADMIN, ROLE_RESIDENT, ROLE_STAFF, Complaint,
                    ComplaintCategory, ComplaintStatus, ComplaintUpdate,
                    StaffAssignment, User)


# ---------------------------------------------------------------- permissions
def can_view(user, complaint):
    """Single source of truth for 'may this user see this complaint?'"""
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_RESIDENT:
        return complaint.flat_id == user.flat_id      # whole household can see it
    if user.role == ROLE_STAFF:
        return complaint.assigned_staff is not None and complaint.assigned_staff.id == user.id
    return False                                       # guards: no access


def get_complaint_or_404(complaint_id):
    complaint = db.get_or_404(Complaint, complaint_id)
    if not can_view(current_user, complaint):
        # 404 rather than 403: don't even reveal that complaint #7 exists.
        abort(404)
    return complaint


def log_update(complaint, message, photo=None, kind="update"):
    db.session.add(ComplaintUpdate(complaint=complaint, author_id=current_user.id,
                                   status=complaint.status, message=message,
                                   photo_filename=photo, kind=kind))


def can_escalate(user, complaint):
    """May this resident press 'Report no progress'? Returns (yes/no, why not).
    Allowed when: it's their flat, it isn't already escalated, AND either
      - it was marked Fixed (they can dispute the fix), or
      - nobody has updated it for STALE_DAYS days."""
    if user.role != ROLE_RESIDENT or complaint.flat_id != user.flat_id:
        return False, ""
    if complaint.is_escalated:
        return False, "Already reported to the admin."
    if complaint.status == ComplaintStatus.FIXED:
        return True, ""
    days = current_app.config["STALE_DAYS"]
    idle = datetime.now() - complaint.last_progress_at
    if idle >= timedelta(days=days):
        return True, ""
    return False, f"You can report no progress if there's no update for {days} days."


# ---------------------------------------------------------------- list
@bp.route("/complaints")
@role_required(ROLE_RESIDENT, ROLE_STAFF, ROLE_ADMIN)
def complaint_list():
    query = db.select(Complaint).order_by(Complaint.created_at.desc())

    # Each role sees a different slice of the same table.
    if current_user.role == ROLE_RESIDENT:
        query = query.where(Complaint.flat_id == current_user.flat_id)
    elif current_user.role == ROLE_STAFF:
        # "currently assigned to me" is decided in Python (latest assignment),
        # so first narrow to complaints I was EVER assigned to, then filter.
        query = query.join(StaffAssignment).where(StaffAssignment.staff_id == current_user.id).distinct()

    status_filter = request.args.get("status", "")
    if status_filter in ComplaintStatus.ALL:
        query = query.where(Complaint.status == status_filter)
    escalated_only = request.args.get("escalated") == "1"
    if escalated_only:
        query = query.where(Complaint.escalated_at.is_not(None))

    complaints = db.session.execute(query).scalars().all()
    if current_user.role == ROLE_STAFF:
        complaints = [c for c in complaints if can_view(current_user, c)]

    return render_template("maintenance/complaint_list.html", complaints=complaints,
                           statuses=ComplaintStatus.ALL, status_filter=status_filter,
                           escalated_only=escalated_only)


# ---------------------------------------------------------------- create
@bp.route("/complaints/new", methods=["GET", "POST"])
@role_required(ROLE_RESIDENT)
def complaint_new():
    categories = db.session.execute(
        db.select(ComplaintCategory).order_by(ComplaintCategory.name)).scalars().all()

    if current_user.flat_id is None:
        flash("Your account isn't linked to a flat yet. Please contact the admin.", "warning")
        return redirect(url_for("maintenance.complaint_list"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)

        # --- server-side validation (never trust the browser) ---
        errors = []
        if not 5 <= len(title) <= 120:
            errors.append("Title must be 5–120 characters.")
        if len(description) < 10:
            errors.append("Please describe the issue in at least 10 characters.")
        if category_id is None or db.session.get(ComplaintCategory, category_id) is None:
            errors.append("Choose a valid category.")

        photo_name = None
        if not errors:                       # only save the file if the rest is valid
            try:
                photo_name = save_complaint_photo(request.files.get("photo"))
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for e in errors:
                flash(e, "danger")
            # Re-show the form with what they typed, so they don't lose it.
            return render_template("maintenance/complaint_form.html",
                                   categories=categories, form=request.form), 400

        complaint = Complaint(title=title, description=description, category_id=category_id,
                              flat_id=current_user.flat_id, raised_by_id=current_user.id,
                              photo_filename=photo_name)
        db.session.add(complaint)
        log_update(complaint, "Complaint raised.")
        db.session.commit()
        flash(f"Complaint #{complaint.id} submitted. We'll keep you posted.", "success")
        return redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))

    return render_template("maintenance/complaint_form.html", categories=categories, form={})


# ---------------------------------------------------------------- detail
@bp.route("/complaints/<int:complaint_id>")
@role_required(ROLE_RESIDENT, ROLE_STAFF, ROLE_ADMIN)
def complaint_detail(complaint_id):
    complaint = get_complaint_or_404(complaint_id)

    staff_members = []
    if current_user.role == ROLE_ADMIN:
        staff_members = db.session.execute(
            db.select(User).where(User.role == ROLE_STAFF).order_by(User.name)).scalars().all()

    escalate_ok, escalate_why = can_escalate(current_user, complaint)
    return render_template("maintenance/complaint_detail.html", complaint=complaint,
                           staff_members=staff_members,
                           next_statuses=allowed_statuses(current_user, complaint),
                           escalate_ok=escalate_ok, escalate_why=escalate_why)


def allowed_statuses(user, complaint):
    """Which statuses can THIS user pick? 'Working On It' while already
    Working On It = a progress update."""
    if user.role == ROLE_STAFF:
        return ComplaintStatus.STAFF_NEXT[complaint.status]
    if user.role == ROLE_ADMIN:
        return [s for s in ComplaintStatus.ALL
                if s != complaint.status or s == ComplaintStatus.WORKING]
    return []


# ---------------------------------------------------------------- assign (admin)
@bp.route("/complaints/<int:complaint_id>/assign", methods=["POST"])
@role_required(ROLE_ADMIN)
def complaint_assign(complaint_id):
    complaint = get_complaint_or_404(complaint_id)
    staff = db.session.get(User, request.form.get("staff_id", type=int) or 0)
    note = request.form.get("note", "").strip()[:255]
    same_person = complaint.assigned_staff and staff and complaint.assigned_staff.id == staff.id

    if staff is None or staff.role != ROLE_STAFF:
        flash("Pick a valid maintenance staff member.", "danger")
    elif same_person and not complaint.is_escalated:
        flash(f"Already assigned to {staff.name}.", "info")
    else:
        # Re-assigning the SAME person is allowed on an escalated complaint:
        # it acts as "admin has chased this up" and clears the escalation.
        db.session.add(StaffAssignment(complaint=complaint, staff_id=staff.id,
                                       assigned_by_id=current_user.id, note=note or None))
        verb = "Escalation handled: re-assigned to" if complaint.is_escalated else "Assigned to"
        complaint.escalated_at = None
        log_update(complaint, f"{verb} {staff.name}." + (f" Note: {note}" if note else ""))
        db.session.commit()
        flash(f"Complaint assigned to {staff.name}.", "success")

    return redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))


# ---------------------------------------------------------------- status / progress (admin / staff)
@bp.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@role_required(ROLE_ADMIN, ROLE_STAFF)
def complaint_status(complaint_id):
    complaint = get_complaint_or_404(complaint_id)   # staff: must be the assignee
    new_status = request.form.get("status", "")
    note = request.form.get("note", "").strip()[:400]
    photo_file = request.files.get("photo")
    has_photo = photo_file is not None and photo_file.filename != ""
    back = redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))

    if new_status not in allowed_statuses(current_user, complaint):
        flash(f"Can't change status from '{complaint.status}' to '{new_status}'.", "danger")
        return back

    is_progress = new_status == complaint.status        # Working On It -> Working On It
    if is_progress and len(note) < 5:
        flash("A progress update needs a short note saying what was done.", "danger")
        return back
    if new_status == ComplaintStatus.FIXED and current_user.role == ROLE_STAFF and not has_photo:
        flash("Please attach a photo as proof that it's fixed.", "danger")
        return back

    try:
        photo_name = save_complaint_photo(photo_file)
    except ValueError as e:
        flash(str(e), "danger")
        return back

    complaint.status = new_status
    complaint.resolved_at = datetime.now() if new_status == ComplaintStatus.FIXED else None
    if new_status == ComplaintStatus.FIXED:
        complaint.escalated_at = None                    # a new fix answers the escalation

    if is_progress:
        message = f"Progress update: {note}"
    else:
        message = f"Status changed to {new_status}." + (f" {note}" if note else "")
    log_update(complaint, message, photo=photo_name)
    db.session.commit()
    flash("Progress update posted." if is_progress else f"Status updated to '{new_status}'.", "success")
    return back


# ---------------------------------------------------------------- escalate (resident)
@bp.route("/complaints/<int:complaint_id>/escalate", methods=["POST"])
@role_required(ROLE_RESIDENT)
def complaint_escalate(complaint_id):
    complaint = get_complaint_or_404(complaint_id)
    back = redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))
    ok, why = can_escalate(current_user, complaint)
    if not ok:
        flash(why or "You can't report this complaint right now.", "warning")
        return back

    reason = request.form.get("reason", "").strip()[:400]
    if len(reason) < 10:
        flash("Please explain what's still wrong (at least 10 characters).", "danger")
        return back

    try:
        photo_name = save_complaint_photo(request.files.get("photo"))
    except ValueError as e:
        flash(str(e), "danger")
        return back

    was_fixed = complaint.status == ComplaintStatus.FIXED
    if was_fixed:                                        # the fix didn't work -> reopen
        complaint.status = ComplaintStatus.WORKING
        complaint.resolved_at = None
    complaint.escalated_at = datetime.now()
    complaint.escalation_count += 1
    prefix = "Reopened, not actually fixed" if was_fixed else "Reported no progress"
    log_update(complaint, f"{prefix}: {reason}", photo=photo_name, kind="escalation")
    db.session.commit()
    flash("Reported to the admin. They'll follow it up.", "success")
    return back


# ---------------------------------------------------------------- protected photo
@bp.route("/complaints/photo/<path:filename>")
@login_required
def complaint_photo(filename):
    # The photo may belong to the complaint itself OR to one of its updates.
    complaint = db.session.execute(
        db.select(Complaint).filter_by(photo_filename=filename)).scalar_one_or_none()
    if complaint is None:
        update = db.session.execute(
            db.select(ComplaintUpdate).filter_by(photo_filename=filename)).scalar_one_or_none()
        complaint = update.complaint if update else None
    if complaint is None or not can_view(current_user, complaint):
        abort(404)
    # send_from_directory refuses paths like ../../config.py
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
