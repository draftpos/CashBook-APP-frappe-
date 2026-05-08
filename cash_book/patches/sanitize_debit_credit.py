import frappe
from frappe.utils import flt

def execute():
    if not frappe.db.table_exists("Cash Book Account"):
        return

    # Fetch all records to sanitize debit and credit strings before they are converted to Decimal
    entries = frappe.db.sql("""
        SELECT name, debit, credit 
        FROM `tabCash Book Account`
    """, as_dict=1)

    for d in entries:
        # flt() converts empty strings or None to 0.0
        new_debit = flt(d.debit)
        new_credit = flt(d.credit)
        
        # Update with cleaned numeric strings
        frappe.db.sql("""
            UPDATE `tabCash Book Account` 
            SET debit = %s, credit = %s 
            WHERE name = %s
        """, (str(new_debit), str(new_credit), d.name))

    frappe.db.commit()
