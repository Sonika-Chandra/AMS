# seed.py — sample data so you can demo Person 3's module immediately.
# Run:  python seed.py      (WARNING: wipes and recreates the database)
from datetime import date, timedelta

from app import app
from extensions import db
from models import (ROLE_ADMIN, ROLE_GUARD, ROLE_RESIDENT, ROLE_STAFF, Bill, BillItem,
                    ComplaintCategory, Flat, ItemType, User)

with app.app_context():
    db.drop_all()
    db.create_all()

    flats = {n: Flat(number=n) for n in ["A-101", "A-102", "B-201", "B-202"]}
    db.session.add_all(flats.values())

    def user(name, email, role, flat=None):
        u = User(name=name, email=email, role=role, flat=flat)
        u.set_password("password")
        db.session.add(u)
        return u

    user("Asha Admin", "admin@ams.test", ROLE_ADMIN)
    user("Riya Resident", "riya@ams.test", ROLE_RESIDENT, flats["A-101"])
    user("Karan Resident", "karan@ams.test", ROLE_RESIDENT, flats["A-102"])
    user("Prakash Plumber", "plumber@ams.test", ROLE_STAFF)
    user("Elina Electrician", "electrician@ams.test", ROLE_STAFF)
    user("Gopal Guard", "guard@ams.test", ROLE_GUARD)

    for name in ["Plumbing", "Electrical", "Carpentry", "Cleaning", "Other"]:
        db.session.add(ComplaintCategory(name=name))

    # One overdue bill for A-101 so the late fee can be demonstrated.
    last_month = (date.today().replace(day=1) - timedelta(days=1))
    old = Bill(flat=flats["A-101"], billing_month=last_month.strftime("%Y-%m"),
               due_date=last_month.replace(day=10))
    old.items += [BillItem(item_type=ItemType.MAINTENANCE, description="Monthly maintenance",
                           amount_paise=2500_00),
                  BillItem(item_type=ItemType.WATER, description="Water charges",
                           amount_paise=350_00)]
    db.session.add(old)

    db.session.commit()
    print("Seeded. Every account's password is: password")
    print("  admin@ams.test | riya@ams.test | karan@ams.test")
    print("  plumber@ams.test | electrician@ams.test | guard@ams.test")
