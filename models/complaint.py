# models/complaint.py — PERSON 3 (Helpdesk)
from datetime import datetime

from extensions import db
from models.user import ROLE_RESIDENT


class ComplaintStatus:
    """The three statuses from the spec, kept in one place so no route
    ever types the string "Working On It" by hand (typos = silent bugs)."""
    PENDING = "Pending"
    WORKING = "Working On It"
    FIXED = "Fixed"
    ALL = [PENDING, WORKING, FIXED]

    # Which status can follow which. Staff may only move a complaint
    # forward; an admin may set any status (e.g. reopen a "Fixed" one).
    # WORKING -> WORKING is allowed: that is a "progress update"
    # (same status, new note/photo), which a worker can post any number of times.
    STAFF_NEXT = {
        PENDING: [WORKING],
        WORKING: [WORKING, FIXED],
        FIXED: [],
    }


class ComplaintCategory(db.Model):
    __tablename__ = "complaint_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)   # Plumbing, Electrical...

    complaints = db.relationship("Complaint", back_populates="category")


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(255))          # None if no photo attached
    status = db.Column(db.String(20), nullable=False, default=ComplaintStatus.PENDING)

    category_id = db.Column(db.Integer, db.ForeignKey("complaint_categories.id"), nullable=False)
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    raised_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    resolved_at = db.Column(db.DateTime)

    # Escalation: set when a resident reports "no progress"; cleared when
    # the admin re-assigns or the job is marked Fixed again.
    escalated_at = db.Column(db.DateTime)
    escalation_count = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship("ComplaintCategory", back_populates="complaints")
    flat = db.relationship("Flat")
    raised_by = db.relationship("User", foreign_keys=[raised_by_id])

    # Newest first, so assignments[0] is the current assignee.
    assignments = db.relationship(
        "StaffAssignment", back_populates="complaint",
        order_by="StaffAssignment.assigned_at.desc()",
        cascade="all, delete-orphan",
    )
    updates = db.relationship(
        "ComplaintUpdate", back_populates="complaint",
        order_by="ComplaintUpdate.created_at",
        cascade="all, delete-orphan",
    )

    @property
    def assigned_staff(self):
        """The staff member currently responsible, or None."""
        return self.assignments[0].staff if self.assignments else None

    @property
    def is_escalated(self):
        return self.escalated_at is not None

    @property
    def last_progress_at(self):
        """When staff/admin last did anything on this complaint.
        Resident messages (like an escalation) don't count as progress."""
        times = [u.created_at for u in self.updates if u.author.role != ROLE_RESIDENT]
        return max(times, default=self.created_at)

    @property
    def fix_proof(self):
        """The newest update that marked it Fixed AND has a photo, or None."""
        proofs = [u for u in self.updates
                  if u.status == ComplaintStatus.FIXED and u.photo_filename and u.kind == "update"]
        return proofs[-1] if proofs else None

    def __repr__(self):
        return f"<Complaint #{self.id} {self.status}>"


class StaffAssignment(db.Model):
    """Who was assigned to a complaint, by whom, and when.
    Re-assigning adds a new row instead of overwriting, so history is kept."""
    __tablename__ = "staff_assignments"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.String(255))
    assigned_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    complaint = db.relationship("Complaint", back_populates="assignments")
    # Two foreign keys point at users, so SQLAlchemy needs to be told which is which.
    staff = db.relationship("User", foreign_keys=[staff_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])


class ComplaintUpdate(db.Model):
    """A timeline entry: every status change or assignment is logged here,
    so the resident can see *what happened*, not just the latest status."""
    __tablename__ = "complaint_updates"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20))                   # status after this update
    message = db.Column(db.String(500), nullable=False)
    photo_filename = db.Column(db.String(255))          # progress / proof-of-fix photo
    kind = db.Column(db.String(20), nullable=False, default="update")   # "update" | "escalation"
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    complaint = db.relationship("Complaint", back_populates="updates")
    author = db.relationship("User")
