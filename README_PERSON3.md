# AMS – Person 3: Helpdesk, Maintenance & Payments

## Run it
```bash
pip install -r requirements.txt
python seed.py          # creates instance/ams.db with demo data (wipes old data!)
python app.py           # open http://127.0.0.1:5000
```
Every demo account's password is `password`:
`admin@ams.test`, `riya@ams.test` (A-101), `karan@ams.test` (A-102),
`plumber@ams.test`, `electrician@ams.test`, `guard@ams.test`.

## What is mine vs shared
| Person 3 (mine) | Shared stubs (Person 4 replaces these) |
|---|---|
| `models/complaint.py`, `models/billing.py` | `app.py`, `config.py`, `extensions.py` |
| `maintenance/` (blueprint, routes, utils) | `models/user.py` (User, Flat) |
| `templates/maintenance/*` | `auth/` (login, `role_required`) |
| `static/js/maintenance.js`, `static/css/maintenance.css` | `templates/base.html`, `home.html`, `error.html`, `static/css/base.css` |

To integrate, Person 4 needs to: register `maintenance.bp`, keep `User.role`, `User.flat_id` and
`Flat.number`, include `maintenance.css` + `maintenance.js` in `base.html`, and add the
`UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH`, `ALLOWED_IMAGE_EXTENSIONS` and `LATE_FEE_PAISE` config values.

## Routes (all under /maintenance)
| Method | URL | Role |
|---|---|---|
| GET | /complaints | resident (own flat), staff (assigned), admin (all) |
| GET/POST | /complaints/new | resident |
| GET | /complaints/<id> | allowed viewer |
| POST | /complaints/<id>/assign | admin |
| POST | /complaints/<id>/status | admin, assigned staff |
| GET | /complaints/photo/<file> | allowed viewer |
| GET | /bills | resident, admin |
| GET | /bills/<id> | resident (own), admin |
| GET/POST | /bills/generate | admin |
| GET/POST | /bills/<id>/pay | resident (own) |
| GET | /payments | resident, admin |
| GET | /receipts/<id> | resident (own), admin |

## For Person 4's admin dashboard
```python
from models import Complaint, ComplaintStatus, Bill, BillStatus, Payment
unresolved = db.session.scalar(db.select(db.func.count(Complaint.id)).where(Complaint.status != ComplaintStatus.FIXED))
unpaid_bills = db.session.scalars(db.select(Bill).where(Bill.status == BillStatus.UNPAID)).all()
collected_paise = db.session.scalar(db.select(db.func.coalesce(db.func.sum(Payment.amount_paise), 0)))
```

## Known limitations
- No CSRF protection on forms (add Flask-WTF's `CSRFProtect` once the team agrees).
- Payment is simulated; Razorpay test mode would replace `bill_pay`.
- Late fees are added when an overdue bill is first viewed, not by a scheduled job.
- No partial payments: a bill is paid in full or not at all.
