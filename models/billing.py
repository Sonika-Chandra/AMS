# models/billing.py — PERSON 3 (Bills & Payments)
#
# MONEY IS STORED AS WHOLE PAISE (integers), never as floats.
#   0.1 + 0.2 == 0.30000000000000004 in floating point, which is unacceptable
#   for money. ₹1,250.50 is stored as 125050. Templates turn it back into
#   rupees with the `rupees` filter (see maintenance/utils.py).
from datetime import datetime, date

from extensions import db


class BillStatus:
    UNPAID = "Unpaid"
    PAID = "Paid"


class ItemType:
    MAINTENANCE = "Maintenance"
    WATER = "Water"
    LATE_FEE = "Late fee"


class Bill(db.Model):
    """One bill per flat per month. The amount lives in its BillItems."""
    __tablename__ = "bills"
    __table_args__ = (
        # The database itself refuses a second bill for the same flat+month.
        db.UniqueConstraint("flat_id", "billing_month", name="uq_bill_flat_month"),
    )
    id = db.Column(db.Integer, primary_key=True)
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    billing_month = db.Column(db.String(7), nullable=False)        # "2026-11"
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default=BillStatus.UNPAID)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    flat = db.relationship("Flat")
    items = db.relationship("BillItem", back_populates="bill",
                            cascade="all, delete-orphan", order_by="BillItem.id")
    payments = db.relationship("Payment", back_populates="bill",
                               order_by="Payment.paid_at.desc()")

    # ---------- computed values (not stored, always correct) ----------
    @property
    def total_paise(self):
        return sum(item.amount_paise for item in self.items)

    @property
    def is_paid(self):
        return self.status == BillStatus.PAID

    @property
    def is_overdue(self):
        return not self.is_paid and date.today() > self.due_date

    @property
    def has_late_fee(self):
        return any(i.item_type == ItemType.LATE_FEE for i in self.items)

    @property
    def month_label(self):
        """'2026-11' -> 'November 2026'"""
        return datetime.strptime(self.billing_month, "%Y-%m").strftime("%B %Y")

    # ---------- behaviour ----------
    def apply_late_fee_if_due(self, fee_paise):
        """Add ONE late-fee line if the bill is overdue. Safe to call many
        times: it never adds a second late fee. Returns True if it added one."""
        if self.is_overdue and not self.has_late_fee and fee_paise > 0:
            self.items.append(BillItem(
                item_type=ItemType.LATE_FEE,
                description=f"Late fee (due {self.due_date.strftime('%d %b %Y')})",
                amount_paise=fee_paise,
            ))
            return True
        return False


class BillItem(db.Model):
    __tablename__ = "bill_items"
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False)
    item_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(120), nullable=False)
    amount_paise = db.Column(db.Integer, nullable=False)

    bill = db.relationship("Bill", back_populates="items")


class Payment(db.Model):
    """A (mock) payment against a bill. In the prototype every recorded
    payment is successful — a failed mock payment is simply not saved."""
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False)
    paid_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount_paise = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(30), nullable=False)           # "UPI (mock)" ...
    transaction_ref = db.Column(db.String(40), unique=True, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    bill = db.relationship("Bill", back_populates="payments")
    paid_by = db.relationship("User")
    receipt = db.relationship("Receipt", back_populates="payment", uselist=False)  # one-to-one


class Receipt(db.Model):
    __tablename__ = "receipts"
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), unique=True, nullable=False)
    receipt_number = db.Column(db.String(30), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    payment = db.relationship("Payment", back_populates="receipt")
