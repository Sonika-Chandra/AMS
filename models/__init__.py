# Import every model here so db.create_all() knows about all tables.
from models.user import User, Flat, ROLE_RESIDENT, ROLE_GUARD, ROLE_ADMIN, ROLE_STAFF  # noqa: F401
from models.complaint import (  # noqa: F401
    Complaint, ComplaintCategory, StaffAssignment, ComplaintUpdate, ComplaintStatus,
)
from models.billing import Bill, BillItem, Payment, Receipt, BillStatus, ItemType  # noqa: F401
