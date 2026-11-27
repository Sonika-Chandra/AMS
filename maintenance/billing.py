# maintenance/billing.py — PERSON 3: Bills & Payments routes.
#
#   URL                                   Who
#   /maintenance/bills                    resident (own flat) | admin (all)
#   /maintenance/bills/<id>               resident (own flat) | admin
#   /maintenance/bills/generate           admin  — create a month's bills for every flat
#   /maintenance/bills/<id>/pay           resident — mock payment
#   /maintenance/payments                 resident (own flat) | admin (all)
#   /maintenance/receipts/<id>            resident (own flat) | admin
from datetime import date, datetime

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from auth.decorators import role_required
from extensions import db
from maintenance import bp
from maintenance.utils import new_receipt_number, new_transaction_ref, rupees_to_paise
from models import (ROLE_ADMIN, ROLE_RESIDENT, Bill, BillItem, BillStatus, Flat,
                    ItemType, Payment, Receipt)

PAYMENT_METHODS = ["UPI (mock)", "Card (mock)", "Net banking (mock)"]


# ---------------------------------------------------------------- helpers
def can_view_bill(user, bill):
    return user.role == ROLE_ADMIN or (user.role == ROLE_RESIDENT and bill.flat_id == user.flat_id)


def get_bill_or_404(bill_id):
    bill = db.get_or_404(Bill, bill_id)
    if not can_view_bill(current_user, bill):
        abort(404)
    return bill


def apply_late_fees(bills):
    """Lazily add late fees whenever bills are looked at. No background job
    needed for a prototype: the fee appears the first time someone views an
    overdue bill (and apply_late_fee_if_due never adds it twice)."""
    fee = current_app.config["LATE_FEE_PAISE"]
    if any([b.apply_late_fee_if_due(fee) for b in bills]):   # list, not generator: apply to ALL
        db.session.commit()


# ---------------------------------------------------------------- list
@bp.route("/bills")
@role_required(ROLE_RESIDENT, ROLE_ADMIN)
def bill_list():
    query = db.select(Bill).order_by(Bill.billing_month.desc(), Bill.flat_id)

    if current_user.role == ROLE_RESIDENT:
        query = query.where(Bill.flat_id == current_user.flat_id)
    else:
        status = request.args.get("status", "")
        if status in (BillStatus.PAID, BillStatus.UNPAID):
            query = query.where(Bill.status == status)
        month = request.args.get("month", "")
        if month:
            query = query.where(Bill.billing_month == month)

    bills = db.session.execute(query).scalars().all()
    apply_late_fees(bills)

    unpaid = [b for b in bills if not b.is_paid]
    outstanding = sum(b.total_paise for b in unpaid)
    return render_template("maintenance/bill_list.html", bills=bills,
                           outstanding=outstanding, unpaid_count=len(unpaid),
                           filters=request.args)


# ---------------------------------------------------------------- detail
@bp.route("/bills/<int:bill_id>")
@role_required(ROLE_RESIDENT, ROLE_ADMIN)
def bill_detail(bill_id):
    bill = get_bill_or_404(bill_id)
    apply_late_fees([bill])
    return render_template("maintenance/bill_detail.html", bill=bill)


# ---------------------------------------------------------------- generate (admin)
@bp.route("/bills/generate", methods=["GET", "POST"])
@role_required(ROLE_ADMIN)
def bill_generate():
    flats = db.session.execute(db.select(Flat).order_by(Flat.number)).scalars().all()
    default_month = date.today().strftime("%Y-%m")

    if request.method == "POST":
        form = request.form
        errors = []
        month = form.get("billing_month", "")
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            errors.append("Billing month must look like 2026-11.")
        try:
            due = datetime.strptime(form.get("due_date", ""), "%Y-%m-%d").date()
        except ValueError:
            due = None
            errors.append("Choose a valid due date.")
        try:
            maint = rupees_to_paise(form.get("maintenance_amount", ""))
            water_default = rupees_to_paise(form.get("water_amount", "0") or "0")
        except ValueError as e:
            errors.append(str(e))

        selected_ids = {int(x) for x in form.getlist("flat_ids") if x.isdigit()}
        if not selected_ids:
            errors.append("Select at least one flat.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("maintenance/bill_generate.html", flats=flats,
                                   form=form, default_month=default_month), 400

        created, skipped = 0, []
        for flat in flats:
            if flat.id not in selected_ids:
                continue
            # Water can differ per flat (meter readings) — optional per-flat override.
            override = form.get(f"water_{flat.id}", "").strip()
            try:
                water = rupees_to_paise(override) if override else water_default
            except ValueError:
                water = water_default

            bill = Bill(flat_id=flat.id, billing_month=month, due_date=due)
            bill.items.append(BillItem(item_type=ItemType.MAINTENANCE,
                                       description="Monthly maintenance", amount_paise=maint))
            if water:
                bill.items.append(BillItem(item_type=ItemType.WATER,
                                           description="Water charges", amount_paise=water))
            # SAVEPOINT: if this one flat already has a bill for the month,
            # the unique constraint fails — undo just this bill, keep the rest.
            try:
                with db.session.begin_nested():
                    db.session.add(bill)
                created += 1
            except IntegrityError:
                skipped.append(flat.number)

        db.session.commit()
        flash(f"Created {created} bill(s) for {month}.", "success")
        if skipped:
            flash(f"Skipped (bill already exists): {', '.join(skipped)}", "warning")
        return redirect(url_for("maintenance.bill_list", month=month))

    return render_template("maintenance/bill_generate.html", flats=flats,
                           form={}, default_month=default_month)


# ---------------------------------------------------------------- mock payment
@bp.route("/bills/<int:bill_id>/pay", methods=["GET", "POST"])
@role_required(ROLE_RESIDENT)
def bill_pay(bill_id):
    bill = get_bill_or_404(bill_id)
    apply_late_fees([bill])

    if bill.is_paid:
        flash("This bill is already paid.", "info")
        return redirect(url_for("maintenance.bill_detail", bill_id=bill.id))

    if request.method == "POST":
        method = request.form.get("method", "")
        if method not in PAYMENT_METHODS:
            flash("Choose a payment method.", "danger")
            return render_template("maintenance/pay.html", bill=bill, methods=PAYMENT_METHODS), 400

        # Demo switch so you can show what a failed payment looks like.
        if request.form.get("simulate_failure"):
            flash("Payment failed (simulated). No money was taken — please try again.", "danger")
            return redirect(url_for("maintenance.bill_pay", bill_id=bill.id))

        # The amount is taken from the DATABASE, never from the form —
        # otherwise someone could edit the HTML and pay ₹1.
        payment = Payment(bill=bill, paid_by_id=current_user.id, amount_paise=bill.total_paise,
                          method=method, transaction_ref=new_transaction_ref())
        db.session.add(payment)
        db.session.flush()                      # gives payment.id before commit
        db.session.add(Receipt(payment=payment, receipt_number=new_receipt_number(payment.id)))
        bill.status = BillStatus.PAID
        db.session.commit()                     # all three changes succeed or none do

        flash("Payment successful!", "success")
        return redirect(url_for("maintenance.receipt_view", receipt_id=payment.receipt.id))

    return render_template("maintenance/pay.html", bill=bill, methods=PAYMENT_METHODS)


# ---------------------------------------------------------------- history & receipts
@bp.route("/payments")
@role_required(ROLE_RESIDENT, ROLE_ADMIN)
def payment_history():
    query = db.select(Payment).join(Bill).order_by(Payment.paid_at.desc())
    if current_user.role == ROLE_RESIDENT:
        query = query.where(Bill.flat_id == current_user.flat_id)
    payments = db.session.execute(query).scalars().all()
    total = sum(p.amount_paise for p in payments)
    return render_template("maintenance/payment_history.html", payments=payments, total=total)


@bp.route("/receipts/<int:receipt_id>")
@role_required(ROLE_RESIDENT, ROLE_ADMIN)
def receipt_view(receipt_id):
    receipt = db.get_or_404(Receipt, receipt_id)
    if not can_view_bill(current_user, receipt.payment.bill):
        abort(404)
    return render_template("maintenance/receipt.html", receipt=receipt,
                           payment=receipt.payment, bill=receipt.payment.bill)
